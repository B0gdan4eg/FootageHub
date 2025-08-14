import sys
import asyncio
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from bot.config import BOT_TOKEN, DATABASE_URL
from bot.handlers import start, download, info, admin, payment
from bot.webhook import cryptobot
from db.user_crud import add_daily_credits
from db.base import backup_database, run_migrations







# Добавить в самое начало файла, перед созданием приложения
import os
import logging
from sqlalchemy import create_engine  # Если используете SQLAlchemy

# Настройка логов для диагностики
logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)

# Функция диагностики
async def log_db_config():
    logger.critical("=== DIAGNOSTICS START ===")
    logger.critical(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
    logger.critical(f"POSTGRES_DB: {os.getenv('POSTGRES_DB')}")
    logger.critical(f"DB_HOST: {os.getenv('DB_HOST', 'db')}")
    
    try:
        engine = create_engine(os.getenv("DATABASE_URL"))
        logger.critical(f"SQLAlchemy URL: {engine.url}")
    except Exception as e:
        logger.critical(f"SQLAlchemy error: {e}")

# Вызов диагностики перед запуском приложения


# ... ваш обычный код запуска приложения ...














# Настройка Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# FastAPI app
app = FastAPI()
app.include_router(cryptobot.router)

# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Роутеры бота
dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(info.router)
dp.include_router(download.router)
dp.include_router(payment.router)

# Подключение к базе
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Планировщик
async def scheduler_job():
    async with async_session() as session:
        await add_daily_credits(session, bot)

async def weekly_backup_job():
    await backup_database()

async def start_bot():
    await run_migrations()
    await log_db_config()
    await dp.start_polling(bot)

async def main():
    # Инициализация планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(scheduler_job, "cron", hour=3, minute=0)
    scheduler.add_job(weekly_backup_job, "cron", day_of_week="sun", hour=4, minute=0)
    scheduler.start()

    config = uvicorn.Config(
        app, host="0.0.0.0", port=443,
        ssl_certfile="/app/ssl/cert.pem",
        ssl_keyfile="/app/ssl/key.pem",
        log_level="info"
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),  # Если нужен вебхук — раскомментировать
        start_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())
