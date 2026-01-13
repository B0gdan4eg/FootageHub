"""
Integration tests for AI Bot generation flow.

Tests the complete AI generation workflow including credits management.
"""

import random

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_bot.services.credit_manager import CreditManager
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.user_repository import UserRepository
from shared.services.credit_service import CreditService


@pytest.fixture
def unique_tg_id():
    """Generate unique telegram ID for each test."""
    import time

    # Use timestamp + random to ensure uniqueness
    return int(time.time() * 1000) + random.randint(0, 999)


@pytest.fixture
def unique_referral_code():
    """Generate unique referral code for each test."""
    import time

    # Use timestamp + random to ensure uniqueness
    return f"REF{int(time.time() * 1000) % 1000000}{random.randint(0, 999)}"


class TestAIBotGenerationFlow:
    """Integration tests for AI generation flow."""

    @pytest.mark.asyncio
    async def test_ai_credits_deduction_flow(
        self, async_session: AsyncSession, unique_tg_id, unique_referral_code
    ):
        """Test that AI credits are properly deducted during generation."""
        # Setup repositories and services
        user_repo = UserRepository(async_session)
        BonusRepository(async_session)
        credit_service = CreditService(async_session, user_repo)

        # Create user with AI credits
        user = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"ai_user_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        await async_session.commit()

        # Add AI credits
        await credit_service.add_ai_credits(user.id, 100, "initial credits")
        await async_session.commit()

        # Verify initial balance
        balance = await credit_service.get_ai_credits_balance(user.id)
        assert balance == 100

        # Simulate AI generation cost (10 credits)
        await credit_service.deduct_ai_credits(user.id, 10, "image generation")
        await async_session.commit()

        # Verify credits were deducted
        await async_session.refresh(user)
        assert user.ai_credits == 90
        assert user.ai_credits_used == 10

    @pytest.mark.asyncio
    async def test_ai_credits_refund_on_failure(
        self, async_session: AsyncSession, unique_tg_id, unique_referral_code
    ):
        """Test that AI credits are refunded when generation fails."""
        user_repo = UserRepository(async_session)
        credit_service = CreditService(async_session, user_repo)

        # Create user
        user = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"refund_user_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        await async_session.commit()

        # Add AI credits
        await credit_service.add_ai_credits(user.id, 50)
        await async_session.commit()

        # Deduct for generation
        await credit_service.deduct_ai_credits(user.id, 15, "video generation")
        await async_session.commit()

        assert user.ai_credits == 35
        assert user.ai_credits_used == 15

        # Refund on failure
        await credit_service.refund_ai_credits(user.id, 15, "generation failed")
        await async_session.commit()

        # Verify refund
        await async_session.refresh(user)
        assert user.ai_credits == 50
        assert user.ai_credits_used == 0

    @pytest.mark.asyncio
    async def test_insufficient_ai_credits(
        self, async_session: AsyncSession, unique_tg_id, unique_referral_code
    ):
        """Test that generation fails with insufficient AI credits."""
        from shared.core.exceptions import InsufficientAICreditsError

        user_repo = UserRepository(async_session)
        credit_service = CreditService(async_session, user_repo)

        # Create user with low credits
        user = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"poor_user_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        await async_session.commit()

        await credit_service.add_ai_credits(user.id, 5)
        await async_session.commit()

        # Try to deduct more than available
        with pytest.raises(InsufficientAICreditsError):
            await credit_service.deduct_ai_credits(user.id, 20, "expensive generation")

    @pytest.mark.asyncio
    async def test_ai_credits_usage_tracking(
        self, async_session: AsyncSession, unique_tg_id, unique_referral_code
    ):
        """Test tracking AI credits usage over time."""
        user_repo = UserRepository(async_session)
        credit_service = CreditService(async_session, user_repo)

        # Create user
        user = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"tracker_user_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        await async_session.commit()

        # Add credits
        await credit_service.add_ai_credits(user.id, 100)
        await async_session.commit()

        # Perform multiple generations
        await credit_service.deduct_ai_credits(user.id, 10, "gen 1")
        await credit_service.deduct_ai_credits(user.id, 15, "gen 2")
        await credit_service.deduct_ai_credits(user.id, 20, "gen 3")
        await async_session.commit()

        # Verify total usage
        await async_session.refresh(user)
        assert user.ai_credits == 55  # 100 - 10 - 15 - 20
        assert user.ai_credits_used == 45  # 10 + 15 + 20

        # Get usage stats
        stats = await credit_service.get_usage_stats(user.id)
        assert stats["ai_credits"]["current"] == 55
        assert stats["ai_credits"]["used"] == 45

    @pytest.mark.asyncio
    async def test_credit_manager_has_sufficient_credits(
        self, async_session: AsyncSession, unique_tg_id, unique_referral_code
    ):
        """Test CreditManager checking sufficient credits."""
        user_repo = UserRepository(async_session)
        credit_service = CreditService(async_session, user_repo)
        credit_manager = CreditManager(async_session, user_repo, credit_service)

        # Create user with credits
        user = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"check_user_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        await async_session.commit()

        await credit_service.add_ai_credits(user.id, 50)
        await async_session.commit()

        # Check sufficient credits
        has_credits = await credit_manager.has_sufficient_credits(user.id, required_credits=30)
        assert has_credits is True

        # Check insufficient credits
        has_credits = await credit_manager.has_sufficient_credits(user.id, required_credits=100)
        assert has_credits is False

    @pytest.mark.asyncio
    async def test_complete_ai_generation_flow(
        self, async_session: AsyncSession, unique_tg_id, unique_referral_code
    ):
        """Test complete AI generation flow from start to finish."""
        user_repo = UserRepository(async_session)
        credit_service = CreditService(async_session, user_repo)
        credit_manager = CreditManager(async_session, user_repo, credit_service)

        # Create user
        user = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"gen_user_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        await async_session.commit()

        # Add initial AI credits
        await credit_service.add_ai_credits(user.id, 100, "initial")
        await async_session.commit()

        initial_balance = await credit_service.get_ai_credits_balance(user.id)
        assert initial_balance == 100

        # Check if user has sufficient credits for generation
        generation_cost = 15
        has_credits = await credit_manager.has_sufficient_credits(user.id, generation_cost)
        assert has_credits is True

        # Deduct credits for generation (using CreditService directly)
        await credit_service.deduct_ai_credits(user.id, generation_cost, "image generation")
        await async_session.commit()

        # Verify deduction
        new_balance = await credit_service.get_ai_credits_balance(user.id)
        assert new_balance == 85

        # Simulate successful generation - no refund needed

        # Get final stats
        stats = await credit_service.get_usage_stats(user.id)
        assert stats["ai_credits"]["current"] == 85
        assert stats["ai_credits"]["used"] == 15

    @pytest.mark.asyncio
    async def test_multiple_users_concurrent_credits(
        self, async_session: AsyncSession, unique_tg_id, unique_referral_code
    ):
        """Test multiple users using AI credits concurrently."""
        user_repo = UserRepository(async_session)
        credit_service = CreditService(async_session, user_repo)

        # Create multiple users
        user1 = await user_repo.create(
            tg_id=unique_tg_id,
            username=f"user1_{unique_tg_id}",
            referral_code=unique_referral_code,
        )
        user2 = await user_repo.create(
            tg_id=unique_tg_id + 1,
            username=f"user2_{unique_tg_id + 1}",
            referral_code=f"{unique_referral_code}X",
        )
        user3 = await user_repo.create(
            tg_id=unique_tg_id + 2,
            username=f"user3_{unique_tg_id + 2}",
            referral_code=f"{unique_referral_code}Y",
        )
        await async_session.commit()

        # Add credits to all
        await credit_service.add_ai_credits(user1.id, 50)
        await credit_service.add_ai_credits(user2.id, 75)
        await credit_service.add_ai_credits(user3.id, 100)
        await async_session.commit()

        # All users perform generations
        await credit_service.deduct_ai_credits(user1.id, 20, "gen")
        await credit_service.deduct_ai_credits(user2.id, 30, "gen")
        await credit_service.deduct_ai_credits(user3.id, 40, "gen")
        await async_session.commit()

        # Verify balances
        await async_session.refresh(user1)
        await async_session.refresh(user2)
        await async_session.refresh(user3)

        assert user1.ai_credits == 30
        assert user2.ai_credits == 45
        assert user3.ai_credits == 60
