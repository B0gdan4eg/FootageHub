from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
CRYPTO_BOT_API_KEY = os.getenv("CRYPTO_BOT_API_KEY")
CRYPTO_BOT_WEBHOOK = os.getenv("CRYPTO_BOT_WEBHOOK")
ADMIN = os.getenv("ADMIN")

# WebPay configuration
WEBPAY_RESOURCE_ID = os.getenv("WEBPAY_RESOURCE_ID")  # Идентификатор магазина (merchantId)
WEBPAY_API_KEY = os.getenv("WEBPAY_API_KEY")  # Username для логина
WEBPAY_SECRET_KEY = os.getenv("WEBPAY_SECRET_KEY")  # Password для логина
WEBPAY_SIGNING_KEY = os.getenv("WEBPAY_SIGNING_KEY")  # Secret key для подписи платежей
WEBPAY_AUTH_TOKEN = os.getenv("WEBPAY_AUTH_TOKEN")  # Auth token (получить через get_webpay_token.py)
WEBPAY_SANDBOX = os.getenv("WEBPAY_SANDBOX", "false").lower() == "true"

# Channel configuration
CHANNEL_ID = os.getenv("CHANNEL_ID", "@footagehub_channel")
CHANNEL_BONUS_CREDITS = int(os.getenv("CHANNEL_BONUS_CREDITS", "2"))

# Kie.ai API configuration
KIE_AI_API_KEY = os.getenv("KIE_AI_API_KEY")

# File paths
BOT_DIR = Path(__file__).resolve().parent
HANDLERS_DIR = BOT_DIR / "handlers"
PRICE_LIST_PATH = HANDLERS_DIR / "prices_list.json"

# Лимиты и таймауты
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
BROWSER_RESTART_AFTER = int(os.getenv("BROWSER_RESTART_AFTER", "50"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "300"))

# Бонусы и кредиты
DAILY_FREE_CREDITS = int(os.getenv("DAILY_FREE_CREDITS", "3"))

# Размеры браузера
BROWSER_VIEWPORT_WIDTH = 1920
BROWSER_VIEWPORT_HEIGHT = 1080