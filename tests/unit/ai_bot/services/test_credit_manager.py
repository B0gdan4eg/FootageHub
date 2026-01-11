"""
Unit тесты для CreditManager.

Тестируем:
- Получение баланса AI кредитов
- Проверку достаточности кредитов
- Списание кредитов
- Добавление кредитов
- Возврат кредитов
- Получение статистики
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_bot.services.credit_manager import CreditManager


def create_mock_scalar_result(value):
    """Создает мок для session.execute().scalar_one_or_none()"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


def create_mock_first_result(value):
    """Создает мок для session.execute().first()"""
    mock_result = MagicMock()
    mock_result.first.return_value = value
    return mock_result


@pytest.fixture
def mock_session():
    """Mock AsyncSession"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_user_repo():
    """Mock UserRepository"""
    return AsyncMock()


@pytest.fixture
def mock_credit_service():
    """Mock CreditService"""
    return AsyncMock()


@pytest.fixture
def credit_manager(mock_session):
    """Экземпляр CreditManager с базовыми моками"""
    return CreditManager(session=mock_session)


@pytest.fixture
def credit_manager_with_services(mock_session, mock_user_repo, mock_credit_service):
    """Экземпляр CreditManager со всеми сервисами"""
    return CreditManager(
        session=mock_session,
        user_repo=mock_user_repo,
        credit_service=mock_credit_service,
    )


# ==================== ТЕСТЫ GET_USER_CREDITS ====================


@pytest.mark.asyncio
async def test_get_user_credits_success(credit_manager, mock_session):
    """Тест успешного получения баланса AI кредитов"""
    # Arrange
    user_id = 123456
    expected_credits = 100
    mock_session.execute.return_value = create_mock_scalar_result(expected_credits)

    # Act
    credits = await credit_manager.get_user_credits(user_id)

    # Assert
    assert credits == expected_credits
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_credits_user_not_found(credit_manager, mock_session):
    """Тест получения кредитов - пользователь не найден"""
    # Arrange
    user_id = 999999
    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act
    credits = await credit_manager.get_user_credits(user_id)

    # Assert
    assert credits is None


@pytest.mark.asyncio
async def test_get_user_credits_zero_balance(credit_manager, mock_session):
    """Тест получения кредитов - нулевой баланс"""
    # Arrange
    user_id = 123456

    mock_session.execute.return_value = create_mock_scalar_result(0)

    # Act
    credits = await credit_manager.get_user_credits(user_id)

    # Assert
    assert credits == 0


# ==================== ТЕСТЫ HAS_ENOUGH_CREDITS ====================


@pytest.mark.asyncio
async def test_has_enough_credits_true(credit_manager, mock_session):
    """Тест проверки кредитов - достаточно"""
    # Arrange
    user_id = 123456
    required = 50

    mock_session.execute.return_value = create_mock_scalar_result(100)

    # Act
    result = await credit_manager.has_enough_credits(user_id, required)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_has_enough_credits_false(credit_manager, mock_session):
    """Тест проверки кредитов - недостаточно"""
    # Arrange
    user_id = 123456
    required = 150

    mock_session.execute.return_value = create_mock_scalar_result(100)

    # Act
    result = await credit_manager.has_enough_credits(user_id, required)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_has_enough_credits_exact_amount(credit_manager, mock_session):
    """Тест проверки кредитов - точное совпадение"""
    # Arrange
    user_id = 123456
    required = 100

    mock_session.execute.return_value = create_mock_scalar_result(100)

    # Act
    result = await credit_manager.has_enough_credits(user_id, required)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_has_enough_credits_user_not_found(credit_manager, mock_session):
    """Тест проверки кредитов - пользователь не найден"""
    # Arrange
    user_id = 999999
    required = 50

    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act
    result = await credit_manager.has_enough_credits(user_id, required)

    # Assert
    assert result is False


# ==================== ТЕСТЫ HAS_SUFFICIENT_CREDITS ====================


@pytest.mark.asyncio
async def test_has_sufficient_credits_with_credit_service(
    credit_manager_with_services, mock_credit_service
):
    """Тест has_sufficient_credits с использованием CreditService"""
    # Arrange
    user_id = 1
    required = 50
    mock_credit_service.has_sufficient_credits.return_value = True

    # Act
    result = await credit_manager_with_services.has_sufficient_credits(user_id, required)

    # Assert
    assert result is True
    mock_credit_service.has_sufficient_credits.assert_called_once_with(
        user_id, required, "ai_credits"
    )


@pytest.mark.asyncio
async def test_has_sufficient_credits_without_credit_service(credit_manager, mock_session):
    """Тест has_sufficient_credits без CreditService (fallback)"""
    # Arrange
    user_id = 123456
    required = 50

    mock_session.execute.return_value = create_mock_scalar_result(100)

    # Act
    result = await credit_manager.has_sufficient_credits(user_id, required)

    # Assert
    assert result is True


# ==================== ТЕСТЫ DEDUCT_CREDITS ====================


@pytest.mark.asyncio
async def test_deduct_credits_success(credit_manager, mock_session):
    """Тест успешного списания кредитов"""
    # Arrange
    user_id = 123456
    amount = 50

    # Mock для has_enough_credits (возвращает 100 кредитов)
    # Mock для update (просто выполняет UPDATE)
    mock_session.execute.side_effect = [
        create_mock_scalar_result(100),  # has_enough_credits
        MagicMock(),  # update query
    ]

    # Act
    result = await credit_manager.deduct_credits(user_id, amount)

    # Assert
    assert result is True
    assert mock_session.execute.call_count == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_deduct_credits_insufficient(credit_manager, mock_session):
    """Тест списания кредитов - недостаточно средств"""
    # Arrange
    user_id = 123456
    amount = 150

    mock_session.execute.return_value = create_mock_scalar_result(100)

    # Act
    result = await credit_manager.deduct_credits(user_id, amount)

    # Assert
    assert result is False
    # Commit не должен быть вызван
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_deduct_credits_negative_amount(credit_manager):
    """Тест списания отрицательного количества кредитов"""
    # Arrange
    user_id = 123456
    amount = -50

    # Act & Assert
    with pytest.raises(ValueError, match="Amount must be positive"):
        await credit_manager.deduct_credits(user_id, amount)


@pytest.mark.asyncio
async def test_deduct_credits_zero(credit_manager, mock_session):
    """Тест списания нуля кредитов"""
    # Arrange
    user_id = 123456
    amount = 0

    mock_session.execute.side_effect = [
        create_mock_scalar_result(100),  # has_enough_credits
        MagicMock(),  # update query
    ]

    # Act
    result = await credit_manager.deduct_credits(user_id, amount)

    # Assert
    assert result is True


# ==================== ТЕСТЫ ADD_CREDITS ====================


@pytest.mark.asyncio
async def test_add_credits_success(credit_manager, mock_session):
    """Тест успешного добавления кредитов"""
    # Arrange
    user_id = 123456
    amount = 100

    # Act
    result = await credit_manager.add_credits(user_id, amount)

    # Assert
    assert result is True
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_add_credits_negative_amount(credit_manager):
    """Тест добавления отрицательного количества кредитов"""
    # Arrange
    user_id = 123456
    amount = -100

    # Act & Assert
    with pytest.raises(ValueError, match="Amount must be positive"):
        await credit_manager.add_credits(user_id, amount)


@pytest.mark.asyncio
async def test_add_credits_zero(credit_manager, mock_session):
    """Тест добавления нуля кредитов"""
    # Arrange
    user_id = 123456
    amount = 0

    # Act
    result = await credit_manager.add_credits(user_id, amount)

    # Assert
    assert result is True


# ==================== ТЕСТЫ GET_USER_STATS ====================


@pytest.mark.asyncio
async def test_get_user_stats_success(credit_manager, mock_session):
    """Тест успешного получения статистики"""
    # Arrange
    user_id = 123456

    mock_row = MagicMock()
    mock_row.ai_credits = 150
    mock_row.ai_credits_used = 50

    # Fixed: using helper function
    mock_session.execute.return_value = create_mock_first_result(mock_row)

    # Act
    stats = await credit_manager.get_user_stats(user_id)

    # Assert
    assert stats is not None
    assert stats["ai_credits"] == 150
    assert stats["ai_credits_used"] == 50
    assert stats["total_received"] == 200


@pytest.mark.asyncio
async def test_get_user_stats_user_not_found(credit_manager, mock_session):
    """Тест получения статистики - пользователь не найден"""
    # Arrange
    user_id = 999999

    # Fixed: using helper function
    mock_session.execute.return_value = create_mock_first_result(None)

    # Act
    stats = await credit_manager.get_user_stats(user_id)

    # Assert
    assert stats is None


@pytest.mark.asyncio
async def test_get_user_stats_zero_usage(credit_manager, mock_session):
    """Тест получения статистики - пользователь не использовал кредиты"""
    # Arrange
    user_id = 123456

    mock_row = MagicMock()
    mock_row.ai_credits = 100
    mock_row.ai_credits_used = 0

    # Fixed: using helper function
    mock_session.execute.return_value = create_mock_first_result(mock_row)

    # Act
    stats = await credit_manager.get_user_stats(user_id)

    # Assert
    assert stats["ai_credits"] == 100
    assert stats["ai_credits_used"] == 0
    assert stats["total_received"] == 100


# ==================== ТЕСТЫ REFUND_CREDITS ====================


@pytest.mark.asyncio
async def test_refund_credits_success(credit_manager, mock_session):
    """Тест успешного возврата кредитов"""
    # Arrange
    user_id = 123456
    amount = 50
    reason = "Generation failed"

    # Act
    result = await credit_manager.refund_credits(user_id, amount, reason)

    # Assert
    assert result is True
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refund_credits_without_reason(credit_manager, mock_session):
    """Тест возврата кредитов без указания причины"""
    # Arrange
    user_id = 123456
    amount = 50

    # Act
    result = await credit_manager.refund_credits(user_id, amount)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_refund_credits_negative_amount(credit_manager):
    """Тест возврата отрицательного количества кредитов"""
    # Arrange
    user_id = 123456
    amount = -50

    # Act & Assert
    with pytest.raises(ValueError, match="Amount must be positive"):
        await credit_manager.refund_credits(user_id, amount)


@pytest.mark.asyncio
async def test_refund_credits_zero(credit_manager, mock_session):
    """Тест возврата нуля кредитов"""
    # Arrange
    user_id = 123456
    amount = 0

    # Act
    result = await credit_manager.refund_credits(user_id, amount)

    # Assert
    assert result is True


# ==================== ИНТЕГРАЦИОННЫЕ ТЕСТЫ ====================


@pytest.mark.asyncio
async def test_deduct_and_refund_flow(credit_manager, mock_session):
    """Тест полного flow: списание -> возврат кредитов"""
    # Arrange
    user_id = 123456
    amount = 50

    mock_session.execute.side_effect = [
        create_mock_scalar_result(100),  # deduct: has_enough_credits
        MagicMock(),  # deduct: update query
        MagicMock(),  # refund: update query
    ]

    # Act - Deduct
    deduct_result = await credit_manager.deduct_credits(user_id, amount)

    # Act - Refund
    refund_result = await credit_manager.refund_credits(user_id, amount, "Test refund")

    # Assert
    assert deduct_result is True
    assert refund_result is True
    assert mock_session.commit.call_count == 2


@pytest.mark.asyncio
async def test_multiple_operations_flow(credit_manager, mock_session):
    """Тест последовательных операций с кредитами"""
    # Arrange
    user_id = 123456

    mock_session.execute.side_effect = [
        MagicMock(),  # add_credits: update query
        create_mock_scalar_result(200),  # get_user_credits
    ]

    # Act
    add_result = await credit_manager.add_credits(user_id, 100)
    credits = await credit_manager.get_user_credits(user_id)

    # Assert
    assert add_result is True
    assert credits == 200
