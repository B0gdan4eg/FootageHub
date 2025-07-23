import aiohttp
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
from envato_utils.test_env import test

router = Router()

DOWNLOAD_DIR = "downloads"  # Папка для сохранения файлов
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def download_file(url: str, original_name: str = None) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                content_type = resp.headers.get("Content-Type", "").lower()
                ext = mimetypes.guess_extension(content_type.split(";")[0]) or ".bin"

                if original_name and "." in original_name:
                    filename = original_name
                else:
                    filename = f"{uuid4().hex}{ext}"

                file_path = os.path.join(DOWNLOAD_DIR, filename)

                with open(file_path, "wb") as f:
                    f.write(await resp.read())

                return file_path
    return None


@router.message(lambda message: message.text in ["Скачать Envato", "Скачать Freepik"])
async def ask_for_link(message: types.Message):
    await message.answer("Пришли ссылку для скачивания (URL на изображение, например с сайта Unsplash)")


@router.message(F.text)
async def handle_link(message: types.Message):
    url = message.text.strip()
    if not url.startswith("http"):
        await message.answer("Это не похоже на ссылку.")
        return

    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("Ошибка: пользователь не найден.")
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
                        [InlineKeyboardButton(text="Купить подписку или кредиты", callback_data="create_invoice")]
                    ]
                )

                await message.answer(
                    "У вас закончились бесплатные скачивания. Купите подписку или пополните кредиты.",
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

            if not has_active_sub:
                user.credits -= 1
                await session.commit()

            await message.answer("Файл скачан и сохранён, отправляю:")
            await message.answer_document(types.FSInputFile(file_path))
        else:
            await message.answer("Не удалось скачать файл по ссылке.")


@router.callback_query(lambda c: c.data == "create_invoice")
async def process_invoice_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    amount = 1.0  # Цена подписки или пакета кредитов

    pay_url, invoice_id = await create_crypto_invoice(user_id, amount, type_="subscription")

    if pay_url:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=pay_url)]
            ]
        )
        await callback_query.message.answer(
            "Пожалуйста, оплатите подписку по ссылке ниже:",
            reply_markup=keyboard
        )
    else:
        await callback_query.message.answer(
            "Произошла ошибка при создании инвойса, попробуйте позже."
        )

    await callback_query.answer()

