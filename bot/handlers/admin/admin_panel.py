# bot/handlers/admin/admin_panel.py
from html import escape
import logging
import math
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from bot.gpt.yagpt_integration import enable_gpt, disable_gpt, get_gpt_status

from bot.filters.role import RoleFilter
from db.models import UserRole, User
# Импорты для показа списков
from db.crud import get_all_in_progress_requests, get_all_users, get_archived_requests, get_user, set_user_role
from bot.keyboards.inline.admin_inline import (
    get_admin_main_menu, AdminActiveNavCallback, create_admin_active_requests_keyboard,
    AdminUserManageCallback, create_admin_users_list_keyboard, create_admin_user_profile_keyboard # <--- Новые импорты
)
from bot.keyboards.reply import ADMIN_PANEL_BTN_TEXT
from bot.keyboards.inline.requests_inline import (
    HistoryNavigationCallback, create_archive_requests_keyboard # Для истории
)

# Константы пагинации
ADMIN_USERS_PAGE_SIZE = 10 # Пагинация для пользователей
ADMIN_ACTIVE_PAGE_SIZE = 10
ADMIN_HISTORY_PAGE_SIZE = 10


router = Router()
# Применяем фильтр Админа ко всем хендлерам этого роутера
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))

# --- Вход в админ-панель ---
@router.message(Command("admin"))
@router.message(F.text == ADMIN_PANEL_BTN_TEXT)
async def cmd_admin(message: types.Message):
    await message.answer("🔑 Админ-панель:", reply_markup=get_admin_main_menu())

# --- Обработка кнопок главного меню админки ---

@router.callback_query(F.data == "admin_manage_users")
async def cq_admin_manage_users(callback: types.CallbackQuery):
    # Используем ИСПРАВЛЕННЫЙ текст с < и >
    text = (
        "👥 Управление инженерами:\n\n"
        "🔹 `/list_engineers` - Показать список текущих инженеров\n"
        "🔹 `/add_engineer <ID пользователя>` - Назначить пользователя инженером\n"
        "🔹 `/remove_engineer <ID пользователя>` - Разжаловать инженера до клиента\n\n"
        "<i>Примечание:</i> ID пользователя можно узнать, например, с помощью @userinfobot, "
        "попросив нужного человека переслать сообщение от этого бота."
    )
    await callback.answer()
    try:
        # --- ОТПРАВЛЯЕМ БЕЗ PARSE_MODE ---
        await callback.message.answer(text, parse_mode=None)
        logging.info("Sent admin manage users text with parse_mode=None")
        # ----------------------------------
    except Exception as e:
        logging.error(f"Error sending admin manage users text (parse_mode=None): {e}", exc_info=True)
        await callback.message.answer("Ошибка отображения инструкций.")

        
