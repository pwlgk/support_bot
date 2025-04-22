# bot/handlers/engineer/manage_requests.py
from html import escape
import logging
import math
from aiogram import Router, types, F, Bot # Добавляем Bot для уведомлений
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramBadRequest 
# Фильтр ролей и модель роли
from bot.filters.role import RoleFilter
from bot.handlers.admin.admin_panel import ADMIN_HISTORY_PAGE_SIZE
from db.models import RequestStatus, UserRole
# Текст кнопки из reply клавиатуры
from bot.keyboards.reply import (VIEW_NEW_REQUESTS_BTN_TEXT,
                                 MY_ASSIGNED_REQUESTS_BTN_TEXT, HISTORY_BTN_TEXT) # Обновлено
# --- ОБНОВИТЬ ИМПОРТЫ CRUD ---
from db.crud import (get_new_requests, get_request, accept_request, get_user,
                     get_engineer_requests, complete_request,
                     get_archived_requests) # Убран archive_old_completed_requests
# --- Импорты клавиатур остаются прежними ---
from bot.keyboards.inline.requests_inline import (
    HistoryNavigationCallback, RequestActionCallback, create_new_requests_keyboard, create_view_request_keyboard,
    create_in_progress_requests_keyboard, create_complete_request_keyboard,
    create_archive_requests_keyboard # Эта функция нужна для просмотра истории
)
HISTORY_PAGE_SIZE = 5

router = Router()
# Применяем фильтр ко всем хендлерам в этом роутере
router.message.filter(RoleFilter(UserRole.ENGINEER))
router.callback_query.filter(RoleFilter(UserRole.ENGINEER))

# --- Хендлер для отображения новых заявок ---
@router.message(F.text == VIEW_NEW_REQUESTS_BTN_TEXT)
@router.message(Command('view_new_requests'))
async def view_new_requests(message: types.Message, session: AsyncSession):
    logging.info(f"Engineer {message.from_user.id} requested new requests.")
    new_requests = await get_new_requests(session)

    if not new_requests:
        await message.answer("✅ Новых заявок нет.")
        return

    # Создаем клавиатуру со списком заявок
    keyboard = create_new_requests_keyboard(new_requests)
    await message.answer(
        f"📋 Найдены новые заявки ({len(new_requests)} шт.):",
        reply_markup=keyboard
    )

# --- Хендлер для коллбэка просмотра деталей заявки ---
@router.callback_query(RequestActionCallback.filter(F.action.in_(["view", "view_my", "view_archive"])))
async def cq_view_request_details(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession):
    request_id = callback_data.request_id
    current_user_id = callback.from_user.id
    action_type = callback_data.action
    logging.info(f"User {current_user_id} viewing request #{request_id} (action: {action_type})")

    request = await get_request(session, request_id)

    if not request:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    # --- Формирование текста (остается почти таким же) ---
    engineer_name = f"{escape(request.engineer.first_name or '')} (ID: {request.engineer.id})" if request.engineer else "Не назначен"
    requester_info = f"{escape(request.requester.first_name or '')} (@{escape(request.requester.username or '')})" if request.requester.username else f"{escape(request.requester.first_name or '')} (ID: {request.requester_id})"
    status_map = {
        RequestStatus.WAITING: "⏳ Ожидает", RequestStatus.IN_PROGRESS: "🛠️ В работе",
        RequestStatus.COMPLETED: "✅ Выполнена", RequestStatus.ARCHIVED: "🗄️ В архиве (Выполнена)",
        RequestStatus.CANCELED: "❌ Отменена",
    }
    status_text = status_map.get(request.status, f"Неизвестный ({escape(request.status.value)})")
    pc_text = f"<b>ПК/Инв.:</b> {escape(request.pc_number)}\n" if request.pc_number else ""

    details_text = (
        f"📄 <b>Заявка #{request.id}</b>\n"
        f"<b>Статус:</b> {status_text}\n"
        f"<b>Создана:</b> {request.created_at.strftime('%Y-%m-%d %H:%M') if request.created_at else 'N/A'}\n\n"
        f"<b>Заявитель:</b> {requester_info}\n"
        f"<b>ФИО:</b> {escape(request.full_name or 'Не указано')}\n"
        f"<b>Телефон:</b> {escape(request.contact_phone or 'Не указан')}\n\n"
        f"<b>Место:</b> Корпус {escape(request.building)}, Каб. {escape(request.room)}\n"
        f"{pc_text}" # Инв. номер (уже содержит тег <b>)
        f"----------------------------\n"
        f"<b>Описание проблемы:</b>\n{escape(request.description)}\n"
        f"----------------------------\n"
        f"<b>Принята:</b> {request.accepted_at.strftime('%Y-%m-%d %H:%M') if request.accepted_at else '-'}\n"
        f"<b>Исполнитель:</b> {engineer_name}\n"
        f"<b>Завершена:</b> {request.completed_at.strftime('%Y-%m-%d %H:%M') if request.completed_at else '-'}\n"
        f"<b>Архивирована:</b> {request.archived_at.strftime('%Y-%m-%d %H:%M') if request.archived_at else '-'}\n"
    )
    # --- Определяем клавиатуру ---
    keyboard = None
    if action_type == "view" and request.status == RequestStatus.WAITING:
        keyboard = create_view_request_keyboard(request_id)
    elif action_type == "view_my" and request.status == RequestStatus.IN_PROGRESS and request.engineer_id == current_user_id:
        keyboard = create_complete_request_keyboard(request_id)
    # Если action == 'view_archive' или другие статусы - клавиатура не нужна (keyboard = None)

    await callback.answer()
    # Отправляем новое сообщение (проще, чем редактировать списки)
    await callback.message.answer(details_text, reply_markup=keyboard)

