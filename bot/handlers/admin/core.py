"""
Core admin functionality: authentication and main panel.
"""

from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy import select

from db.models import User, UserRole
from db.session import get_session

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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_give_subscription")],
        [InlineKeyboardButton(text="👤 Назначить роль", callback_data="admin_assign_role")],
        [InlineKeyboardButton(text="💳 Загрузить цены", callback_data="admin_upload_prices")],
        [InlineKeyboardButton(text="📁 Выгрузка базы", callback_data="export_db")],
        [InlineKeyboardButton(text="🔄 Восстановить базу", callback_data="admin_restore_db")],
        [InlineKeyboardButton(text="🍪 Загрузить cookies", callback_data="admin_upload_cookies")],
        [InlineKeyboardButton(text="📦 Установить лимит всем", callback_data="admin_set_download_limit")],
        [InlineKeyboardButton(text="🗑️ Удалить все подписки", callback_data="admin_delete_all_subscriptions")],
        [InlineKeyboardButton(text="📢 Оповещение", callback_data="admin_broadcast")],
    ])
    await message.answer("📂 Панель администратора", reply_markup=keyboard)
    await state.clear()


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
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"📋 <b>Информация о чате:</b>\n\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n"
            f"📊 Тип: {chat_type}",
            parse_mode="HTML"
        )
