"""
Unit тесты для ReferralService.

Тестируем:
- Создание реферальных связей
- Триггеры наград (регистрация, первая покупка, подписка)
- Milestone награды
- Статистику рефералов
"""

from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.core.constants import BonusCodes, ReferralRewards
from shared.core.exceptions import BonusException, ReferralException, UserNotFoundException
from shared.db.models import (
    ReferralReward,
    ReferralRewardStatus,
    ReferralTriggerType,
    User,
    UserBonus,
)
from shared.services.referral_service import ReferralService


def create_mock_scalar_result(value):
    """Create mock for session.execute().scalar_one_or_none()"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


def create_mock_scalars_result(data):
    """Create mock for session.execute().scalars().all()"""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = data
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


@pytest.fixture
def mock_session():
    """Mock AsyncSession"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_user_repo():
    """Mock UserRepository"""
    return AsyncMock()


@pytest.fixture
def mock_bonus_repo():
    """Mock BonusRepository"""
    return AsyncMock()


@pytest.fixture
def mock_bonus_service():
    """Mock BonusService"""
    return AsyncMock()


@pytest.fixture
def referral_service(mock_session, mock_user_repo, mock_bonus_repo, mock_bonus_service):
    """Экземпляр ReferralService с моками"""
    return ReferralService(
        session=mock_session,
        user_repo=mock_user_repo,
        bonus_repo=mock_bonus_repo,
        bonus_service=mock_bonus_service,
    )


# ==================== ТЕСТЫ СОЗДАНИЯ РЕФЕРАЛЬНОЙ СВЯЗИ ====================


@pytest.mark.asyncio
async def test_create_referral_registration_success(
    referral_service, mock_user_repo, mock_bonus_service, mock_session
):
    """Тест успешного создания реферальной связи"""
    # Arrange
    referrer_id, referred_id = 1, 2
    referrer = MagicMock(id=referrer_id, tg_id=111)
    referred = MagicMock(id=referred_id, tg_id=222)

    mock_user_repo.get_by_id.side_effect = [referrer, referred]

    # Mock: реферальной связи еще нет
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))

    # Mock: бонус успешно начислен
    user_bonus = MagicMock(id=10, user_id=referrer_id, credits_granted=50)
    mock_bonus_service.claim_bonus.return_value = user_bonus

    # Act
    referral_reward = await referral_service.create_referral_registration(referrer_id, referred_id)

    # Assert
    assert referral_reward.referrer_id == referrer_id
    assert referral_reward.referred_id == referred_id
    assert referral_reward.reward_type == "credits"
    assert referral_reward.reward_value == ReferralRewards.REGISTRATION_CREDITS
    assert referral_reward.status == ReferralRewardStatus.PENDING
    assert referral_reward.trigger_type == ReferralTriggerType.REGISTRATION
    assert referral_reward.condition_met is True

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called()


@pytest.mark.asyncio
async def test_create_referral_registration_referrer_not_found(referral_service, mock_user_repo):
    """Тест создания реферальной связи - реферер не найден"""
    # Arrange
    mock_user_repo.get_by_id.side_effect = [None, None]

    # Act & Assert
    with pytest.raises(UserNotFoundException, match="Referrer .* not found"):
        await referral_service.create_referral_registration(referrer_id=1, referred_id=2)


@pytest.mark.asyncio
async def test_create_referral_registration_referred_not_found(referral_service, mock_user_repo):
    """Тест создания реферальной связи - реферал не найден"""
    # Arrange
    referrer = MagicMock(id=1, tg_id=111)
    mock_user_repo.get_by_id.side_effect = [referrer, None]

    # Act & Assert
    with pytest.raises(UserNotFoundException, match="Referred .* not found"):
        await referral_service.create_referral_registration(referrer_id=1, referred_id=2)


@pytest.mark.asyncio
async def test_create_referral_registration_already_exists(
    referral_service, mock_user_repo, mock_session
):
    """Тест создания реферальной связи - связь уже существует"""
    # Arrange
    referrer = MagicMock(id=1, tg_id=111)
    referred = MagicMock(id=2, tg_id=222)
    mock_user_repo.get_by_id.side_effect = [referrer, referred]

    # Mock: реферальная связь уже существует
    existing_reward = MagicMock(id=5, referrer_id=1, referred_id=2)
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(existing_reward))

    # Act & Assert
    with pytest.raises(ReferralException, match="already exists"):
        await referral_service.create_referral_registration(referrer_id=1, referred_id=2)


