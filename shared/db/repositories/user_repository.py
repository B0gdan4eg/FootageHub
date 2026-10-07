"""
User repository for database operations.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.exceptions import (
    InsufficientAICreditsError,
    InsufficientCreditsError,
    UserNotFoundError,
)
from shared.db.models import User
from shared.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int, *, lock: bool = False) -> Optional[User]:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User or None if not found
        """
        query = select(User).where(User.tg_id == telegram_id)
        if lock:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, referral_code: str) -> Optional[User]:
        """
        Get user by referral code.

        Args:
            referral_code: Referral code

        Returns:
            User or None if not found
        """
        result = await self.session.execute(select(User).where(User.referral_code == referral_code))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number."""
        result = await self.session.execute(select(User).where(User.phone_number == phone))
        return result.scalar_one_or_none()

    async def get_or_create_by_phone(self, phone: str, username: Optional[str] = None) -> tuple:
        """
        Get user by phone or create new one.

        Returns:
            Tuple (user, created: bool)
        """
        import random
        import string

        user = await self.get_by_phone(phone)
        if user:
            return user, False

        code = "REF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        user = await self.create(
            phone_number=phone,
            username=username,
            referral_code=code,
            credits=3,
        )
        return user, True

    async def get_or_create_by_telegram_id(
        self, telegram_id: int, username: Optional[str] = None, referral_code: Optional[str] = None
    ) -> User:
        """
        Get user by Telegram ID or create if doesn't exist.

        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            referral_code: User's referral code

        Returns:
            User object
        """
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            user = await self.create(
                tg_id=telegram_id, username=username, referral_code=referral_code, credits=3
            )
        return user

    async def add_credits(self, user_id: int, credits: int = 0, ai_credits: int = 0) -> User:
        """
        Add credits to user.

        Args:
            user_id: User ID
            credits: Regular credits to add
            ai_credits: AI credits to add

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        user.credits += credits
        user.ai_credits += ai_credits

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def deduct_credits(self, user_id: int, credits: int) -> User:
        """
        Deduct regular credits from user.

        Args:
            user_id: User ID
            credits: Credits to deduct

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user not found
            InsufficientCreditsError: If not enough credits
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        if user.credits < credits:
            raise InsufficientCreditsError(f"User has {user.credits} credits, needs {credits}")

        user.credits -= credits
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def deduct_ai_credits(self, user_id: int, ai_credits: int) -> User:
        """
        Deduct AI credits from user.

        Args:
            user_id: User ID
            ai_credits: AI credits to deduct

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user not found
            InsufficientAICreditsError: If not enough AI credits
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        if user.ai_credits < ai_credits:
            raise InsufficientAICreditsError(
                f"User has {user.ai_credits} AI credits, needs {ai_credits}"
            )

        user.ai_credits -= ai_credits
        user.ai_credits_used += ai_credits

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def refund_ai_credits(self, user_id: int, ai_credits: int) -> User:
        """
        Refund AI credits to user (e.g., after failed generation).

        Args:
            user_id: User ID
            ai_credits: AI credits to refund

        Returns:
            Updated user

        Raises:
            UserNotFoundError: If user not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        user.ai_credits += ai_credits
        if user.ai_credits_used >= ai_credits:
            user.ai_credits_used -= ai_credits

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_referral_count(self, user_id: int) -> int:
        """
        Get number of users referred by this user.

        Args:
            user_id: User ID

        Returns:
            Number of referrals
        """
        from shared.db.models import ReferralReward, ReferralTriggerType

        user = await self.get_by_id(user_id)
        if not user:
            return 0

        # Считаем только регистрационные награды (каждая = один уникальный реферал)
        result = await self.session.execute(
            select(func.count(ReferralReward.id)).where(
                ReferralReward.referrer_id == user_id,
                ReferralReward.trigger_type == ReferralTriggerType.REGISTRATION,
            )
        )
        return result.scalar() or 0

    async def has_any_payment(self, user_id: int) -> bool:
        """
        Check if user has made any payments.

        Args:
            user_id: User ID

        Returns:
            True if user has payments
        """
        from shared.db.models import Payment

        result = await self.session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.user_id == user_id)
            .where(Payment.status == "success")
        )
        count = result.scalar() or 0
        return count > 0

    async def get_payment_count(self, user_id: int) -> int:
        """
        Get number of successful payments by user.

        Args:
            user_id: User ID

        Returns:
            Number of successful payments
        """
        from shared.db.models import Payment

        result = await self.session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.user_id == user_id)
            .where(Payment.status == "success")
        )
        return result.scalar() or 0

    async def get_all_users(self):
        """
        Get all users.

        Returns:
            List of all users
        """
        result = await self.session.execute(select(User))
        return result.scalars().all()

    async def set_user_referrer(self, new_user_tg_id: int, referral_code: str) -> bool:
        """
        Set referrer for a user by referral code.

        Args:
            new_user_tg_id: Telegram ID of new user
            referral_code: Referral code of referrer

        Returns:
            True if user was updated, False if user not found
        """
        # Find referrer (may be None)
        referrer = await self.get_by_referral_code(referral_code)

        # Find new user
        new_user = await self.get_by_telegram_id(new_user_tg_id)

        if not new_user:
            return False  # User not found

        # Set referred_by_id (None if referrer not found)
        new_user.referred_by_id = referrer.id if referrer else None
        await self.session.commit()
        return True

    async def update_subscription(self, user_id: int, months: int = 1) -> None:
        """
        Update user subscription for specified months.

        Args:
            user_id: User ID
            months: Number of months to add (default 1)
        """
        from datetime import datetime, timedelta

        from sqlalchemy import update

        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                is_subscribed=True,
                subscription_until=datetime.utcnow() + timedelta(days=30 * months),
            )
        )
        await self.session.commit()

    async def count_active_subscriptions(self) -> int:
        """
        Count active subscriptions.

        Returns:
            Number of active subscriptions
        """
        from datetime import datetime

        from sqlalchemy import and_

        from shared.db.models import Subscription

        result = await self.session.execute(
            select(func.count())
            .select_from(Subscription)
            .where(and_(Subscription.is_active, Subscription.end_date > datetime.utcnow()))
        )
        return result.scalar() or 0

    async def grant_access(self, user_id: int, type_: str, value: int) -> None:
        """
        Grant subscription days or credits to user by telegram ID.

        Args:
            user_id: Telegram user ID
            type_: Type of grant ('subscription' or 'credits')
            value: Days for subscription or credits amount

        Raises:
            ValueError: If user not found or invalid type
        """
        from datetime import datetime, timedelta

        user = await self.get_by_telegram_id(user_id)
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

        await self.session.commit()

    async def generate_referral_code(self, user_id: int) -> str:
        """
        Generate and set unique referral code for user.

        Args:
            user_id: User ID

        Returns:
            Generated referral code

        Raises:
            UserNotFoundError: If user not found
        """
        import random
        import string

        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        # Если уже есть код, вернуть его
        if user.referral_code:
            return user.referral_code

        # Генерация уникального кода
        max_attempts = 10
        for _ in range(max_attempts):
            # Формат: REF + 6 случайных символов (буквы и цифры)
            code = "REF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

            # Проверка уникальности
            existing = await self.get_by_referral_code(code)
            if not existing:
                user.referral_code = code
                await self.session.commit()
                await self.session.refresh(user)
                return code

        # Если не удалось сгенерировать уникальный код за 10 попыток,
        # используем user_id в коде для гарантии уникальности
        code = f"REF{user_id:08d}"
        user.referral_code = code
        await self.session.commit()
        await self.session.refresh(user)
        return code

    async def has_downloaded(self, user_id: int, url: str, hours: int = 24) -> bool:
        """
        Check if user has downloaded file from URL within specified hours.

        Args:
            user_id: User's database ID
            url: Media URL
            hours: Time window in hours (default 24)

        Returns:
            True if user has downloaded this file within time window
        """
        from datetime import datetime, timedelta

        from shared.db.models import Download, Media

        try:
            time_limit = datetime.utcnow() - timedelta(hours=hours)

            result = await self.session.execute(
                select(Download)
                .join(Media, Download.media_id == Media.id)
                .where(
                    Download.user_id == user_id,
                    Media.url == url,
                    Download.downloaded_at >= time_limit,
                )
            )
            download = result.scalars().first()
            return download is not None

        except Exception as e:
            print(f"Error checking user download history: {e}")
            return False

    async def add_daily_credits(self) -> dict[str, int]:
        """
        Process daily credit addition for active subscribers.
        Also expires outdated subscriptions.

        Returns:
            Dictionary with counts of expired and credited users
        """
        from datetime import datetime

        now = datetime.utcnow()

        # Disable expired subscriptions
        expired_result = await self.session.execute(
            select(User).where(
                User.is_subscribed,
                User.subscription_until is not None,
                User.subscription_until <= now,
            )
        )
        expired_users = expired_result.scalars().all()
        for user in expired_users:
            user.is_subscribed = False

        # Add credits to active subscribers
        active_result = await self.session.execute(
            select(User).where(
                User.is_subscribed,
                User.subscription_until is not None,
                User.subscription_until > now,
            )
        )
        active_users = active_result.scalars().all()
        for user in active_users:
            user.credits += 30

        await self.session.commit()

        return {"expired": len(expired_users), "credited": len(active_users)}
