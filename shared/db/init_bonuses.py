"""
Инициализация базовых типов бонусов в базе данных.

Создает или обновляет все необходимые бонусы при старте приложения.
"""

from typing import Any

from shared.core.constants import BonusCodes, ChannelConfig, ReferralRewards
from shared.core.logger import get_logger
from shared.db.models import BonusRewardType, BonusType
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.session import get_session

logger = get_logger(__name__)


# Конфигурация всех бонусов в системе
BONUS_CONFIGURATIONS = [
    # Бонус за регистрацию
    {
        "code": BonusCodes.REGISTRATION,
        "name": "Бонус за регистрацию",
        "description": "Стартовые скачивания для нового пользователя",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": 3,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": False,
        "cooldown_days": None,
        "conditions": None,
    },
    # Бонус за подписку на канал
    {
        "code": BonusCodes.CHANNEL_SUBSCRIPTION,
        "name": "Бонус за подписку на канал",
        "description": "Награда за подписку на официальный канал",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ChannelConfig.BONUS_CREDITS,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": False,
        "cooldown_days": None,
        "conditions": None,
    },
    # Реферальные бонусы
    {
        "code": BonusCodes.REFERRAL_REGISTRATION,
        "name": "Бонус за приглашение пользователя",
        "description": "Награда когда приглашенный пользователь подписывается на канал",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ReferralRewards.REGISTRATION_CREDITS,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": True,
        "cooldown_days": None,
        "conditions": None,
    },
    {
        "code": BonusCodes.REFERRAL_FIRST_PAYMENT,
        "name": "Бонус за первую покупку реферала",
        "description": "Награда когда приглашенный пользователь совершает первую покупку",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ReferralRewards.FIRST_PAYMENT_CREDITS,
        "ai_credits_amount": ReferralRewards.FIRST_PAYMENT_AI_CREDITS,
        "is_active": True,
        "is_repeatable": True,
        "cooldown_days": None,
        "conditions": None,
    },
    # Milestone бонусы
    {
        "code": BonusCodes.REFERRAL_MILESTONE_5,
        "name": "Майлстоун: 5 рефералов",
        "description": "Награда за привлечение 5 рефералов",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ReferralRewards.MILESTONE_5_CREDITS,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": False,
        "cooldown_days": None,
        "conditions": {"milestone_count": 5},
    },
    {
        "code": BonusCodes.REFERRAL_MILESTONE_10,
        "name": "Майлстоун: 10 рефералов",
        "description": "Награда за привлечение 10 рефералов",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ReferralRewards.MILESTONE_10_CREDITS,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": False,
        "cooldown_days": None,
        "conditions": {"milestone_count": 10},
    },
    {
        "code": BonusCodes.REFERRAL_MILESTONE_25,
        "name": "Майлстоун: 25 рефералов",
        "description": "Награда за привлечение 25 рефералов",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ReferralRewards.MILESTONE_25_CREDITS,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": False,
        "cooldown_days": None,
        "conditions": {"milestone_count": 25},
    },
    {
        "code": BonusCodes.REFERRAL_MILESTONE_50,
        "name": "Майлстоун: 50 рефералов",
        "description": "Награда за привлечение 50 рефералов",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ReferralRewards.MILESTONE_50_CREDITS,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": False,
        "cooldown_days": None,
        "conditions": {"milestone_count": 50},
    },
    {
        "code": BonusCodes.REFERRAL_MILESTONE_100,
        "name": "Майлстоун: 100 рефералов",
        "description": "Награда за привлечение 100 рефералов",
        "reward_type": BonusRewardType.CREDITS,
        "credits_amount": ReferralRewards.MILESTONE_100_CREDITS,
        "ai_credits_amount": 0,
        "is_active": True,
        "is_repeatable": False,
        "cooldown_days": None,
        "conditions": {"milestone_count": 100},
    },
]


async def initialize_bonuses() -> dict[str, int]:
    """
    Инициализировать все базовые типы бонусов в базе данных.

    Создает новые бонусы или обновляет существующие.

    Returns:
        Словарь с количеством созданных и обновленных бонусов
    """
    created_count = 0
    updated_count = 0

    async for session in get_session():
        bonus_repo = BonusRepository(session)

        for config in BONUS_CONFIGURATIONS:
            try:
                # Проверяем существование бонуса
                existing_bonus = await bonus_repo.get_by_code(config["code"])

                if existing_bonus:
                    # Обновляем существующий бонус
                    existing_bonus.name = config["name"]
                    existing_bonus.description = config["description"]
                    existing_bonus.reward_type = config["reward_type"]
                    existing_bonus.credits_amount = config["credits_amount"]
                    existing_bonus.ai_credits_amount = config["ai_credits_amount"]
                    existing_bonus.is_active = config["is_active"]
                    existing_bonus.is_repeatable = config["is_repeatable"]
                    existing_bonus.cooldown_days = config["cooldown_days"]
                    existing_bonus.conditions = config["conditions"]

                    await session.commit()
                    updated_count += 1
                    logger.info(f"✅ Updated bonus: {config['code']}")
                else:
                    # Создаем новый бонус
                    new_bonus = BonusType(**config)
                    session.add(new_bonus)
                    await session.commit()
                    created_count += 1
                    logger.info(f"✨ Created bonus: {config['code']}")

            except Exception as e:
                logger.error(f"❌ Failed to initialize bonus {config['code']}: {e}")
                await session.rollback()
                continue

    logger.info(
        f"🎁 Bonus initialization complete: {created_count} created, {updated_count} updated"
    )
    return {"created": created_count, "updated": updated_count}


async def get_bonus_stats() -> dict[str, Any]:
    """
    Получить статистику по всем бонусам в системе.

    Returns:
        Словарь со статистикой
    """
    async for session in get_session():
        bonus_repo = BonusRepository(session)

        all_bonuses = []
        for config in BONUS_CONFIGURATIONS:
            bonus = await bonus_repo.get_by_code(config["code"])
            if bonus:
                all_bonuses.append(
                    {
                        "code": bonus.code,
                        "name": bonus.name,
                        "credits": bonus.credits_amount,
                        "ai_credits": bonus.ai_credits_amount,
                        "is_active": bonus.is_active,
                    }
                )

        return {
            "total_bonuses": len(all_bonuses),
            "active_bonuses": sum(1 for b in all_bonuses if b["is_active"]),
            "bonuses": all_bonuses,
        }
