# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL") # Добавлено
YAGPT_API_KEY = os.getenv("YAGPT_API_KEY")
YAGPT_FOLDER_ID = os.getenv("YAGPT_FOLDER_ID")
YAGPT_ENABLED_BY_DEFAULT = bool(YAGPT_API_KEY and YAGPT_FOLDER_ID)

if not BOT_TOKEN:
    print("Ошибка: Не найден BOT_TOKEN в .env файле!")
    exit()
if not DATABASE_URL: # Добавлено
    print("Ошибка: Не найден DATABASE_URL в .env файле!")
    exit()
    YAGPT_ENABLED_BY_DEFAULT = bool(YAGPT_API_KEY and YAGPT_FOLDER_ID) # Включен по умолчанию, если есть ключи
if not YAGPT_API_KEY or not YAGPT_FOLDER_ID:
    print("Warning: Yandex")