@router.callback_query(F.data == "admin_view_active")
async def cq_admin_view_active(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    logging.info(f"Admin {user_id} requested active requests page 0.")
    current_page = 0
    current_sort = 'accepted_asc' # Сортировка по умолчанию для активных
    offset = current_page * ADMIN_ACTIVE_PAGE_SIZE

    active_requests, total_count = await get_all_in_progress_requests(
        session, limit=ADMIN_ACTIVE_PAGE_SIZE, offset=offset, sort_by=current_sort
    )
    total_pages = math.ceil(total_count / ADMIN_ACTIVE_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_admin_active_requests_keyboard(
        active_requests, current_page, total_pages, current_sort
    )
    text = f"🛠️ Активные заявки (Всего: {total_count}):"

    await callback.answer()
    # Редактируем сообщение, в котором была нажата кнопка "Активные заявки"
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest: # Сообщение не изменилось
        pass
    except Exception as e:
         logging.error(f"Error editing message for admin active requests: {e}", exc_info=True)

# --- Обработчик кнопки "История выполненных" АДМИНОМ ---
@router.callback_query(F.data == "admin_view_history")
async def cq_admin_view_history(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    logging.info(f"Admin {user_id} requested ALL history page 0.")
    current_page = 0
    current_sort = 'date_desc'
    offset = current_page * ADMIN_HISTORY_PAGE_SIZE

    # --- ВЫЗЫВАЕМ CRUD БЕЗ engineer_id ---
    archived_requests, total_count = await get_archived_requests(
        session=session,
        limit=ADMIN_HISTORY_PAGE_SIZE,
        offset=offset,
        sort_by=current_sort
        # engineer_id НЕ передается
    )
    # -----------------------------------
    total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_archive_requests_keyboard(
         archived_requests, current_page, total_pages, current_sort,
         user_role=UserRole.ADMIN # Передаем роль для кнопки "Назад в меню"
    )
    text = f"📚 История выполненных (Всего: {total_count}):" # Текст для админа

    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for admin history view: {e}")


# --- Обработчик пагинации истории АДМИНОМ ---
@router.callback_query(HistoryNavigationCallback.filter(F.action == "page"))
async def cq_admin_history_page(callback: types.CallbackQuery, callback_data: HistoryNavigationCallback, session: AsyncSession):
    user_id = callback.from_user.id
    current_page = callback_data.page
    current_sort = callback_data.sort_by
    logging.info(f"Admin {user_id} requested ALL history page {current_page} (sort: {current_sort}).")

    if current_page < 0: await callback.answer(); return
    offset = current_page * ADMIN_HISTORY_PAGE_SIZE

    # --- ВЫЗЫВАЕМ CRUD БЕЗ engineer_id ---
    archived_requests, total_count = await get_archived_requests(
        session=session,
        limit=ADMIN_HISTORY_PAGE_SIZE,
        offset=offset,
        sort_by=current_sort
        # engineer_id НЕ передается
    )
    # -----------------------------------
    total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    # Коррекция страницы
    if current_page >= total_pages and current_page > 0:
        current_page = max(0, total_pages - 1)
        offset = current_page * ADMIN_HISTORY_PAGE_SIZE
        # Повторный вызов без engineer_id
        archived_requests, total_count = await get_archived_requests(
             session, ADMIN_HISTORY_PAGE_SIZE, offset, current_sort
        )
        total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_archive_requests_keyboard(
         archived_requests, current_page, total_pages, current_sort,
         user_role=UserRole.ADMIN # Передаем роль для кнопки "Назад в меню"
    )
    text = f"📚 История выполненных (Всего: {total_count}):" # Текст для админа

    try:
        if callback.message and callback.message.reply_markup != keyboard:
             await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for admin history pagination: {e}")

    await callback.answer()

# --- Хендлеры для пагинации списков админа ---

@router.callback_query(AdminActiveNavCallback.filter(F.action == "page"))
async def cq_admin_active_page(callback: types.CallbackQuery, callback_data: AdminActiveNavCallback, session: AsyncSession):
    user_id = callback.from_user.id
    current_page = callback_data.page
    current_sort = callback_data.sort_by
    logging.info(f"Admin {user_id} requested active requests page {current_page} (sort: {current_sort}).")

    if current_page < 0:
        await callback.answer()
        return

    offset = current_page * ADMIN_ACTIVE_PAGE_SIZE
    active_requests, total_count = await get_all_in_progress_requests(
        session, limit=ADMIN_ACTIVE_PAGE_SIZE, offset=offset, sort_by=current_sort
    )
    total_pages = math.ceil(total_count / ADMIN_ACTIVE_PAGE_SIZE) if total_count > 0 else 0

    # Коррекция страницы, если она стала недоступной
    if current_page >= total_pages and current_page > 0:
        current_page = max(0, total_pages - 1) # Переходим на последнюю доступную или 0
        offset = current_page * ADMIN_ACTIVE_PAGE_SIZE
        active_requests, total_count = await get_all_in_progress_requests(
             session, limit=ADMIN_ACTIVE_PAGE_SIZE, offset=offset, sort_by=current_sort
        )
        total_pages = math.ceil(total_count / ADMIN_ACTIVE_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_admin_active_requests_keyboard(
        active_requests, current_page, total_pages, current_sort
    )
    text = f"🛠️ Активные заявки (Всего: {total_count}):"

    try:
        if callback.message and callback.message.reply_markup != keyboard:
             await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass
    except Exception as e:
        logging.error(f"Error editing message for admin active pagination: {e}", exc_info=True)

    await callback.answer()


@router.callback_query(AdminUserManageCallback.filter(F.action == "list_page"))
async def cq_admin_users_list(callback: types.CallbackQuery, callback_data: AdminUserManageCallback, session: AsyncSession):
    current_page = callback_data.page
    user_id = callback.from_user.id
    logging.info(f"Admin {user_id} requested users list page {current_page}.")

    if current_page < 0: # Защита
        await callback.answer()
        return

    offset = current_page * ADMIN_USERS_PAGE_SIZE
    users, total_count = await get_all_users(session, limit=ADMIN_USERS_PAGE_SIZE, offset=offset)
    total_pages = math.ceil(total_count / ADMIN_USERS_PAGE_SIZE) if total_count > 0 else 0

    # Коррекция страницы
    if current_page >= total_pages and current_page > 0:
        current_page = max(0, total_pages - 1)
        offset = current_page * ADMIN_USERS_PAGE_SIZE
        users, total_count = await get_all_users(session, limit=ADMIN_USERS_PAGE_SIZE, offset=offset)
        total_pages = math.ceil(total_count / ADMIN_USERS_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_admin_users_list_keyboard(users, current_page, total_pages)
    text = f"👥 Пользователи (Всего: {total_count}):"

    await callback.answer()
    try:
        # Редактируем исходное сообщение (меню админки или другую страницу списка)
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for user list: {e}")

# Просмотр профиля пользователя
@router.callback_query(AdminUserManageCallback.filter(F.action == "view"))
async def cq_admin_view_user(callback: types.CallbackQuery, callback_data: AdminUserManageCallback, session: AsyncSession):
    target_user_id = callback_data.user_id
    admin_id = callback.from_user.id
    logging.info(f"Admin {admin_id} viewing profile for user {target_user_id}.")

    user = await get_user(session, target_user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    # Формируем текст профиля
    role_map = {UserRole.ADMIN: "👑 Администратор", UserRole.ENGINEER: "🛠️ Инженер", UserRole.CLIENT: "👤 Клиент"}
    role_text = role_map.get(user.role, "Неизвестно")
    user_name = f"{escape(user.first_name or '')} {escape(user.last_name or '')}".strip()
    user_mention = f"@{escape(user.username)}" if user.username else "Нет"
    reg_date = user.registered_at.strftime('%Y-%m-%d %H:%M') if user.registered_at else "Неизвестно"

    profile_text = (
        f"👤 <b>Профиль пользователя</b>\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Имя:</b> {user_name or 'Не указано'}\n"
        f"<b>Username:</b> {user_mention}\n"
        f"<b>Текущая роль:</b> {role_text}\n"
        f"<b>Дата регистрации:</b> {reg_date}\n\n"
        f"Выберите действие:"
    )

    keyboard = create_admin_user_profile_keyboard(user)

    await callback.answer()
    try:
        # Редактируем сообщение (список пользователей)
        await callback.message.edit_text(profile_text, reply_markup=keyboard)
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for user profile view: {e}")


# Смена роли пользователя
@router.callback_query(AdminUserManageCallback.filter(F.action == "set_role"))
async def cq_admin_set_role(callback: types.CallbackQuery, callback_data: AdminUserManageCallback, session: AsyncSession):
    target_user_id = callback_data.user_id
    new_role_str = callback_data.new_role
    admin_id = callback.from_user.id

    # Преобразуем строку роли обратно в Enum
    try:
        new_role_enum = UserRole(new_role_str)
    except ValueError:
        logging.error(f"Invalid role string '{new_role_str}' received in set_role callback.")
        await callback.answer("❌ Некорректная роль указана.", show_alert=True)
        return

    # Небольшая защита от случайного разжалования себя
    if target_user_id == admin_id and new_role_enum != UserRole.ADMIN:
        await callback.answer("❌ Нельзя изменить свою роль с админа на другую через кнопки.", show_alert=True)
        return

    logging.info(f"Admin {admin_id} trying to set role {new_role_enum.value} for user {target_user_id}.")

    # Используем существующую CRUD функцию
    updated_user = await set_user_role(session, target_user_id, new_role_enum)

    if updated_user:
        logging.info(f"Role for user {target_user_id} set to {new_role_enum.value} by admin {admin_id}.")
        await callback.answer(f"✅ Роль пользователя обновлена на '{new_role_enum.value}'!", show_alert=False) # Краткий ответ

        # Обновляем сообщение с профилем, чтобы показать новую роль и кнопки
        await cq_admin_view_user(callback, callback_data, session) # Вызываем хендлер просмотра профиля заново

    else:
        logging.error(f"Failed to set role {new_role_enum.value} for user {target_user_id}.")
        await callback.answer("❌ Не удалось обновить роль пользователя. Ошибка БД.", show_alert=True)

@router.callback_query(F.data == "admin_back_to_main")
async def cq_admin_back_to_main(callback: types.CallbackQuery):
    logging.info(f"Admin {callback.from_user.id} requested back to main admin menu.") # Добавим лог
    await callback.answer() # Отвечаем на коллбэк
    try:
        # Редактируем текущее сообщение (список пользователей) на главное меню
        await callback.message.edit_text("🔑 Админ-панель:", reply_markup=get_admin_main_menu())
    except TelegramBadRequest:
        # Может возникнуть, если сообщение не изменилось (уже главное меню?)
        logging.warning("Back to main menu: Message not modified.")
        pass
    except Exception as e:
        logging.error(f"Error editing message to admin main menu: {e}", exc_info=True)
        # Можно отправить новое сообщение, если редактирование не удалось
        await callback.message.answer("Не удалось вернуться в меню.")

# Обработчики для игнорируемых кнопок (можно в общем роутере или здесь)
@router.callback_query(F.data.startswith("ignore_"))
async def cq_admin_ignore(callback: types.CallbackQuery):
    await callback.answer()

@router.message(Command("gpt_on"))
async def cmd_gpt_on(message: types.Message):
    if enable_gpt():
        await message.answer("✅ Интеграция с YandexGPT **включена**.")
    else:
         await message.answer("⚠️ Не удалось включить YandexGPT. Проверьте наличие API-ключа и Folder ID в конфигурации.")

@router.message(Command("gpt_off"))
async def cmd_gpt_off(message: types.Message):
    disable_gpt()
    await message.answer("☑️ Интеграция с YandexGPT **отключена**.")

@router.message(Command("gpt_status"))
async def cmd_gpt_status(message: types.Message):
    status = "🟢 Включена" if get_gpt_status() else "🔴 Отключена"
    await message.answer(f"Статус интеграции с YandexGPT: {status}")