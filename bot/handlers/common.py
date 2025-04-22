# bot/handlers/common.py
import logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from db.crud import get_or_create_user, get_user
from bot.keyboards.reply import (
    get_main_menu_keyboard, # Больше не импортируем тексты кнопок отсюда
    get_cancel_keyboard,
    CANCEL_BTN_TEXT
)
# Импортируем тексты кнопок из reply.py для фильтров
from bot.keyboards.reply import (
    NEW_REQUEST_BTN_TEXT, MY_REQUESTS_BTN_TEXT,
    VIEW_NEW_REQUESTS_BTN_TEXT, MY_ASSIGNED_REQUESTS_BTN_TEXT,
    HISTORY_BTN_TEXT, ADMIN_PANEL_BTN_TEXT, CANCEL_BTN_TEXT
)
from db.models import UserRole # Для определения роли в help

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, session: AsyncSession, state: FSMContext): # Добавили state для очистки
    # Сбросим состояние FSM на всякий случай, если пользователь был в процессе
    await state.clear()

    tg_user = message.from_user
    if not tg_user:
         await message.answer("Не удалось определить пользователя.")
         return

    db_user, created = await get_or_create_user(
        session=session, user_id=tg_user.id, username=tg_user.username,
        first_name=tg_user.first_name, last_name=tg_user.last_name
    )

    user_display_name = tg_user.first_name or tg_user.username or f"User {tg_user.id}"
    if created:
        greeting = f"Добро пожаловать, {user_display_name}!\n"
        greeting += "Вы зарегистрированы в системе службы поддержки.\n\n"
    else:
        greeting = f"Снова здравствуйте, {user_display_name}!\n\n"

    text = greeting + "Выберите действие:"
    # Получаем клавиатуру, передавая роль пользователя из БД
    keyboard = get_main_menu_keyboard(db_user.role)
    await message.answer(text, reply_markup=keyboard)

# Хендлер отмены остается без изменений
@router.message(F.text == CANCEL_BTN_TEXT)
async def cancel_handler(message: types.Message, state: FSMContext, session: AsyncSession): # Добавили session
    current_state = await state.get_state()
    # Получим роль пользователя, чтобы вернуть правильную клавиатуру
    db_user = await get_or_create_user(
        session=session, user_id=message.from_user.id, username=message.from_user.username,
        first_name=message.from_user.first_name, last_name=message.from_user.last_name
    )
    keyboard = get_main_menu_keyboard(db_user[0].role) # db_user[0] это сам юзер

    if current_state is None:
        await message.answer("Нет активного действия для отмены.", reply_markup=keyboard)
        return

    logging.info(f"Cancelling state {current_state} for user {message.from_user.id}")
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=keyboard)


@router.message(Command('help'))
async def cmd_help(message: types.Message, session: AsyncSession):
    """
    Обработчик команды /help. Показывает разную справку в зависимости от роли.
    """
    user_id = message.from_user.id
    # Получаем пользователя и его роль
    # Используем get_user, т.к. пользователь точно существует, раз прислал /help
    db_user = await get_user(session, user_id)

    # Базовый текст
    help_text_lines = [
        "👋 Привет! Я бот службы поддержки. Вот что я умею:",
        "" # Пустая строка для разделения
    ]

    user_role = db_user.role if db_user else UserRole.CLIENT # По умолчанию - клиент, если вдруг юзера нет

    # --- Справка для Клиента ---
    if user_role == UserRole.CLIENT:
        help_text_lines.extend([
            "<b>Для Вас (Клиент):</b>",
            f"🔹 <b>{NEW_REQUEST_BTN_TEXT}</b> или /new_request - Начать создание новой заявки на ремонт.",
            f"   - Я задам несколько вопросов: ФИО, место (корпус, кабинет), описание проблемы, инв. номер (опционально), телефон.",
            f"   - Во время создания можно нажать <b>{CANCEL_BTN_TEXT}</b> для отмены.",
            f"🔹 <b>{MY_REQUESTS_BTN_TEXT}</b> или /my_requests - Посмотреть список ваших текущих заявок и их статус.",
            f"🔹 /start - Перезапустить бота и показать главное меню.",
            f"🔹 /help - Показать это справочное сообщение.",
            "",
            "Если у вас вопрос не по работе бота, а по вашей проблеме, пожалуйста, создайте заявку."
        ])

    # --- Справка для Инженера ---
    elif user_role == UserRole.ENGINEER:
         help_text_lines.extend([
            "<b>Для Вас (Инженер):</b>",
            f"🔹 <b>{VIEW_NEW_REQUESTS_BTN_TEXT}</b> или /view_new_requests - Посмотреть список новых заявок, ожидающих принятия.",
            f"   - Нажмите на заявку в списке, чтобы увидеть детали и кнопку 'Принять в работу'.",
            f"🔹 <b>{MY_ASSIGNED_REQUESTS_BTN_TEXT}</b> или /my_requests - Посмотреть список заявок, которые вы уже приняли в работу.",
            f"   - Нажмите на заявку, чтобы увидеть детали и кнопку 'Завершить (Выполнено)'. При завершении заявка уходит в историю.",
            f"🔹 <b>{HISTORY_BTN_TEXT}</b> или /archive - Просмотреть историю выполненных <i>вами</i> заявок (с пагинацией).",
            f"🔹 /start - Показать главное меню инженера.",
            f"🔹 /help - Показать это справочное сообщение.",
            # Если инженер может создавать заявки:
            # f"🔹 <b>{NEW_REQUEST_BTN_TEXT}</b> - Вы также можете создавать заявки от своего имени.",
        ])

    # --- Справка для Администратора ---
    elif user_role == UserRole.ADMIN:
        help_text_lines.extend([
            "Для Вас (Администратор):",
            f"-> {ADMIN_PANEL_BTN_TEXT} или /admin - Открыть панель администратора:",
            f"   - Управление пользователями",
            f"   - Активные заявки",
            f"   - История выполненных",
            "",
            "   Команды управления пользователями:",
            "   - /list_engineers",
            "   - /add_engineer <ID>",
            "   - /remove_engineer <ID>",
            "",
            "   Управление YandexGPT:",
            "   - /gpt_on",
            "   - /gpt_off",
            "   - /gpt_status",
            "",
            "   Функции инженера также доступны.",
            f"-> /start - Главное меню.",
            f"-> /help - Эта справка.",
        ])


    # Формируем итоговое сообщение
    full_help_text = "\n".join(help_text_lines)
    
    # Получаем клавиатуру для текущей роли
    keyboard = get_main_menu_keyboard(user_role)

    # Отправляем сообщение
    try:
        # --- ОТПРАВКА БЕЗ PARSE_MODE ---
        await message.answer(full_help_text, reply_markup=keyboard, parse_mode=None)
        logging.info("Help sent successfully with parse_mode=None")
        # -------------------------------
    except Exception as e:
        # Логируем ошибку, даже если отправляем без форматирования
        logging.error(f"Error sending help message for user {user_id} role {user_role}: {e}", exc_info=True)
        await message.answer("Не удалось загрузить справку (ошибка форматирования).", reply_markup=keyboard)