"""
Unit тесты для AIRepository.

Тестируем:
- Создание и обновление логов генераций
- Получение генераций пользователя
- Статистику AI генераций
- Глобальную статистику
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.db.models import AIGenerationLog, AIGenerationStatus, AIGenerationType
from shared.db.repositories.ai_repository import AIRepository


def create_mock_execute_result(data):
    """
    Создает правильную цепочку моков для session.execute().

    Для работы с SQLAlchemy AsyncSession нужна цепочка:
    await session.execute(query) -> Result
    Result.scalars() -> ScalarResult
    ScalarResult.all() -> List[Model]

    Args:
        data: Список объектов или одно значение для возврата

    Returns:
        MagicMock настроенный для цепочки scalars().all()
    """
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = data
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


def create_mock_scalar_result(value):
    """
    Создает мок для session.execute().scalar() / scalar_one_or_none().

    Args:
        value: Значение для возврата

    Returns:
        MagicMock настроенный для scalar() методов
    """
    mock_result = MagicMock()
    mock_result.scalar.return_value = value
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


@pytest.fixture
def mock_session():
    """Mock AsyncSession"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    # execute должен возвращать результат напрямую, а не как корутину
    # так как AsyncMock уже awaitable
    return session


@pytest.fixture
def ai_repo(mock_session):
    """Экземпляр AIRepository с моками"""
    return AIRepository(session=mock_session)


# ==================== ТЕСТЫ CREATE_GENERATION_LOG ====================


@pytest.mark.asyncio
async def test_create_generation_log_minimal(ai_repo, mock_session):
    """Тест создания лога генерации с минимальными параметрами"""
    # Arrange
    user_id = 1
    provider = "KIE_AI"
    model = "nano-banana"
    generation_type = AIGenerationType.IMAGE
    prompt = "A beautiful sunset"

    # Act
    result = await ai_repo.create_generation_log(
        user_id=user_id,
        provider=provider,
        model=model,
        generation_type=generation_type,
        prompt=prompt,
    )

    # Assert
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_generation_log_full(ai_repo, mock_session):
    """Тест создания лога генерации со всеми параметрами"""
    # Arrange
    user_id = 1
    provider = "KLING"
    model = "kling-2.6"
    generation_type = AIGenerationType.VIDEO
    prompt = "A cat playing piano"
    parameters = {"duration": 5, "quality": "high"}
    ai_credits_spent = 10

    # Act
    result = await ai_repo.create_generation_log(
        user_id=user_id,
        provider=provider,
        model=model,
        generation_type=generation_type,
        prompt=prompt,
        parameters=parameters,
        ai_credits_spent=ai_credits_spent,
    )

    # Assert
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()


# ==================== ТЕСТЫ UPDATE_GENERATION_LOG ====================


@pytest.mark.asyncio
async def test_update_generation_log_success(ai_repo, mock_session):
    """Тест обновления лога генерации - успех"""
    # Arrange
    log_id = 1
    existing_log = AIGenerationLog(
        id=log_id,
        user_id=1,
        provider="KIE_AI",
        model="nano-banana",
        generation_type=AIGenerationType.IMAGE,
        prompt="test",
        status=AIGenerationStatus.PENDING,
    )

    # Mock get_by_id
    ai_repo.get_by_id = AsyncMock(return_value=existing_log)

    # Act
    result = await ai_repo.update_generation_log(
        log_id=log_id,
        status=AIGenerationStatus.SUCCESS,
        result_url="https://example.com/result.jpg",
        processing_time_seconds=30,
    )

    # Assert
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_generation_log_not_found(ai_repo, mock_session):
    """Тест обновления лога генерации - не найден"""
    # Arrange
    ai_repo.get_by_id = AsyncMock(return_value=None)

    # Act & Assert
    with pytest.raises(ValueError, match="not found"):
        await ai_repo.update_generation_log(log_id=999, status=AIGenerationStatus.SUCCESS)


