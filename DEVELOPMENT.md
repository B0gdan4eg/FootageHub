# Development Guide

## Настройка окружения для разработки

### 1. Установка зависимостей

```bash
# Установить production зависимости
pip install -r requirements/base.txt

# Установить development зависимости (линтеры, тесты и т.д.)
pip install -r requirements/dev.txt
```

### 2. Настройка pre-commit hooks

Pre-commit hooks автоматически проверяют код перед каждым коммитом.

```bash
# Установить pre-commit hooks
pre-commit install

# Или через Makefile
make pre-commit-install
```

После этого, при каждом `git commit` будут автоматически запускаться:
- ✅ black (форматирование кода)
- ✅ isort (сортировка импортов)
- ✅ flake8 (проверка стиля кода)
- ✅ mypy (проверка типов)
- ✅ bandit (проверка безопасности)

### 3. Запуск проверок вручную

#### Форматирование кода

```bash
# Автоматическое форматирование с black и isort
make format

# Или по отдельности:
black shared/ media_bot/ ai_bot/ tests/
isort shared/ media_bot/ ai_bot/ tests/
```

#### Проверка стиля (linting)

```bash
# Запустить flake8
make lint

# Или напрямую:
flake8 shared/ media_bot/ ai_bot/
```

#### Проверка типов

```bash
# Запустить mypy
make type-check

# Или напрямую:
mypy shared/ media_bot/ ai_bot/ --config-file pyproject.toml
```

#### Проверка безопасности

```bash
# Запустить bandit
make security

# Или напрямую:
bandit -r shared/ media_bot/ ai_bot/ -c pyproject.toml
```

#### Запустить все проверки сразу

```bash
make check
```

Эта команда запустит: format + lint + type-check + security + tests

### 4. Тестирование

#### Запуск тестов

```bash
# Простой запуск тестов
make test

# Запуск с coverage report
make test-cov

# Или напрямую:
pytest tests/ -v
pytest tests/ -v --cov=shared --cov=media_bot --cov=ai_bot --cov-report=html
```

После запуска с coverage, откройте `htmlcov/index.html` в браузере для детального отчета.

#### Запуск конкретного теста

```bash
# Запустить конкретный файл
pytest tests/test_bonus_service.py -v

# Запустить конкретный тест
pytest tests/test_bonus_service.py::test_claim_first_login_bonus -v

# Запустить тесты с определенной меткой
pytest tests/ -v -m "unit"
```

### 5. Использование Makefile

Все частые команды собраны в Makefile:

```bash
# Показать все доступные команды
make help

# Основные команды:
make install          # Установить production зависимости
make install-dev      # Установить dev зависимости
make format           # Отформатировать код
make lint             # Проверить стиль
make type-check       # Проверить типы
make security         # Проверить безопасность
make test             # Запустить тесты
make test-cov         # Тесты с coverage
make check            # Все проверки сразу
make clean            # Очистить временные файлы

# Docker команды:
make docker-build     # Собрать Docker образы
make docker-up        # Запустить контейнеры
make docker-down      # Остановить контейнеры
make docker-logs      # Показать логи

# Database миграции:
make migrate          # Применить миграции
make migrate-down     # Откатить последнюю миграцию
make migrate-create   # Создать новую миграцию
```

### 6. Конфигурация инструментов

#### Black (форматирование)

Конфигурация в `pyproject.toml`:
- Длина строки: 100 символов
- Python версия: 3.11
- Исключены: migrations, venv

#### Flake8 (linting)

Конфигурация в `.flake8`:
- Максимальная длина строки: 100
- Игнорируемые правила: E203, W503, E501 (конфликты с black)
- Максимальная сложность: 10

#### MyPy (type checking)

Конфигурация в `pyproject.toml`:
- Строгие проверки включены
- Игнорируются импорты из сторонних библиотек без типов

#### Bandit (security)

Конфигурация в `pyproject.toml`:
- Исключены: tests, migrations
- Пропускаются: B101 (assert), B601 (shell injection в тестах)

### 7. CI/CD

#### GitHub Actions

При каждом push в master/develop ветку автоматически запускаются:

1. **Lint and Test** job:
   - Проверка форматирования (isort, black)
   - Проверка стиля (flake8)
   - Проверка типов (mypy)
   - Проверка безопасности (bandit)
   - Запуск тестов с coverage
   - Загрузка coverage в Codecov

2. **Docker Build** job:
   - Сборка Docker образов для MediaBot и AIBot
   - Проверка что контейнеры собираются без ошибок

#### Pre-commit.ci

При создании Pull Request, [pre-commit.ci](https://pre-commit.ci) автоматически:
- Запустит все pre-commit hooks
- Исправит форматирование кода
- Создаст коммит с исправлениями

### 8. Рекомендации по разработке

#### Перед коммитом

1. Запустить `make check` чтобы проверить что все в порядке
2. Убедиться что все тесты проходят
3. Обновить документацию если нужно

#### Написание кода

1. **Используйте type hints**:
```python
def add_credits(user_id: int, amount: int) -> User:
    ...
```

2. **Документируйте функции**:
```python
def claim_bonus(user_id: int, bonus_code: str) -> UserBonus:
    """
    Начислить бонус пользователю.

    Args:
        user_id: ID пользователя
        bonus_code: Код бонуса (FIRST_LOGIN, CHANNEL_SUBSCRIPTION, etc.)

    Returns:
        Созданный объект UserBonus

    Raises:
        BonusNotFoundError: Бонус не найден
        BonusAlreadyClaimedError: Бонус уже получен
    """
    ...
```

3. **Пишите тесты** для новых функций:
```python
def test_claim_first_login_bonus():
    # Given
    user_id = 123

    # When
    bonus = bonus_service.claim_bonus(user_id, "FIRST_LOGIN")

    # Then
    assert bonus.credits_granted == 3
```

4. **Следуйте SOLID принципам**:
   - Single Responsibility
   - Open/Closed
   - Liskov Substitution
   - Interface Segregation
   - Dependency Inversion

### 9. Troubleshooting

#### Pre-commit hooks не работают

```bash
# Переустановить hooks
pre-commit uninstall
pre-commit install

# Запустить вручную
pre-commit run --all-files
```

#### Mypy ошибки типов

Если mypy выдает ошибки для сторонних библиотек, добавьте в `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["library_name.*"]
ignore_missing_imports = true
```

#### Тесты не проходят локально

```bash
# Убедитесь что БД запущена
docker-compose up -d postgres

# Примените миграции
make migrate

# Запустите тесты
make test
```

### 10. Полезные ссылки

- [Black documentation](https://black.readthedocs.io/)
- [Flake8 documentation](https://flake8.pycqa.org/)
- [MyPy documentation](https://mypy.readthedocs.io/)
- [Pytest documentation](https://docs.pytest.org/)
- [Pre-commit documentation](https://pre-commit.com/)