# --- Хендлер для коллбэка принятия заявки ---
@router.callback_query(RequestActionCallback.filter(F.action == "accept"))
async def cq_accept_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession, bot: Bot):
     # ... (код остается прежним) ...
    request_id = callback_data.request_id
    engineer_id = callback.from_user.id
    logging.info(f"Engineer {engineer_id} trying to accept request #{request_id}")

    updated_request = await accept_request(session, request_id, engineer_id)

    if updated_request:
        # ... (логирование, ответ коллбэку) ...
        logging.info(f"Request #{request_id} accepted by engineer {engineer_id}")
        await callback.answer("✅ Заявка принята в работу!", show_alert=True)

        # Обновляем сообщение с деталями заявки
        final_request = await get_request(session, request_id)
        # ... (формирование updated_details_text как раньше) ...
        engineer_name = f"{final_request.engineer.first_name} (ID: {final_request.engineer.id})" if final_request.engineer else "Ошибка"
        requester_info = f"{final_request.requester.first_name} (@{final_request.requester.username})" if final_request.requester.username else f"{final_request.requester.first_name} (ID: {final_request.requester_id})"
        status_map = { # Дублируем маппинг статусов
            RequestStatus.WAITING: "⏳ Ожидает", RequestStatus.IN_PROGRESS: "🛠️ В работе",
            RequestStatus.COMPLETED: "✅ Выполнена", RequestStatus.ARCHIVED: "🗄️ В архиве",
            RequestStatus.CANCELED: "❌ Отменена",
        }
        status_text = status_map.get(final_request.status, f"Неизвестный ({final_request.status.value})")
        updated_details_text = (
            f"📄 Заявка #{final_request.id}\n"
            f"Статус: {status_text}\n"
            f"Создана: {final_request.created_at.strftime('%Y-%m-%d %H:%M') if final_request.created_at else 'N/A'}\n"
            f"Заявитель: {requester_info}\n"
            f"----------------------------\n"
            f"Описание:\n{final_request.description}\n"
            f"----------------------------\n"
            f"<b>Место:</b> Корпус {escape(final_request.building)}, Каб. {escape(final_request.room)}\n"
            f"Контактный телефон: {final_request.contact_phone or 'Не указан'}\n"
            f"----------------------------\n"
            f"Принята: {final_request.accepted_at.strftime('%Y-%m-%d %H:%M') if final_request.accepted_at else '-'}\n"
            f"Исполнитель: {engineer_name}\n"
            f"Завершена: {final_request.completed_at.strftime('%Y-%m-%d %H:%M') if final_request.completed_at else '-'}\n"
        )
        try:
            await callback.message.edit_text(updated_details_text, reply_markup=None) # Убираем кнопки
        except Exception as e:
            logging.error(f"Failed to edit message after accepting request {request_id}: {e}")
            await callback.message.answer("Заявка принята. Не удалось обновить предыдущее сообщение.")

        # --- Отправка уведомления клиенту ---
        client_id = updated_request.requester_id
        engineer_user = await get_user(session, engineer_id)
        if client_id and engineer_user:
            try:
                await bot.send_message(
                    chat_id=client_id,
                    text=f"🔔 Ваша заявка №{request_id} принята в работу инженером {engineer_user.first_name}."
                )
                logging.info(f"Sent notification to client {client_id} about request {request_id} acceptance.")
            except Exception as e:
                logging.error(f"Failed to send notification to client {client_id} for request {request_id}: {e}")
    else:
        # ... (обработка ошибки принятия) ...
        logging.warning(f"Engineer {engineer_id} failed to accept request #{request_id} (possibly already taken).")
        await callback.answer("❌ Не удалось принять заявку. Возможно, ее уже взял другой инженер.", show_alert=True)
        # ... (обновление сообщения об ошибке как раньше) ...
        try:
            request_info = await get_request(session, request_id)
            if request_info and request_info.status != RequestStatus.WAITING:
                 await callback.message.edit_text(f"Заявка #{request_id} уже находится в статусе '{status_map.get(request_info.status, request_info.status.value)}'.", reply_markup=None)
            else:
                 await callback.message.edit_text(f"Не удалось обновить статус заявки #{request_id}.", reply_markup=None)
        except Exception as e:
            logging.error(f"Failed to edit message after failed acceptance for request {request_id}: {e}")


