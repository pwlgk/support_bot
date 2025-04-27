# bot/keyboards/inline/requests_inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Request, UserRole

# --- CallbackData для действий с заявками ---
class RequestActionCallback(CallbackData, prefix="req"):
    action: str 
    request_id: int

# --- CallbackData для навигации по ИСТОРИИ заявок (для инженера и админа) ---
class HistoryNavigationCallback(CallbackData, prefix="hist"):
    action: str 
    page: int
    sort_by: str

# --- CallbackData для навигации по АКТИВНЫМ заявкам ИНЖЕНЕРА ---
class EngActiveNavCallback(CallbackData, prefix="eng_act"):
    action: str 
    page: int
    sort_by: str


# --- Клавиатура для списка НОВЫХ заявок  ---
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

# --- Клавиатура для списка активных заявок ИНЖЕНЕРА  ---
def create_engineer_active_requests_keyboard(
    requests: list[Request],
    current_page: int,
    total_pages: int,
    current_sort: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not requests and current_page == 0:
        builder.button(text="Нет заявок в работе", callback_data="ignore_empty_inprogress")
    else:
        for req in requests:
            client_name = req.requester.first_name if req.requester and req.requester.first_name else f"ID:{req.requester_id}"
            accepted_date_str = req.accepted_at.strftime('%d.%m') if req.accepted_at else '??.??'
            desc_text = req.description or "Без описания"
            button_text = f"#{req.id} ({accepted_date_str}) {client_name} - {desc_text[:20]}..."
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text
            builder.button(
                text=button_text,
                callback_data=RequestActionCallback(action="view_my", request_id=req.id).pack()
            )
        builder.adjust(1)
    if total_pages > 0:
        pagination_row = []
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=EngActiveNavCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_prev"))
        pagination_row.append(InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="ignore_page_indicator"
        ))
        if current_page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед >",
                callback_data=EngActiveNavCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_next"))
        builder.row(*pagination_row)
    elif total_pages == 0 and current_page == 0:
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))
    return builder.as_markup()

# --- Клавиатуры для просмотра деталей заявок ---
def create_view_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять в работу",
        callback_data=RequestActionCallback(action="accept", request_id=request_id).pack()
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад к новым", callback_data="eng_view_new"))
    builder.adjust(1)
    return builder.as_markup()

def create_complete_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏁 Завершить (Выполнено)",
        callback_data=RequestActionCallback(action="complete", request_id=request_id).pack()
    )
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра ИСТОРИИ заявок ---
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
            # Для админа показываем инженера
            engineer_info = f" ({req.engineer.first_name})" if req.engineer and req.engineer.first_name else ""
            desc_text = req.description or "Без описания"
            # Отображаем инженера и описание
            button_text = f"#{req.id} ({date_str}{engineer_info}) {desc_text[:15]}..."
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text

            builder.button(
                text=button_text,
                # Этот action используется хендлером просмотра в admin_panel.py
                callback_data=RequestActionCallback(action="view_archive", request_id=req.id).pack()
            )
        builder.adjust(1)

    if total_pages > 0:
        pagination_row = []
        # 1. Кнопка "Назад"
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=HistoryNavigationCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
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
                callback_data=HistoryNavigationCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_next")) # Заполнитель

        builder.row(*pagination_row)
    elif total_pages == 0 and current_page == 0:
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))

    # Кнопка "Назад в меню" в зависимости от роли
    if user_role == UserRole.ADMIN:
        builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))
    elif user_role == UserRole.ENGINEER:
        builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))

    return builder.as_markup()
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Request, UserRole

# --- CallbackData для действий с заявками ---
class RequestActionCallback(CallbackData, prefix="req"):
    action: str 
    request_id: int

# --- CallbackData для навигации по ИСТОРИИ заявок (для инженера и админа) ---
class HistoryNavigationCallback(CallbackData, prefix="hist"):
    action: str 
    page: int
    sort_by: str

class EngActiveNavCallback(CallbackData, prefix="eng_act"):
    action: str # 'page', 'sort'
    page: int
    sort_by: str # Поле сортировки (например, 'accepted_asc', 'created_desc')


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

def create_engineer_active_requests_keyboard(
    requests: list[Request],
    current_page: int,
    total_pages: int,
    current_sort: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not requests and current_page == 0:
        builder.button(text="Нет заявок в работе", callback_data="ignore_empty_inprogress")
    else:
        for req in requests:
            client_name = req.requester.first_name if req.requester and req.requester.first_name else f"ID:{req.requester_id}"
            accepted_date_str = req.accepted_at.strftime('%d.%m') if req.accepted_at else '??.??'
            desc_text = req.description or "Без описания"
            button_text = f"#{req.id} ({accepted_date_str}) {client_name} - {desc_text[:20]}..."
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text

            builder.button(
                text=button_text,
                callback_data=RequestActionCallback(action="view_my", request_id=req.id).pack()
            )
        builder.adjust(1)

    if total_pages > 0:
        pagination_row = []
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=EngActiveNavCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_prev"))

        pagination_row.append(InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="ignore_page_indicator"
        ))

        if current_page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед >",
                callback_data=EngActiveNavCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text="•", callback_data="ignore_nav_next"))

        builder.row(*pagination_row)
    elif total_pages == 0 and current_page == 0:
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))

    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng")) # Нужен обработчик

    return builder.as_markup()


# --- Клавиатура для просмотра деталей НОВОЙ заявки (инженером) ---
def create_view_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять в работу",
        callback_data=RequestActionCallback(action="accept", request_id=request_id).pack()
    )
    # Кнопка Назад к списку новых заявок
    builder.row(InlineKeyboardButton(text="⬅️ Назад к новым", callback_data="eng_view_new"))
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра деталей СВОЕЙ ЗАЯВКИ В РАБОТЕ (инженером) ---
def create_complete_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏁 Завершить (Выполнено)",
        callback_data=RequestActionCallback(action="complete", request_id=request_id).pack()
    )
    # Кнопка Назад в главное меню (возврат к списку активных сложнее из-за пагинации)
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра ИСТОРИИ заявок (инженером или админом) ---
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
            # Для инженера его имя не так важно, важнее клиент
            client_name = req.requester.first_name if req.requester and req.requester.first_name else f"ID:{req.requester_id}"
            desc_text = req.description or "Без описания"
            # Отображаем клиента и описание
            button_text = f"#{req.id} ({date_str}) {client_name} - {desc_text[:15]}..."
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text

            builder.button(
                text=button_text,
                callback_data=RequestActionCallback(action="view_archive", request_id=req.id).pack()
            )
        builder.adjust(1)

    if total_pages > 0:
        pagination_row = []
        if current_page > 0:
            pagination_row.append(InlineKeyboardButton(
                text="< Назад",
                callback_data=HistoryNavigationCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_prev"))
        pagination_row.append(InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data="ignore_page_indicator"
        ))
        if current_page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton(
                text="Вперед >",
                callback_data=HistoryNavigationCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
            ))
        else:
            pagination_row.append(InlineKeyboardButton(text=" ", callback_data="ignore_nav_next"))
        builder.row(*pagination_row)
    elif total_pages == 0 and current_page == 0:
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))

    # Кнопка "Назад в меню" в зависимости от роли
    if user_role == UserRole.ADMIN:
        builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))
    elif user_role == UserRole.ENGINEER:
        builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu_eng"))

    return builder.as_markup()