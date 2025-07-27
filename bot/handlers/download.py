import os
from aiogram import Router, types, F
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.downloaded_file_crud import get_media_by_url, create_media, create_download
import mimetypes
from uuid import uuid4
import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.crypto import create_crypto_invoice
from services.json_reader import dict_to_namespace
from envato_utils.test_env import test

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
async def handle_link(message: types.Message):
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

        media = await get_media_by_url(session, url)
        if media:
            if not has_active_sub and user.credits <= 0:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Купить подписку или кредиты", callback_data="create_invoice")]
                    ]
                )

                await message.answer(
                    "⚠️ У вас закончились кредиты и нет активной подписки.\n"
                    "Пожалуйста, пополните баланс, чтобы продолжить загрузки.",
                    reply_markup=keyboard
                )
                return

            await create_download(session, user.id, media.id)

            if not has_active_sub:
                user.credits -= 1
                await session.commit()

            await message.answer("Файл найден в кеше, отправляю:")
            await message.answer_document(types.FSInputFile(media.file_path))
            return

        # Если файл не в кеше
        if not has_active_sub and user.credits <= 0:
            keyboard = InlineKeyboardMarkup(row_width=1)
            pay_button = InlineKeyboardButton(text="Купить подписку или кредиты", callback_data="create_invoice")
            keyboard.add(pay_button)

            await message.answer(
                "У вас закончились бесплатные скачивания. Купите подписку или пополните кредиты.",
                reply_markup=keyboard
            )
            return

        # filename = url.split("/")[-1].split("?")[0] or "file"
        # file_path = await download_file(url, filename)
        file_path = await test(url)
        print(file_path,url)
        if file_path:
            media = await create_media(session, url=url, file_path=file_path, file_type="image")
            await create_download(session, user.id, media.id)
            
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
            await message.answer("Не удалось скачать файл по ссылке.")


# @router.callback_query(lambda c: c.data == "create_invoice")
# async def process_invoice_callback(callback_query: types.CallbackQuery):
#     user_id = callback_query.from_user.id
#     amount = 1.0  # Цена подписки или пакета кредитов

#     pay_url, invoice_id = await create_crypto_invoice(user_id, amount, type_="subscription")

#     if pay_url:
#         keyboard = InlineKeyboardMarkup(
#             inline_keyboard=[[
#                     InlineKeyboardButton(text="Подписка"),
#                     InlineKeyboardButton(text="Кредиты")
#                 ]]
#         )
#         await callback_query.message.answer(
#             "Пожалуйста, оплатите подписку по ссылке ниже:",
#             reply_markup=keyboard
#         )
#     else:
#         await callback_query.message.answer(
#             "Произошла ошибка при создании инвойса, попробуйте позже."
#         )

#     await callback_query.answer()
    
