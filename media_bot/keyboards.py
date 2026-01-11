from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

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


# Admin menu keyboard
admin_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="👥 Пользователи"),
        ],
        [
            KeyboardButton(text="🎁 Выдать подписку"),
            KeyboardButton(text="💎 Управление кредитами"),
        ],
        [
            KeyboardButton(text="🎉 Управление бонусами"),
            KeyboardButton(text="👤 Назначить роль"),
        ],
        [
            KeyboardButton(text="💳 Загрузить цены"),
            KeyboardButton(text="📢 Рассылка"),
        ],
        [
            KeyboardButton(text="📁 Выгрузка базы"),
            KeyboardButton(text="🔄 Восстановить базу"),
        ],
        [
            KeyboardButton(text="🍪 Загрузить cookies"),
            KeyboardButton(text="📦 Установить лимит"),
        ],
        [
            KeyboardButton(text="🗑️ Удалить подписку"),
            KeyboardButton(text="« Назад в главное меню"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# Manager menu keyboard
manager_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="📁 Выгрузка базы"),
        ],
        [
            KeyboardButton(text="➕ Создать реф. ссылку"),
            KeyboardButton(text="👥 Мои рефералы"),
        ],
        [
            KeyboardButton(text="🔄 Рестарт Envato"),
            KeyboardButton(text="🔄 Рестарт Freepik"),
        ],
        [
            KeyboardButton(text="🔄 Рестарт Motion Array"),
        ],
        [
            KeyboardButton(text="« Назад в главное меню"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# Cancel keyboard
def get_cancel_kb() -> ReplyKeyboardMarkup:
    """Get cancel keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
