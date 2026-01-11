"""
Bonus repository for database operations.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.exceptions import BonusNotFoundError
from shared.db.models import BonusStatus, BonusType, UserBonus
from shared.db.repositories.base import BaseRepository


class BonusRepository(BaseRepository[BonusType]):
    """Repository for BonusType operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(BonusType, session)

    async def get_by_code(self, code: str) -> Optional[BonusType]:
        """
        Get bonus type by code.

        Args:
            code: Bonus type code (e.g., "CHANNEL_SUBSCRIPTION")

        Returns:
            BonusType or None
        """
        result = await self.session.execute(select(BonusType).where(BonusType.code == code))
        return result.scalar_one_or_none()

    async def get_active_bonuses(self) -> List[BonusType]:
        """
        Get all active bonus types.

        Returns:
            List of active bonus types
        """
        result = await self.session.execute(select(BonusType).where(BonusType.is_active == True))
        return list(result.scalars().all())

    async def create_user_bonus(
        self,
        user_id: int,
        bonus_type_id: int,
        credits_granted: int = 0,
        ai_credits_granted: int = 0,
        metadata: Optional[dict] = None,
        status: str = "PENDING",
        completed_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
    ) -> UserBonus:
        """
        Create a user bonus record.

        Args:
            user_id: User ID
            bonus_type_id: Bonus type ID
            credits_granted: Credits granted
            ai_credits_granted: AI credits granted
            metadata: Additional metadata
            status: Bonus status
            completed_at: When bonus was completed
            expires_at: When bonus expires

        Returns:
            Created UserBonus
        """
        user_bonus = UserBonus(
            user_id=user_id,
            bonus_type_id=bonus_type_id,
            credits_granted=credits_granted,
            ai_credits_granted=ai_credits_granted,
            extra_data=metadata or {},
            status=BonusStatus[status],
            completed_at=completed_at,
            expires_at=expires_at,
        )

        self.session.add(user_bonus)
        await self.session.commit()
        await self.session.refresh(user_bonus)
        return user_bonus

    async def get_user_bonuses(self, user_id: int, status: Optional[str] = None) -> List[UserBonus]:
        """
        Get all bonuses for a user.

        Args:
            user_id: User ID
            status: Optional status filter

        Returns:
            List of user bonuses
        """
        query = select(UserBonus).where(UserBonus.user_id == user_id)

        if status:
            query = query.where(UserBonus.status == BonusStatus[status])

        result = await self.session.execute(query.order_by(UserBonus.created_at.desc()))
        return list(result.scalars().all())

    async def user_has_bonus(
        self, user_id: int, bonus_type_id: int, status: Optional[str] = None
    ) -> bool:
        """
        Check if user has a specific bonus.

        Args:
            user_id: User ID
            bonus_type_id: Bonus type ID
            status: Optional status filter (e.g., "COMPLETED")

        Returns:
            True if user has the bonus
        """
        query = select(UserBonus).where(
            and_(UserBonus.user_id == user_id, UserBonus.bonus_type_id == bonus_type_id)
        )

        if status:
            query = query.where(UserBonus.status == BonusStatus[status])

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_last_user_bonus(self, user_id: int, bonus_type_id: int) -> Optional[UserBonus]:
        """
        Get the last bonus of a specific type for a user.

        Args:
            user_id: User ID
            bonus_type_id: Bonus type ID

        Returns:
            Last UserBonus or None
        """
        result = await self.session.execute(
            select(UserBonus)
            .where(and_(UserBonus.user_id == user_id, UserBonus.bonus_type_id == bonus_type_id))
            .order_by(UserBonus.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_bonus_status(
        self, bonus_id: int, status: str, completed_at: Optional[datetime] = None
    ) -> UserBonus:
        """
        Update bonus status.

        Args:
            bonus_id: UserBonus ID
            status: New status
            completed_at: Completion timestamp

        Returns:
            Updated UserBonus

        Raises:
            BonusNotFoundError: If bonus not found
        """
        result = await self.session.execute(select(UserBonus).where(UserBonus.id == bonus_id))
        bonus = result.scalar_one_or_none()

        if not bonus:
            raise BonusNotFoundError(f"Bonus {bonus_id} not found")

        bonus.status = BonusStatus[status]
        if completed_at:
            bonus.completed_at = completed_at

        await self.session.commit()
        await self.session.refresh(bonus)
        return bonus

    async def get_total_credits_from_bonuses(
        self, user_id: int, bonus_codes: Optional[List[str]] = None, status: str = "COMPLETED"
    ) -> tuple[int, int]:
        """
        Get total credits and AI credits user received from bonuses.

        Args:
            user_id: User ID
            bonus_codes: Optional list of bonus codes to filter by
            status: Bonus status filter

        Returns:
            Tuple of (total_credits, total_ai_credits)
        """
        from sqlalchemy import func

        # Базовое условие
        conditions = [UserBonus.user_id == user_id, UserBonus.status == BonusStatus[status]]

        # Если нужна фильтрация по кодам, делаем JOIN с BonusType
        if bonus_codes:
            query = (
                select(func.sum(UserBonus.credits_granted), func.sum(UserBonus.ai_credits_granted))
                .join(BonusType, UserBonus.bonus_type_id == BonusType.id)
                .where(and_(*conditions, BonusType.code.in_(bonus_codes)))
            )
        else:
            query = select(
                func.sum(UserBonus.credits_granted), func.sum(UserBonus.ai_credits_granted)
            ).where(and_(*conditions))

        result = await self.session.execute(query)

        row = result.one()
        total_credits = row[0] or 0
        total_ai_credits = row[1] or 0

        return (total_credits, total_ai_credits)
