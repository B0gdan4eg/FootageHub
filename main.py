import sys
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import BOT_TOKEN
from bot.handlers import start, download, info, admin, payment, channel_check, manager
from db.base import run_migrations, create_tables
from bot.schedule_tasks import scheduler_job, weekly_backup_job
from bot.webhook.server_start import start_server

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Роутеры бота
dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(info.router)
dp.include_router(download.router)
dp.include_router(payment.router)
dp.include_router(channel_check.router)
dp.include_router(manager.router)

async def start_bot():
    """Запуск Telegram-бота."""
    await dp.start_polling(bot)

async def main():
    # 1. Миграции перед стартом
    try:
        await run_migrations()
    except Exception as e:
        print(f"[WARN] Миграции не выполнены: {e}")
        print("[INFO] Создаю таблицы напрямую...")
        await create_tables()

    # 2. Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(scheduler_job, "cron", hour=3, minute=0, args=[bot])
    scheduler.add_job(weekly_backup_job, "cron", day_of_week="sun", hour=4, minute=0)
    scheduler.start()

    # 3. Запуск сервера и бота параллельно
    await asyncio.gather(
        start_server(),
        start_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())
