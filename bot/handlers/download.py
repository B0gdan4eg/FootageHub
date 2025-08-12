from aiogram import Router, types, F
from db.session import get_session
from db.user_crud import get_user_by_telegram_id, has_user_downloaded
from db.downloaded_file_crud import create_media, create_download
import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from envato_utils.test_env import test
import asyncio
from aiogram import Bot
from bot.handlers.messages import CANCLE_DOWNLOAD, APPLY_DOWNLOAD, FREEPIK, BAD_URL
from aiogram.enums.parse_mode import ParseMode

router = Router()


async def animate_thinking(message):
    thinking_msg = await message.answer("⏳")
    for emoji in ["🤔", "💭", "🔎", "⏳", "🚀", "⚙️"]:
        await asyncio.sleep(3)
        await thinking_msg.edit_text(emoji)
    return thinking_msg

# Кнопка ENVATO
@router.message(lambda message: message.text == "Скачать Envato")
async def ask_for_link(message: types.Message):
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
        
        if user.credits <= 0:
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
    
# Кнопка FREEPIK 
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
@router.message(F.text)
async def handle_link(message: types.Message, bot: Bot):
    url = message.text.strip()
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
            await message.answer("❌ Пользователь не найден в системе.")
            return
        
        downloaded = await has_user_downloaded(session=session, user_id=user.id, url=url)
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
            
            return
        
        if user.credits <= 0:
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
                    [InlineKeyboardButton(text="⬇️ Скачать", url=file_path)]
                ]
            )
            
            await message.answer(
                "Ваша ссылка:",
                reply_markup=keyboard
            )

            user.credits -= 1
            await session.commit()
        else:
            await thinking_msg.edit_text("❌ Не удалось скачать файл по ссылке.")
