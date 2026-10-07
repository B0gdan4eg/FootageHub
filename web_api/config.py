"""Configuration for the web API."""

import os


class WebApiConfig:
    GOOGLE_AUTH_ENABLED = os.getenv("GOOGLE_AUTH_ENABLED", "false").lower() == "true"
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI", "https://envato-freepik-download.store/api/auth/google/callback"
    )
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней

    # SMSC.ru — SMS-провайдер для РФ
    SMSC_LOGIN: str = os.getenv("SMSC_LOGIN", "")
    SMSC_PASSWORD: str = os.getenv("SMSC_PASSWORD", "")
    SMSC_SENDER: str = os.getenv("SMSC_SENDER", "FOOTAGE")

    # Telegram Bot Token (для отправки сообщений при привязке аккаунтов)
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")  # Без @, нужен для Login Widget

    # Платёжные системы
    WEBPAY_RESOURCE_ID: str = os.getenv("WEBPAY_RESOURCE_ID", "")
    WEBPAY_SIGNING_KEY: str = os.getenv("WEBPAY_SIGNING_KEY", "")
    WEBPAY_SECRET_KEY: str = os.getenv("WEBPAY_SECRET_KEY", "")
    WEBPAY_SANDBOX: bool = os.getenv("WEBPAY_SANDBOX", "false").lower() == "true"
    CRYPTO_BOT_API_KEY: str = os.getenv("CRYPTO_BOT_API_KEY", "")

    # AI
    KIE_AI_API_KEY: str = os.getenv("KIE_AI_API_KEY", "")

    # CORS
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    ]

    # Rate limits
    SMS_MAX_PER_DAY: int = 5
    SMS_COOLDOWN_SECONDS: int = 60
    LINK_REQUEST_TTL_MINUTES: int = 10
    QR_LOGIN_TTL_MINUTES: int = 5  # Срок жизни QR-сессии входа через Telegram


config = WebApiConfig()


def validate_security_config() -> None:
    if (
        len(config.JWT_SECRET_KEY.strip()) < 32
        or config.JWT_SECRET_KEY == "change-me-in-production"  # nosec B105: reject legacy default
    ):
        raise RuntimeError("JWT_SECRET_KEY must be a non-default secret of at least 32 characters")
