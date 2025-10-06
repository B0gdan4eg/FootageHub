from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.context import FSMContext
from bot.keyboards import main_menu_kb

router = Router()

@router.message(Command("menu"))
@router.callback_query(F.data == "go_back_menu")
@router.message(lambda message: message.text.lower() in ["меню", "menu", "📋 меню"])
async def main_menu(message: types.Message, state: FSMContext):
    """
    Главное меню с командами бота
    """
    await message.answer(
        """📋 <b>Главное меню</b>\n\nВыберите нужный раздел:""",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb,
    )
    await state.clear()