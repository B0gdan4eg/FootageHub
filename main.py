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
from bot.schedule_tasks import scheduler_job, daily_backup_job, cleanup_playwright_cache, process_monthly_subscriptions, check_expired_subscriptions
from bot.webhook.server_start import start_server
from envato_utils.test_env import LinkProcessor
from bot.services import BotServices
from freepik_utils.logger import logger

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
        BotCommand(command="freepik", description="Скачать Freepik"),
        BotCommand(command="info", description="Информация"),
        BotCommand(command="menu", description="Меню"),
        BotCommand(command="pay", description="Увеличить лимиты"),
    ]
    await bot.set_my_commands(commands)

# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize bot services
BotServices.bot = bot
BotServices.link_processor = LinkProcessor(max_workers=5)

# Initialize universal logger for error reporting
logger.set_bot(bot)

# Роутеры бота
dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(manager.router)
dp.include_router(menu.router)
dp.include_router(info.router)
dp.include_router(download.router)
dp.include_router(channel_check.router)
dp.include_router(payment.router)
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

    # 2. Запуск LinkProcessor для Envato и Freepik
    print("[INFO] Запуск LinkProcessor (Envato + Freepik)...")
    await BotServices.link_processor.start()

    # 3. Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Ежедневное начисление кредитов в 03:00
    scheduler.add_job(scheduler_job, "cron", hour=3, minute=0, args=[bot])
    # Обработка месячных подписок (MONTHLY_150) в 03:05
    scheduler.add_job(process_monthly_subscriptions, "cron", hour=3, minute=5, args=[bot])
    # Проверка истекших подписок в 03:10
    scheduler.add_job(check_expired_subscriptions, "cron", hour=3, minute=10, args=[bot])
    # Ежедневный бэкап БД в 04:00
    scheduler.add_job(daily_backup_job, "interval", hours=4)
    # Очистка Playwright кэша каждые 2 часа
    scheduler.add_job(cleanup_playwright_cache, "interval", hours=1)
    scheduler.start()
    print("[INFO] ✅ Scheduler started:")
    print("  - Daily credits: 03:00")
    print("  - MONTHLY_150 processing: 03:05")
    print("  - Expired subscriptions check: 03:10")
    print("  - Daily backup: every 4 hours")
    print("  - Playwright cleanup: every 2 hours")

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
    