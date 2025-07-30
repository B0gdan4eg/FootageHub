from aiogram import Router, types, F
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.downloaded_file_crud import create_media, create_download
import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from envato_utils.test_env import test
import asyncio
from aiogram import Bot

router = Router()

@router.message(lambda message: message.text == "Скачать Envato")
async def ask_for_link(message: types.Message):
    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("Похоже, вы не зарегистрированы. Пожалуйста, начните с /start.")
            return

        has_active_sub = (
            user.is_subscribed
            and user.subscription_until
            and user.subscription_until > datetime.datetime.utcnow()
        )
        
        if not has_active_sub and user.credits <= 0:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Купить подписку или кредиты", callback_data="create_invoice")]
                ]
            )
            await message.answer(
                "У вас нет активной подписки и закончились кредиты.\nПожалуйста, приобретите подписку или кредиты, чтобы продолжить.",
                reply_markup=keyboard
            )
            return

        # Если подписка есть или кредиты больше 0 — просим ссылку
        await message.answer(f"У вас осталось ({user.credits}) кредита\nПришли ссылку для скачивания (URL с сайта Envato)")
    
@router.message(lambda message: message.text in ["Скачать Freepik(Скоро...)"])
async def ask_for_link(message: types.Message):
    await message.answer("Находится в разработке, так же как и многие другие ресурсы, ждите обновлений")

@router.message(F.text)
async def handle_link(message: types.Message, bot: Bot):
    url = message.text.strip()
    if not url.startswith("https://elements.envato.com/"):
        await message.answer("❌ Это не похоже на ссылку от Envato Elements.")
        return

    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден в системе.")
            return

        has_active_sub = (
            user.is_subscribed
            and user.subscription_until
            and user.subscription_until > datetime.datetime.utcnow()
        )

        # Если файл не в кеше
        if not has_active_sub and user.credits <= 0:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Купить подписку или кредиты", callback_data="create_invoice")]
                ]
            )

            await message.answer(
                "У вас закончились бесплатные скачивания. Купите подписку или пополните кредиты.",
                reply_markup=keyboard
            )
            return
        
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        thinking_msg = await message.answer("⏳")
        for emoji in ["🤔", "💭", "🧠", "⏳"]:
            await asyncio.sleep(0.5)
            await thinking_msg.edit_text(emoji)


        file_path = await test(url)
        print(file_path,url)
        if file_path:
            media = await create_media(session, url=url, file_path=file_path, file_type="image")
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

            if not has_active_sub:
                user.credits -= 1
                await session.commit()
        else:
            await thinking_msg.edit_text("❌ Не удалось скачать файл по ссылке.")
