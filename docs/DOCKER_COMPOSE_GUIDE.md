# Docker Compose Configuration Guide

Полное объяснение файла `docker-compose.yml` для проекта FootageHub.

---

## Общая структура

```yaml
services:
```
- Начало определения сервисов (контейнеров)

---

## 1. MediaBot (основной бот для загрузок)

### Базовая конфигурация

```yaml
  # MediaBot - Main bot for Envato/Freepik downloads
  bot:
```
- **Комментарий** описывает назначение сервиса
- **`bot:`** - имя сервиса (можно обращаться через `docker compose up bot`)

```yaml
    image: ghcr.io/b0gdan4eg/footagehub:latest
```
- **Docker образ** который будет использован
- `ghcr.io` = GitHub Container Registry
- `b0gdan4eg` = username в GitHub
- `footagehub:latest` = название образа и тег

```yaml
    container_name: footagehub-media-bot
```
- **Имя контейнера** в Docker (вместо случайного имени)
- Полезно для логов: `docker logs footagehub-media-bot`

```yaml
    restart: always
```
- **Политика перезапуска**: всегда перезапускать контейнер при:
  - Падении контейнера
  - Перезагрузке сервера
  - Ошибках выполнения

### Переменные окружения

```yaml
    env_file: .env
```
- **Загрузить переменные окружения** из файла `.env`
- Все переменные из `.env` станут доступны в контейнере

```yaml
    depends_on:
      db:
        condition: service_healthy
```
- **Зависимость от другого сервиса**: не запускать пока база данных не будет здорова
- `service_healthy` = ждет пока healthcheck БД не вернет success
- Гарантирует что БД готова принимать подключения

```yaml
    environment:
      DATABASE_URL: ${DATABASE_URL}
      PYTHONUNBUFFERED: 1
      DISPLAY: :99
```
- **Переопределение переменных окружения** (приоритет над `.env`)
- `${DATABASE_URL}` - подставит значение из `.env` или системных переменных
- `PYTHONUNBUFFERED: 1` - Python выводит логи сразу (без буферизации)
- `DISPLAY: :99` - для Playwright/браузеров (виртуальный X-сервер)

### Сетевые настройки

```yaml
    ports:
     - "127.0.0.1:8000:8000"
     - "127.0.0.1:8443:8443"
```
- **Проброс портов** контейнера на хост
- Формат: `"хост_ip:хост_порт:контейнер_порт"`
- `127.0.0.1` = только локальный доступ (не из интернета)
- `8000` - WebPay webhooks
- `8443` - CryptoBot webhooks

```yaml
    networks:
      - footagehub-network
```
- **Подключение к сети** `footagehub-network`
- Позволяет контейнерам общаться друг с другом по именам сервисов
- Пример: `postgresql://user:pass@db:5432/footagehub`

### Тома (volumes)

```yaml
    volumes:
    # Убрали SSL сертификаты - их обрабатывает Nginx
    - ./backups:/app/backups
    - /tmp/.X11-unix:/tmp/.X11-unix:rw
```
- **Монтирование директорий** с хоста в контейнер
- `./backups:/app/backups` - локальная папка `backups` → `/app/backups` в контейнере
- `/tmp/.X11-unix:/tmp/.X11-unix:rw` - X-сервер для Playwright (read-write доступ)

---

## 2. AIBot (AI генерация контента)

### Базовая конфигурация

```yaml
  # AIBot - AI content generation (isolated)
  ai-bot:
    image: ghcr.io/b0gdan4eg/footagehub-ai:latest
    container_name: footagehub-ai-bot
    restart: always
    env_file: .env
```
- Аналогично MediaBot, но **отдельный образ**: `footagehub-ai:latest`
- **Изоляция**: свой контейнер, свой образ, можно разрабатывать независимо

### Зависимости

```yaml
    depends_on:
      db:
        condition: service_healthy
```
- Также ждет готовности БД перед запуском

### Переменные окружения

```yaml
    environment:
      DATABASE_URL: ${DATABASE_URL}
      AI_BOT_TOKEN: ${AI_BOT_TOKEN}
      KIE_AI_API_KEY: ${KIE_AI_API_KEY}
      ADMIN: ${ADMIN}
      CHANNEL_ID: ${CHANNEL_ID}
      PYTHONUNBUFFERED: 1
```
- **Отдельный токен бота**: `AI_BOT_TOKEN` (не конфликтует с MediaBot)
- `KIE_AI_API_KEY` - ключ для AI провайдера Kie.ai
- **Общие с MediaBot**: `DATABASE_URL`, `ADMIN`, `CHANNEL_ID`