@pytest.mark.asyncio
async def test_create_referral_registration_bonus_fails_gracefully(
    referral_service, mock_user_repo, mock_bonus_service, mock_session
):
    """Тест создания реферальной связи - бонус не удалось начислить, но связь создается"""
    # Arrange
    referrer = MagicMock(id=1, tg_id=111)
    referred = MagicMock(id=2, tg_id=222)
    mock_user_repo.get_by_id.side_effect = [referrer, referred]

    # Mock: реферальной связи нет
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))

    # Mock: бонус не удалось начислить
    mock_bonus_service.claim_bonus.side_effect = BonusException("Already claimed")

    # Act
    referral_reward = await referral_service.create_referral_registration(
        referrer_id=1, referred_id=2
    )

    # Assert - связь создается, несмотря на ошибку бонуса
    assert referral_reward.referrer_id == 1
    assert referral_reward.referred_id == 2
    mock_session.add.assert_called_once()


# ==================== ТЕСТЫ ТРИГГЕРА ПЕРВОЙ ПОКУПКИ ====================


@pytest.mark.asyncio
async def test_trigger_first_payment_success(
    referral_service, mock_user_repo, mock_bonus_service, mock_session
):
    """Тест триггера первой покупки реферала"""
    # Arrange
    user_id, referrer_id = 2, 1
    payment_amount, payment_id = 100.0, 50

    # Mock: найдена реферальная связь
    referral_reward = MagicMock(id=10, referrer_id=referrer_id, referred_id=user_id)
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(referral_reward))

    # Mock: это первая покупка
    mock_user_repo.get_payment_count.return_value = 1

    # Mock: бонус начислен
    user_bonus = MagicMock(id=20, user_id=referrer_id, credits_granted=100)
    mock_bonus_service.claim_bonus.return_value = user_bonus

    # Act
    result = await referral_service.trigger_first_payment(
        user_id=user_id, payment_amount=payment_amount, payment_id=payment_id
    )

    # Assert
    assert result is not None
    assert result.user_id == referrer_id
    mock_bonus_service.claim_bonus.assert_called_once()
    mock_session.add.assert_called()
    mock_session.flush.assert_called()


@pytest.mark.asyncio
async def test_trigger_first_payment_no_referral(referral_service, mock_session):
    """Тест триггера первой покупки - нет реферальной связи"""
    # Arrange
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))

    # Act
    result = await referral_service.trigger_first_payment(
        user_id=2, payment_amount=100.0, payment_id=50
    )

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_trigger_first_payment_not_first(referral_service, mock_user_repo, mock_session):
    """Тест триггера первой покупки - уже не первая покупка"""
    # Arrange
    referral_reward = MagicMock(id=10, referrer_id=1, referred_id=2)
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(referral_reward))

    # Mock: уже 2+ покупок
    mock_user_repo.get_payment_count.return_value = 2

    # Act
    result = await referral_service.trigger_first_payment(
        user_id=2, payment_amount=100.0, payment_id=50
    )

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_trigger_first_payment_bonus_fails(
    referral_service, mock_user_repo, mock_bonus_service, mock_session
):
    """Тест триггера первой покупки - бонус не удалось начислить"""
    # Arrange
    referral_reward = MagicMock(id=10, referrer_id=1, referred_id=2)
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(referral_reward))

    mock_user_repo.get_payment_count.return_value = 1
    mock_bonus_service.claim_bonus.side_effect = BonusException("Failed")

    # Act
    result = await referral_service.trigger_first_payment(
        user_id=2, payment_amount=100.0, payment_id=50
    )

    # Assert
    assert result is None


# ==================== ТЕСТЫ ТРИГГЕРА ПОДПИСКИ ====================


@pytest.mark.asyncio
async def test_trigger_subscription_success(referral_service, mock_session):
    """Тест триггера покупки подписки рефералом"""
    # Arrange
    referral_reward = MagicMock(id=10, referrer_id=1, referred_id=2)
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(referral_reward))

    # Act
    result = await referral_service.trigger_subscription(
        user_id=2, subscription_id=100, subscription_type="MONTHLY"
    )

    # Assert
    # Пока возвращает None (функционал не реализован полностью)
    assert result is None
    mock_session.add.assert_called()
    mock_session.flush.assert_called()


