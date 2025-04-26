# bot/keyboards/reply.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from db.models import UserRole # Импортируем UserRole для проверки

NEW_REQUEST_BTN_TEXT = "📝 Создать заявку"
MY_REQUESTS_BTN_TEXT = "📄 Мои заявки"
HISTORY_BTN_TEXT = "📚 История выполненных"
VIEW_NEW_REQUESTS_BTN_TEXT = "👀 Новые заявки"
MY_ASSIGNED_REQUESTS_BTN_TEXT = "🛠️ Мои заявки в работе" 
SKIP_BTN_TEXT = "➡️ Пропустить"
CANCEL_BTN_TEXT = "❌ Отмена"
ADMIN_PANEL_BTN_TEXT = "👑 Панель администратора"


def get_main_menu_keyboard(user_role: UserRole) -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру главного меню в зависимости от роли пользователя.
    """
    builder = ReplyKeyboardBuilder()

    if user_role == UserRole.ADMIN:
        builder.row(
            KeyboardButton(text=ADMIN_PANEL_BTN_TEXT) # Главная кнопка админа
        )
    elif user_role == UserRole.ENGINEER:
        builder.row(
            KeyboardButton(text=VIEW_NEW_REQUESTS_BTN_TEXT),
            KeyboardButton(text=MY_ASSIGNED_REQUESTS_BTN_TEXT)
        )
        builder.row(
            KeyboardButton(text=HISTORY_BTN_TEXT)
        )
    else: # По умолчанию или для UserRole.CLIENT
         builder.row(
            KeyboardButton(text=NEW_REQUEST_BTN_TEXT)
        )
         builder.row(
             KeyboardButton(text=MY_REQUESTS_BTN_TEXT) 
        )

    
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=CANCEL_BTN_TEXT))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_skip_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру с кнопками Пропустить и Отмена."""
    builder = ReplyKeyboardBuilder()
    # Кнопки в один ряд
    builder.row(
        KeyboardButton(text=SKIP_BTN_TEXT),
        KeyboardButton(text=CANCEL_BTN_TEXT)
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

