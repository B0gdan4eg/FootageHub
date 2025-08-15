from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram import Bot

from db.models import User  # предполагаемая модель
from db.session import get_session
from db.user_crud import get_all_users, count_active_subs, get_user_by_telegram_id
from db.downloaded_file_crud import count_total_downloads
from sqlalchemy import select
from bot.state import AdminStates

from bot.config import ADMIN  # список Telegram ID админов
from datetime import datetime, timedelta
import os
import json
from pathlib import Path

router = Router()

PRICE_LIST = Path(__file__).resolve().parent / "prices_list.json"

def is_admin(user_id):
    return str(user_id) in ADMIN

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
        
    await callback.message.edit_text(text)
    await callback.answer()

@router.message(lambda message: message.text == "admin")
async def admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ У тебя нет доступа")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="👤 Назначить роль", callback_data="admin_assign_role")],
        [InlineKeyboardButton(text="💳 Загрузить цены", callback_data="admin_upload_prices")]
    ])
    await message.answer("📂 Панель администратора", reply_markup=keyboard)
    await state.clear()

# Назначение роли
@router.callback_query(lambda c: c.data == "admin_assign_role")
async def assign_role_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому хотите назначить роль:")
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id)
async def receive_user_id(message: types.Message, state: FSMContext):
    user_id = message.text.strip()
    if not user_id.isdigit():
        return await message.answer("❌ ID должен быть числом. Попробуйте снова.")
    await state.update_data(user_id=int(user_id))
    await state.set_state(AdminStates.waiting_for_role)
    await message.answer("Введите роль для пользователя (например: premium, vip):")

@router.message(AdminStates.waiting_for_role)
async def receive_role(message: types.Message, state: FSMContext):
    role = message.text.strip()
    data = await state.get_data()
    user_id = data["user_id"]

    # Сохраняем роль в JSON
    roles_file = "user_roles.json"
    roles = {}
    if os.path.exists(roles_file):
        with open(roles_file, "r", encoding="utf-8") as f:
            roles = json.load(f)
    roles[str(user_id)] = role
    with open(roles_file, "w", encoding="utf-8") as f:
        json.dump(roles, f, indent=4, ensure_ascii=False)

    await message.answer(f"✅ Роль '{role}' назначена пользователю с ID {user_id}")
    await state.clear()

# Загрузка JSON цен
@router.callback_query(lambda c: c.data == "admin_upload_prices")
async def upload_prices(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_price_json)
    await callback.message.answer("Отправьте JSON с ценами (например, кредиты и подписки):")
    await callback.answer()

@router.message(AdminStates.waiting_for_price_json, F.content_type == "document")
async def receive_price_json(message: types.Message, state: FSMContext, bot: Bot):
    file = await bot.download(message.document.file_id)
    content = file.read().decode("utf-8")

    try:
        data = json.loads(content)
    except Exception as e:
        return await message.answer(f"❌ Ошибка при чтении JSON: {e}")

    with open(PRICE_LIST, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    await message.answer("✅ Цены успешно обновлены.")
    await state.clear()