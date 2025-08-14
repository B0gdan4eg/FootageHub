from db.session import get_session
from db.user_crud import add_daily_credits
from db.base import backup_database
from aiogram import Bot

async def scheduler_job(bot: Bot):
    """Ежедневная выдача кредитов."""
    async for session in get_session():
        await add_daily_credits(session, bot)

async def weekly_backup_job():
    """Еженедельный бэкап базы."""
    await backup_database()
