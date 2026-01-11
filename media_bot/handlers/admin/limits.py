"""
Download limit management functionality for admin panel.
"""

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import update

from media_bot.state import AdminStates
from shared.db.models import User
from shared.db.session import get_session

# Create a separate router for limit functions
router = Router()


@router.callback_query(lambda c: c.data == "admin_set_download_limit")
async def ask_download_limit(callback: types.CallbackQuery, state: FSMContext):
    """Запрос нового лимита скачиваний"""
    await state.set_state(AdminStates.waiting_for_limit_value)
    await callback.message.answer(
        "Введите новое количество доступных скачиваний для всех пользователей:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_limit_value)
async def set_download_limit(message: types.Message, state: FSMContext):
    """Установка лимита скачиваний для всех пользователей"""
    if not message.text.isdigit():
        return await message.answer("❌ Введите число.")

    limit = int(message.text)

    async for session in get_session():
        await session.execute(update(User).values(credits=limit))
        await session.commit()

    await message.answer(f"✅ Всем пользователям установлено {limit} скачиваний.")
    await state.clear()
