"""
Credits management functionality for admin panel.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from media_bot.handlers.admin.core import is_admin
from media_bot.keyboards import admin_menu_kb, get_cancel_kb
from media_bot.state import AdminStates
from shared.db.models import User
from shared.db.session import get_session

router = Router()


@router.message(F.text == "💎 Управление кредитами")
async def admin_credits_menu(message: types.Message, state: FSMContext):
    """Credits management menu"""
    if not await is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_for_user_id_credits)
    await message.answer(
        "💎 <b>Управление кредитами</b>\n\n" "Отправьте Telegram ID пользователя:",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_user_id_credits)
async def admin_user_id_received(message: types.Message, state: FSMContext):
    """Process user ID for credits management"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Отменено", reply_markup=admin_menu_kb)
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Попробуйте снова.")
        return

    # Check if user exists
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                f"❌ Пользователь с ID {user_id} не найден", reply_markup=admin_menu_kb
            )
            await state.clear()
            return

        user_info = (
            f"👤 <b>Пользователь {user_id}</b>\n"
            f"Username: @{user.username or 'Нет'}\n\n"
            f"💰 Обычных кредитов: <b>{user.credits:,}</b>\n\n"
            "Введите количество кредитов для добавления (или отрицательное число для вычитания):"
        )

        await state.update_data(user_id=user_id)
        await state.set_state(AdminStates.waiting_for_credits_amount)
        await message.answer(user_info, parse_mode="HTML")


@router.message(AdminStates.waiting_for_credits_amount)
async def admin_credits_amount_received(message: types.Message, state: FSMContext):
    """Process credits amount"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Отменено", reply_markup=admin_menu_kb)
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число.")
        return

    data = await state.get_data()
    user_id = data.get("user_id")

    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(f"❌ Пользователь {user_id} не найден", reply_markup=admin_menu_kb)
            await state.clear()
            return

        # Update credits
        old_balance = user.credits
        user.credits = max(0, user.credits + amount)
        new_balance = user.credits

        await session.commit()

        if amount > 0:
            result_text = f"✅ Добавлено {amount} кредитов пользователю {user_id}"
        else:
            result_text = f"✅ Снято {abs(amount)} кредитов у пользователя {user_id}"

        result_text += f"\n\n💰 Было: <b>{old_balance:,}</b>\n💰 Стало: <b>{new_balance:,}</b>"

    await message.answer(result_text, reply_markup=admin_menu_kb, parse_mode="HTML")
    await state.clear()


@router.message(F.text == "👥 Пользователи")
async def admin_users(message: types.Message):
    """Show recent users"""
    if not await is_admin(message.from_user.id):
        return

    async for session in get_session():
        result = await session.execute(select(User).order_by(User.created_at.desc()).limit(10))
        users = result.scalars().all()

    if not users:
        await message.answer("Нет пользователей")
        return

    users_text = "👥 <b>Последние пользователи</b>\n\n"

    for user in users:
        username = user.username or "Без username"
        users_text += (
            f"ID: <code>{user.tg_id}</code>\n"
            f"Username: @{username}\n"
            f"💰 Кредитов: {user.credits}\n"
            f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
        )

    await message.answer(users_text, parse_mode="HTML")