@pytest.mark.asyncio
async def test_update_generation_log_failed(ai_repo, mock_session):
    """Тест обновления лога генерации - провал"""
    # Arrange
    log_id = 1
    existing_log = AIGenerationLog(
        id=log_id,
        user_id=1,
        provider="KIE_AI",
        model="nano-banana",
        generation_type=AIGenerationType.IMAGE,
        prompt="test",
        status=AIGenerationStatus.PROCESSING,
    )

    ai_repo.get_by_id = AsyncMock(return_value=existing_log)

    # Act
    result = await ai_repo.update_generation_log(
        log_id=log_id,
        status=AIGenerationStatus.FAILED,
        error_message="API Error",
        processing_time_seconds=15,
    )

    # Assert
    mock_session.flush.assert_called_once()


# ==================== ТЕСТЫ MARK_AS_* ====================


@pytest.mark.asyncio
async def test_mark_as_processing(ai_repo):
    """Тест маркировки генерации как обрабатывающейся"""
    # Arrange
    log_id = 1
    ai_repo.update_generation_log = AsyncMock()

    # Act
    await ai_repo.mark_as_processing(log_id)

    # Assert
    ai_repo.update_generation_log.assert_called_once_with(
        log_id=log_id, status=AIGenerationStatus.PROCESSING
    )


@pytest.mark.asyncio
async def test_mark_as_success(ai_repo):
    """Тест маркировки генерации как успешной"""
    # Arrange
    log_id = 1
    result_url = "https://example.com/result.jpg"
    processing_time = 45
    ai_repo.update_generation_log = AsyncMock()

    # Act
    await ai_repo.mark_as_success(log_id, result_url, processing_time)

    # Assert
    ai_repo.update_generation_log.assert_called_once_with(
        log_id=log_id,
        status=AIGenerationStatus.SUCCESS,
        result_url=result_url,
        processing_time_seconds=processing_time,
    )


@pytest.mark.asyncio
async def test_mark_as_failed(ai_repo):
    """Тест маркировки генерации как провалившейся"""
    # Arrange
    log_id = 1
    error_message = "API timeout"
    processing_time = 60
    ai_repo.update_generation_log = AsyncMock()

    # Act
    await ai_repo.mark_as_failed(log_id, error_message, processing_time)

    # Assert
    ai_repo.update_generation_log.assert_called_once_with(
        log_id=log_id,
        status=AIGenerationStatus.FAILED,
        error_message=error_message,
        processing_time_seconds=processing_time,
    )


# ==================== ТЕСТЫ GET_USER_GENERATIONS ====================


@pytest.mark.asyncio
async def test_get_user_generations_all(ai_repo, mock_session):
    """Тест получения всех генераций пользователя"""
    # Arrange
    user_id = 1
    generations = [
        AIGenerationLog(id=1, user_id=user_id),
        AIGenerationLog(id=2, user_id=user_id),
    ]
    mock_session.execute.return_value = create_mock_execute_result(generations)

    # Act
    result = await ai_repo.get_user_generations(user_id=user_id)

    # Assert
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_user_generations_with_filters(ai_repo, mock_session):
    """Тест получения генераций с фильтрами"""
    # Arrange
    user_id = 1
    generations = [
        AIGenerationLog(id=1, user_id=user_id, status=AIGenerationStatus.SUCCESS),
    ]
    mock_session.execute.return_value = create_mock_execute_result(generations)

    # Act
    result = await ai_repo.get_user_generations(
        user_id=user_id,
        limit=10,
        offset=0,
        status=AIGenerationStatus.SUCCESS,
        generation_type=AIGenerationType.IMAGE,
    )

    # Assert
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_user_generations_pagination(ai_repo, mock_session):
    """Тест пагинации генераций"""
    # Arrange
    user_id = 1
    generations = [AIGenerationLog(id=i, user_id=user_id) for i in range(6, 11)]
    mock_session.execute.return_value = create_mock_execute_result(generations)

    # Act
    result = await ai_repo.get_user_generations(user_id=user_id, limit=5, offset=5)

    # Assert
    assert len(result) == 5


