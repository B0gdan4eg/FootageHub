from datetime import datetime

from aiogram import Bot, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select

from media_bot.handlers.admin import is_admin
from media_bot.services import BotServices
from shared.db.models import Payment, ServiceType, User, UserRole
from shared.db.repositories import (
    BonusRepository,
    DownloadRepository,
    SubscriptionRepository,
    UserRepository,
)
from shared.db.repositories.referral_repository import ReferralRewardRepository
from shared.db.session import get_session

router = Router()


async def is_manager(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь роль MANAGER.
    """
    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return False
        return user.role == UserRole.MANAGER


@router.message(Command("manager"))
async def manager_command(message: types.Message, state: FSMContext):
    await state.clear()
    is_mgr = await is_manager(message.from_user.id)
    is_adm = await is_admin(message.from_user.id)
    access = is_mgr or is_adm

    if not access:
        await message.answer("🚫 У вас нет прав для этой команды.")
        return

    # Создаем inline keyboard с закодированными коллбэками
    manager_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="mgr_7k2p9x")],
            [InlineKeyboardButton(text="📁 Выгрузка базы", callback_data="mgr_4h8n3q")],
            [InlineKeyboardButton(text="🔄 Рестарт Envato", callback_data="mgr_2b7f4k")],
            [InlineKeyboardButton(text="🔄 Рестарт Freepik", callback_data="mgr_8c5j1n")],
            [InlineKeyboardButton(text="🔄 Рестарт Motion Array", callback_data="mgr_6d9l3p")],
        ]
    )

    manager_text = (
        "👨‍💼 <b>Панель менеджера</b>\n\n"
        "Добро пожаловать в панель управления менеджера!\n"
        "Выберите нужное действие:"
    )

    await message.answer(manager_text, reply_markup=manager_kb, parse_mode="HTML")


# Обработчики закодированных коллбэков
async def get_stats_text():
    """Получить текст статистики"""
    async for session in get_session():
        # Initialize repositories
        download_repo = DownloadRepository(session)
        user_repo = UserRepository(session)
        subscription_repo = SubscriptionRepository(session)
        bonus_repo = BonusRepository(session)
        referral_repo = ReferralRewardRepository(session)

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

        # Статистика по реферальной системе и подписке на канал
        users_from_referral = await referral_repo.count_total_referred_users()
        users_subscribed_channel = await bonus_repo.count_users_with_bonus("CHANNEL_SUBSCRIPTION")

        # Пользователи по реферальной ссылке за сегодня
        users_from_referral_today = await referral_repo.count_referred_users_since(today_start)

        # Пользователи подписавшиеся на канал за сегодня
        users_subscribed_channel_today = await bonus_repo.count_users_with_bonus_since(
            "CHANNEL_SUBSCRIPTION", today_start
        )

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

    # Текущее время для отображения последнего обновления
    current_time = datetime.utcnow().strftime("%H:%M:%S UTC")

    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"   • Всего: {total_users}\n"
        f"   • Новых сегодня: {new_users_today}\n"
        f"   • Активных подписок: {active_subs}\n"
        f"   • По реферальной ссылке: {users_from_referral} (+{users_from_referral_today})\n"
        f"   • Подписались на канал: {users_subscribed_channel} (+{users_subscribed_channel_today})\n\n"
        f"📥 <b>Загрузки:</b>\n"
        f"   • Всего: {total_downloads}\n"
        f"   • Сегодня: {downloads_today}\n"
        f"   • Envato сегодня: {envato_downloads_today}\n"
        f"   • Freepik сегодня: {freepik_downloads_today}\n"
        f"   • Motion сегодня: {motion_downloads_today}\n\n"
        f"💰 <b>Платежи (успешные):</b>\n"
        f"   • Всего:\n{total_payments_text}\n"
        f"   • Сегодня:\n{today_payments_text}\n\n"
        f"📋 <b>Счета:</b>\n"
        f"   • Создано сегодня: {payments_created_today}\n\n"
        f"🕐 Обновлено: {current_time}"
    )

    return text


def get_stats_keyboard():
    """Получить клавиатуру для статистики с кнопкой обновления"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="mgr_refresh_stats")],
        ]
    )


