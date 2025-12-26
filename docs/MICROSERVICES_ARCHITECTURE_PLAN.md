# План миграции на микросервисную архитектуру

## ⚠️ ВАЖНОЕ ПРАВИЛО РАЗРАБОТКИ

**СТРОГО ЗАПРЕЩЕНО** отклоняться от этого плана без предварительного согласования!

Перед любым отклонением от плана необходимо:
1. Объяснить причину отклонения
2. Предоставить альтернативное решение
3. Обосновать преимущества альтернативы
4. Получить явное подтверждение от владельца проекта

Все, что написано в этом плане, является **обязательным к исполнению**. Любые изменения должны быть задокументированы и одобрены.

---

## Обзор

Разделение FootageHub на два независимых бота с общей базой данных:
1. **MediaBot** - загрузка медиа с Envato/Freepik (текущий функционал)
2. **AIBot** - генерация контента через нейросети (все через Kie.ai API)

## Архитектура микросервисов

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
│  (Container: footage-bot)    │  │  (Container: ai-bot)     │
├──────────────────────────────┤  ├──────────────────────────┤
│ - Envato downloads           │  │ - Nano Banana (Kie.ai)   │
│ - Freepik downloads          │  │ - Kling 2.6 (Kie.ai)     │
│ - Motion Array downloads     │  │ - VEO 3.1 (Kie.ai)       │
│ - Payment webhooks           │  │ - AI credit management   │
│ - Subscription management    │  │ - AI usage tracking      │
│ - Referral system            │  │ - Future Kie.ai models   │
│ - Channel bonus              │  │                          │
└──────────────────────────────┘  └──────────────────────────┘
```

---

## 1. База данных - Новая схема

### 1.1 Модификации существующих таблиц

#### Таблица `users` - добавить поля:
```python
class User(Base):
    # ... существующие поля ...

    # AI Credits
    ai_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_credits_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Отношения
    bonuses = relationship("UserBonus", back_populates="user", cascade="all, delete-orphan")
```

### 1.2 Новая таблица - Бонусная система

```python
class BonusType(Base):
    """
    Типы бонусов (конфигурация)
    Описывает правила начисления бонусов
    """
    __tablename__ = "bonus_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # CHANNEL_SUBSCRIPTION, FIRST_LOGIN, REFERRAL_REWARD
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Награда
    reward_type: Mapped[str] = mapped_column(Enum("CREDITS", "AI_CREDITS", "BOTH", name="reward_type_enum"), nullable=False)
    credits_amount: Mapped[int] = mapped_column(Integer, default=0)
    ai_credits_amount: Mapped[int] = mapped_column(Integer, default=0)

    # Условия активации
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, default=False)  # Можно получить несколько раз?
    cooldown_days: Mapped[int] = mapped_column(Integer, nullable=True)  # Период повтора (если repeatable)

    # Дополнительные условия (JSON)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=True)  # {"min_referrals": 3, "require_payment": true}

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Отношения
    user_bonuses = relationship("UserBonus", back_populates="bonus_type", cascade="all, delete-orphan")


class UserBonus(Base):
    """
    История начисления бонусов пользователям
    """
    __tablename__ = "user_bonuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    bonus_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("bonus_types.id"), nullable=False)

    # Статус
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "COMPLETED", "CANCELLED", "EXPIRED", name="bonus_status_enum"),
        default="PENDING"
    )

    # Начисленные ресурсы
    credits_granted: Mapped[int] = mapped_column(Integer, default=0)
    ai_credits_granted: Mapped[int] = mapped_column(Integer, default=0)

    # Метаданные
    metadata: Mapped[dict] = mapped_column(JSON, nullable=True)  # {"referral_id": 123, "channel_id": "@channel"}

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Отношения
    user = relationship("User", back_populates="bonuses")
    bonus_type = relationship("BonusType", back_populates="user_bonuses")
```

### 1.3 Улучшение реферальной системы

```python
class ReferralReward(Base):
    """
    Обновленная таблица реферальных наград
    """
    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    referred_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)

    # Связь с бонусной системой
    bonus_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_bonuses.id"), nullable=True)

    # Старая система (для совместимости)
    status: Mapped[str] = mapped_column(Enum("PENDING", "COMPLETED", name="referral_status_enum"), default="PENDING")
    credits_earned: Mapped[int] = mapped_column(Integer, default=0)

    # Триггеры наград
    trigger_type: Mapped[str] = mapped_column(
        Enum("REGISTRATION", "FIRST_PAYMENT", "SUBSCRIPTION", "MILESTONE", name="referral_trigger_enum"),
        nullable=True
    )
    trigger_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Отношения
    referrer = relationship("User", foreign_keys=[referrer_id], backref="referrals_given")
    referred = relationship("User", foreign_keys=[referred_id], backref="referrals_received")
    bonus = relationship("UserBonus", foreign_keys=[bonus_id])
```

### 1.4 AI Usage Tracking

```python
class AIGenerationLog(Base):
    """
    Логирование AI генераций для аналитики
    """
    __tablename__ = "ai_generation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)

    # Тип генерации
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # KIE_AI, KLING, etc.
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # nano-banana, kling-2.6
    generation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # IMAGE, VIDEO

    # Параметры запроса
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=True)  # aspect_ratio, resolution, etc.

    # Результат
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "PROCESSING", "SUCCESS", "FAILED", name="ai_status_enum"),
        default="PENDING"
    )
    result_url: Mapped[str] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Затраты
    ai_credits_spent: Mapped[int] = mapped_column(Integer, default=1)
    processing_time_seconds: Mapped[int] = mapped_column(Integer, nullable=True)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Отношения
    user = relationship("User", backref="ai_generations")
