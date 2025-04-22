# db/crud.py
import datetime
import logging
from sqlalchemy import select, update, and_, func as sql_func, or_ # Добавляем update
from sqlalchemy.ext.asyncio import AsyncSession
from .models import RequestStatus, User, UserRole, Request # Импортируем все модели
from sqlalchemy.orm import selectinload # Для загрузки связей
from sqlalchemy.sql import func # Для func.now()


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
    # Сначала получаем пользователя, чтобы убедиться, что он существует
    user = await get_user(session, user_id)
    if not user:
        return None # Пользователь не найден

    # Обновляем роль
    user.role = role
    try:
        await session.commit()
        await session.refresh(user)
        return user
    except Exception as e:
        logging.error(f"Error setting role {role.value} for user {user_id}: {e}")
        await session.rollback()
        return None

async def get_all_in_progress_requests(
    session: AsyncSession,
    limit: int = 10, # Можно сделать поменьше, чем в истории
    offset: int = 0,
    sort_by: str = 'accepted_asc' # Сортируем по дате принятия (старые сверху)
) -> tuple[list[Request], int]:
    """
    Получает ВСЕ заявки со статусом IN_PROGRESS с пагинацией и сортировкой.
    Возвращает кортеж: (список заявок, общее количество).
    """
    base_query = (
        select(Request)
        .where(Request.status == RequestStatus.IN_PROGRESS)
        .options(selectinload(Request.requester))
        .options(selectinload(Request.engineer))
    )

    # Сортировка
    if sort_by == 'created_asc':
        base_query = base_query.order_by(Request.created_at.asc())
    elif sort_by == 'created_desc':
         base_query = base_query.order_by(Request.created_at.desc())
    else: # accepted_asc по умолчанию
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


async def get_or_create_user(session: AsyncSession, user_id: int, username: str | None, first_name: str | None, last_name: str | None) -> tuple[User, bool]:
    """
    Получает пользователя по ID или создает нового, если он не найден.
    Возвращает кортеж: (объект User, был ли создан новый пользователь True/False).
    Также обновляет username/first_name/last_name, если они изменились.
    """
    user = await get_user(session, user_id)
    created = False
    if user:
        # Проверяем и обновляем данные, если нужно
        updated = False
        if user.username != username:
            user.username = username
            updated = True
        if user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if user.last_name != last_name:
            user.last_name = last_name
            updated = True
        if updated:
            await session.commit()
    else:
        # Создаем нового пользователя
        print(f"Creating new user: id={user_id}, username={username}") # Лог для отладки
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.CLIENT # По умолчанию - клиент
        )
        session.add(user)
        await session.commit()
        await session.refresh(user) # Загружаем данные из БД (включая defaults)
        created = True
        print(f"User created: {user}") # Лог для отладки

    return user, created


async def create_request(
    session: AsyncSession,
    requester_id: int,
    full_name: str | None, # <-- Новое поле
    building: str,         # <-- Новое поле
    room: str,             # <-- Новое поле
    description: str,
    pc_number: str | None = None, # <-- Новое поле
    contact_phone: str | None = None
    # location: str | None = None # <-- Убрали старое поле
) -> Request:
    """Создает новую заявку в БД с детальной информацией."""
    new_request = Request(
        requester_id=requester_id,
        full_name=full_name,      # <-- Сохраняем
        building=building,        # <-- Сохраняем
        room=room,                # <-- Сохраняем
        description=description,
        pc_number=pc_number,      # <-- Сохраняем
        contact_phone=contact_phone,
        status=RequestStatus.WAITING
    )
    session.add(new_request)
    await session.commit()
    await session.refresh(new_request)
    return new_request

async def get_new_requests(session: AsyncSession) -> list[Request]:
    """Получает список новых заявок (статус WAITING), отсортированных по дате создания."""
    stmt = (
        select(Request)
        .where(Request.status == RequestStatus.WAITING)
        .order_by(Request.created_at.asc()) # Сначала самые старые
        # Можно добавить .limit(10) для пагинации в будущем
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()) # Возвращаем список объектов Request