# --- НОВЫЙ: Хендлер для завершения заявки ---
@router.callback_query(RequestActionCallback.filter(F.action == "complete"))
async def cq_complete_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession, bot: Bot):
    request_id = callback_data.request_id
    engineer_id = callback.from_user.id
    # --- ОБНОВЛЕННЫЙ ЛОГ ---
    logging.info(f"Engineer {engineer_id} trying to complete and archive request #{request_id}")

    # Вызываем обновленную функцию complete_request, которая сразу архивирует
    completed_db_request = await complete_request(session, request_id, engineer_id)

    if completed_db_request:
        # --- ОБНОВЛЕННЫЙ ЛОГ И ОТВЕТ ---
        logging.info(f"Request #{request_id} completed and archived by engineer {engineer_id}")
        await callback.answer("✅ Заявка выполнена и перемещена в историю!", show_alert=True) # Обновлен текст ответа

        # Обновляем сообщение с деталями, статус будет ARCHIVED
        engineer_name = f"{completed_db_request.engineer.first_name} (ID: {completed_db_request.engineer.id})" if completed_db_request.engineer else "Ошибка"
        requester_info = f"{completed_db_request.requester.first_name} (@{completed_db_request.requester.username})" if completed_db_request.requester.username else f"{completed_db_request.requester.first_name} (ID: {completed_db_request.requester_id})"
        status_map = {
            RequestStatus.WAITING: "⏳ Ожидает", RequestStatus.IN_PROGRESS: "🛠️ В работе",
            RequestStatus.COMPLETED: "✅ Выполнена", # Не используется
            RequestStatus.ARCHIVED: "🗄️ В архиве (Выполнена)", # Используем этот текст
            RequestStatus.CANCELED: "❌ Отменена",
        }
        status_text = status_map.get(completed_db_request.status, f"Неизвестный ({completed_db_request.status.value})")

        final_details_text = (
            f"📄 Заявка #{completed_db_request.id}\n"
            f"Статус: {status_text}\n" # Будет "В архиве (Выполнена)"
            f"Создана: {completed_db_request.created_at.strftime('%Y-%m-%d %H:%M') if completed_db_request.created_at else 'N/A'}\n"
            f"Заявитель: {requester_info}\n"
            f"----------------------------\n"
            f"Описание:\n{completed_db_request.description}\n"
            f"----------------------------\n"
            f"<b>Место:</b> Корпус {escape(completed_db_request.building)}, Каб. {escape(completed_db_request.room)}\n"
            f"Контактный телефон: {completed_db_request.contact_phone or 'Не указан'}\n"
            f"----------------------------\n"
            f"Принята: {completed_db_request.accepted_at.strftime('%Y-%m-%d %H:%M') if completed_db_request.accepted_at else '-'}\n"
            f"Исполнитель: {engineer_name}\n"
            f"Завершена: {completed_db_request.completed_at.strftime('%Y-%m-%d %H:%M') if completed_db_request.completed_at else 'Только что'}\n"
            f"Архивирована: {completed_db_request.archived_at.strftime('%Y-%m-%d %H:%M') if completed_db_request.archived_at else 'Только что'}\n"
        )
        try:
            # Убираем кнопку "Выполнено"
            await callback.message.edit_text(final_details_text, reply_markup=None)
        except Exception as e:
            logging.error(f"Failed to edit message after completing/archiving request {request_id}: {e}")
            await callback.message.answer("Заявка выполнена и архивирована. Не удалось обновить предыдущее сообщение.")

        # --- Отправка уведомления клиенту (текст без изменений) ---
        client_id = completed_db_request.requester_id
        if client_id:
            try:
                await bot.send_message(
                    chat_id=client_id,
                    text=f"🎉 Ваша заявка №{request_id} была выполнена!"
                )
                logging.info(f"Sent completion notification to client {client_id} for request {request_id}.")
            except Exception as e:
                logging.error(f"Failed to send completion notification to client {client_id} for request {request_id}: {e}")

    else:
        # Обработка случая, если завершить/архивировать не удалось
        logging.warning(f"Engineer {engineer_id} failed to complete/archive request #{request_id}.")
        # (Логика обработки ошибки остается примерно такой же, как была для complete)
        current_request = await get_request(session, request_id)
        error_text = f"❌ Не удалось завершить заявку #{request_id}."
        status_map = { # Нужен маппинг и здесь
            RequestStatus.WAITING: "⏳ Ожидает", RequestStatus.IN_PROGRESS: "🛠️ В работе",
            RequestStatus.COMPLETED: "✅ Выполнена", RequestStatus.ARCHIVED: "🗄️ В архиве (Выполнена)",
            RequestStatus.CANCELED: "❌ Отменена",
        }
        if current_request:
            if current_request.status != RequestStatus.IN_PROGRESS:
                error_text += f" Текущий статус: '{status_map.get(current_request.status, current_request.status.value)}'."
            elif current_request.engineer_id != engineer_id:
                error_text += " Она назначена на другого инженера."
            else:
                 error_text += " Неизвестная причина."
        else:
            error_text += " Заявка не найдена."

        await callback.answer(error_text, show_alert=True)
        try:
             await callback.message.edit_text(error_text, reply_markup=None)
        except Exception as e:
             logging.error(f"Failed to edit message after failed completion/archiving for request {request_id}: {e}")


