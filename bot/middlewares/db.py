# bot/middlewares/db.py
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject # Базовый тип для событий (Message, CallbackQuery)
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware для создания и передачи сессии SQLAlchemy в хендлеры.
    """
    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        super().__init__()
        # Сохраняем фабрику сессий (session pool)
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject, # Событие (Message, CallbackQuery и т.д.)
        data: Dict[str, Any]   # Данные, которые передаются в хендлер
    ) -> Any:
        """
        Выполняется для каждого события (update).

        :param handler: Следующий обработчик в цепочке (или сам хендлер).
        :param event: Пришедшее событие (апдейт).
        :param data: Словарь с данными для передачи хендлеру.
        :return: Результат выполнения хендлера.
        """
        # Создаем сессию из пула (фабрики)
        async with self.session_pool() as session:
            # Добавляем объект сессии в словарь data под ключом 'session'.
            # Имя ключа ('session') должно совпадать с именем аргумента
            # в хендлере (например, session: AsyncSession).
            data['session'] = session

            # Вызываем следующий обработчик в цепочке, передавая ему событие и обновленные данные
            result = await handler(event, data)

        # Сессия автоматически коммитится (если не было ошибок) или
        # откатывается (если возникло исключение) благодаря 'async with'.
        # Возвращаем результат выполнения хендлера.
        return result