@router.callback_query(lambda c: c.data == "mgr_7k2p9x")
async def show_stats(callback: types.CallbackQuery):
    """Показывает статистику по всем пользователям"""
    if not await is_manager(callback.from_user.id) and not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    await callback.answer()

    text = await get_stats_text()
    await callback.message.answer(text, reply_markup=get_stats_keyboard(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "mgr_refresh_stats")
async def refresh_stats(callback: types.CallbackQuery):
    """Обновить статистику"""
    if not await is_manager(callback.from_user.id) and not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    await callback.answer("🔄 Обновление...")

    text = await get_stats_text()
    try:
        await callback.message.edit_text(text, reply_markup=get_stats_keyboard(), parse_mode="HTML")
    except Exception as e:
        # Игнорируем ошибку, если сообщение не изменилось
        if "message is not modified" not in str(e):
            raise


@router.callback_query(lambda c: c.data == "mgr_4h8n3q")
async def export_db_callback(callback: types.CallbackQuery, bot: Bot):
    """Экспорт базы данных в XLSX"""
    if not await is_manager(callback.from_user.id) and not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer("📁 Начинаю выгрузку базы данных...")

    try:
        from media_bot.handlers.admin.database import export_full_db_and_send

        async for session in get_session():
            await export_full_db_and_send(session, bot, callback.message.chat.id)

        await callback.message.answer("✅ База данных успешно выгружена!")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при экспорте базы данных:\n{e}")
        print(f"[MANAGER] Ошибка экспорта БД: {e}")


@router.callback_query(lambda c: c.data == "mgr_2b7f4k")
async def restart_envato_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Envato через LinkProcessor"""
    if not await is_manager(callback.from_user.id) and not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.envato_downloader:
            await callback.answer("⚠️ Браузер Envato не запущен", show_alert=True)
            return

        await callback.answer()
        if link_processor.envato_http_enabled:
            await callback.message.answer(
                "Обновляю сессию Envato. После проверки браузер закроется."
            )
            ok = await link_processor.envato_downloader.refresh_session()
            await callback.message.answer(
                "Сессия Envato обновлена, браузер закрыт."
                if ok
                else "Обновление не удалось. Предыдущие cookies сохранены."
            )
            return
        await callback.message.answer("🔄 Начинаю рестарт браузера Envato...")

        # Безопасный рестарт: не прерывает активные скачивания.
        current_requests = link_processor.envato_request_count
        ok, status = await link_processor.restart_envato_now()
        if not ok and status == "busy":
            await callback.message.answer(
                "⏳ Есть активные скачивания Envato — рестарт отложен. " "Повторите через минуту."
            )
            return
        if not ok:
            await callback.message.answer(f"❌ Рестарт не выполнен: {status}")
            return

        await callback.message.answer(
            f"✅ <b>Браузер Envato перезапущен!</b>\n\n"
            f"📊 Обработано запросов до рестарта: <b>{current_requests}</b>\n"
            f"🔄 Счетчик сброшен: <b>0/{link_processor.restart_after}</b>",
            parse_mode="HTML",
        )

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Envato:\n{e}")
        print(f"[MANAGER] Ошибка рестарта браузера Envato: {e}")


@router.callback_query(lambda c: c.data == "mgr_8c5j1n")
async def restart_freepik_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Freepik через LinkProcessor"""
    if not await is_manager(callback.from_user.id) and not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.freepik_downloader:
            await callback.answer("⚠️ Браузер Freepik не запущен", show_alert=True)
            return

        await callback.answer()
        if link_processor.freepik_http_enabled:
            await callback.message.answer(
                "Обновляю сессию Freepik. После проверки браузер закроется."
            )
            ok = await link_processor.freepik_downloader.refresh_session()
            await callback.message.answer(
                "Сессия Freepik обновлена, браузер закрыт."
                if ok
                else "Обновление не удалось. Предыдущие cookies сохранены."
            )
            return
        await callback.message.answer("🔄 Начинаю рестарт браузера Freepik...")

        # Принудительно запускаем рестарт браузера
        async with link_processor._freepik_restart_lock:
            # Текущее количество запросов
            current_requests = link_processor.freepik_request_count

            # Закрываем старый браузер
            if link_processor.freepik_downloader:
                await link_processor.freepik_downloader.__aexit__(None, None, None)

            # Создаем новый браузер
            from media_bot.utils.freepik_utils.freepik import FreepikDownloader

            link_processor.freepik_downloader = await FreepikDownloader().__aenter__()
            link_processor.freepik_request_count = 0

        await callback.message.answer(
            f"✅ <b>Браузер Freepik перезапущен!</b>\n\n"
            f"📊 Обработано запросов до рестарта: <b>{current_requests}</b>\n"
            f"🔄 Счетчик сброшен: <b>0/{link_processor.restart_after}</b>",
            parse_mode="HTML",
        )

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Freepik:\n{e}")
        print(f"[MANAGER] Ошибка рестарта браузера Freepik: {e}")


@router.callback_query(lambda c: c.data == "mgr_6d9l3p")
async def restart_motion_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Motion Array через LinkProcessor"""
    if not await is_manager(callback.from_user.id) and not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.motion_downloader:
            await callback.answer("⚠️ Браузер Motion Array не запущен", show_alert=True)
            return

        await callback.answer()
        await callback.message.answer("🔄 Начинаю рестарт браузера Motion Array...")

        # Принудительно запускаем рестарт браузера
        async with link_processor._motion_restart_lock:
            # Текущее количество запросов
            current_requests = link_processor.motion_request_count

            # Закрываем старый браузер
            if link_processor.motion_downloader:
                await link_processor.motion_downloader.__aexit__(None, None, None)

            # Создаем новый браузер
            from media_bot.utils.motion_utils.motion import MotionDownloader

            link_processor.motion_downloader = await MotionDownloader().__aenter__()
            link_processor.motion_request_count = 0

        await callback.message.answer(
            f"✅ <b>Браузер Motion Array перезапущен!</b>\n\n"
            f"📊 Обработано запросов до рестарта: <b>{current_requests}</b>\n"
            f"🔄 Счетчик сброшен: <b>0/{link_processor.restart_after}</b>",
            parse_mode="HTML",
        )

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Motion Array:\n{e}")
        print(f"[MANAGER] Ошибка рестарта браузера Motion Array: {e}")
