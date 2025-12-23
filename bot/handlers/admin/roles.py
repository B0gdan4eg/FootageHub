"""
Role assignment functionality for admin panel.
"""

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update

from db.models import User, UserRole
from db.session import get_session
from bot.state import AdminStates

# Create a separate router for role functions
router = Router()


@router.callback_query(lambda c: c.data == "admin_assign_role")
async def assign_manager_start(callback: types.CallbackQuery, state: FSMContext):
    """Запрос ID пользователя для назначения роли"""
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому хотите назначить роль менеджера:")
    await callback.answer()


@router.message(AdminStates.waiting_for_user_id)
async def assign_manager(message: types.Message, state: FSMContext):
    """Назначение роли менеджера пользователю"""
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
