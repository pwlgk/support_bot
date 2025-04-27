# add_test_data.py
import asyncio
import os
import sys
import logging
import random
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

try:
    from db.database import AsyncSessionFactory, engine, Base
    from db.crud import (
        get_or_create_user, set_user_role, create_request,
        accept_request, complete_request, get_request, get_user
    )
    from db.models import UserRole, RequestStatus # Нужны Enum'ы
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

# --- ТЕСТОВЫЕ ДАННЫЕ ---

TEST_USERS = [
    # Клиенты (10)
    {"id": 111111111, "first_name": "Тест", "last_name": "Клиентов", "username": "testclient1", "role": UserRole.CLIENT},
    {"id": 222222222, "first_name": "Анна", "last_name": "Заявкина", "username": None, "role": UserRole.CLIENT},
    {"id": 987654321, "first_name": "Петр", "last_name": "Петров", "username": "peter_client", "role": UserRole.CLIENT},
    {"id": 666666666, "first_name": "Иван", "last_name": "Иванов", "username": "ivan_ivanov", "role": UserRole.CLIENT},
    {"id": 777777777, "first_name": "Мария", "last_name": "Сидорова", "username": None, "role": UserRole.CLIENT},
    {"id": 888888888, "first_name": "Алексей", "last_name": "Кузнецов", "username": "alex_kuz", "role": UserRole.CLIENT},
    {"id": 999999999, "first_name": "Ольга", "last_name": "Васильева", "username": "olga_v", "role": UserRole.CLIENT},
    {"id": 101010101, "first_name": "Дмитрий", "last_name": "Павлов", "username": "dima_p", "role": UserRole.CLIENT},
    {"id": 121212121, "first_name": "Екатерина", "last_name": "Новикова", "username": None, "role": UserRole.CLIENT},
    {"id": 131313131, "first_name": "Михаил", "last_name": "Морозов", "username": "moroz_m", "role": UserRole.CLIENT},

    # Инженеры (8)
    {"id": 333333333, "first_name": "Сергей", "last_name": "Инженеров", "username": "serg_eng", "role": UserRole.ENGINEER},
    {"id": 444444444, "first_name": "Елена", "last_name": "Техникова", "username": "lena_tech", "role": UserRole.ENGINEER},
    {"id": 141414141, "first_name": "Андрей", "last_name": "Волков", "username": "wolf_a", "role": UserRole.ENGINEER},
    {"id": 151515151, "first_name": "Татьяна", "last_name": "Зайцева", "username": None, "role": UserRole.ENGINEER},
    {"id": 161616161, "first_name": "Евгений", "last_name": "Соколов", "username": "evg_sokol", "role": UserRole.ENGINEER},
    {"id": 171717171, "first_name": "Наталья", "last_name": "Лебедева", "username": "nata_l", "role": UserRole.ENGINEER},
    {"id": 181818181, "first_name": "Артем", "last_name": "Козлов", "username": None, "role": UserRole.ENGINEER},
    {"id": 191919191, "first_name": "Ирина", "last_name": "Семенова", "username": "sem_ira", "role": UserRole.ENGINEER},

    # Администраторы (2)
    {"id": 555555555, "first_name": "Главный", "last_name": "Админов", "username": "super_admin", "role": UserRole.ADMIN},
    {"id": 202020202, "first_name": "Второй", "last_name": "Админ", "username": "admin_two", "role": UserRole.ADMIN},
]

CLIENT_IDS = [u['id'] for u in TEST_USERS if u['role'] == UserRole.CLIENT]
ENGINEER_IDS = [u['id'] for u in TEST_USERS if u['role'] == UserRole.ENGINEER]

