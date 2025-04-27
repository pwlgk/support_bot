# bot/handlers/engineer/manage_requests.py
import logging
import math
from html import escape
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

# Фильтр ролей и модель роли
from bot.filters.role import RoleFilter
from db.models import UserRole, RequestStatus

# Текст кнопок из reply клавиатуры
from bot.keyboards.reply import (
    VIEW_NEW_REQUESTS_BTN_TEXT, MY_ASSIGNED_REQUESTS_BTN_TEXT, HISTORY_BTN_TEXT
)

# CRUD функции
from db.crud import (
    get_new_requests, get_request, accept_request, get_user,
    get_engineer_requests, complete_request, get_archived_requests
)

# Клавиатуры и CallbackData
from bot.keyboards.inline.requests_inline import (
    create_new_requests_keyboard, create_view_request_keyboard,
    create_complete_request_keyboard, RequestActionCallback,
    create_archive_requests_keyboard, HistoryNavigationCallback,
    create_engineer_active_requests_keyboard, EngActiveNavCallback
)
# Импорт главного меню инженера
from bot.keyboards.inline.engineer_inline import get_engineer_main_menu

# Константы пагинации
ENG_ACTIVE_PAGE_SIZE = 5 
ENG_HISTORY_PAGE_SIZE = 5 

router = Router()

router.message.filter(RoleFilter(UserRole.ENGINEER))
router.callback_query.filter(RoleFilter(UserRole.ENGINEER))

# --- Главное меню инженера (для кнопки Назад) ---
@router.callback_query(F.data == "back_to_main_menu_eng")
async def back_to_main_menu_eng(callback: types.CallbackQuery):
    """Возвращает пользователя в главное меню инженера."""
    await callback.answer()
    try:
        if callback.message:
            await callback.message.edit_text(
                "Главное меню Инженера:",
                reply_markup=get_engineer_main_menu()
            )
    except TelegramBadRequest: pass
    except Exception as e:
        logging.error(f"Error showing engineer main menu: {e}", exc_info=True)
        try:
            # Отправляем новое сообщение, если редактирование не удалось
            await callback.message.answer("Главное меню Инженера:", reply_markup=get_engineer_main_menu())
        except Exception as e2:
             logging.error(f"Failed to send engineer main menu as new message: {e2}", exc_info=True)

# --- Просмотр НОВЫХ заявок ---
@router.message(F.text == VIEW_NEW_REQUESTS_BTN_TEXT)
@router.message(Command('view_new_requests'))
@router.callback_query(F.data == "eng_view_new") # Для кнопки "Назад к новым"
async def view_new_requests(event: types.Message | types.CallbackQuery, session: AsyncSession):
    """Показывает список новых заявок (без пагинации)."""
    user_id = event.from_user.id
    logging.info(f"Engineer {user_id} requested new requests list.")
    new_requests = await get_new_requests(session)

    text = "📝 Новые заявки, ожидающие принятия:"
    keyboard = create_new_requests_keyboard(new_requests)
    if not new_requests:
        text = "✅ Новых заявок нет."
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))
        keyboard = builder.as_markup()

    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=keyboard)
    elif isinstance(event, types.CallbackQuery) and event.message:
        await event.answer() 
        try:
            await event.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest: pass
        except Exception as e: logging.error(f"Error editing message for new requests view: {e}", exc_info=True)