### Тома

```yaml
    volumes:
      - ./ai_generations:/app/ai_generations
```
- **Папка для AI генераций**: сохраняет результаты на хосте
- Если контейнер удалится, сгенерированные файлы останутся

### Сеть

```yaml
    networks:
      - footagehub-network
```
- В той же сети, что и MediaBot + DB
- Контейнеры могут общаться друг с другом

### Health Check

```yaml
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import sys; sys.exit(0)'"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```
- **Проверка здоровья** контейнера
- `test:` - команда для проверки (запуск Python)
- `interval: 30s` - проверять каждые 30 секунд
- `timeout: 10s` - команда должна завершиться за 10 секунд
- `retries: 3` - 3 неудачные попытки = контейнер unhealthy
- `start_period: 10s` - первые 10 секунд не считать как ошибку (время на прогрев)

---

## 3. PostgreSQL Database

### Базовая конфигурация

```yaml
  db:
    image: postgres:15
```
- **Официальный образ PostgreSQL** версии 15 с Docker Hub

```yaml
    container_name: footagehub-db
    restart: always
```
- Имя контейнера + политика автоперезапуска

### Переменные окружения

```yaml
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```
- **Настройки PostgreSQL**:
  - `POSTGRES_DB` - имя базы данных (по умолчанию создается при первом запуске)
  - `POSTGRES_USER` - имя пользователя БД
  - `POSTGRES_PASSWORD` - пароль для подключения

### Персистентность данных

```yaml
    volumes:
      - pgdata:/var/lib/postgresql/data
```
- **Именованный volume** `pgdata` для хранения данных БД
- `/var/lib/postgresql/data` - стандартная папка PostgreSQL для данных
- **Важно**: данные сохраняются даже при удалении контейнера!

### Сетевые настройки

```yaml
    ports:
      - "127.0.0.1:15432:5432"
```
- **Проброс порта БД** наружу
- `15432` на хосте → `5432` в контейнере (стандартный порт PostgreSQL)
- `127.0.0.1` = только локальный доступ (безопасность)
- Можно подключиться с хоста: `psql -h 127.0.0.1 -p 15432 -U user -d footagehub`

```yaml
    networks:
      - footagehub-network
```
- В общей сети с ботами

### Health Check

```yaml
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
```
- **Проверка готовности БД**: команда `pg_isready`
- Проверяет каждые **5 секунд** (быстрее чем у ботов)
- Используется в `depends_on.condition: service_healthy`
- БД считается здоровой когда может принимать подключения

---

## 4. Networks (сети)

```yaml
networks:
  footagehub-network:
    driver: bridge
```
- **Создание пользовательской сети** `footagehub-network`
- `driver: bridge` - стандартный драйвер Docker (контейнеры в одной локальной сети)

### Преимущества пользовательской сети:
1. **DNS резолвинг**: контейнеры видят друг друга по именам сервисов
   - Можно обращаться: `http://bot:8000`, `postgresql://db:5432`
2. **Изоляция**: контейнеры изолированы от других Docker сетей
3. **Безопасность**: внешние контейнеры не могут подключиться
4. **Легкая настройка**: не нужно прописывать IP адреса

---

## 5. Volumes (именованные тома)

```yaml
volumes:
  pgdata:
```
- **Создание именованного volume** `pgdata`
- Docker сам управляет этим volume (обычно в `/var/lib/docker/volumes/`)
- **Персистентность**: данные сохраняются между:
  - `docker compose down` и `docker compose up`
  - Пересборкой контейнеров
  - Обновлениями образов

### Отличие от bind mounts:
- **Named volume** (`pgdata:`): управляется Docker, оптимизирован для производительности
- **Bind mount** (`./backups:/app/backups`): прямое монтирование папки с хоста

---

## Архитектура системы

