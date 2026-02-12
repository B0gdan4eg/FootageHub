from aiogram import F, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from media_bot.handlers.messages import msg
from media_bot.keyboards import main_menu_kb

router = Router()


@router.message(Command("menu"))
@router.message(F.text.lower().in_(["меню", "menu", "📋 меню"]))
async def main_menu(message: types.Message, state: FSMContext, lang: str = "ru"):
    """
    Главное меню с командами бота
    """
    await state.clear()
    await message.answer(
        msg("MAIN_MENU", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb,
    )


@router.callback_query(F.data == "go_back_menu")
async def main_menu_callback(callback: types.CallbackQuery, state: FSMContext, lang: str = "ru"):
    """
    Главное меню через callback
    """
    await callback.message.answer(
        msg("MAIN_MENU", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb,
    )
    await callback.answer()
    await state.clear()
