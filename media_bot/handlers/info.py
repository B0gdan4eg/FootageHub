from datetime import datetime, timedelta

from aiogram import Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select

from media_bot.handlers.messages import msg
from shared.db.models import Download
from shared.db.repositories import DownloadRepository, SubscriptionRepository, UserRepository
from shared.db.session import get_session

router = Router()


@router.message(Command("info"))
@router.callback_query(lambda c: c.data == "user_info")
@router.message(lambda message: message.text == "Информация")
async def info(message: types.Message, state: FSMContext, lang: str = "ru"):
    await state.clear()
    telegram_id = message.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)
        if not user:
            await message.answer(msg("USER_NOT_FOUND_SHORT", lang))
            return

        download_repo = DownloadRepository(session)
        downloads_count = await download_repo.count_by_user(user.id)

        # Получаем статистику за 24 часа
        time_limit = datetime.utcnow() - timedelta(hours=24)

        # Загрузки за сутки
        result = await session.execute(
            select(func.count(Download.id)).where(Download.downloaded_at >= time_limit)
        )
        downloads_24h = result.scalar()

        # Общее количество пользователей
        len(await user_repo.get_all_users())

        # Получаем активную подписку
        subscription_repo = SubscriptionRepository(session)
        subscription = await subscription_repo.get_active_by_user_id(user.id)

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

        credits_display = str(user.credits) if user.credits > 0 else "0 ❗️"
        info_text = msg("INFO_MESSAGE", lang).format(
            credits=credits_display,
            sub_status=sub_status,
            sub_until=sub_until,
            sub_limits=sub_limits,
            downloads_count=downloads_count,
            downloads_24h=downloads_24h,
        )

        # Создаём кнопку увеличения лимитов
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
            ]
        )

        await message.answer(
            info_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
