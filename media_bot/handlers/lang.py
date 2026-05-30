"""Выбор языка интерфейса — /lang."""

from aiogram import Bot, F, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from media_bot.handlers.messages import SUPPORTED_LANGUAGES, msg
from media_bot.keyboards import get_main_menu_kb
from shared.db.repositories.user_repository import UserRepository
from shared.db.session import get_session

router = Router()


def _lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=msg("BTN_LANG_RU", "ru"), callback_data="set_lang_ru")],
            [InlineKeyboardButton(text=msg("BTN_LANG_EN", "en"), callback_data="set_lang_en")],
        ]
    )


def _build_commands(lang: str) -> list[BotCommand]:
    return [
        BotCommand(command="menu", description=msg("CMD_MENU", lang)),
        BotCommand(command="envato", description=msg("CMD_ENVATO", lang)),
        BotCommand(command="freepik", description=msg("CMD_FREEPIK", lang)),
        BotCommand(command="motion", description=msg("CMD_MOTION", lang)),
        BotCommand(command="info", description=msg("CMD_INFO", lang)),
        BotCommand(command="pay", description=msg("CMD_PAY", lang)),
        BotCommand(command="referral", description=msg("CMD_REFERRAL", lang)),
        BotCommand(command="lang", description=msg("CMD_LANG", lang)),
    ]


@router.message(Command("lang"))
async def cmd_lang(message: types.Message, lang: str = "ru"):
    await message.answer(
        msg("LANG_CHOOSE", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_lang_keyboard(),
    )


@router.callback_query(F.data.startswith("set_lang_"))
async def set_lang_callback(callback: types.CallbackQuery, bot: Bot):
    new_lang = callback.data.replace("set_lang_", "")
    if new_lang not in SUPPORTED_LANGUAGES:
        new_lang = "ru"

    telegram_id = callback.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user:
            user.username = new_lang
            await session.commit()

    # Обновляем описания команд для этого пользователя
    await bot.set_my_commands(
        _build_commands(new_lang),
        scope=BotCommandScopeChat(chat_id=telegram_id),
    )

    await callback.message.edit_text(
        msg("LANG_SET", new_lang),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()

    # Отправляем обновлённое главное меню
    await callback.message.answer(
        msg("MAIN_MENU", new_lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_kb(new_lang),
    )
