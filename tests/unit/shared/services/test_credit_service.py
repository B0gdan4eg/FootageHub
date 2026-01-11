"""
Unit tests for CreditService.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.core.exceptions import (
    InsufficientAICreditsError,
    InsufficientCreditsError,
    UserNotFoundException,
)
from shared.db.models import User
from shared.db.repositories.user_repository import UserRepository
from shared.services.credit_service import CreditService


class TestCreditService:
    """Tests for CreditService."""

    @pytest.mark.asyncio
    async def test_add_credits_regular(self):
        """Test adding regular credits to user."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.add_credits(1, 25, "credits", "test")

        assert result == {"credits": 125, "ai_credits": 50}
        user_repo.add_credits.assert_called_once_with(user_id=1, credits=25, ai_credits=0)

    @pytest.mark.asyncio
    async def test_add_credits_ai(self):
        """Test adding AI credits to user."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.add_credits(1, 10, "ai_credits", "bonus")

        assert result == {"credits": 100, "ai_credits": 60}
        user_repo.add_credits.assert_called_once_with(user_id=1, credits=0, ai_credits=10)

    @pytest.mark.asyncio
    async def test_add_credits_both(self):
        """Test adding both types of credits."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.add_credits(1, 20, "both")

        assert result == {"credits": 120, "ai_credits": 70}
        user_repo.add_credits.assert_called_once_with(user_id=1, credits=20, ai_credits=20)

    @pytest.mark.asyncio
    async def test_add_credits_user_not_found(self):
        """Test adding credits raises error when user not found."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user_repo.get_by_id.return_value = None

        service = CreditService(session, user_repo)

        with pytest.raises(UserNotFoundException):
            await service.add_credits(999, 10)

    @pytest.mark.asyncio
    async def test_add_ai_credits(self):
        """Test adding AI credits convenience method."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.add_ai_credits(1, 15, "test")

        assert result == 65

    @pytest.mark.asyncio
    async def test_deduct_credits_success(self):
        """Test deducting credits successfully."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.deduct_credits(1, 30, "credits")

        assert result == {"credits": 70, "ai_credits": 50}
        user_repo.deduct_credits.assert_called_once_with(user_id=1, credits=30)

    @pytest.mark.asyncio
    async def test_deduct_credits_insufficient(self):
        """Test deducting credits raises error when insufficient."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 10
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)

        with pytest.raises(InsufficientCreditsError):
            await service.deduct_credits(1, 50, "credits")

    @pytest.mark.asyncio
    async def test_deduct_ai_credits_success(self):
        """Test deducting AI credits successfully."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.deduct_credits(1, 20, "ai_credits")

        assert result == {"credits": 100, "ai_credits": 30}
        user_repo.deduct_ai_credits.assert_called_once_with(user_id=1, ai_credits=20)

    @pytest.mark.asyncio
    async def test_deduct_ai_credits_insufficient(self):
        """Test deducting AI credits raises error when insufficient."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 5

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)

        with pytest.raises(InsufficientAICreditsError):
            await service.deduct_credits(1, 20, "ai_credits")

    @pytest.mark.asyncio
    async def test_refund_credits(self):
        """Test refunding credits."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.refund_credits(1, 25, "credits", "failed generation")

        assert result == {"credits": 125, "ai_credits": 50}

    @pytest.mark.asyncio
    async def test_refund_ai_credits(self):
        """Test refunding AI credits."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user
        user_repo.refund_ai_credits.return_value = None

        service = CreditService(session, user_repo)
        result = await service.refund_ai_credits(1, 10, "error")

        assert result == 50
        user_repo.refund_ai_credits.assert_called_once_with(user_id=1, ai_credits=10)

    @pytest.mark.asyncio
    async def test_get_balance(self):
        """Test getting user balance."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 1
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.get_balance(1)

        assert result == {"credits": 100, "ai_credits": 50}

    @pytest.mark.asyncio
    async def test_get_balance_user_not_found(self):
        """Test getting balance raises error when user not found."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user_repo.get_by_id.return_value = None

        service = CreditService(session, user_repo)

        with pytest.raises(UserNotFoundException):
            await service.get_balance(999)

    @pytest.mark.asyncio
    async def test_get_ai_credits_balance(self):
        """Test getting AI credits balance."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.get_ai_credits_balance(1)

        assert result == 50

    @pytest.mark.asyncio
    async def test_has_sufficient_credits_true(self):
        """Test has sufficient credits returns True."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.credits = 100
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.has_sufficient_credits(1, 50, "credits")

        assert result is True

    @pytest.mark.asyncio
    async def test_has_sufficient_credits_false(self):
        """Test has sufficient credits returns False."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.credits = 30
        user.ai_credits = 50

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.has_sufficient_credits(1, 50, "credits")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_usage_stats(self):
        """Test getting usage statistics."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user = MagicMock(spec=User)
        user.credits = 100
        user.ai_credits = 50
        user.ai_credits_used = 25

        user_repo.get_by_id.return_value = user

        service = CreditService(session, user_repo)
        result = await service.get_usage_stats(1)

        assert result == {
            "credits": {"current": 100, "used": 0},
            "ai_credits": {"current": 50, "used": 25},
        }

    @pytest.mark.asyncio
    async def test_transfer_credits(self):
        """Test transferring credits between users."""
        user_repo = AsyncMock(spec=UserRepository)
        session = AsyncMock()

        user1 = MagicMock(spec=User)
        user1.id = 1
        user1.credits = 100
        user1.ai_credits = 50

        user2 = MagicMock(spec=User)
        user2.id = 2
        user2.credits = 50
        user2.ai_credits = 25

        user_repo.get_by_id.side_effect = [user1, user1, user2]

        service = CreditService(session, user_repo)
        result = await service.transfer_credits(1, 2, 20, "credits")

        assert result["from_user_id"] == 1
        assert result["to_user_id"] == 2
        assert result["amount"] == 20
        assert result["credit_type"] == "credits"
