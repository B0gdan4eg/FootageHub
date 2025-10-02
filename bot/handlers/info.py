from aiogram import Router, types
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.downloaded_file_crud import count_downloads_by_user
from aiogram.enums.parse_mode import ParseMode

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

        INFO_MASSEGE = (
            f"<b>👤 Информация о вашем аккаунте:</b>\n\n"
            f"💼 <b>Подписка:</b> {'✅ Активна' if user.is_subscribed else '❌ Неактивна'}\n"
            f"📅 <b>Действует до:</b> {user.subscription_until if user.is_subscribed else '—'}\n"
            f"💳 <b>Доступные загрузки:</b> {'❗️0' if user.credits == 0 else user.credits}\n"
            f"📥 <b>Скачиваний всего:</b> {downloads_count}"
        )

        await message.answer(
            INFO_MASSEGE.format(name=message.from_user.first_name),
            parse_mode=ParseMode.HTML,
        )
