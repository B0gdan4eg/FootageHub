"""
Handler для привязки аккаунта бота к веб-сайту.

Пользователь получает сообщение от бота с кнопками "Подтвердить"/"Отклонить".
После подтверждения — phone_number переносится из web-аккаунта в бот-аккаунт.
"""

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select

from shared.db.models import BotLinkRequest, User
from shared.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("link_confirm:"))
async def handle_link_confirm(callback: CallbackQuery):
    """Пользователь нажал 'Подтвердить' — привязываем аккаунт."""
    try:
        request_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Неверный запрос")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BotLinkRequest).where(BotLinkRequest.id == request_id)
        )
        req = result.scalar_one_or_none()

        if not req:
            await callback.message.edit_text("❌ Запрос не найден.")
            await callback.answer()
            return

        if req.status != "PENDING":
            await callback.message.edit_text(f"ℹ️ Запрос уже обработан (статус: {req.status}).")
            await callback.answer()
            return

        if req.expires_at < datetime.utcnow():
            req.status = "EXPIRED"
            await session.commit()
            await callback.message.edit_text("❌ Запрос истёк. Попробуйте снова.")
            await callback.answer()
            return

        # Загружаем оба аккаунта
        web_user_result = await session.execute(select(User).where(User.id == req.web_user_id))
        web_user = web_user_result.scalar_one_or_none()

        bot_user_result = await session.execute(select(User).where(User.id == req.bot_user_id))
        bot_user = bot_user_result.scalar_one_or_none()

        if not web_user or not bot_user:
            await callback.message.edit_text("❌ Пользователь не найден.")
            await callback.answer()
            return

        if bot_user.phone_number is not None:
            await callback.message.edit_text("❌ Ваш аккаунт уже привязан к другому номеру.")
            req.status = "REJECTED"
            await session.commit()
            await callback.answer()
            return

        # Переносим phone_number из web-аккаунта в бот-аккаунт
        phone = web_user.phone_number
        bot_user.phone_number = phone

        # Помечаем web-аккаунт как удалённый (или просто убираем phone)
        web_user.phone_number = None  # теперь у web-аккаунта нет телефона
        # Опционально: можно объединить кредиты
        if web_user.credits > 0:
            bot_user.credits += web_user.credits
            web_user.credits = 0
        if web_user.ai_credits > 0:
            bot_user.ai_credits += web_user.ai_credits
            web_user.ai_credits = 0

        req.status = "CONFIRMED"
        await session.commit()

    await callback.message.edit_text(
        "✅ Аккаунт успешно привязан!\n\n"
        "Теперь вы можете войти на сайт через номер телефона "
        "и видеть всю историю из бота."
    )
    await callback.answer("Готово!")
    logger.info(f"Bot link request {request_id} confirmed: bot_user={req.bot_user_id}")


@router.callback_query(F.data.startswith("link_reject:"))
async def handle_link_reject(callback: CallbackQuery):
    """Пользователь нажал 'Отклонить' — отменяем запрос."""
    try:
        request_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Неверный запрос")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BotLinkRequest).where(BotLinkRequest.id == request_id)
        )
        req = result.scalar_one_or_none()

        if req and req.status == "PENDING":
            req.status = "REJECTED"
            await session.commit()

    await callback.message.edit_text(
        "❌ Привязка аккаунта отменена.\n\n"
        "Если вы не делали этот запрос — ничего страшного, "
        "ваш аккаунт в безопасности."
    )
    await callback.answer()
    logger.info(f"Bot link request {request_id} rejected")
