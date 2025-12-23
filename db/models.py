from sqlalchemy import (
    Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, Numeric, Text, Enum, Date
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"
    MANAGER = "manager"
    PARTNER = "partner"

class SubscriptionType(enum.Enum):
    MONTHLY_50 = "monthly_50"    # 50 скачиваний на месяц (Lite)
    MONTHLY_150 = "monthly_150"  # 150 скачиваний на месяц (Standard)
    MONTHLY_400 = "monthly_400"  # 400 скачиваний на месяц (Pro)
    DAILY_30 = "daily_30"        # 30 скачиваний каждый день
    UNLIMITED = "unlimited"       # без лимитов
    CUSTOM = "custom"             # кастомные условия

class ServiceType(enum.Enum):
    ENVATO = "ENVATO"
    FREEPIK = "FREEPIK"
    MOTION_ARRAY = "MOTION_ARRAY"
    ALL = "ALL"  # доступ ко всем сервисам

class ReferralRewardStatus(enum.Enum):
    PENDING = "pending"      # ожидает выполнения условий
    COMPLETED = "completed"  # вознаграждение выдано
    CANCELLED = "cancelled"  # отменено
    
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)

    # Бесплатные кредиты (начисляются ежедневно всем пользователям)
    credits = Column(Integer, default=0)

    # Реферальная система
    referral_code = Column(String, unique=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    downloads = relationship("Download", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    referral_rewards = relationship("ReferralReward", foreign_keys="ReferralReward.referrer_id", back_populates="referrer")
    received_rewards = relationship("ReferralReward", foreign_keys="ReferralReward.referred_id", back_populates="referred")

class Media(Base):
    __tablename__ = "media"

    id = Column(BigInteger, primary_key=True)
    url = Column(Text, unique=True, nullable=False)
    file_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    downloads = relationship("Download", back_populates="media")


class Download(Base):
    __tablename__ = "downloads"

    id = Column(BigInteger, primary_key=True)
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
    __tablename__ = "payments"

    id = Column(BigInteger, primary_key=True)
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

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)

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
    payment_id = Column(BigInteger, ForeignKey('payments.id'), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payment = relationship("Payment", back_populates="subscription")
    downloads = relationship("Download", back_populates="subscription")


class ReferralReward(Base):
    """Таблица вознаграждений за рефералов"""
    __tablename__ = "referral_rewards"

    id = Column(BigInteger, primary_key=True)

    # Кто пригласил (referrer) и кто был приглашён (referred)
    referrer_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    referred_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)

    # Тип вознаграждения
    reward_type = Column(String, nullable=False)  # credits / subscription / bonus
    reward_value = Column(Integer, nullable=True)  # количество кредитов или дней подписки

    # Статус
    status = Column(Enum(ReferralRewardStatus), default=ReferralRewardStatus.PENDING)

    # Условия выполнения
    condition_met = Column(Boolean, default=False)  # выполнено ли условие (например, реферал купил подписку)
    condition_date = Column(DateTime, nullable=True)  # когда условие выполнено

    # Даты
    created_at = Column(DateTime, default=datetime.utcnow)
    rewarded_at = Column(DateTime, nullable=True)  # когда выдано вознаграждение

    # Relationships
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referral_rewards")
    referred = relationship("User", foreign_keys=[referred_id], back_populates="received_rewards")
