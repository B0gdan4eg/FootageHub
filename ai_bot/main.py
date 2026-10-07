"""
AI Bot Main Entry Point

Telegram bot for AI content generation
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from ai_bot.config import config
from ai_bot.handlers import setup_handlers
from shared import error_tracking

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for AI Bot"""
    error_tracking.configure("ai-bot")
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    logger.info("Starting AI Bot...")

    # Initialize bot and dispatcher
    bot = Bot(token=config.AI_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher()
    dp.update.outer_middleware(error_tracking.TrackingMiddleware())

    # Setup handlers
    main_router = setup_handlers()
    dp.include_router(main_router)

    # Start polling
    try:
        logger.info("Bot started successfully! Polling for updates...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        error_tracking.report_exception(e)
        logger.error(f"Error during polling: {e}")
    finally:
        await error_tracking.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
