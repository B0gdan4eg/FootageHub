from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
CRYPTO_BOT_API_KEY = os.getenv("CRYPTO_BOT_API_KEY")
CRYPTO_BOT_WEBHOOK = os.getenv("CRYPTO_BOT_WEBHOOK")
ADMIN = os.getenv("ADMIN")

# WebPay configuration
WEBPAY_RESOURCE_ID = os.getenv("WEBPAY_RESOURCE_ID")  # Идентификатор магазина
WEBPAY_API_KEY = os.getenv("WEBPAY_API_KEY")  # API ключ
WEBPAY_SECRET_KEY = os.getenv("WEBPAY_SECRET_KEY")  # Secret key для проверки подписи
WEBPAY_SANDBOX = os.getenv("WEBPAY_SANDBOX", "true").lower() == "true"  # Sandbox режим