# ==================== ТЕСТЫ GET_RECENT_GENERATIONS ====================


@pytest.mark.asyncio
async def test_get_recent_generations(ai_repo, mock_session):
    """Тест получения последних генераций за период"""
    # Arrange
    user_id = 1
    generations = [
        AIGenerationLog(id=1, user_id=user_id),
        AIGenerationLog(id=2, user_id=user_id),
    ]
    mock_session.execute.return_value = create_mock_execute_result(generations)

    # Act
    result = await ai_repo.get_recent_generations(user_id=user_id, hours=24)

    # Assert
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_recent_generations_custom_period(ai_repo, mock_session):
    """Тест получения последних генераций за кастомный период"""
    # Arrange
    user_id = 1
    mock_session.execute.return_value = create_mock_execute_result([])

    # Act
    result = await ai_repo.get_recent_generations(user_id=user_id, hours=1)

    # Assert
    assert result == []


# ==================== ТЕСТЫ GET_PENDING_GENERATIONS ====================


@pytest.mark.asyncio
async def test_get_pending_generations_all_users(ai_repo, mock_session):
    """Тест получения зависших генераций всех пользователей"""
    # Arrange
    generations = [
        AIGenerationLog(id=1, user_id=1, status=AIGenerationStatus.PENDING),
        AIGenerationLog(id=2, user_id=2, status=AIGenerationStatus.PROCESSING),
    ]
    mock_session.execute.return_value = create_mock_execute_result(generations)

    # Act
    result = await ai_repo.get_pending_generations(older_than_minutes=60)

    # Assert
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_pending_generations_specific_user(ai_repo, mock_session):
    """Тест получения зависших генераций конкретного пользователя"""
    # Arrange
    user_id = 1
    generations = [
        AIGenerationLog(id=1, user_id=user_id, status=AIGenerationStatus.PENDING),
    ]
    mock_session.execute.return_value = create_mock_execute_result(generations)

    # Act
    result = await ai_repo.get_pending_generations(user_id=user_id, older_than_minutes=30)

    # Assert
    assert len(result) == 1


# ==================== ТЕСТЫ GET_USER_STATS ====================


@pytest.mark.asyncio
async def test_get_user_stats(ai_repo, mock_session):
    """Тест получения статистики пользователя"""
    # Arrange
    user_id = 1

    # Создаем моки для каждого запроса
    # Mock: по типам (использует .all())
    mock_by_type = MagicMock()
    mock_by_type.all.return_value = [
        (AIGenerationType.IMAGE, 60),
        (AIGenerationType.VIDEO, 40),
    ]

    mock_session.execute.side_effect = [
        create_mock_scalar_result(100),  # total
        create_mock_scalar_result(80),  # success
        create_mock_scalar_result(10),  # failed
        create_mock_scalar_result(150),  # credits
        mock_by_type,  # by_type (использует .all(), не .scalars().all())
        create_mock_scalar_result(45.5),  # avg_time
    ]

    # Act
    stats = await ai_repo.get_user_stats(user_id)

    # Assert
    assert stats["total_generations"] == 100
    assert stats["successful_generations"] == 80
    assert stats["failed_generations"] == 10
    assert stats["total_ai_credits_spent"] == 150
    assert stats["generations_by_type"]["IMAGE"] == 60
    assert stats["generations_by_type"]["VIDEO"] == 40
    assert stats["average_processing_time_seconds"] == 45
    assert stats["success_rate"] == 80.0


