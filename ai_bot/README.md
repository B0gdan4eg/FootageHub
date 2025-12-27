# AI Bot

AI контент-генерация через Telegram бот с использованием Kie.ai API

## Функционал

### Генерация изображений
- **Провайдер**: Google Nano Banana Pro через Kie.ai
- **Стоимость**: 4 AI кредита ($0.02)
- **Параметры**:
  - Aspect Ratio: 1:1, 16:9, 9:16, 4:3, и др.
  - Resolution: 1K, 2K, 4K
  - Output Format: PNG, JPG

### Генерация видео
- **Провайдеры**:
  - Kling 2.6 (с поддержкой звука) - 100 кредитов ($0.50)
  - VEO 3.1 Fast (Google) - 80 кредитов ($0.40)
  - VEO 3.1 Quality (Google) - 400 кредитов ($2.00)
- **Параметры**:
  - Aspect Ratio: 1:1, 16:9, 9:16
  - Duration: 5 или 10 секунд
  - Sound: Да/Нет (только Kling)
  - Image-to-video: Поддержка референсных изображений

## Структура проекта

```
ai_bot/
├── providers/              # AI провайдеры
│   ├── base.py            # AbstractAIProvider
│   ├── kie_ai_client.py   # Базовый клиент Kie.ai API
│   ├── nano_banana.py     # Генерация изображений
│   ├── kling.py           # Генерация видео (Kling 2.6)
│   └── veo.py             # Генерация видео (VEO 3.1)
│
├── services/              # Бизнес-логика
│   ├── ai_service.py      # Основной сервис AI генерации
│   ├── credit_manager.py  # Управление AI кредитами
│   └── pricing_service.py # Управление ценами и балансом Kie.ai
│
├── handlers/              # Telegram handlers
│   ├── start.py           # Стартовые команды
│   ├── credits.py         # Проверка баланса и цен
│   ├── image_generation.py # Генерация изображений
│   └── video_generation.py # Генерация видео
│
├── middlewares/           # Middleware (пока пусто)
├── state.py               # FSM состояния
├── config.py              # Конфигурация
└── main.py                # Точка входа
```

## Архитектура

### Provider Pattern
Все AI провайдеры реализуют интерфейс `AbstractAIProvider`:
- `generate()` - генерация контента
- `check_status()` - проверка статуса задачи
- `get_cost()` - стоимость в AI кредитах

### Service Layer
- **AIService** - координирует провайдеры, управляет процессом генерации
- **CreditManager** - управление балансом AI кредитов пользователей
- **PricingService** - управление ценами моделей и балансом Kie.ai (с кэшированием)

### FSM States
- **ImageGenerationStates** - flow генерации изображений
- **VideoGenerationStates** - flow генерации видео

## Команды бота

- `/start` - Приветствие и главное меню
- `/help` - Справка
- `/balance` или `/credits` - Просмотр баланса AI кредитов (включая Kie.ai баланс)
- `/pricing` - Показать актуальные цены на все модели
- `/image` - Генерация изображения
- `/video` - Генерация видео
- `/cancel` - Отмена текущей операции

## Интеграция с базой данных

Бот использует shared database модели:
- `User.ai_credits` - доступные AI кредиты
- `User.ai_credits_used` - потраченные AI кредиты

## Конфигурация

Переменные окружения (`.env`):
```env
AI_BOT_TOKEN=your_bot_token
KIE_AI_API_KEY=your_kie_ai_key
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
ADMIN=123456789
CHANNEL_ID=@your_channel
```

## Стоимость генерации

Цены основаны на актуальных ценах Kie.ai (2025):

### Изображения
- **Nano Banana Pro**: 4 кредита ($0.02)
- **Seedream 4.0**: 4 кредита ($0.02)
- **Midjourney**: 2 кредита ($0.01)

### Видео
- **Kling 2.6**: 100 кредитов ($0.50)
- **VEO 3.1 Fast**: 80 кредитов ($0.40)
- **VEO 3.1 Quality**: 400 кредитов ($2.00)

*1 кредит Kie.ai = $0.005 (0.5¢)*

Цены получаются динамически через `PricingService` с кэшированием баланса Kie.ai на 5 минут.

## Особенности

### Dynamic Pricing System
- Цены на модели хранятся в `PricingService` на основе документации Kie.ai
- Баланс Kie.ai получается через API и кэшируется на 5 минут
- Провайдеры автоматически используют актуальные цены
- Конвертация кредитов в USD для удобного отображения

### Refund System
Если генерация не удалась, кредиты автоматически возвращаются пользователю.

### Adaptive Polling
Система адаптивно проверяет статус генерации:
- Первые 30с - каждые 2с
- 30-120с - каждые 5с
- После 120с - каждые 10с

### Error Handling
Все ошибки Kie.ai API обрабатываются с user-friendly сообщениями:
- 402 - Недостаточно кредитов на Kie.ai
- 401 - Неверный API ключ
- 429 - Превышен лимит запросов

### Kie.ai API Integration
- `GET /api/v1/chat/credit` - получение баланса Kie.ai кредитов
- Автоматическое кэширование для снижения нагрузки на API
- Fallback на статические цены при недоступности API

## Запуск

```bash
python -m ai_bot.main
```

Или через Docker:
```bash
docker-compose up ai-bot
```

## TODO

- [ ] Добавить логирование генераций в `AIGenerationLog`
- [ ] Реализовать middleware для проверки AI credits
- [ ] Добавить admin панель для управления AI кредитами
- [ ] Интеграция с payment системой для покупки AI кредитов
- [ ] Добавить queue для обработки нескольких генераций
- [ ] Поддержка image editing в Nano Banana
- [ ] WebHook callbacks для async уведомлений о завершении генерации
