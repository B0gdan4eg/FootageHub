# FootageHub Docker Infrastructure

Микросервисная архитектура FootageHub с двумя независимыми ботами:
- **MediaBot** - загрузка медиа с Envato/Freepik/Motion Array
- **AIBot** - генерация контента через нейросети (Kie.ai API)

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                      │
│  (Shared: users, subscriptions, payments, bonuses, referrals)│
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
                ┌─────────────┴──────────────┐
                │                            │
┌───────────────▼──────────────┐  ┌─────────▼────────────────┐
│      MediaBot Service        │  │      AIBot Service       │
│  (Container: media-bot)      │  │  (Container: ai-bot)     │
│  Port: 8000 (webhooks)       │  │                          │
└──────────────────────────────┘  └──────────────────────────┘
```

## Quick Start

### 1. Настройка окружения

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env и заполнить все необходимые переменные
nano .env
```

### 2. Запуск сервисов

```bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Просмотр логов конкретного сервиса
docker-compose logs -f media-bot
docker-compose logs -f ai-bot
```

### 3. Применение миграций БД

Миграции автоматически применяются при старте ботов через `db/base.py:run_migrations()`.

Для ручного применения:
```bash
# Подключиться к контейнеру MediaBot
docker-compose exec media-bot bash

# Выполнить миграции
alembic upgrade head
```

### 4. Остановка сервисов

```bash
# Остановить все сервисы
docker-compose down

# Остановить с удалением volumes (ОСТОРОЖНО: удалит БД!)
docker-compose down -v
```

## Управление сервисами

### Перезапуск отдельного сервиса

```bash
docker-compose restart media-bot
docker-compose restart ai-bot
```

### Просмотр статуса

```bash
docker-compose ps
```

### Выполнение команд внутри контейнера

```bash
# MediaBot
docker-compose exec media-bot python envato_utils/test_env.py

# AIBot
docker-compose exec ai-bot python -c "from ai_bot.config import *; print(KIE_AI_API_KEY[:10])"
```

## Структура Dockerfiles

### media-bot.Dockerfile

- **Base image**: `python:3.11-slim`
- **Особенности**:
  - Xvfb virtual display (требуется для Freepik)
  - Playwright + Chromium
  - PostgreSQL client для бэкапов
- **Volumes**:
  - `./cookies` - куки для загрузчиков
  - `./debug_screenshots` - скриншоты при ошибках

### ai-bot.Dockerfile

- **Base image**: `python:3.11-slim`
- **Особенности**:
  - Минимальный набор зависимостей
  - Нет Playwright (не требуется)
  - Только HTTP клиенты для Kie.ai API

## Volumes

### postgres_data

Хранит данные PostgreSQL. Для бэкапа:

```bash
# Создать дамп БД
docker-compose exec postgres pg_dump -U postgres footagehub > backup.sql

# Восстановить из дампа
docker-compose exec -T postgres psql -U postgres footagehub < backup.sql
```

## Networks

Все сервисы находятся в одной сети `footagehub-network`:
- postgres: `postgres:5432`
- media-bot: `media-bot:8000`
- ai-bot: `ai-bot` (без открытых портов)

## Переменные окружения

См. `.env.example` для полного списка.

### Критичные переменные:

- `MEDIA_BOT_TOKEN` - токен MediaBot от BotFather
- `AI_BOT_TOKEN` - токен AIBot от BotFather
- `DATABASE_URL` - строка подключения к PostgreSQL
- `ADMIN` - Telegram ID администратора
- `KIE_AI_API_KEY` - API ключ Kie.ai

### WebPay (опционально):

- `WEBPAY_RESOURCE_ID`, `WEBPAY_SIGNING_KEY` - для приёма платежей

## Troubleshooting

### MediaBot не запускается

```bash
# Проверить логи
docker-compose logs media-bot

# Проверить Xvfb
docker-compose exec media-bot ps aux | grep Xvfb

# Переустановить Playwright browsers
docker-compose exec media-bot playwright install chromium
```

### AIBot - ошибка Kie.ai API

```bash
# Проверить API ключ
docker-compose exec ai-bot python -c "import os; print(os.getenv('KIE_AI_API_KEY'))"

# Проверить подключение
docker-compose exec ai-bot curl https://api.kie.ai/v1/models
```

### БД не подключается

```bash
# Проверить статус PostgreSQL
docker-compose ps postgres

# Проверить health check
docker-compose exec postgres pg_isready -U postgres

# Проверить логи
docker-compose logs postgres
```

## Development

### Разработка с live reload

Volumes уже настроены для live reload:

```yaml
volumes:
  - ./media_bot:/app/media_bot  # Изменения в коде автоматически подхватываются
  - ./shared:/app/shared
```

После изменения кода:
```bash
docker-compose restart media-bot
```

### Запуск тестов

```bash
# MediaBot - тест Envato downloader
docker-compose exec media-bot python envato_utils/test_env.py

# MediaBot - тест Freepik downloader
docker-compose exec media-bot python freepik_utils/freepik.py

# MediaBot - тест Motion Array
docker-compose exec media-bot python test/test_motion.py
```

## Production Deployment

### Рекомендации:

1. **Используйте secrets** вместо .env файла
2. **Настройте автоматические бэкапы БД** (cron в контейнере media-bot)
3. **Добавьте Nginx** для reverse proxy
4. **Настройте мониторинг** (Prometheus + Grafana)
5. **Логирование**: централизованный сбор логов (ELK/Loki)

### Health Checks

PostgreSQL уже имеет health check. Добавьте для ботов:

```yaml
# В docker-compose.yml
healthcheck:
  test: ["CMD-SHELL", "python -c 'import sys; sys.exit(0)'"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Дополнительная информация

- **CLAUDE.md** - руководство по разработке
- **MICROSERVICES_ARCHITECTURE_PLAN.md** - план миграции на микросервисы
- **docs/** - техническая документация
