from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
CRYPTO_BOT_API_KEY = os.getenv("CRYPTO_BOT_API_KEY")
CRYPTO_BOT_WEBHOOK = os.getenv("CRYPTO_BOT_WEBHOOK")
ADMIN = os.getenv("ADMIN")