# 🧪 Staging Environment - Quick Reference

Быстрая справка по работе со staging окружением FootageHub.

---

## 🚀 Быстрый старт

### 1. Первичная настройка

**Linux/macOS:**
```bash
# 1. Заполните .env.staging реальными токенами
#    (создайте тестовых ботов через @BotFather)

# 2. Запустите staging окружение
make staging-init
```

**Windows (PowerShell):**
```powershell
# 1. Заполните .env.staging реальными токенами

# 2. Разрешите выполнение скриптов (один раз)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. Запустите staging окружение
.\staging.ps1 init

# Или напрямую через Docker:
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
```

Эта команда:
- Собирает Docker образы
- Запускает контейнеры (DB, MediaBot, AIBot)
- Применяет миграции
- Заполняет БД тестовыми данными

### 2. Проверка статуса

**Linux/macOS:**
```bash
make staging-ps     # Статус контейнеров
make staging-logs   # Логи
```

**Windows:**
```powershell
.\staging.ps1 ps      # Статус контейнеров
.\staging.ps1 logs    # Логи
```

### 3. Тестирование

Откройте ваших staging ботов в Telegram и следуйте [тест-плану](docs/STAGING_TEST_PLAN.md).

---

## 📖 Основные команды

### Linux/macOS (Makefile)

```bash
# Управление
make staging-up        # Запустить
make staging-down      # Остановить
make staging-restart   # Перезапустить
make staging-rebuild   # Пересобрать

# Логи
make staging-logs         # Все логи
make staging-logs-media   # MediaBot
make staging-logs-ai      # AIBot
make staging-logs-db      # PostgreSQL

# База данных
make staging-migrate   # Применить миграции
make staging-seed      # Заполнить тестовыми данными
make staging-shell-db  # PostgreSQL shell

# Shell доступ
make staging-shell-media  # Bash в MediaBot
make staging-shell-ai     # Bash в AIBot

# Очистка
make staging-clean     # Удалить всё (с подтверждением)
```

### Windows (PowerShell)

```powershell
# Управление
.\staging.ps1 up        # Запустить
.\staging.ps1 down      # Остановить
.\staging.ps1 restart   # Перезапустить
.\staging.ps1 rebuild   # Пересобрать

# Логи
.\staging.ps1 logs         # Все логи
.\staging.ps1 logs-media   # MediaBot
.\staging.ps1 logs-ai      # AIBot
.\staging.ps1 logs-db      # PostgreSQL

# База данных
.\staging.ps1 migrate   # Применить миграции
.\staging.ps1 seed      # Заполнить тестовыми данными
.\staging.ps1 shell-db  # PostgreSQL shell

# Shell доступ
.\staging.ps1 shell-media  # Bash в MediaBot
.\staging.ps1 shell-ai     # Bash в AIBot

# Очистка
.\staging.ps1 clean     # Удалить всё (с подтверждением)
```

---

## 👥 Тестовые пользователи

| Username | User ID | Роль | Credits | AI Credits |
|----------|---------|------|---------|------------|
| staging_admin | 111111111 | ADMIN | 1000 | 500 |
| test_user_1 | 222222222 | USER | 100 | 50 |
| test_user_2 | 333333333 | USER | 50 | 25 |
| poor_user | 555555555 | USER | 0 | 0 |
| vip_user | 666666666 | USER + Sub | 500 | 200 |
| referrer | 777777777 | USER | 200 | 100 |

---

## 📚 Документация

- **Quick Start:** [docs/STAGING_QUICKSTART.md](docs/STAGING_QUICKSTART.md)
- **Тест-план:** [docs/STAGING_TEST_PLAN.md](docs/STAGING_TEST_PLAN.md) (42 кейса)
- **Phase Summary:** [docs/PHASE_5_SUMMARY.md](docs/PHASE_5_SUMMARY.md)
- **Архитектура:** [docs/MICROSERVICES_ARCHITECTURE_PLAN.md](docs/MICROSERVICES_ARCHITECTURE_PLAN.md)

---

## 🔧 Troubleshooting

### Бот не отвечает
```bash
# Проверьте логи
make staging-logs-media
# или
make staging-logs-ai

# Перезапустите контейнер
make staging-restart
```

### База данных не готова
```bash
# Подождите 10-20 секунд после старта
make staging-ps

# Проверьте логи
make staging-logs-db
```

### Миграции не применяются
```bash
# Примените вручную
make staging-migrate
```

Подробнее: [docs/STAGING_QUICKSTART.md#troubleshooting](docs/STAGING_QUICKSTART.md#-troubleshooting)

---

## ⚠️ Важно

- ❌ НЕ используйте production токены!
- ❌ НЕ коммитьте .env.staging с реальными ключами!
- ✅ Используйте sandbox режимы (WEBPAY_SANDBOX=true)
- ✅ Используйте отдельные тестовые боты

---

## 🎯 Следующие шаги

1. ✅ Настроить .env.staging
2. ✅ Запустить окружение (`make staging-init`)
3. ⏳ Выполнить функциональное тестирование
4. ⏳ Задокументировать баги
5. ⏳ Исправить критические баги
6. ⏳ Performance testing
7. ⏳ Production deployment

---

**Версия:** 1.0
**Дата:** 2025-12-30