# Хендлер для игнорирования пустого архива/истории остается
@router.callback_query(F.data == "ignore_empty_archive")
async def cq_ignore_empty(callback: types.CallbackQuery):
    await callback.answer()

@router.message(F.text == VIEW_NEW_REQUESTS_BTN_TEXT)
@router.message(Command('view_new_requests'))
async def view_new_requests_handler(message: types.Message, session: AsyncSession):
    # ... (код остается прежним) ...
    logging.info(f"Engineer {message.from_user.id} requested new requests.")
    new_requests = await get_new_requests(session)
    if not new_requests:
        await message.answer("✅ Новых заявок нет.")
        return
    keyboard = create_new_requests_keyboard(new_requests)
    await message.answer(
        f"📋 Найдены новые заявки ({len(new_requests)} шт.):",
        reply_markup=keyboard
    )

# --- НОВЫЙ: Хендлер для СВОИХ заявок В РАБОТЕ ---
@router.message(F.text == MY_ASSIGNED_REQUESTS_BTN_TEXT)
@router.message(Command('my_requests'))
async def view_my_requests_handler(message: types.Message, session: AsyncSession):
    engineer_id = message.from_user.id
    logging.info(f"Engineer {engineer_id} requested their assigned requests.")
    in_progress_requests = await get_engineer_requests(session, engineer_id)

    if not in_progress_requests:
        await message.answer("👍 У вас нет заявок в работе.")
        return

    keyboard = create_in_progress_requests_keyboard(in_progress_requests)
    await message.answer(
        f"🛠️ Ваши заявки в работе ({len(in_progress_requests)} шт.):",
        reply_markup=keyboard
    )


