from aiogram import Router, types, F, Bot
from db.session import get_session
from db.user_crud import get_user_by_telegram_id, has_user_downloaded
from db.downloaded_file_crud import create_media, create_download
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from bot.handlers.messages import (
    CANCLE_DOWNLOAD, APPLY_DOWNLOAD, FREEPIK, BAD_URL, DOWNLOAD_FILE,
    CHANEL_CHECK, CANCLE_DOWNLOAD_PAYMENT_OFF, APPLY_DOWNLOAD_FREEPIK,
    BAD_URL_FREEPIK, USER_NOT_REGISTERED, USER_NOT_FOUND, DOWNLOAD_FAILED,
    DOWNLOAD_RETRY, LINK_NOT_FOUND, LINK_READY, PROCESSING_LINK,
    PROCESSING_COMPLETE, ALREADY_DOWNLOADED, NO_SUBSCRIPTION_FOR_LICENSE
)
from aiogram.enums.parse_mode import ParseMode
from bot.state import DownloadFlow
from aiogram.fsm.context import FSMContext
from bot.handlers.channel_check import is_subscribed, CHANNEL_ID

router = Router()


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
                [InlineKeyboardButton(text="💳 Увеличить лимиты", callback_data="buy_subscription")]
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


# Кнопка ENVATO
@router.message(Command("envato"))
@router.callback_query(F.data == "envato_start")
@router.message(lambda message: message.text == "Скачать Envato")
async def ask_for_link(message: types.Message, state: FSMContext, bot: Bot):
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
    
# Кнопка FREEPIK
@router.message(Command("freepik"))
@router.callback_query(F.data == "freepik_start")
@router.message(lambda message: message.text == "Скачать Freepik")
async def ask_for_freepik_link(message: types.Message, state: FSMContext, bot: Bot):
    async for session in get_session():
        is_eligible, user = await check_user_eligibility(message, bot, session)
        if not is_eligible:
            return

        await message.answer(
            APPLY_DOWNLOAD_FREEPIK.format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await state.set_state(DownloadFlow.waiting_for_freepik_link)

# Обработка ссылки
@router.message(DownloadFlow.waiting_for_link)
async def handle_link(message: types.Message, state: FSMContext, bot: Bot):
    url = message.text.strip()

    # Проверяем формат ссылки и определяем нужна ли лицензия
    with_license = False
    if url.startswith(".https://elements.envato.com/"):
        # Убираем точку и включаем режим с лицензией
        url = url[1:]
        with_license = True
        print(f"[DOWNLOAD] Запрос на скачивание С ЛИЦЕНЗИЕЙ: {url[:50]}...")
    elif url.startswith("https://elements.envato.com/"):
        with_license = False
    else:
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
        
        # Проверка подписки для скачивания с лицензией
        if with_license:
            from db.subscription_crud import get_active_subscription
            from db.models import ServiceType

            subscription = await get_active_subscription(session, user.id, ServiceType.ENVATO)
            if not subscription:
                # Нет активной подписки - отказываем
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="buy_subscription")]
                    ]
                )
                await message.answer(
                    NO_SUBSCRIPTION_FOR_LICENSE,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
                await state.clear()
                return
            print(f"[DOWNLOAD] ✅ Подписка активна, разрешаем скачивание с лицензией")

        downloaded = await has_user_downloaded(session=session, user_id=user.id, url=url)
        print(downloaded)
        if downloaded:

            await message.answer(ALREADY_DOWNLOADED)

            # Get link_processor from BotServices
            from bot.services import BotServices
            link_processor = BotServices.link_processor
            file_path = await link_processor.submit(url, with_license=with_license)

            # ✅ ДОБАВЛЯЕМ ПРОВЕРКУ
            if file_path:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬇️ Скачать", url=file_path)]
                    ]
                )

                await message.answer(
                    LINK_READY,
                    reply_markup=keyboard
                )
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
            await create_download(session, user.id, media.id)

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

            await message.answer(
                DOWNLOAD_FILE.format(credit=user.credits),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )

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

# Обработка ссылки Freepik
@router.message(DownloadFlow.waiting_for_freepik_link)
async def handle_freepik_link(message: types.Message, state: FSMContext, bot: Bot):
    url = message.text.strip()
    if not "freepik.com" in url.lower():

        await message.answer(
            BAD_URL_FREEPIK,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
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

            # Get Freepik downloader
            from freepik_utils.freepik import get_freepik_direct_download_url
            file_path = await get_freepik_direct_download_url(url)

            if file_path:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬇️ Скачать", url=file_path)]
                    ]
                )

                await message.answer(
                    LINK_READY,
                    reply_markup=keyboard
                )
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

        # Get Freepik downloader
        from freepik_utils.freepik import get_freepik_direct_download_url
        file_path = await get_freepik_direct_download_url(url)

        if file_path:
            media = await create_media(session, url=url, file_type="image")
            await create_download(session, user.id, media.id)

            await thinking_msg.edit_text(PROCESSING_COMPLETE)

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Cкачать файл 📁", url=file_path)],
                    [InlineKeyboardButton(text="Cкачать ещё", callback_data="download_more_freepik")]
                ]
            )

            user.credits -= 1

            # Увеличиваем счетчик подписки если она есть
            from db.subscription_crud import increment_download_count, get_active_subscription

            subscription = await get_active_subscription(session, user.id)
            if subscription:
                await increment_download_count(session, subscription.id)
                print(f"[DOWNLOAD] ✅ Увеличен счетчик подписки #{subscription.id}")

            await message.answer(
                DOWNLOAD_FILE.format(credit=user.credits),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )

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

# Хэндлер на кнопку "Скачать ещё"
@router.callback_query(F.data == "download_more")
async def download_more(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # Получаем telegram_id из callback, а не из message
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

# Хэндлер на кнопку "Скачать ещё" для Freepik
@router.callback_query(F.data == "download_more_freepik")
async def download_more_freepik(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # Получаем telegram_id из callback, а не из message
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
            APPLY_DOWNLOAD_FREEPIK.format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await state.set_state(DownloadFlow.waiting_for_freepik_link)
        await callback.answer()