```

---

## 2. Разделение кодовой базы

### 2.1 Структура проекта после разделения

```
FootageHub/
├── shared/                          # Общий код для обоих ботов
│   ├── __init__.py
│   ├── db/                          # База данных (shared)
│   │   ├── __init__.py
│   │   ├── models.py                # Все модели SQLAlchemy
│   │   ├── session.py               # Фабрика сессий
│   │   ├── base.py                  # Миграции
│   │   ├── crud/                    # CRUD operations
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── subscription.py
│   │   │   ├── payment.py
│   │   │   ├── bonus.py             # NEW
│   │   │   ├── referral.py
│   │   │   └── ai_generation.py     # NEW
│   │   └── repositories/            # NEW: Repository pattern
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── user_repository.py
│   │       ├── bonus_repository.py
│   │       └── ai_repository.py
│   ├── services/                    # Бизнес-логика (shared)
│   │   ├── __init__.py
│   │   ├── bonus_service.py         # NEW: Управление бонусами
│   │   ├── referral_service.py      # NEW: Улучшенная реферальная система
│   │   └── credit_service.py        # NEW: Управление кредитами
│   ├── core/                        # Общие утилиты
│   │   ├── __init__.py
│   │   ├── config.py                # Базовая конфигурация
│   │   ├── logger.py                # Централизованное логирование
│   │   └── exceptions.py            # Кастомные исключения
│   └── schemas/                     # Pydantic schemas для валидации
│       ├── __init__.py
│       ├── user.py
│       ├── bonus.py
│       └── ai_generation.py
│
├── media_bot/                       # MediaBot (Envato/Freepik)
│   ├── __init__.py
│   ├── main.py
│   ├── config.py                    # Специфичная конфигурация
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── download/
│   │   │   ├── __init__.py
│   │   │   ├── envato.py
│   │   │   ├── freepik.py
│   │   │   └── motion_array.py      # NEW: Motion Array
│   │   ├── payment.py
│   │   ├── subscription.py
│   │   ├── referral.py
│   │   └── admin/
│   ├── services/                    # MediaBot-специфичные сервисы
│   │   ├── __init__.py
│   │   ├── download_service.py      # NEW: Абстракция загрузок
│   │   ├── payment_service.py       # NEW: Управление платежами
│   │   └── subscription_service.py  # NEW: Управление подписками
│   ├── downloaders/                 # Refactored download logic
│   │   ├── __init__.py
│   │   ├── base.py                  # AbstractDownloader
│   │   ├── envato.py                # EnvatoDownloader
│   │   ├── freepik.py               # FreepikDownloader
│   │   └── link_processor.py        # Queue manager
│   ├── webhook/
│   │   ├── __init__.py
│   │   ├── webpay.py
│   │   ├── cryptobot.py
│   │   └── server_start.py
│   ├── schedule_tasks.py
│   ├── state.py
│   └── middlewares/                 # NEW: Middleware layer
│       ├── __init__.py
│       ├── auth.py
│       └── subscription_check.py
│
├── ai_bot/                          # AIBot (AI generation)
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── image_generation.py      # Kie.ai NANO BANANA
│   │   ├── video_generation.py      # Kling 2.6 + VEO 3.1
│   │   └── admin/
│   ├── services/                    # AI-специфичные сервисы
│   │   ├── __init__.py
│   │   ├── ai_service.py            # NEW: Абстракция AI провайдеров
│   │   ├── credit_manager.py        # NEW: AI кредиты
│   │   └── generation_queue.py      # NEW: Очередь генераций
│   ├── providers/                   # AI providers (все через Kie.ai API)
│   │   ├── __init__.py
│   │   ├── base.py                  # AbstractAIProvider
│   │   ├── kie_ai_client.py         # Базовый Kie.ai API клиент
│   │   ├── nano_banana.py           # Nano Banana (image gen)
│   │   ├── kling.py                 # Kling 2.6 (video gen)
│   │   └── veo.py                   # VEO 3.1 (video gen)
│   ├── state.py
│   └── middlewares/
│       ├── __init__.py
│       └── ai_credit_check.py
│
├── alembic/                         # Миграции (shared)
│   ├── versions/
│   └── env.py
│
├── docker/
│   ├── media-bot.Dockerfile
│   ├── ai-bot.Dockerfile
│   └── docker-compose.yml
│
├── tests/                           # Тесты для обоих ботов
│   ├── shared/
│   ├── media_bot/
│   └── ai_bot/
│
├── requirements/
│   ├── base.txt                     # Shared dependencies
│   ├── media-bot.txt
│   └── ai-bot.txt
│
└── docs/
    ├── CLAUDE.md
    ├── MICROSERVICES_ARCHITECTURE_PLAN.md
    └── API_CONTRACTS.md             # NEW: Контракты между сервисами
```

---

## 3. SOLID & Clean Code Refactoring

### 3.1 Принципы рефакторинга

#### Single Responsibility Principle (SRP)
- **ДО**: `bot/handlers/download.py` - обработка команд + загрузка + проверка подписки + начисление кредитов
- **ПОСЛЕ**:
  - `handlers/download/envato.py` - только обработка команд
  - `services/download_service.py` - бизнес-логика загрузок
  - `services/subscription_service.py` - проверка подписок
  - `repositories/download_repository.py` - работа с БД

#### Open/Closed Principle (OCP)
- **Абстрактные базовые классы** для расширяемости:

```python
# shared/services/bonus_service.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BonusStrategy(ABC):
    """Абстрактная стратегия начисления бонусов"""

    @abstractmethod
    async def can_apply(self, user_id: int, metadata: Dict[str, Any]) -> bool:
        """Проверка условий применения бонуса"""
        pass

    @abstractmethod
    async def apply_bonus(self, user_id: int, metadata: Dict[str, Any]) -> UserBonus:
        """Применение бонуса"""
        pass


