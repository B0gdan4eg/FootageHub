from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Скачать Envato"),
            KeyboardButton(text="Скачать Freepik"),
        ],
        [
            KeyboardButton(text="Информация"),
            # KeyboardButton(text="Оплата 💳"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)