@router.message(F.text == HISTORY_BTN_TEXT)
@router.message(Command('archive')) # или /history
async def view_history_handler(message: types.Message, session: AsyncSession):
    engineer_id = message.from_user.id # <-- Получаем ID инженера
    logging.info(f"Engineer {engineer_id} requested THEIR history page 0 (default sort).")
    current_page = 0
    current_sort = 'date_desc'
    offset = current_page * ADMIN_HISTORY_PAGE_SIZE # Используем ту же константу или свою

    # --- ВЫЗЫВАЕМ CRUD С engineer_id ---
    archived_requests, total_count = await get_archived_requests(
        session=session,
        limit=ADMIN_HISTORY_PAGE_SIZE,
        offset=offset,
        sort_by=current_sort,
        engineer_id=engineer_id # <-- Передаем ID
    )
    # -----------------------------------
    total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_archive_requests_keyboard(
        requests=archived_requests,
        current_page=current_page,
        total_pages=total_pages,
        current_sort=current_sort
        # Не передаем user_role=UserRole.ADMIN
    )
    count_text = f" (Найдено: {total_count})" if total_count > 0 else ""
    await message.answer(
        f"📚 История выполненных вами заявок{count_text}:", # Обновляем текст
        reply_markup=keyboard
    )

# --- Хендлер для пагинации истории ИНЖЕНЕРОМ ---
# Применяем фильтр по роли инженера
@router.callback_query(RoleFilter(UserRole.ENGINEER), HistoryNavigationCallback.filter(F.action == "page"))
async def cq_engineer_history_page_handler(callback: types.CallbackQuery, callback_data: HistoryNavigationCallback, session: AsyncSession):
     engineer_id = callback.from_user.id # <-- Получаем ID инженера
     current_page = callback_data.page
     current_sort = callback_data.sort_by
     logging.info(f"Engineer {engineer_id} requested THEIR history page {current_page} (sort: {current_sort}).")

     if current_page < 0: await callback.answer(); return
     offset = current_page * ADMIN_HISTORY_PAGE_SIZE

     # --- ВЫЗЫВАЕМ CRUD С engineer_id ---
     archived_requests, total_count = await get_archived_requests(
         session=session,
         limit=ADMIN_HISTORY_PAGE_SIZE,
         offset=offset,
         sort_by=current_sort,
         engineer_id=engineer_id # <-- Передаем ID
     )
     # -----------------------------------
     total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

     # Коррекция страницы
     if current_page >= total_pages and current_page > 0:
         current_page = max(0, total_pages - 1)
         offset = current_page * ADMIN_HISTORY_PAGE_SIZE
         # Повторный вызов с engineer_id
         archived_requests, total_count = await get_archived_requests(
              session, ADMIN_HISTORY_PAGE_SIZE, offset, current_sort, engineer_id=engineer_id
         )
         total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

     keyboard = create_archive_requests_keyboard(
          archived_requests, current_page, total_pages, current_sort
          # Не передаем user_role=UserRole.ADMIN
     )
     text = f"📚 История выполненных вами заявок (Всего: {total_count}):" # Обновляем текст

     try:
         if callback.message and callback.message.reply_markup != keyboard:
              await callback.message.edit_text(text, reply_markup=keyboard)
     except TelegramBadRequest: pass
     except Exception as e: logging.error(f"Error editing message for engineer history pagination: {e}")

     await callback.answer()

# --- Добавляем обработчики для игнорируемых кнопок пагинации ---
@router.callback_query(F.data.startswith("ignore_"))
async def cq_ignore_pagination(callback: types.CallbackQuery):
    await callback.answer()

