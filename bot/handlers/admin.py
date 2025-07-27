from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models import User  # предполагаемая модель
from db.session import get_session
from db.user_crud import get_all_users, count_active_subs, get_user_by_telegram_id
from db.downloaded_file_crud import count_total_downloads
from sqlalchemy import select

from bot.config import ADMIN  # список Telegram ID админов
from datetime import datetime, timedelta

router = Router()

def is_admin(user_id):
    return str(user_id) in ADMIN


@router.message(F.text == "/admin")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ У тебя нет доступа")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_grant_sub")],
    ])
    await message.answer("📂 Панель администратора", reply_markup=keyboard)


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery):
    async for session in get_session():
        total_users = len(await get_all_users(session))
        active_subs = await count_active_subs(session)
        total_downloads = await count_total_downloads(session)

    text = (
        f"📊 Статистика:\n"
        f"👥 Пользователей: {total_users}\n"
        f"🔐 Подписок: {active_subs}\n"
        f"⬇️ Скачиваний: {total_downloads}"
    )
    await callback.message.edit_text(text)


@router.callback_query(F.data == "admin_users")
async def list_users(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    async for session in get_session():
        stmt = select(User).order_by(User.id.desc()).limit(10)
        result = await session.execute(stmt)
        users = result.scalars().all()

    if not users:
        await callback.message.edit_text("🙅‍ Пользователи не найдены.")
        return

    text = "👥 Последние пользователи:\n\n"
    keyboard = InlineKeyboardBuilder()

    for user in users:
        sub_until = user.subscription_until.strftime("%d.%m.%Y") if user.subscription_until else "—"
        text += (
            f"🆔 {user.tg_id}\n"
            f"👤 {user.username or 'Без имени'}\n"
            f"💳 Кредиты: {user.credits}\n"
            f"📅 Подписка до: {user.subscription_until}\n\n"
        )

        keyboard.button(
            text=f"➕ Выдать подписку",
            callback_data=f"admin_grant_sub_{user.tg_id}"
        )

    keyboard.adjust(1)  # по 1 кнопке в столбец
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()
    
@router.callback_query(lambda c: c.data.startswith("admin_grant_sub"))
async def admin_grant_subscription(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ У вас нет доступа.", show_alert=True)
        return

    telegram_id_str = callback_query.data.replace("admin_grant_sub_", "")
    try:
        target_id = int(telegram_id_str)
    except ValueError:
        await callback_query.answer("Неверный ID.", show_alert=True)
        return

    async for session in get_session():
        user = await get_user_by_telegram_id(session, target_id)
        if not user:
            await callback_query.message.answer("❌ Пользователь не найден.")
            return

        user.is_subscribed = True
        user.subscription_until = datetime.utcnow() + timedelta(days=30)
        await session.commit()

    await callback_query.message.answer(f"✅ Пользователю {target_id} выдана подписка на 30 дней.")
    await callback_query.answer("Подписка выдана ✅")
