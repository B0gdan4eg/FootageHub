from sqlalchemy import (
    Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, Numeric, Text, Enum
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
    
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String)
    is_subscribed = Column(Boolean, default=False)
    subscription_until = Column(DateTime, nullable=True)
    credits = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # New fields
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    referral_code = Column(String, unique=True, nullable=True)
    referred_by_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    
    # Relationships
    referrals = relationship("User", backref="referrer", remote_side=[id])
    downloads = relationship("Download", back_populates="user")
    payments = relationship("Payment", back_populates="user")

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
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    paid = Column(Boolean, default=False)

    user = relationship("User", back_populates="downloads")
    media = relationship("Media", back_populates="downloads")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    amount = Column(Numeric, nullable=False)
    currency = Column(String)  # Например, USDT
    type = Column(String)  # subscription / credits
    status = Column(String, default="pending")  # pending / success / failed
    invoice_id = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payments")
