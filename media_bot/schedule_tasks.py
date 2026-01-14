import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from sqlalchemy import and_, select, update

from media_bot.config import DAILY_FREE_CREDITS
from shared.db.base import backup_database
from shared.db.models import Subscription, SubscriptionType, User
from shared.db.session import get_session


async def scheduler_job(bot: Bot):
    """Еженедельное пополнение бесплатных кредитов до 5."""
    print("🎁 Еженедельное пополнение бесплатных кредитов!")
    async for session in get_session():
        # Получаем всех пользователей с кредитами < 5
        result = await session.execute(select(User).where(User.credits < DAILY_FREE_CREDITS))
        users_to_top_up = result.scalars().all()

        # Пополняем кредиты до 5
        topped_up_count = 0
        for user in users_to_top_up:
            user.credits = DAILY_FREE_CREDITS
            topped_up_count += 1

        # Статистика
        total_result = await session.execute(select(User))
        total_users = len(total_result.scalars().all())

        print(f"✅ Пополнено кредитов для {topped_up_count} пользователей")
        print(
            f"📊 {total_users - topped_up_count} пользователей уже имели >= {DAILY_FREE_CREDITS} кредитов"
        )

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
    """Обработка месячных подписок (MONTHLY_50, MONTHLY_150, MONTHLY_400) - сброс дневного лимита и деактивация при исчерпании."""
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

        deactivated_count = 0

        for subscription in monthly_subscriptions:
            # Проверяем, исчерпан ли лимит
            if subscription.total_limit <= subscription.used_total:
                # Лимит исчерпан - деактивируем подписку
                subscription.is_active = False
                subscription.updated_at = datetime.utcnow()
                print(
                    f"⚠️ Подписка #{subscription.id} деактивирована (лимит исчерпан: {subscription.used_total}/{subscription.total_limit}, пользователь {subscription.user_id})"
                )
                deactivated_count += 1

            # Сбрасываем used_today в любом случае
            subscription.used_today = 0

        await session.commit()

        if deactivated_count > 0:
            print(f"✅ Обработка месячных подписок завершена: деактивировано {deactivated_count}")
        else:
            print("✅ Нет месячных подписок с исчерпанным лимитом")


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
                # Вычисляем неиспользованные кредиты (остаток лимита)
                unused_credits = subscription.total_limit - subscription.used_total

                # Если есть неиспользованные кредиты, отнимаем их от пользователя
                if unused_credits > 0:
                    result = await session.execute(
                        select(User).where(User.id == subscription.user_id)
                    )
                    user = result.scalar_one_or_none()
                    if user:
                        # Отнимаем неиспользованные кредиты, но не допускаем отрицательных значений
                        user.credits = max(0, user.credits - unused_credits)
                        print(
                            f"💳 Отнято {unused_credits} неиспользованных кредитов у пользователя {subscription.user_id} (осталось {user.credits})"
                        )

                # Деактивируем подписку
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
