"""
Core admin functionality: authentication and main panel.
"""

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from media_bot.keyboards import get_admin_menu_kb, main_menu_kb
from media_bot.state import AdminStates
from shared.db.models import User, UserRole
from shared.db.session import get_session

# Create a separate router for core functions
router = Router()


async def is_admin(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь роль ADMIN.
    """
    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return False
        return user.role == UserRole.ADMIN


@router.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    """Отображает панель администратора"""
    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У тебя нет доступа")

    admin_text = (
        "🔐 <b>Админ-панель Media Bot</b>\n\n"
        "Добро пожаловать в панель управления!\n"
        "Выберите нужное действие:"
    )

    await message.answer(admin_text, reply_markup=get_admin_menu_kb(), parse_mode="HTML")
    await state.clear()


# Callback handlers with obfuscated callback_data


# Main admin panel handlers
@router.callback_query(lambda c: c.data == "adm_1e9u2s")
async def admin_edit_user_callback(callback: types.CallbackQuery, state: FSMContext):
    """👤 Редактировать пользователя - запрос Telegram ID"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    await callback.answer()
    from media_bot.state import AdminStates

    await state.set_state(AdminStates.waiting_for_edit_user_id)
    await callback.message.answer(
        "👤 <b>Редактирование пользователя</b>\n\n" "Введите Telegram ID пользователя:",
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "adm_8c7j2n")
async def admin_bonuses_callback(callback: types.CallbackQuery):
    """🎉 Управление бонусами - redirect to bonuses handler"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    await callback.answer()
    from media_bot.handlers.admin.bonuses import manage_bonuses

    await manage_bonuses(callback.message)


@router.callback_query(lambda c: c.data == "adm_6f1m4r")
async def admin_broadcast_callback(callback: types.CallbackQuery, state: FSMContext):
    """📢 Рассылка - redirect to broadcast handler"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    await callback.answer()
    from media_bot.handlers.admin.broadcast import broadcast_start

    await broadcast_start(callback.message, state)


@router.callback_query(lambda c: c.data == "adm_7k5w9v")
async def admin_restore_db_callback(callback: types.CallbackQuery, state: FSMContext):
    """🔄 Восстановить базу - redirect to database handler"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    from media_bot.handlers.admin.database import restore_db_start

    await restore_db_start(callback, state)


# User edit menu handlers
@router.message(AdminStates.waiting_for_edit_user_id, F.text)
async def handle_edit_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного Telegram ID для редактирования пользователя"""
    if not await is_admin(message.from_user.id):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.")
        return

    # Check if user exists
    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(f"❌ Пользователь с ID {user_id} не найден.")
            await state.clear()
            return

        # Save user_id to state
        await state.update_data(edit_user_id=user_id)
        await state.clear()

        from media_bot.keyboards import get_user_edit_menu_kb

        user_info = (
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"🆔 Telegram ID: <code>{user_id}</code>\n"
            f"👤 Username: @{user.username or 'Нет'}\n"
            f"📛 Имя: {user.first_name or 'Нет'}\n"
            f"🎭 Роль: {user.role.value}\n"
            f"💰 Кредиты: {user.credits:,}\n\n"
            f"Выберите действие:"
        )

        await message.answer(user_info, reply_markup=get_user_edit_menu_kb(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "usr_5h2n8q")
async def user_give_sub_callback(callback: types.CallbackQuery, state: FSMContext):
    """🎁 Выдать подписку пользователю"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    user_id = data.get("edit_user_id")

    if not user_id:
        await callback.answer("❌ Пользователь не выбран", show_alert=True)
        return

    await callback.answer()
    from media_bot.handlers.admin.subscriptions import give_subscription_start
    from media_bot.state import AdminStates

    # Set user_id in state for subscription handler
    await state.update_data(subscription_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_subscription_plan)

    # Show subscription plan selection
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Monthly 50 (30 дней)", callback_data="sub_plan_monthly_50"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Monthly 150 (30 дней)", callback_data="sub_plan_monthly_150"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Monthly 400 (30 дней)", callback_data="sub_plan_monthly_400"
                )
            ],
            [InlineKeyboardButton(text="⚡ Daily 30 (30 дней)", callback_data="sub_plan_daily_30")],
            [
                InlineKeyboardButton(
                    text="♾️ Unlimited (30 дней)", callback_data="sub_plan_unlimited"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="sub_plan_cancel")],
        ]
    )

    await callback.message.answer(
        f"✅ Пользователь: <b>{user_id}</b>\n\n" f"Выберите план подписки:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "usr_4n6y1z")
async def user_delete_sub_callback(callback: types.CallbackQuery, state: FSMContext):
    """🗑️ Удалить подписку пользователя"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    user_id = data.get("edit_user_id")

    if not user_id:
        await callback.answer("❌ Пользователь не выбран", show_alert=True)
        return

    await callback.answer()

    from shared.db.models import Subscription

    async for session in get_session():
        # Find user
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await callback.message.answer(f"❌ Пользователь с ID {user_id} не найден.")
            return

        # Find and delete subscription
        result = await session.execute(select(Subscription).where(Subscription.user_id == user.id))
        subscription = result.scalar_one_or_none()

        if not subscription:
            await callback.message.answer(f"❌ У пользователя {user_id} нет активной подписки.")
            return

        # Delete subscription
        await session.delete(subscription)
        await session.commit()

    await callback.message.answer(
        f"✅ Подписка пользователя {user_id} (@{user.username or 'Нет username'}) успешно удалена",
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "usr_1b4f6k")
async def user_credits_callback(callback: types.CallbackQuery, state: FSMContext):
    """💎 Управление кредитами пользователя"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    user_id = data.get("edit_user_id")

    if not user_id:
        await callback.answer("❌ Пользователь не выбран", show_alert=True)
        return

    await callback.answer()

    async for session in get_session():
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await callback.message.answer(f"❌ Пользователь с ID {user_id} не найден.")
            return

        user_info = (
            f"👤 <b>Пользователь {user_id}</b>\n"
            f"Username: @{user.username or 'Нет'}\n\n"
            f"💰 Обычных кредитов: <b>{user.credits:,}</b>\n\n"
            "Введите количество кредитов для добавления (или отрицательное число для вычитания):"
        )

        from media_bot.state import AdminStates

        await state.update_data(user_id=user_id)
        await state.set_state(AdminStates.waiting_for_credits_amount)
        await callback.message.answer(user_info, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "usr_3d9l5p")
async def user_assign_role_callback(callback: types.CallbackQuery, state: FSMContext):
    """👤 Назначить роль пользователю"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    user_id = data.get("edit_user_id")

    if not user_id:
        await callback.answer("❌ Пользователь не выбран", show_alert=True)
        return

    await callback.answer()

    from media_bot.state import AdminStates

    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.answer(
        f"👤 Пользователь: <code>{user_id}</code>\n\n" "Введите роль (MANAGER или USER):",
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "usr_back")
async def user_back_callback(callback: types.CallbackQuery, state: FSMContext):
    """« Назад - вернуться в главное меню админки"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return

    await callback.answer()
    await state.clear()

    admin_text = (
        "🔐 <b>Админ-панель Media Bot</b>\n\n"
        "Добро пожаловать в панель управления!\n"
        "Выберите нужное действие:"
    )

    await callback.message.edit_text(
        admin_text, reply_markup=get_admin_menu_kb(), parse_mode="HTML"
    )


@router.message(Command("get_chat_id"))
async def get_chat_id_command(message: types.Message):
    """Показывает ID текущего чата (работает в группах и личных сообщениях)"""
    chat_type = message.chat.type
    chat_id = message.chat.id

    if chat_type in ["group", "supergroup"]:
        await message.answer(
            f"📋 <b>Информация о группе:</b>\n\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n"
            f"📛 Название: {message.chat.title}\n"
            f"📊 Тип: {chat_type}\n\n"
            f"Используйте этот Chat ID для ADMIN_CHAT_ID в .env",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"📋 <b>Информация о чате:</b>\n\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n"
            f"📊 Тип: {chat_type}",
            parse_mode="HTML",
        )
