"""Database repositories."""

from shared.db.repositories.ai_repository import AIRepository
from shared.db.repositories.base import BaseRepository
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.download_repository import DownloadRepository
from shared.db.repositories.media_repository import MediaRepository
from shared.db.repositories.payment_repository import PaymentRepository
from shared.db.repositories.referral_repository import ReferralRewardRepository
from shared.db.repositories.subscription_repository import SubscriptionRepository
from shared.db.repositories.user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "SubscriptionRepository",
    "BonusRepository",
    "AIRepository",
    "DownloadRepository",
    "MediaRepository",
    "PaymentRepository",
    "ReferralRewardRepository",
]
