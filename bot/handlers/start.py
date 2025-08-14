from aiogram import Router, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode

from db.session import get_session
from db.user_crud import get_user_by_telegram_id, create_user, set_user_referrer
from bot.keyboards import main_menu_kb
from bot.handlers.messages import WELCOME

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject):
    telegram_id = message.from_user.id
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