from db.session import get_session
from db.user_crud import add_daily_credits
from db.base import backup_database
from aiogram import Bot
import logging
from db.models import User, Subscription, SubscriptionType
from sqlalchemy import update, select, and_
from datetime import datetime
import shutil
import tempfile
from pathlib import Path

async def scheduler_job(bot: Bot):
    """Ежедневная выдача кредитов."""
    logging.info("Ежедневное начисление!")
    async for session in get_session():
        # Всем пользователям начисляем базовые 3 кредита
        await session.execute(update(User).values(credits=3))

        # Получаем всех пользователей с активной дневной подпиской
        result = await session.execute(
            select(User.id).join(Subscription).where(
                and_(
                    Subscription.subscription_type == SubscriptionType.DAILY_30,
                    Subscription.is_active == True,
                    Subscription.end_date > datetime.utcnow()
                )
            )
        )
        daily_sub_users = result.scalars().all()

        # Начисляем 30 кредитов пользователям с дневной подпиской
        if daily_sub_users:
            await session.execute(
                update(User)
                .where(User.id.in_(daily_sub_users))
                .values(credits=30)
            )
            logging.info(f"✅ Начислено 30 кредитов {len(daily_sub_users)} пользователям с дневной подпиской")

        await session.commit()
        # await add_daily_credits(session, bot)

async def process_monthly_subscriptions(bot: Bot):
    """Обработка месячных подписок MONTHLY_150 - начисление остатка и деактивация при исчерпании."""
    logging.info("🔄 Обработка месячных подписок MONTHLY_150...")
    async for session in get_session():
        # Получаем активные месячные подписки
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.subscription_type == SubscriptionType.MONTHLY_150,
                    Subscription.is_active == True,
                    Subscription.end_date > datetime.utcnow()
                )
            )
        )
        monthly_subscriptions = result.scalars().all()

        processed_count = 0
        deactivated_count = 0

        for subscription in monthly_subscriptions:
            # Вычисляем остаток кредитов
            remaining_credits = subscription.total_limit - subscription.used_total

            if remaining_credits > 0:
                # Начисляем оставшиеся кредиты
                result = await session.execute(
                    select(User).where(User.id == subscription.user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    user.credits += remaining_credits
                    logging.info(f"✅ Начислено {remaining_credits} кредитов пользователю {subscription.user_id} (MONTHLY_150)")
                    processed_count += 1
            else:
                # Лимит исчерпан - деактивируем подписку
                subscription.is_active = False
                subscription.updated_at = datetime.utcnow()
                logging.info(f"⚠️ Подписка #{subscription.id} деактивирована (лимит исчерпан, пользователь {subscription.user_id})")
                deactivated_count += 1

        await session.commit()

        if processed_count > 0 or deactivated_count > 0:
            logging.info(f"✅ Обработка MONTHLY_150 завершена: начислено {processed_count}, деактивировано {deactivated_count}")
        else:
            logging.info("✅ Нет активных подписок MONTHLY_150 для обработки")

async def check_expired_subscriptions(bot: Bot):
    """Проверка и деактивация истекших подписок."""
    logging.info("🔄 Проверка истекших подписок...")
    async for session in get_session():
        # Находим все активные подписки, срок которых истек
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.is_active == True,
                    Subscription.end_date <= datetime.utcnow()
                )
            )
        )
        expired_subscriptions = result.scalars().all()

        if expired_subscriptions:
            expired_count = 0
            for subscription in expired_subscriptions:
                subscription.is_active = False
                subscription.updated_at = datetime.utcnow()
                logging.info(
                    f"⏰ Подписка #{subscription.id} деактивирована (истек срок): "
                    f"тип={subscription.subscription_type.value}, "
                    f"пользователь={subscription.user_id}, "
                    f"окончание={subscription.end_date.strftime('%Y-%m-%d %H:%M')}"
                )
                expired_count += 1

            await session.commit()
            logging.info(f"✅ Деактивировано истекших подписок: {expired_count}")
        else:
            logging.info("✅ Нет истекших подписок")

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
    print("🧹 Starting Playwright cache cleanup...")

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
        print(f"✅ Cleanup complete: Removed {removed_count} directories, freed {total_size:.2f} MB")
    else:
        print("✅ No Playwright cache to clean")