class ChannelSubscriptionBonus(BonusStrategy):
    """Стратегия бонуса за подписку на канал"""

    async def can_apply(self, user_id: int, metadata: Dict[str, Any]) -> bool:
        # Проверка подписки на канал
        channel_id = metadata.get("channel_id")
        return await check_user_subscribed(user_id, channel_id)

    async def apply_bonus(self, user_id: int, metadata: Dict[str, Any]) -> UserBonus:
        # Начисление бонуса
        bonus_type = await get_bonus_type_by_code("CHANNEL_SUBSCRIPTION")
        return await create_user_bonus(user_id, bonus_type.id, metadata)


class ReferralBonus(BonusStrategy):
    """Стратегия реферального бонуса"""
    # ...


class BonusManager:
    """Менеджер бонусов (использует стратегии)"""

    def __init__(self):
        self._strategies: Dict[str, BonusStrategy] = {
            "CHANNEL_SUBSCRIPTION": ChannelSubscriptionBonus(),
            "REFERRAL_REWARD": ReferralBonus(),
            "FIRST_LOGIN": FirstLoginBonus(),
        }

    async def apply_bonus(self, bonus_code: str, user_id: int, metadata: Dict[str, Any]):
        strategy = self._strategies.get(bonus_code)
        if not strategy:
            raise ValueError(f"Unknown bonus type: {bonus_code}")

        if await strategy.can_apply(user_id, metadata):
            return await strategy.apply_bonus(user_id, metadata)
```

#### Liskov Substitution Principle (LSP)
- **Абстрактные загрузчики**:

```python
# media_bot/downloaders/base.py
from abc import ABC, abstractmethod
from typing import Optional

class AbstractDownloader(ABC):
    """Базовый класс для всех загрузчиков"""

    @abstractmethod
    async def download(self, url: str) -> Optional[str]:
        """Загрузка медиа по URL"""
        pass

    @abstractmethod
    async def check_auth(self) -> bool:
        """Проверка авторизации"""
        pass

    @abstractmethod
    async def rotate_cookies(self) -> None:
        """Ротация куки"""
        pass


class EnvatoDownloader(AbstractDownloader):
    async def download(self, url: str) -> Optional[str]:
        # Реализация для Envato
        pass


class FreepikDownloader(AbstractDownloader):
    async def download(self, url: str) -> Optional[str]:
        # Реализация для Freepik
        pass
```

#### Interface Segregation Principle (ISP)
- **Разделение интерфейсов** вместо жирных классов:

```python
# shared/db/repositories/base.py
from typing import Protocol, TypeVar, Generic, Optional, List

T = TypeVar('T')

class IReadRepository(Protocol[T]):
    """Интерфейс для чтения данных"""
    async def get_by_id(self, id: int) -> Optional[T]: ...
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]: ...


class IWriteRepository(Protocol[T]):
    """Интерфейс для записи данных"""
    async def create(self, obj: T) -> T: ...
    async def update(self, obj: T) -> T: ...
    async def delete(self, id: int) -> bool: ...


class IUserRepository(IReadRepository, IWriteRepository):
    """Полный интерфейс репозитория пользователей"""
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]: ...
    async def get_by_referral_code(self, code: str) -> Optional[User]: ...
```

#### Dependency Inversion Principle (DIP)
- **Инъекция зависимостей**:

```python
# media_bot/services/download_service.py
from shared.db.repositories.base import IUserRepository
from media_bot.downloaders.base import AbstractDownloader

class DownloadService:
    """Сервис загрузок с инъекцией зависимостей"""

    def __init__(
        self,
        user_repository: IUserRepository,
        downloader: AbstractDownloader,
        subscription_service: SubscriptionService
    ):
        self._user_repo = user_repository
        self._downloader = downloader
        self._subscription_service = subscription_service

    async def process_download(self, user_id: int, url: str) -> str:
        # Использование инжектированных зависимостей
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise UserNotFoundError()

        can_download = await self._subscription_service.check_can_download(user.id)
        if not can_download:
            raise InsufficientCreditsError()

        result = await self._downloader.download(url)
        return result
```

### 3.2 Clean Code practices

#### 3.2.1 Именование
```python
# ❌ ПЛОХО
async def gub(u, s):
    r = await db.query(User).filter(User.id == u).first()
    return r

# ✅ ХОРОШО
async def get_user_by_id(user_id: int, session: AsyncSession) -> Optional[User]:
    """
    Получить пользователя по ID.

    Args:
        user_id: Telegram ID пользователя
        session: Сессия БД

    Returns:
        Объект User или None если не найден
    """
    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    return result.scalar_one_or_none()
```

#### 3.2.2 Функции - одна ответственность
```python
# ❌ ПЛОХО
async def handle_download(message, url):
    user = await get_user(message.from_user.id)
    if not user.subscription or user.subscription.downloads_left == 0:
        await message.answer("No credits")
        return

    result = await download_file(url)
    user.subscription.downloads_left -= 1
    await save_user(user)
    await message.answer(result)

# ✅ ХОРОШО
async def handle_download_request(message: Message, state: FSMContext):
    """Обработчик запроса на загрузку"""
    url = await extract_url_from_message(message)

    try:
        download_result = await download_service.process_download(
            user_id=message.from_user.id,
            url=url
        )
        await send_download_result(message, download_result)
    except InsufficientCreditsError:
        await send_no_credits_message(message)
    except InvalidUrlError:
        await send_invalid_url_message(message)
```

#### 3.2.3 Константы и магические числа
```python
# ❌ ПЛОХО
if user.credits < 1:
    return False

