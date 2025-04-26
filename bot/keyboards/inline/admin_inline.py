# bot/keyboards/inline/admin_inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
# --- ИЗМЕНЕНО: импорт RequestActionCallback ---
from .requests_inline import RequestActionCallback, HistoryNavigationCallback # Добавляем HistoryNavigationCallback
from db.models import Request, User, UserRole  # Для клавиатуры активных заявок

# --- CallbackData для навигации по АКТИВНЫМ заявкам админа ---
class AdminActiveNavCallback(CallbackData, prefix="adm_act"):
    action: str # 'page' или 'sort'
    page: int
    sort_by: str # 'accepted_asc', 'created_asc', 'created_desc'

# --- CallbackData для управления пользователями админом ---
class AdminUserManageCallback(CallbackData, prefix="adm_usr"):
    action: str # 'list_page', 'view', 'set_role'
    page: int = 0 # Для пагинации списка, нужно для возврата на нужную страницу
    user_id: int = 0 # ID целевого пользователя
    new_role: str = "" # Новая роль ('admin', 'engineer', 'client')

# --- Главное меню админки ---
def get_admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="👥 Управление пользователями",
            callback_data=AdminUserManageCallback(action="list_page", page=0).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🛠️ Активные заявки",
            callback_data=AdminActiveNavCallback(action="page", page=0, sort_by='accepted_asc').pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📚 История выполненных",
            callback_data=HistoryNavigationCallback(action="page", page=0, sort_by='date_desc').pack()
        )
    )
    return builder.as_markup()

# --- Клавиатура для списка пользователей ---
def create_admin_users_list_keyboard(
    users: list[User],
    current_page: int,
    total_pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not users and current_page == 0:
        builder.button(text="Пользователи не найдены", callback_data="ignore_empty_list")
    else:
        for user in users:
            role_emoji = {
                UserRole.ADMIN: "👑", UserRole.ENGINEER: "🛠️", UserRole.CLIENT: "👤"
            }
            role_text = role_emoji.get(user.role, "❓")
            name_parts = [user.first_name, user.last_name]
            display_name = " ".join(filter(None, name_parts))
            if not display_name: display_name = f"ID:{user.id}"
            user_details = f"(@{user.username})" if user.username else f"(ID:{user.id})"
            full_display = f"{role_text} {display_name} {user_details}"
            max_len = 50
            button_text = full_display[:max_len] + "..." if len(full_display) > max_len else full_display
            builder.button(
                text=button_text,
                callback_data=AdminUserManageCallback(action="view", user_id=user.id, page=current_page).pack()
            )
        builder.adjust(1)

    # --- ИСПРАВЛЕННЫЙ БЛОК ПАГИНАЦИИ ---
    if total_pages > 0:
        pagination_row = []
        # 1. Кнопка "Назад" или заполнитель
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=AdminUserManageCallback(action="list_page", page=current_page - 1).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_prev")) # Заполнитель

        # 2. Индикатор страницы
        pagination_row.append(InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="ignore_page_indicator"
        ))

        # 3. Кнопка "Вперед" или заполнитель
        if current_page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед >",
                callback_data=AdminUserManageCallback(action="list_page", page=current_page + 1).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_next")) # Заполнитель

        builder.row(*pagination_row) # Добавляем ряд из 3х кнопок
    elif total_pages == 0 and current_page == 0: # Если список изначально пуст
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))
    # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))
    return builder.as_markup()

# --- Клавиатура для профиля пользователя (смена роли) ---
def create_admin_user_profile_keyboard(user: User, current_list_page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    user_id = user.id
    callback_params = {"user_id": user_id, "page": current_list_page}

    if user.role != UserRole.ADMIN:
        builder.button(text="👑 Назначить Админом", callback_data=AdminUserManageCallback(
            action="set_role", new_role=UserRole.ADMIN.value, **callback_params).pack())
    if user.role != UserRole.ENGINEER:
        builder.button(text="🛠️ Назначить Инженером", callback_data=AdminUserManageCallback(
            action="set_role", new_role=UserRole.ENGINEER.value, **callback_params).pack())
    if user.role != UserRole.CLIENT:
        builder.button(text="👤 Сделать Клиентом", callback_data=AdminUserManageCallback(
            action="set_role", new_role=UserRole.CLIENT.value, **callback_params).pack())

    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад к списку",
        callback_data=AdminUserManageCallback(action="list_page", page=current_list_page).pack()
    ))
    return builder.as_markup()


