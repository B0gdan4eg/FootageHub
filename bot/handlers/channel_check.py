# channel_check.py
from aiogram import Bot, Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramForbiddenError
from aiogram.enums import ChatMemberStatus
from aiogram import Bot, Router, types
from bot.handlers.messages import CHANEL_CANCLE, CHANEL_APPLY
from aiogram.enums.parse_mode import ParseMode

# ID или @username канала
CHANNEL_ID = "@footageChanel"  # например, "@mycoolchannel"

router = Router()

async def is_subscribed(bot: Bot, tg_user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=tg_user_id
        )
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR
        )
    except TelegramForbiddenError:
        return False
    except Exception as e:
        print(f"Ошибка при проверке подписки: {e}")
        return False


@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    subscribed = await is_subscribed(bot, user_id)

    if not subscribed:
        # Пользователь не подписан — клавиатура для подписки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Подписаться ✅", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                [InlineKeyboardButton(text="Проверить подписку 🔍", callback_data="check_subscription")]
            ]
        )
        await callback.message.edit_text(
            CHANEL_CANCLE,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            CHANEL_APPLY,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    await callback.answer()  # убирает "часики"