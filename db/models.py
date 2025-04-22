# db/models.py
from sqlalchemy import (BigInteger, Column, DateTime, ForeignKey, Integer,
                        String, Enum as SQLEnum, Text, func)
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
import datetime

# Импортируем Base из database.py
from .database import Base

class UserRole(PyEnum):
    CLIENT = "client"
    ENGINEER = "engineer"
    ADMIN = "admin"

class RequestStatus(PyEnum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELED = "canceled"

class User(Base):
    __tablename__ = 'users'
    # Telegram User ID, BigInteger т.к. ID могут быть > 2^31
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    # Явно именуем Enum тип для совместимости с некоторыми БД
    role = Column(SQLEnum(UserRole, name="user_role_enum"), default=UserRole.CLIENT, nullable=False)
    phone_number = Column(String, nullable=True) # Будет заполняться позже
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Определяем связи. lazy="selectin" загружает связанные объекты одним доп. запросом
    created_requests = relationship(
        "Request",
        back_populates="requester",
        foreign_keys="Request.requester_id",
        lazy="selectin"
    )
    assigned_requests = relationship(
        "Request",
        back_populates="engineer",
        foreign_keys="Request.engineer_id",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role.value}')>"

class Request(Base):
    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    requester_id = Column(BigInteger, ForeignKey('users.id'), nullable=False, index=True)
    engineer_id = Column(BigInteger, ForeignKey('users.id'), nullable=True, index=True)

    full_name = Column(String, nullable=True)  # ФИО заявителя (может быть предзаполнено)
    building = Column(String, nullable=False) # Корпус
    room = Column(String, nullable=False)     # Кабинет
    description = Column(Text, nullable=False) # Описание проблемы (уже было)
    pc_number = Column(String, nullable=True)  # ПК / Инвентарный номер (необязательно)
    contact_phone = Column(String, nullable=True) # Контактный телефон (уже было)

    status = Column(SQLEnum(RequestStatus, name="request_status_enum"), default=RequestStatus.WAITING, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    last_updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Связи
    requester = relationship(
        "User", back_populates="created_requests", foreign_keys=[requester_id], lazy="selectin"
    )
    engineer = relationship(
        "User", back_populates="assigned_requests", foreign_keys=[engineer_id], lazy="selectin"
    )

    def __repr__(self):
         return f"<Request(id={self.id}, status='{self.status.value}', requester_id={self.requester_id})>"
