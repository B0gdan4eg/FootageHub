from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram import Bot

from db.models import User, Download, Media, Payment, UserRole  # предполагаемая модель
from db.session import get_session
from db.user_crud import get_all_users, count_active_subs
from db.downloaded_file_crud import count_total_downloads
from sqlalchemy import select, update
from bot.state import AdminStates
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession
import openpyxl
import json
from pathlib import Path

router = Router()

# УБРАТЬ!!!
PRICE_LIST = Path(__file__).resolve().parent / "prices_list.json"


# Метод проверки роли админа
# ------------------------------------------------------------
async def is_admin(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь роль ADMIN.
    """
    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return False
        return user.role == UserRole.ADMIN
# ------------------------------------------------------------

# Роутер на коллбэк статистику по всем пользователям
# ------------------------------------------------------------
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
# ------------------------------------------------------------


# Роутер на коллбэк список пользователей
# ------------------------------------------------------------
@router.callback_query(F.data == "admin_users")
async def list_users(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
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
# ------------------------------------------------------------

# Роутер на текст вызов панели админа
# ------------------------------------------------------------
@router.message(lambda message: message.text == "admin")
async def admin_panel(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У тебя нет доступа")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="👤 Назначить роль", callback_data="admin_assign_role")],
        [InlineKeyboardButton(text="💳 Загрузить цены", callback_data="admin_upload_prices")],
        [InlineKeyboardButton(text="🧹 Очистка базы", callback_data="clear_db")],
        [InlineKeyboardButton(text="📁 Выгрузка базы", callback_data="export_db")]
        
    ])
    await message.answer("📂 Панель администратора", reply_markup=keyboard)
    await state.clear()
# ------------------------------------------------------------

# Роутер на коллбэк выдача роли манагера
# ------------------------------------------------------------
@router.callback_query(lambda c: c.data == "admin_assign_role")
async def assign_manager_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому хотите назначить роль менеджера:")
    await callback.answer()
# ------------------------------------------------------------

# Роутер на коллбэк ввод ид для выдачи роли
# ------------------------------------------------------------
@router.message(AdminStates.waiting_for_user_id)
async def assign_manager(message: types.Message, state: FSMContext):
    user_id_text = message.text.strip()
    if user_id_text == "q":
        return await state.clear()
    if not user_id_text.isdigit():
        return await message.answer("❌ ID должен быть числом. Попробуйте снова.")

    user_id = int(user_id_text)

    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return await message.answer(f"❌ Пользователь с ID {user_id} не найден.")

        # Назначаем роль MANAGER
        await session.execute(
            update(User)
            .where(User.tg_id == user_id)
            .values(role=UserRole.MANAGER)
        )
        await session.commit()

    await message.answer(f"✅ Пользователю с ID {user_id} назначена роль MANAGER.")
    await state.clear()
# ------------------------------------------------------------

# Роутер на коллбэк смена цен
# ------------------------------------------------------------
@router.callback_query(lambda c: c.data == "admin_upload_prices")
async def upload_prices(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_price_json)
    await callback.message.answer("Отправьте JSON с ценами (например, кредиты и подписки):")
    await callback.answer()
# ------------------------------------------------------------

# Роутре на коллбэк ожидание json с ценами
# ------------------------------------------------------------
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
# ------------------------------------------------------------    


async def export_full_db_and_send(session: AsyncSession, bot: Bot, chat_id: int):
    """
    Экспортирует все таблицы БД в XLSX и отправляет в Telegram.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Удаляем пустой первый лист

    # Список моделей и названия листов
    tables = [
        (User, "Users"),
        (Media, "Media"),
        (Download, "Downloads"),
        (Payment, "Payments")
    ]

    for model, sheet_name in tables:
        # Создаём лист
        ws = wb.create_sheet(title=sheet_name)

        # Получаем все записи из модели
        result = await session.execute(select(model))
        rows = result.scalars().all()

        if not rows:
            ws.append(["Нет данных"])
            continue

        # Заголовки — это имена всех колонок в модели
        columns = [col.name for col in model.__table__.columns]
        ws.append(columns)

        # Данные
        for row in rows:
            ws.append([
                getattr(row, col) if getattr(row, col) is not None else ""
                for col in columns
            ])

    # Сохраняем в память
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    # Отправляем в чат
    await bot.send_document(
        chat_id=chat_id,
        document=file_stream,
        filename="full_database_export.xlsx",
        caption="📊 Полный экспорт базы данных"
    )

@router.callback_query(lambda c: c.data == "clear_db")
async def clear_db_callback(callback_query: types.CallbackQuery, bot: Bot):
    async for session in get_session():
        # 1️⃣ Сначала выгружаем базу и отправляем пользователю
        await export_full_db_and_send(session, bot, callback_query.message.chat.id)

        # 2️⃣ После успешной отправки очищаем таблицы
        await session.execute("DELETE FROM payments")
        await session.execute("DELETE FROM downloads")
        await session.execute("DELETE FROM media")
        await session.execute("DELETE FROM users")
        await session.commit()

    await callback_query.answer("✅ База выгружена и очищена!")

@router.callback_query(lambda c: c.data == "export_db")
async def export_db_callback(callback_query: types.CallbackQuery, bot: Bot):
    async for session in get_session():
        await export_full_db_and_send(session, bot, callback_query.message.chat.id)
    await callback_query.answer("📁 База выгружена!")
