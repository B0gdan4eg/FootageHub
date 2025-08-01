from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User
from datetime import datetime, timedelta
from sqlalchemy import update, func

async def get_user_by_telegram_id(session: AsyncSession, tg_id: int):
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalars().first()

async def create_user(session: AsyncSession, tg_id: int):
    user = User(
        tg_id=tg_id,
        credits=0
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
    result = await session.execute(select(User).where(User.id == user_id))
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