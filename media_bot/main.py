import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from media_bot.config import BOT_TOKEN
from media_bot.handlers import (
    admin,
    channel_check,
    download,
    info,
    lang,
    link_account,
    manager,
    menu,
    payment,
    perpetual_credits,
    qr_login,
    referral,
    start,
)
from media_bot.middlewares import I18nMiddleware
from media_bot.schedule_tasks import (
    check_expired_subscriptions,
    cleanup_playwright_cache,
    daily_backup_job,
    process_monthly_subscriptions,
    scheduler_job,
)
from media_bot.services import BotServices
from media_bot.utils.envato_utils.test_env import LinkProcessor
from media_bot.utils.freepik_utils.logger import logger as error_logger
from media_bot.webhook.server_start import start_server
from shared.core.logger import get_logger
from shared.db.base import create_tables, run_migrations
from shared.db.init_bonuses import initialize_bonuses

# Setup centralized logging
logger = get_logger("media_bot", level=logging.INFO)
logger.info("=" * 60)
logger.info("MEDIA BOT STARTING - CENTRALIZED LOGGER ACTIVE")
logger.info("=" * 60)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def set_bot_commands(bot: Bot):
    """Устанавливает список команд бота на двух языках."""
    from media_bot.handlers.messages import msg

    ru_commands = [
        BotCommand(command="menu", description=msg("CMD_MENU", "ru")),
        BotCommand(command="envato", description=msg("CMD_ENVATO", "ru")),
        BotCommand(command="freepik", description=msg("CMD_FREEPIK", "ru")),
        BotCommand(command="motion", description=msg("CMD_MOTION", "ru")),
        BotCommand(command="info", description=msg("CMD_INFO", "ru")),
        BotCommand(command="pay", description=msg("CMD_PAY", "ru")),
        BotCommand(command="referral", description=msg("CMD_REFERRAL", "ru")),
        BotCommand(command="lang", description=msg("CMD_LANG", "ru")),
    ]

    en_commands = [
        BotCommand(command="menu", description=msg("CMD_MENU", "en")),
        BotCommand(command="envato", description=msg("CMD_ENVATO", "en")),
        BotCommand(command="freepik", description=msg("CMD_FREEPIK", "en")),
        BotCommand(command="motion", description=msg("CMD_MOTION", "en")),
        BotCommand(command="info", description=msg("CMD_INFO", "en")),
        BotCommand(command="pay", description=msg("CMD_PAY", "en")),
        BotCommand(command="referral", description=msg("CMD_REFERRAL", "en")),
        BotCommand(command="lang", description=msg("CMD_LANG", "en")),
    ]

    # Дефолтные команды (русские)
    await bot.set_my_commands(ru_commands)
    # Per-language команды
    await bot.set_my_commands(ru_commands, language_code="ru")
    await bot.set_my_commands(en_commands, language_code="en")


# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize bot services
BotServices.bot = bot
BotServices.link_processor = LinkProcessor(max_workers=5)

# Initialize universal logger for error reporting
error_logger.set_bot(bot)

# i18n middleware — определяет язык и инжектит data["lang"]
dp.message.middleware(I18nMiddleware())
dp.callback_query.middleware(I18nMiddleware())

# Роутеры бота
# Порядок важен! Сначала роутеры с FSM состояниями, потом общие команды
dp.include_router(link_account.router)  # Привязка web-аккаунта (callback без состояний)
dp.include_router(qr_login.router)  # QR-вход на сайт (callback подтверждения входа)
dp.include_router(lang.router)  # Выбор языка (до остальных команд)
dp.include_router(admin.router)  # Админ-панель с FSM состояниями
dp.include_router(manager.router)  # Менеджер-панель с FSM состояниями
dp.include_router(download.router)  # Скачивание с FSM состояниями (waiting_for_link)
dp.include_router(payment.router)  # Платежи (могут быть FSM состояния)
dp.include_router(perpetual_credits.router)  # Несгораемые кредиты с FSM
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

    # 2. Инициализация бонусов
    try:
        logger.info("Инициализация бонусной системы...")
        bonus_stats = await initialize_bonuses()
        logger.info(
            f"🎁 Бонусы инициализированы: создано {bonus_stats['created']}, "
            f"обновлено {bonus_stats['updated']}"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бонусов: {e}")

    await set_bot_commands(bot)

    # 3. Запуск LinkProcessor для Envato и Freepik
    logger.info("Запуск LinkProcessor (Envato + Freepik)...")
    await BotServices.link_processor.start()

    # 4. Планировщик
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
        # 5. Запуск сервера и бота параллельно
        await asyncio.gather(start_server(), start_bot())
    finally:
        # Остановка LinkProcessor при завершении
        logger.info("Остановка LinkProcessor...")
        await BotServices.link_processor.stop()


if __name__ == "__main__":
    asyncio.run(main())