await asyncio.sleep(3)

# ✅ ХОРОШО
# shared/core/constants.py
class DownloadLimits:
    MIN_CREDITS_FOR_DOWNLOAD = 1
    DOWNLOAD_COOLDOWN_SECONDS = 3
    MAX_CONCURRENT_DOWNLOADS = 5

# usage
if user.credits < DownloadLimits.MIN_CREDITS_FOR_DOWNLOAD:
    return False

await asyncio.sleep(DownloadLimits.DOWNLOAD_COOLDOWN_SECONDS)
```

---

## 4. Docker Infrastructure

### 4.1 docker-compose.yml

```yaml
version: '3.8'

services:
  # Shared PostgreSQL database
  postgres:
    image: postgres:15-alpine
    container_name: footagehub-db
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: footagehub
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "5432:5432"
    networks:
      - footagehub-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # MediaBot - Envato/Freepik downloads
  media-bot:
    build:
      context: .
      dockerfile: docker/media-bot.Dockerfile
    container_name: footagehub-media-bot
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/footagehub
      - BOT_TOKEN=${MEDIA_BOT_TOKEN}
      - ADMIN=${ADMIN}
      - DISPLAY=:99
      # WebPay
      - WEBPAY_RESOURCE_ID=${WEBPAY_RESOURCE_ID}
      - WEBPAY_API_KEY=${WEBPAY_API_KEY}
      - WEBPAY_SECRET_KEY=${WEBPAY_SECRET_KEY}
      - WEBPAY_SIGNING_KEY=${WEBPAY_SIGNING_KEY}
      - WEBPAY_SANDBOX=${WEBPAY_SANDBOX}
      # CryptoBot
      - CRYPTO_BOT_API_KEY=${CRYPTO_BOT_API_KEY}
      # Channel
      - CHANNEL_ID=${CHANNEL_ID}
      - CHANNEL_BONUS_CREDITS=${CHANNEL_BONUS_CREDITS}
    volumes:
      - ./media_bot:/app/media_bot
      - ./shared:/app/shared
      - ./envato_utils:/app/envato_utils
      - ./freepik_utils:/app/freepik_utils
      - ./cookies:/app/cookies
      - ./debug_screenshots:/app/debug_screenshots
    networks:
      - footagehub-network
    restart: unless-stopped
    ports:
      - "8000:8000"  # WebPay webhooks

  # AIBot - AI content generation
  ai-bot:
    build:
      context: .
      dockerfile: docker/ai-bot.Dockerfile
    container_name: footagehub-ai-bot
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/footagehub
      - BOT_TOKEN=${AI_BOT_TOKEN}
      - ADMIN=${ADMIN}
      # AI Providers
      - KIE_AI_API_KEY=${KIE_AI_API_KEY}
      # Channel
      - CHANNEL_ID=${CHANNEL_ID}
    volumes:
      - ./ai_bot:/app/ai_bot
      - ./shared:/app/shared
      - ./ai_generations:/app/ai_generations
    networks:
      - footagehub-network
    restart: unless-stopped

  # Nginx (optional) - для проксирования webhooks
  nginx:
    image: nginx:alpine
    container_name: footagehub-nginx
    depends_on:
      - media-bot
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "80:80"
      - "443:443"
    networks:
      - footagehub-network
    restart: unless-stopped

volumes:
  postgres_data:

networks:
  footagehub-network:
    driver: bridge
```

### 4.2 media-bot.Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
    x11vnc \
    fluxbox \
    supervisor \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements/base.txt requirements/base.txt
COPY requirements/media-bot.txt requirements/media-bot.txt
RUN pip install --no-cache-dir -r requirements/media-bot.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy shared code
COPY shared/ /app/shared/

# Copy media bot code
COPY media_bot/ /app/media_bot/
COPY envato_utils/ /app/envato_utils/
COPY freepik_utils/ /app/freepik_utils/

# Copy alembic migrations
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini

# Setup Xvfb for headless Playwright
COPY docker/xvfb-run.sh /usr/local/bin/xvfb-run.sh
RUN chmod +x /usr/local/bin/xvfb-run.sh

# Environment
ENV PYTHONPATH=/app
ENV DISPLAY=:99

CMD ["/usr/local/bin/xvfb-run.sh", "python", "-m", "media_bot.main"]
```

### 4.3 ai-bot.Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements/base.txt requirements/base.txt
COPY requirements/ai-bot.txt requirements/ai-bot.txt
RUN pip install --no-cache-dir -r requirements/ai-bot.txt

# Copy shared code
COPY shared/ /app/shared/

# Copy AI bot code
COPY ai_bot/ /app/ai_bot/

# Environment
ENV PYTHONPATH=/app

