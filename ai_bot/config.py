"""
AI Bot Configuration

Environment variables and settings for AI Bot
"""
import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """AI Bot configuration"""

    # Bot settings
    AI_BOT_TOKEN: str = os.getenv("AI_BOT_TOKEN", "")
    ADMIN: int = int(os.getenv("ADMIN", "0"))

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/footagehub"
    )

    # AI Providers
    KIE_AI_API_KEY: str = os.getenv("KIE_AI_API_KEY", "")
    KIE_AI_BASE_URL: str = "https://api.kie.ai/v1"

    # Channel
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")

    # AI Credits pricing
    IMAGE_GENERATION_COST: int = 1  # AI credits per image
    VIDEO_GENERATION_COST: int = 5  # AI credits per video

    # Rate limiting
    MAX_CONCURRENT_GENERATIONS: int = 3
    GENERATION_COOLDOWN_SECONDS: int = 5

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration"""
        if not cls.AI_BOT_TOKEN:
            raise ValueError("AI_BOT_TOKEN is required")

        if not cls.KIE_AI_API_KEY:
            raise ValueError("KIE_AI_API_KEY is required")

        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")


config = Config()