```
┌─────────────────────────────────────────────────────────┐
│          footagehub-network (bridge)                    │
│                                                         │
│  ┌───────────────────┐       ┌───────────────────┐     │
│  │    MediaBot       │       │      AIBot        │     │
│  │  (bot container)  │       │ (ai-bot container)│     │
│  │                   │       │                   │     │
│  │  Ports:           │       │  No exposed ports │     │
│  │  - 8000 (WebPay)  │       │                   │     │
│  │  - 8443 (Crypto)  │       │                   │     │
│  └─────────┬─────────┘       └─────────┬─────────┘     │
│            │                           │               │
│            │    ┌──────────────────────┘               │
│            │    │                                      │
│            ▼    ▼                                      │
│     ┌──────────────────┐                               │
│     │   PostgreSQL     │                               │
│     │  (db container)  │                               │
│     │                  │                               │
│     │  Port: 15432     │                               │
│     └──────────────────┘                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
                    │          │          │
                    ▼          ▼          ▼
             ┌──────────┐ ┌────────┐ ┌─────────────┐
             │ backups/ │ │ pgdata │ │ai_generations│
             │(на хосте)│ │(volume)│ │  (на хосте) │
             └──────────┘ └────────┘ └─────────────┘
```

---

## Основные принципы дизайна

1. ✅ **Изоляция сервисов**: каждый бот в своем контейнере
2. ✅ **Общая база данных**: через одну сеть и один PostgreSQL
3. ✅ **Автовосстановление**: `restart: always` для всех сервисов
4. ✅ **Безопасность**: порты доступны только на `127.0.0.1`
5. ✅ **Персистентность данных**: volumes для БД и генераций
6. ✅ **Health checks**: проверка готовности сервисов
7. ✅ **Зависимости**: правильный порядок запуска через `depends_on`

---

## Полезные команды

### Управление контейнерами

```bash
# Запустить все сервисы
docker compose up -d

# Запустить только MediaBot и БД (без AI бота)
docker compose up -d bot db

# Запустить только AI бот
docker compose up -d ai-bot

# Остановить все сервисы
docker compose down

# Перезапустить AI бот
docker compose restart ai-bot

# Просмотр логов
docker compose logs -f ai-bot
docker compose logs -f bot
docker compose logs -f db

# Статус сервисов
docker compose ps

# Проверка health check
docker inspect footagehub-ai-bot | grep -A 10 Health
```

### Управление данными

```bash
# Удалить все (включая volumes)
docker compose down -v

# Бэкап БД
docker exec footagehub-db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql

# Восстановление БД
cat backup.sql | docker exec -i footagehub-db psql -U $POSTGRES_USER -d $POSTGRES_DB
```

### Обновление образов

```bash
# Скачать новые образы
docker compose pull

# Пересобрать и перезапустить
docker compose up -d --build

# Обновить только AI бот
docker compose pull ai-bot
docker compose up -d ai-bot
```

---

## Troubleshooting

### AI бот не запускается

```bash
# Проверить логи
docker compose logs ai-bot

# Проверить переменные окружения
docker exec footagehub-ai-bot env | grep AI_BOT_TOKEN

# Проверить health check
docker inspect footagehub-ai-bot --format='{{json .State.Health}}'
```

### База данных не готова

```bash
# Проверить статус healthcheck
docker compose ps db

# Проверить логи
docker compose logs db

# Подключиться к БД вручную
docker exec -it footagehub-db psql -U $POSTGRES_USER -d $POSTGRES_DB
```

### Сетевые проблемы

```bash
# Проверить сеть
docker network inspect footagehub-network

# Проверить можно ли достучаться до БД из бота
docker exec footagehub-ai-bot ping db
```

---

## Переменные окружения (.env)

### Обязательные для MediaBot:
- `BOT_TOKEN` - токен MediaBot
- `DATABASE_URL` - строка подключения к БД
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - настройки БД

### Обязательные для AIBot:
- `AI_BOT_TOKEN` - токен AIBot
- `KIE_AI_API_KEY` - ключ Kie.ai API
- `DATABASE_URL` - строка подключения к БД (та же что и для MediaBot)

### Общие:
- `ADMIN` - Telegram ID администратора
- `CHANNEL_ID` - ID канала для бонусной системы

---

## Примечания по безопасности

1. **Порты**: привязаны к `127.0.0.1` - недоступны извне
2. **Secrets**: хранятся в `.env`, не коммитятся в Git
3. **Сеть**: изолированная bridge сеть
4. **Volumes**: данные БД не доступны напрямую через HTTP
5. **Health checks**: автоматическая проверка состояния сервисов

---

## История изменений

- **2025-12-25**: Добавлен AIBot сервис с изоляцией
- **2025-12-25**: Добавлена кастомная сеть `footagehub-network`
- **2025-12-25**: Добавлены health checks для AI бота