@pytest.mark.asyncio
async def test_get_user_stats_zero_generations(ai_repo, mock_session):
    """Тест получения статистики пользователя без генераций"""
    # Arrange
    user_id = 1

    mock_by_type_empty = MagicMock()
    mock_by_type_empty.all.return_value = []

    mock_session.execute.side_effect = [
        create_mock_scalar_result(0),  # total
        create_mock_scalar_result(0),  # success
        create_mock_scalar_result(0),  # failed
        create_mock_scalar_result(0),  # credits
        mock_by_type_empty,  # by_type
        create_mock_scalar_result(0),  # avg_time
    ]

    # Act
    stats = await ai_repo.get_user_stats(user_id)

    # Assert
    assert stats["total_generations"] == 0
    assert stats["success_rate"] == 0


# ==================== ТЕСТЫ GET_GLOBAL_STATS ====================


@pytest.mark.asyncio
async def test_get_global_stats(ai_repo, mock_session):
    """Тест получения глобальной статистики"""
    # Arrange
    mock_provider = MagicMock()
    mock_provider.all.return_value = [
        ("KIE_AI", 500),
        ("KLING", 300),
        ("VEO", 200),
    ]

    mock_model = MagicMock()
    mock_model.all.return_value = [
        ("nano-banana", 500),
        ("kling-2.6", 300),
        ("veo-3.1", 200),
    ]

    mock_session.execute.side_effect = [
        create_mock_scalar_result(1000),  # total
        mock_provider,  # by_provider
        mock_model,  # by_model
        create_mock_scalar_result(5000),  # credits
    ]

    # Act
    stats = await ai_repo.get_global_stats()

    # Assert
    assert stats["total_generations"] == 1000
    assert stats["by_provider"]["KIE_AI"] == 500
    assert stats["by_model"]["nano-banana"] == 500
    assert stats["total_ai_credits_spent"] == 5000


@pytest.mark.asyncio
async def test_get_global_stats_with_since(ai_repo, mock_session):
    """Тест получения глобальной статистики с указанием периода"""
    # Arrange
    since = datetime.utcnow() - timedelta(days=7)

    mock_empty_list = MagicMock()
    mock_empty_list.all.return_value = []

    mock_session.execute.side_effect = [
        create_mock_scalar_result(100),  # total
        mock_empty_list,  # by_provider
        mock_empty_list,  # by_model
        create_mock_scalar_result(100),  # credits
    ]

    # Act
    stats = await ai_repo.get_global_stats(since=since)

    # Assert
    assert stats["total_generations"] == 100


# ==================== ТЕСТЫ GET_TOTAL_USER_GENERATIONS ====================


@pytest.mark.asyncio
async def test_get_total_user_generations(ai_repo, mock_session):
    """Тест получения общего количества генераций пользователя"""
    # Arrange
    user_id = 1
    mock_session.execute.return_value = create_mock_scalar_result(42)

    # Act
    result = await ai_repo.get_total_user_generations(user_id)

    # Assert
    assert result == 42


@pytest.mark.asyncio
async def test_get_total_user_generations_zero(ai_repo, mock_session):
    """Тест получения общего количества генераций - нет генераций"""
    # Arrange
    user_id = 1
    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act
    result = await ai_repo.get_total_user_generations(user_id)

    # Assert
    assert result == 0


# ==================== ТЕСТЫ GET_TOTAL_USER_AI_CREDITS_SPENT ====================


@pytest.mark.asyncio
async def test_get_total_user_ai_credits_spent(ai_repo, mock_session):
    """Тест получения общего количества потраченных AI кредитов"""
    # Arrange
    user_id = 1
    mock_session.execute.return_value = create_mock_scalar_result(250)

    # Act
    result = await ai_repo.get_total_user_ai_credits_spent(user_id)

    # Assert
    assert result == 250


@pytest.mark.asyncio
async def test_get_total_user_ai_credits_spent_zero(ai_repo, mock_session):
    """Тест получения общего количества потраченных AI кредитов - нет кредитов"""
    # Arrange
    user_id = 1
    mock_session.execute.return_value = create_mock_scalar_result(None)

    # Act
    result = await ai_repo.get_total_user_ai_credits_spent(user_id)

    # Assert
    assert result == 0