# --- Клавиатура для списка АКТИВНЫХ заявок (с пагинацией) ---
def create_admin_active_requests_keyboard(
    requests: list[Request],
    current_page: int,
    total_pages: int,
    current_sort: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not requests and current_page == 0:
        builder.button(text="Нет активных заявок", callback_data="ignore_empty_list")
    else:
        for req in requests:
            engineer_info = f" ({req.engineer.first_name})" if req.engineer and req.engineer.first_name else ""
            req_date = req.accepted_at or req.created_at
            date_str = req_date.strftime('%d.%m') if req_date else '??.??'
            button_text = f"#{req.id} ({date_str}{engineer_info}) {req.description or 'Без описания'}"
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text
            builder.button(
                text=button_text,
                callback_data=RequestActionCallback(action="view_active", request_id=req.id).pack()
            )
        builder.adjust(1)

    # --- ИСПРАВЛЕННЫЙ БЛОК ПАГИНАЦИИ ---
    if total_pages > 0:
        pagination_row = []
        # 1. Кнопка "Назад" или заполнитель
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=AdminActiveNavCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_prev"))

        # 2. Индикатор страницы
        pagination_row.append(InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="ignore_page_indicator"
        ))

        # 3. Кнопка "Вперед" или заполнитель
        if current_page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед >",
                callback_data=AdminActiveNavCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_next"))

        builder.row(*pagination_row)
    elif total_pages == 0 and current_page == 0:
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))
    # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))
    return builder.as_markup()


# bot/keyboards/inline/requests_inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Request, UserRole

# --- CallbackData для действий с заявками ---
class RequestActionCallback(CallbackData, prefix="req"):
    action: str # 'view', 'accept', 'complete', 'view_my', 'view_archive', 'view_active'
    request_id: int

# --- CallbackData для навигации по истории ---
class HistoryNavigationCallback(CallbackData, prefix="hist"):
    action: str # 'page', 'sort'
    page: int
    sort_by: str

# --- Клавиатура для списка НОВЫХ заявок---
def create_new_requests_keyboard(requests: list[Request]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not requests:
        builder.button(text="Нет новых заявок", callback_data="ignore_empty_new")
    else:
        for req in requests:
            builder.button(
                text=f"#{req.id} - {req.description[:30]}...",
                callback_data=RequestActionCallback(action="view", request_id=req.id).pack()
            )
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для списка СВОИХ заявок В РАБОТЕ ---
def create_in_progress_requests_keyboard(requests: list[Request]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not requests:
        builder.button(text="Нет заявок в работе", callback_data="ignore_empty_inprogress")
    else:
        for req in requests:
            client_name = req.requester.first_name if req.requester and req.requester.first_name else f"ID:{req.requester_id}"
            button_text = f"#{req.id} - {client_name} - {req.description[:25]}..."
            builder.button(
                text=button_text,
                callback_data=RequestActionCallback(action="view_my", request_id=req.id).pack()
            )
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра деталей НОВОЙ заявки (инженером) ---
def create_view_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять в работу",
        callback_data=RequestActionCallback(action="accept", request_id=request_id).pack()
    )
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра деталей СВОЕЙ ЗАЯВКИ В РАБОТЕ (инженером) ---
def create_complete_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏁 Завершить (Выполнено)",
        callback_data=RequestActionCallback(action="complete", request_id=request_id).pack()
    )
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра истории заявок (инженером или админом) ---
def create_archive_requests_keyboard(
    requests: list[Request],
    current_page: int,
    total_pages: int,
    current_sort: str,
    user_role: UserRole | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not requests and current_page == 0:
        builder.button(text="История пуста", callback_data="ignore_empty_history")
    else:
        for req in requests:
            date_info = req.archived_at or req.completed_at
            date_str = date_info.strftime('%d.%m') if date_info else '??.??'
            engineer_info = f" ({req.engineer.first_name})" if req.engineer and req.engineer.first_name else ""
            button_text = f"#{req.id} ({date_str}{engineer_info}) {req.description[:15]}..."
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text
            builder.button(
                text=button_text,
                callback_data=RequestActionCallback(action="view_archive", request_id=req.id).pack()
            )
        builder.adjust(1)

    # --- ИСПРАВЛЕННЫЙ БЛОК ПАГИНАЦИИ ---
    if total_pages > 0:
        pagination_row = []
        # 1. Кнопка "Назад" или заполнитель
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=HistoryNavigationCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_prev")) # Заполнитель

        # 2. Индикатор страницы
        pagination_row.append(InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="ignore_page_indicator"
        ))

        # 3. Кнопка "Вперед" или заполнитель
        if current_page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед >",
                callback_data=HistoryNavigationCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_next")) # Заполнитель

        builder.row(*pagination_row)
    elif total_pages == 0 and current_page == 0:
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))
    # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

    if user_role == UserRole.ADMIN:
        builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))

    return builder.as_markup()