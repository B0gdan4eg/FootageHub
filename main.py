import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.types import BotCommand
from bot.config import BOT_TOKEN
from bot.handlers import start, download, info, admin, payment, channel_check, manager, menu #group_st
from db.base import run_migrations, create_tables
from bot.schedule_tasks import scheduler_job, weekly_backup_job
from bot.webhook.server_start import start_server
from envato_utils.test_env import LinkProcessor
from bot.services import BotServices

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),  # Save to file
        logging.StreamHandler()  # Also print to console
    ]
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
async def set_bot_commands(bot: Bot):
    """Устанавливает список команд бота, чтобы меню отображалось на всех устройствах."""
    commands = [
        BotCommand(command="envato", description="Скачать Envato"),
        BotCommand(command="freepik", description="Скачать Freepik(Скоро...)"),
        BotCommand(command="info", description="Информация"),
        BotCommand(command="menu", description="Меню"),
    ]
    await bot.set_my_commands(commands)

# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize link processor for Envato downloads
BotServices.link_processor = LinkProcessor(max_workers=3)

# Роутеры бота
dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(menu.router)
dp.include_router(info.router)
dp.include_router(download.router)
dp.include_router(payment.router)
dp.include_router(channel_check.router)
dp.include_router(manager.router)
#dp.include_router(group_st.router)

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

    await set_bot_commands(bot)

    # 2. Запуск LinkProcessor для Envato
    print("[INFO] Запуск LinkProcessor...")
    await BotServices.link_processor.start()

    # 3. Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(scheduler_job, "cron", hour=3, minute=0, args=[bot])
    scheduler.add_job(weekly_backup_job, "cron", day_of_week="sun", hour=4, minute=0)
    scheduler.start()

    try:
        # 4. Запуск сервера и бота параллельно
        await asyncio.gather(
            start_server(),
            start_bot()
        )
    finally:
        # Остановка LinkProcessor при завершении
        print("[INFO] Остановка LinkProcessor...")
        await BotServices.link_processor.stop()

if __name__ == "__main__":
    asyncio.run(main())
