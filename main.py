# main.py
import asyncio
import logging
import argparse # <--- Импорт для парсинга аргументов
import sys # <-- Добавляем sys для выхода

# Импорты роутеров
from bot.handlers.admin import admin_panel as admin_main_router
from bot.handlers.client import new_request as client_new_request_router
from bot.handlers.client import view_requests as client_view_router
from bot.handlers.engineer import manage_requests as engineer_manage_router
from bot.handlers import common

# Импорты базы данных и middleware
# --- ИЗМЕНЕНО: Убираем bot, dp из импорта bot.loader здесь ---
# Они понадобятся только если мы *действительно* запускаем бота
from db.database import engine, Base, AsyncSessionFactory
from db import models # noqa
from db.crud import set_user_role, get_user
from db.models import UserRole
from bot.middlewares.db import DbSessionMiddleware
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def create_db_tables():
    """Создает таблицы в БД, если они не существуют."""
    logging.info("Checking and creating database tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logging.info("Database tables checked/created.")
        return True
    except Exception as e:
        logging.error(f"Failed to connect or create database tables: {e}", exc_info=True)
        return False

async def set_initial_admin(user_id: int):
    """Устанавливает роль ADMIN пользователю с указанным ID."""
    logging.info(f"Attempting to set user {user_id} as initial admin...")
    async with AsyncSessionFactory() as session:
        try:
            check_user = await get_user(session, user_id)
            if not check_user:
                logging.error(f"Cannot set admin: User with ID {user_id} not found in the database. User must start the bot first.")
                return False

            updated_user = await set_user_role(session, user_id, UserRole.ADMIN)
            if updated_user:
                logging.info(f"Successfully set user {user_id} ({updated_user.first_name}) role to ADMIN.")
                return True
            else:
                logging.error(f"Failed to set role ADMIN for user {user_id}.")
                return False
        except Exception as e:
            logging.error(f"Error during initial admin setup for user {user_id}: {e}", exc_info=True)
            return False
        finally:
             # Закрываем engine здесь, так как при set-admin дальше не идем
             await engine.dispose()
             logging.info("DB Engine disposed after admin setup attempt.")


async def run_bot():
    """Функция для настройки и запуска самого бота (поллинга)."""
    # --- ИЗМЕНЕНО: Импортируем bot, dp только здесь ---
    from bot.loader import bot, dp
    # --------------------------------------------------

    logging.info("Configuring dispatcher and routers for bot polling...")
    # 2. Конфигурируем Dispatcher
    dp['bot'] = bot
    db_middleware = DbSessionMiddleware(session_pool=AsyncSessionFactory)
    dp.update.outer_middleware.register(db_middleware)

    # 3. Регистрируем роутеры
    dp.include_router(admin_main_router.router)
    dp.include_router(client_new_request_router.router)
    dp.include_router(client_view_router.router)
    dp.include_router(engineer_manage_router.router)
    dp.include_router(common.router)
    logging.info("Routers registered.")

    # 4. Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook deleted. Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logging.info("Stopping polling. Closing resources...")
        # engine может быть уже закрыт, если был --set-admin, но dispose безопасен для повторного вызова
        await engine.dispose()
        await bot.session.close()
        logging.info("Bot polling stopped.")


async def main():
    # --- ПАРСИНГ АРГУМЕНТОВ КОМАНДНОЙ СТРОКИ ---
    parser = argparse.ArgumentParser(description="Support Bot")
    parser.add_argument(
        "--set-admin",
        type=int,
        metavar="USER_ID",
        help="Set the user with the specified Telegram ID as the initial administrator and exit." # Обновили help
    )
    args = parser.parse_args()

    # 1. Создаем таблицы (всегда нужно, т.к. set_admin требует их наличия)
    db_ready = await create_db_tables()
    if not db_ready:
         logging.critical("Database initialization failed. Exiting.")
         # Закрываем engine и выходим, если БД недоступна
         await engine.dispose()
         sys.exit(1) # Выход с кодом ошибки

    # --- УСТАНОВКА АДМИНА И ВЫХОД, ЕСЛИ УКАЗАН АРГУМЕНТ ---
    if args.set_admin:
        admin_user_id = args.set_admin
        success = await set_initial_admin(admin_user_id)
        if success:
            logging.info(f"Admin role set for user {admin_user_id}. Script finished.")
        else:
            logging.critical(f"Failed to set initial admin {admin_user_id}. Script finished with errors.")
        # --- ИЗМЕНЕНО: Выходим из main после попытки установить админа ---
        # engine.dispose() вызывается внутри set_initial_admin
        sys.exit(0 if success else 1) # Выход с кодом 0 при успехе, 1 при ошибке
        # -----------------------------------------------------------

    # --- ЕСЛИ --set-admin НЕ БЫЛ УКАЗАН, ЗАПУСКАЕМ БОТА ---
    logging.info("No --set-admin flag provided, starting bot polling...")
    await run_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as e:
        # Обрабатываем SystemExit с кодом 0 (успешный выход после set-admin) как нормальный выход
        if isinstance(e, SystemExit) and e.code == 0:
             logging.info("Script finished as expected.")
        else:
             logging.info("Bot stopped by user or system exit.")
    except Exception as e:
         logging.error(f"Unhandled exception in main: {e}", exc_info=True)