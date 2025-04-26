# bot/keyboards/inline/engineer_inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
# Импортируем CallbackData для кнопок
from .requests_inline import EngActiveNavCallback, HistoryNavigationCallback

def get_engineer_main_menu() -> InlineKeyboardMarkup:
    """Создает главное инлайн-меню для инженера."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Новые заявки", callback_data="eng_view_new")
    )
    builder.row(
        InlineKeyboardButton(
            text="🛠️ Мои активные заявки",
            # Передаем начальную страницу и сортировку по умолчанию
            callback_data=EngActiveNavCallback(action="page", page=0, sort_by='accepted_asc').pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📚 Моя история",
            # Передаем начальную страницу и сортировку по умолчанию
            callback_data=HistoryNavigationCallback(action="page", page=0, sort_by='date_desc').pack()
        )
    )
    # Можно добавить другие кнопки, например, /help
    # builder.row(InlineKeyboardButton(text="❓ Помощь", callback_data="help_command")) # Потребуется хендлер

    return builder.as_markup()