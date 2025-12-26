"""
Common validation and utility functions for downloads.
"""

from aiogram import types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums.parse_mode import ParseMode
from db.user_crud import get_user_by_telegram_id
from bot.handlers.channel_check import is_subscribed, CHANNEL_ID
from bot.handlers.messages import (
    USER_NOT_REGISTERED,
    CHANEL_CHECK,
    CANCLE_DOWNLOAD_PAYMENT_OFF
)
import asyncio


async def auto_delete_download_link(message: types.Message, delay: int = 30, keep_second_button: bool = False):
    """
    Удаляет кнопку со ссылкой на скачивание через заданное время.

    Args:
        message: Сообщение с кнопкой скачивания
        delay: Задержка в секундах (по умолчанию 30)
        keep_second_button: Оставить вторую кнопку (например "Скачать ещё")
    """
    await asyncio.sleep(delay)
    try:
        if keep_second_button:
            # Получаем текущую клавиатуру
            current_keyboard = message.reply_markup
            if current_keyboard and len(current_keyboard.inline_keyboard) > 1:
                # Оставляем только вторую строку с кнопкой "Скачать ещё"
                new_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[current_keyboard.inline_keyboard[1]]
                )
                await message.edit_reply_markup(reply_markup=new_keyboard)
            else:
                await message.edit_reply_markup(reply_markup=None)
        else:
            await message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def check_user_eligibility(message: types.Message, bot: Bot, session) -> tuple[bool, any]:
    """
    Проверяет, может ли пользователь скачивать файлы.

    Returns:
        tuple: (is_eligible: bool, user: User | None)
    """
    telegram_id = message.from_user.id
    user = await get_user_by_telegram_id(session, telegram_id)

    if not user:
        await message.answer(
            USER_NOT_REGISTERED,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return False, None

    if user.credits <= 0:
        if not await is_subscribed(bot, telegram_id):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Подписаться ✅", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                    [InlineKeyboardButton(text="Проверить подписку 🔍", callback_data="check_subscription")]
                ]
            )
            await message.answer(
                CHANEL_CHECK,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            return False, None

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
            ]
        )
        await message.answer(
            CANCLE_DOWNLOAD_PAYMENT_OFF,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard
        )
        return False, None

    return True, user
