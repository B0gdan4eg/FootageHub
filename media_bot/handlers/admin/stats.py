"""
Statistics functionality for admin panel.
"""

from datetime import datetime

from aiogram import Router, types
from sqlalchemy import func, select

from media_bot.handlers.admin.core import is_admin
from shared.db.models import Payment, ServiceType, User
from shared.db.repositories import DownloadRepository, SubscriptionRepository, UserRepository
from shared.db.session import get_session

# Create a separate router for stats functions
router = Router()


async def show_stats(message: types.Message):
    """Показывает статистику по всем пользователям"""
    if not await is_admin(message.from_user.id):
        return

    async for session in get_session():
        # Initialize repositories
        download_repo = DownloadRepository(session)
        user_repo = UserRepository(session)
        subscription_repo = SubscriptionRepository(session)

        total_users = len(await user_repo.get_all_users())
        active_subs = await subscription_repo.count_active_subs()
        total_downloads = await download_repo.count_total()

        # Граница времени (начало сегодняшнего дня в UTC)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Новые пользователи с начала дня
        result = await session.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )
        new_users_today = result.scalar()

        # Загрузки с начала дня
        downloads_today = await download_repo.count_today(today_start)

        # Загрузки с Envato за сегодня
        envato_downloads_today = await download_repo.count_by_service_today(
            ServiceType.ENVATO, today_start
        )

        # Загрузки с Freepik за сегодня
        freepik_downloads_today = await download_repo.count_by_service_today(
            ServiceType.FREEPIK, today_start
        )

        # Загрузки с Motion Array за сегодня
        motion_downloads_today = await download_repo.count_by_service_today(
            ServiceType.MOTION_ARRAY, today_start
        )

        # Общая сумма всех успешных платежей по валютам
        result = await session.execute(
            select(Payment.currency, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.status == "success")
            .group_by(Payment.currency)
        )
        total_payments_by_currency = result.all()

        # Сумма платежей за сегодня по валютам
        result = await session.execute(
            select(Payment.currency, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.status == "success", Payment.created_at >= today_start)
            .group_by(Payment.currency)
        )
        payments_today_by_currency = result.all()

        # Количество созданных платежей сегодня (всех статусов)
        result = await session.execute(
            select(func.count(Payment.id)).where(Payment.created_at >= today_start)
        )
        payments_created_today = result.scalar()

    # Форматируем суммы по валютам
    total_payments_text = (
        "\n".join(
            [f"   • {currency}: {amount:.2f}" for currency, amount in total_payments_by_currency]
        )
        if total_payments_by_currency
        else "   • Нет платежей"
    )
    today_payments_text = (
        "\n".join(
            [f"   • {currency}: {amount:.2f}" for currency, amount in payments_today_by_currency]
        )
        if payments_today_by_currency
        else "   • Нет платежей"
    )

    text = (
        f"📊 Статистика:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🆕 Новых сегодня: {new_users_today}\n\n"
        f"🔐 Активных подписок: {active_subs}\n\n"
        f"⬇️ Всего скачиваний: {total_downloads}\n"
        f"📥 Сегодня: {downloads_today}\n"
        f"   • Envato: {envato_downloads_today}\n"
        f"   • Freepik: {freepik_downloads_today}\n"
        f"   • Motion Array: {motion_downloads_today}\n\n"
        f"💰 Всего платежей:\n{total_payments_text}\n\n"
        f"💵 Сегодня:\n{today_payments_text}\n"
        f"📋 Создано платежей сегодня: {payments_created_today}"
    )
    await message.answer(text)
