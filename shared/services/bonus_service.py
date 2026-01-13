"""
Bonus service with Strategy pattern for different bonus types.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from shared.core.exceptions import BonusAlreadyClaimedError, BonusNotFoundError
from shared.db.models import BonusType, UserBonus
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.user_repository import UserRepository

# ==================== STRATEGY PATTERN ====================


class BonusStrategy(ABC):
    """
    Abstract strategy for bonus application.

    Each bonus type implements this interface with its own logic.
    """

    @abstractmethod
    async def can_apply(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> bool:
        """
        Check if bonus can be applied to user.

        Args:
            user_id: User ID
            bonus_type: Bonus type configuration
            metadata: Additional metadata
            bonus_repo: Bonus repository
            user_repo: User repository

        Returns:
            True if bonus can be applied
        """

    @abstractmethod
    async def apply_bonus(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> UserBonus:
        """
        Apply bonus to user.

        Args:
            user_id: User ID
            bonus_type: Bonus type configuration
            metadata: Additional metadata
            bonus_repo: Bonus repository
            user_repo: User repository

        Returns:
            Created UserBonus
        """


class ChannelSubscriptionBonus(BonusStrategy):
    """Strategy for channel subscription bonus."""

    async def can_apply(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> bool:
        """Check if user hasn't claimed this bonus yet."""
        # Проверяем, не получал ли уже бонус
        has_bonus = await bonus_repo.user_has_bonus(
            user_id=user_id, bonus_type_id=bonus_type.id, status="COMPLETED"
        )
        return not has_bonus

    async def apply_bonus(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> UserBonus:
        """Apply channel subscription bonus."""
        # Создаем запись о бонусе
        user_bonus = await bonus_repo.create_user_bonus(
            user_id=user_id,
            bonus_type_id=bonus_type.id,
            credits_granted=bonus_type.credits_amount,
            ai_credits_granted=bonus_type.ai_credits_amount,
            metadata=metadata,
            status="COMPLETED",
            completed_at=datetime.utcnow(),
        )

        # Начисляем кредиты пользователю
        await user_repo.add_credits(
            user_id=user_id,
            credits=bonus_type.credits_amount,
            ai_credits=bonus_type.ai_credits_amount,
        )

        return user_bonus


class ReferralBonus(BonusStrategy):
    """Strategy for referral bonuses."""

    async def can_apply(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> bool:
        """Check referral bonus conditions."""
        trigger = metadata.get("trigger")
        referred_id = metadata.get("referred_id")

        if not referred_id:
            return False

        if trigger == "REGISTRATION":
            # Можем давать бонус за каждого реферала
            return True

        elif trigger == "FIRST_PAYMENT":
            # Проверяем, первая ли это покупка реферала
            payment_count = await user_repo.get_payment_count(referred_id)
            return payment_count == 1

        return False

    async def apply_bonus(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> UserBonus:
        """Apply referral bonus."""
        user_bonus = await bonus_repo.create_user_bonus(
            user_id=user_id,
            bonus_type_id=bonus_type.id,
            credits_granted=bonus_type.credits_amount,
            ai_credits_granted=bonus_type.ai_credits_amount,
            metadata=metadata,
            status="COMPLETED",
            completed_at=datetime.utcnow(),
        )

        await user_repo.add_credits(
            user_id=user_id,
            credits=bonus_type.credits_amount,
            ai_credits=bonus_type.ai_credits_amount,
        )

        return user_bonus


class RegistrationBonus(BonusStrategy):
    """Strategy for registration bonus."""

    async def can_apply(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> bool:
        """Check if user hasn't claimed registration bonus yet."""
        has_bonus = await bonus_repo.user_has_bonus(
            user_id=user_id, bonus_type_id=bonus_type.id, status="COMPLETED"
        )
        return not has_bonus

    async def apply_bonus(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> UserBonus:
        """Apply registration bonus."""
        user_bonus = await bonus_repo.create_user_bonus(
            user_id=user_id,
            bonus_type_id=bonus_type.id,
            credits_granted=bonus_type.credits_amount,
            ai_credits_granted=bonus_type.ai_credits_amount,
            metadata=metadata,
            status="COMPLETED",
            completed_at=datetime.utcnow(),
        )

        await user_repo.add_credits(
            user_id=user_id,
            credits=bonus_type.credits_amount,
            ai_credits=bonus_type.ai_credits_amount,
        )

        return user_bonus


class MilestoneBonus(BonusStrategy):
    """Strategy for referral milestone bonuses."""

    async def can_apply(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> bool:
        """Check if milestone bonus can be applied."""
        # Проверяем, не получен ли уже этот майлстоун
        has_bonus = await bonus_repo.user_has_bonus(
            user_id=user_id, bonus_type_id=bonus_type.id, status="COMPLETED"
        )
        if has_bonus:
            return False

        # Проверяем, достиг ли пользователь нужного количества рефералов
        referral_count = await user_repo.get_referral_count(user_id)
        milestone_count = (
            bonus_type.conditions.get("milestone_count", 0) if bonus_type.conditions else 0
        )

        return referral_count >= milestone_count

    async def apply_bonus(
        self,
        user_id: int,
        bonus_type: BonusType,
        metadata: Dict[str, Any],
        bonus_repo: BonusRepository,
        user_repo: UserRepository,
    ) -> UserBonus:
        """Apply milestone bonus."""
        user_bonus = await bonus_repo.create_user_bonus(
            user_id=user_id,
            bonus_type_id=bonus_type.id,
            credits_granted=bonus_type.credits_amount,
            ai_credits_granted=bonus_type.ai_credits_amount,
            metadata=metadata,
            status="COMPLETED",
            completed_at=datetime.utcnow(),
        )

        await user_repo.add_credits(
            user_id=user_id,
            credits=bonus_type.credits_amount,
            ai_credits=bonus_type.ai_credits_amount,
        )

        return user_bonus


# ==================== BONUS MANAGER ====================


class BonusService:
    """
    Bonus service that manages bonus application using Strategy pattern.
    """

    def __init__(self, bonus_repo: BonusRepository, user_repo: UserRepository):
        """
        Initialize bonus service.

        Args:
            bonus_repo: Bonus repository
            user_repo: User repository
        """
        self._bonus_repo = bonus_repo
        self._user_repo = user_repo

        # Регистрируем стратегии для каждого типа бонуса
        self._strategies: Dict[str, BonusStrategy] = {
            "CHANNEL_SUBSCRIPTION": ChannelSubscriptionBonus(),
            "REGISTRATION": RegistrationBonus(),
            "REFERRAL_REGISTRATION": ReferralBonus(),
            "REFERRAL_FIRST_PAYMENT": ReferralBonus(),
            # Milestone strategies
            "REFERRAL_MILESTONE_5": MilestoneBonus(),
            "REFERRAL_MILESTONE_10": MilestoneBonus(),
            "REFERRAL_MILESTONE_25": MilestoneBonus(),
            "REFERRAL_MILESTONE_50": MilestoneBonus(),
            "REFERRAL_MILESTONE_100": MilestoneBonus(),
        }

    async def get_bonus_type(self, code: str) -> Optional[BonusType]:
        """
        Get bonus type by code.

        Args:
            code: Bonus code

        Returns:
            BonusType or None
        """
        return await self._bonus_repo.get_by_code(code)

    async def can_claim_bonus(
        self, user_id: int, bonus_code: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if user can claim bonus.

        Args:
            user_id: User ID
            bonus_code: Bonus code
            metadata: Additional metadata

        Returns:
            True if bonus can be claimed
        """
        bonus_type = await self.get_bonus_type(bonus_code)
        if not bonus_type or not bonus_type.is_active:
            return False

        # Получаем стратегию для этого типа бонуса
        strategy = self._strategies.get(bonus_code)
        if not strategy:
            return False

        # Проверяем через стратегию
        return await strategy.can_apply(
            user_id=user_id,
            bonus_type=bonus_type,
            metadata=metadata or {},
            bonus_repo=self._bonus_repo,
            user_repo=self._user_repo,
        )

    async def claim_bonus(
        self, user_id: int, bonus_code: str, metadata: Optional[Dict[str, Any]] = None
    ) -> UserBonus:
        """
        Claim bonus for user.

        Args:
            user_id: User ID
            bonus_code: Bonus code
            metadata: Additional metadata

        Returns:
            Created UserBonus

        Raises:
            BonusNotFoundError: Bonus not found
            BonusAlreadyClaimedError: Bonus already claimed
            BonusConditionNotMetError: Conditions not met
        """
        # Проверяем возможность получения
        if not await self.can_claim_bonus(user_id, bonus_code, metadata):
            raise BonusAlreadyClaimedError(f"User {user_id} cannot claim bonus {bonus_code}")

        bonus_type = await self.get_bonus_type(bonus_code)
        if not bonus_type:
            raise BonusNotFoundError(f"Bonus {bonus_code} not found")

        # Получаем стратегию и применяем бонус
        strategy = self._strategies.get(bonus_code)
        if not strategy:
            raise BonusNotFoundError(f"No strategy for bonus {bonus_code}")

        return await strategy.apply_bonus(
            user_id=user_id,
            bonus_type=bonus_type,
            metadata=metadata or {},
            bonus_repo=self._bonus_repo,
            user_repo=self._user_repo,
        )

    async def get_user_bonuses(self, user_id: int, status: Optional[str] = None) -> list[UserBonus]:
        """
        Get user bonuses.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            List of user bonuses
        """
        return await self._bonus_repo.get_user_bonuses(user_id, status)

    async def get_bonus_stats(self, user_id: int) -> Dict[str, int]:
        """
        Get user bonus statistics.

        Args:
            user_id: User ID

        Returns:
            Dictionary with bonus stats
        """
        credits, ai_credits = await self._bonus_repo.get_total_credits_from_bonuses(user_id)

        return {"total_credits_from_bonuses": credits, "total_ai_credits_from_bonuses": ai_credits}