TEST_REQUESTS_DATA = [
    {"description": "Не работает принтер HP LaserJet", "full_name": "Тестов Тест", "building": "Корпус А", "room": "101", "pc_number": "INV-PRN-001", "contact_phone": "+79001112233", "status": RequestStatus.WAITING},
    {"description": "Синий экран", "full_name": "Заявкина Анна", "building": "АБК", "room": "205", "pc_number": "COMP-ACC-05", "contact_phone": "55-66-77", "status": RequestStatus.WAITING},
    {"description": "Установить MS Office", "full_name": "Петров Петр", "building": "Корпус Б", "room": "310", "pc_number": None, "contact_phone": "+79119876543", "status": RequestStatus.IN_PROGRESS, "assign_to_engineer_index": 0},
    {"description": "Медленно работает 1С", "full_name": "Тестов Тест", "building": "Корпус А", "room": "102", "pc_number": "COMP-MAIN-15", "contact_phone": "+79001112244", "status": RequestStatus.IN_PROGRESS, "assign_to_engineer_index": 1},
    {"description": "Заменить картридж", "full_name": "Заявкина Анна", "building": "АБК", "room": "206", "pc_number": "INV-PRN-005", "contact_phone": "55-66-78", "status": RequestStatus.ARCHIVED, "assign_to_engineer_index": 0},
    {"description": "Проложить кабель", "full_name": "Петров Петр", "building": "Корпус Б", "room": "311", "pc_number": None, "contact_phone": "+79119876543", "status": RequestStatus.ARCHIVED, "assign_to_engineer_index": 1},
    {"description": "Сломалась мышка", "full_name": "Иванов Иван", "building": "Корпус В", "room": "401", "pc_number": None, "contact_phone": "+79221112233", "status": RequestStatus.WAITING},
    {"description": "Не открывается сайт", "full_name": "Сидорова Мария", "building": "АБК", "room": "205", "pc_number": "COMP-ACC-06", "contact_phone": "55-66-99", "status": RequestStatus.ARCHIVED, "assign_to_engineer_index": 2},
    {"description": "Проблема с доступом к папке", "full_name": "Кузнецов Алексей", "building": "Корпус Б", "room": "303", "pc_number": "COMP-ENG-01", "contact_phone": "+79339876511", "status": RequestStatus.WAITING},
    {"description": "Переустановить Windows", "full_name": "Васильева Ольга", "building": "Удаленно", "room": "-", "pc_number": "LAPTOP-01", "contact_phone": "11-22-33", "status": RequestStatus.WAITING},
    {"description": "Настроить VPN", "full_name": "Павлов Дмитрий", "building": "Корпус Г", "room": "50", "pc_number": None, "contact_phone": "+79441234567", "status": RequestStatus.IN_PROGRESS, "assign_to_engineer_index": 3},
    {"description": "Зависает Excel", "full_name": "Новикова Екатерина", "building": "АБК", "room": "210", "pc_number": "COMP-ACC-07", "contact_phone": "55-77-88", "status": RequestStatus.IN_PROGRESS, "assign_to_engineer_index": 4},
    {"description": "Не печатает из 1С", "full_name": "Морозов Михаил", "building": "Корпус Б", "room": "305", "pc_number": "COMP-MAN-02", "contact_phone": "+79558765432", "status": RequestStatus.IN_PROGRESS, "assign_to_engineer_index": 5},
    {"description": "Установить антивирус", "full_name": "Иванов Иван", "building": "Корпус В", "room": "402", "pc_number": "COMP-DEV-03", "contact_phone": "+79221112244", "status": RequestStatus.ARCHIVED, "assign_to_engineer_index": 6},
    {"description": "Подключить монитор", "full_name": "Сидорова Мария", "building": "АБК", "room": "211", "pc_number": "COMP-ACC-08", "contact_phone": "55-66-00", "status": RequestStatus.ARCHIVED, "assign_to_engineer_index": 7},
    {"description": "Обновить драйверы", "full_name": "Кузнецов Алексей", "building": "Корпус Б", "room": "304", "pc_number": "COMP-ENG-02", "contact_phone": "+79339876522", "status": RequestStatus.ARCHIVED, "assign_to_engineer_index": 0},
    {"description": "Не работает сканер ШК", "full_name": "Васильева Ольга", "building": "Склад", "room": "1", "pc_number": "SCAN-01", "contact_phone": "11-22-44", "status": RequestStatus.WAITING},
    {"description": "Заменить клавиатуру", "full_name": "Павлов Дмитрий", "building": "Корпус Г", "room": "55", "pc_number": "COMP-SALE-01", "contact_phone": "+79441234577", "status": RequestStatus.IN_PROGRESS, "assign_to_engineer_index": 1},
    {"description": "Почистить ПК от пыли", "full_name": "Новикова Екатерина", "building": "АБК", "room": "215", "pc_number": "COMP-ACC-09", "contact_phone": "55-77-99", "status": RequestStatus.ARCHIVED, "assign_to_engineer_index": 2},
    {"description": "Ошибка сохранения Word", "full_name": "Морозов Михаил", "building": "Корпус Б", "room": "306", "pc_number": "COMP-MAN-03", "contact_phone": "+79558765411", "status": RequestStatus.WAITING},
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

async def add_test_data():
    """Основная функция добавления/обновления пользователей и заявок."""
    log.info("--- Начало добавления тестовых данных ---")

    if not AsyncSessionFactory:
        log.error("Фабрика сессий AsyncSessionFactory недоступна. Невозможно продолжить.")
        return

    try:
        # 0. Убедимся, что таблицы существуют
        await create_db_tables_if_not_exist()

        # 1. Добавляем/обновляем пользователей
        log.info(f"--- Обработка {len(TEST_USERS)} пользователей ---")
        processed_users = 0
        failed_users = 0
        async with AsyncSessionFactory() as session:
            for user_data in TEST_USERS:
                user_id = user_data['id']
                role_to_set = user_data['role']
                try:
                    user_obj, created = await get_or_create_user(
                        session=session, user_id=user_id, first_name=user_data['first_name'],
                        last_name=user_data['last_name'], username=user_data['username']
                    )
                    if not user_obj:
                        log.warning(f"Не удалось создать/обновить пользователя ID: {user_id}")
                        failed_users += 1
                        continue

                    if user_obj.role != role_to_set:
                        updated_user = await set_user_role(session, user_id, role_to_set)
                        if updated_user:
                             pass 
                        else:
                            log.warning(f"Не удалось установить роль {role_to_set.name} для ID: {user_id}")

                    processed_users += 1
                except Exception as e:
                    log.error(f"Ошибка при обработке пользователя ID {user_id}: {e}", exc_info=False)
                    failed_users += 1
        log.info(f"Обработка пользователей завершена. Успешно: {processed_users}, Ошибки: {failed_users}")

        # 2. Добавляем заявки
        log.info(f"--- Обработка {len(TEST_REQUESTS_DATA)} заявок ---")
        processed_requests = 0
        failed_requests = 0
        request_ids = {} # Сохраним ID созданных заявок для статусов

        if not CLIENT_IDS or not ENGINEER_IDS:
             log.warning("Списки CLIENT_IDS или ENGINEER_IDS пусты. Невозможно создать связанные заявки.")
             return

        async with AsyncSessionFactory() as session:
            for i, req_data in enumerate(TEST_REQUESTS_DATA):
                # log.info(f"Создание заявки #{i+1}: {req_data['description'][:30]}...")
                requester_id = random.choice(CLIENT_IDS)
                try:
                    client_exists = await get_user(session, requester_id)
                    if not client_exists:
                        log.warning(f"Клиент с ID {requester_id} не найден для заявки #{i+1}. Пропуск.")
                        failed_requests += 1
                        continue

                    new_request = await create_request(
                        session=session, requester_id=requester_id, full_name=req_data['full_name'],
                        building=req_data['building'], room=req_data['room'], description=req_data['description'],
                        pc_number=req_data.get('pc_number'), contact_phone=req_data.get('contact_phone')
                    )
                    request_ids[i] = new_request.id

                    target_status = req_data['status']
                    current_request_obj = new_request # Начинаем с только что созданной заявки

                    if target_status in [RequestStatus.IN_PROGRESS, RequestStatus.ARCHIVED]:
                        engineer_index = req_data.get('assign_to_engineer_index')
                        if engineer_index is not None and 0 <= engineer_index < len(ENGINEER_IDS):
                            engineer_id = ENGINEER_IDS[engineer_index]
                            eng_exists = await get_user(session, engineer_id)
                            if not eng_exists:
                                 log.warning(f"Инженер с ID {engineer_id} не найден для заявки #{current_request_obj.id}. Невозможно назначить.")
                            else:
                                accepted_req = await accept_request(session, current_request_obj.id, engineer_id)
                                if accepted_req:
                                    current_request_obj = accepted_req # Обновляем объект
                                else:
                                    log.warning(f"Не удалось принять заявку #{current_request_obj.id} инженером {engineer_id}")
                        else:
                            log.warning(f"Некорректный индекс инженера ({engineer_index}) для заявки #{current_request_obj.id}")

                    if target_status == RequestStatus.ARCHIVED and current_request_obj.status == RequestStatus.IN_PROGRESS:
                        engineer_id_to_complete = current_request_obj.engineer_id
                        if engineer_id_to_complete:
                            completed_req = await complete_request(session, current_request_obj.id, engineer_id_to_complete)
                            if completed_req:
                                current_request_obj = completed_req
                            else:
                                log.warning(f"Не удалось завершить заявку #{current_request_obj.id}")
                        else:
                            log.warning(f"Невозможно завершить заявку #{current_request_obj.id}, т.к. не назначен инженер.")

                    if current_request_obj.status == RequestStatus.ARCHIVED:
                         days_ago_completed = random.randint(1, 10)
                         days_ago_accepted = days_ago_completed + random.randint(0, 3)
                         days_ago_created = days_ago_accepted + random.randint(0, 2)
                         now = datetime.utcnow()
                         # Устанавливаем прошлые даты, делая их timezone-naive
                         current_request_obj.completed_at = (now - timedelta(days=days_ago_completed)).replace(tzinfo=None)
                         current_request_obj.archived_at = (current_request_obj.completed_at + timedelta(minutes=random.randint(5, 60))).replace(tzinfo=None)
                         if current_request_obj.accepted_at: # Если дата принятия уже есть
                            current_request_obj.accepted_at = (now - timedelta(days=days_ago_accepted)).replace(tzinfo=None)
                         # Устанавливаем дату создания только если она еще не установлена (маловероятно)
                         # current_request_obj.created_at = (now - timedelta(days=days_ago_created)).replace(tzinfo=None)
                         session.add(current_request_obj) # Добавляем для сохранения изменений дат
                         await session.commit()

                    processed_requests += 1

                except Exception as e:
                    log.error(f"Ошибка при обработке заявки #{i+1}: {e}", exc_info=False)
                    failed_requests += 1
                    await session.rollback()

        log.info(f"Обработка заявок завершена. Успешно: {processed_requests}, Ошибки: {failed_requests}")

    except Exception as e:
        log.error(f"Критическая ошибка во время выполнения скрипта: {e}", exc_info=True)
    finally:
         if engine:
             await engine.dispose()
             log.info("Пул соединений SQLAlchemy закрыт.")


if __name__ == "__main__":
    print("--- Запуск скрипта добавления тестовых данных (20 пользователей и 20 заявок) ---")

    if not DATABASE_URL:
        print("\n!!! Ошибка: DATABASE_URL не найден.")
        sys.exit(1)
    else:
        url_safe_parts = DATABASE_URL.split('@')
        url_display = url_safe_parts[0].split(':')[0] + ':********@' + url_safe_parts[1] if '@' in DATABASE_URL and ':' in url_safe_parts[0] else DATABASE_URL
        print(f"Используется URL базы данных (скрыты учетные данные): {url_display}")

    # Закомментировать, если не нужно каждый раз удалять всё
    # print("\n!!! ВНИМАНИЕ: Сейчас база данных будет очищена и заполнена тестовыми данными.")
    # print("!!! Прервите выполнение (Ctrl+C), если это нежелательно.")
    # try:
    #    asyncio.sleep(5)
    # except KeyboardInterrupt:
    #    print("\nОтмена операции.")
    #    sys.exit(0)
    #
    # async def drop_create():
    #      log.info("Удаление и создание таблиц...")
    #      async with engine.begin() as conn:
    #          await conn.run_sync(Base.metadata.drop_all)
    #          await conn.run_sync(Base.metadata.create_all)
    #      log.info("Таблицы пересозданы.")
    # asyncio.run(drop_create())

    # Запускаем основную асинхронную функцию
    asyncio.run(add_test_data())

    print("--- Скрипт завершил работу ---")