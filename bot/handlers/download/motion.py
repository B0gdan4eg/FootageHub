"""
Motion Array download handlers.
"""

import asyncio

from aiogram import Bot, F, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers.channel_check import CHANNEL_ID, is_subscribed
from bot.handlers.download.validators import auto_delete_download_link, check_user_eligibility
from bot.handlers.messages import (
    ALREADY_DOWNLOADED,
    APPLY_DOWNLOAD_MOTION,
    BAD_URL_MOTION,
    CANCLE_DOWNLOAD_PAYMENT_OFF,
    CHANEL_CHECK,
    DOWNLOAD_FAILED,
    DOWNLOAD_FILE,
    DOWNLOAD_RETRY,
    LINK_NOT_FOUND,
    LINK_READY,
    PROCESSING_COMPLETE,
    PROCESSING_LINK,
    USER_NOT_FOUND,
    USER_NOT_REGISTERED,
)
from bot.state import DownloadFlow
from db.downloaded_file_crud import create_download, create_media
from db.models import ServiceType
from db.session import get_session
from db.user_crud import get_user_by_telegram_id, has_user_downloaded

# Create a separate router for Motion Array functions
router = Router()


@router.message(Command("motion"))
@router.callback_query(F.data == "motion_start")
@router.message(lambda message: message.text == "Скачать Motion Array")
async def ask_for_motion_link(message: types.Message, state: FSMContext, bot: Bot):
    """Запрос ссылки на Motion Array файл"""
    async for session in get_session():
        is_eligible, user = await check_user_eligibility(message, bot, session)
        if not is_eligible:
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="« Назад", callback_data="go_back_menu")]]
        )
        await message.answer(
            APPLY_DOWNLOAD_MOTION.format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
        await state.set_state(DownloadFlow.waiting_for_motion_link)


@router.message(DownloadFlow.waiting_for_motion_link)
async def handle_motion_link(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка ссылки на Motion Array файл"""
    url = message.text.strip()

    # Проверяем формат ссылки
    if not url.startswith("https://motionarray.com/"):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="« Назад", callback_data="go_back_menu")]]
        )
        await message.answer(
            BAD_URL_MOTION,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
        return

    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer(
                USER_NOT_FOUND, parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
            await state.clear()
            return

        downloaded = await has_user_downloaded(session=session, user_id=user.id, url=url)
        print(downloaded)
        if downloaded:
            await message.answer(ALREADY_DOWNLOADED)

            # Get link_processor from BotServices
            from bot.services import BotServices

            link_processor = BotServices.link_processor
            file_path = await link_processor.submit(url, platform="motion")

            if file_path:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬇️ Скачать", url=file_path)]]
                )

                sent_message = await message.answer(
                    LINK_READY,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )

                # Удаляем кнопку через 30 секунд
                asyncio.create_task(
                    auto_delete_download_link(sent_message, delay=30, keep_second_button=True)
                )
            else:
                await message.answer(
                    LINK_NOT_FOUND, parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )

            await state.clear()
            return

        # Условие оплаты
        if user.credits <= 0:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💳 Оформить подписку", callback_data="buy_subscription"
                        )
                    ]
                ]
            )
            await message.answer(
                CANCLE_DOWNLOAD_PAYMENT_OFF,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            await state.clear()
            return

        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Отправляем сообщение о загрузке
        thinking_msg = await message.answer(PROCESSING_LINK)

        # Get link_processor from BotServices (no circular import)
        from bot.services import BotServices

        link_processor = BotServices.link_processor
        file_path = await link_processor.submit(url, platform="motion")

        if file_path:
            media = await create_media(session, url=url, file_type="video")
            await create_download(session, user.id, media.id, service_type=ServiceType.MOTION_ARRAY)

            await thinking_msg.edit_text(PROCESSING_COMPLETE)

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Cкачать файл 📁", url=file_path)],
                    [
                        InlineKeyboardButton(
                            text="Cкачать ещё", callback_data="download_more_motion"
                        )
                    ],
                ]
            )

            user.credits -= 1

            # Увеличиваем счетчик подписки если она есть
            from db.subscription_crud import get_active_subscription, increment_download_count

            subscription = await get_active_subscription(session, user.id)
            if subscription:
                await increment_download_count(session, subscription.id)
                print(f"[DOWNLOAD] ✅ Увеличен счетчик подписки #{subscription.id}")

            sent_message = await message.answer(
                DOWNLOAD_FILE.format(credit=user.credits),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )

            # Удаляем кнопку через 30 секунд, оставляя кнопку "Скачать ещё"
            asyncio.create_task(
                auto_delete_download_link(sent_message, delay=30, keep_second_button=True)
            )

            await session.commit()
        else:
            await thinking_msg.edit_text(
                DOWNLOAD_FAILED, parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
            await message.answer(DOWNLOAD_RETRY, parse_mode=ParseMode.HTML)
        await state.clear()


@router.callback_query(F.data == "download_more_motion")
async def download_more_motion(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка кнопки 'Скачать ещё' для Motion Array"""
    telegram_id = callback.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)

        if not user:
            await callback.message.answer(
                USER_NOT_REGISTERED, parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
            await callback.answer()
            return

        if user.credits <= 0:
            if not await is_subscribed(bot, telegram_id):
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Подписаться ✅", url=f"https://t.me/{CHANNEL_ID[1:]}"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="Проверить подписку 🔍", callback_data="check_subscription"
                            )
                        ],
                    ]
                )
                await callback.message.answer(
                    CHANEL_CHECK,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )
                await callback.answer()
                return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="« Назад", callback_data="go_back_menu")]]
        )
        await callback.message.answer(
            APPLY_DOWNLOAD_MOTION.format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
        await state.set_state(DownloadFlow.waiting_for_motion_link)
        await callback.answer()
