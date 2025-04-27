# db/crud.py
import datetime
import logging
from sqlalchemy import select, update, and_, or_
from sqlalchemy.sql import func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession
from .models import RequestStatus, User, UserRole, Request
from sqlalchemy.orm import selectinload

# --- Функции для пользователей (get_user, set_user_role, get_all_users, etc.) ---

async def get_user(session: AsyncSession, user_id: int) -> User | None:
    """Получает пользователя по Telegram ID."""
    result = await session.execute(select(User).filter(User.id == user_id))
    return result.scalar_one_or_none()

async def get_users_by_role(session: AsyncSession, role: UserRole) -> list[User]:
    """Получает список пользователей с указанной ролью."""
    stmt = select(User).where(User.role == role)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def set_user_role(session: AsyncSession, user_id: int, role: UserRole) -> User | None:
    """Устанавливает указанную роль пользователю. Возвращает обновленного пользователя или None."""
    user = await get_user(session, user_id)
    if not user:
        return None
    user.role = role
    try:
        await session.commit()
        await session.refresh(user)
        return user
    except Exception as e:
        logging.error(f"Error setting role {role.value} for user {user_id}: {e}")
        await session.rollback()
        return None

async def get_or_create_user(session: AsyncSession, user_id: int, username: str | None, first_name: str | None, last_name: str | None) -> tuple[User, bool]:
    """
    Получает пользователя по ID или создает нового, если он не найден.
    Возвращает кортеж: (объект User, был ли создан новый пользователь True/False).
    Также обновляет username/first_name/last_name, если они изменились.
    """
    user = await get_user(session, user_id)
    created = False
    if user:
        updated = False
        if user.username != username: user.username = username; updated = True
        if user.first_name != first_name: user.first_name = first_name; updated = True
        if user.last_name != last_name: user.last_name = last_name; updated = True
        if updated:
            try:
                await session.commit()
            except Exception as e:
                 logging.error(f"Error updating user {user_id} data: {e}")
                 await session.rollback()
    else:
        user = User(id=user_id, username=username, first_name=first_name, last_name=last_name, role=UserRole.CLIENT)
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
            created = True
        except Exception as e:
            logging.error(f"Error creating user {user_id}: {e}")
            await session.rollback()
            user = None

    return user, created

async def get_all_users(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
) -> tuple[list[User], int]:
    """
    Получает список ВСЕХ пользователей с пагинацией.
    Возвращает кортеж: (список пользователей, общее количество).
    Сортировка по ID.
    """
    select_stmt = (
        select(User)
        .order_by(User.id.asc())
        .limit(limit)
        .offset(offset)
    )
    count_stmt = select(sql_func.count(User.id))

    users_result = await session.execute(select_stmt)
    users_list = list(users_result.scalars().all())

    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar_one_or_none() or 0

    return users_list, total_count

# --- Функции для заявок ---

async def create_request(
    session: AsyncSession,
    requester_id: int,
    full_name: str | None,
    building: str,
    room: str,
    description: str,
    pc_number: str | None = None,
    contact_phone: str | None = None
) -> Request:
    """Создает новую заявку в БД с детальной информацией."""
    new_request = Request(
        requester_id=requester_id, full_name=full_name, building=building, room=room,
        description=description, pc_number=pc_number, contact_phone=contact_phone,
        status=RequestStatus.WAITING
    )
    session.add(new_request)
    await session.commit()
    await session.refresh(new_request)
    return new_request

