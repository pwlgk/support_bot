# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла (если он есть)
# Это важно делать в самом начале
load_dotenv()

# 1. Загрузка токена бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 2. Загрузка параметров подключения к БД
db_user = os.getenv("POSTGRES_USER")
db_password = os.getenv("POSTGRES_PASSWORD")
db_host = os.getenv("DATABASE_HOST") # Ожидается имя сервиса Docker ('db') или 'localhost'
db_port = os.getenv("DATABASE_PORT", "5432") # Используем порт по умолчанию 5432, если не указан
db_name = os.getenv("POSTGRES_DB")

# 3. Валидация обязательных переменных
# Собираем список отсутствующих переменных для более информативной ошибки
missing_vars = []
if not BOT_TOKEN:
    missing_vars.append("BOT_TOKEN")
if not db_user:
    missing_vars.append("POSTGRES_USER")
if not db_password:
    missing_vars.append("POSTGRES_PASSWORD")
if not db_host:
    missing_vars.append("DATABASE_HOST")
if not db_name:
    missing_vars.append("POSTGRES_DB")
# db_port имеет значение по умолчанию, поэтому его не обязательно проверять здесь

# Если есть отсутствующие переменные, выводим ошибку и выходим
if missing_vars:
    print(f"Ошибка: Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    # Используем exit(1), чтобы обозначить выход с ошибкой
    exit(1)

# 4. Формирование строки подключения к БД
# Этот код выполнится только если все необходимые переменные (кроме db_port) были найдены
DATABASE_URL = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
# config.py
# ...
print(f"!!!!!!!!!! DEBUG: Password being used by bot = '{db_password}' !!!!!!!!!!!") # Добавьте эту строку
print(DATABASE_URL)
# ... остальной код валидации и сборки DATABASE_URL ...