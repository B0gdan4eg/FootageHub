from aiogram import Router, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode

from db.session import get_session
from db.user_crud import get_user_by_telegram_id, create_user, set_user_referrer
from bot.keyboards import main_menu_kb
from bot.handlers.messages import WELCOME, MAINTENANCE_MESSAGE

router = Router()

# Пользователи, для которых показываем сообщение о технических работах
BLOCKED_USERS = {472785197, 289997391, 6269570979}

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject):
    await state.clear()
    telegram_id = message.from_user.id

    # Проверка на заблокированных пользователей
    if telegram_id in BLOCKED_USERS:
        await message.answer(
            MAINTENANCE_MESSAGE,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return

    args = command.args  # Аргументы после /start (в 3.x так правильно)

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await create_user(session, telegram_id)
            # Если есть реферальный код — пытаемся его записать
            if args:
                await set_user_referrer(session, telegram_id, args)

    await message.answer(
        WELCOME.format(name=message.from_user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb,
        disable_web_page_preview=True
    )