# bot/filters/role.py
from typing import Union, List 
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud import get_user 
from db.models import UserRole 


class RoleFilter(BaseFilter):
    """
    Фильтр для проверки роли пользователя.
    """
    # Указываем, какие роли разрешены
    def __init__(self, allowed_roles: Union[UserRole, List[UserRole]]):
        if not isinstance(allowed_roles, list):
            allowed_roles = [allowed_roles]
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        event: Union[Message, CallbackQuery], 
        session: AsyncSession 
    ) -> bool:
        """
        Проверяет, есть ли у пользователя одна из разрешенных ролей.
        """
        user = event.from_user
        if not user:
            return False 

        # Получаем пользователя из БД
        db_user = await get_user(session, user.id)

        if not db_user:
            return False

        # Проверяем, входит ли роль пользователя в список разрешенных
        return db_user.role in self.allowed_roles