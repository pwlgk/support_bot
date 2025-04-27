# main.py
import asyncio
import logging
import argparse # Для обработки аргументов командной строки
import sys # Для завершения работы скрипта

# Импорты обработчиков (роутеров)
from bot.handlers.admin import admin_panel as admin_main_router
from bot.handlers.client import new_request as client_new_request_router
from bot.handlers.client import view_requests as client_view_router
from bot.handlers.engineer import manage_requests as engineer_manage_router
from bot.handlers import common

# Импорты для работы с базой данных и middlewares
from db.database import engine, Base, AsyncSessionFactory
from db import models # noqa: Импортируем модели для создания таблиц SQLAlchemy
from db.crud import set_user_role, get_user
from db.models import UserRole
from bot.middlewares.db import DbSessionMiddleware

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def create_db_tables():
    """Проверяет и создает таблицы в базе данных, если они не существуют."""
    # Логирование: Начало проверки/создания таблиц БД
    logging.info("Проверка и создание таблиц базы данных...")
    try:
        async with engine.begin() as conn:
            # Используем run_sync для вызова синхронной функции create_all
            await conn.run_sync(Base.metadata.create_all)
        # Логирование: Успешное завершение проверки/создания таблиц
        logging.info("Таблицы базы данных проверены/созданы.")
        return True
    except Exception as e:
        # Логирование: Ошибка при подключении или создании таблиц
        logging.error(f"Не удалось подключиться или создать таблицы базы данных: {e}", exc_info=True)
        return False

async def set_initial_admin(user_id: int):
    """Назначает роль ADMIN пользователю с заданным Telegram ID."""
    # Логирование: Попытка назначения роли администратора
    logging.info(f"Попытка установить пользователя {user_id} как первоначального администратора...")
    async with AsyncSessionFactory() as session:
        try:
            # Проверяем, существует ли пользователь в БД
            check_user = await get_user(session, user_id)
            if not check_user:
                # Логирование: Ошибка - пользователь не найден
                logging.error(f"Невозможно назначить админа: Пользователь с ID {user_id} не найден. Пользователь должен сначала запустить бота.")
                return False

            # Устанавливаем роль
            updated_user = await set_user_role(session, user_id, UserRole.ADMIN)
            if updated_user:
                # Логирование: Успешное назначение роли
                logging.info(f"Роль ADMIN успешно установлена для пользователя {user_id} ({updated_user.first_name}).")
                return True
            else:
                # Эта ветка маловероятна при текущей логике set_user_role, но оставим для полноты
                # Логирование: Неудача при установке роли (внутренняя логика)
                logging.error(f"Не удалось установить роль ADMIN для пользователя {user_id}.")
                return False
        except Exception as e:
            # Логирование: Ошибка в процессе установки администратора
            logging.error(f"Ошибка при установке первоначального администратора для пользователя {user_id}: {e}", exc_info=True)
            return False
        finally:
             # Освобождаем ресурсы БД, так как скрипт завершится после этой операции
             await engine.dispose()
             # Логирование: Освобождение ресурсов БД
             logging.info("Движок БД освобожден после попытки установки администратора.")


async def run_bot():
    """Настраивает и запускает бота в режиме поллинга."""
    # Импортируем объекты бота и диспетчера только при реальном запуске
    from bot.loader import bot, dp

    # Логирование: Начало настройки диспетчера и роутеров
    logging.info("Настройка диспетчера и роутеров для поллинга бота...")
    # Передаем объект бота в диспетчер
    dp['bot'] = bot
    # Создаем и регистрируем middleware для сессий БД
    db_middleware = DbSessionMiddleware(session_pool=AsyncSessionFactory)
    dp.update.outer_middleware.register(db_middleware)

    # Подключаем роутеры к диспетчеру
    dp.include_router(admin_main_router.router)
    dp.include_router(client_new_request_router.router)
    dp.include_router(client_view_router.router)
    dp.include_router(engineer_manage_router.router)
    dp.include_router(common.router)
    # Логирование: Успешная регистрация роутеров
    logging.info("Роутеры зарегистрированы.")

    # Удаляем вебхук (если был) и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    # Логирование: Удаление вебхука и запуск поллинга
    logging.info("Вебхук удален. Запуск поллинга...")
    try:
        # Запуск получения обновлений
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Логирование: Начало остановки поллинга и закрытия ресурсов
        logging.info("Остановка поллинга. Закрытие ресурсов...")
        # Закрываем соединение с БД и сессию бота
        # Повторный вызов dispose() безопасен, если он уже был вызван в set_initial_admin
        await engine.dispose()
        await bot.session.close()
        # Логирование: Успешное завершение поллинга
        logging.info("Поллинг бота остановлен.")


async def main():
    # Настройка парсера аргументов командной строки
    parser = argparse.ArgumentParser(description="Support Bot")
    parser.add_argument(
        "--set-admin",
        type=int,
        metavar="USER_ID",
        help="Установить пользователя с указанным Telegram ID как первоначального администратора и выйти." # Переведенный help
    )
    args = parser.parse_args()

    # Инициализация базы данных (необходима в любом случае)
    db_ready = await create_db_tables()
    if not db_ready:
         # Логирование: Критическая ошибка инициализации БД
         logging.critical("Инициализация базы данных не удалась. Завершение работы.")
         # Освобождаем ресурсы движка БД перед выходом
         await engine.dispose()
         sys.exit(1) # Выход с кодом ошибки

    # Если указан флаг --set-admin, устанавливаем админа и выходим
    if args.set_admin:
        admin_user_id = args.set_admin
        success = await set_initial_admin(admin_user_id)
        if success:
            # Логирование: Успешная установка админа через аргумент
            logging.info(f"Роль администратора установлена для пользователя {admin_user_id}. Скрипт завершен.")
        else:
            # Логирование: Неудача установки админа через аргумент
            logging.critical(f"Не удалось установить первоначального администратора {admin_user_id}. Скрипт завершен с ошибками.")
        # Завершаем работу скрипта (engine.dispose() уже вызван в set_initial_admin)
        sys.exit(0 if success else 1) # 0 - успех, 1 - ошибка

    # Если флаг --set-admin не указан, запускаем бота
    # Логирование: Запуск бота в обычном режиме
    logging.info("Флаг --set-admin не указан, запуск поллинга бота...")
    await run_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as e:
        # Обработка штатного завершения (Ctrl+C или sys.exit)
        # Успешный выход после --set-admin (код 0) - это ожидаемое поведение
        if isinstance(e, SystemExit) and e.code == 0:
             # Логирование: Штатное завершение скрипта (например, после --set-admin)
             logging.info("Скрипт завершен штатно.")
        else:
             # Логирование: Остановка бота пользователем или системой
             logging.info("Бот остановлен пользователем или системным выходом.")
    except Exception as e:
         # Логирование непредвиденных ошибок на верхнем уровне
         logging.error(f"Необработанное исключение в main: {e}", exc_info=True)