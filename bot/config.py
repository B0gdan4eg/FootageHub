from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
CRYPTO_BOT_API_KEY = os.getenv("CRYPTO_BOT_API_KEY")
CRYPTO_BOT_WEBHOOK = os.getenv("CRYPTO_BOT_WEBHOOK")
ADMIN = os.getenv("ADMIN")

# WebPay configuration
WEBPAY_RESOURCE_ID = os.getenv("WEBPAY_RESOURCE_ID")  # Идентификатор магазина (merchantId)
WEBPAY_API_KEY = os.getenv("WEBPAY_API_KEY")  # Username для логина
WEBPAY_SECRET_KEY = os.getenv("WEBPAY_SECRET_KEY")  # Password для логина / Secret key для webhook
WEBPAY_AUTH_TOKEN = os.getenv("WEBPAY_AUTH_TOKEN")  # Auth token (получить через get_webpay_token.py)
WEBPAY_SANDBOX = os.getenv("WEBPAY_SANDBOX")