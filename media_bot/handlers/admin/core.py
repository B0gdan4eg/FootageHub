"""
Core admin functionality: authentication and main panel.
"""

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from media_bot.keyboards import admin_menu_kb, main_menu_kb
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

    await message.answer(admin_text, reply_markup=admin_menu_kb, parse_mode="HTML")
    await state.clear()


@router.message(F.text == "« Назад в главное меню")
async def admin_back_to_main(message: types.Message, state: FSMContext):
    """Return to main menu from admin panel"""
    await state.clear()
    await message.answer("Вы вернулись в главное меню", reply_markup=main_menu_kb)


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
