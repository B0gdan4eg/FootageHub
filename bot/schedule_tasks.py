from db.session import get_session
from db.user_crud import add_daily_credits
from db.base import backup_database
from aiogram import Bot
import logging
from db.models import User
from sqlalchemy import update
import shutil
import tempfile
from pathlib import Path

async def scheduler_job(bot: Bot):
    """Ежедневная выдача кредитов."""
    logging.info("Ежедневное начисление!")
    async for session in get_session():
        await session.execute(update(User).values(credits=5))
        await session.commit()
        # await add_daily_credits(session, bot)

async def daily_backup_job():
    """Ежедневный бэкап базы данных."""
    logging.info("🔄 Starting daily database backup...")
    try:
        await backup_database()
        logging.info("✅ Daily backup completed successfully")
    except Exception as e:
        logging.error(f"❌ Daily backup failed: {e}")

def cleanup_playwright_cache():
    """Очистка временных файлов Playwright для освобождения места на диске."""
    logging.info("🧹 Starting Playwright cache cleanup...")

    temp_dir = Path(tempfile.gettempdir())
    patterns = ["playwright*", "playwright_*", "chromium*", ".playwright-*"]

    total_size = 0
    removed_count = 0

    for pattern in patterns:
        for dir_path in temp_dir.glob(pattern):
            try:
                # Calculate size
                size_mb = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file()) / (1024 * 1024)
                total_size += size_mb

                # Remove directory
                shutil.rmtree(dir_path, ignore_errors=True)
                removed_count += 1
                logging.info(f"   🗑️ Removed: {dir_path.name} ({size_mb:.2f} MB)")
            except Exception as e:
                logging.warning(f"   ⚠️ Failed to remove {dir_path.name}: {e}")

    if removed_count > 0:
        logging.info(f"✅ Cleanup complete: Removed {removed_count} directories, freed {total_size:.2f} MB")
    else:
        logging.info("✅ No Playwright cache to clean")
