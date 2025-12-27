"""
AI Bot Keyboards

Reply keyboards for AI Bot
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# Main menu keyboard
main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🎨 Изображение"),
            KeyboardButton(text="🎬 Видео"),
        ],
        [
            KeyboardButton(text="🛠 Прочие инструменты"),
        ],
        [
            KeyboardButton(text="ℹ️ Информация"),
            KeyboardButton(text="💰 Купить кредиты"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# Admin menu keyboard
admin_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="🌐 Kie.ai баланс"),
        ],
        [
            KeyboardButton(text="👥 Пользователи"),
            KeyboardButton(text="💎 Управление кредитами"),
        ],
        [
            KeyboardButton(text="📢 Рассылка"),
            KeyboardButton(text="⚙️ Настройки цен"),
        ],
        [
            KeyboardButton(text="📝 Логи"),
            KeyboardButton(text="« Назад в главное меню"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# Tools menu keyboard
tools_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="💎 Баланс кредитов"),
            KeyboardButton(text="💰 Цены"),
        ],
        [
            KeyboardButton(text="ℹ️ Помощь"),
            KeyboardButton(text="⚙️ Настройки"),
        ],
        [
            KeyboardButton(text="« Назад"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


def get_admin_user_actions_kb() -> InlineKeyboardMarkup:
    """Get inline keyboard for user actions in admin panel"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить кредиты", callback_data="admin_add_credits")
    builder.button(text="➖ Отнять кредиты", callback_data="admin_remove_credits")
    builder.button(text="🔒 Заблокировать", callback_data="admin_ban_user")
    builder.button(text="🔓 Разблокировать", callback_data="admin_unban_user")
    builder.button(text="« Назад", callback_data="admin_back")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Get cancel keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