CMD ["python", "-m", "ai_bot.main"]
```

---

## 5. Migration Plan (Пошаговый план миграции)

### Фаза 1: Подготовка (1-2 недели)

#### Шаг 1.1: Создание shared модуля
- [ ] Создать директорию `shared/`
- [ ] Переместить `db/models.py` → `shared/db/models.py`
- [ ] Добавить новые модели: `BonusType`, `UserBonus`, `AIGenerationLog`
- [x] Обновить модель `User` (добавить `ai_credits`, `ai_credits_used`) ✅ 2025-12-26
- [x] Создать Alembic миграцию для новых таблиц ✅ 2025-12-26

#### Шаг 1.2: Рефакторинг CRUD → Repositories
- [ ] Создать `shared/db/repositories/base.py` с интерфейсами
- [ ] Создать `UserRepository`, `BonusRepository`, `SubscriptionRepository`
- [ ] Переписать существующие CRUD операции на паттерн Repository

#### Шаг 1.3: Создание сервисного слоя
- [ ] `shared/services/bonus_service.py` - управление бонусами
- [ ] `shared/services/referral_service.py` - улучшенная реферальная система
- [ ] `shared/services/credit_service.py` - управление кредитами

#### Шаг 1.4: Настройка логирования и исключений
- [ ] `shared/core/logger.py` - централизованное логирование
- [ ] `shared/core/exceptions.py` - кастомные исключения
- [ ] `shared/core/constants.py` - константы

### Фаза 2: Разделение на микросервисы (2-3 недели)

#### Шаг 2.1: MediaBot
- [ ] Создать `media_bot/` директорию
- [ ] Переместить handlers: `download/`, `payment.py`, `subscription.py`
- [ ] Рефакторить downloaders:
  - [ ] `envato_playwright.py` → `media_bot/downloaders/envato.py`
  - [ ] `freepik.py` → `media_bot/downloaders/freepik.py`
  - [ ] Создать `media_bot/downloaders/motion_array.py` - НОВЫЙ
- [ ] Создать `media_bot/services/download_service.py`
- [ ] Создать `media_bot/services/payment_service.py`
- [ ] Обновить `main.py` → `media_bot/main.py`
- [ ] Добавить handler для Motion Array: `media_bot/handlers/download/motion_array.py`

#### Шаг 2.2: AIBot ⭐ ВЫСОКИЙ ПРИОРИТЕТ
- [x] Создать `ai_bot/` директорию ✅ 2025-12-26
- [x] Создать базовый Kie.ai API клиент: `ai_bot/providers/kie_ai_client.py` ✅ 2025-12-26
- [x] Рефакторить `kie_utils.py` → разделить на отдельные провайдеры: ✅ 2025-12-26
  - [x] `ai_bot/providers/nano_banana.py` (Nano Banana - images) ✅ 2025-12-26
  - [x] `ai_bot/providers/kling.py` (Kling 2.6 - video) ✅ 2025-12-26
  - [x] `ai_bot/providers/veo.py` (VEO 3.1 - video) - НОВЫЙ ✅ 2025-12-26
- [x] Создать `ai_bot/providers/base.py` (AbstractAIProvider) ✅ 2025-12-26
- [x] Создать handlers: ✅ 2025-12-26
  - [x] `image_generation.py` (Nano Banana) ✅ 2025-12-26
  - [x] `video_generation.py` (Kling 2.6 + VEO 3.1) ✅ 2025-12-26
- [x] Создать `ai_bot/services/ai_service.py` ✅ 2025-12-26
- [x] Создать `ai_bot/services/credit_manager.py` ✅ 2025-12-26
- [x] Создать `ai_bot/main.py` ✅ 2025-12-26
- [x] Создать `ai_bot/state.py` для FSM управления ✅ 2025-12-26
- [x] Протестировать запуск AIBot ✅ 2025-12-26

#### Шаг 2.3: Бонусная система
- [ ] Реализовать `BonusStrategy` паттерн
- [ ] Создать стратегии: `ChannelSubscriptionBonus`, `ReferralBonus`, `FirstLoginBonus`
- [ ] Интегрировать в MediaBot handlers
- [ ] Создать админ-панель для управления бонусами

#### Шаг 2.4: Улучшение реферальной системы
- [ ] Обновить `ReferralReward` модель
- [ ] Связать с бонусной системой
- [ ] Добавить триггеры: `REGISTRATION`, `FIRST_PAYMENT`, `SUBSCRIPTION`
- [ ] Создать отдельный хендлер `media_bot/handlers/referral.py`

### Фаза 3: Docker & DevOps (1 неделя)

#### Шаг 3.1: Docker configuration
- [ ] Создать `docker/media-bot.Dockerfile`
- [ ] Создать `docker/ai-bot.Dockerfile`
- [ ] Настроить `docker-compose.yml`
- [ ] Настроить health checks для PostgreSQL

#### Шаг 3.2: CI/CD
- [ ] Настроить GitHub Actions для автоматической сборки
- [ ] Настроить линтеры (black, flake8, mypy)
- [ ] Настроить pre-commit hooks

#### Шаг 3.3: Мониторинг
- [ ] Добавить Prometheus metrics (опционально)
- [ ] Настроить Sentry для error tracking
- [ ] Логирование в ELK/Loki (опционально)

### Фаза 4: Тестирование и деплой (1-2 недели)

#### Шаг 4.1: Unit тесты
- [ ] Тесты для `shared/services/`
- [ ] Тесты для `shared/db/repositories/`
- [ ] Тесты для `media_bot/services/`
- [ ] Тесты для `ai_bot/services/`

#### Шаг 4.2: Integration тесты
- [ ] Тест полного flow загрузки (MediaBot)
- [ ] Тест полного flow AI генерации (AIBot)
- [ ] Тест реферальной системы
- [ ] Тест бонусной системы

#### Шаг 4.3: Staging деплой
- [ ] Деплой на staging сервер
- [ ] Тестирование обоих ботов
- [ ] Load testing

#### Шаг 4.4: Production деплой
- [ ] Миграция БД
- [ ] Zero-downtime deployment
- [ ] Мониторинг после деплоя

---

## 6. Примеры кода после рефакторинга

### 6.1 Пример: BonusService

```python
# shared/services/bonus_service.py
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.user_repository import UserRepository
from shared.db.models import BonusType, UserBonus
from shared.core.exceptions import BonusNotFoundError, BonusAlreadyClaimedError

