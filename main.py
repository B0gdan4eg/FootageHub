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
    # await run_migrations()
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
    asyncio.run(start_bot())
