"""CRUD операции для работы с подписками"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime, timedelta
from db.models import Subscription, SubscriptionType, ServiceType, User


async def create_subscription(
    session: AsyncSession,
    user_id: int,
    subscription_type: SubscriptionType,
    service_type: ServiceType = ServiceType.ALL,
    total_limit: int = None,
    daily_limit: int = None,
    days: int = 30,
    payment_id: int = None
) -> Subscription:
    """
    Создаёт новую подписку для пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя
        subscription_type: Тип подписки
        service_type: Тип сервиса
        total_limit: Общий лимит скачиваний
        daily_limit: Дневной лимит
        days: Длительность подписки в днях
        payment_id: ID платежа (опционально)
    """
    subscription = Subscription(
        user_id=user_id,
        subscription_type=subscription_type,
        service_type=service_type,
        total_limit=total_limit,
        daily_limit=daily_limit,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=days),
        payment_id=payment_id,
        is_active=True
    )

    session.add(subscription)

    # Начисляем кредиты пользователю при создании подписки с total_limit
    if total_limit:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.credits += total_limit
            print(f"[SUBSCRIPTION] Начислено {total_limit} кредитов пользователю {user_id}")

    await session.commit()
    await session.refresh(subscription)
    return subscription


async def get_active_subscription(
    session: AsyncSession,
    user_id: int,
    service_type: ServiceType = None
) -> Subscription | None:
    """
    Получает активную подписку пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя
        service_type: Фильтр по типу сервиса (опционально)

    Returns:
        Активная подписка или None
    """
    query = select(Subscription).where(
        and_(
            Subscription.user_id == user_id,
            Subscription.is_active == True,
            Subscription.end_date > datetime.utcnow()
        )
    )

    if service_type:
        query = query.where(
            or_(
                Subscription.service_type == service_type,
                Subscription.service_type == ServiceType.ALL
            )
        )

    result = await session.execute(query)
    return result.scalar_one_or_none()


async def check_download_limit(
    session: AsyncSession,
    subscription: Subscription
) -> tuple[bool, str]:
    """
    Проверяет, доступно ли скачивание по подписке

    Args:
        session: Сессия БД
        subscription: Объект подписки

    Returns:
        Tuple (можно_скачать, сообщение_об_ошибке)
    """
    # Проверка срока действия
    if subscription.end_date < datetime.utcnow():
        return False, "Подписка истекла"

    # Проверка общего лимита
    if subscription.total_limit and subscription.used_total >= subscription.total_limit:
        return False, "Достигнут общий лимит скачиваний"

    # Сброс дневного счётчика если новый день
    today = datetime.utcnow().date()
    if subscription.last_reset_date < today:
        subscription.used_today = 0
        subscription.last_reset_date = today
        await session.commit()

    # Проверка дневного лимита
    if subscription.daily_limit and subscription.used_today >= subscription.daily_limit:
        return False, "Достигнут дневной лимит скачиваний"

    return True, ""


async def increment_download_count(
    session: AsyncSession,
    subscription_id: int
):
    """
    Увеличивает счётчик скачиваний для подписки

    Args:
        session: Сессия БД
        subscription_id: ID подписки
    """
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.used_total += 1
        subscription.used_today += 1
        subscription.updated_at = datetime.utcnow()
        await session.commit()


async def deactivate_subscription(
    session: AsyncSession,
    subscription_id: int
):
    """
    Деактивирует подписку

    Args:
        session: Сессия БД
        subscription_id: ID подписки
    """
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.is_active = False
        subscription.updated_at = datetime.utcnow()
        await session.commit()


async def get_user_subscriptions(
    session: AsyncSession,
    user_id: int,
    include_expired: bool = False
) -> list[Subscription]:
    """
    Получает все подписки пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя
        include_expired: Включить истекшие подписки

    Returns:
        Список подписок
    """
    query = select(Subscription).where(Subscription.user_id == user_id)

    if not include_expired:
        query = query.where(
            and_(
                Subscription.is_active == True,
                Subscription.end_date > datetime.utcnow()
            )
        )

    result = await session.execute(query)
    return result.scalars().all()


async def extend_subscription(
    session: AsyncSession,
    subscription_id: int,
    days: int
) -> Subscription:
    """
    Продлевает подписку на указанное количество дней

    Args:
        session: Сессия БД
        subscription_id: ID подписки
        days: Количество дней для продления

    Returns:
        Обновлённая подписка
    """
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.end_date = subscription.end_date + timedelta(days=days)
        subscription.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(subscription)

    return subscription