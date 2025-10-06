from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

@router.message(Command("menu"))
@router.message(lambda message: message.text.lower() in ["меню", "menu", "📋 меню"])
async def main_menu(message: types.Message):
    """
    Главное меню с командами бота
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Скачать Envato", callback_data="envato_start")],
        [InlineKeyboardButton(text="🖼 Скачать Freepik (Скоро...)", callback_data="freepik_soon")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="user_info")],
    ])

    await message.answer(
        "📋 <b>Главное меню</b>\n\nВыберите нужный раздел:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )