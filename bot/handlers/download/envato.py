"""
Envato download handlers.
"""

from aiogram import Router, types, F, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode
import asyncio

from db.session import get_session
from db.user_crud import get_user_by_telegram_id, has_user_downloaded
from db.downloaded_file_crud import create_media, create_download
from db.models import ServiceType
from bot.state import DownloadFlow
from bot.handlers.channel_check import is_subscribed, CHANNEL_ID
from bot.handlers.messages import (
    APPLY_DOWNLOAD, BAD_URL, DOWNLOAD_FILE,
    USER_NOT_REGISTERED, USER_NOT_FOUND, DOWNLOAD_FAILED,
    DOWNLOAD_RETRY, LINK_NOT_FOUND, LINK_READY, PROCESSING_LINK,
    PROCESSING_COMPLETE, ALREADY_DOWNLOADED, CHANEL_CHECK,
    CANCLE_DOWNLOAD_PAYMENT_OFF
)
from bot.handlers.download.validators import check_user_eligibility, auto_delete_download_link

# Create a separate router for Envato functions
router = Router()


@router.message(Command("envato"))
@router.callback_query(F.data == "envato_start")
@router.message(lambda message: message.text == "Скачать Envato")
async def ask_for_link(message: types.Message, state: FSMContext, bot: Bot):
    """Запрос ссылки на Envato файл"""
    async for session in get_session():
        is_eligible, user = await check_user_eligibility(message, bot, session)
        if not is_eligible:
            return

        await message.answer(
            APPLY_DOWNLOAD.format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await state.set_state(DownloadFlow.waiting_for_link)


@router.message(DownloadFlow.waiting_for_link)
async def handle_link(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка ссылки на Envato файл"""
    url = message.text.strip()

    # Проверяем, нужна ли лицензия (точка перед URL)
    with_license = False
    if url.startswith(".https://elements.envato.com/"):
        url = url[1:]  # Remove leading dot
        with_license = True
        print(f"[DOWNLOAD] 🔐 Лицензия запрошена для: {url[:60]}...")

    # Проверяем формат ссылки
    if not url.startswith("https://elements.envato.com/"):
        await message.answer(
            BAD_URL,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return

    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer(
                USER_NOT_FOUND,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
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
            file_path = await link_processor.submit(url, with_license=with_license)

            if file_path:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬇️ Скачать", url=file_path)]
                    ]
                )

                sent_message = await message.answer(
                    LINK_READY,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )

                # Удаляем кнопку через 30 секунд
                asyncio.create_task(auto_delete_download_link(sent_message, delay=30, keep_second_button=True))
            else:
                await message.answer(
                    LINK_NOT_FOUND,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

            await state.clear()
            return

        # Условие оплаты
        if user.credits <= 0:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Увеличить лимиты", callback_data="buy_subscription")]
                ]
            )
            await message.answer(
                CANCLE_DOWNLOAD_PAYMENT_OFF,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            await state.clear()
            return

        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Отправляем сообщение о загрузке
        thinking_msg = await message.answer(PROCESSING_LINK)

        # Get link_processor from BotServices (no circular import)
        from bot.services import BotServices
        link_processor = BotServices.link_processor
        file_path = await link_processor.submit(url, with_license=with_license)

        if file_path:
            media = await create_media(session, url=url, file_type="image")
            await create_download(session, user.id, media.id, service_type=ServiceType.ENVATO)

            await thinking_msg.edit_text(PROCESSING_COMPLETE)

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Cкачать файл 📁", url=file_path)],
                    [InlineKeyboardButton(text="Cкачать ещё", callback_data="download_more")]
                ]
            )

            user.credits -= 1

            # Увеличиваем счетчик подписки если она есть
            from db.subscription_crud import increment_download_count, get_active_subscription

            subscription = await get_active_subscription(session, user.id)
            if subscription:
                await increment_download_count(session, subscription.id)
                print(f"[DOWNLOAD] ✅ Увеличен счетчик подписки #{subscription.id}")

            sent_message = await message.answer(
                DOWNLOAD_FILE.format(credit=user.credits),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )

            # Удаляем кнопку через 30 секунд, оставляя кнопку "Скачать ещё"
            asyncio.create_task(auto_delete_download_link(sent_message, delay=30, keep_second_button=True))

            await session.commit()
        else:
            await thinking_msg.edit_text(
                DOWNLOAD_FAILED,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            await message.answer(
                DOWNLOAD_RETRY,
                parse_mode=ParseMode.HTML
            )
        await state.clear()


@router.callback_query(F.data == "download_more")
async def download_more(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка кнопки 'Скачать ещё' для Envato"""
    telegram_id = callback.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)

        if not user:
            await callback.message.answer(
                USER_NOT_REGISTERED,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            await callback.answer()
            return

        if user.credits <= 0:
            if not await is_subscribed(bot, telegram_id):
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Подписаться ✅", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                        [InlineKeyboardButton(text="Проверить подписку 🔍", callback_data="check_subscription")]
                    ]
                )
                await callback.message.answer(
                    CHANEL_CHECK,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
                await callback.answer()
                return

        await callback.message.answer(
            APPLY_DOWNLOAD.format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await state.set_state(DownloadFlow.waiting_for_link)
        await callback.answer()
