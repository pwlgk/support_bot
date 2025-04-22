# bot/keyboards/inline/requests_inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Request, UserRole

# --- CallbackData для действий с заявками ---
class RequestActionCallback(CallbackData, prefix="req"):
    action: str # 'view', 'accept', 'complete', 'view_my', 'view_archive'
    request_id: int


class HistoryNavigationCallback(CallbackData, prefix="hist"):
    action: str # 'page', 'sort' (пока только 'page')
    page: int   # Номер страницы (0-индексированный)
    sort_by: str # Поле сортировки ('date_desc', 'date_asc', 'id_asc', 'id_desc')
# --- Клавиатура для списка НОВЫХ заявок (без изменений) ---
def create_new_requests_keyboard(requests: list[Request]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for req in requests:
        builder.button(
            text=f"#{req.id} - {req.description[:30]}...",
            callback_data=RequestActionCallback(action="view", request_id=req.id)
        )
    builder.adjust(1)
    return builder.as_markup()

# --- НОВАЯ: Клавиатура для списка СВОИХ заявок В РАБОТЕ ---
def create_in_progress_requests_keyboard(requests: list[Request]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for req in requests:
        # Используем action="view_my", чтобы можно было различать в хендлере, откуда пришел просмотр
        builder.button(
            text=f"#{req.id} - {req.requester.first_name} - {req.description[:25]}...",
            callback_data=RequestActionCallback(action="view_my", request_id=req.id)
        )
    builder.adjust(1)
    # Можно добавить кнопку "Назад в меню" или пагинацию
    return builder.as_markup()

# --- Клавиатура для просмотра деталей заявки (инженером) ---
# Эту функцию будем использовать для показа кнопки "Принять"
def create_view_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять в работу",
        callback_data=RequestActionCallback(action="accept", request_id=request_id)
    )
    # builder.button(text="⬅️ Назад", ...)
    builder.adjust(1)
    return builder.as_markup()

def create_complete_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏁 Завершить (Выполнено)",
        callback_data=RequestActionCallback(action="complete", request_id=request_id)
    )
    # builder.button(text="⬅️ Назад к списку", ...)
    builder.adjust(1)
    return builder.as_markup()
def create_archive_requests_keyboard(
    requests: list[Request],
    current_page: int,
    total_pages: int,
    current_sort: str,
    user_role: UserRole | None = None # <-- УБЕДИТЕСЬ, ЧТО ЭТОТ ПАРАМЕТР ДОБАВЛЕН
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Кнопки с заявками (код без изменений)
    if not requests and current_page == 0:
        builder.button(text="История пуста", callback_data="ignore_empty_history")
    else:
        for req in requests:
            date_info = req.archived_at or req.completed_at
            date_str = date_info.strftime('%y-%m-%d') if date_info else 'N/A'
            engineer_name = req.engineer.first_name if req.engineer else "N/A"
            builder.button(
                text=f"#{req.id} ({date_str}) {engineer_name} - {req.description[:15]}...",
                callback_data=RequestActionCallback(action="view_archive", request_id=req.id).pack()
            )
        builder.adjust(1)

    # Кнопки пагинации (код без изменений)
    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(InlineKeyboardButton(
            text="< Назад",
            callback_data=HistoryNavigationCallback(action="page", page=current_page - 1, sort_by=current_sort).pack()
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
            callback_data=HistoryNavigationCallback(action="page", page=current_page + 1, sort_by=current_sort).pack()
        ))
    else:
        pagination_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore_pagination_space"))
    if total_pages > 0:
        builder.row(*pagination_buttons)

    # Условное добавление кнопки "Назад в меню" (код без изменений)
    if user_role == UserRole.ADMIN:
        builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))

    return builder.as_markup()