class BonusService:
    """Сервис управления бонусами"""

    def __init__(
        self,
        bonus_repo: BonusRepository,
        user_repo: UserRepository
    ):
        self._bonus_repo = bonus_repo
        self._user_repo = user_repo

    async def get_bonus_type(self, code: str) -> Optional[BonusType]:
        """Получить тип бонуса по коду"""
        return await self._bonus_repo.get_by_code(code)

    async def can_claim_bonus(
        self,
        user_id: int,
        bonus_code: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Проверить, может ли пользователь получить бонус

        Args:
            user_id: ID пользователя
            bonus_code: Код бонуса (CHANNEL_SUBSCRIPTION, FIRST_LOGIN, etc.)
            metadata: Дополнительные данные для проверки условий

        Returns:
            True если бонус может быть начислен
        """
        bonus_type = await self.get_bonus_type(bonus_code)
        if not bonus_type or not bonus_type.is_active:
            return False

        # Проверка на повторное получение
        if not bonus_type.is_repeatable:
            already_claimed = await self._bonus_repo.user_has_bonus(
                user_id=user_id,
                bonus_type_id=bonus_type.id,
                status="COMPLETED"
            )
            if already_claimed:
                return False

        # Проверка cooldown
        if bonus_type.is_repeatable and bonus_type.cooldown_days:
            last_claim = await self._bonus_repo.get_last_user_bonus(
                user_id=user_id,
                bonus_type_id=bonus_type.id
            )
            if last_claim:
                cooldown_end = last_claim.completed_at + timedelta(days=bonus_type.cooldown_days)
                if datetime.utcnow() < cooldown_end:
                    return False

        # Проверка дополнительных условий
        if bonus_type.conditions:
            if not await self._check_conditions(user_id, bonus_type.conditions, metadata):
                return False

        return True

    async def claim_bonus(
        self,
        user_id: int,
        bonus_code: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UserBonus:
        """
        Начислить бонус пользователю

        Args:
            user_id: ID пользователя
            bonus_code: Код бонуса
            metadata: Метаданные (например, {"channel_id": "@channel"})

        Returns:
            Созданный UserBonus

        Raises:
            BonusNotFoundError: Бонус не найден
            BonusAlreadyClaimedError: Бонус уже получен
        """
        # Проверки
        if not await self.can_claim_bonus(user_id, bonus_code, metadata):
            raise BonusAlreadyClaimedError(f"User {user_id} cannot claim bonus {bonus_code}")

        bonus_type = await self.get_bonus_type(bonus_code)
        if not bonus_type:
            raise BonusNotFoundError(f"Bonus {bonus_code} not found")

        # Создание записи бонуса
        user_bonus = await self._bonus_repo.create_user_bonus(
            user_id=user_id,
            bonus_type_id=bonus_type.id,
            credits_granted=bonus_type.credits_amount,
            ai_credits_granted=bonus_type.ai_credits_amount,
            metadata=metadata or {},
            status="COMPLETED",
            completed_at=datetime.utcnow()
        )

        # Начисление кредитов пользователю
        await self._user_repo.add_credits(
            user_id=user_id,
            credits=bonus_type.credits_amount,
            ai_credits=bonus_type.ai_credits_amount
        )

        return user_bonus

    async def _check_conditions(
        self,
        user_id: int,
        conditions: Dict[str, Any],
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Проверка дополнительных условий из JSON"""
        # Пример: {"min_referrals": 3, "require_payment": true}

        if "min_referrals" in conditions:
            referral_count = await self._user_repo.get_referral_count(user_id)
            if referral_count < conditions["min_referrals"]:
                return False

        if conditions.get("require_payment"):
            has_payment = await self._user_repo.has_any_payment(user_id)
            if not has_payment:
                return False

        return True

    async def get_user_bonuses(
        self,
        user_id: int,
        status: Optional[str] = None
    ) -> List[UserBonus]:
        """Получить список бонусов пользователя"""
        return await self._bonus_repo.get_user_bonuses(user_id, status)
```

### 6.2 Пример: AIService (AIBot)

```python
# ai_bot/services/ai_service.py
from typing import Optional, Dict, Any
from ai_bot.providers.base import AbstractAIProvider
from ai_bot.providers.kie_ai import KieAIProvider
from ai_bot.providers.kling import KlingProvider
from shared.db.repositories.user_repository import UserRepository
from shared.db.repositories.ai_repository import AIRepository
from shared.core.exceptions import InsufficientAICreditsError, AIProviderError

class AIService:
    """Сервис AI генерации"""

    def __init__(
        self,
        user_repo: UserRepository,
        ai_repo: AIRepository
    ):
        self._user_repo = user_repo
        self._ai_repo = ai_repo
        self._providers: Dict[str, AbstractAIProvider] = {
            "KIE_AI": KieAIProvider(),
            "KLING": KlingProvider()
        }

    async def generate_image(
        self,
        user_id: int,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "2K"
    ) -> str:
        """
        Генерация изображения через Kie.ai

        Returns:
            URL сгенерированного изображения
        """
        # Проверка кредитов
        user = await self._user_repo.get_by_telegram_id(user_id)
        if user.ai_credits < 1:
            raise InsufficientAICreditsError("Not enough AI credits")

        # Создание лога
        log = await self._ai_repo.create_generation_log(
            user_id=user.id,
            provider="KIE_AI",
            model="google/nano-banana",
            generation_type="IMAGE",
            prompt=prompt,
            parameters={"aspect_ratio": aspect_ratio, "resolution": resolution},
            ai_credits_spent=1
        )

        try:
            # Генерация
            provider = self._providers["KIE_AI"]
            result_url = await provider.generate_image(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )

            # Обновление лога
            await self._ai_repo.update_generation_log(
                log_id=log.id,
                status="SUCCESS",
                result_url=result_url
            )

            # Списание кредитов
            await self._user_repo.deduct_ai_credits(user.id, 1)

            return result_url

        except Exception as e:
            # Логирование ошибки
            await self._ai_repo.update_generation_log(
                log_id=log.id,
                status="FAILED",
                error_message=str(e)
            )
            raise AIProviderError(f"Image generation failed: {e}")

    async def generate_video(
        self,
        user_id: int,
        prompt: str,
        duration: str = "5",
        aspect_ratio: str = "16:9"
    ) -> str:
        """Генерация видео через Kling"""
        # Аналогичная логика
        pass
```

### 6.3 Пример: Handler с DI (MediaBot)

```python
# media_bot/handlers/download/envato.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from media_bot.services.download_service import DownloadService
from media_bot.state import DownloadStates
from shared.core.exceptions import (
    InsufficientCreditsError,
    InvalidUrlError,
    SubscriptionRequiredError
)

router = Router()

# Dependency injection через middleware или factory
async def get_download_service() -> DownloadService:
    # В реальности это будет dependency injection container
    from media_bot.dependencies import download_service
    return download_service


@router.message(DownloadStates.waiting_for_envato_url)
async def handle_envato_download(message: Message, state: FSMContext):
    """Обработка загрузки с Envato"""
    url = message.text.strip()

    # Получение сервиса
    download_service = await get_download_service()

    try:
        # Основная логика делегирована сервису
        result = await download_service.process_download(
            user_id=message.from_user.id,
            url=url,
            provider="ENVATO"
        )

        await message.answer(
            f"✅ Файл загружен!\n\n"
            f"🔗 {result.download_url}\n\n"
            f"💳 Осталось кредитов: {result.remaining_credits}"
        )
        await state.clear()

    except InvalidUrlError:
        await message.answer(
            "❌ Неверная ссылка. Отправьте ссылку на Envato Elements."
        )

    except InsufficientCreditsError:
        await message.answer(
            "❌ Недостаточно кредитов.\n\n"
            "Купите подписку: /subscribe"
        )
        await state.clear()

    except SubscriptionRequiredError as e:
        await message.answer(f"❌ {str(e)}")
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки: {str(e)}")
        await state.clear()
```

---

## 7. Конфигурация бонусов (seed data)

### 7.1 SQL для начальных данных

```sql
-- alembic/versions/xxxx_seed_bonus_types.py
"""Seed bonus types

Revision ID: xxxx
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Создание базовых типов бонусов
    op.execute("""
        INSERT INTO bonus_types (code, name, description, reward_type, credits_amount, ai_credits_amount, is_active, is_repeatable, cooldown_days)
        VALUES
        -- Бонус за подписку на канал
        ('CHANNEL_SUBSCRIPTION', 'Бонус за подписку на канал', 'Начисляется при подписке на официальный канал', 'CREDITS', 2, 0, true, false, null),

        -- Первый вход
        ('FIRST_LOGIN', 'Приветственный бонус', 'Начисляется при первом входе в бота', 'BOTH', 3, 5, true, false, null),

        -- Реферальная система
        ('REFERRAL_REGISTRATION', 'Регистрация реферала', 'Когда реферал зарегистрировался', 'CREDITS', 1, 0, true, true, null),

        ('REFERRAL_FIRST_PAYMENT', 'Первая оплата реферала', 'Когда реферал совершил первую покупку', 'BOTH', 5, 10, true, true, null),

        -- Ежедневный бонус
        ('DAILY_LOGIN', 'Ежедневный вход', 'Бонус за ежедневный вход в бота', 'CREDITS', 1, 0, true, true, 1),

        -- Промо-бонусы
        ('PROMO_NEW_YEAR', 'Новогодний бонус', 'Специальный новогодний бонус', 'BOTH', 10, 20, false, false, null),

        ('PROMO_BIRTHDAY', 'День рождения бота', 'Бонус на день рождения бота', 'AI_CREDITS', 0, 50, false, false, null);
    """)

def downgrade():
    op.execute("DELETE FROM bonus_types;")
```

---

## 8. Метрики успеха миграции

### 8.1 Технические метрики
- [ ] Code coverage > 80%
- [ ] Все тесты проходят
- [ ] Zero downtime при деплое
- [ ] Response time < 2s для 95% запросов
- [ ] Memory usage < 512MB per bot container

### 8.2 Бизнес метрики
- [ ] Количество active users не снизилось
- [ ] Конверсия подписок не снизилась
- [ ] Средний чек не изменился
- [ ] Referral rate вырос (после внедрения улучшений)

---

## 9. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Потеря данных при миграции БД | Средняя | Критическое | Полный бэкап перед миграцией, тестирование на staging |
| Несовместимость старых/новых моделей | Высокая | Высокое | Постепенная миграция, алембик версионирование |
| Downtime при переходе | Средняя | Среднее | Blue-green deployment, feature flags |
| Баги в новом коде | Высокая | Среднее | Unit тесты, integration тесты, staging environment |
| Производительность хуже | Низкая | Среднее | Load testing перед деплоем, мониторинг |

---

## 10. Следующие шаги

1. **Approval** - утверждение плана
2. **Создание веток** - `feature/microservices-migration`, `feature/bonus-system`
3. **Начало Фазы 1** - создание shared модуля
4. **Еженедельные ревью** - прогресс по задачам

---

## 11. Приоритеты реализации

### ✅ Подтверждено:
1. **ВЫСОКИЙ ПРИОРИТЕТ**: Создание AIBot с нейросетями через Kie.ai
   - Nano Banana (генерация изображений)
   - Kling 2.6 (генерация видео)
   - VEO 3.1 (генерация видео)

2. **AI провайдеры**: ВСЕ AI модели работают через Kie.ai API (единая точка интеграции)

3. **Архитектура БД**: Прямое подключение обоих ботов к PostgreSQL (без API Gateway)

4. **MediaBot расширение**: Добавить поддержку Motion Array downloads

### ❓ На обсуждение:
1. Какие еще типы бонусов нужно добавить в систему?
2. Нужна ли отдельная веб админ-панель для управления бонусами?
3. Timing: когда начинать рефакторинг MediaBot?

---

## 12. История реализации

### 2025-12-26: AIBot - Базовая реализация ✅

#### Выполненные задачи:

**База данных:**
- ✅ Добавлены поля `ai_credits` и `ai_credits_used` в модель User
- ✅ Создана Alembic миграция `cfc529f762df_add_ai_credits_to_users_table.py`
- ✅ Миграция применена к production БД с `server_default='0'`

**Архитектура провайдеров:**
- ✅ Создан `AbstractAIProvider` базовый класс с pattern Strategy
- ✅ Реализован `KieAIClient` - универсальный клиент для Kie.ai API
- ✅ Провайдер `NanoBananaProvider` для генерации изображений
- ✅ Провайдер `KlingProvider` для генерации видео (Kling 2.6)
- ✅ Провайдер `VeoProvider` для генерации видео (VEO 3.1)
- ✅ Поддержка image-to-video (референсные изображения)

**Сервисный слой:**
- ✅ `AIService` - координация провайдеров и генераций
- ✅ `CreditManager` - управление AI кредитами с поддержкой:
  - Проверка баланса
  - Списание кредитов
  - Возврат кредитов (refund system)
  - Статистика использования

**Telegram Bot Handlers:**
- ✅ `start.py` - отображение реального баланса AI кредитов
- ✅ `image_generation.py` - полный FSM flow для генерации изображений
  - Выбор aspect ratio (1:1, 16:9, 9:16, 4:3, auto)
  - Выбор resolution (1K, 2K, 4K)
  - Автоматический refund при ошибках
- ✅ `video_generation.py` - полный FSM flow для генерации видео
  - Выбор провайдера (Kling 2.6 / VEO 3.1)
  - Выбор aspect ratio, duration
  - Опция звука для Kling
  - Автоматический refund при ошибках

**FSM State Management:**
- ✅ `ImageGenerationStates` - состояния для генерации изображений
- ✅ `VideoGenerationStates` - состояния для генерации видео

**Тестирование:**
- ✅ AIBot успешно запускается
- ✅ Все импорты работают корректно
- ✅ Интеграция с существующей БД через `tg_id`

#### Технические детали:

**Стоимость генерации:**
- Изображения (Nano Banana): 1 AI кредит
- Видео (Kling/VEO): 5 AI кредитов

**Особенности реализации:**
1. **Adaptive Polling** - умное ожидание результатов:
   - 0-30с: проверка каждые 2с
   - 30-120с: проверка каждые 5с
   - >120с: проверка каждые 10с

2. **Refund System** - автоматический возврат кредитов:
   - При ошибке генерации
   - При exception в коде
   - С логированием причины

3. **Error Handling** - user-friendly сообщения для ошибок Kie.ai:
   - 402: Недостаточно кредитов на Kie.ai
   - 401: Неверный API ключ
   - 429: Превышен лимит запросов

#### Структура файлов:

```
ai_bot/
├── providers/
│   ├── base.py              ✅ AbstractAIProvider
│   ├── kie_ai_client.py     ✅ Базовый Kie.ai клиент
│   ├── nano_banana.py       ✅ Генерация изображений
│   ├── kling.py             ✅ Генерация видео (Kling)
│   └── veo.py               ✅ Генерация видео (VEO)
├── services/
│   ├── ai_service.py        ✅ Основной AI сервис
│   └── credit_manager.py    ✅ Управление кредитами
├── handlers/
│   ├── start.py             ✅ Старт и баланс
│   ├── image_generation.py  ✅ Генерация изображений
│   └── video_generation.py  ✅ Генерация видео
├── state.py                 ✅ FSM состояния
├── config.py                ✅ Конфигурация
├── main.py                  ✅ Точка входа
└── README.md                ✅ Документация

migrations/versions/
└── cfc529f762df_add_ai_credits_to_users_table.py ✅

db/
└── models.py                ✅ User.ai_credits, User.ai_credits_used
```

#### Временные решения (требуют рефакторинга):

⚠️ **Использование `db/` вместо `shared/db/`**
- Текущее состояние: импорты из `db.models`, `db.session`
- Планируется: миграция на `shared/db/` структуру
- Причина отсрочки: фокус на функциональности AIBot

#### Следующие шаги:

**Высокий приоритет:**
- [ ] Добавить логирование в таблицу `AIGenerationLog`
- [ ] Создать middleware для автоматической проверки AI credits
- [ ] Интеграция payment системы для покупки AI кредитов

**Средний приоритет:**
- [ ] Мигрировать на `shared/` структуру
- [ ] Добавить queue систему для обработки нескольких генераций
- [ ] WebHook callbacks для async уведомлений

**Низкий приоритет:**
- [ ] Поддержка image editing в Nano Banana
- [ ] Admin панель для управления AI кредитами
- [ ] Метрики и аналитика использования AI

#### Метрики:

- **Код:** ~2500 строк нового кода
- **Файлы:** 12 новых файлов
- **Провайдеры:** 3 AI провайдера (Nano Banana, Kling, VEO)
- **Миграции:** 1 новая миграция БД
- **Время реализации:** ~4 часа

#### Известные ограничения:

1. Нет логирования генераций в БД (TODO)
2. Нет middleware для проверки кредитов (TODO)
3. Нет системы очередей для параллельных генераций
4. Временное использование `db/` вместо `shared/db/`
