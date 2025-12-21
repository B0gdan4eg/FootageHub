# FootageHub Bot

Telegram бот для скачивания медиа-файлов с Envato Elements и Freepik.

## Возможности

- 📥 Скачивание с Envato Elements
- 🎨 Скачивание с Freepik
- 💳 Система кредитов
- 📊 Статистика скачиваний
- 🔄 Автоматические бэкапы БД
- 🧹 Автоочистка Playwright кэша

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <your-repo-url>
cd FootageHub
```

### 2. Настройка окружения

Создайте файл `.env`:

```env
BOT_TOKEN=your_bot_token
DATABASE_URL=postgresql://user:password@db:5432/dbname
POSTGRES_DB=footagehub
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### 3. Запуск локально (для разработки)

```bash
# Установить зависимости
pip install -r requirements.txt

# Установить Playwright browsers
python -m playwright install chromium

# Запустить бота
python main.py
```

### 4. Запуск в Docker

```bash
docker-compose up -d
```

## Настройка на сервере с Xvfb (для Freepik)

Freepik блокирует headless браузеры, поэтому на сервере нужен Xvfb (виртуальный дисплей).

### Автоматическая установка

```bash
# На сервере выполните:
chmod +x scripts/setup_xvfb.sh
sudo ./scripts/setup_xvfb.sh
```

### Ручная установка

См. подробную инструкцию в [SERVER_SETUP.md](SERVER_SETUP.md)

### После установки Xvfb

```bash
# Перезапустить контейнеры
cd /path/to/FootageHub
docker-compose down
docker-compose pull
docker-compose up -d

# Проверить логи
docker-compose logs -f bot
```

## Структура проекта

```
FootageHub/
├── bot/                    # Основной код бота
│   ├── handlers/          # Обработчики команд
│   ├── services.py        # Сервисы бота
│   └── schedule_tasks.py  # Планировщик задач
├── db/                    # База данных
│   ├── models.py          # Модели SQLAlchemy
│   └── *_crud.py          # CRUD операции
├── envato_utils/          # Утилиты для Envato
│   ├── envato_playwright.py
│   ├── envato_cookies.json
│   └── cleanup_playwright.py
├── freepik_utils/         # Утилиты для Freepik
│   ├── freepik.py         # Основной downloader
│   ├── freepik_cookies.json
│   ├── debug_download.py  # Отладка
│   └── convert_cookies.py # Конвертация cookies
├── scripts/               # Скрипты установки
│   └── setup_xvfb.sh      # Установка Xvfb
├── docker-compose.yml     # Docker композиция
├── Dockerfile             # Docker образ
├── requirements.txt       # Python зависимости
└── main.py               # Точка входа

```

## Получение cookies

### Для Envato:

1. Установите расширение [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/)
2. Авторизуйтесь на elements.envato.com
3. Экспортируйте cookies в JSON
4. Конвертируйте: `python envato_utils/convert_cookies.py`
5. Сохраните в `envato_utils/envato_cookies.json`

### Для Freepik:

1. Установите расширение [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/)
2. Авторизуйтесь на www.freepik.com
3. Экспортируйте cookies в JSON
4. Конвертируйте: `python freepik_utils/convert_cookies.py`
5. Сохраните в `freepik_utils/freepik_cookies.json`

## Настройка планировщика

Бот автоматически выполняет:

- **03:00** - Ежедневное начисление кредитов (5 кредитов всем пользователям)
- **04:00** - Ежедневный бэкап базы данных
- **Каждые 6 часов** - Очистка Playwright кэша

Настройки в `main.py:77-84`

## Команды бота

- `/start` - Начать работу с ботом
- `/envato` - Скачать с Envato Elements
- `/freepik` - Скачать с Freepik
- `/info` - Информация о боте
- `/admin` - Админ панель (только для админов)

## Troubleshooting

### Ошибка "Cannot open display :99"

```bash
# Проверьте что Xvfb запущен
sudo systemctl status xvfb

# Проверьте права на сокет
sudo chmod 1777 /tmp/.X11-unix
```

### Ошибка "Playwright browser not found"

```bash
# В контейнере выполните
docker-compose exec bot python -m playwright install chromium
docker-compose exec bot python -m playwright install-deps chromium
```

### Ошибка с cookies

```bash
# Проверьте формат cookies
python freepik_utils/check_cookies.py
python freepik_utils/convert_cookies.py
```

## Мониторинг

### Логи

```bash
# Все логи
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Xvfb
sudo journalctl -u xvfb -f
```

### Проверка работы

```bash
# Проверить DISPLAY в контейнере
docker-compose exec bot env | grep DISPLAY

# Тест Envato
docker-compose exec bot python envato_utils/envato_playwright.py

# Тест Freepik
docker-compose exec bot python freepik_utils/freepik.py
```

## Разработка

### Добавление нового провайдера

1. Создайте директорию `provider_utils/`
2. Создайте `provider_playwright.py` аналогично Envato
3. Добавьте обработчики в `bot/handlers/download.py`
4. Добавьте состояние в `bot/state.py`

### Запуск тестов

```bash
# Тест Envato
python envato_utils/test_env.py

# Тест Freepik
python freepik_utils/freepik.py

# Отладка Freepik
python freepik_utils/debug_download.py
```

## Лицензия

Этот проект предназначен для образовательных целей.

## Поддержка

Для вопросов и предложений: [@footage_hub_support](https://t.me/footage_hub_support)