# db/models.py
from sqlalchemy import (BigInteger, Column, DateTime, ForeignKey, Integer,
                        String, Enum as SQLEnum, Text, func)
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
import datetime

# Импортируем базовый класс для моделей SQLAlchemy
from .database import Base

# Определяем возможные роли пользователей через Enum
class UserRole(PyEnum):
    CLIENT = "client"
    ENGINEER = "engineer"
    ADMIN = "admin"

# Определяем возможные статусы заявок через Enum
class RequestStatus(PyEnum):
    WAITING = "waiting"       # Ожидает назначения
    IN_PROGRESS = "in_progress" # В работе у инженера
    COMPLETED = "completed"   # Выполнена
    ARCHIVED = "archived"     # В архиве (для статистики, скрыта из активных)
    CANCELED = "canceled"     # Отменена

# Модель пользователя (клиент, инженер, админ)
class User(Base):
    __tablename__ = 'users'
    # Используем BigInteger для ID Telegram, так как он может превышать стандартный Integer
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=False)
    username = Column(String, nullable=True) # Имя пользователя в Telegram
    first_name = Column(String, nullable=True) # Имя
    last_name = Column(String, nullable=True)  # Фамилия
    # Роль пользователя в системе (из UserRole enum)
    # Явное имя 'user_role_enum' для SQL Enum типа улучшает совместимость
    role = Column(SQLEnum(UserRole, name="user_role_enum"), default=UserRole.CLIENT, nullable=False)
    phone_number = Column(String, nullable=True) # Номер телефона (может быть запрошен позже)
    # Дата и время регистрации пользователя (автоматически устанавливается БД)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связь "один ко многим": один пользователь может создать много заявок
    # lazy="selectin" оптимизирует загрузку: связанные заявки грузятся одним доп. запросом
    created_requests = relationship(
        "Request",
        back_populates="requester", # Обратная связь с моделью Request (поле requester)
        foreign_keys="Request.requester_id", # Указываем внешний ключ для этой связи
        lazy="selectin"
    )
    # Связь "один ко многим": один инженер может быть назначен на много заявок
    assigned_requests = relationship(
        "Request",
        back_populates="engineer", # Обратная связь с моделью Request (поле engineer)
        foreign_keys="Request.engineer_id", # Указываем внешний ключ для этой связи
        lazy="selectin"
    )

    # Стандартный метод для представления объекта User в виде строки (удобно для отладки)
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role.value}')>"

# Модель заявки на техподдержку
class Request(Base):
    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True, autoincrement=True) # Первичный ключ заявки
    # Внешний ключ на пользователя-создателя заявки (обязательно)
    requester_id = Column(BigInteger, ForeignKey('users.id'), nullable=False, index=True)
    # Внешний ключ на пользователя-инженера (необязательно, назначается позже)
    engineer_id = Column(BigInteger, ForeignKey('users.id'), nullable=True, index=True)

    full_name = Column(String, nullable=True)     # ФИО заявителя (может отличаться от Telegram)
    building = Column(String, nullable=False)    # Корпус/Здание
    room = Column(String, nullable=False)        # Номер кабинета/аудитории
    description = Column(Text, nullable=False)   # Подробное описание проблемы
    pc_number = Column(String, nullable=True)     # Инвентарный номер ПК (если применимо)
    contact_phone = Column(String, nullable=True) # Контактный телефон для связи

    # Статус заявки (из RequestStatus enum)
    status = Column(SQLEnum(RequestStatus, name="request_status_enum"), default=RequestStatus.WAITING, nullable=False, index=True)
    # Дата и время создания заявки (автоматически устанавливается БД)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Дата и время принятия заявки инженером
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    # Дата и время выполнения заявки
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Дата и время архивации заявки
    archived_at = Column(DateTime(timezone=True), nullable=True)
    # Дата и время последнего обновления записи (автоматически обновляется БД)
    last_updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Связи "многие к одному"
    # Связь с пользователем, создавшим заявку
    requester = relationship(
        "User", back_populates="created_requests", foreign_keys=[requester_id], lazy="selectin"
    )
    # Связь с инженером, назначенным на заявку
    engineer = relationship(
        "User", back_populates="assigned_requests", foreign_keys=[engineer_id], lazy="selectin"
    )

    # Стандартный метод для представления объекта Request в виде строки
    def __repr__(self):
         return f"<Request(id={self.id}, status='{self.status.value}', requester_id={self.requester_id})>"