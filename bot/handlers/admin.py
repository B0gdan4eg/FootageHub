from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.session import get_session
from db.user_crud import get_all_users, count_active_subs
from db.downloaded_file_crud import count_total_downloads
from bot.config import ADMIN  # список Telegram ID админов

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
        [InlineKeyboardButton(text="📁 Файлы", callback_data="admin_files")],
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
    # (для краткости — просто пример)
    await callback.message.edit_text("👥 Здесь будет список пользователей")


@router.callback_query(F.data == "admin_files")
async def list_files(callback: types.CallbackQuery):
    # (добавим позже при необходимости)
    await callback.message.edit_text("📁 Здесь будет список загруженных файлов")
