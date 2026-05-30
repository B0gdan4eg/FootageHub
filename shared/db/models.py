"""
Database models for FootageHub microservices.

This module contains all SQLAlchemy models shared between MediaBot and AIBot.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

# ==================== ENUMS ====================


class UserRole(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    PARTNER = "PARTNER"


class SubscriptionType(enum.Enum):
    MONTHLY_50 = "MONTHLY_50"  # 50 скачиваний на месяц (Lite)
    MONTHLY_150 = "MONTHLY_150"  # 150 скачиваний на месяц (Standard)
    MONTHLY_400 = "MONTHLY_400"  # 400 скачиваний на месяц (Pro)
    DAILY_30 = "DAILY_30"  # 30 скачиваний каждый день
    UNLIMITED = "UNLIMITED"  # без лимитов
    CUSTOM = "CUSTOM"  # кастомные условия


class ServiceType(enum.Enum):
    ENVATO = "ENVATO"
    FREEPIK = "FREEPIK"
    MOTION_ARRAY = "MOTION_ARRAY"
    ALL = "ALL"  # доступ ко всем сервисам


class ReferralRewardStatus(enum.Enum):
    PENDING = "PENDING"  # ожидает выполнения условий
    COMPLETED = "COMPLETED"  # вознаграждение выдано
    CANCELLED = "CANCELLED"  # отменено


class ReferralTriggerType(enum.Enum):
    """Триггеры для реферальных наград"""

    REGISTRATION = "REGISTRATION"  # Регистрация реферала
    FIRST_PAYMENT = "FIRST_PAYMENT"  # Первая покупка реферала
    SUBSCRIPTION = "SUBSCRIPTION"  # Покупка подписки
    MILESTONE = "MILESTONE"  # Достижение milestone (например, 5 рефералов)


class BonusRewardType(enum.Enum):
    """Тип награды бонуса"""

    CREDITS = "CREDITS"  # Только обычные кредиты
    AI_CREDITS = "AI_CREDITS"  # Только AI кредиты
    BOTH = "BOTH"  # Оба типа кредитов


class BonusStatus(enum.Enum):
    """Статус бонуса пользователя"""

    PENDING = "PENDING"  # Ожидает выполнения условий
    COMPLETED = "COMPLETED"  # Бонус получен
    CANCELLED = "CANCELLED"  # Отменен
    EXPIRED = "EXPIRED"  # Истек срок действия


class AIGenerationStatus(enum.Enum):
    """Статус AI генерации"""

    PENDING = "PENDING"  # Ожидает обработки
    PROCESSING = "PROCESSING"  # В процессе генерации
    SUCCESS = "SUCCESS"  # Успешно сгенерировано
    FAILED = "FAILED"  # Ошибка генерации


class AIGenerationType(enum.Enum):
    """Тип AI генерации"""

    IMAGE = "IMAGE"  # Генерация изображения
    VIDEO = "VIDEO"  # Генерация видео
    IMAGE_TO_VIDEO = "IMAGE_TO_VIDEO"  # Видео из изображения


# ==================== MODELS ====================


class User(Base):
    """Модель пользователя"""

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=True)
    username = Column(String)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)

    # Бесплатные кредиты (начисляются ежедневно всем пользователям)
    credits = Column(Integer, default=0)

    # AI Credits для AI Bot
    ai_credits = Column(Integer, default=0, nullable=False)
    ai_credits_used = Column(Integer, default=0, nullable=False)

    # Реферальная система
    referral_code = Column(String, unique=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    downloads = relationship("Download", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")

    # Реферальная система
    referral_rewards = relationship(
        "ReferralReward", foreign_keys="ReferralReward.referrer_id", back_populates="referrer"
    )
    received_rewards = relationship(
        "ReferralReward", foreign_keys="ReferralReward.referred_id", back_populates="referred"
    )

    # Бонусная система (NEW)
    bonuses = relationship("UserBonus", back_populates="user", cascade="all, delete-orphan")

    # AI генерации (NEW)
    ai_generations = relationship(
        "AIGenerationLog", back_populates="user", cascade="all, delete-orphan"
    )


class Media(Base):
    """Модель медиафайла"""

    __tablename__ = "media"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    url = Column(Text, unique=True, nullable=False)
    file_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    downloads = relationship("Download", back_populates="media")


class Download(Base):
    """Модель загрузки"""

    __tablename__ = "downloads"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    media_id = Column(BigInteger, ForeignKey("media.id"))
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    paid = Column(Boolean, default=False)
    service_type = Column(Enum(ServiceType), nullable=True)

    user = relationship("User", back_populates="downloads")
    media = relationship("Media", back_populates="downloads")
    subscription = relationship("Subscription", back_populates="downloads")


class Payment(Base):
    """Модель платежа"""

    __tablename__ = "payments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    amount = Column(Numeric, nullable=False)
    currency = Column(String)  # Например, USDT
    status = Column(String, default="pending")  # pending / success / failed
    invoice_id = Column(String, unique=True)

    # Ключ плана подписки: monthly_150, daily_30
    plan_key = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payment", uselist=False)


class Subscription(Base):
    """Таблица подписок пользователей"""

    __tablename__ = "subscriptions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Тип и сервис
    subscription_type = Column(Enum(SubscriptionType), nullable=False)
    service_type = Column(Enum(ServiceType), default=ServiceType.ALL)

    # Лимиты
    total_limit = Column(Integer, nullable=True)  # общий лимит на период
    daily_limit = Column(Integer, nullable=True)  # дневной лимит

    # Использование
    used_total = Column(Integer, default=0)
    used_today = Column(Integer, default=0)
    last_reset_date = Column(Date, default=lambda: datetime.utcnow().date())

    # Период действия
    start_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Статус
    is_active = Column(Boolean, default=True)

    # Связь с оплатой (опционально)
    payment_id = Column(BigInteger, ForeignKey("payments.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payment = relationship("Payment", back_populates="subscription")
    downloads = relationship("Download", back_populates="subscription")


# ==================== НОВЫЕ МОДЕЛИ: БОНУСНАЯ СИСТЕМА ====================


class BonusType(Base):
    """
    Типы бонусов (конфигурация).

    Описывает правила начисления бонусов.
    Примеры: подписка на канал, первый вход, реферальная награда.
    """

    __tablename__ = "bonus_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)  # CHANNEL_SUBSCRIPTION, FIRST_LOGIN
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Награда
    reward_type = Column(Enum(BonusRewardType), nullable=False)
    credits_amount = Column(Integer, default=0)
    ai_credits_amount = Column(Integer, default=0)

    # Условия активации
    is_active = Column(Boolean, default=True)
    is_repeatable = Column(Boolean, default=False)  # Можно получить несколько раз?
    cooldown_days = Column(Integer, nullable=True)  # Период повтора (если repeatable)

    # Дополнительные условия (JSON)
    # Пример: {"min_referrals": 3, "require_payment": true}
    conditions = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Отношения
    user_bonuses = relationship(
        "UserBonus", back_populates="bonus_type", cascade="all, delete-orphan"
    )


class UserBonus(Base):
    """
    История начисления бонусов пользователям.

    Каждая запись = один начисленный бонус конкретному пользователю.
    """

    __tablename__ = "user_bonuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    bonus_type_id = Column(Integer, ForeignKey("bonus_types.id"), nullable=False)

    # Статус
    status = Column(Enum(BonusStatus), default=BonusStatus.PENDING, nullable=False)

    # Начисленные ресурсы
    credits_granted = Column(Integer, default=0)
    ai_credits_granted = Column(Integer, default=0)

    # Метаданные (JSON)
    # Пример: {"referral_id": 123, "channel_id": "@channel"}
    extra_data = Column("metadata", JSON, nullable=True)  # Column name in DB is still 'metadata'

    # Временные метки
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Отношения
    user = relationship("User", back_populates="bonuses")
    bonus_type = relationship("BonusType", back_populates="user_bonuses")


# ==================== ОБНОВЛЕННАЯ РЕФЕРАЛЬНАЯ СИСТЕМА ====================


class ReferralReward(Base):
    """
    Таблица вознаграждений за рефералов.

    ОБНОВЛЕНО: добавлена интеграция с бонусной системой.
    """

    __tablename__ = "referral_rewards"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Кто пригласил (referrer) и кто был приглашён (referred)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    referred_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Связь с бонусной системой (NEW)
    bonus_id = Column(Integer, ForeignKey("user_bonuses.id"), nullable=True)

    # Старая система (для совместимости)
    reward_type = Column(String, nullable=False)  # credits / subscription / bonus
    reward_value = Column(Integer, nullable=True)  # количество кредитов или дней подписки

    # Статус
    status = Column(Enum(ReferralRewardStatus), default=ReferralRewardStatus.PENDING)

    # Триггеры наград (NEW)
    trigger_type = Column(Enum(ReferralTriggerType), nullable=True)
    trigger_metadata = Column(JSON, nullable=True)

    # Условия выполнения
    condition_met = Column(Boolean, default=False)  # выполнено ли условие
    condition_date = Column(DateTime, nullable=True)  # когда условие выполнено

    # Даты
    created_at = Column(DateTime, default=datetime.utcnow)
    rewarded_at = Column(DateTime, nullable=True)  # когда выдано вознаграждение
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referral_rewards")
    referred = relationship("User", foreign_keys=[referred_id], back_populates="received_rewards")
    bonus = relationship("UserBonus", foreign_keys=[bonus_id])


# ==================== AI BOT: ЛОГИРОВАНИЕ ГЕНЕРАЦИЙ ====================


class AIGenerationLog(Base):
    """
    Логирование AI генераций для аналитики и отслеживания.

    Каждая запись = одна попытка генерации (изображение или видео).
    """

    __tablename__ = "ai_generation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Тип генерации
    provider = Column(String(50), nullable=False)  # KIE_AI, KLING, VEO
    model = Column(String(100), nullable=False)  # nano-banana, kling-2.6, veo-3.1
    generation_type = Column(Enum(AIGenerationType), nullable=False)  # IMAGE, VIDEO

    # Параметры запроса
    prompt = Column(Text, nullable=False)
    parameters = Column(JSON, nullable=True)  # aspect_ratio, resolution, duration, etc.

    # Результат
    status = Column(Enum(AIGenerationStatus), default=AIGenerationStatus.PENDING, nullable=False)
    result_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    # Затраты
    ai_credits_spent = Column(Integer, default=1)
    processing_time_seconds = Column(Integer, nullable=True)

    # Временные метки
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)

    # Отношения
    user = relationship("User", back_populates="ai_generations")


# ==================== WEB AUTH MODELS ====================


class SmsVerification(Base):
    """Коды SMS-верификации для входа на сайт"""

    __tablename__ = "sms_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())


class BotLinkRequest(Base):
    """Запросы на привязку бот-аккаунта к веб-аккаунту"""

    __tablename__ = "bot_link_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    web_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    bot_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(
        Enum("PENDING", "CONFIRMED", "REJECTED", "EXPIRED", name="link_request_status"),
        default="PENDING",
        nullable=False,
    )
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())

    web_user = relationship("User", foreign_keys=[web_user_id])
    bot_user = relationship("User", foreign_keys=[bot_user_id])


class QrLoginSession(Base):
    """QR/deep-link сессии входа на сайт через Telegram (Upscale-style).

    Сайт создаёт PENDING-сессию и показывает QR с deep-link
    ``t.me/<bot>?start=login_<token>``. Пользователь подтверждает вход в боте —
    бот ставит CONFIRMED + user_id, сайт по поллингу получает JWT.
    """

    __tablename__ = "qr_login_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(
        Enum("PENDING", "CONFIRMED", "REJECTED", "EXPIRED", name="qr_login_status"),
        default="PENDING",
        nullable=False,
    )
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    confirmed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
