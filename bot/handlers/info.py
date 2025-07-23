from aiogram import Router, types
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.downloaded_file_crud import count_downloads_by_user
import datetime

router = Router()

@router.message(lambda message: message.text == "Информация")
async def info(message: types.Message):
    telegram_id = message.from_user.id

    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("Пользователь не найден.")
            return

        downloads_count = await count_downloads_by_user(session, user.id)

        if user.is_subscribed and user.subscription_until:
            subscription_status = "Активна"
            subscription_until_str = user.subscription_until.strftime("%d.%m.%Y %H:%M")
        else:
            subscription_status = "Отсутствует"
            subscription_until_str = "-"

        text = (
            f"Информация о вашем аккаунте:\n"
            f"Подписка: {subscription_status}\n"
            f"Действует до: {subscription_until_str}\n"
            f"Кредиты: {user.credits}\n"
            f"Скачиваний всего: {downloads_count}"
        )
        await message.answer(text)
