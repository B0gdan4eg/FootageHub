# FootageHub — Веб-версия: Прогресс реализации

## Домен
`envato-freepik-download.store`

## Стек
- **Frontend**: Next.js 14 (App Router, TypeScript, Tailwind CSS) — `FootageHub/frontend/`
- **Backend**: FastAPI (Python) — `FootageHub/web_api/`
- **БД**: PostgreSQL (существующая, общая с ботами)
- **SMS**: SMSC.ru (верификация телефона)
- **Auth**: JWT (7 дней) в cookie

---

## ✅ ВЫПОЛНЕНО

### 1. Исправления shared/ (разблокируют web_api от импортов ботов)
- `shared/db/session.py:6` — убрал `from media_bot.config import DATABASE_URL`, заменил на `os.getenv("DATABASE_URL")`
- `shared/db/repositories/subscription_repository.py:13` — убрал `from media_bot.handlers.messages import msg`, заменил 3 вызова на строки

### 2. Изменения моделей БД (`shared/db/models.py`)
- `User.tg_id` → `nullable=True` (web-пользователи без Telegram)
- Добавлено поле `User.phone_number = Column(String(20), unique=True, index=True, nullable=True)`
- Новая модель `SmsVerification` (хранение SMS-кодов с TTL 5 мин)
- Новая модель `BotLinkRequest` (запросы привязки бот-аккаунта к web)

### 3. Новые методы в `shared/db/repositories/user_repository.py`
- `get_by_phone(phone: str)` — поиск по номеру телефона
- `get_or_create_by_phone(phone, username)` → `(user, created: bool)`
- `get_by_referral_code(code)` — уже был, проверен

### 4. Alembic миграция
- Файл: `migrations/versions/a1b2c3d4e5f6_add_web_auth.py`
- down_revision: `89d86cb91e50`
- Операции: tg_id nullable, phone_number + unique index, таблица sms_verifications, enum + таблица bot_link_requests

### 5. web_api/ — FastAPI-сервис (порт 8080)
```
web_api/
├── __init__.py
├── config.py          — все env переменные
├── dependencies.py    — get_db(), get_current_user(), get_admin_user()
├── main.py            — FastAPI app, CORS, роутеры
├── auth/
│   ├── __init__.py
│   ├── jwt_handler.py  — create_access_token(), decode_token()
│   ├── sms_client.py   — send_verification_sms(), verify_sms_code() (SMSC.ru)
│   └── router.py       — /send-code, /verify-code, /link-bot, /link-status, /me
├── routers/
│   ├── __init__.py
│   ├── users.py        — /me, /me/downloads, /me/subscriptions, /me/ai-generations
│   ├── downloads.py    — POST /, GET /file/{token}
│   ├── ai.py           — /pricing, /generate, /status/{task_id}, /history
│   ├── payments.py     — /plans, /create, /webhook/cryptobot, /webhook/webpay, /history
│   └── admin.py        — /users, /users/{id}, PATCH /users/{id}, /stats
└── adapters/
    ├── __init__.py
    ├── download_adapter.py  — WebDownloadAdapter (обёртка над media_bot downloaders)
    └── ai_adapter.py        — WebAIAdapter (обёртка над ai_bot AIService, async tasks)
```

### 6. media_bot/handlers/link_account.py
- Callback-хендлер для `link_confirm:{request_id}` и `link_reject:{request_id}`
- При подтверждении: переносит phone_number из web_user → bot_user, объединяет кредиты
- Подключён в `media_bot/main.py` (dp.include_router(link_account.router))

### 7. frontend/ — Next.js 14
```
frontend/
├── .env.local           — NEXT_PUBLIC_API_URL=https://envato-freepik-download.store/api
├── src/
│   ├── middleware.ts    — защита маршрутов, редирект на /auth
│   ├── lib/
│   │   ├── api.ts       — axios-клиент + authApi, usersApi, downloadsApi, aiApi, paymentsApi, adminApi
│   │   └── auth.ts      — setToken(), clearToken(), getToken(), isAuthenticated()
│   └── app/
│       ├── layout.tsx   — обновлён title/description
│       └── page.tsx     — ✅ Лендинг готов (Hero, Features, Pricing, CTA, Footer)
```