@router.message(F.text == MY_ASSIGNED_REQUESTS_BTN_TEXT)
@router.message(Command('my_requests'))
async def view_my_active_requests_first(message: types.Message, session: AsyncSession):
    """Показывает первую страницу активных заявок инженера."""
    engineer_id = message.from_user.id
    logging.info(f"Engineer {engineer_id} requested own active requests FIRST page (default sort).")
    current_page = 0
    current_sort = 'accepted_asc' # Сортировка по умолчанию
    offset = current_page * ENG_ACTIVE_PAGE_SIZE

    # Используем обновленный CRUD с пагинацией
    active_requests, total_count = await get_engineer_requests(
        session=session, engineer_id=engineer_id, limit=ENG_ACTIVE_PAGE_SIZE,
        offset=offset, sort_by=current_sort
    )
    total_pages = math.ceil(total_count / ENG_ACTIVE_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_engineer_active_requests_keyboard(
        active_requests, current_page, total_pages, current_sort
    )
    text = f"🛠️ Мои заявки в работе (Всего: {total_count}):"
    if total_count == 0:
        text = "👍 У вас нет заявок в работе."
        # Клавиатура уже содержит кнопку "Главное меню"

    await message.answer(text, reply_markup=keyboard)

# Обработчик для пагинации активных заявок
@router.callback_query(EngActiveNavCallback.filter(F.action == "page"))
async def view_my_active_requests_page(callback: types.CallbackQuery, callback_data: EngActiveNavCallback, session: AsyncSession):
    """Обрабатывает пагинацию списка активных заявок инженера."""
    engineer_id = callback.from_user.id
    current_page = callback_data.page
    current_sort = callback_data.sort_by
    logging.info(f"Engineer {engineer_id} requested own active requests page {current_page} (sort: {current_sort}).")

    if current_page < 0: await callback.answer(); return

    offset = current_page * ENG_ACTIVE_PAGE_SIZE
    active_requests, total_count = await get_engineer_requests(
        session=session, engineer_id=engineer_id, limit=ENG_ACTIVE_PAGE_SIZE,
        offset=offset, sort_by=current_sort
    )
    total_pages = math.ceil(total_count / ENG_ACTIVE_PAGE_SIZE) if total_count > 0 else 0

    # Коррекция страницы (если последняя страница опустела)
    if current_page >= total_pages and current_page > 0:
        current_page = max(0, total_pages - 1)
        offset = current_page * ENG_ACTIVE_PAGE_SIZE
        active_requests, total_count = await get_engineer_requests(
             session, engineer_id, ENG_ACTIVE_PAGE_SIZE, offset, current_sort
        )
        # Пересчитываем total_pages после коррекции
        total_pages = math.ceil(total_count / ENG_ACTIVE_PAGE_SIZE) if total_count > 0 else 0


    keyboard = create_engineer_active_requests_keyboard(
        active_requests, current_page, total_pages, current_sort
    )
    text = f"🛠️ Мои заявки в работе (Всего: {total_count}):"
    if total_count == 0 and current_page == 0: # Если последняя заявка была завершена
         text = "👍 У вас больше нет заявок в работе."

    await callback.answer()
    try:
        if callback.message:
            # Редактируем только если текст или клавиатура изменились
            if callback.message.text != text or callback.message.reply_markup != keyboard:
                 await callback.message.edit_text(text, reply_markup=keyboard)
            else:
                 logging.debug("Engineer active page: Message not modified.")
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for engineer active pagination: {e}", exc_info=True)


# --- Просмотр ИСТОРИИ выполненных заявок (С ПАГИНАЦИЕЙ) ---
# Обработчик для первого входа (по кнопке/команде)
@router.message(F.text == HISTORY_BTN_TEXT)
@router.message(Command('archive')) # или /history
async def view_history_first(message: types.Message, session: AsyncSession):
    """Показывает первую страницу истории заявок инженера."""
    engineer_id = message.from_user.id
    logging.info(f"Engineer {engineer_id} requested THEIR history FIRST page (default sort).")
    current_page = 0
    current_sort = 'date_desc' # Сортировка по умолчанию
    offset = current_page * ENG_HISTORY_PAGE_SIZE

    # Используем CRUD с пагинацией и фильтром по инженеру
    archived_requests, total_count = await get_archived_requests(
        session=session, engineer_id=engineer_id, # Передаем ID инженера
        limit=ENG_HISTORY_PAGE_SIZE, offset=offset, sort_by=current_sort
    )
    total_pages = math.ceil(total_count / ENG_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_archive_requests_keyboard(
         archived_requests, current_page, total_pages, current_sort,
         user_role=UserRole.ENGINEER # Передаем роль для кнопки Назад
    )
    text = f"📚 История выполненных вами заявок (Всего: {total_count}):"
    if total_count == 0:
         text = "🗄️ Ваша история выполненных заявок пока пуста."

    await message.answer(text, reply_markup=keyboard)

# Обработчик для пагинации истории инженером
@router.callback_query(HistoryNavigationCallback.filter(F.action == "page"))
async def view_history_page(callback: types.CallbackQuery, callback_data: HistoryNavigationCallback, session: AsyncSession):
    """Обрабатывает пагинацию истории заявок инженера."""
    engineer_id = callback.from_user.id
    current_page = callback_data.page
    current_sort = callback_data.sort_by
    logging.info(f"Engineer {engineer_id} requested own history page {current_page} (sort: {current_sort}).")


    if current_page < 0: await callback.answer(); return

    offset = current_page * ENG_HISTORY_PAGE_SIZE
    archived_requests, total_count = await get_archived_requests(
        session=session, engineer_id=engineer_id, # Передаем ID инженера
        limit=ENG_HISTORY_PAGE_SIZE, offset=offset, sort_by=current_sort
    )
    total_pages = math.ceil(total_count / ENG_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    # Коррекция страницы
    if current_page >= total_pages and current_page > 0:
        current_page = max(0, total_pages - 1)
        offset = current_page * ENG_HISTORY_PAGE_SIZE
        archived_requests, total_count = await get_archived_requests(
             session, engineer_id=engineer_id, limit=ENG_HISTORY_PAGE_SIZE, offset=offset, sort_by=current_sort
        )
        total_pages = math.ceil(total_count / ENG_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_archive_requests_keyboard(
         archived_requests, current_page, total_pages, current_sort,
         user_role=UserRole.ENGINEER # Передаем роль для кнопки Назад
    )
    text = f"📚 История выполненных вами заявок (Всего: {total_count}):"
    if total_count == 0 and current_page == 0:
         text = "🗄️ Ваша история выполненных заявок пуста."

    await callback.answer()
    try:
        if callback.message:
             if callback.message.text != text or callback.message.reply_markup != keyboard:
                  await callback.message.edit_text(text, reply_markup=keyboard)
             else:
                  logging.debug("Engineer history page: Message not modified.")
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for engineer history pagination: {e}", exc_info=True)



async def show_request_details(
    callback: types.CallbackQuery,
    request_id: int,
    session: AsyncSession,
    view_mode: str 
):
    """Отображает детали заявки и соответствующие кнопки."""
    user_id = callback.from_user.id
    logging.info(f"Engineer {user_id} viewing request {request_id} in mode '{view_mode}'")

    request = await get_request(session, request_id)
    if not request:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        # Пытаемся обновить список, из которого пришел пользователь
        if view_mode == 'new':
            await view_new_requests(callback, session)
        try:
            if callback.message: await callback.message.delete() 
        except Exception: pass
        return

    # Формирование текста (остается прежним)
    status_map = {
        RequestStatus.WAITING: "⏳ Ожидает принятия",
        RequestStatus.IN_PROGRESS: "🛠️ В работе",
        RequestStatus.ARCHIVED: "✅ Выполнена (в архиве)",
        RequestStatus.CANCELED: "❌ Отменена",
    }
    status_text = status_map.get(request.status, "Неизвестный статус")
    client_name = f"{request.requester.first_name or ''} {request.requester.last_name or ''}".strip()
    client_name = client_name or f"ID:{request.requester_id}"
    engineer_name = f"{request.engineer.first_name or ''} {request.engineer.last_name or ''}".strip() if request.engineer else "Не назначен"

    created_at = request.created_at.strftime('%Y-%m-%d %H:%M') if request.created_at else "N/A"
    accepted_at = request.accepted_at.strftime('%Y-%m-%d %H:%M') if request.accepted_at else "-"
    completed_at = request.completed_at.strftime('%Y-%m-%d %H:%M') if request.completed_at else "-"
    archived_at = request.archived_at.strftime('%Y-%m-%d %H:%M') if request.archived_at else "-"

    location = f"{escape(request.building)}, каб. {escape(request.room)}"
    pc_text = f"\n<b>ПК/Инв. номер:</b> {escape(request.pc_number)}" if request.pc_number else ""
    phone_text = f"\n<b>Телефон:</b> {escape(request.contact_phone)}" if request.contact_phone else ""
    full_name_text = f"\n<b>ФИО (из заявки):</b> {escape(request.full_name)}" if request.full_name else ""

    details_text_lines = [
        f"<b>Заявка #{request.id}</b>",
        f"<b>Статус:</b> {status_text}",
        f"<b>Клиент:</b> {escape(client_name)}",
        f"<b>Место:</b> {location}{pc_text}{phone_text}{full_name_text}",
        f"<b>Инженер:</b> {escape(engineer_name)}",
        f"<b>Создана:</b> {created_at}",
    ]
    # Добавляем даты только если они есть
    if request.accepted_at: details_text_lines.append(f"<b>Принята:</b> {accepted_at}")
    if request.completed_at: details_text_lines.append(f"<b>Завершена:</b> {completed_at}")
    if request.archived_at and request.status == RequestStatus.ARCHIVED:
        details_text_lines.append(f"<b>Архивирована:</b> {archived_at}")

    details_text_lines.append(f"\n<b>Описание:</b>\n{escape(request.description or 'Нет описания')}")

    text = "\n".join(details_text_lines)

    # Формируем клавиатуру
    keyboard = None
    if request.status == RequestStatus.WAITING and view_mode == 'new':
        keyboard = create_view_request_keyboard(request_id) # Кнопка "Принять" + "Назад"
    elif request.status == RequestStatus.IN_PROGRESS and view_mode == 'active_eng':
        if request.engineer_id == user_id:
             keyboard = create_complete_request_keyboard(request_id) # Кнопка "Завершить" + "Назад"
        else:
            # Инженер смотрит чужую активную заявку - только кнопка Назад
             builder = InlineKeyboardBuilder()
             builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))
             keyboard = builder.as_markup()
    elif view_mode == 'archive':
        # Для архива просто кнопка Назад в меню
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))
        keyboard = builder.as_markup()


    # Редактируем сообщение
    await callback.answer()
    try:
        if callback.message:
            if callback.message.text != text or callback.message.reply_markup != keyboard:
                 await callback.message.edit_text(text, reply_markup=keyboard)
            else:
                 logging.debug(f"Request details {request_id} message not modified.")
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for request view {request_id}: {e}", exc_info=True)


