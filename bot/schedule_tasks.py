import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from sqlalchemy import and_, select, update

from bot.config import DAILY_FREE_CREDITS
from db.base import backup_database
from db.models import Subscription, SubscriptionType, User
from db.session import get_session


async def scheduler_job(bot: Bot):
    """Еженедельная выдача бесплатных кредитов."""
    print("🎁 Еженедельное начисление бесплатных кредитов!")
    async for session in get_session():
        # Всем пользователям начисляем базовые бесплатные кредиты
        await session.execute(update(User).values(credits=DAILY_FREE_CREDITS))

        result = await session.execute(select(User))
        total_users = len(result.scalars().all())
        print(f"✅ Начислено {DAILY_FREE_CREDITS} бесплатных кредитов {total_users} пользователям")

        # Получаем всех пользователей с активной дневной подпиской
        result = await session.execute(
            select(User.id)
            .join(Subscription)
            .where(
                and_(
                    Subscription.subscription_type == SubscriptionType.DAILY_30,
                    Subscription.is_active,
                    Subscription.end_date > datetime.utcnow(),
                )
            )
        )
        daily_sub_users = result.scalars().all()

        # Начисляем 30 кредитов пользователям с дневной подпиской
        if daily_sub_users:
            await session.execute(
                update(User).where(User.id.in_(daily_sub_users)).values(credits=30)
            )
            print(
                f"✅ Начислено 30 кредитов {len(daily_sub_users)} пользователям с дневной подпиской"
            )

        await session.commit()
        # await add_daily_credits(session, bot)


async def process_monthly_subscriptions(bot: Bot):
    """Обработка месячных подписок (MONTHLY_50, MONTHLY_150, MONTHLY_400) - начисление остатка и деактивация при исчерпании."""
    print("🔄 Обработка месячных подписок (MONTHLY_50, MONTHLY_150, MONTHLY_400)...")
    async for session in get_session():
        # Получаем активные месячные подписки всех типов
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.subscription_type.in_(
                        [
                            SubscriptionType.MONTHLY_50,
                            SubscriptionType.MONTHLY_150,
                            SubscriptionType.MONTHLY_400,
                        ]
                    ),
                    Subscription.is_active,
                    Subscription.end_date > datetime.utcnow(),
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
                # Обновляем кредиты до оставшегося количества
                result = await session.execute(select(User).where(User.id == subscription.user_id))
                user = result.scalar_one_or_none()
                if user:
                    user.credits = remaining_credits
                    print(
                        f"✅ Обновлены кредиты до {remaining_credits} для пользователя {subscription.user_id} ({subscription.subscription_type.value})"
                    )
                    processed_count += 1
            else:
                # Лимит исчерпан - деактивируем подписку
                subscription.is_active = False
                subscription.updated_at = datetime.utcnow()
                print(
                    f"⚠️ Подписка #{subscription.id} деактивирована (лимит исчерпан, пользователь {subscription.user_id})"
                )
                deactivated_count += 1

            # Сбрасываем used_today в любом случае
            subscription.used_today = 0

        await session.commit()

        if processed_count > 0 or deactivated_count > 0:
            print(
                f"✅ Обработка месячных подписок завершена: начислено {processed_count}, деактивировано {deactivated_count}"
            )
        else:
            print("✅ Нет активных месячных подписок для обработки")


async def check_expired_subscriptions(bot: Bot):
    """Проверка и деактивация истекших подписок."""
    print("🔄 Проверка истекших подписок...")
    async for session in get_session():
        # Находим все активные подписки, срок которых истек
        result = await session.execute(
            select(Subscription).where(
                and_(Subscription.is_active, Subscription.end_date <= datetime.utcnow())
            )
        )
        expired_subscriptions = result.scalars().all()

        if expired_subscriptions:
            expired_count = 0
            for subscription in expired_subscriptions:
                subscription.is_active = False
                subscription.updated_at = datetime.utcnow()
                print(
                    f"⏰ Подписка #{subscription.id} деактивирована (истек срок): "
                    f"тип={subscription.subscription_type.value}, "
                    f"пользователь={subscription.user_id}, "
                    f"окончание={subscription.end_date.strftime('%Y-%m-%d %H:%M')}"
                )
                expired_count += 1

            await session.commit()
            print(f"✅ Деактивировано истекших подписок: {expired_count}")
        else:
            print("✅ Нет истекших подписок")


async def daily_backup_job():
    """Ежедневный бэкап базы данных."""
    print("🔄 Starting daily database backup...")
    try:
        await backup_database()
        print("✅ Daily backup completed successfully")
    except Exception as e:
        print(f"❌ Daily backup failed: {e}")


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
                size_mb = sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file()) / (
                    1024 * 1024
                )
                total_size += size_mb

                # Remove directory
                shutil.rmtree(dir_path, ignore_errors=True)
                removed_count += 1
                print(f"   🗑️ Removed: {dir_path.name} ({size_mb:.2f} MB)")
            except Exception as e:
                print(f"   ⚠️ Failed to remove {dir_path.name}: {e}")

    if removed_count > 0:
        print(f"✅ Cleanup complete: Removed {removed_count} directories, freed {total_size:.2f} MB")
    else:
        print("✅ No Playwright cache to clean")
