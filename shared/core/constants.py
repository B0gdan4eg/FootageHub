"""
Constants for FootageHub application.
"""

# ==================== BONUS CODES ====================


class BonusCodes:
    """Bonus type codes"""

    CHANNEL_SUBSCRIPTION = "CHANNEL_SUBSCRIPTION"
    FIRST_LOGIN = "FIRST_LOGIN"
    REFERRAL_REGISTRATION = "REFERRAL_REGISTRATION"
    REFERRAL_FIRST_PAYMENT = "REFERRAL_FIRST_PAYMENT"
    DAILY_LOGIN = "DAILY_LOGIN"


# ==================== DOWNLOAD LIMITS ====================


class DownloadLimits:
    """Download-related constants"""

    MIN_CREDITS_FOR_DOWNLOAD = 1
    DOWNLOAD_COOLDOWN_SECONDS = 3
    MAX_CONCURRENT_DOWNLOADS = 5


# ==================== AI LIMITS ====================


class AILimits:
    """AI generation limits"""

    MIN_AI_CREDITS_FOR_IMAGE = 1
    MIN_AI_CREDITS_FOR_VIDEO = 5

    # Timeouts
    IMAGE_GENERATION_TIMEOUT_SECONDS = 300  # 5 minutes
    VIDEO_GENERATION_TIMEOUT_SECONDS = 600  # 10 minutes

    # Polling intervals
    POLL_INTERVAL_INITIAL_SECONDS = 2
    POLL_INTERVAL_MID_SECONDS = 5
    POLL_INTERVAL_LATE_SECONDS = 10


# ==================== REFERRAL ====================


class ReferralRewards:
    """Referral reward amounts"""

    REGISTRATION_CREDITS = 3  # Начисляется когда реферал подписался на канал
    FIRST_PAYMENT_CREDITS = 3
    FIRST_PAYMENT_AI_CREDITS = 0  # AI кредиты больше не используются


# ==================== CHANNEL ====================


class ChannelConfig:
    """Channel-related configuration"""

    BONUS_CREDITS = 3  # Credits for subscribing to channel
