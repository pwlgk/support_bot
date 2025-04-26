# bot/keyboards/inline/requests_inline.py
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Request, UserRole

# --- CallbackData для действий с заявками ---
class RequestActionCallback(CallbackData, prefix="req"):
    # --- ИЗМЕНЕНО: Добавлен 'view_active' для админа ---
    action: str # 'view', 'accept', 'complete', 'view_my', 'view_archive', 'view_active'
    request_id: int

# --- CallbackData для навигации по истории ---
class HistoryNavigationCallback(CallbackData, prefix="hist"):
    action: str # 'page', 'sort' (пока только 'page')
    page: int   # Номер страницы (0-индексированный)
    sort_by: str # Поле сортировки ('date_desc', 'date_asc', 'id_asc', 'id_desc')

# --- Клавиатура для списка НОВЫХ заявок---
def create_new_requests_keyboard(requests: list[Request]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # --- ИЗМЕНЕНО: Добавлена проверка на пустой список ---
    if not requests:
        builder.button(text="Нет новых заявок", callback_data="ignore_empty_new")
    else:
        for req in requests:
            builder.button(
                text=f"#{req.id} - {req.description[:30]}...",
                # --- ИСПРАВЛЕНО: добавлен .pack() ---
                callback_data=RequestActionCallback(action="view", request_id=req.id).pack()
            )
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для списка СВОИХ заявок В РАБОТЕ ---
def create_in_progress_requests_keyboard(requests: list[Request]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # --- ИЗМЕНЕНО: Добавлена проверка на пустой список ---
    if not requests:
        builder.button(text="Нет заявок в работе", callback_data="ignore_empty_inprogress")
    else:
        for req in requests:
             # Отображение имени клиента
            client_name = req.requester.first_name if req.requester and req.requester.first_name else f"ID:{req.requester_id}"
            button_text = f"#{req.id} - {client_name} - {req.description[:25]}..."
            builder.button(
                text=button_text,
                # --- ИСПРАВЛЕНО: добавлен .pack() ---
                callback_data=RequestActionCallback(action="view_my", request_id=req.id).pack()
            )
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра деталей НОВОЙ заявки (инженером) ---
def create_view_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять в работу",
        # --- ИСПРАВЛЕНО: добавлен .pack() ---
        callback_data=RequestActionCallback(action="accept", request_id=request_id).pack()
    )
    # Можно добавить кнопку назад к списку новых заявок, если нужно
    # builder.button(text="⬅️ Назад к новым", callback_data="back_to_new_requests")
    builder.adjust(1)
    return builder.as_markup()

# --- Клавиатура для просмотра деталей СВОЕЙ ЗАЯВКИ В РАБОТЕ (инженером) ---
def create_complete_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏁 Завершить (Выполнено)",
        # --- ИСПРАВЛЕНО: добавлен .pack() ---
        callback_data=RequestActionCallback(action="complete", request_id=request_id).pack()
    )
    # Можно добавить кнопку назад к списку "в работе"
    # builder.button(text="⬅️ Назад к списку", callback_data="back_to_my_requests")
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
            # Отображение даты архивации или завершения
            date_info = req.archived_at or req.completed_at
            date_str = date_info.strftime('%d.%m') if date_info else '??.??' # Короткий формат
            # Отображение инженера (если есть)
            engineer_info = f" ({req.engineer.first_name})" if req.engineer and req.engineer.first_name else ""

            # Формируем текст кнопки
            # --- ИЗМЕНЕНО: Убрано дублирование req.description ---
            desc_text = req.description or "Без описания"
            button_text = f"#{req.id} ({date_str}{engineer_info}) {desc_text[:15]}..."
            max_len = 50
            button_text = button_text[:max_len] + "..." if len(button_text) > max_len else button_text

            builder.button(
                text=button_text,
                # Используем pack(), как и было
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

        builder.row(*pagination_row) # Добавляем ряд из 3х кнопок
    elif total_pages == 0 and current_page == 0: # Если список изначально пуст
        builder.row(InlineKeyboardButton(text="- / -", callback_data="ignore_page_indicator"))
    # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

    # Кнопка "Назад в меню" для Админа (если передана роль)
    if user_role == UserRole.ADMIN:
        builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_to_main"))
    # Для инженера кнопка "Назад" не предусмотрена здесь,
    # предполагается, что он вернется через главное меню

    return builder.as_markup()