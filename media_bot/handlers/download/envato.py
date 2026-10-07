"""
Envato download handlers.
"""

import asyncio

from aiogram import Bot, F, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from media_bot.handlers.channel_check import CHANNEL_ID, is_subscribed
from media_bot.handlers.download.validators import auto_delete_download_link, check_user_eligibility
from media_bot.handlers.messages import msg
from media_bot.services import BotServices
from media_bot.state import DownloadFlow
from shared.asset_urls import validate_asset_url
from shared.db.models import ServiceType
from shared.db.repositories import (
    DownloadRepository,
    MediaRepository,
    SubscriptionRepository,
    UserRepository,
)
from shared.db.session import get_session
from shared.error_tracking import report_exception

# Create a separate router for Envato functions
router = Router()


async def _submit_download(url, with_license):
    try:
        return await BotServices.link_processor.submit(url, with_license=with_license)
    except Exception as exc:
        report_exception(exc)
        return None


@router.message(Command("envato"))
@router.callback_query(F.data == "envato_start")
@router.message(F.text.in_({"Скачать Envato", "Download Envato"}))
async def ask_for_link(message: types.Message, state: FSMContext, bot: Bot, lang: str = "ru"):
    """Запрос ссылки на Envato файл"""
    async for session in get_session():
        is_eligible, user = await check_user_eligibility(message, bot, session, lang)
        if not is_eligible:
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=msg("BTN_BACK", lang), callback_data="go_back_menu")]
            ]
        )
        await message.answer(
            msg("APPLY_DOWNLOAD", lang).format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
        await state.set_state(DownloadFlow.waiting_for_link)


@router.message(DownloadFlow.waiting_for_link)
async def handle_link(message: types.Message, state: FSMContext, bot: Bot, lang: str = "ru"):
    """Обработка ссылки на Envato файл"""
    url = message.text.strip()

    # Проверяем, нужна ли лицензия (точка перед URL)
    with_license = False
    if url.startswith(".https://elements.envato.com/") or url.startswith(
        ".https://app.envato.com/"
    ):
        url = url[1:]  # Remove leading dot
        with_license = True
        print(f"[DOWNLOAD] 🔐 Лицензия запрошена для: {url[:60]}...")

    # Проверяем формат ссылки (поддерживаем оба формата)
    try:
        validate_asset_url(url, "envato")
    except ValueError:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=msg("BTN_BACK", lang), callback_data="go_back_menu")]
            ]
        )
        await message.answer(
            msg("BAD_URL", lang),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
        return

    telegram_id = message.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)

        user = await user_repo.get_by_telegram_id(telegram_id)
        if not user:
            await message.answer(
                msg("USER_NOT_FOUND", lang),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            await state.clear()
            return

        download_repo = DownloadRepository(session)
        downloaded = await download_repo.has_user_downloaded(user_id=user.id, url=url)
        print(downloaded)
        if downloaded:
            await message.answer(msg("ALREADY_DOWNLOADED", lang))

            BotServices.link_processor
            file_path = await _submit_download(url, with_license)

            if file_path:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=msg("BTN_DOWNLOAD", lang), url=file_path)]
                    ]
                )

                sent_message = await message.answer(
                    msg("LINK_READY", lang),
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
                    msg("LINK_NOT_FOUND", lang),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )

            await state.clear()
            return

        # Условие оплаты
        if user.credits <= 0:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=msg("BTN_BUY_SUBSCRIPTION", lang), callback_data="buy_subscription"
                        )
                    ]
                ]
            )
            await message.answer(
                msg("CANCLE_DOWNLOAD_PAYMENT_OFF", lang),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            await state.clear()
            return

        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Отправляем сообщение о загрузке
        thinking_msg = await message.answer(msg("PROCESSING_LINK", lang))

        BotServices.link_processor
        file_path = await _submit_download(url, with_license)

        if file_path:
            media_repo = MediaRepository(session)
            media = await media_repo.get_or_create(url=url, file_type="image")
            await download_repo.create_download(
                user_id=user.id, media_id=media.id, service_type=ServiceType.ENVATO
            )

            await thinking_msg.edit_text(msg("PROCESSING_COMPLETE", lang))

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=msg("BTN_DOWNLOAD_FILE", lang), url=file_path)],
                    [
                        InlineKeyboardButton(
                            text=msg("BTN_DOWNLOAD_MORE", lang), callback_data="download_more"
                        )
                    ],
                ]
            )

            user.credits -= 1

            # Увеличиваем счетчик подписки если она есть

            subscription_repo = SubscriptionRepository(session)
            subscription = await subscription_repo.get_active_by_user_id(user.id)
            if subscription:
                await subscription_repo.increment_usage(subscription.id)
                print(f"[DOWNLOAD] ✅ Увеличен счетчик подписки #{subscription.id}")

            sent_message = await message.answer(
                msg("DOWNLOAD_FILE", lang).format(credit=user.credits),
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
                msg("DOWNLOAD_FAILED", lang),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            await message.answer(msg("DOWNLOAD_RETRY", lang), parse_mode=ParseMode.HTML)
        await state.clear()


@router.callback_query(F.data == "download_more")
async def download_more(callback: CallbackQuery, state: FSMContext, bot: Bot, lang: str = "ru"):
    """Обработка кнопки 'Скачать ещё' для Envato"""
    telegram_id = callback.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)

        user = await user_repo.get_by_telegram_id(telegram_id)

        if not user:
            await callback.message.answer(
                msg("USER_NOT_REGISTERED", lang),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            await callback.answer()
            return

        if user.credits <= 0:
            if not await is_subscribed(bot, telegram_id):
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=msg("BTN_SUBSCRIBE_CHANNEL", lang),
                                url=f"https://t.me/{CHANNEL_ID[1:]}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=msg("BTN_CHECK_SUBSCRIPTION", lang),
                                callback_data="check_subscription",
                            )
                        ],
                    ]
                )
                await callback.message.answer(
                    msg("CHANEL_CHECK", lang),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )
                await callback.answer()
                return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=msg("BTN_BACK", lang), callback_data="go_back_menu")]
            ]
        )
        await callback.message.answer(
            msg("APPLY_DOWNLOAD", lang).format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
        await state.set_state(DownloadFlow.waiting_for_link)
        await callback.answer()
