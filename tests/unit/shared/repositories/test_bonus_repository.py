"""
Unit тесты для BonusRepository.

Тестируем:
- Получение бонусных типов
- Создание записей бонусов пользователей
- Проверку наличия бонусов
- Обновление статусов
- Подсчет суммарных кредитов
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.core.exceptions import BonusNotFoundError
from shared.db.models import BonusStatus, BonusType, UserBonus
from shared.db.repositories.bonus_repository import BonusRepository


def create_mock_execute_result(data):
    """
    Создает правильную цепочку моков для session.execute().scalars().all()
    """
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = data
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


def create_mock_scalar_result(value):
    """
    Создает мок для session.execute().scalar() / scalar_one_or_none().
    """
    mock_result = MagicMock()
    mock_result.scalar.return_value = value
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


def create_mock_one_result(value):
    """
    Создает мок для session.execute().one().
    """
    mock_result = MagicMock()
    mock_result.one.return_value = value
    return mock_result


@pytest.fixture
def mock_session():
    """Mock AsyncSession"""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    # execute() - async метод, поэтому AsyncMock уже правильно работает
    return session


@pytest.fixture
def bonus_repo(mock_session):
    """Экземпляр BonusRepository с моками"""
    return BonusRepository(session=mock_session)


# ==================== ТЕСТЫ GET_BY_CODE ====================


@pytest.mark.asyncio
async def test_get_by_code_found(bonus_repo, mock_session):
    """Тест получения бонусного типа по коду - найден"""
    # Arrange
    bonus_type = BonusType(id=1, code="REFERRAL_REGISTRATION", name="Referral", credits_amount=50)
    mock_session.execute.return_value = create_mock_scalar_result(bonus_type)

    # Act
    result = await bonus_repo.get_by_code("REFERRAL_REGISTRATION")

    # Assert
    assert result is not None
    assert result.code == "REFERRAL_REGISTRATION"
    assert result.credits_amount == 50


@pytest.mark.asyncio
async def test_get_by_code_not_found(bonus_repo, mock_session):
    """Тест получения бонусного типа по коду - не найден"""
    # Arrange
    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act
    result = await bonus_repo.get_by_code("NONEXISTENT_CODE")

    # Assert
    assert result is None


# ==================== ТЕСТЫ GET_ACTIVE_BONUSES ====================


@pytest.mark.asyncio
async def test_get_active_bonuses(bonus_repo, mock_session):
    """Тест получения всех активных бонусов"""
    # Arrange
    active_bonuses = [
        BonusType(id=1, code="BONUS1", is_active=True),
        BonusType(id=2, code="BONUS2", is_active=True),
        BonusType(id=3, code="BONUS3", is_active=True),
    ]
    mock_session.execute.return_value = create_mock_execute_result(active_bonuses)

    # Act
    result = await bonus_repo.get_active_bonuses()

    # Assert
    assert len(result) == 3
    assert all(b.is_active for b in result)


@pytest.mark.asyncio
async def test_get_active_bonuses_empty(bonus_repo, mock_session):
    """Тест получения активных бонусов - нет активных"""
    # Arrange
    mock_session.execute.return_value = create_mock_execute_result([])

    # Act
    result = await bonus_repo.get_active_bonuses()

    # Assert
    assert result == []


# ==================== ТЕСТЫ CREATE_USER_BONUS ====================


@pytest.mark.asyncio
async def test_create_user_bonus_minimal(bonus_repo, mock_session):
    """Тест создания пользовательского бонуса с минимальными параметрами"""
    # Arrange
    user_id, bonus_type_id = 1, 10

    # Act
    result = await bonus_repo.create_user_bonus(
        user_id=user_id,
        bonus_type_id=bonus_type_id,
    )

    # Assert
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_bonus_full(bonus_repo, mock_session):
    """Тест создания пользовательского бонуса со всеми параметрами"""
    # Arrange
    user_id, bonus_type_id = 1, 10
    credits = 100
    ai_credits = 50
    metadata = {"referral_id": 5}
    status = "COMPLETED"
    completed_at = datetime.utcnow()
    expires_at = datetime.utcnow()

    # Act
    result = await bonus_repo.create_user_bonus(
        user_id=user_id,
        bonus_type_id=bonus_type_id,
        credits_granted=credits,
        ai_credits_granted=ai_credits,
        metadata=metadata,
        status=status,
        completed_at=completed_at,
        expires_at=expires_at,
    )

    # Assert
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()


# ==================== ТЕСТЫ GET_USER_BONUSES ====================


@pytest.mark.asyncio
async def test_get_user_bonuses_all(bonus_repo, mock_session):
    """Тест получения всех бонусов пользователя"""
    # Arrange
    user_id = 1
    user_bonuses = [
        UserBonus(id=1, user_id=user_id, credits_granted=50),
        UserBonus(id=2, user_id=user_id, credits_granted=100),
    ]
    mock_session.execute.return_value = create_mock_execute_result(user_bonuses)

    # Act
    result = await bonus_repo.get_user_bonuses(user_id)

    # Assert
    assert len(result) == 2
    assert all(b.user_id == user_id for b in result)


@pytest.mark.asyncio
async def test_get_user_bonuses_with_status_filter(bonus_repo, mock_session):
    """Тест получения бонусов пользователя с фильтром по статусу"""
    # Arrange
    user_id = 1
    completed_bonuses = [
        UserBonus(id=1, user_id=user_id, status=BonusStatus.COMPLETED),
    ]
    mock_session.execute.return_value = create_mock_execute_result(completed_bonuses)

    # Act
    result = await bonus_repo.get_user_bonuses(user_id, status="COMPLETED")

    # Assert
    assert len(result) == 1
    assert result[0].status == BonusStatus.COMPLETED


@pytest.mark.asyncio
async def test_get_user_bonuses_empty(bonus_repo, mock_session):
    """Тест получения бонусов пользователя - нет бонусов"""
    # Arrange
    mock_session.execute.return_value = create_mock_execute_result([])

    # Act
    result = await bonus_repo.get_user_bonuses(user_id=1)

    # Assert
    assert result == []


# ==================== ТЕСТЫ USER_HAS_BONUS ====================


@pytest.mark.asyncio
async def test_user_has_bonus_true(bonus_repo, mock_session):
    """Тест проверки наличия бонуса - есть"""
    # Arrange
    user_bonus = UserBonus(id=1, user_id=1, bonus_type_id=10)
    mock_session.execute.return_value = create_mock_scalar_result(user_bonus)

    # Act
    result = await bonus_repo.user_has_bonus(user_id=1, bonus_type_id=10)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_user_has_bonus_false(bonus_repo, mock_session):
    """Тест проверки наличия бонуса - нет"""
    # Arrange
    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act
    result = await bonus_repo.user_has_bonus(user_id=1, bonus_type_id=10)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_user_has_bonus_with_status_filter(bonus_repo, mock_session):
    """Тест проверки наличия бонуса с фильтром по статусу"""
    # Arrange
    user_bonus = UserBonus(id=1, user_id=1, bonus_type_id=10, status=BonusStatus.COMPLETED)
    mock_session.execute.return_value = create_mock_scalar_result(user_bonus)

    # Act
    result = await bonus_repo.user_has_bonus(user_id=1, bonus_type_id=10, status="COMPLETED")

    # Assert
    assert result is True


# ==================== ТЕСТЫ GET_LAST_USER_BONUS ====================


@pytest.mark.asyncio
async def test_get_last_user_bonus_found(bonus_repo, mock_session):
    """Тест получения последнего бонуса пользователя - найден"""
    # Arrange
    last_bonus = UserBonus(id=5, user_id=1, bonus_type_id=10)
    mock_session.execute.return_value = create_mock_scalar_result(last_bonus)

    # Act
    result = await bonus_repo.get_last_user_bonus(user_id=1, bonus_type_id=10)

    # Assert
    assert result is not None
    assert result.id == 5


@pytest.mark.asyncio
async def test_get_last_user_bonus_not_found(bonus_repo, mock_session):
    """Тест получения последнего бонуса пользователя - не найден"""
    # Arrange
    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act
    result = await bonus_repo.get_last_user_bonus(user_id=1, bonus_type_id=10)

    # Assert
    assert result is None


# ==================== ТЕСТЫ UPDATE_BONUS_STATUS ====================


@pytest.mark.asyncio
async def test_update_bonus_status_success(bonus_repo, mock_session):
    """Тест обновления статуса бонуса - успешно"""
    # Arrange
    bonus = UserBonus(id=1, user_id=1, status=BonusStatus.PENDING)
    mock_session.execute.return_value = create_mock_scalar_result(bonus)

    completed_at = datetime.utcnow()

    # Act
    result = await bonus_repo.update_bonus_status(
        bonus_id=1, status="COMPLETED", completed_at=completed_at
    )

    # Assert
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_bonus_status_not_found(bonus_repo, mock_session):
    """Тест обновления статуса бонуса - бонус не найден"""
    # Arrange
    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act & Assert
    with pytest.raises(BonusNotFoundError, match="Bonus .* not found"):
        await bonus_repo.update_bonus_status(bonus_id=999, status="COMPLETED")


@pytest.mark.asyncio
async def test_update_bonus_status_without_completed_at(bonus_repo, mock_session):
    """Тест обновления статуса бонуса без указания completed_at"""
    # Arrange
    bonus = UserBonus(id=1, user_id=1, status=BonusStatus.PENDING)
    mock_session.execute.return_value = create_mock_scalar_result(bonus)

    # Act
    result = await bonus_repo.update_bonus_status(bonus_id=1, status="COMPLETED")

    # Assert
    mock_session.commit.assert_called_once()


# ==================== ТЕСТЫ GET_TOTAL_CREDITS_FROM_BONUSES ====================


@pytest.mark.asyncio
async def test_get_total_credits_from_bonuses(bonus_repo, mock_session):
    """Тест подсчета общих кредитов из бонусов"""
    # Arrange
    mock_session.execute.return_value = create_mock_one_result((500, 100))

    # Act
    total_credits, total_ai_credits = await bonus_repo.get_total_credits_from_bonuses(
        user_id=1, status="COMPLETED"
    )

    # Assert
    assert total_credits == 500
    assert total_ai_credits == 100


@pytest.mark.asyncio
async def test_get_total_credits_from_bonuses_zero(bonus_repo, mock_session):
    """Тест подсчета общих кредитов - нет бонусов"""
    # Arrange
    mock_session.execute.return_value = create_mock_one_result((None, None))

    # Act
    total_credits, total_ai_credits = await bonus_repo.get_total_credits_from_bonuses(
        user_id=1, status="COMPLETED"
    )

    # Assert
    assert total_credits == 0
    assert total_ai_credits == 0


@pytest.mark.asyncio
async def test_get_total_credits_from_bonuses_partial_none(bonus_repo, mock_session):
    """Тест подсчета общих кредитов - частичные None значения"""
    # Arrange
    mock_session.execute.return_value = create_mock_one_result((500, None))

    # Act
    total_credits, total_ai_credits = await bonus_repo.get_total_credits_from_bonuses(
        user_id=1, status="COMPLETED"
    )

    # Assert
    assert total_credits == 500
    assert total_ai_credits == 0
