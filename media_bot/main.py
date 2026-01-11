import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from envato_utils.test_env import LinkProcessor
from freepik_utils.logger import logger as error_logger
from media_bot.config import BOT_TOKEN
from media_bot.handlers import (
    admin,
    channel_check,
    download,
    info,
    manager,
    menu,
    payment,
    referral,
    start,
)
from media_bot.schedule_tasks import (
    check_expired_subscriptions,
    cleanup_playwright_cache,
    daily_backup_job,
    process_monthly_subscriptions,
    scheduler_job,
)
from media_bot.services import BotServices
from media_bot.webhook.server_start import start_server
from shared.core.logger import get_logger
from shared.db.base import create_tables, run_migrations

# Setup centralized logging
logger = get_logger("media_bot", level=logging.INFO)
logger.info("=" * 60)
logger.info("MEDIA BOT STARTING - CENTRALIZED LOGGER ACTIVE")
logger.info("=" * 60)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def set_bot_commands(bot: Bot):
    """Устанавливает список команд бота, чтобы меню отображалось на всех устройствах."""
    commands = [
        BotCommand(command="menu", description="Меню"),
        BotCommand(command="envato", description="Скачать Envato"),
        BotCommand(command="freepik", description="Скачать Freepik"),
        BotCommand(command="motion", description="Скачать Motion Array"),
        BotCommand(command="info", description="Информация"),
        BotCommand(command="pay", description="Оформить подписку"),
        BotCommand(command="referral", description="Реферальная программа"),
    ]
    await bot.set_my_commands(commands)


# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize bot services
BotServices.bot = bot
BotServices.link_processor = LinkProcessor(max_workers=5)

# Initialize universal logger for error reporting
error_logger.set_bot(bot)

# Роутеры бота
# Порядок важен! Сначала роутеры с FSM состояниями, потом общие команды
dp.include_router(admin.router)  # Админ-панель с FSM состояниями
dp.include_router(manager.router)  # Менеджер-панель с FSM состояниями
dp.include_router(download.router)  # Скачивание с FSM состояниями (waiting_for_link)
dp.include_router(payment.router)  # Платежи (могут быть FSM состояния)
dp.include_router(channel_check.router)  # Проверка подписки на канал
dp.include_router(referral.router)  # Реферальная программа (команды без состояний)
dp.include_router(menu.router)  # Главное меню (сбрасывает состояния)
dp.include_router(info.router)  # Информация (сбрасывает состояния)
dp.include_router(start.router)  # /start должен быть последним (сбрасывает состояния)


async def start_bot():
    """Запуск Telegram-бота."""
    await dp.start_polling(bot)


async def main():
    # 1. Миграции перед стартом
    try:
        await run_migrations()
    except Exception as e:
        logger.warning(f"Миграции не выполнены: {e}")
        logger.info("Создаю таблицы напрямую...")
        await create_tables()

    await set_bot_commands(bot)

    # 2. Запуск LinkProcessor для Envato и Freepik
    logger.info("Запуск LinkProcessor (Envato + Freepik)...")
    await BotServices.link_processor.start()

    # 3. Планировщик
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Еженедельное начисление бесплатных кредитов (каждый понедельник в 03:00)
    scheduler.add_job(scheduler_job, "cron", day_of_week="wed", hour=3, minute=0, args=[bot])
    # Обработка месячных подписок (MONTHLY_50, MONTHLY_150, MONTHLY_400) в 03:05
    scheduler.add_job(process_monthly_subscriptions, "cron", hour=3, minute=5, args=[bot])
    # Проверка истекших подписок в 03:10
    scheduler.add_job(check_expired_subscriptions, "cron", hour=3, minute=10, args=[bot])
    # Ежедневный бэкап БД в 04:00
    scheduler.add_job(daily_backup_job, "interval", hours=4)
    # Очистка Playwright кэша каждые 2 часа
    scheduler.add_job(cleanup_playwright_cache, "interval", hours=1)
    scheduler.start()
    logger.info("✅ Scheduler started:")
    logger.info("  - Weekly free credits: Every Monday at 03:00")
    logger.info("  - Monthly subscriptions processing: Daily at 03:05")
    logger.info("  - Expired subscriptions check: Daily at 03:10")
    logger.info("  - Database backup: Every 4 hours")
    logger.info("  - Playwright cleanup: Every hour")

    try:
        # 4. Запуск сервера и бота параллельно
        await asyncio.gather(start_server(), start_bot())
    finally:
        # Остановка LinkProcessor при завершении
        logger.info("Остановка LinkProcessor...")
        await BotServices.link_processor.stop()


if __name__ == "__main__":
    asyncio.run(main())
