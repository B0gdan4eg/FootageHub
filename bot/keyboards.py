from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Скачать Envato"),
            KeyboardButton(text="Скачать Freepik(Скоро...)"),
        ],
        [
            KeyboardButton(text="Информация"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)
