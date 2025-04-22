# db/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
# --- ИЗМЕНИТЬ ИМПОРТЫ ---
# Убираем declarative_base, импортируем DeclarativeBase
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)

# Создаем базовый класс для декларативных моделей с поддержкой AsyncAttrs
# AsyncAttrs нужен для удобной работы со связанными объектами в async коде
class Base(AsyncAttrs, DeclarativeBase):
    pass

# Создаем фабрику для асинхронных сессий
# expire_on_commit=False предотвращает истечение срока действия объектов после коммита
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)
