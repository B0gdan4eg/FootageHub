from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db.session import get_session
from db.user_crud import get_user_by_telegram_id, get_all_users
from db.downloaded_file_crud import count_downloads_by_user
from db.subscription_crud import get_active_subscription
from db.models import User, Download
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from sqlalchemy import select, func
from datetime import datetime, timedelta

router = Router()

@router.message(Command("info"))
@router.callback_query(lambda c: c.data == "user_info")
@router.message(lambda message: message.text == "Информация")
async def info(message: types.Message):
    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("Пользователь не найден.")
            return

        downloads_count = await count_downloads_by_user(session, user.id)

        # Получаем статистику за 24 часа
        time_limit = datetime.utcnow() - timedelta(hours=24)

        # Загрузки за сутки
        result = await session.execute(
            select(func.count(Download.id)).where(Download.downloaded_at >= time_limit)
        )
        downloads_24h = result.scalar()

        # Общее количество пользователей
        total_users = len(await get_all_users(session))

        # Получаем активную подписку
        subscription = await get_active_subscription(session, user.id)

        # Формируем информацию о подписке
        if subscription:
            sub_status = "✅ Активна"
            sub_until = subscription.end_date.strftime("%d.%m.%Y")

            # Определяем тип отображения лимитов
            if subscription.total_limit:
                # MONTHLY_150: показываем общий лимит
                sub_limits = f"{subscription.used_total}/{subscription.total_limit}"
            elif subscription.daily_limit:
                # DAILY_30: показываем только дневной лимит
                sub_limits = f"{subscription.used_today}/{subscription.daily_limit} (сегодня)"
            else:
                # UNLIMITED: безлимит
                sub_limits = "♾️ Безлимит"
        else:
            sub_status = "❌ Неактивна"
            sub_until = "—"
            sub_limits = "—"

        INFO_MASSEGE = (
            f"👤 <b>Информация о вашем аккаунте</b>\n\n"
            f"🎁 <b>Бесплатные загрузки:</b> {'❗️0' if user.credits == 0 else user.credits}\n"
            f"💼 <b>Подписка:</b> {sub_status}\n"
            f"📅 <b>Действует до:</b> {sub_until}\n"
            f"📊 <b>Лимиты подписки:</b> {sub_limits}\n"
            f"📥 <b>Ваших скачиваний:</b> {downloads_count}\n\n"
            f"{'─' * 30}\n\n"
            f"📈 <b>Статистика сервиса за 24 часа</b>\n"
            f"🔥 Скачано файлов: <b>{downloads_24h}</b>\n"
            f"👥 Активных пользователей: <b>{total_users:,}</b>"
        )

        # Создаём кнопку увеличения лимитов
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Увеличить лимиты", callback_data="buy_subscription")]
        ])

        await message.answer(
            INFO_MASSEGE.format(name=message.from_user.first_name),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
