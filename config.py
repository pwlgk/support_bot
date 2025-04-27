# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Загрузка токена бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 2. Загрузка параметров подключения к БД
db_user = os.getenv("POSTGRES_USER")
db_password = os.getenv("POSTGRES_PASSWORD")
db_host = os.getenv("DATABASE_HOST") 
db_port = os.getenv("DATABASE_PORT", "5432") # Используем порт по умолчанию 5432, если не указан
db_name = os.getenv("POSTGRES_DB")

# 3. Валидация обязательных переменных
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

if missing_vars:
    print(f"Ошибка: Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    exit(1)

# 4. Формирование строки подключения к БД
DATABASE_URL = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
