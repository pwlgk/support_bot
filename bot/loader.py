# bot/loader.py
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties # <--- ДОБАВИТЬ ЭТОТ ИМПОРТ
from config import BOT_TOKEN

storage = MemoryStorage()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

dp = Dispatcher(storage=storage)