# bot/keyboards/inline/admin_inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Request,  User, UserRole  # Для клавиатуры активных заявок

# --- CallbackData для навигации по АКТИВНЫМ заявкам админа ---
class AdminActiveNavCallback(CallbackData, prefix="adm_act"):
    action: str # 'page'
    page: int
    sort_by: str # 'accepted_asc', 'created_asc', 'created_desc'

class AdminUserManageCallback(CallbackData, prefix="adm_usr"):
    action: str # 'list_page', 'view', 'set_role'
    page: int = 0 # Для пагинации списка
    user_id: int = 0 # ID целевого пользователя
    new_role: str = "" # Новая роль ('admin', 'engineer', 'client')

# --- Главное меню админки ---
def get_admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        # Используем новый CallbackData для кнопки управления пользователями
        InlineKeyboardButton(
            text="👥 Управление пользователями",
            callback_data=AdminUserManageCallback(action="list_page", page=0).pack() # Показываем 1ю страницу списка
        )
    )
    builder.row(
        InlineKeyboardButton(text="🛠️ Активные заявки", callback_data="admin_view_active") # Пока оставим строкой
    )
    builder.row(
        InlineKeyboardButton(text="📚 История выполненных", callback_data="admin_view_history") # Пока оставим строкой
    )
    return builder.as_markup()

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
            user_display = f"{user.first_name or ''} {user.last_name or ''} (@{user.username})" if user.username else f"{user.first_name or ''} {user.last_name or ''} (ID:{user.id})"
            user_display = user_display.strip() or f"ID:{user.id}" # Если имя/фамилия пустые
            builder.button(
                text=f"{role_text} {user_display[:40]}...", # Ограничиваем длину
                callback_data=AdminUserManageCallback(action="view", user_id=user.id).pack()
            )
        builder.adjust(1) # По одному пользователю в строке

    # Кнопки пагинации (аналогично другим спискам)
    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(InlineKeyboardButton(
            text="< Назад",
            callback_data=AdminUserManageCallback(action="list_page", page=current_page - 1).pack()
        ))
    else:
         pagination_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore_pagination_space"))

    if total_pages > 1:
         pagination_buttons.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="ignore_page_indicator"))
    elif total_pages == 1 and users:
         pagination_buttons.append(InlineKeyboardButton(text="1/1", callback_data="ignore_page_indicator"))
    else:
         pagination_buttons.append(InlineKeyboardButton(text="-", callback_data="ignore_page_indicator"))

    if current_page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед >",
            callback_data=AdminUserManageCallback(action="list_page", page=current_page + 1).pack()
        ))
    else:
        pagination_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore_pagination_space"))

    if total_pages > 0:
        builder.row(*pagination_buttons)

    # Кнопка "Назад в админ-меню"
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))

    return builder.as_markup()

# --- НОВАЯ Клавиатура для профиля пользователя (смена роли) ---
def create_admin_user_profile_keyboard(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    user_id = user.id
    # Добавляем кнопки для назначения каждой роли, кроме текущей
    # Передаем user_id и новую роль в callback_data
    if user.role != UserRole.ADMIN:
        builder.button(text="👑 Назначить Админом", callback_data=AdminUserManageCallback(
            action="set_role", user_id=user_id, new_role=UserRole.ADMIN.value).pack())
    if user.role != UserRole.ENGINEER:
        builder.button(text="🛠️ Назначить Инженером", callback_data=AdminUserManageCallback(
            action="set_role", user_id=user_id, new_role=UserRole.ENGINEER.value).pack())
    if user.role != UserRole.CLIENT:
        builder.button(text="👤 Сделать Клиентом", callback_data=AdminUserManageCallback(
            action="set_role", user_id=user_id, new_role=UserRole.CLIENT.value).pack())

    builder.adjust(1) # По кнопке в строке
    # Кнопка "Назад к списку пользователей" (нужно передать текущую страницу списка)
    # Пока просто кнопка без действия или можно ее убрать/сделать возврат в меню
    builder.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=AdminUserManageCallback(
        action="list_page", page=0).pack())) # Возвращаем на 1ю страницу
    
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
            engineer_name = req.engineer.first_name if req.engineer else "N/A"
            req_date = req.accepted_at or req.created_at # Используем дату принятия или создания
            date_str = req_date.strftime('%y-%m-%d') if req_date else 'N/A'
            builder.button(
                text=f"#{req.id} ({date_str}) {engineer_name} - {req.description[:15]}...",
                # Используем тот же callback просмотра деталей, что и для архива/инженера
                callback_data=f"req:view_archive:{req.id}" # Или создать action 'view_admin'
            )
        builder.adjust(1)

    # Кнопки пагинации (аналогично истории)
    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(InlineKeyboardButton(
            text="< Назад",
            callback_data=AdminActiveNavCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
        ))
    else:
         pagination_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore_pagination_space"))

    if total_pages > 1:
         pagination_buttons.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="ignore_page_indicator"))
    elif total_pages == 1 and requests:
         pagination_buttons.append(InlineKeyboardButton(text="1/1", callback_data="ignore_page_indicator"))
    else:
         pagination_buttons.append(InlineKeyboardButton(text="-", callback_data="ignore_page_indicator"))

    if current_page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton(
            text="Вперед >",
            callback_data=AdminActiveNavCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
        ))
    else:
        pagination_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore_pagination_space"))

    if total_pages > 0:
        builder.row(*pagination_buttons)

    # TODO: Добавить кнопки сортировки для активных заявок
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))
    return builder.as_markup()