"""
Credit Manager

Service for managing AI credits
"""
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import User
from shared.db.repositories.user_repository import UserRepository
from shared.services.credit_service import CreditService


class CreditManager:
    """Manager for AI credits operations"""

    def __init__(
        self,
        session: AsyncSession,
        user_repo: Optional[UserRepository] = None,
        credit_service: Optional[CreditService] = None,
    ):
        self.session = session
        self._user_repo = user_repo
        self._credit_service = credit_service

    async def get_user_credits(self, user_id: int) -> Optional[int]:
        """
        Get user's AI credits balance

        Args:
            user_id: Telegram user ID

        Returns:
            Number of AI credits or None if user not found
        """
        result = await self.session.execute(select(User.ai_credits).where(User.tg_id == user_id))
        credits = result.scalar_one_or_none()
        return credits

    async def has_enough_credits(self, user_id: int, required_credits: int) -> bool:
        """
        Check if user has enough AI credits

        Args:
            user_id: Telegram user ID
            required_credits: Required amount of credits

        Returns:
            True if user has enough credits
        """
        current_credits = await self.get_user_credits(user_id)

        if current_credits is None:
            return False

        return current_credits >= required_credits

    async def has_sufficient_credits(self, user_id: int, required_credits: int) -> bool:
        """
        Alias for has_enough_credits (for compatibility with tests)

        Args:
            user_id: Internal user ID (not Telegram ID)
            required_credits: Required amount of credits

        Returns:
            True if user has enough credits
        """
        if self._credit_service:
            # Use credit service if available (preferred for tests)
            return await self._credit_service.has_sufficient_credits(
                user_id, required_credits, "ai_credits"
            )

        # Fall back to legacy method
        return await self.has_enough_credits(user_id, required_credits)

    async def deduct_credits(self, user_id: int, amount: int) -> bool:
        """
        Deduct AI credits from user

        Args:
            user_id: Telegram user ID
            amount: Amount of credits to deduct

        Returns:
            True if successful, False if insufficient credits

        Raises:
            ValueError: If amount is negative
        """
        if amount < 0:
            raise ValueError("Amount must be positive")

        # Check if user has enough credits
        if not await self.has_enough_credits(user_id, amount):
            return False

        # Deduct credits
        await self.session.execute(
            update(User)
            .where(User.tg_id == user_id)
            .values(
                ai_credits=User.ai_credits - amount, ai_credits_used=User.ai_credits_used + amount
            )
        )

        await self.session.commit()
        return True

    async def add_credits(self, user_id: int, amount: int) -> bool:
        """
        Add AI credits to user

        Args:
            user_id: Telegram user ID
            amount: Amount of credits to add

        Returns:
            True if successful

        Raises:
            ValueError: If amount is negative
        """
        if amount < 0:
            raise ValueError("Amount must be positive")

        await self.session.execute(
            update(User).where(User.tg_id == user_id).values(ai_credits=User.ai_credits + amount)
        )

        await self.session.commit()
        return True

    async def get_user_stats(self, user_id: int) -> Optional[dict]:
        """
        Get user's AI credits statistics

        Args:
            user_id: Telegram user ID

        Returns:
            Dict with credits statistics or None if user not found
        """
        result = await self.session.execute(
            select(User.ai_credits, User.ai_credits_used).where(User.tg_id == user_id)
        )
        row = result.first()

        if not row:
            return None

        return {
            "ai_credits": row.ai_credits,
            "ai_credits_used": row.ai_credits_used,
            "total_received": row.ai_credits + row.ai_credits_used,
        }

    async def refund_credits(self, user_id: int, amount: int, reason: str = "") -> bool:
        """
        Refund AI credits to user (e.g., on failed generation)

        Args:
            user_id: Telegram user ID
            amount: Amount of credits to refund
            reason: Reason for refund (for logging)

        Returns:
            True if successful
        """
        if amount < 0:
            raise ValueError("Amount must be positive")

        await self.session.execute(
            update(User)
            .where(User.tg_id == user_id)
            .values(
                ai_credits=User.ai_credits + amount, ai_credits_used=User.ai_credits_used - amount
            )
        )

        await self.session.commit()
        return True
