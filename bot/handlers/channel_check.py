# channel_check.py
from aiogram import Bot, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramForbiddenError
from aiogram.enums import ChatMemberStatus
from bot.handlers.messages import CHANEL_CANCLE, CHANEL_APPLY
from aiogram.enums.parse_mode import ParseMode
from db.session import get_session
from db.models import User
from sqlalchemy import select
import os
import json
import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession

# ID или @username канала УБРАТЬ!!!
CHANNEL_ID = "@footageChanel"  # например, "@mycoolchannel"

router = Router()

# Метод проверки подписки на канал
# ------------------------------------------------------------
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
# ------------------------------------------------------------


# Роутер по коллбэку на проверку подписки
# ------------------------------------------------------------
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
        async for session in get_session():
            user = await session.scalar(select(User).where(User.tg_id == user_id))
            if user:
                bonus_given = await give_channel_bonus(user_id, CHANNEL_ID)
                if bonus_given:
                    user.credits += 2  # начисляем 2 кредита
                    await session.commit()
                    text = f"{CHANEL_APPLY}\n💰 Вам начислено 2 кредита за подписку!"
                else:
                    text = f"{CHANEL_APPLY}\n❌ Бонус за подписку вы уже получали ранее."

                await callback.message.edit_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )

    await callback.answer()  # убирает "часики"

    # ------------------------------------------------------------
    
async def give_channel_bonus(user_id: int, channel_id: str) -> bool:
    
    file_name = f"bonuses_channel_{channel_id}.json"

    # Загружаем текущий словарь
    if os.path.exists(file_name):
        async with aiofiles.open(file_name, "r", encoding="utf-8") as f:
            content = await f.read()
            bonuses = json.loads(content)
    else:
        bonuses = {}

    # Проверяем, получал ли пользователь
    if str(user_id) in bonuses:
        return False  # бонус уже был

    # Записываем пользователя как получившего бонус
    bonuses[str(user_id)] = True
    async with aiofiles.open(file_name, "w", encoding="utf-8") as f:
        await f.write(json.dumps(bonuses, indent=4, ensure_ascii=False))

    return True