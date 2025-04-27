# bot/keyboards/inline/admin_inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
# Импортируем колбэки для заявок, чтобы использовать их в главном меню
from .requests_inline import RequestActionCallback, HistoryNavigationCallback
from db.models import Request, User, UserRole  # Для клавиатуры активных заявок

# --- CallbackData для навигации по АКТИВНЫМ заявкам админа ---
class AdminActiveNavCallback(CallbackData, prefix="adm_act"):
    action: str # 'page', 'sort'
    page: int
    sort_by: str

# --- CallbackData для управления пользователями админом ---
class AdminUserManageCallback(CallbackData, prefix="adm_usr"):
    action: str 
    page: int = 0 
    user_id: int = 0
    new_role: str = "" 

# --- Главное меню админки ---
def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Создает главное инлайн-меню для админа."""
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
    """Создает клавиатуру со списком пользователей и пагинацией для админа."""
    builder = InlineKeyboardBuilder()
    if not users and current_page == 0:
        builder.button(text="Пользователи не найдены", callback_data="ignore_empty_list")
    else:
        for user in users:
            role_emoji = {
                UserRole.ADMIN: "👑", UserRole.ENGINEER: "🛠️", UserRole.CLIENT: "👤"
            }
            role_text = role_emoji.get(user.role, "❓")
            # Формируем отображаемое имя
            name_parts = [user.first_name, user.last_name]
            display_name = " ".join(filter(None, name_parts))
            if not display_name: display_name = f"ID:{user.id}" 
            # Добавляем username, если есть
            user_details = f"(@{user.username})" if user.username else f"(ID:{user.id})"
            # Ограничиваем общую длину строки
            full_display = f"{role_text} {display_name} {user_details}"
            max_len = 50 # Макс. длина текста кнопки (примерно)
            button_text = full_display[:max_len] + "..." if len(full_display) > max_len else full_display

            builder.button(
                text=button_text,
                # Передаем текущую страницу в CallbackData для возврата
                callback_data=AdminUserManageCallback(action="view", user_id=user.id, page=current_page).pack()
            )
        builder.adjust(1) # По одному пользователю в строке

    if total_pages > 0:
        pagination_row = []
        # 1. Кнопка "Назад" или заполнитель
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=AdminUserManageCallback(action="list_page", page=current_page - 1).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_prev")) # Заполнитель

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
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_next")) # Заполнитель

        builder.row(*pagination_row) # Добавляем ряд из 3х кнопок
    elif total_pages == 0 and current_page == 0: # Если список изначально пуст
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))

    # Кнопка "Назад в админ-меню"
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))

    return builder.as_markup()

# --- Клавиатура для профиля пользователя (смена роли) ---
def create_admin_user_profile_keyboard(user: User, current_list_page: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для профиля пользователя с кнопками смены роли."""
    builder = InlineKeyboardBuilder()
    user_id = user.id
    # Передаем текущую страницу списка пользователей (current_list_page) во все колбэки,
    # чтобы знать, на какую страницу возвращаться после смены роли
    callback_params = {"user_id": user_id, "page": current_list_page}

    # Добавляем кнопки для назначения каждой роли, кроме текущей
    if user.role != UserRole.ADMIN:
        builder.button(text="👑 Назначить Админом", callback_data=AdminUserManageCallback(
            action="set_role", new_role=UserRole.ADMIN.value, **callback_params).pack())
    if user.role != UserRole.ENGINEER:
        builder.button(text="🛠️ Назначить Инженером", callback_data=AdminUserManageCallback(
            action="set_role", new_role=UserRole.ENGINEER.value, **callback_params).pack())
    if user.role != UserRole.CLIENT:
        builder.button(text="👤 Сделать Клиентом", callback_data=AdminUserManageCallback(
            action="set_role", new_role=UserRole.CLIENT.value, **callback_params).pack())

    builder.adjust(1) # По кнопке в строке
    # Кнопка "Назад к списку пользователей"
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад к списку",
        # Возвращаемся на ту страницу списка, с которой пришли
        callback_data=AdminUserManageCallback(action="list_page", page=current_list_page).pack()
    ))

    return builder.as_markup()


# --- Клавиатура для списка АКТИВНЫХ заявок админа (с пагинацией) ---
def create_admin_active_requests_keyboard(
    requests: list[Request],
    current_page: int,
    total_pages: int,
    current_sort: str
) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком активных заявок и пагинацией для админа."""
    builder = InlineKeyboardBuilder()
    if not requests and current_page == 0:
        builder.button(text="Нет активных заявок", callback_data="ignore_empty_list")
    else:
        for req in requests:
            # Отображение инженера (если есть)
            engineer_info = f" ({req.engineer.first_name})" if req.engineer and req.engineer.first_name else ""
            # Отображение даты (принятия или создания)
            req_date = req.accepted_at or req.created_at
            date_str = req_date.strftime('%d.%m') if req_date else '??.??' # Короткий формат

            # Формируем текст кнопки
            desc_text = req.description or "Без описания"
            button_text = f"#{req.id} ({date_str}{engineer_info}) {desc_text[:20]}..." # Укоротил описание
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text

            builder.button(
                text=button_text,
                # Этот action используется хендлером просмотра в admin_panel.py
                callback_data=RequestActionCallback(action="view_active", request_id=req.id).pack()
            )
        builder.adjust(1) # По одной заявке в строке

    if total_pages > 0:
        pagination_row = []
        # 1. Кнопка "Назад"
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=AdminActiveNavCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_prev")) # Заполнитель

        # 2. Индикатор страницы
        pagination_row.append(InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="ignore_page_indicator"
        ))

        # 3. Кнопка "Вперед"
        if current_page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед >",
                callback_data=AdminActiveNavCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_next")) # Заполнитель

        builder.row(*pagination_row)
    elif total_pages == 0 and current_page == 0: # Если список изначально пуст
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))

    # Кнопка "Назад в меню"
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))
    return builder.as_markup()