from aiogram import Router, types, F, Bot
from db.session import get_session
from db.user_crud import get_user_by_telegram_id, has_user_downloaded
from db.downloaded_file_crud import create_media, create_download
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from envato_utils.test_env import test
import asyncio
from aiogram.filters import Command
from bot.handlers.messages import CANCLE_DOWNLOAD, APPLY_DOWNLOAD, FREEPIK, BAD_URL, DOWNLOAD_FILE, CHANEL_CHECK
from aiogram.enums.parse_mode import ParseMode
from bot.state import DownloadFlow
from aiogram.fsm.context import FSMContext
from bot.handlers.channel_check import is_subscribed, CHANNEL_ID

router = Router()


async def animate_thinking(message):
    thinking_msg = await message.answer("⏳")
    for emoji in ["🤔", "💭", "🔎", "⏳", "🚀", "⚙️"]:
        await asyncio.sleep(3)
        await thinking_msg.edit_text(emoji)
    return thinking_msg

# Кнопка ENVATO
@router.message(Command("envato"))
@router.callback_query(F.data == "envato_start")
@router.message(lambda message: message.text == "Скачать Envato")
async def ask_for_link(message: types.Message, state: FSMContext, bot: Bot):
    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("Похоже, вы не зарегистрированы. Пожалуйста, начните с /start.")
            return

        # has_active_sub = (
        #     user.is_subscribed
        #     and user.subscription_until
        #     and user.subscription_until > datetime.datetime.utcnow()
        # )
        
        # if user.credits <= 0:
        if False:    
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
                return
                
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Оплата 💳", callback_data="create_invoice")]
                ]
            )
            await message.answer(
                CANCLE_DOWNLOAD,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            return

        # Если подписка есть или кредиты больше 0 — просим ссылку
        await message.answer(
                APPLY_DOWNLOAD.format(credit=user.credits),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        
        # Переходим в состояние ожидания ссылки
        await state.set_state(DownloadFlow.waiting_for_link)
    
# Кнопка FREEPIK 
@router.message(Command("freepik"))
@router.callback_query(F.data == "freepik_soon")
@router.message(lambda message: message.text in ["Скачать Freepik(Скоро...)"])
async def ask_for_link(message: types.Message):
    subscribe_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
        [InlineKeyboardButton(text="Канал с новостями📢", url="https://t.me/+HVUoctN58uc3ZDYy")]
            ]
        )
    await message.answer(
                FREEPIK,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=subscribe_keyboard
            )

# Обработка ссылки
@router.message(DownloadFlow.waiting_for_link)
async def handle_link(message: types.Message, state: FSMContext, bot: Bot):
    url = message.text.strip()
    if not url.startswith("https://elements.envato.com/"):
    
        # back_keyboard = InlineKeyboardMarkup(
        #     inline_keyboard=[
        #         [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="go_back_menu")]
        #     ]
        # )
            
        await message.answer(
            BAD_URL,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            # reply_markup=back_keyboard
            )
        return

    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден в системе.")
            await state.clear()
            return
        
        downloaded = await has_user_downloaded(session=session, user_id=user.id, url=url)
        print(downloaded)
        if downloaded:
            
            await message.answer(
                "Мы видим что вы ранее пытались скачать этот файл, ожидайте вышлем вам новую ссылку",
            )
            
            file_path = await test(url)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬇️ Скачать", url=file_path)]
                ]
            )
            
            await message.answer(
                "Ваша ссылка:",
                reply_markup=keyboard
            )
            await state.clear()
            return
        
        # if user.credits <= 0:
        if False:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Оплата 💳", callback_data="create_invoice")]
                ]
            )
            await message.answer(
                CANCLE_DOWNLOAD,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            await state.clear()
            return
        
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # Запускаем анимацию в таске (чтобы не блокировать основной поток)
        thinking_task = asyncio.create_task(animate_thinking(message))
        
        file_path = await test(url)
        
        # Ждём завершения анимации (если она ещё не закончилась) и получаем сообщение
        thinking_msg = await thinking_task
        
        if file_path:
            media = await create_media(session, url=url, file_type="image")
            await create_download(session, user.id, media.id)
            
            await thinking_msg.edit_text("✅ Готово!")
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Cкачать файл 📁", url=file_path)],
                    [InlineKeyboardButton(text="Cкачать ещё", callback_data="download_more")]
                ]
            )
            
            user.credits -= 1
            
            await message.answer(
                DOWNLOAD_FILE.format(credit=user.credits),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )

            await session.commit()
        else:
            await thinking_msg.edit_text("❌ Не удалось скачать файл по ссылке.")
        await state.clear()

# Хэндлер на кнопку "Скачать ещё"
@router.callback_query(F.data == "download_more")
async def download_more(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await callback.message.answer("❌ Пользователь не найден в системе.")
            return

        # if user.credits <= 0:
        if False:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Оплата 💳", callback_data="create_invoice")]
                ]
            )
            await callback.message.answer(
                CANCLE_DOWNLOAD,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            return

        # Просим новую ссылку
        await callback.message.answer(
            APPLY_DOWNLOAD.format(credit=user.credits),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        # Переводим в состояние ожидания ссылки
        await state.set_state(DownloadFlow.waiting_for_link)