# 🚀 Staging Environment - Quick Start Guide

Быстрый запуск staging окружения для тестирования FootageHub.

---

## 📋 Предварительные требования

- Docker и Docker Compose установлены
- Python 3.11+ (для запуска seed скриптов)
- Telegram аккаунты для тестирования
- Тестовые токены ботов от [@BotFather](https://t.me/BotFather)

---

## ⚙️ Шаг 1: Настройка переменных окружения

### 1.1 Скопировать .env.staging и заполнить токены

```bash
# .env.staging уже создан, откройте его и заполните:
# - MEDIA_BOT_TOKEN (создайте тестового бота через @BotFather)
# - AI_BOT_TOKEN (создайте второго тестового бота через @BotFather)
# - ADMIN (ваш Telegram user ID)
# - KIE_AI_API_KEY (ваш staging/test API ключ от Kie.ai)
```

**Как получить Telegram User ID:**
```
1. Отправьте сообщение боту @userinfobot
2. Скопируйте ваш ID
```

**Создание тестовых ботов:**
```
1. Откройте @BotFather в Telegram
2. Отправьте /newbot
3. Назовите бота (например: "FootageHub Media Staging Bot")
4. Задайте username (должен заканчиваться на "bot", например: footagehub_media_staging_bot)
5. Скопируйте полученный токен в .env.staging
6. Повторите для AI бота
```

### 1.2 Создать тестовый канал (опционально)

Для тестирования бонуса за подписку:
```
1. Создайте тестовый канал в Telegram
2. Назовите его, например: "FootageHub Staging"
3. Установите публичный username: @footagehub_staging_channel
4. Добавьте ваших ботов как администраторов канала
5. Обновите CHANNEL_ID в .env.staging
```

---

## 🐳 Шаг 2: Запуск Docker Compose

### 2.1 Собрать и запустить контейнеры

```bash
# Находясь в корне проекта
docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
```

### 2.2 Проверить статус контейнеров

```bash
docker-compose -f docker-compose.staging.yml ps
```

Ожидаемый вывод:
```
NAME                              STATUS
footagehub-staging-db             Up (healthy)
footagehub-staging-media-bot      Up
footagehub-staging-ai-bot         Up
```

### 2.3 Просмотр логов

```bash
# Все сервисы
docker-compose -f docker-compose.staging.yml logs -f

# Только MediaBot
docker-compose -f docker-compose.staging.yml logs -f media-bot

# Только AIBot
docker-compose -f docker-compose.staging.yml logs -f ai-bot

# Только БД
docker-compose -f docker-compose.staging.yml logs -f postgres
```

---

## 🗄️ Шаг 3: Инициализация базы данных

### 3.1 Применить миграции

```bash
# Войти в контейнер media-bot
docker exec -it footagehub-staging-media-bot bash

# Внутри контейнера:
alembic upgrade head

# Выйти из контейнера
exit
```

**Альтернатива (если alembic не установлен глобально):**
```bash
docker exec -it footagehub-staging-media-bot python -m alembic upgrade head
```

### 3.2 Заполнить тестовыми данными

```bash
# Запустить seed скрипт (из корня проекта на host машине)
# Убедитесь, что .env.staging загружен
docker exec -it footagehub-staging-media-bot python scripts/setup_staging_db.py
```

**Ожидаемый вывод:**
```
✅ Created 8 test users
✅ Created test subscriptions
✅ Created test referrals
✅ Created test bonuses
✅ Created test AI generation logs
✅ STAGING DATABASE READY! 🚀

📝 TEST USER CREDENTIALS:
  staging_admin        | ID: 111111111 | ADMIN | Credits: 1000/500
  test_user_1          | ID: 222222222 | USER  | Credits: 100/50
  ...
```

---

## ✅ Шаг 4: Проверка работоспособности

### 4.1 Проверить MediaBot

1. Откройте Telegram
2. Найдите вашего MediaBot по username
3. Отправьте `/start`
4. Проверьте, что:
   - Бот отвечает
   - Отображается клавиатура
   - Команда `/admin` работает (от вашего user_id)

### 4.2 Проверить AIBot

1. Найдите вашего AIBot
2. Отправьте `/start`
3. Проверьте, что:
   - Бот отвечает
   - Отображается клавиатура
   - Баланс синхронизирован с MediaBot

### 4.3 Проверить базу данных

```bash
# Подключиться к PostgreSQL
docker exec -it footagehub-staging-db psql -U postgres -d footagehub_staging

# Проверить пользователей
SELECT user_id, username, credits, ai_credits FROM users LIMIT 5;

# Проверить бонусные типы
SELECT code, name, is_active FROM bonus_types;

# Выйти
\q
```

---

## 🧪 Шаг 5: Функциональное тестирование

Следуйте тест-плану: [STAGING_TEST_PLAN.md](./STAGING_TEST_PLAN.md)

**Основные сценарии для быстрой проверки:**

### MediaBot:
- [ ] Регистрация нового пользователя (`/start`)
- [ ] Просмотр баланса
- [ ] Загрузка контента по URL (если есть тестовые URL)
- [ ] Админ-панель (`/admin`)
- [ ] Реферальная ссылка (`/referral`)

### AIBot:
- [ ] Вход существующего пользователя (`/start`)
- [ ] Просмотр баланса
- [ ] Генерация изображения (если есть API ключ)
- [ ] Генерация видео (если есть API ключ)

---

## 🛠️ Управление staging окружением

### Остановка сервисов

```bash
docker-compose -f docker-compose.staging.yml stop
```

### Перезапуск сервисов

```bash
docker-compose -f docker-compose.staging.yml restart
```

### Полная очистка (удаление контейнеров и volumes)

```bash
# ВНИМАНИЕ: Удалит все данные staging БД!
docker-compose -f docker-compose.staging.yml down -v
```

### Пересборка после изменений в коде

```bash
docker-compose -f docker-compose.staging.yml up -d --build
```

---

## 🐛 Troubleshooting

### Проблема: Контейнеры не стартуют

**Решение:**
```bash
# Проверьте логи
docker-compose -f docker-compose.staging.yml logs

# Убедитесь, что порты не заняты
netstat -an | grep 5433  # PostgreSQL
netstat -an | grep 8001  # MediaBot webhooks
```

### Проблема: БД не готова (health check fails)

**Решение:**
```bash
# Подождите 10-20 секунд после запуска
docker-compose -f docker-compose.staging.yml ps

# Проверьте логи PostgreSQL
docker-compose -f docker-compose.staging.yml logs postgres
```

### Проблема: Миграции не применяются

**Решение:**
```bash
# Проверьте DATABASE_URL
docker exec footagehub-staging-media-bot env | grep DATABASE_URL

# Проверьте доступность БД
docker exec footagehub-staging-media-bot nc -zv postgres 5432

# Примените миграции вручную
docker exec -it footagehub-staging-media-bot alembic upgrade head
```

### Проблема: Бот не отвечает

**Решение:**
```bash
# Проверьте логи бота
docker-compose -f docker-compose.staging.yml logs media-bot
# или
docker-compose -f docker-compose.staging.yml logs ai-bot

# Убедитесь, что BOT_TOKEN правильный
docker exec footagehub-staging-media-bot env | grep BOT_TOKEN

# Перезапустите контейнер
docker-compose -f docker-compose.staging.yml restart media-bot
```

### Проблема: Seed скрипт не работает

**Решение:**
```bash
# Убедитесь, что миграции применены
docker exec footagehub-staging-media-bot alembic current

# Проверьте DATABASE_URL в .env.staging
cat .env.staging | grep DATABASE_URL

# Запустите скрипт с логированием
docker exec -it footagehub-staging-media-bot python scripts/setup_staging_db.py
```

---

## 📊 Мониторинг

### Просмотр использования ресурсов

```bash
docker stats
```

### Проверка дискового пространства

```bash
docker system df
```

### Просмотр сетевых соединений

```bash
docker network inspect footagehub-staging-network
```

---

## 🔐 Безопасность

**ВАЖНО:**
- ❌ НЕ используйте production токены в staging!
- ❌ НЕ коммитьте .env.staging с реальными ключами в Git!
- ✅ Используйте sandbox режимы для платежных систем (WEBPAY_SANDBOX=true)
- ✅ Используйте отдельные тестовые API ключи
- ✅ Убедитесь, что staging боты имеют разные usernames от production

---

## 📝 Следующие шаги

После успешного запуска staging:

1. Выполните все тест-кейсы из [STAGING_TEST_PLAN.md](./STAGING_TEST_PLAN.md)
2. Задокументируйте найденные баги
3. Исправьте критические баги
4. Проведите load testing
5. Обновите [MICROSERVICES_ARCHITECTURE_PLAN.md](./MICROSERVICES_ARCHITECTURE_PLAN.md)
6. Подготовьтесь к production deployment

---

## 📞 Получение помощи

Если возникли проблемы:
1. Проверьте [Troubleshooting](#-troubleshooting) выше
2. Изучите логи: `docker-compose -f docker-compose.staging.yml logs -f`
3. Проверьте документацию: [docs/](./README.md)

---

**Дата последнего обновления:** 2025-12-30