# Просмотр новой заявки (из списка view_new_requests)
@router.callback_query(RequestActionCallback.filter(F.action == "view"))
async def cq_view_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession):
    await show_request_details(callback, callback_data.request_id, session, view_mode='new')

# Принятие заявки в работу
@router.callback_query(RequestActionCallback.filter(F.action == "accept"))
async def cq_accept_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession, bot: Bot):
    engineer_id = callback.from_user.id
    request_id = callback_data.request_id
    logging.info(f"Engineer {engineer_id} trying to accept request {request_id}")

    updated_request = await accept_request(session, request_id, engineer_id)

    if updated_request:
        await callback.answer("✅ Заявка принята в работу!", show_alert=False)
        # Показываем обновленные детали заявки с кнопкой Завершить
        await show_request_details(callback, request_id, session, view_mode='active_eng')

        # Уведомление клиента
        try:
            client_text = (f"✅ Ваша заявка #{request_id} принята в работу инженером "
                           f"{updated_request.engineer.first_name if updated_request.engineer else ''}.")
            await bot.send_message(updated_request.requester_id, client_text)
            logging.info(f"Sent notification to client {updated_request.requester_id} about request {request_id} acceptance.")
        except Exception as e:
            logging.error(f"Failed to send acceptance notification to client {updated_request.requester_id}: {e}")
    else:
        await callback.answer("⚠️ Не удалось принять заявку (возможно, уже принята).", show_alert=True)
        # Обновляем список новых заявок
        try:
            if isinstance(callback, types.CallbackQuery):
                 await view_new_requests(callback, session)
        except Exception as e:
            logging.error(f"Failed to refresh new requests list after failed accept: {e}")