---

## ✅ ВЫПОЛНЕНО (продолжение)

### 8. Frontend страницы (все в `frontend/src/app/`)
- `auth/page.tsx` — телефон с маской, 6-инпутов для кода, таймер 60 сек, привязка бота по реф-коду + polling
- `dashboard/page.tsx` — баланс кредитов/AI, активные подписки с прогресс-баром, последние 5 скачиваний
- `download/page.tsx` — URL-поле с авто-определением платформы, индикатор прогресса, кнопка скачивания
- `ai/page.tsx` — табы IMAGE/VIDEO/IMAGE_TO_VIDEO, провайдеры из API, polling каждые 4 сек, превью результата
- `payment/page.tsx` — карточки тарифов из API, выбор WebPay/CryptoBot, редирект на invoice URL
- `admin/page.tsx` — статистика, таблица пользователей с поиском/пагинацией, модал редактирования

### 9. Инфраструктура
- `docker-compose.yml` — добавлены сервисы `web-api`, `frontend`, `nginx`
- `nginx/nginx.conf` — `/api/` → web-api:8080, `/` → frontend:3000, HTTPS, rate limiting на auth

---

## 🔄 ОСТАЛОСЬ СДЕЛАТЬ

### Деплой
- Добавить в `.env`: `JWT_SECRET_KEY`, `SMSC_LOGIN`, `SMSC_PASSWORD`, `SMSC_SENDER=FOOTAGE`, `CORS_ORIGINS=https://envato-freepik-download.store`
- SSL сертификаты → `nginx/ssl/fullchain.pem` + `nginx/ssl/privkey.pem` (certbot)
- Собрать и запушить Docker-образы `web-api` и `frontend` (или заменить `image:` на `build:` в compose)
- Добавить в `requirements.txt`: `python-jose[cryptography]==3.3.0`

### Мелкие детали
- Проверить что `SubscriptionRepository.has_active_subscription()` и `increment_usage()` существуют (используются в download_adapter.py)
- Проверить что `SubscriptionRepository.create_subscription_from_plan()` существует (используется в payments.py)

---

## Архитектура флоу привязки аккаунта

```
1. Web: POST /api/auth/link-bot {referral_code}
   → Найти бот-юзера по реф-коду
   → Создать BotLinkRequest {PENDING, TTL 10 мин}
   → Отправить сообщение в Telegram: [✅ Да] [❌ Нет]
   → Вернуть {request_id}

2. Bot: пользователь нажимает "Да"
   → callback link_confirm:{request_id}
   → BotLinkRequest.status = CONFIRMED
   → bot_user.phone_number = web_user.phone_number
   → Объединить кредиты

3. Web: GET /api/auth/link-status/{request_id} (polling каждые 3 сек)
   → status=CONFIRMED → получить новый JWT для bot_user.id → обновить cookie
```

---

## Переменные окружения для добавления в .env

```env
# Web API
JWT_SECRET_KEY=<сгенерировать: openssl rand -hex 32>
SMSC_LOGIN=<логин SMSC.ru>
SMSC_PASSWORD=<пароль SMSC.ru>
SMSC_SENDER=FOOTAGE
CORS_ORIGINS=https://envato-freepik-download.store

# Уже есть (используются web_api)
BOT_TOKEN=...
DATABASE_URL=...
KIE_AI_API_KEY=...
WEBPAY_RESOURCE_ID=...
WEBPAY_SIGNING_KEY=...
CRYPTO_BOT_API_KEY=...
```

## Запуск web_api локально
```bash
cd FootageHub
uvicorn web_api.main:app --host 0.0.0.0 --port 8080 --reload
```

## Запуск frontend локально
```bash
cd FootageHub/frontend
npm run dev
# Откроется на http://localhost:3000
```
