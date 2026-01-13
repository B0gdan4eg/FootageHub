"""
Unit tests for UserRepository.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.core.exceptions import (
    InsufficientAICreditsError,
    InsufficientCreditsError,
    UserNotFoundError,
)
from shared.db.models import User
from shared.db.repositories.user_repository import UserRepository


def create_mock_scalar_result(value):
    """Create mock for session.execute().scalar_one_or_none()"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


def create_mock_execute_result(data):
    """Create mock for session.execute().scalars().all()"""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = data
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


class TestUserRepository:
    """Tests for UserRepository."""

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Test creating a new user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        # Mock commit and refresh
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Call create from base repository
        result = await repo.create(
            tg_id=123456,
            username="testuser",
            referral_code="ABC123",
        )

        # Verify session interactions
        assert mock_session.add.called
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_get_by_telegram_id(self):
        """Test getting user by Telegram ID."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=999888, username="user1")

        # Mock execute result
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))

        result = await repo.get_by_telegram_id(999888)

        assert result == user
        assert result.tg_id == 999888
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_telegram_id_not_found(self):
        """Test getting user by Telegram ID that doesn't exist."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        # Mock execute result (not found)
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))

        result = await repo.get_by_telegram_id(999999999)

        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_referral_code(self):
        """Test getting user by referral code."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=111222, username="user2", referral_code="REF123")

        # Mock execute result
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))

        result = await repo.get_by_referral_code("REF123")

        assert result == user
        assert result.referral_code == "REF123"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_by_telegram_id_existing(self):
        """Test get_or_create returns existing user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        existing_user = User(id=1, tg_id=333444, username="existing")

        # Mock get_by_telegram_id to return existing user
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(existing_user))

        result = await repo.get_or_create_by_telegram_id(333444, "different_name")

        assert result == existing_user
        assert result.username == "existing"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_by_telegram_id_new(self):
        """Test get_or_create creates new user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        # Mock get_by_telegram_id to return None (user doesn't exist)
        # Then mock create
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        await repo.get_or_create_by_telegram_id(555666, "newuser", "NEWREF")

        # Verify create was called
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_credits(self):
        """Test adding credits to user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=777888, credits=0, ai_credits=0)

        # Mock get_by_id
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await repo.add_credits(user.id, credits=50, ai_credits=25)

        assert user.credits == 50
        assert user.ai_credits == 25
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_credits_user_not_found(self):
        """Test adding credits raises error when user not found."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        # Mock get_by_id to return None
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))

        with pytest.raises(UserNotFoundError):
            await repo.add_credits(999999, credits=10)

    @pytest.mark.asyncio
    async def test_deduct_credits(self):
        """Test deducting credits from user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=888999, credits=100, ai_credits=0)

        # Mock get_by_id
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await repo.deduct_credits(user.id, credits=30)

        assert user.credits == 70
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_deduct_credits_insufficient(self):
        """Test deducting credits raises error when insufficient."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=111000, credits=10, ai_credits=0)

        # Mock get_by_id
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))

        with pytest.raises(InsufficientCreditsError):
            await repo.deduct_credits(user.id, credits=50)

    @pytest.mark.asyncio
    async def test_deduct_ai_credits(self):
        """Test deducting AI credits from user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=222000, credits=0, ai_credits=50, ai_credits_used=0)

        # Mock get_by_id
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await repo.deduct_ai_credits(user.id, ai_credits=20)

        assert user.ai_credits == 30
        assert user.ai_credits_used == 20
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_deduct_ai_credits_insufficient(self):
        """Test deducting AI credits raises error when insufficient."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=333000, credits=0, ai_credits=5, ai_credits_used=0)

        # Mock get_by_id
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))

        with pytest.raises(InsufficientAICreditsError):
            await repo.deduct_ai_credits(user.id, ai_credits=20)

    @pytest.mark.asyncio
    async def test_refund_ai_credits(self):
        """Test refunding AI credits to user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=444000, credits=0, ai_credits=20, ai_credits_used=30)

        # Mock get_by_id
        mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(user))
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await repo.refund_ai_credits(user.id, ai_credits=10)

        assert user.ai_credits == 30  # 20 + 10
        assert user.ai_credits_used == 20  # 30 - 10
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_referral_count(self):
        """Test getting referral count for user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        user = User(id=1, tg_id=555000)

        # Mock get_by_id to return user
        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        # First call returns user, second call returns count
        mock_session.execute = AsyncMock(
            side_effect=[
                create_mock_scalar_result(user),  # get_by_id
                mock_count_result,  # count query
            ]
        )

        count = await repo.get_referral_count(1)

        assert count == 5
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_has_any_payment(self):
        """Test checking if user has any payments."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        # Mock execute result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1  # Has payment
        mock_session.execute = AsyncMock(return_value=mock_result)

        has_payment = await repo.has_any_payment(1)

        assert has_payment is True
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_payment_count(self):
        """Test getting payment count for user."""
        mock_session = AsyncMock()
        repo = UserRepository(mock_session)

        # Mock execute result for count
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        mock_session.execute = AsyncMock(return_value=mock_result)

        count = await repo.get_payment_count(1)

        assert count == 3
        mock_session.execute.assert_called_once()
