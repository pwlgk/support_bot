# add_test_users.py
import asyncio
import os
import sys
import logging
from pathlib import Path

# --- Добавляем корень проекта в sys.path ---
# Убедитесь, что этот путь корректен для вашего расположения скрипта
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# --- Импорты из вашего проекта ---
try:
    from db.database import AsyncSessionFactory, engine, Base
    # --- ИЗМЕНЕНО: Используем get_or_create_user вместо create_or_update_user ---
    from db.crud import get_or_create_user, set_user_role
    from db.models import UserRole
    from config import DATABASE_URL
except ImportError as e:
    print(f"Ошибка импорта модулей проекта: {e}")
    print("Убедитесь, что вы запускаете этот скрипт из корневой папки проекта,")
    print("и что ваша виртуальная среда активирована и содержит все зависимости (`pip install -r requirements.txt`).")
    sys.exit(1)
except Exception as e:
    print(f"Произошла непредвиденная ошибка при импорте: {e}")
    sys.exit(1)

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# --- Загрузка переменных окружения ---
if not load_dotenv():
    log.warning("Не удалось загрузить файл .env. Убедитесь, что он существует и содержит учетные данные БД.")

# --- ТЕСТОВЫЕ ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ---
TEST_USERS = [
    # Клиенты
    {"id": 111111111, "first_name": "Тест", "last_name": "Клиентов", "username": "testclient1", "role": UserRole.CLIENT},
    {"id": 222222222, "first_name": "Анна", "last_name": "Заявкина", "username": None, "role": UserRole.CLIENT},
    {"id": 987654321, "first_name": "Петр", "last_name": None, "username": "peter_client", "role": UserRole.CLIENT},

    # Инженеры
    {"id": 333333333, "first_name": "Сергей", "last_name": "Инженеров", "username": "serg_eng", "role": UserRole.ENGINEER},
    {"id": 444444444, "first_name": "Елена", "last_name": "Техникова", "username": "lena_tech", "role": UserRole.ENGINEER},
    {"id": 123456789, "first_name": "Виктор", "last_name": "Ремонтов", "username": None, "role": UserRole.ENGINEER},

    # Администратор
    {"id": 555555555, "first_name": "Главный", "last_name": "Админов", "username": "super_admin", "role": UserRole.ADMIN},
]

async def create_db_tables_if_not_exist():
    """Создает таблицы в БД, если они не существуют."""
    log.info("Проверка и создание таблиц БД (если необходимо)...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Таблицы БД проверены/созданы.")
    except Exception as e:
        log.error(f"Ошибка при создании таблиц: {e}", exc_info=True)
        raise

async def add_test_users():
    """Основная функция добавления/обновления пользователей."""
    log.info("Попытка добавления/обновления тестовых пользователей...")

    if not AsyncSessionFactory:
        log.error("Фабрика сессий AsyncSessionFactory недоступна. Невозможно продолжить.")
        return

    try:
        await create_db_tables_if_not_exist()

        processed_count = 0
        failed_count = 0

        async with AsyncSessionFactory() as session:
            for user_data in TEST_USERS:
                user_id = user_data['id']
                role_to_set = user_data['role']
                log.info(f"Обработка пользователя ID: {user_id} ({user_data['first_name']}) с ролью {role_to_set.name}")

                try:
                    # --- ИЗМЕНЕНО: Используем get_or_create_user ---
                    # Эта функция сама создает или обновляет и коммитит изменения имени/username
                    user_obj, created = await get_or_create_user(
                        session=session,
                        user_id=user_id,
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name'],
                        username=user_data['username']
                    )
                    log_prefix = "Создан" if created else "Обновлен"
                    log.info(f"{log_prefix} пользователь ID: {user_id}")

                    # --- ИЗМЕНЕНО: Устанавливаем роль только если она отличается ---
                    # Функция set_user_role теперь используется только для изменения роли,
                    # так как get_or_create_user уже создала пользователя (если нужно)
                    if user_obj.role != role_to_set:
                        log.info(f"Установка роли {role_to_set.name} для пользователя ID: {user_id}")
                        updated_user_with_role = await set_user_role(
                            session=session,
                            user_id=user_id,
                            role=role_to_set # <--- ИЗМЕНЕНО ЗДЕСЬ
                        )
                        if updated_user_with_role:
                            log.info(f"Роль {updated_user_with_role.role.name} успешно установлена для ID: {user_id}")
                        else:
                            log.warning(f"Не удалось установить роль {role_to_set.name} для ID: {user_id} (возможно, ошибка в set_user_role)")
                            # Не считаем это критической ошибкой, но отмечаем
                    else:
                        log.info(f"Пользователь ID: {user_id} уже имеет роль {role_to_set.name}, установка роли пропущена.")

                    processed_count += 1

                except Exception as e:
                    log.error(f"Ошибка при обработке пользователя ID {user_id}: {e}", exc_info=False)
                    failed_count += 1
                    # Откат больше не нужен здесь явно, так как get_or_create_user и set_user_role
                    # должны управлять своими коммитами/откатами внутри себя

            # Финальный коммит не требуется, если CRUD функции коммитят сами

        log.info(f"Обработка тестовых пользователей завершена. Успешно: {processed_count}, Ошибки: {failed_count}")

    except Exception as e:
        log.error(f"Критическая ошибка во время выполнения скрипта: {e}", exc_info=True)
    finally:
         if engine:
             await engine.dispose()
             log.info("Пул соединений SQLAlchemy закрыт.")


if __name__ == "__main__":
    print("--- Запуск скрипта добавления тестовых пользователей ---")

    if not DATABASE_URL:
        print("\n!!! Ошибка: DATABASE_URL не найден в конфигурации или .env файле.")
        print("!!! Убедитесь, что файл .env существует в корне проекта и содержит корректную строку")
        print("!!! или что переменная окружения DATABASE_URL установлена.")
        sys.exit(1)
    else:
        # Показываем URL без пароля
        url_safe_parts = DATABASE_URL.split('@')
        url_display = url_safe_parts[0].split(':')[0] + ':********@' + url_safe_parts[1] if '@' in DATABASE_URL and ':' in url_safe_parts[0] else DATABASE_URL
        print(f"Используется URL базы данных (скрыты учетные данные): {url_display}")

    asyncio.run(add_test_users())

    print("--- Скрипт завершил работу ---")