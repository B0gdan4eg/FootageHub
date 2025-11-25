from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.downloaded_file_crud import count_downloads_by_user
from db.subscription_crud import get_active_subscription
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command

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

        # Получаем активную подписку
        subscription = await get_active_subscription(session, user.id)

        # Формируем информацию о подписке
        if subscription:
            sub_status = "✅ Активна"
            sub_until = subscription.end_date.strftime("%d.%m.%Y")
            sub_limits = f"{subscription.used_total}/{subscription.total_limit or '∞'}"
            if subscription.daily_limit:
                sub_limits += f" (сегодня: {subscription.used_today}/{subscription.daily_limit})"
        else:
            sub_status = "❌ Неактивна"
            sub_until = "—"
            sub_limits = "—"

        INFO_MASSEGE = (
            f"<b>👤 Информация о вашем аккаунте:</b>\n\n"
            f"🎁 <b>Бесплатные кредиты:</b> {'❗️0' if user.credits == 0 else user.credits}\n"
            f"💼 <b>Подписка:</b> {sub_status}\n"
            f"📅 <b>Действует до:</b> {sub_until}\n"
            f"📊 <b>Лимиты подписки:</b> {sub_limits}\n"
            f"📥 <b>Скачиваний всего:</b> {downloads_count}"
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
