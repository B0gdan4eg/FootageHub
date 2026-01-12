"""
Role assignment functionality for admin panel.
"""

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update

from media_bot.state import AdminStates
from shared.db.models import User, UserRole
from shared.db.session import get_session

# Create a separate router for role functions
router = Router()


async def assign_manager_start(callback: types.CallbackQuery, state: FSMContext):
    """Запрос ID пользователя для назначения роли"""
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.answer(
        "Введите Telegram ID пользователя, которому хотите назначить роль менеджера:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_user_id)
async def assign_role(message: types.Message, state: FSMContext):
    """Назначение роли пользователю"""
    role_text = message.text.strip().upper()

    if role_text == "Q":
        await state.clear()
        return await message.answer("❌ Отменено.")

    # Check if role is valid
    try:
        new_role = UserRole[role_text]
    except KeyError:
        return await message.answer(
            f"❌ Неверная роль. Доступные роли: {', '.join([r.name for r in UserRole])}"
        )

    # Get user_id from state
    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        await state.clear()
        return await message.answer("❌ Ошибка: ID пользователя не найден.")

    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await state.clear()
            return await message.answer(f"❌ Пользователь с ID {user_id} не найден.")

        # Назначаем роль
        await session.execute(update(User).where(User.tg_id == user_id).values(role=new_role))
        await session.commit()

    await message.answer(f"✅ Пользователю с ID {user_id} назначена роль {new_role.value}.")
    await state.clear()
