# bot/handlers/admin/admin_panel.py
from html import escape
import logging
import math
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.filters.role import RoleFilter
from db.models import UserRole, User, Request # <-- Импортируем Request
# Импорты для показа списков
from db.crud import (
    get_all_in_progress_requests, get_all_users, get_archived_requests,
    get_request_by_id, get_user, set_user_role # <-- Импортируем get_request_by_id
)
from bot.keyboards.inline.admin_inline import (
    get_admin_main_menu, AdminActiveNavCallback, create_admin_active_requests_keyboard,
    AdminUserManageCallback, create_admin_users_list_keyboard, create_admin_user_profile_keyboard
)
from bot.keyboards.reply import ADMIN_PANEL_BTN_TEXT
from bot.keyboards.inline.requests_inline import (
    # --- ИЗМЕНЕНО: Добавляем RequestActionCallback ---
    HistoryNavigationCallback, RequestActionCallback, create_archive_requests_keyboard
)

# Константы пагинации
ADMIN_USERS_PAGE_SIZE = 3
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

# --- ОБРАБОТЧИКИ КНОПОК ГЛАВНОГО МЕНЮ АДМИНКИ И ПАГИНАЦИИ ---

# --- Управление пользователями ---
# Этот хендлер теперь обрабатывает и первый вход (page=0), и пагинацию
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

    # Коррекция страницы, если она стала недоступной (например, после удаления пользователя)
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
    except TelegramBadRequest: pass # Сообщение не изменилось
    except Exception as e: logging.error(f"Error editing message for user list: {e}", exc_info=True)

# --- Активные заявки ---
# Этот хендлер обрабатывает и первый вход (page=0), и пагинацию
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

    # Коррекция страницы
    if current_page >= total_pages and current_page > 0:
        current_page = max(0, total_pages - 1)
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
        # --- ИЗМЕНЕНО: Проверяем, отличается ли клавиатура перед редактированием ---
        if callback.message and callback.message.reply_markup != keyboard:
             await callback.message.edit_text(text, reply_markup=keyboard)
        elif callback.message and callback.message.text != text: # Или если изменился только текст
             await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        logging.debug("Admin active page: Message not modified.")
        pass
    except Exception as e:
        logging.error(f"Error editing message for admin active pagination: {e}", exc_info=True)

    await callback.answer()

# --- История выполненных ---
# Этот хендлер обрабатывает и первый вход (page=0), и пагинацию
@router.callback_query(HistoryNavigationCallback.filter(F.action == "page"))
async def cq_admin_history_page(callback: types.CallbackQuery, callback_data: HistoryNavigationCallback, session: AsyncSession):
    user_id = callback.from_user.id
    current_page = callback_data.page
    current_sort = callback_data.sort_by
    # Проверяем, пришел ли коллбэк от админа (должен, т.к. фильтр роли на роутере)
    # Это нужно, чтобы убедиться, что мы показываем ВСЮ историю, а не историю инженера
    db_user = await get_user(session, user_id)
    is_admin = db_user and db_user.role == UserRole.ADMIN

    if not is_admin:
         logging.warning(f"Non-admin user {user_id} tried to access admin history view.")
         await callback.answer("Доступ запрещен.", show_alert=True)
         return

    logging.info(f"Admin {user_id} requested ALL history page {current_page} (sort: {current_sort}).")

    if current_page < 0: await callback.answer(); return
    offset = current_page * ADMIN_HISTORY_PAGE_SIZE

    # Вызываем CRUD для ВСЕХ архивных заявок (без engineer_id)
    archived_requests, total_count = await get_archived_requests(
        session=session,
        limit=ADMIN_HISTORY_PAGE_SIZE,
        offset=offset,
        sort_by=current_sort
    )
    total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    # Коррекция страницы
    if current_page >= total_pages and current_page > 0:
        current_page = max(0, total_pages - 1)
        offset = current_page * ADMIN_HISTORY_PAGE_SIZE
        archived_requests, total_count = await get_archived_requests(
             session, ADMIN_HISTORY_PAGE_SIZE, offset, current_sort
        )
        total_pages = math.ceil(total_count / ADMIN_HISTORY_PAGE_SIZE) if total_count > 0 else 0

    keyboard = create_archive_requests_keyboard(
         archived_requests, current_page, total_pages, current_sort,
         user_role=UserRole.ADMIN # Передаем роль для кнопки "Назад в меню"
    )
    text = f"📚 История выполненных (Всего: {total_count}):"

    try:
        # --- ИЗМЕНЕНО: Проверяем, отличается ли клавиатура перед редактированием ---
        if callback.message and callback.message.reply_markup != keyboard:
             await callback.message.edit_text(text, reply_markup=keyboard)
        elif callback.message and callback.message.text != text: # Или если изменился только текст
             await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
         logging.debug("Admin history page: Message not modified.")
         pass
    except Exception as e: logging.error(f"Error editing message for admin history pagination: {e}", exc_info=True)

    await callback.answer()


