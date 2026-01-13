"""
Referral Repository - управление реферальной системой.

Реализует паттерн Repository для работы с моделями ReferralReward.
"""

import secrets
import string
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import ReferralReward, ReferralRewardStatus, User
from shared.db.repositories.base import BaseRepository


def generate_referral_code(length: int = 8) -> str:
    """
    Generate unique referral code.

    Args:
        length: Code length

    Returns:
        Referral code
    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class ReferralRewardRepository(BaseRepository[ReferralReward]):
    """Репозиторий для управления реферальными вознаграждениями"""

    def __init__(self, session: AsyncSession):
        super().__init__(ReferralReward, session)

    async def create_referral_code(self, user_id: int) -> str:
        """
        Create or get existing referral code for user.

        Args:
            user_id: User ID

        Returns:
            Referral code

        Raises:
            ValueError: If user not found
        """
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Пользователь не найден")

        if user.referral_code:
            return user.referral_code

        # Generate unique code
        while True:
            code = generate_referral_code()
            existing = await self.session.execute(select(User).where(User.referral_code == code))
            if not existing.scalar_one_or_none():
                break

        user.referral_code = code
        await self.session.commit()
        await self.session.refresh(user)

        return code

    async def apply_referral_code(self, referred_user_id: int, referral_code: str) -> bool:
        """
        Apply referral code to new user.

        Args:
            referred_user_id: ID of invited user
            referral_code: Referral code

        Returns:
            True if successful, False if not found
        """
        # Find user with this code
        result = await self.session.execute(select(User).where(User.referral_code == referral_code))
        referrer = result.scalar_one_or_none()

        if not referrer:
            return False

        # Don't allow using own code
        if referrer.id == referred_user_id:
            return False

        # Check if user already used referral code
        existing_reward = await self.session.execute(
            select(ReferralReward).where(ReferralReward.referred_id == referred_user_id)
        )
        if existing_reward.scalar_one_or_none():
            return False

        # Create reward record (pending)
        await self.create_reward(
            referrer_id=referrer.id,
            referred_id=referred_user_id,
            reward_type="credits",
            reward_value=5,  # e.g., 5 credits for registration
        )

        return True

    async def create_reward(
        self,
        referrer_id: int,
        referred_id: int,
        reward_type: str,
        reward_value: Optional[int] = None,
        status: ReferralRewardStatus = ReferralRewardStatus.PENDING,
    ) -> ReferralReward:
        """
        Create referral reward record.

        Args:
            referrer_id: ID of referrer
            referred_id: ID of referred user
            reward_type: Reward type (credits/subscription/bonus)
            reward_value: Reward value
            status: Reward status

        Returns:
            Created reward record
        """
        reward = ReferralReward(
            referrer_id=referrer_id,
            referred_id=referred_id,
            reward_type=reward_type,
            reward_value=reward_value,
            status=status,
        )

        self.session.add(reward)
        await self.session.commit()
        await self.session.refresh(reward)

        return reward

    async def complete_reward(self, reward_id: int) -> ReferralReward:
        """
        Mark reward as completed and grant it.

        Args:
            reward_id: Reward ID

        Returns:
            Updated reward record
        """
        result = await self.session.execute(
            select(ReferralReward).where(ReferralReward.id == reward_id)
        )
        reward = result.scalar_one_or_none()

        if reward and reward.status == ReferralRewardStatus.PENDING:
            reward.status = ReferralRewardStatus.COMPLETED
            reward.condition_met = True
            reward.condition_date = datetime.utcnow()
            reward.rewarded_at = datetime.utcnow()

            # Grant reward
            if reward.reward_type == "credits":
                referrer_result = await self.session.execute(
                    select(User).where(User.id == reward.referrer_id)
                )
                referrer = referrer_result.scalar_one_or_none()
                if referrer and reward.reward_value:
                    referrer.credits += reward.reward_value

            await self.session.commit()
            await self.session.refresh(reward)

        return reward

    async def get_stats(self, user_id: int) -> dict:
        """
        Get referral statistics for user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with statistics
        """
        # Number of referrals (unique referred_id)
        referrals_count = await self.session.execute(
            select(func.count(func.distinct(ReferralReward.referred_id))).where(
                ReferralReward.referrer_id == user_id
            )
        )
        total_referrals = referrals_count.scalar_one()

        # Number of completed rewards
        completed_rewards = await self.session.execute(
            select(func.count(ReferralReward.id)).where(
                and_(
                    ReferralReward.referrer_id == user_id,
                    ReferralReward.status == ReferralRewardStatus.COMPLETED,
                )
            )
        )
        total_completed = completed_rewards.scalar_one()

        # Sum of received credits
        credits_sum = await self.session.execute(
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

    async def get_user_referrals(self, user_id: int) -> list[User]:
        """
        Get list of all user referrals.

        Args:
            user_id: User ID

        Returns:
            List of referred users
        """
        # Get IDs of all referred users via ReferralReward
        rewards = await self.session.execute(
            select(ReferralReward.referred_id).where(ReferralReward.referrer_id == user_id)
        )
        referred_ids = [r for r in rewards.scalars().all()]

        if not referred_ids:
            return []

        # Get users
        result = await self.session.execute(select(User).where(User.id.in_(referred_ids)))
        return list(result.scalars().all())

    async def get_pending_rewards(self, user_id: int) -> list[ReferralReward]:
        """
        Get list of pending rewards.

        Args:
            user_id: User ID

        Returns:
            List of pending rewards
        """
        result = await self.session.execute(
            select(ReferralReward).where(
                and_(
                    ReferralReward.referrer_id == user_id,
                    ReferralReward.status == ReferralRewardStatus.PENDING,
                )
            )
        )
        return list(result.scalars().all())

    async def count_total_referred_users(self) -> int:
        """
        Count total number of users who came via referral link.

        Returns:
            Number of unique referred users
        """
        from shared.db.models import ReferralTriggerType

        result = await self.session.execute(
            select(func.count(func.distinct(ReferralReward.referred_id))).where(
                ReferralReward.trigger_type == ReferralTriggerType.REGISTRATION
            )
        )
        return result.scalar() or 0