@pytest.mark.asyncio
async def test_trigger_subscription_no_referral(referral_service, mock_session):
    """Тест триггера подписки - нет реферальной связи"""
    # Arrange
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))

    # Act
    result = await referral_service.trigger_subscription(
        user_id=2, subscription_id=100, subscription_type="MONTHLY"
    )

    # Assert
    assert result is None


# ==================== ТЕСТЫ MILESTONE НАГРАД ====================


@pytest.mark.asyncio
async def test_check_milestone_rewards_5_referrals(referral_service, mock_user_repo, mock_session):
    """Тест milestone награды за 5 рефералов"""
    # Arrange
    referrer_id = 1
    mock_user_repo.get_referral_count.return_value = 5

    # Mock: milestone награды еще нет
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(None))

    # Act
    bonuses = await referral_service.check_milestone_rewards(referrer_id)

    # Assert
    assert isinstance(bonuses, list)
    mock_session.add.assert_called()
    mock_session.flush.assert_called()


@pytest.mark.asyncio
async def test_check_milestone_rewards_already_received(
    referral_service, mock_user_repo, mock_session
):
    """Тест milestone награды - уже получена"""
    # Arrange
    referrer_id = 1
    mock_user_repo.get_referral_count.return_value = 5

    # Mock: milestone награда уже существует
    existing_milestone = MagicMock(id=50, referrer_id=referrer_id)
    # Mock: query result
    mock_session.execute = AsyncMock(return_value=create_mock_scalar_result(existing_milestone))

    # Act
    bonuses = await referral_service.check_milestone_rewards(referrer_id)

    # Assert
    assert bonuses == []


@pytest.mark.asyncio
async def test_check_milestone_rewards_no_milestone(referral_service, mock_user_repo):
    """Тест milestone наград - количество рефералов не является milestone"""
    # Arrange
    referrer_id = 1
    mock_user_repo.get_referral_count.return_value = 7  # Не milestone

    # Act
    bonuses = await referral_service.check_milestone_rewards(referrer_id)

    # Assert
    assert bonuses == []


# ==================== ТЕСТЫ СТАТИСТИКИ ====================


@pytest.mark.asyncio
async def test_get_referral_stats(referral_service, mock_user_repo, mock_bonus_repo, mock_session):
    """Тест получения статистики рефералов"""
    # Arrange
    user_id = 1
    mock_user_repo.get_referral_count.return_value = 10

    # Mock: 5 активных рефералов
    mock_result_active = MagicMock()
    mock_result_active.scalar.return_value = 5

    # Mock: список рефералов
    referrals = [
        MagicMock(id=1, referrer_id=user_id, referred_id=2),
        MagicMock(id=2, referrer_id=user_id, referred_id=3),
    ]
    mock_result_list = create_mock_scalars_result(referrals)

    mock_session.execute.side_effect = [mock_result_active, mock_result_list]

    # Mock: всего заработано бонусов
    mock_bonus_repo.get_total_credits_from_bonuses.return_value = {
        "credits": 500,
        "ai_credits": 100,
    }

    # Act
    stats = await referral_service.get_referral_stats(user_id)

    # Assert
    assert stats["total_referrals"] == 10
    assert stats["active_referrals"] == 5
    assert stats["total_credits_earned"] == 500
    assert stats["total_ai_credits_earned"] == 100
    assert len(stats["referrals"]) == 2


@pytest.mark.asyncio
async def test_get_user_referral_rewards(referral_service, mock_session):
    """Тест получения списка реферальных наград"""
    # Arrange
    user_id = 1
    rewards_data = [
        MagicMock(id=1, referrer_id=user_id),
        MagicMock(id=2, referrer_id=user_id),
        MagicMock(id=3, referrer_id=user_id),
    ]
    mock_session.execute = AsyncMock(return_value=create_mock_scalars_result(rewards_data))

    # Act
    rewards = await referral_service.get_user_referral_rewards(user_id, limit=10)

    # Assert
    assert len(rewards) == 3
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_referral_rewards_with_limit(referral_service, mock_session):
    """Тест получения списка реферальных наград с лимитом"""
    # Arrange
    user_id = 1
    limit = 5
    rewards_data = [MagicMock(id=i, referrer_id=user_id) for i in range(1, 6)]
    mock_session.execute = AsyncMock(return_value=create_mock_scalars_result(rewards_data))

    # Act
    rewards = await referral_service.get_user_referral_rewards(user_id, limit=limit)

    # Assert
    assert len(rewards) == 5
