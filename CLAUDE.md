# FootageHub — CLAUDE.md

## Проект
Сервис для скачивания медиа с Envato Elements, Freepik, Motion Array через Telegram-бота и веб-интерфейс.

## Архитектура

| Компонент | Путь | Описание |
|-----------|------|----------|
| `media_bot` | `media_bot/` | Основной Telegram-бот (скачивание) |
| `ai_bot` | `ai_bot/` | AI-бот (генерация через Kie.ai) |
| `web_api` | `web_api/` | FastAPI-бэкенд для веб-версии (порт 8080) |
| `frontend` | `frontend/` | Next.js 16 фронтенд (порт 3000) |
| `shared` | `shared/` | Общие модели, репозитории, сессия БД |
| `migrations` | `migrations/` | Alembic миграции |

## Стек
- **Backend**: Python 3.11, FastAPI, SQLAlchemy async, asyncpg, Alembic
- **Frontend**: Next.js 16 (App Router, TypeScript, Tailwind CSS)
- **БД**: PostgreSQL 15 (`botdb`, user `botuser`)
- **Боты**: aiogram 3
- **Auth**: JWT (7 дней) + Telegram Login Widget + SMS (SMSC.ru)
- **Инфра**: Docker, GitHub Actions CI/CD, nginx, Let's Encrypt

## Продакшн-сервер
- **Домен**: `https://envato-freepik-download.store`
- **Бот-домен**: `https://footage.com.by` (вебхуки)
- **Docker Compose**: `/opt/my_bot/docker-compose.yml`
- **Env**: `/opt/my_bot/.env`
- **БД**: `botuser` / `botdb`

## Переменные окружения (.env на сервере)
```env
BOT_TOKEN=<основной бот>
AI_BOT_TOKEN=<ai бот>
BOT_USERNAME=FootageHub_bot
DATABASE_URL=postgresql+asyncpg://botuser:...@postgres:5432/botdb
JWT_SECRET_KEY=...
SMSC_LOGIN=...
SMSC_PASSWORD=...
KIE_AI_API_KEY=...
WEBPAY_RESOURCE_ID=...
WEBPAY_SIGNING_KEY=...
CRYPTO_BOT_API_KEY=...
CORS_ORIGINS=https://envato-freepik-download.store
POSTGRES_USER=botuser
POSTGRES_PASSWORD=...
POSTGRES_DB=botdb
```

## CI/CD (GitHub Actions)
- `deploy.yml` — media-bot: триггер на изменения в `media_bot/`, `shared/`
- `deploy-ai-bot.yml` — ai-bot: триггер на изменения в `ai_bot/`
- `deploy-web.yml` — web-api + frontend: триггер на `web_api/`, `frontend/`, `shared/`
- Все workflows: копируют `docker-compose.yml` на сервер, запускают `alembic upgrade head`, деплоят контейнеры

## Авторизация на веб-сайте
1. **Telegram Login Widget** (основной способ) — POST `/api/auth/telegram`
2. **SMS через SMSC.ru** — POST `/api/auth/send-code` → `/api/auth/verify-code`
3. **Привязка бот-аккаунта** — POST `/api/auth/link-bot` + polling `/api/auth/link-status/{id}`

## Важные детали

### Alembic на сервере
БД создавалась без Alembic — при первом запуске нужно штамповать:
```bash
docker compose run --rm web-api alembic stamp 89d86cb91e50
docker compose run --rm web-api alembic upgrade head
```

### Проблема с env_file vs environment в docker-compose
`BOT_USERNAME` не должен быть в секции `environment:` — иначе перекрывается пустым значением из shell.
Берётся напрямую из `env_file: .env`.

### Обновление docker-compose.yml на сервере
Workflows копируют файл через `scp` при каждом деплое.
Для ручного обновления: `wget -O /opt/my_bot/docker-compose.yml <url>` (одной строкой).

### Пересоздание контейнеров
`docker compose restart` НЕ перечитывает env. Использовать:
```bash
docker compose up -d --force-recreate web-api
```

### Telegram Login Widget и браузерные расширения
MetaMask и другие SES-расширения блокируют `eval` — виджет не работает в таких браузерах.
В инкогнито/другом браузере — работает.

## Nginx конфиг (сервер)
`/etc/nginx/sites-available/envato` — проксирует:
- `/api/` → `http://127.0.0.1:8080` (web-api)
- `/` → `http://127.0.0.1:3000` (frontend)

SSL: `/etc/letsencrypt/live/envato-freepik-download.store/`

## Docker образы (GHCR)
- `ghcr.io/b0gdan4eg/footagehub-media-bot:latest`
- `ghcr.io/b0gdan4eg/footagehub-ai-bot:latest`
- `ghcr.io/b0gdan4eg/footagehub-web-api:latest`
- `ghcr.io/b0gdan4eg/footagehub-frontend:latest`

## Известные особенности
- `web_api/adapters/ai_adapter.py` и `download_adapter.py` — импортируют `ai_bot` и `media_bot` lazy (внутри методов) чтобы не падать при старте
- Оба модуля (`ai_bot/`, `media_bot/`) копируются в образ web-api через Dockerfile
- POST `/api/downloads/` — со слешем в конце (иначе 307 редирект)
