from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Скачать Envato"),
            KeyboardButton(text="Скачать Freepik"),
        ],
        [
            KeyboardButton(text="Скачать Motion Array"),
        ],
        [
            KeyboardButton(text="Информация"),
            KeyboardButton(text="Оформить подписку 💳"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)
