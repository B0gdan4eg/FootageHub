"""CRUD операции для реферальной системы"""
import secrets
import string
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ReferralReward, ReferralRewardStatus, User


def generate_referral_code(length: int = 8) -> str:
    """
    Генерирует уникальный реферальный код

    Args:
        length: Длина кода

    Returns:
        Реферальный код
    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def create_referral_code(session: AsyncSession, user_id: int) -> str:
    """
    Создаёт реферальный код для пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя

    Returns:
        Реферальный код
    """
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("Пользователь не найден")

    if user.referral_code:
        return user.referral_code

    # Генерируем уникальный код
    while True:
        code = generate_referral_code()
        existing = await session.execute(select(User).where(User.referral_code == code))
        if not existing.scalar_one_or_none():
            break

    user.referral_code = code
    await session.commit()
    await session.refresh(user)

    return code


async def apply_referral_code(
    session: AsyncSession, referred_user_id: int, referral_code: str
) -> bool:
    """
    Применяет реферальный код к новому пользователю

    Args:
        session: Сессия БД
        referred_user_id: ID приглашённого пользователя
        referral_code: Реферальный код

    Returns:
        True если успешно, False если не найден
    """
    # Находим пользователя с таким кодом
    result = await session.execute(select(User).where(User.referral_code == referral_code))
    referrer = result.scalar_one_or_none()

    if not referrer:
        return False

    # Не даём использовать свой код
    if referrer.id == referred_user_id:
        return False

    # Проверяем, что этот пользователь ещё не использовал реферальный код
    existing_reward = await session.execute(
        select(ReferralReward).where(ReferralReward.referred_id == referred_user_id)
    )
    if existing_reward.scalar_one_or_none():
        return False

    # Создаём запись о вознаграждении (пока pending)
    await create_referral_reward(
        session,
        referrer_id=referrer.id,
        referred_id=referred_user_id,
        reward_type="credits",
        reward_value=5,  # Например, 5 кредитов за регистрацию
    )

    return True


async def create_referral_reward(
    session: AsyncSession,
    referrer_id: int,
    referred_id: int,
    reward_type: str,
    reward_value: int = None,
    status: ReferralRewardStatus = ReferralRewardStatus.PENDING,
) -> ReferralReward:
    """
    Создаёт запись о вознаграждении за реферала

    Args:
        session: Сессия БД
        referrer_id: ID пригласившего
        referred_id: ID приглашённого
        reward_type: Тип вознаграждения (credits/subscription/bonus)
        reward_value: Значение вознаграждения
        status: Статус вознаграждения

    Returns:
        Созданная запись
    """
    reward = ReferralReward(
        referrer_id=referrer_id,
        referred_id=referred_id,
        reward_type=reward_type,
        reward_value=reward_value,
        status=status,
    )

    session.add(reward)
    await session.commit()
    await session.refresh(reward)

    return reward


async def complete_referral_reward(session: AsyncSession, reward_id: int) -> ReferralReward:
    """
    Отмечает вознаграждение как выполненное

    Args:
        session: Сессия БД
        reward_id: ID вознаграждения

    Returns:
        Обновлённая запись
    """
    result = await session.execute(select(ReferralReward).where(ReferralReward.id == reward_id))
    reward = result.scalar_one_or_none()

    if reward and reward.status == ReferralRewardStatus.PENDING:
        reward.status = ReferralRewardStatus.COMPLETED
        reward.condition_met = True
        reward.condition_date = datetime.utcnow()
        reward.rewarded_at = datetime.utcnow()

        # Выдаём вознаграждение
        if reward.reward_type == "credits":
            referrer_result = await session.execute(
                select(User).where(User.id == reward.referrer_id)
            )
            referrer = referrer_result.scalar_one_or_none()
            if referrer and reward.reward_value:
                referrer.credits += reward.reward_value

        await session.commit()
        await session.refresh(reward)

    return reward


async def get_referral_stats(session: AsyncSession, user_id: int) -> dict:
    """
    Получает статистику рефералов пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя

    Returns:
        Словарь со статистикой
    """
    # Количество рефералов (уникальные referred_id)
    referrals_count = await session.execute(
        select(func.count(func.distinct(ReferralReward.referred_id))).where(
            ReferralReward.referrer_id == user_id
        )
    )
    total_referrals = referrals_count.scalar_one()

    # Количество завершённых вознаграждений
    completed_rewards = await session.execute(
        select(func.count(ReferralReward.id)).where(
            and_(
                ReferralReward.referrer_id == user_id,
                ReferralReward.status == ReferralRewardStatus.COMPLETED,
            )
        )
    )
    total_completed = completed_rewards.scalar_one()

    # Сумма полученных кредитов
    credits_sum = await session.execute(
        select(func.sum(ReferralReward.reward_value)).where(
            and_(
                ReferralReward.referrer_id == user_id,
                ReferralReward.reward_type == "credits",
                ReferralReward.status == ReferralRewardStatus.COMPLETED,
            )
        )
    )
    total_credits = credits_sum.scalar_one() or 0

    return {
        "total_referrals": total_referrals,
        "completed_rewards": total_completed,
        "total_credits_earned": total_credits,
    }


async def get_user_referrals(session: AsyncSession, user_id: int) -> list[User]:
    """
    Получает список всех рефералов пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя

    Returns:
        Список пользователей-рефералов
    """
    # Получаем ID всех приглашённых через ReferralReward
    rewards = await session.execute(
        select(ReferralReward.referred_id).where(ReferralReward.referrer_id == user_id)
    )
    referred_ids = [r for r in rewards.scalars().all()]

    if not referred_ids:
        return []

    # Получаем пользователей
    result = await session.execute(select(User).where(User.id.in_(referred_ids)))
    return result.scalars().all()


async def get_pending_rewards(session: AsyncSession, user_id: int) -> list[ReferralReward]:
    """
    Получает список ожидающих вознаграждений

    Args:
        session: Сессия БД
        user_id: ID пользователя

    Returns:
        Список ожидающих вознаграждений
    """
    result = await session.execute(
        select(ReferralReward).where(
            and_(
                ReferralReward.referrer_id == user_id,
                ReferralReward.status == ReferralRewardStatus.PENDING,
            )
        )
    )
    return result.scalars().all()
