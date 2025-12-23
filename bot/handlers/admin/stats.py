"""
Statistics functionality for admin panel.
"""

from aiogram import Router, types, F
from sqlalchemy import select, func
from datetime import datetime

from db.models import User, Download, Payment, ServiceType
from db.session import get_session
from db.user_crud import get_all_users, count_active_subs
from db.downloaded_file_crud import count_total_downloads

# Create a separate router for stats functions
router = Router()


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery):
    """Показывает статистику по всем пользователям"""
    async for session in get_session():
        total_users = len(await get_all_users(session))
        active_subs = await count_active_subs(session)
        total_downloads = await count_total_downloads(session)

        # Граница времени (начало сегодняшнего дня в UTC)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Новые пользователи с начала дня
        result = await session.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )
        new_users_today = result.scalar()

        # Загрузки с начала дня
        result = await session.execute(
            select(func.count(Download.id)).where(Download.downloaded_at >= today_start)
        )
        downloads_today = result.scalar()

        # Загрузки с Envato за сегодня
        result = await session.execute(
            select(func.count(Download.id)).where(
                Download.downloaded_at >= today_start,
                Download.service_type == ServiceType.ENVATO
            )
        )
        envato_downloads_today = result.scalar()

        # Загрузки с Freepik за сегодня
        result = await session.execute(
            select(func.count(Download.id)).where(
                Download.downloaded_at >= today_start,
                Download.service_type == ServiceType.FREEPIK
            )
        )
        freepik_downloads_today = result.scalar()

        # Общая сумма всех успешных платежей по валютам
        result = await session.execute(
            select(
                Payment.currency,
                func.coalesce(func.sum(Payment.amount), 0)
            ).where(Payment.status == "success").group_by(Payment.currency)
        )
        total_payments_by_currency = result.all()

        # Сумма платежей за сегодня по валютам
        result = await session.execute(
            select(
                Payment.currency,
                func.coalesce(func.sum(Payment.amount), 0)
            ).where(
                Payment.status == "success",
                Payment.created_at >= today_start
            ).group_by(Payment.currency)
        )
        payments_today_by_currency = result.all()

    # Форматируем суммы по валютам
    total_payments_text = "\n".join([f"   • {currency}: {amount:.2f}" for currency, amount in total_payments_by_currency]) if total_payments_by_currency else "   • Нет платежей"
    today_payments_text = "\n".join([f"   • {currency}: {amount:.2f}" for currency, amount in payments_today_by_currency]) if payments_today_by_currency else "   • Нет платежей"

    text = (
        f"📊 Статистика:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🆕 Новых сегодня: {new_users_today}\n\n"
        f"🔐 Активных подписок: {active_subs}\n\n"
        f"⬇️ Всего скачиваний: {total_downloads}\n"
        f"📥 Сегодня: {downloads_today}\n"
        f"   • Envato: {envato_downloads_today}\n"
        f"   • Freepik: {freepik_downloads_today}\n\n"
        f"💰 Всего платежей:\n{total_payments_text}\n\n"
        f"💵 Сегодня:\n{today_payments_text}"
    )
    await callback.message.edit_text(text)
