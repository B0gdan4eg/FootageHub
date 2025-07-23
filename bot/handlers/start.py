from aiogram import Router, types
from aiogram.filters import Command
from db.session import get_session
from db.user_crud import get_user_by_telegram_id, create_user
from aiogram.fsm.context import FSMContext
from bot.keyboards import main_menu_kb  # импорт клавиатуры

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id

    # Получаем сессию из асинхронного генератора
    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            user = await create_user(session, telegram_id)

    await message.answer(
        f"Привет, {message.from_user.first_name}! Ты успешно зарегистрирован в боте. Выбери действие ниже.",
        reply_markup=main_menu_kb  # прикрепляем клавиатуру
    )