async def get_request(session: AsyncSession, request_id: int) -> Request | None:
    """Получает заявку по её ID с загрузкой связанных пользователя и инженера."""
    stmt = (
        select(Request)
        .where(Request.id == request_id)
        .options(
            selectinload(Request.requester),
            selectinload(Request.engineer)
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_new_requests(session: AsyncSession) -> list[Request]:
    """Получает список новых заявок (статус WAITING), отсортированных по дате создания."""
    stmt = (
        select(Request)
        .where(Request.status == RequestStatus.WAITING)
        .order_by(Request.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def accept_request(session: AsyncSession, request_id: int, engineer_id: int) -> Request | None:
    """
    Назначает инженера на заявку и меняет статус на IN_PROGRESS.
    Возвращает обновленную заявку или None, если заявка не найдена или уже принята.
    """
    stmt = (
        update(Request)
        .where(Request.id == request_id)
        .where(Request.status == RequestStatus.WAITING)
        .values(
            engineer_id=engineer_id,
            status=RequestStatus.IN_PROGRESS,
            accepted_at=sql_func.now(),
            last_updated_at=sql_func.now()
        )
        .returning(Request.id)
    )
    result = await session.execute(stmt)
    updated_request_id = result.scalar_one_or_none()

    if updated_request_id:
        await session.commit()
        return await get_request(session, updated_request_id)
    else:
        await session.rollback()
        return None

async def complete_request(session: AsyncSession, request_id: int, engineer_id: int) -> Request | None:
    """
    Меняет статус заявки на ARCHIVED и устанавливает время выполнения и архивации,
    если она IN_PROGRESS и назначена на этого инженера.
    Возвращает обновленную заявку или None, если условия не выполнены.
    """
    stmt = (
        update(Request)
        .where(and_(Request.id == request_id, Request.engineer_id == engineer_id, Request.status == RequestStatus.IN_PROGRESS))
        .values(
            status=RequestStatus.ARCHIVED,
            completed_at=sql_func.now(),
            archived_at=sql_func.now(),
            last_updated_at=sql_func.now()
        ).returning(Request.id)
    )
    result = await session.execute(stmt)
    updated_request_id = result.scalar_one_or_none()

    if updated_request_id:
        await session.commit()
        return await get_request(session, updated_request_id)
    else:
        await session.rollback()
        return None

# --- Пагинация активных заявок (общая для админа) ---
async def get_all_in_progress_requests(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = 'accepted_asc'
) -> tuple[list[Request], int]:
    """
    Получает ВСЕ заявки со статусом IN_PROGRESS с пагинацией и сортировкой.
    Используется админом.
    Возвращает кортеж: (список заявок, общее количество).
    """
    base_query = (
        select(Request)
        .where(Request.status == RequestStatus.IN_PROGRESS)
        .options(selectinload(Request.requester))
        .options(selectinload(Request.engineer)) # Загружаем инженера
    )
    if sort_by == 'created_asc':
        base_query = base_query.order_by(Request.created_at.asc())
    elif sort_by == 'created_desc':
         base_query = base_query.order_by(Request.created_at.desc())
    else: 
        base_query = base_query.order_by(Request.accepted_at.asc())

    # Запрос для количества
    count_stmt = select(sql_func.count(Request.id)).where(Request.status == RequestStatus.IN_PROGRESS)
    total_count_res = await session.execute(count_stmt)
    total_count = total_count_res.scalar_one_or_none() or 0

    # Запрос для данных с пагинацией
    paginated_stmt = base_query.limit(limit).offset(offset)
    requests_res = await session.execute(paginated_stmt)
    requests_list = list(requests_res.scalars().all())

    return requests_list, total_count

# --- Пагинация активных заявок (для инженера) ---
async def get_engineer_requests(
    session: AsyncSession,
    engineer_id: int,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = 'accepted_asc'
) -> tuple[list[Request], int]:
    """
    Получает список заявок со статусом IN_PROGRESS, назначенных на данного инженера,
    с пагинацией и сортировкой.
    Возвращает кортеж: (список заявок на странице, общее количество таких заявок).
    """
    base_where_conditions = [
        Request.engineer_id == engineer_id,
        Request.status == RequestStatus.IN_PROGRESS
    ]

    count_stmt = select(sql_func.count(Request.id)).where(and_(*base_where_conditions))
    total_count_res = await session.execute(count_stmt)
    total_count = total_count_res.scalar_one_or_none() or 0

    select_stmt = (
        select(Request)
        .where(and_(*base_where_conditions))
        .options(selectinload(Request.requester))
    )

    if sort_by == 'created_desc':
         select_stmt = select_stmt.order_by(Request.created_at.desc())
    else: 
        select_stmt = select_stmt.order_by(Request.accepted_at.asc())

    paginated_stmt = select_stmt.limit(limit).offset(offset)
    requests_result = await session.execute(paginated_stmt)
    requests_list = list(requests_result.scalars().all())

    return requests_list, total_count

# --- Пагинация архивных заявок (для админа и инженера) ---
async def get_archived_requests(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = 'date_desc',
    engineer_id: int | None = None # Фильтр по инженеру (None для админа)
) -> tuple[list[Request], int]:
    """
    Получает список архивных заявок (статус ARCHIVED) с пагинацией и сортировкой.
    Если указан engineer_id, фильтрует по нему.
    Возвращает кортеж: (список заявок на странице, общее количество найденных заявок).
    """
    base_where_conditions = [Request.status == RequestStatus.ARCHIVED]
    if engineer_id is not None:
        base_where_conditions.append(Request.engineer_id == engineer_id)

    # Запрос для данных
    select_stmt = (
        select(Request)
        .where(and_(*base_where_conditions))
        .options(selectinload(Request.requester))
        .options(selectinload(Request.engineer))
    )

    # Сортировка
    if sort_by == 'date_asc':
        select_stmt = select_stmt.order_by(Request.archived_at.asc())
    elif sort_by == 'id_asc':
        select_stmt = select_stmt.order_by(Request.id.asc())
    elif sort_by == 'id_desc':
        select_stmt = select_stmt.order_by(Request.id.desc())
    else: # По умолчанию 'date_desc' (сначала самые новые в архиве)
        select_stmt = select_stmt.order_by(Request.archived_at.desc())

    # Запрос для количества
    count_stmt = select(sql_func.count(Request.id)).where(and_(*base_where_conditions))
    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar_one_or_none() or 0

    # Пагинация
    paginated_stmt = select_stmt.limit(limit).offset(offset)
    requests_result = await session.execute(paginated_stmt)
    requests_list = list(requests_result.scalars().all())

    return requests_list, total_count

async def get_client_requests(session: AsyncSession, requester_id: int) -> list[Request]:
    """
    Получает список НЕ архивных и НЕ отмененных заявок для конкретного клиента.
    Сортировка по дате создания (сначала новые).
    """
    stmt = (
        select(Request)
        .where(Request.requester_id == requester_id)
        .where(Request.status.not_in([RequestStatus.ARCHIVED, RequestStatus.CANCELED]))
        .order_by(Request.created_at.desc())
        .options(selectinload(Request.engineer))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())