async def get_request(session: AsyncSession, request_id: int) -> Request | None:
    """Получает заявку по её ID, подгружая информацию о заявителе."""
    stmt = (
        select(Request)
        .where(Request.id == request_id)
        .options(selectinload(Request.requester)) # Загружаем связанного пользователя (заявителя)
        .options(selectinload(Request.engineer)) # Также загружаем инженера, если он назначен
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def accept_request(session: AsyncSession, request_id: int, engineer_id: int) -> Request | None:
    """
    Назначает инженера на заявку и меняет статус на IN_PROGRESS.
    Возвращает обновленную заявку или None, если заявка не найдена или уже принята.
    """
    # Используем update для атомарности (хотя можно и через get + save)
    stmt = (
        update(Request)
        .where(Request.id == request_id)
        .where(Request.status == RequestStatus.WAITING) # Важно: проверяем, что она еще не принята
        .values(
            engineer_id=engineer_id,
            status=RequestStatus.IN_PROGRESS,
            accepted_at=func.now(), # Используем SQL функцию для времени БД
            last_updated_at=func.now()
        )
        .returning(Request) # Возвращаем обновленные данные
    )
    result = await session.execute(stmt)
    updated_request = result.scalar_one_or_none()

    if updated_request:
        await session.commit()
        # Нужно перезагрузить объект с отношениями после returning
        # (или можно было сделать get_request после commit)
        return await get_request(session, request_id)
    else:
        # Если ничего не обновилось (заявка не найдена или уже не WAITING)
        await session.rollback() # Откатываем транзакцию на всякий случай
        return None
    
async def get_engineer_requests(session: AsyncSession, engineer_id: int) -> list[Request]:
    """
    Получает список заявок со статусом IN_PROGRESS, назначенных на данного инженера.
    Сортировка по дате принятия в работу.
    """
    stmt = (
        select(Request)
        .where(
            and_( # Используем and_ для нескольких условий WHERE
                Request.engineer_id == engineer_id,
                Request.status == RequestStatus.IN_PROGRESS
            )
        )
        .order_by(Request.accepted_at.asc()) # Сначала те, что дольше в работе
        .options(selectinload(Request.requester)) # Подгружаем заявителя
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

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
            completed_at=sql_func.now(), # Используем sql_func
            archived_at=sql_func.now(),  # Используем sql_func
            last_updated_at=sql_func.now() # Используем sql_func
        ).returning(Request)
    )
    result = await session.execute(stmt)
    updated_request = result.scalar_one_or_none()

    if updated_request:
        await session.commit()
        # Возвращаем обновленную заявку (можно снова сделать get_request для подгрузки связей)
        return await get_request(session, request_id)
    else:
        await session.rollback() # Откатываем, если ничего не обновилось
        return None


async def get_archived_requests(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = 'date_desc',
    engineer_id: int | None = None # <-- Добавлен необязательный параметр
) -> tuple[list[Request], int]:
    """
    Получает список архивных заявок (статус ARCHIVED) с пагинацией и сортировкой.
    Если указан engineer_id, фильтрует по нему.
    Возвращает кортеж: (список заявок на странице, общее количество найденных заявок).
    """
    # --- Базовые условия WHERE ---
    base_where_conditions = [Request.status == RequestStatus.ARCHIVED]
    if engineer_id is not None:
        base_where_conditions.append(Request.engineer_id == engineer_id)
    # ---------------------------

    # Запрос для выборки заявок
    select_stmt = (
        select(Request)
        .where(and_(*base_where_conditions)) # Применяем условия
        .options(selectinload(Request.requester))
        .options(selectinload(Request.engineer))
    )

    # Применяем сортировку
    if sort_by == 'date_asc':
        select_stmt = select_stmt.order_by(Request.archived_at.asc())
    elif sort_by == 'id_asc':
        select_stmt = select_stmt.order_by(Request.id.asc())
    elif sort_by == 'id_desc':
        select_stmt = select_stmt.order_by(Request.id.desc())
    else: # По умолчанию 'date_desc'
        select_stmt = select_stmt.order_by(Request.archived_at.desc())

    # Запрос для получения общего количества (с теми же фильтрами!)
    count_stmt = select(sql_func.count(Request.id)).where(and_(*base_where_conditions))

    # Выполняем запрос на количество
    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar_one_or_none() or 0

    # Добавляем пагинацию к основному запросу
    paginated_stmt = select_stmt.limit(limit).offset(offset)

    # Выполняем основной запрос
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
        # Исключаем архивные и отмененные, показываем только активные или ожидающие
        .where(Request.status.not_in([RequestStatus.ARCHIVED, RequestStatus.CANCELED]))
        .order_by(Request.created_at.desc()) # Сначала новые
        .options(selectinload(Request.engineer)) # Подгрузим инженера, если назначен
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_users(
    session: AsyncSession,
    limit: int = 10,
    offset: int = 0,
    # Можно добавить фильтры по имени/роли в будущем
) -> tuple[list[User], int]:
    """
    Получает список ВСЕХ пользователей с пагинацией.
    Возвращает кортеж: (список пользователей, общее количество).
    Сортировка по ID.
    """
    # Запрос для данных
    select_stmt = (
        select(User)
        .order_by(User.id.asc()) # Сортируем по ID
        .limit(limit)
        .offset(offset)
    )
    # Запрос для общего количества
    count_stmt = select(sql_func.count(User.id))

    # Выполнение запросов
    users_result = await session.execute(select_stmt)
    users_list = list(users_result.scalars().all())

    total_count_result = await session.execute(count_stmt)
    total_count = total_count_result.scalar_one_or_none() or 0

    return users_list, total_count