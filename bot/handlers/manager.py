from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db.session import get_session
from db.models import User, UserRole, Payment  # Ваша модель пользователя
from bot.state import ManagerFlow
from bot.handlers.admin import is_admin

router = Router()

async def is_manager(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь роль MANAGER.
    """
    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return False
        return user.role == UserRole.MANAGER


@router.message(Command("manager"))
async def manager_command(message: types.Message, state: FSMContext):
    access = not await is_manager(message.from_user.id) or not await is_admin(message.from_user.id)
    if access:
        await message.answer("🚫 У вас нет прав для этой команды.")
        return
        
    manager_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Создать реферальную ссылку", callback_data="manager_create_referral")],
    [InlineKeyboardButton(text="👥 Просмотреть всех рефералов", callback_data="manager_view_referrals")]
])
    # Если роль менеджера подтверждена
    await message.answer(
        "✅ Привет, менеджер! Что будем делать?",
        reply_markup=manager_kb
    )
    

@router.callback_query(lambda c: c.data == "manager_create_referral")
async def start_referral(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ManagerFlow.waiting_for_ref_code)
    await callback.message.answer("Введите аргумент для реферальной ссылки (например: promo123):")
    await callback.answer()

# Шаг 2: Получаем аргумент
@router.message(ManagerFlow.waiting_for_ref_code)
async def receive_ref_code(message: types.Message, state: FSMContext):
    ref_code = message.text.strip()
    if not ref_code:
        return await message.answer("❌ Аргумент не может быть пустым. Попробуйте снова.")
    await state.update_data(ref_code=ref_code)
    await state.set_state(ManagerFlow.waiting_for_description)
    await message.answer("Введите описание/комментарий для этой ссылки:")

# Шаг 3: Получаем описание и сохраняем
@router.message(ManagerFlow.waiting_for_description)
async def save_referral(message: types.Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()
    ref_code = data["ref_code"]

    user_id = message.from_user.id  # менеджер, создающий ссылку

    async for session in get_session():
        # Сохраняем код у менеджера (если один код на менеджера)
        await session.execute(
            update(User)
            .where(User.tg_id == user_id)
            .values(referral_code=ref_code)
        )
        await session.commit()

    referral_link = f"https://t.me/YourBot?start={ref_code}"
    await message.answer(f"✅ Реферальная ссылка создана!\n\nСсылка: {referral_link}\nОписание: {description}")
    await state.clear()


@router.callback_query(lambda c: c.data == "manager_view_referrals")
async def view_referrals(callback: types.CallbackQuery):
    manager_id = callback.from_user.id

    async for session in get_session():
        # Получаем всех рефералов
        result = await session.execute(select(User).where(User.referred_by_id == manager_id))
        referrals = result.scalars().all()

        if not referrals:
            await callback.message.answer("У вас ещё нет рефералов.")
            return

        total_referrals = len(referrals)
        total_purchases = 0
        total_earnings = 0.0

        # Собираем список с данными для сортировки
        referral_stats = []

        for ref in referrals:
            # Считаем успешные платежи
            payments_result = await session.execute(
                select(func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.user_id == ref.id, Payment.status == "success")
            )
            count, amount = payments_result.one()
            earnings = float(amount) * 0.2  # 20% доход менеджера
            total_purchases += count
            total_earnings += earnings

            referral_stats.append({
                "ref": ref,
                "count": count,
                "earnings": earnings
            })

        # Сортируем по заработку (убывание)
        referral_stats.sort(key=lambda x: x["earnings"], reverse=True)

        # Формируем текст
        details = ""
        for stat in referral_stats:
            ref = stat["ref"]
            username = f"@{ref.username}" if ref.username else "нет username"
            details += f"ID: {ref.tg_id}, {username}, Покупок: {stat['count']}, Заработок: {stat['earnings']:.2f}\n"

        summary = (
            f"📊 Статистика ваших рефералов:\n\n"
            f"Всего рефералов: {total_referrals}\n"
            f"Всего покупок: {total_purchases}\n"
            f"Ваш заработок (20%): {total_earnings:.2f}\n\n"
            f"Детали (сортировка по заработку):\n{details}"
        )

        await callback.message.answer(summary)