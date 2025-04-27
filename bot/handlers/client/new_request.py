# bot/handlers/client/new_request.py
import logging
from html import escape
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Router, types, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import  InlineKeyboardButton

from bot.keyboards.inline.requests_inline import RequestActionCallback
from bot.states.request_states import CreateRequest # Импортируем обновленные состояния
# Импортируем нужные клавиатуры и тексты
from bot.keyboards.reply import (
    get_cancel_keyboard, get_skip_cancel_keyboard, get_main_menu_keyboard,
    NEW_REQUEST_BTN_TEXT, SKIP_BTN_TEXT, CANCEL_BTN_TEXT
)
# Импортируем CRUD и модели
from db.crud import create_request, get_user, get_users_by_role
from db.models import UserRole

router = Router()

# Список всех состояний процесса создания заявки
all_create_request_states = ( # Используем кортеж для неизменяемости
    CreateRequest.waiting_for_full_name,
    CreateRequest.waiting_for_building,
    CreateRequest.waiting_for_room,
    CreateRequest.waiting_for_description,
    CreateRequest.waiting_for_pc_number,
    CreateRequest.waiting_for_phone,
)

# --- Обработчик отмены создания заявки (ПЕРВЫЙ) ---
@router.message(F.text == CANCEL_BTN_TEXT, StateFilter(*all_create_request_states))
async def cancel_request_creation(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    current_state = await state.get_state()
    if current_state is not None and current_state in all_create_request_states:
        logging.info(f"User {user_id} cancelled request creation from state {current_state}")
        await state.clear()
        db_user = await get_user(session, user_id)
        user_role = db_user.role if db_user else UserRole.CLIENT 
        await message.answer(
            "Действие отменено. Создание заявки прервано.",
            reply_markup=get_main_menu_keyboard(user_role)
        )
    else:
         logging.debug(f"User {user_id} sent cancel text '{CANCEL_BTN_TEXT}' but was not in a relevant state ({current_state}). Filter should have caught this.")


# --- Шаг 1: Начало создания заявки -> Запрос ФИО ---
@router.message(F.text == NEW_REQUEST_BTN_TEXT)
@router.message(Command('new_request'))
async def start_create_request(message: types.Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    logging.info(f"User {user_id} starting detailed request creation.")
    db_user = await get_user(session, user_id)
    prefilled_name = ""
    if db_user:
        f_name = db_user.first_name or ""
        l_name = db_user.last_name or ""
        prefilled_name = f"{f_name} {l_name}".strip()

    await state.update_data(full_name=prefilled_name if prefilled_name else None)

    await state.set_state(CreateRequest.waiting_for_full_name)
    question = "Пожалуйста, введите ваше ФИО:"

    await message.answer(question, reply_markup=get_cancel_keyboard())

# --- Шаг 2: Получение ФИО -> Запрос Корпуса ---
@router.message(CreateRequest.waiting_for_full_name, F.text, F.text != CANCEL_BTN_TEXT)
async def process_full_name(message: types.Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 5: # Простая валидация
        await message.answer("Пожалуйста, введите полное ФИО (хотя бы 5 символов):")
        return
    await state.update_data(full_name=full_name)
    logging.info(f"User {message.from_user.id} provided name: {full_name}")

    await state.set_state(CreateRequest.waiting_for_building)
    await message.answer("В каком корпусе возникла проблема? (Например: Корпус 1, АБК, Главный)")

# --- Шаг 3: Получение Корпуса -> Запрос Кабинета ---
@router.message(CreateRequest.waiting_for_building, F.text, F.text != CANCEL_BTN_TEXT)
async def process_building(message: types.Message, state: FSMContext):
    building = message.text.strip()
    if not building:
        await message.answer("Пожалуйста, укажите корпус:")
        return
    await state.update_data(building=building)
    logging.info(f"User {message.from_user.id} provided building: {building}")

    await state.set_state(CreateRequest.waiting_for_room)
    await message.answer("Укажите номер кабинета (или название помещения):")

# --- Шаг 4: Получение Кабинета -> Запрос Описания ---
@router.message(CreateRequest.waiting_for_room, F.text, F.text != CANCEL_BTN_TEXT)
async def process_room(message: types.Message, state: FSMContext):
    room = message.text.strip()
    if not room:
        await message.answer("Пожалуйста, укажите номер кабинета:")
        return
    await state.update_data(room=room)
    logging.info(f"User {message.from_user.id} provided room: {room}")

    await state.set_state(CreateRequest.waiting_for_description)
    await message.answer("Теперь опишите проблему как можно подробнее:")

# --- Шаг 5: Получение Описания -> Запрос ПК/Инв. номера ---
@router.message(CreateRequest.waiting_for_description, F.text, F.text != CANCEL_BTN_TEXT)
async def process_description(message: types.Message, state: FSMContext):
    description = message.text 
    if len(description) < 10: 
        await message.answer("Описание слишком короткое. Пожалуйста, опишите проблему подробнее:")
        return
    await state.update_data(description=description)
    logging.info(f"User {message.from_user.id} provided description: {description[:30]}...")

    await state.set_state(CreateRequest.waiting_for_pc_number)
    # Показываем клавиатуру с Пропустить и Отмена
    await message.answer(
        "Укажите инвентарный номер компьютера или оборудования (если проблема связана с ним). "
        "Если номера нет или он неизвестен, нажмите 'Пропустить'.",
        reply_markup=get_skip_cancel_keyboard()
    )

# --- Шаг 6: Получение ПК/Инв. номера (или Пропуск) -> Запрос Телефона ---
@router.message(CreateRequest.waiting_for_pc_number, F.text)
async def process_pc_number(message: types.Message, state: FSMContext):
    if message.text == CANCEL_BTN_TEXT:
        logging.warning(f"Cancel text '{CANCEL_BTN_TEXT}' reached process_pc_number handler. This should ideally be caught by cancel_request_creation.")
        return 

    pc_number = None # По умолчанию None
    if message.text != SKIP_BTN_TEXT: 
        pc_number = message.text.strip()
        if not pc_number:
             await message.answer("Инвентарный номер не может быть пустым. Введите номер, нажмите 'Пропустить' или 'Отмена'.")
             return
        logging.info(f"User {message.from_user.id} provided PC number: {pc_number}")
    else:
        logging.info(f"User {message.from_user.id} skipped PC number.")

    await state.update_data(pc_number=pc_number) # Сохраняем номер или None
    await state.set_state(CreateRequest.waiting_for_phone)
    # Возвращаем клавиатуру только с Отменой
    await message.answer("Укажите ваш контактный номер телефона для связи:", reply_markup=get_cancel_keyboard())


# --- Шаг 7: Получение Телефона -> Сохранение заявки и Уведомление ---
@router.message(CreateRequest.waiting_for_phone, F.text, F.text != CANCEL_BTN_TEXT)
async def process_phone_and_finish(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    phone_number = message.text.strip()
    if not phone_number or len(phone_number) <= 3:
        await message.answer("Пожалуйста, введите корректный номер телефона (хотя бы 3 символa):")
        return

    await state.update_data(contact_phone=phone_number)
    user_data = await state.get_data() 
    requester_id = message.from_user.id
    logging.info(f"User {requester_id} provided phone: {phone_number}. Data collected: {user_data}")

    # Получаем пользователя для определения его роли и имени/ника
    db_user = await get_user(session, requester_id)
    if not db_user:
        logging.error(f"User {requester_id} not found in DB during finalization!")
        await message.answer("❌ Произошла внутренняя ошибка. Попробуйте /start", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    user_role = db_user.role
    user_mention = f"@{db_user.username}" if db_user.username else f"ID: {db_user.id}"

    try:
        # --- Сохранение заявки в БД ---
        new_request = await create_request(
            session=session,
            requester_id=requester_id,
            full_name=user_data.get('full_name'),
            building=user_data.get('building', 'Не указан'),
            room=user_data.get('room', 'Не указан'),
            description=user_data.get('description', 'Описание отсутствует'),
            pc_number=user_data.get('pc_number'),
            contact_phone=user_data.get('contact_phone') 
        )
        logging.info(f"Request {new_request.id} created for user {requester_id}")

        # --- Отправляем подтверждение клиенту с новыми данными ---
        pc_text = f"ПК/Инв. номер: {escape(new_request.pc_number)}\n" if new_request.pc_number else ""
        confirmation_text = (
            f"✅ Ваша заявка №{new_request.id} успешно создана!\n\n"
            f"<b>ФИО:</b> {escape(new_request.full_name or 'Не указано')}\n"
            f"<b>Корпус:</b> {escape(new_request.building)}\n"
            f"<b>Кабинет:</b> {escape(new_request.room)}\n"
            f"{pc_text}"
            f"<b>Телефон:</b> {escape(new_request.contact_phone or 'Не указан')}\n\n" 
            f"<b>Описание проблемы:</b>\n{escape(new_request.description[:150])}...\n\n"
            "Ожидайте уведомление о принятии заявки в работу."
        )
        await message.answer(confirmation_text, reply_markup=get_main_menu_keyboard(user_role))

        # --- Уведомление инженеров с новыми данными ---
        engineers = await get_users_by_role(session, UserRole.ENGINEER)
        if not engineers:
            logging.warning("No engineers found to notify about new request.")
        else:
            logging.info(f"Found {len(engineers)} engineers to notify.")
            view_button_callback_data = RequestActionCallback(action="view", request_id=new_request.id).pack()
            view_button = InlineKeyboardButton(text="👀 Посмотреть детали", callback_data=view_button_callback_data)
            notification_keyboard = InlineKeyboardBuilder().add(view_button).as_markup()

            pc_notify_text = f"\n<b>ПК/Инв.:</b> {escape(new_request.pc_number)}" if new_request.pc_number else ""
            notification_text = (
                f"🔔 Новая заявка №{new_request.id} от {user_mention}\n\n"
                f"<b>ФИО:</b> {escape(new_request.full_name or 'Не указано')}\n"
                f"<b>Корпус:</b> {escape(new_request.building)}, <b>Каб:</b> {escape(new_request.room)}{pc_notify_text}\n"
                f"<b>Телефон:</b> {escape(new_request.contact_phone or 'Не указан')}\n" 
                f"<b>Описание:</b> {escape(new_request.description[:200])}..."
            )

            sent_count = 0
            failed_count = 0
            for engineer in engineers:
                try:
                    await bot.send_message(
                        chat_id=engineer.id,
                        text=notification_text,
                        reply_markup=notification_keyboard
                    )
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    logging.error(f"Failed to send new request notification to engineer {engineer.id}: {e}")
            logging.info(f"Notifications sent: {sent_count}, failed: {failed_count}")

    except Exception as e:
        logging.error(f"Error creating request or notifying for user {requester_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при создании заявки. Попробуйте еще раз позже.",
            reply_markup=get_main_menu_keyboard(user_role)
        )

    await state.clear() 


@router.message(
    StateFilter(*all_create_request_states), 
    F.text, # Убеждаемся, что это текст
    F.text.notin_({SKIP_BTN_TEXT, CANCEL_BTN_TEXT}) 
)
async def process_invalid_text_input(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.warning(f"User {message.from_user.id} sent invalid text '{message.text}' in state {current_state}")
    if current_state == CreateRequest.waiting_for_pc_number.state:
        await message.answer("Пожалуйста, отправьте текст (инв. номер), нажмите 'Пропустить' или 'Отмена'.")
    else:
        # Общий ответ для других текстовых шагов
        await message.answer("Пожалуйста, введите запрашиваемые данные или нажмите 'Отмена'.")

@router.message(StateFilter(*all_create_request_states), ~F.text) 
async def process_invalid_content_input(message: types.Message, state: FSMContext):
     current_state = await state.get_state()
     logging.warning(f"User {message.from_user.id} sent non-text content ({message.content_type}) in state {current_state}")
     await message.answer("Пожалуйста, отправьте текстовое сообщение или нажмите 'Отмена'.")

