# channel_check.py
import json
import logging
import os

import aiofiles
from aiogram import Bot, Router
from aiogram.enums import ChatMemberStatus
from aiogram.enums.parse_mode import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from media_bot.config import CHANNEL_BONUS_CREDITS, CHANNEL_ID
from media_bot.handlers.messages import CHANEL_APPLY, CHANEL_CANCLE
from shared.core.logger import get_logger
from shared.db.models import User
from shared.db.repositories import BonusRepository, UserRepository
from shared.db.session import get_session
from shared.services.bonus_service import BonusService
from shared.services.referral_service import ReferralService

logger = get_logger(__name__)
router = Router()


# Метод проверки подписки на канал
# ------------------------------------------------------------
async def is_subscribed(bot: Bot, tg_user_id: int) -> bool:
    try:
        logger.debug(f"Checking subscription for user {tg_user_id} in channel {CHANNEL_ID}")
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=tg_user_id)
        logger.debug(f"Member status: {member.status}")
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        )
    except TelegramForbiddenError as e:
        logger.debug(f"TelegramForbiddenError: {e}")
        return False
    except Exception as e:
        logger.debug(f"Ошибка при проверке подписки: {type(e).__name__}: {e}")
        return False


# ------------------------------------------------------------


# Роутер по коллбэку на проверку подписки
# ------------------------------------------------------------
@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    logger.debug(f"check_subscription callback triggered for user {user_id}")
    subscribed = await is_subscribed(bot, user_id)
    logger.debug(f"User {user_id} subscription status: {subscribed}")

    if not subscribed:
        # Пользователь не подписан — клавиатура для подписки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Подписаться ✅", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                [
                    InlineKeyboardButton(
                        text="Проверить подписку 🔍", callback_data="check_subscription"
                    )
                ],
            ]
        )
        try:
            await callback.message.edit_text(
                CHANEL_CANCLE,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку, если сообщение не изменилось
            if "message is not modified" not in str(e):
                raise
    else:
        logger.debug(f"User {user_id} is subscribed!")
        try:
            async for session in get_session():
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(user_id)
                logger.debug(f"User found in DB: {user is not None}")

                if user:
                    # Используем новую бонусную систему
                    try:
                        bonus_repo = BonusRepository(session)
                        bonus_service = BonusService(bonus_repo, user_repo)
                        referral_service = ReferralService(
                            session, user_repo, bonus_repo, bonus_service
                        )

                        # Проверяем, можно ли начислить бонус
                        can_claim = await bonus_service.can_claim_bonus(
                            user_id=user.id,
                            bonus_code="CHANNEL_SUBSCRIPTION",
                            metadata={"channel_id": CHANNEL_ID},
                        )

                        bonuses_text = []

                        if can_claim:
                            # Начисляем бонус
                            bonus = await bonus_service.claim_bonus(
                                user_id=user.id,
                                bonus_code="CHANNEL_SUBSCRIPTION",
                                metadata={"channel_id": CHANNEL_ID},
                            )
                            bonuses_text.append(
                                f"💰 Вам начислено {bonus.credits_granted} кредита за подписку!"
                            )
                            logger.info(f"CHANNEL_SUBSCRIPTION bonus claimed by user {user_id}")
                        else:
                            bonuses_text.append("✅ Бонус за подписку вы уже получали ранее.")

                        # Проверяем реферальный бонус - начисляем рефереру если этот пользователь был приглашен
                        try:
                            referral_bonus = (
                                await referral_service.trigger_referred_channel_subscription(
                                    referred_user_id=user.id
                                )
                            )
                            if referral_bonus:
                                bonuses_text.append(
                                    f"🎁 Ваш реферер получил {referral_bonus.credits_granted} кредитов за вашу подписку!"
                                )
                                logger.info(f"Referral bonus granted for referred user {user_id}")
                        except Exception as e:
                            logger.error(f"Failed to grant referral bonus: {e}")

                        text = f"{CHANEL_APPLY}\n" + "\n".join(bonuses_text)
                    except Exception as e:
                        logger.error(f"Failed to claim CHANNEL_SUBSCRIPTION bonus: {e}")
                        # Fallback на старую систему
                        bonus_given = await give_channel_bonus(user_id, CHANNEL_ID)
                        logger.debug(f"Bonus given (fallback): {bonus_given}")
                        if bonus_given:
                            user_obj = await session.scalar(
                                select(User).where(User.tg_id == user_id)
                            )
                            if user_obj:
                                user_obj.credits += CHANNEL_BONUS_CREDITS
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
                        logger.debug(f"Message edited successfully")
                    except TelegramBadRequest as e:
                        # Игнорируем ошибку, если сообщение не изменилось
                        if "message is not modified" not in str(e):
                            logger.debug(f"TelegramBadRequest: {e}")
                            raise
        except Exception as e:
            logger.debug(f"Error in subscription success branch: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()

    await callback.answer()  # убирает "часики"
    logger.debug(f"Callback answered")

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