# --- Просмотр профиля пользователя ---
@router.callback_query(AdminUserManageCallback.filter(F.action == "view"))
async def cq_admin_view_user(callback: types.CallbackQuery, callback_data: AdminUserManageCallback, session: AsyncSession):
    target_user_id = callback_data.user_id
    # --- ИЗМЕНЕНО: Получаем страницу списка, с которой пришли ---
    current_list_page = callback_data.page
    admin_id = callback.from_user.id
    logging.info(f"Admin {admin_id} viewing profile for user {target_user_id} (from list page {current_list_page}).")

    user = await get_user(session, target_user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        # Возможно, стоит обновить список пользователей, если мы отсюда пришли
        # await cq_admin_users_list(callback, AdminUserManageCallback(action="list_page", page=current_list_page), session)
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

    # --- ИЗМЕНЕНО: Передаем страницу списка в клавиатуру ---
    keyboard = create_admin_user_profile_keyboard(user, current_list_page)

    await callback.answer()
    try:
        # Редактируем сообщение (список пользователей)
        await callback.message.edit_text(profile_text, reply_markup=keyboard)
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for user profile view: {e}", exc_info=True)


# --- Смена роли пользователя ---
@router.callback_query(AdminUserManageCallback.filter(F.action == "set_role"))
async def cq_admin_set_role(callback: types.CallbackQuery, callback_data: AdminUserManageCallback, session: AsyncSession):
    target_user_id = callback_data.user_id
    new_role_str = callback_data.new_role
    # --- ИЗМЕНЕНО: Получаем страницу списка, с которой пришли ---
    current_list_page = callback_data.page
    admin_id = callback.from_user.id

    # Преобразуем строку роли обратно в Enum
    try:
        new_role_enum = UserRole(new_role_str)
    except ValueError:
        logging.error(f"Invalid role string '{new_role_str}' received in set_role callback.")
        await callback.answer("❌ Некорректная роль указана.", show_alert=True)
        return

    if target_user_id == admin_id and new_role_enum != UserRole.ADMIN:
        await callback.answer("❌ Нельзя изменить свою роль с админа на другую через кнопки.", show_alert=True)
        return

    logging.info(f"Admin {admin_id} trying to set role {new_role_enum.value} for user {target_user_id}.")

    updated_user = await set_user_role(session, target_user_id, new_role_enum)

    if updated_user:
        logging.info(f"Role for user {target_user_id} set to {new_role_enum.value} by admin {admin_id}.")
        await callback.answer(f"✅ Роль пользователя обновлена на '{new_role_enum.value}'!", show_alert=False)

        # --- ИЗМЕНЕНО: Создаем новый callback_data с сохраненной страницей ---
        # Передаем user_id и page для обновления профиля
        view_callback_data = AdminUserManageCallback(action="view", user_id=target_user_id, page=current_list_page)
        # Обновляем сообщение с профилем, чтобы показать новую роль и кнопки
        # Передаем новый callback_data в хендлер просмотра
        await cq_admin_view_user(callback, view_callback_data, session)

    else:
        logging.error(f"Failed to set role {new_role_enum.value} for user {target_user_id}.")
        await callback.answer("❌ Не удалось обновить роль пользователя. Ошибка БД.", show_alert=True)


# --- Просмотр деталей активной заявки АДМИНОМ ---
@router.callback_query(RequestActionCallback.filter(F.action == "view_active"))
async def cq_admin_view_active_request(callback: types.CallbackQuery, callback_data: RequestActionCallback, session: AsyncSession):
    request_id = callback_data.request_id
    admin_id = callback.from_user.id
    logging.info(f"Admin {admin_id} viewing active request ID: {request_id}")

    request = await get_request_by_id(session, request_id) # Нужна функция для получения одной заявки

    if not request:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return
    if request.status != 'in_progress': # Проверка, что она все еще активна
        await callback.answer("⚠️ Заявка уже не активна (возможно, завершена или отменена).", show_alert=True)
        # Можно добавить обновление списка активных заявок
        return

    # Формирование текста деталей заявки (можно вынести в отдельную функцию)
    engineer_name = f"{request.engineer.first_name} {request.engineer.last_name}".strip() if request.engineer else "Не назначен"
    client_name = f"{request.requester.first_name} {request.requester.last_name}".strip() if request.requester else f"ID:{request.requester_id}"
    created_at = request.created_at.strftime('%Y-%m-%d %H:%M') if request.created_at else "N/A"
    accepted_at = request.accepted_at.strftime('%Y-%m-%d %H:%M') if request.accepted_at else "N/A"
    location = f"{request.building}, каб. {request.room}"

    pc_text = f"\n<b>ПК/Инв. номер:</b> {escape(request.pc_number)}" if request.pc_number else ""
    phone_text = f"\n<b>Телефон:</b> {escape(request.contact_phone)}" if request.contact_phone else ""

    details_text = (
        f"<b>Заявка #{request.id} (Активная)</b>\n\n"
        f"<b>Статус:</b> В работе 🛠️\n"
        f"<b>Клиент:</b> {escape(client_name)}\n"
        f"<b>Место:</b> {escape(location)}{pc_text}{phone_text}\n"
        f"<b>Инженер:</b> {escape(engineer_name)}\n"
        f"<b>Создана:</b> {created_at}\n"
        f"<b>Принята:</b> {accepted_at}\n\n"
        f"<b>Описание:</b>\n{escape(request.description or 'Нет описания')}"
    )

    # Клавиатура для админа при просмотре активной заявки (пока только "Назад")
    # Можно добавить кнопки типа "Переназначить", "Отменить" и т.д.
    builder = InlineKeyboardBuilder()
    # Кнопка "Назад к списку активных" - нужно знать страницу и сортировку
    # Пока сделаем возврат в главное меню для простоты
    builder.button(text="⬅️ Назад в меню", callback_data="admin_back_to_main")
    keyboard = builder.as_markup()

    await callback.answer()
    try:
        await callback.message.edit_text(details_text, reply_markup=keyboard)
    except TelegramBadRequest: pass
    except Exception as e: logging.error(f"Error editing message for admin view active request {request_id}: {e}", exc_info=True)


# --- Возврат в главное меню админки ---
@router.callback_query(F.data == "admin_back_to_main")
async def cq_admin_back_to_main(callback: types.CallbackQuery):
    logging.info(f"Admin {callback.from_user.id} requested back to main admin menu.")
    await callback.answer()
    try:
        await callback.message.edit_text("🔑 Админ-панель:", reply_markup=get_admin_main_menu())
    except TelegramBadRequest:
        logging.debug("Back to main menu: Message not modified.")
        pass
    except Exception as e:
        logging.error(f"Error editing message to admin main menu: {e}", exc_info=True)


# --- Игнорируемые колбэки ---
@router.callback_query(F.data.startswith("ignore_"))
async def cq_admin_ignore(callback: types.CallbackQuery):
    # Просто отвечаем на коллбэк, чтобы убрать "часики"
    await callback.answer()


# --- Удалены старые хендлеры, которые ловили строковые callback_data ---
# @router.callback_query(F.data == "admin_manage_users") ...
# @router.callback_query(F.data == "admin_view_active") ...
# @router.callback_query(F.data == "admin_view_history") ...