from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, Media, Download
from datetime import datetime, timedelta
from sqlalchemy import update, func

async def get_user_by_telegram_id(session: AsyncSession, tg_id: int):
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalars().first()

async def create_user(session: AsyncSession, tg_id: int):
    user = User(
        tg_id=tg_id,
        credits=1
        )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def update_user_subscription(session, user_id: int, months: int = 1):
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            is_subscribed=True,
            subscription_until=datetime.utcnow() + timedelta(days=30 * months)
        )
    )
    await session.commit()

# Начисление кредитов
async def add_user_credits(session, user_id: int, credits: int):
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            credits=User.credits + credits
        )
    )
    await session.commit()

async def get_all_users(session: AsyncSession):
    result = await session.execute(select(User))
    return result.scalars().all()


async def count_active_subs(session: AsyncSession):
    result = await session.execute(
        select(func.count()).select_from(User).where(
            User.is_subscribed == True,
            User.subscription_until != None,
            User.subscription_until > func.now()
        )
    )
    return result.scalar()

async def grant_access(user_id: int, type_: str, value: int, session: AsyncSession):
    result = await session.execute(select(User).where(User.tg_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError(f"Пользователь с id {user_id} не найден")

    now = datetime.utcnow()

    if type_ == "subscription":
        if user.subscription_until and user.subscription_until > now:
            user.subscription_until += timedelta(days=value)
        else:
            user.subscription_until = now + timedelta(days=value)
        user.is_subscribed = True

    elif type_ == "credits":
        user.credits += value

    else:
        raise ValueError("Тип должен быть 'subscription' или 'credits'")

    await session.commit()

async def has_user_downloaded(session: AsyncSession, user_id: int, url: str) -> bool:
    """
    Проверяет, скачивал ли пользователь файл по данному URL за последние 24 часа.
    """
    # Получаем id медиа по url
    media_id = await session.scalar(
        select(Media.id).where(Media.url == url)
    )

    if media_id is None:
        return False  # Файла с таким URL нет в базе

    # Граница времени (только последние 24 часа)
    time_limit = datetime.utcnow() - timedelta(hours=24)

    # Проверяем наличие скачивания в последние 24 часа
    download_id = await session.scalar(
        select(Download.id).where(
            Download.user_id == user_id,
            Download.media_id == media_id,
            Download.created_at >= time_limit
        )
    )

    return download_id is not None

async def add_daily_credits(session: AsyncSession, bot):
    now = datetime.utcnow()

    # 1. Отключаем просроченные подписки
    expired_result = await session.execute(
        select(User).where(
            User.is_subscribed == True,
            User.subscription_until != None,
            User.subscription_until <= now
        )
    )
    expired_users = expired_result.scalars().all()
    for user in expired_users:
        user.is_subscribed = False

    # 2. Начисляем кредиты активным подписчикам
    active_result = await session.execute(
        select(User).where(
            User.is_subscribed == True,
            User.subscription_until != None,
            User.subscription_until > now
        )
    )
    active_users = active_result.scalars().all()
    for user in active_users:
        user.credits += 30

    await session.commit()
    
async def set_user_referrer(session: AsyncSession, new_user_tg_id: int, referral_code: str) -> bool:
    """
    Устанавливает для пользователя с tg_id new_user_tg_id реферала по referral_code.
    Возвращает True, если реферал успешно установлен, False — если не найден реферал или пользователь.

    :param session: асинхронная сессия SQLAlchemy
    :param new_user_tg_id: telegram id нового пользователя
    :param referral_code: код реферала
    """
    result = await session.execute(
        select(User).where(User.referral_code == referral_code)
    )
    referrer = result.scalar_one_or_none()

    if not referrer:
        return False

    result = await session.execute(
        select(User).where(User.tg_id == new_user_tg_id)
    )
    new_user = result.scalar_one_or_none()

    if not new_user:
        return False

    new_user.referred_by_id = referrer.id
    await session.commit()
    return True