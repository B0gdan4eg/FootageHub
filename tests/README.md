# FootageHub Tests

Comprehensive test suite for FootageHub microservices architecture.

## Test Structure

```
tests/
├── conftest.py                      # Global fixtures
├── unit/                            # Unit tests
│   ├── shared/
│   │   ├── services/               # Service layer tests
│   │   │   ├── test_bonus_service.py
│   │   │   └── test_credit_service.py
│   │   └── repositories/           # Repository tests
│   │       └── test_user_repository.py
│   ├── media_bot/
│   │   └── services/               # MediaBot service tests
│   └── ai_bot/
│       └── services/               # AIBot service tests
├── integration/                     # Integration tests
│   ├── test_bonus_system.py        # End-to-end bonus flow
│   ├── test_referral_system.py     # End-to-end referral flow
│   └── test_ai_bot_flow.py         # AI generation flow
└── e2e/                            # End-to-end tests (future)
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test suite
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/shared/services/test_bonus_service.py

# Specific test class
pytest tests/unit/shared/services/test_bonus_service.py::TestBonusService

# Specific test method
pytest tests/unit/shared/services/test_bonus_service.py::TestBonusService::test_claim_bonus_success
```

### Run tests with coverage
```bash
# Run tests with coverage report
pytest --cov=shared --cov=media_bot --cov=ai_bot

# Generate HTML coverage report
pytest --cov=shared --cov=media_bot --cov=ai_bot --cov-report=html

# View coverage report
open htmlcov/index.html  # On macOS
start htmlcov/index.html  # On Windows
```

### Run tests in parallel
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests on multiple cores
pytest -n auto
```

### Run tests with verbose output
```bash
pytest -v
```

### Run only failed tests
```bash
pytest --lf  # Last failed
pytest --ff  # Failed first
```

## Test Categories

### Unit Tests

Test individual components in isolation using mocks:
- Services (BonusService, CreditService, ReferralService)
- Repositories (UserRepository, BonusRepository)
- Providers (AI providers)

**Characteristics:**
- Fast execution
- No database required (uses mocks)
- Tests single function/method behavior

### Integration Tests

Test interactions between multiple components with real database:
- Complete bonus claiming flow
- Referral system with bonus integration
- AI generation with credits management

**Characteristics:**
- Real database (SQLite in-memory)
- Tests multiple components together
- Verifies end-to-end workflows

### E2E Tests (Future)

Test complete user journeys through the bot:
- Full MediaBot download flow
- Full AIBot generation flow
- Payment and subscription flow

## Coverage Goals

- **Target:** >80% code coverage
- **Critical paths:** 100% coverage
  - Credit management
  - Bonus system
  - Payment processing

## Current Test Statistics

**Unit Tests:**
- BonusService: 15+ test cases
- CreditService: 20+ test cases
- UserRepository: 15+ test cases

**Integration Tests:**
- Bonus System: 7+ scenarios
- Referral System: 6+ scenarios
- AI Bot Flow: 8+ scenarios

## Writing New Tests

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from shared.services.bonus_service import BonusService

class TestBonusService:
    @pytest.mark.asyncio
    async def test_claim_bonus(self):
        # Arrange
        bonus_repo = AsyncMock()
        user_repo = AsyncMock()
        service = BonusService(bonus_repo, user_repo)

        # Act
        result = await service.claim_bonus(1, "BONUS_CODE")

        # Assert
        assert result is not None
```

### Integration Test Example

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.repositories.user_repository import UserRepository

class TestIntegration:
    @pytest.mark.asyncio
    async def test_complete_flow(self, async_session: AsyncSession):
        # Arrange
        repo = UserRepository(async_session)

        # Act
        user = await repo.create(tg_id=123)
        await async_session.commit()

        # Assert
        assert user.id is not None
```

## Fixtures

### Global Fixtures (conftest.py)

- `async_engine`: Async SQLAlchemy engine
- `async_session`: Async database session
- `mock_telegram_user`: Mock Telegram user data
- `mock_envato_url`: Mock Envato URL
- `mock_freepik_url`: Mock Freepik URL

### Test-Specific Fixtures

- `setup_bonus_types`: Creates test bonus types in DB
- `setup_referral_bonus_types`: Creates referral bonus types

## Continuous Integration

Tests are automatically run on every push via GitHub Actions:

```yaml
- name: Run tests
  run: |
    pytest --cov=shared --cov=media_bot --cov=ai_bot
```

## Troubleshooting

### Tests failing with database errors
- Ensure migrations are up to date
- Check that test database is properly isolated

### Import errors
- Verify PYTHONPATH includes project root
- Check that all __init__.py files exist

### Async tests not running
- Ensure pytest-asyncio is installed
- Use `@pytest.mark.asyncio` decorator

## Contributing

When adding new features:
1. Write unit tests first (TDD)
2. Add integration tests for workflows
3. Ensure coverage doesn't drop below 80%
4. Run `make test` before committing

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy testing](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
