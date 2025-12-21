# channel_check.py
from aiogram import Bot, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
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
from bot.config import CHANNEL_ID, CHANNEL_BONUS_CREDITS

router = Router()

# Метод проверки подписки на канал
# ------------------------------------------------------------
async def is_subscribed(bot: Bot, tg_user_id: int) -> bool:
    try:
        print(f"[DEBUG] Checking subscription for user {tg_user_id} in channel {CHANNEL_ID}")
        member = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=tg_user_id
        )
        print(f"[DEBUG] Member status: {member.status}")
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        )
    except TelegramForbiddenError as e:
        print(f"[DEBUG] TelegramForbiddenError: {e}")
        return False
    except Exception as e:
        print(f"[DEBUG] Ошибка при проверке подписки: {type(e).__name__}: {e}")
        return False
# ------------------------------------------------------------


# Роутер по коллбэку на проверку подписки
# ------------------------------------------------------------
@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    print(f"[DEBUG] check_subscription callback triggered for user {user_id}")
    subscribed = await is_subscribed(bot, user_id)
    print(f"[DEBUG] User {user_id} subscription status: {subscribed}")

    if not subscribed:
        # Пользователь не подписан — клавиатура для подписки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Подписаться ✅", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                [InlineKeyboardButton(text="Проверить подписку 🔍", callback_data="check_subscription")]
            ]
        )
        try:
            await callback.message.edit_text(
                CHANEL_CANCLE,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку, если сообщение не изменилось
            if "message is not modified" not in str(e):
                raise
    else:
        print(f"[DEBUG] User {user_id} is subscribed!")
        try:
            async for session in get_session():
                user = await session.scalar(select(User).where(User.tg_id == user_id))
                print(f"[DEBUG] User found in DB: {user is not None}")
                if user:
                    bonus_given = await give_channel_bonus(user_id, CHANNEL_ID)
                    print(f"[DEBUG] Bonus given: {bonus_given}")
                    if bonus_given:
                        user.credits += CHANNEL_BONUS_CREDITS
                        await session.commit()
                        text = f"{CHANEL_APPLY}\n💰 Вам начислено {CHANNEL_BONUS_CREDITS} кредита за подписку!"
                    else:
                        text = f"{CHANEL_APPLY}\n❌ Бонус за подписку вы уже получали ранее."

                    try:
                        await callback.message.edit_text(
                            text,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                        )
                        print(f"[DEBUG] Message edited successfully")
                    except TelegramBadRequest as e:
                        # Игнорируем ошибку, если сообщение не изменилось
                        if "message is not modified" not in str(e):
                            print(f"[DEBUG] TelegramBadRequest: {e}")
                            raise
        except Exception as e:
            print(f"[DEBUG] Error in subscription success branch: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    await callback.answer()  # убирает "часики"
    print(f"[DEBUG] Callback answered")

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