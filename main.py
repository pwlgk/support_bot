# main.py
import asyncio
import logging
import argparse # <--- Импорт для парсинга аргументов

# Импорты роутеров
from bot.handlers.admin import admin_panel as admin_main_router
# from bot.handlers.admin import manage_users as admin_users_router # Убрали этот роутер
from bot.handlers.client import new_request as client_new_request_router
from bot.handlers.client import view_requests as client_view_router
from bot.handlers.engineer import manage_requests as engineer_manage_router
from bot.handlers import common

# Импорты базы данных и middleware
from db.database import engine, Base, AsyncSessionFactory
from db import models # noqa
# --- ИМПОРТ CRUD ФУНКЦИИ ---
from db.crud import set_user_role, get_user
from db.models import UserRole # Импортируем роли
from bot.middlewares.db import DbSessionMiddleware
from bot.loader import bot, dp # Загружаем bot и dp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def create_db_tables():
    """Создает таблицы в БД, если они не существуют."""
    logging.info("Checking and creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Database tables checked/created.")

# --- ФУНКЦИЯ ДЛЯ УСТАНОВКИ АДМИНА ---
async def set_initial_admin(user_id: int):
    """Устанавливает роль ADMIN пользователю с указанным ID."""
    logging.info(f"Attempting to set user {user_id} as initial admin...")
    # Используем фабрику сессий для создания сессии внутри этой функции
    async with AsyncSessionFactory() as session:
        try:
            # Проверяем, существует ли пользователь
            check_user = await get_user(session, user_id)
            if not check_user:
                logging.error(f"Cannot set admin: User with ID {user_id} not found in the database. User must start the bot first.")
                return False # Возвращаем False при неудаче

            # Устанавливаем роль
            updated_user = await set_user_role(session, user_id, UserRole.ADMIN)
            if updated_user:
                logging.info(f"Successfully set user {user_id} ({updated_user.first_name}) role to ADMIN.")
                return True # Возвращаем True при успехе
            else:
                logging.error(f"Failed to set role ADMIN for user {user_id}.")
                return False
        except Exception as e:
            logging.error(f"Error during initial admin setup for user {user_id}: {e}", exc_info=True)
            return False

async def main():
    # --- ПАРСИНГ АРГУМЕНТОВ КОМАНДНОЙ СТРОКИ ---
    parser = argparse.ArgumentParser(description="Support Bot")
    parser.add_argument(
        "--set-admin",
        type=int,
        metavar="USER_ID",
        help="Set the user with the specified Telegram ID as the initial administrator."
    )
    args = parser.parse_args()

    # 1. Создаем таблицы
    await create_db_tables()

    # --- УСТАНОВКА АДМИНА, ЕСЛИ УКАЗАН АРГУМЕНТ ---
    if args.set_admin:
        admin_user_id = args.set_admin
        success = await set_initial_admin(admin_user_id)
        if not success:
            # Если не удалось установить админа, возможно, стоит прервать запуск
            logging.critical(f"Failed to set initial admin {admin_user_id}. Exiting.")
            return # Прерываем выполнение main
        # Если успешно, продолжаем запуск бота

    # 2. Конфигурируем Dispatcher
    dp['bot'] = bot
    db_middleware = DbSessionMiddleware(session_pool=AsyncSessionFactory)
    dp.update.outer_middleware.register(db_middleware)

    # 3. Регистрируем роутеры
    logging.info("Registering routers...")
    dp.include_router(admin_main_router.router)
    dp.include_router(client_new_request_router.router)
    dp.include_router(client_view_router.router)
    dp.include_router(engineer_manage_router.router)
    dp.include_router(common.router)

    # 4. Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook deleted. Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logging.info("Stopping polling. Closing resources...")
        await engine.dispose()
        await bot.session.close()
        logging.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user.")
    except Exception as e:
         logging.error(f"Unhandled exception in main: {e}", exc_info=True)