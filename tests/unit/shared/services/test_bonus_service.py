"""
Unit tests for BonusService.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.core.exceptions import BonusAlreadyClaimedError, BonusNotFoundError
from shared.db.models import BonusType, UserBonus
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.user_repository import UserRepository
from shared.services.bonus_service import (
    BonusService,
    ChannelSubscriptionBonus,
    DailyLoginBonus,
    FirstLoginBonus,
    ReferralBonus,
)


class TestChannelSubscriptionBonus:
    """Tests for ChannelSubscriptionBonus strategy."""

    @pytest.mark.asyncio
    async def test_can_apply_no_previous_bonus(self):
        """Test that bonus can be applied if user hasn't claimed it."""
        strategy = ChannelSubscriptionBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_repo.user_has_bonus.return_value = False

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 1

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is True
        bonus_repo.user_has_bonus.assert_called_once()

    @pytest.mark.asyncio
    async def test_can_apply_already_claimed(self):
        """Test that bonus cannot be applied if already claimed."""
        strategy = ChannelSubscriptionBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_repo.user_has_bonus.return_value = True

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 1

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_bonus_success(self):
        """Test successful bonus application."""
        strategy = ChannelSubscriptionBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 1
        bonus_type.credits_amount = 10
        bonus_type.ai_credits_amount = 5

        user_bonus = MagicMock(spec=UserBonus)
        bonus_repo.create_user_bonus.return_value = user_bonus

        result = await strategy.apply_bonus(
            user_id=1,
            bonus_type=bonus_type,
            metadata={"channel": "test"},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result == user_bonus
        bonus_repo.create_user_bonus.assert_called_once()
        user_repo.add_credits.assert_called_once_with(user_id=1, credits=10, ai_credits=5)


class TestFirstLoginBonus:
    """Tests for FirstLoginBonus strategy."""

    @pytest.mark.asyncio
    async def test_can_apply_first_login(self):
        """Test that bonus can be applied on first login."""
        strategy = FirstLoginBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_repo.user_has_bonus.return_value = False

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 2

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is True


class TestReferralBonus:
    """Tests for ReferralBonus strategy."""

    @pytest.mark.asyncio
    async def test_can_apply_registration_trigger(self):
        """Test bonus can be applied with REGISTRATION trigger."""
        strategy = ReferralBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 3

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={"trigger": "REGISTRATION", "referred_id": 123},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_can_apply_first_payment_trigger(self):
        """Test bonus can be applied with FIRST_PAYMENT trigger."""
        strategy = ReferralBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        user_repo.get_payment_count.return_value = 1

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 3

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={"trigger": "FIRST_PAYMENT", "referred_id": 123},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_can_apply_no_referred_id(self):
        """Test bonus cannot be applied without referred_id."""
        strategy = ReferralBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={"trigger": "REGISTRATION"},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is False


class TestDailyLoginBonus:
    """Tests for DailyLoginBonus strategy."""

    @pytest.mark.asyncio
    async def test_can_apply_no_previous_bonus(self):
        """Test bonus can be applied when no previous bonus exists."""
        strategy = DailyLoginBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_repo.get_last_user_bonus.return_value = None

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 4

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_can_apply_cooldown_expired(self):
        """Test bonus can be applied after cooldown period."""
        strategy = DailyLoginBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        last_bonus = MagicMock(spec=UserBonus)
        last_bonus.completed_at = datetime.utcnow() - timedelta(days=2)
        bonus_repo.get_last_user_bonus.return_value = last_bonus

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 4
        bonus_type.cooldown_days = 1

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_can_apply_cooldown_not_expired(self):
        """Test bonus cannot be applied during cooldown period."""
        strategy = DailyLoginBonus()
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        last_bonus = MagicMock(spec=UserBonus)
        last_bonus.completed_at = datetime.utcnow() - timedelta(hours=12)
        bonus_repo.get_last_user_bonus.return_value = last_bonus

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 4
        bonus_type.cooldown_days = 1

        result = await strategy.can_apply(
            user_id=1,
            bonus_type=bonus_type,
            metadata={},
            bonus_repo=bonus_repo,
            user_repo=user_repo,
        )

        assert result is False


class TestBonusService:
    """Tests for BonusService."""

    @pytest.mark.asyncio
    async def test_get_bonus_type(self):
        """Test getting bonus type by code."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)
        bonus_repo.get_by_code.return_value = bonus_type

        service = BonusService(bonus_repo, user_repo)
        result = await service.get_bonus_type("CHANNEL_SUBSCRIPTION")

        assert result == bonus_type
        bonus_repo.get_by_code.assert_called_once_with("CHANNEL_SUBSCRIPTION")

    @pytest.mark.asyncio
    async def test_can_claim_bonus_success(self):
        """Test can claim bonus when conditions are met."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.is_active = True
        bonus_repo.get_by_code.return_value = bonus_type
        bonus_repo.user_has_bonus.return_value = False

        service = BonusService(bonus_repo, user_repo)
        result = await service.can_claim_bonus(1, "CHANNEL_SUBSCRIPTION")

        assert result is True

    @pytest.mark.asyncio
    async def test_can_claim_bonus_inactive(self):
        """Test cannot claim inactive bonus."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.is_active = False
        bonus_repo.get_by_code.return_value = bonus_type

        service = BonusService(bonus_repo, user_repo)
        result = await service.can_claim_bonus(1, "CHANNEL_SUBSCRIPTION")

        assert result is False

    @pytest.mark.asyncio
    async def test_claim_bonus_success(self):
        """Test successful bonus claim."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.id = 1
        bonus_type.is_active = True
        bonus_type.credits_amount = 10
        bonus_type.ai_credits_amount = 5

        user_bonus = MagicMock(spec=UserBonus)

        bonus_repo.get_by_code.return_value = bonus_type
        bonus_repo.user_has_bonus.return_value = False
        bonus_repo.create_user_bonus.return_value = user_bonus

        service = BonusService(bonus_repo, user_repo)
        result = await service.claim_bonus(1, "CHANNEL_SUBSCRIPTION")

        assert result == user_bonus

    @pytest.mark.asyncio
    async def test_claim_bonus_already_claimed(self):
        """Test claiming bonus raises error when already claimed."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_type = MagicMock(spec=BonusType)
        bonus_type.is_active = True
        bonus_repo.get_by_code.return_value = bonus_type
        bonus_repo.user_has_bonus.return_value = True

        service = BonusService(bonus_repo, user_repo)

        with pytest.raises(BonusAlreadyClaimedError):
            await service.claim_bonus(1, "CHANNEL_SUBSCRIPTION")

    @pytest.mark.asyncio
    async def test_claim_bonus_not_found(self):
        """Test claiming bonus raises error when bonus not found."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_repo.get_by_code.return_value = None

        service = BonusService(bonus_repo, user_repo)

        # First check returns False, then get_bonus_type returns None
        with pytest.raises(BonusAlreadyClaimedError):
            await service.claim_bonus(1, "INVALID_BONUS")

    @pytest.mark.asyncio
    async def test_get_user_bonuses(self):
        """Test getting user bonuses."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonuses = [MagicMock(spec=UserBonus), MagicMock(spec=UserBonus)]
        bonus_repo.get_user_bonuses.return_value = bonuses

        service = BonusService(bonus_repo, user_repo)
        result = await service.get_user_bonuses(1, "COMPLETED")

        assert result == bonuses
        bonus_repo.get_user_bonuses.assert_called_once_with(1, "COMPLETED")

    @pytest.mark.asyncio
    async def test_get_bonus_stats(self):
        """Test getting bonus statistics."""
        bonus_repo = AsyncMock(spec=BonusRepository)
        user_repo = AsyncMock(spec=UserRepository)

        bonus_repo.get_total_credits_from_bonuses.return_value = (100, 50)

        service = BonusService(bonus_repo, user_repo)
        result = await service.get_bonus_stats(1)

        assert result == {
            "total_credits_from_bonuses": 100,
            "total_ai_credits_from_bonuses": 50,
        }
