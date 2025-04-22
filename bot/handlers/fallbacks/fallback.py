# bot/handlers/common/fallback.py
import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext # Для проверки состояния

# Импортируем функции из модуля GPT
from bot.gpt.yagpt_integration import get_yagpt_response, get_gpt_status

router = Router()

# Этот хендлер ловит ЛЮБОЕ текстовое сообщение,
# которое не было поймано предыдущими хендлерами.
# Важно зарегистрировать этот роутер ПОСЛЕДНИМ.
# Фильтр F.text гарантирует, что это текстовое сообщение.
@router.message(F.text)
async def gpt_fallback_handler(message: types.Message, state: FSMContext, bot: Bot):
    # 1. Проверяем, включен ли GPT
    if not get_gpt_status():
        # Если выключен, можно ничего не делать или отправить стандартный ответ
        # logging.debug("GPT is disabled, ignoring message.")
        # await message.reply("Извините, не могу обработать ваш запрос сейчас.")
        return # Важно выйти, чтобы не обрабатывать дальше

    # 2. Проверяем, не находится ли пользователь в каком-либо состоянии FSM
    current_state = await state.get_state()
    if current_state is not None:
        # Если пользователь в FSM, игнорируем его "свободное" сообщение
        logging.debug(f"User {message.from_user.id} is in state {current_state}, ignoring fallback.")
        return # Выходим, чтобы не мешать FSM

    # 3. Если GPT включен и пользователь не в FSM, отправляем запрос к GPT
    user_text = message.text
    user_id = message.from_user.id
    logging.info(f"User {user_id} sent text for YandexGPT processing: '{user_text[:50]}...'")

    # Показываем индикатор "печатает..."
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    gpt_response = await get_yagpt_response(user_text)

    if gpt_response:
        try:
            # Отправляем ответ от GPT
            await message.reply(gpt_response)
        except Exception as e:
            logging.error(f"Failed to send GPT response to user {user_id}: {e}")
            await message.reply("Возникла проблема при отправке ответа.")
    else:
        # Если функция вернула None (ошибка уже залогирована)
        # Можно отправить сообщение об ошибке, но функция get_yagpt_response
        # уже возвращает текст ошибки, так что этот блок может быть не нужен
        # await message.reply("Не удалось получить ответ от нейросети.")
        pass