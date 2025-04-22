# bot/handlers/client/view_requests.py
import logging
from html import escape  # Импортируем стандартную функцию для HTML-экранирования

from aiogram import F, Router, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.reply import \
    MY_REQUESTS_BTN_TEXT  # Импортируем текст кнопки клиента
from db.crud import \
    get_client_requests  # Импортируем CRUD функцию для получения заявок клиента
from db.models import RequestStatus  # Импортируем Enum статусов

# Создаем роутер для этого модуля
router = Router()

# Карта для преобразования статусов Enum в человекочитаемый текст для клиента
STATUS_MAP_CLIENT = {
    RequestStatus.WAITING: "⏳ Ожидает принятия",
    RequestStatus.IN_PROGRESS: "🛠️ В работе",
    # Статус COMPLETED не показываем клиенту отдельно, т.к. он сразу уходит в архив
    # RequestStatus.COMPLETED: "✅ Выполнена (ожидает архивации)",
    # Статусы ARCHIVED и CANCELED отфильтровываются в CRUD-запросе
}

@router.message(F.text == MY_REQUESTS_BTN_TEXT)
@router.message(Command("my_requests"))
async def client_view_my_requests(message: types.Message, session: AsyncSession):
    """
    Обработчик для кнопки "Мои заявки" и команды /my_requests клиента.
    Получает и отображает список активных (не архивных, не отмененных) заявок пользователя.
    """
    user_id = message.from_user.id
    if not user_id:
        # На всякий случай, хотя для message это маловероятно
        await message.answer("Не удалось определить ваш ID.")
        return

    logging.info(f"Client {user_id} requested their requests list.")

    # Получаем список заявок из базы данных
    try:
        requests_list = await get_client_requests(session, user_id)
    except Exception as e:
        logging.error(f"Database error fetching requests for client {user_id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка при загрузке ваших заявок. Попробуйте позже.")
        return

    # Проверяем, есть ли заявки
    if not requests_list:
        await message.answer("У вас пока нет активных или ожидающих заявок.")
        return

    # Формируем ответ
    response_lines = ["<b>Ваши текущие заявки:</b>\n"] # Заголовок с HTML-тегом жирного шрифта
    for req in requests_list:
        # Получаем текстовое представление статуса
        status_text = STATUS_MAP_CLIENT.get(req.status, f"Неизвестный ({req.status.value})")

        # Добавляем информацию об инженере, если он назначен
        engineer_info = ""
        if req.engineer and req.status == RequestStatus.IN_PROGRESS: # Показываем инженера только если заявка в работе
            # Экранируем имя инженера
            safe_engineer_name = escape(req.engineer.first_name or f"ID {req.engineer.id}")
            engineer_info = f" (Инженер: {safe_engineer_name})"

        # Экранируем описание на случай HTML-символов и берем только часть
        safe_description = escape(req.description[:60]) # Ограничиваем длину описания

        # Форматируем строку для одной заявки
        response_lines.append(
            f"<b>#{req.id}</b> ({req.created_at.strftime('%d.%m.%y')}) - {status_text}{engineer_info}\n"
            f"   <i>Описание:</i> {safe_description}..."
        )

    # Собираем итоговое сообщение
    full_response = "\n\n".join(response_lines)

    # TODO: Добавить пагинацию для клиента, если заявок очень много.
    # TODO: Добавить инлайн-кнопки для просмотра ПОЛНЫХ деталей каждой заявки,
    #       если потребуется (сейчас показываем краткую информацию).

    # Отправляем сообщение пользователю
    try:
        # Отправляем, используя parse_mode по умолчанию (HTML)
        await message.answer(full_response)
    except Exception as e:
        # Обрабатываем возможные ошибки отправки (например, сообщение слишком длинное)
        logging.error(f"Error sending client request list message for user {user_id}: {e}", exc_info=True)
        await message.answer("Не удалось отобразить список заявок из-за ошибки.")