# Просмотр своей активной заявки (из списка view_my_active_requests_page)
@router.callback_query(RequestActionCallback.filter(F.action == "view_my"))
async def cq_view_my_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession):
    await show_request_details(callback, callback_data.request_id, session, view_mode='active_eng')

# Завершение заявки
@router.callback_query(RequestActionCallback.filter(F.action == "complete"))
async def cq_complete_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession, bot: Bot):
    engineer_id = callback.from_user.id
    request_id = callback_data.request_id
    logging.info(f"Engineer {engineer_id} trying to complete request {request_id}")

    completed_request = await complete_request(session, request_id, engineer_id)

    if completed_request:
        await callback.answer("🏁 Заявка успешно завершена и архивирована!", show_alert=False)
        # Показываем детали завершенной/архивированной заявки
        await show_request_details(callback, request_id, session, view_mode='archive')

        # Уведомление клиента
        try:
            client_text = (f"✅ Ваша заявка #{request_id} была успешно выполнена.\n"
                           "Спасибо за обращение!")
            await bot.send_message(completed_request.requester_id, client_text)
            logging.info(f"Sent notification to client {completed_request.requester_id} about request {request_id} completion.")
        except Exception as e:
            logging.error(f"Failed to send completion notification to client {completed_request.requester_id}: {e}")
    else:
        await callback.answer("⚠️ Не удалось завершить заявку (проверьте статус).", show_alert=True)
        try:
            await show_request_details(callback, request_id, session, view_mode='active_eng')
        except Exception as e:
             logging.error(f"Failed show details after failed complete: {e}")


# Просмотр архивной заявки (из списка view_history_page)
@router.callback_query(RequestActionCallback.filter(F.action == "view_archive"))
async def cq_view_archive_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession):
    await show_request_details(callback, callback_data.request_id, session, view_mode='archive')


# --- Обработчики для игнорируемых кнопок пагинации ---
@router.callback_query(F.data.startswith("ignore_"))
async def cq_ignore_pagination(callback: types.CallbackQuery):
    """Отвечает на колбэки от неактивных кнопок пагинации."""
    await callback.answer()