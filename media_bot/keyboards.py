from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Main menu keyboard
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


# Admin menu inline keyboard with obfuscated callbacks
def get_admin_menu_kb() -> InlineKeyboardMarkup:
    """Get admin menu inline keyboard with obfuscated callback data"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Редактировать пользователя", callback_data="adm_1e9u2s"
                ),
            ],
            [
                InlineKeyboardButton(text="🎉 Управление бонусами", callback_data="adm_8c7j2n"),
                InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_6f1m4r"),
            ],
            [
                InlineKeyboardButton(text="🔄 Восстановить базу", callback_data="adm_7k5w9v"),
            ],
        ]
    )


# User edit menu inline keyboard with obfuscated callbacks
def get_user_edit_menu_kb() -> InlineKeyboardMarkup:
    """Get user edit menu inline keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="usr_5h2n8q"),
                InlineKeyboardButton(text="🗑️ Удалить подписку", callback_data="usr_4n6y1z"),
            ],
            [
                InlineKeyboardButton(text="💎 Управление кредитами", callback_data="usr_1b4f6k"),
                InlineKeyboardButton(text="👤 Назначить роль", callback_data="usr_3d9l5p"),
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data="usr_back"),
            ],
        ]
    )


# Cancel keyboard
def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Get cancel keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
