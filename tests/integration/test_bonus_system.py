"""
Integration tests for the bonus system.

Tests the complete flow from user creation to bonus claiming.
"""

import random

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.exceptions import BonusAlreadyClaimedError
from shared.db.models import BonusStatus, BonusType, User
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.user_repository import UserRepository
from shared.services.bonus_service import BonusService


@pytest.fixture
def unique_tg_id():
    """Generate unique telegram ID for each test."""
    return random.randint(100000, 999999)


@pytest.fixture
def unique_referral_code():
    """Generate unique referral code for each test."""
    return f"TEST{random.randint(1000, 9999)}"


@pytest_asyncio.fixture
async def setup_bonus_types(async_session: AsyncSession):
    """Create test bonus types in database."""
    from sqlalchemy import select

    bonus_types_data = [
        {
            "code": "CHANNEL_SUBSCRIPTION",
            "name": "Channel Subscription Bonus",
            "description": "Bonus for subscribing to channel",
            "reward_type": "CREDITS",
            "credits_amount": 10,
            "ai_credits_amount": 5,
            "is_active": True,
            "is_repeatable": False,
        },
        {
            "code": "FIRST_LOGIN",
            "name": "First Login Bonus",
            "description": "Welcome bonus for first login",
            "reward_type": "BOTH",
            "credits_amount": 20,
            "ai_credits_amount": 10,
            "is_active": True,
            "is_repeatable": False,
        },
        {
            "code": "DAILY_LOGIN",
            "name": "Daily Login Bonus",
            "description": "Daily login reward",
            "reward_type": "AI_CREDITS",
            "credits_amount": 0,
            "ai_credits_amount": 3,
            "is_active": True,
            "is_repeatable": True,
            "cooldown_days": 1,
        },
    ]

    created_types = []
    for data in bonus_types_data:
        # Check if bonus type already exists
        result = await async_session.execute(
            select(BonusType).where(BonusType.code == data["code"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            for key, value in data.items():
                setattr(existing, key, value)
            created_types.append(existing)
        else:
            # Create new
            bonus_type = BonusType(**data)
            async_session.add(bonus_type)
            created_types.append(bonus_type)

    await async_session.commit()

    return created_types


class TestBonusSystemIntegration:
    """Integration tests for bonus system."""

    @pytest.mark.asyncio
    async def test_complete_bonus_flow(
        self, async_session: AsyncSession, setup_bonus_types, unique_tg_id, unique_referral_code
    ):
        """Test complete flow: create user, claim bonus, verify credits."""
        # Setup repositories and services
        user_repo = UserRepository(async_session)
        bonus_repo = BonusRepository(async_session)
        bonus_service = BonusService(bonus_repo, user_repo)

        # Create user with unique data
        user = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"test_user_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        await async_session.commit()

        assert user.credits == 0
        assert user.ai_credits == 0

        # Claim channel subscription bonus
        can_claim = await bonus_service.can_claim_bonus(user.id, "CHANNEL_SUBSCRIPTION")
        assert can_claim is True

        user_bonus = await bonus_service.claim_bonus(
            user.id, "CHANNEL_SUBSCRIPTION", {"channel": "@test_channel"}
        )
        await async_session.commit()

        assert user_bonus is not None
        assert user_bonus.credits_granted == 10
        assert user_bonus.ai_credits_granted == 5
        assert user_bonus.status == BonusStatus.COMPLETED

        # Verify credits were added to user
        await async_session.refresh(user)
        assert user.credits == 10
        assert user.ai_credits == 5

        # Try to claim again - should fail
        can_claim_again = await bonus_service.can_claim_bonus(user.id, "CHANNEL_SUBSCRIPTION")
        assert can_claim_again is False

        with pytest.raises(BonusAlreadyClaimedError):
            await bonus_service.claim_bonus(user.id, "CHANNEL_SUBSCRIPTION")

    @pytest.mark.asyncio
    async def test_first_login_bonus(
        self, async_session: AsyncSession, setup_bonus_types, unique_tg_id
    ):
        """Test first login bonus flow."""
        user_repo = UserRepository(async_session)
        bonus_repo = BonusRepository(async_session)
        bonus_service = BonusService(bonus_repo, user_repo)

        # Create user
        user = await user_repo.create(tg_id=unique_tg_id, username=f"new_user_{unique_tg_id}")
        await async_session.commit()

        # Claim first login bonus
        user_bonus = await bonus_service.claim_bonus(user.id, "FIRST_LOGIN")
        await async_session.commit()

        assert user_bonus.credits_granted == 20
        assert user_bonus.ai_credits_granted == 10

        # Verify credits
        await async_session.refresh(user)
        assert user.credits == 20
        assert user.ai_credits == 10

    @pytest.mark.asyncio
    async def test_multiple_bonuses(
        self, async_session: AsyncSession, setup_bonus_types, unique_tg_id
    ):
        """Test claiming multiple different bonuses."""
        user_repo = UserRepository(async_session)
        bonus_repo = BonusRepository(async_session)
        bonus_service = BonusService(bonus_repo, user_repo)

        # Create user
        user = await user_repo.create(
            tg_id=unique_tg_id, username=f"multi_bonus_user_{unique_tg_id}"
        )
        await async_session.commit()

        # Claim first login bonus
        await bonus_service.claim_bonus(user.id, "FIRST_LOGIN")
        await async_session.commit()

        # Claim channel subscription bonus
        await bonus_service.claim_bonus(user.id, "CHANNEL_SUBSCRIPTION")
        await async_session.commit()

        # Verify total credits
        await async_session.refresh(user)
        assert user.credits == 30  # 20 + 10
        assert user.ai_credits == 15  # 10 + 5

        # Get bonus stats
        stats = await bonus_service.get_bonus_stats(user.id)
        assert stats["total_credits_from_bonuses"] == 30
        assert stats["total_ai_credits_from_bonuses"] == 15

    @pytest.mark.asyncio
    async def test_daily_login_bonus_repeatable(
        self, async_session: AsyncSession, setup_bonus_types, unique_tg_id
    ):
        """Test daily login bonus can be claimed multiple times."""
        user_repo = UserRepository(async_session)
        bonus_repo = BonusRepository(async_session)
        bonus_service = BonusService(bonus_repo, user_repo)

        # Create user
        user = await user_repo.create(tg_id=unique_tg_id, username=f"daily_user_{unique_tg_id}")
        await async_session.commit()

        # Claim daily login bonus first time
        can_claim = await bonus_service.can_claim_bonus(user.id, "DAILY_LOGIN")
        assert can_claim is True

        user_bonus = await bonus_service.claim_bonus(user.id, "DAILY_LOGIN")
        await async_session.commit()

        assert user_bonus.ai_credits_granted == 3

        # Verify credits
        await async_session.refresh(user)
        assert user.ai_credits == 3

        # Try to claim again immediately - should fail due to cooldown
        can_claim_again = await bonus_service.can_claim_bonus(user.id, "DAILY_LOGIN")
        assert can_claim_again is False

    @pytest.mark.asyncio
    async def test_bonus_stats(self, async_session: AsyncSession, setup_bonus_types, unique_tg_id):
        """Test getting user bonus statistics."""
        user_repo = UserRepository(async_session)
        bonus_repo = BonusRepository(async_session)
        bonus_service = BonusService(bonus_repo, user_repo)

        # Create user and claim bonuses
        user = await user_repo.create(tg_id=unique_tg_id, username=f"stats_user_{unique_tg_id}")
        await async_session.commit()

        await bonus_service.claim_bonus(user.id, "FIRST_LOGIN")
        await bonus_service.claim_bonus(user.id, "CHANNEL_SUBSCRIPTION")
        await async_session.commit()

        # Get user bonuses
        user_bonuses = await bonus_service.get_user_bonuses(user.id, "COMPLETED")
        assert len(user_bonuses) == 2

        # Get stats
        stats = await bonus_service.get_bonus_stats(user.id)
        assert stats["total_credits_from_bonuses"] == 30
        assert stats["total_ai_credits_from_bonuses"] == 15

    @pytest.mark.asyncio
    async def test_inactive_bonus(
        self, async_session: AsyncSession, setup_bonus_types, unique_tg_id
    ):
        """Test that inactive bonuses cannot be claimed."""
        user_repo = UserRepository(async_session)
        bonus_repo = BonusRepository(async_session)
        bonus_service = BonusService(bonus_repo, user_repo)

        # Create user
        user = await user_repo.create(tg_id=unique_tg_id, username=f"inactive_test_{unique_tg_id}")
        await async_session.commit()

        # Deactivate first login bonus
        bonus_type = await bonus_repo.get_by_code("FIRST_LOGIN")
        bonus_type.is_active = False
        await async_session.commit()

        # Try to claim - should fail
        can_claim = await bonus_service.can_claim_bonus(user.id, "FIRST_LOGIN")
        assert can_claim is False

        with pytest.raises(BonusAlreadyClaimedError):
            await bonus_service.claim_bonus(user.id, "FIRST_LOGIN")
