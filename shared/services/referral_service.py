"""
Referral Service - улучшенная реферальная система.

Управляет реферальными наградами, триггерами и интеграцией с бонусной системой.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.constants import BonusCodes, ReferralRewards
from shared.core.exceptions import BonusException, ReferralException, UserNotFoundException
from shared.db.models import ReferralReward, ReferralRewardStatus, ReferralTriggerType, UserBonus
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.user_repository import UserRepository
from shared.services.bonus_service import BonusService


class ReferralService:
    """
    Сервис управления реферальной системой.

    Основные возможности:
    - Создание реферальных связей
    - Обработка триггеров наград (регистрация, первая покупка, подписка)
    - Интеграция с бонусной системой
    - Отслеживание milestone наград
    """

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        bonus_repo: BonusRepository,
        bonus_service: BonusService,
    ):
        self.session = session
        self._user_repo = user_repo
        self._bonus_repo = bonus_repo
        self._bonus_service = bonus_service

    # ==================== СОЗДАНИЕ РЕФЕРАЛЬНЫХ СВЯЗЕЙ ====================

    async def create_referral_registration(
        self, referrer_id: int, referred_id: int
    ) -> tuple[ReferralReward, Optional[UserBonus]]:
        """
        Создать реферальную награду за регистрацию.

        Args:
            referrer_id: ID пригласившего пользователя
            referred_id: ID приглашенного пользователя

        Returns:
            Созданная реферальная награда

        Raises:
            UserNotFoundException: Если пользователь не найден
            ReferralException: Если реферальная связь уже существует
        """
        # Проверка пользователей
        referrer = await self._user_repo.get_by_id(referrer_id)
        referred = await self._user_repo.get_by_id(referred_id)

        if not referrer:
            raise UserNotFoundException(f"Referrer {referrer_id} not found")
        if not referred:
            raise UserNotFoundException(f"Referred {referred_id} not found")

        # Проверка на дубликат
        existing = await self._get_referral_by_users(referrer_id, referred_id)
        if existing:
            raise ReferralException("Referral reward already exists")

        # Создание реферальной награды
        referral_reward = ReferralReward(
            referrer_id=referrer_id,
            referred_id=referred_id,
            reward_type="credits",
            reward_value=ReferralRewards.REGISTRATION_CREDITS,
            status=ReferralRewardStatus.PENDING,
            trigger_type=ReferralTriggerType.REGISTRATION,
            trigger_metadata={"registered_at": datetime.utcnow().isoformat()},
            condition_met=True,
            condition_date=datetime.utcnow(),
        )

        self.session.add(referral_reward)
        await self.session.flush()
        await self.session.refresh(referral_reward)

        # Начисляем бонус сразу при регистрации
        try:
            user_bonus = await self._bonus_service.claim_bonus(
                user_id=referrer_id,
                bonus_code=BonusCodes.REFERRAL_REGISTRATION,
                metadata={
                    "trigger": "REGISTRATION",
                    "referral_reward_id": referral_reward.id,
                    "referred_id": referred_id,
                },
            )

            # Обновляем статус реферальной награды
            referral_reward.bonus_id = user_bonus.id
            referral_reward.status = ReferralRewardStatus.COMPLETED
            referral_reward.rewarded_at = datetime.utcnow()
            referral_reward.completed_at = datetime.utcnow()
            await self.session.flush()

        except BonusException as e:
            # Если не удалось начислить бонус, оставляем награду в статусе PENDING
            print(f"Failed to apply referral registration bonus: {e}")
            return referral_reward, None

        return referral_reward, user_bonus

    async def _apply_registration_bonus(
        self, referrer_id: int, referral_reward_id: int
    ) -> Optional[UserBonus]:
        """
        Применить бонус за регистрацию реферала.

        Args:
            referrer_id: ID пригласившего
            referral_reward_id: ID реферальной награды

        Returns:
            Созданный UserBonus или None
        """
        try:
            user_bonus = await self._bonus_service.claim_bonus(
                user_id=referrer_id,
                bonus_code=BonusCodes.REFERRAL_REGISTRATION,
                metadata={"referral_reward_id": referral_reward_id},
            )

            # Обновляем реферальную награду
            referral_reward = await self._get_referral_by_id(referral_reward_id)
            if referral_reward:
                referral_reward.bonus_id = user_bonus.id
                referral_reward.status = ReferralRewardStatus.COMPLETED
                referral_reward.rewarded_at = datetime.utcnow()
                referral_reward.completed_at = datetime.utcnow()
                await self.session.flush()

            return user_bonus

        except BonusException:
            # Бонус уже получен или условия не выполнены
            return None

    # ==================== ТРИГГЕРЫ НАГРАД ====================

    async def trigger_first_payment(
        self, user_id: int, payment_amount: float, payment_id: int
    ) -> Optional[UserBonus]:
        """
        Триггер первой покупки реферала.

        Начисляет бонус пользователю, который пригласил этого реферала.

        Args:
            user_id: ID пользователя, совершившего покупку
            payment_amount: Сумма покупки
            payment_id: ID платежа

        Returns:
            Созданный UserBonus для реферера или None
        """
        # Найти реферальную связь где user_id = referred_id
        referral_reward = await self._get_referral_for_referred(user_id)
        if not referral_reward:
            return None

        # Проверить, не был ли уже начислен бонус за первую покупку этого реферала
        # Любой платеж считается, но бонус выдается только один раз
        existing_first_payment_bonus = await self._get_first_payment_bonus(
            referral_reward.referrer_id, user_id
        )
        if existing_first_payment_bonus:
            return None  # Бонус уже был начислен

        # Создать триггер первой покупки
        first_payment_reward = ReferralReward(
            referrer_id=referral_reward.referrer_id,
            referred_id=user_id,
            reward_type="credits_and_ai",
            reward_value=ReferralRewards.FIRST_PAYMENT_CREDITS,
            status=ReferralRewardStatus.PENDING,
            trigger_type=ReferralTriggerType.FIRST_PAYMENT,
            trigger_metadata={
                "payment_id": payment_id,
                "amount": payment_amount,
                "payment_date": datetime.utcnow().isoformat(),
            },
            condition_met=True,
            condition_date=datetime.utcnow(),
        )

        self.session.add(first_payment_reward)
        await self.session.flush()
        await self.session.refresh(first_payment_reward)

        # Начислить бонус
        try:
            user_bonus = await self._bonus_service.claim_bonus(
                user_id=referral_reward.referrer_id,
                bonus_code=BonusCodes.REFERRAL_FIRST_PAYMENT,
                metadata={
                    "referral_reward_id": first_payment_reward.id,
                    "referred_user_id": user_id,
                    "payment_amount": payment_amount,
                },
            )

            # Обновить статус
            first_payment_reward.bonus_id = user_bonus.id
            first_payment_reward.status = ReferralRewardStatus.COMPLETED
            first_payment_reward.rewarded_at = datetime.utcnow()
            first_payment_reward.completed_at = datetime.utcnow()
            await self.session.flush()

            # Проверяем майлстоуны
            milestone_bonuses = await self.check_milestone_rewards(referral_reward.referrer_id)
            if milestone_bonuses:
                print(
                    f"Начислено {len(milestone_bonuses)} майлстоун-бонусов пользователю {referral_reward.referrer_id}"
                )

            return user_bonus

        except BonusException as e:
            print(f"Failed to apply first payment bonus: {e}")
            return None

    async def trigger_subscription(
        self, user_id: int, subscription_id: int, subscription_type: str
    ) -> Optional[UserBonus]:
        """
        Триггер покупки подписки рефералом.

        Args:
            user_id: ID пользователя, купившего подписку
            subscription_id: ID подписки
            subscription_type: Тип подписки

        Returns:
            Созданный UserBonus для реферера или None
        """
        # Найти реферальную связь
        referral_reward = await self._get_referral_for_referred(user_id)
        if not referral_reward:
            return None

        # Создать триггер подписки
        subscription_reward = ReferralReward(
            referrer_id=referral_reward.referrer_id,
            referred_id=user_id,
            reward_type="subscription_bonus",
            reward_value=0,
            status=ReferralRewardStatus.PENDING,
            trigger_type=ReferralTriggerType.SUBSCRIPTION,
            trigger_metadata={
                "subscription_id": subscription_id,
                "subscription_type": subscription_type,
                "subscription_date": datetime.utcnow().isoformat(),
            },
            condition_met=True,
            condition_date=datetime.utcnow(),
        )

        self.session.add(subscription_reward)
        await self.session.flush()
        await self.session.refresh(subscription_reward)

        # Можно добавить специальный бонус за покупку подписки
        # Пока просто логируем

        subscription_reward.status = ReferralRewardStatus.COMPLETED
        subscription_reward.completed_at = datetime.utcnow()
        await self.session.flush()

        return None

    async def trigger_referred_channel_subscription(
        self, referred_user_id: int
    ) -> Optional[UserBonus]:
        """
        Триггер подписки реферала на канал.

        ВНИМАНИЕ: Бонус за регистрацию теперь начисляется сразу при регистрации.
        Этот метод больше не начисляет бонус, только проверяет майлстоуны.

        Args:
            referred_user_id: ID реферала (приглашенного пользователя)

        Returns:
            None (бонус уже начислен при регистрации)
        """
        # Найти реферальную связь где referred_user_id = referred_id
        referral_reward = await self._get_referral_for_referred(referred_user_id)
        if not referral_reward:
            return None

        # Бонус уже должен быть начислен при регистрации
        # Проверяем только майлстоуны
        if referral_reward.status == ReferralRewardStatus.COMPLETED:
            try:
                milestone_bonuses = await self.check_milestone_rewards(referral_reward.referrer_id)
                if milestone_bonuses:
                    print(
                        f"Начислено {len(milestone_bonuses)} майлстоун-бонусов пользователю {referral_reward.referrer_id}"
                    )
            except Exception as e:
                print(f"Failed to check milestone rewards: {e}")

        return None

    async def check_milestone_rewards(self, referrer_id: int) -> List[UserBonus]:
        """
        Проверить и начислить milestone награды.

        Milestone награды начисляются за достижение определенного количества рефералов.
        Например: 5, 10, 25, 50, 100 рефералов.

        Args:
            referrer_id: ID пригласившего пользователя

        Returns:
            Список начисленных бонусов
        """
        bonuses = []

        # Получить текущее количество рефералов
        referral_count = await self._user_repo.get_referral_count(referrer_id)

        # Определить майлстоуны
        milestones = {
            5: BonusCodes.REFERRAL_MILESTONE_5,
            10: BonusCodes.REFERRAL_MILESTONE_10,
            25: BonusCodes.REFERRAL_MILESTONE_25,
            50: BonusCodes.REFERRAL_MILESTONE_50,
            100: BonusCodes.REFERRAL_MILESTONE_100,
        }

        # Проверить каждый майлстоун
        for threshold, bonus_code in milestones.items():
            if referral_count >= threshold:
                try:
                    can_claim = await self._bonus_service.can_claim_bonus(
                        user_id=referrer_id,
                        bonus_code=bonus_code,
                        metadata={
                            "milestone": threshold,
                            "referral_count": referral_count,
                            "achieved_at": datetime.utcnow().isoformat(),
                        },
                    )

                    if can_claim:
                        user_bonus = await self._bonus_service.claim_bonus(
                            user_id=referrer_id,
                            bonus_code=bonus_code,
                            metadata={
                                "milestone": threshold,
                                "referral_count": referral_count,
                                "achieved_at": datetime.utcnow().isoformat(),
                            },
                        )
                        bonuses.append(user_bonus)

                except Exception:
                    # Бонус уже получен или условия не выполнены
                    continue

        return bonuses

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    async def _get_referral_by_users(
        self, referrer_id: int, referred_id: int
    ) -> Optional[ReferralReward]:
        """Получить реферальную награду по пользователям"""
        query = select(ReferralReward).where(
            and_(
                ReferralReward.referrer_id == referrer_id,
                ReferralReward.referred_id == referred_id,
                ReferralReward.trigger_type == ReferralTriggerType.REGISTRATION,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_referral_for_referred(self, referred_id: int) -> Optional[ReferralReward]:
        """Получить реферальную связь для приглашенного пользователя"""
        query = (
            select(ReferralReward)
            .where(
                and_(
                    ReferralReward.referred_id == referred_id,
                    ReferralReward.trigger_type == ReferralTriggerType.REGISTRATION,
                )
            )
            .order_by(ReferralReward.created_at.asc())
            .limit(1)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_referral_by_id(self, referral_id: int) -> Optional[ReferralReward]:
        """Получить реферальную награду по ID"""
        query = select(ReferralReward).where(ReferralReward.id == referral_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_first_payment_bonus(
        self, referrer_id: int, referred_id: int
    ) -> Optional[ReferralReward]:
        """Получить бонус за первую покупку для конкретного реферала."""
        query = select(ReferralReward).where(
            and_(
                ReferralReward.referrer_id == referrer_id,
                ReferralReward.referred_id == referred_id,
                ReferralReward.trigger_type == ReferralTriggerType.FIRST_PAYMENT,
                ReferralReward.status == ReferralRewardStatus.COMPLETED,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_milestone_reward(
        self, referrer_id: int, milestone: int
    ) -> Optional[ReferralReward]:
        """Проверить существование milestone награды"""
        query = select(ReferralReward).where(
            and_(
                ReferralReward.referrer_id == referrer_id,
                ReferralReward.trigger_type == ReferralTriggerType.MILESTONE,
                ReferralReward.reward_value == milestone,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # ==================== СТАТИСТИКА ====================

    async def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику по рефералам пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой
        """
        # Количество рефералов
        total_referrals = await self._user_repo.get_referral_count(user_id)

        # Количество активных рефералов (с покупками)
        query_active = select(func.count(ReferralReward.id)).where(
            and_(
                ReferralReward.referrer_id == user_id,
                ReferralReward.trigger_type == ReferralTriggerType.FIRST_PAYMENT,
                ReferralReward.status == ReferralRewardStatus.COMPLETED,
            )
        )
        result_active = await self.session.execute(query_active)
        active_referrals = result_active.scalar() or 0

        # Всего заработано бонусов
        total_credits, total_ai_credits = await self._bonus_repo.get_total_credits_from_bonuses(
            user_id,
            bonus_codes=[BonusCodes.REFERRAL_REGISTRATION, BonusCodes.REFERRAL_FIRST_PAYMENT],
            status="COMPLETED",
        )

        # Список всех рефералов
        query_list = (
            select(ReferralReward)
            .where(
                and_(
                    ReferralReward.referrer_id == user_id,
                    ReferralReward.trigger_type == ReferralTriggerType.REGISTRATION,
                )
            )
            .order_by(ReferralReward.created_at.desc())
        )

        result_list = await self.session.execute(query_list)
        referrals_list = list(result_list.scalars().all())

        return {
            "total_referrals": total_referrals,
            "active_referrals": active_referrals,
            "total_credits_earned": total_credits,
            "total_ai_credits_earned": total_ai_credits,
            "referrals": referrals_list,
        }

    async def get_user_referral_rewards(
        self, user_id: int, limit: int = 20
    ) -> List[ReferralReward]:
        """
        Получить список реферальных наград пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей

        Returns:
            Список реферальных наград
        """
        query = (
            select(ReferralReward)
            .where(ReferralReward.referrer_id == user_id)
            .order_by(ReferralReward.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_referrals_detailed(
        self, user_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Получить детальную информацию о рефералах пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей

        Returns:
            Список словарей с информацией о каждом реферале
        """
        from shared.db.models import BonusType

        # Получаем все регистрационные награды (каждая = один реферал)
        query = (
            select(ReferralReward)
            .where(
                and_(
                    ReferralReward.referrer_id == user_id,
                    ReferralReward.trigger_type == ReferralTriggerType.REGISTRATION,
                )
            )
            .order_by(ReferralReward.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        registration_rewards = list(result.scalars().all())

        referrals_info = []

        for reward in registration_rewards:
            # Получаем информацию о реферале
            referred_user = await self._user_repo.get_by_id(reward.referred_id)
            if not referred_user:
                continue

            # Проверяем, была ли первая покупка
            first_payment_query = select(ReferralReward).where(
                and_(
                    ReferralReward.referrer_id == user_id,
                    ReferralReward.referred_id == reward.referred_id,
                    ReferralReward.trigger_type == ReferralTriggerType.FIRST_PAYMENT,
                    ReferralReward.status == ReferralRewardStatus.COMPLETED,
                )
            )
            first_payment_result = await self.session.execute(first_payment_query)
            has_first_payment = first_payment_result.scalar_one_or_none() is not None

            # Проверяем подписку на канал (через бонус CHANNEL_SUBSCRIPTION)
            channel_sub_query = (
                select(UserBonus)
                .join(BonusType, UserBonus.bonus_type_id == BonusType.id)
                .where(
                    and_(
                        UserBonus.user_id == reward.referred_id,
                        BonusType.code == BonusCodes.CHANNEL_SUBSCRIPTION,
                    )
                )
            )
            channel_sub_result = await self.session.execute(channel_sub_query)
            has_channel_subscription = channel_sub_result.scalar_one_or_none() is not None

            referrals_info.append(
                {
                    "telegram_id": referred_user.telegram_id,
                    "username": referred_user.username,
                    "registered_at": reward.created_at,
                    "has_channel_subscription": has_channel_subscription,
                    "has_first_payment": has_first_payment,
                }
            )

        return referrals_info
