"""
QR-вход на сайт через Telegram (Upscale-style).

Поток:
1. Сайт создаёт ``QrLoginSession`` и показывает QR с deep-link
   ``t.me/<bot>?start=login_<token>``.
2. Пользователь открывает бота → ``/start login_<token>`` (см. handlers/start.py),
   который вызывает :func:`prompt_qr_login`.
3. Бот показывает кнопки «Подтвердить вход» / «Это не я».
4. По подтверждению — сессия CONFIRMED + user_id; сайт по поллингу получает JWT.
"""

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from shared.db.models import QrLoginSession
from shared.db.repositories.user_repository import UserRepository
from shared.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = Router()


async def prompt_qr_login(message: Message, token: str, lang: str = "ru") -> None:
    """Обработать ``/start login_<token>``: показать запрос подтверждения входа."""
    tg_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(QrLoginSession).where(QrLoginSession.token == token))
        qr = result.scalar_one_or_none()

        if not qr:
            await message.answer("❌ Ссылка для входа недействительна. Запросите новый QR на сайте.")
            return

        if qr.status != "PENDING" or qr.expires_at < datetime.utcnow():
            await message.answer("⌛ Срок действия QR истёк. Запросите новый на сайте.")
            return

        # Убеждаемся, что у пользователя есть аккаунт (username хранит код языка)
        repo = UserRepository(session)
        await repo.get_or_create_by_telegram_id(telegram_id=tg_id, username=lang)
        await session.commit()

        session_id = qr.id

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить вход", callback_data=f"qr_confirm:{session_id}"
                ),
                InlineKeyboardButton(text="❌ Это не я", callback_data=f"qr_reject:{session_id}"),
            ]
        ]
    )
    await message.answer(
        "🔐 <b>Вход на сайт FootageHub</b>\n\n"
        "Кто-то входит на сайт под твоим аккаунтом.\n"
        "Если это ты — нажми <b>Подтвердить вход</b>. Если нет — <b>Это не я</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("qr_confirm:"))
async def handle_qr_confirm(callback: CallbackQuery):
    """Пользователь подтвердил вход — помечаем сессию CONFIRMED."""
    try:
        session_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Неверный запрос")
        return

    tg_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(QrLoginSession).where(QrLoginSession.id == session_id).with_for_update()
        )
        qr = result.scalar_one_or_none()

        if not qr:
            await callback.message.edit_text("❌ Сессия входа не найдена.")
            await callback.answer()
            return

        if qr.status != "PENDING":
            await callback.message.edit_text(f"ℹ️ Запрос уже обработан (статус: {qr.status}).")
            await callback.answer()
            return

        if qr.expires_at < datetime.utcnow():
            qr.status = "EXPIRED"
            await session.commit()
            await callback.message.edit_text("⌛ Срок действия истёк. Запросите новый QR на сайте.")
            await callback.answer()
            return

        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(tg_id)
        if not user:
            user = await repo.get_or_create_by_telegram_id(telegram_id=tg_id, username="ru")

        qr.status = "CONFIRMED"
        qr.user_id = user.id
        qr.confirmed_at = datetime.utcnow()
        await session.commit()

    await callback.message.edit_text("✅ Вход подтверждён! Возвращайся на сайт — он откроется сам.")
    await callback.answer("Готово!")
    logger.info(f"QR login {session_id} confirmed for tg_id={tg_id}")


@router.callback_query(F.data.startswith("qr_reject:"))
async def handle_qr_reject(callback: CallbackQuery):
    """Пользователь отклонил вход."""
    try:
        session_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Неверный запрос")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(QrLoginSession).where(QrLoginSession.id == session_id).with_for_update()
        )
        qr = result.scalar_one_or_none()
        if qr and qr.status == "PENDING":
            qr.status = "REJECTED"
            await session.commit()

    await callback.message.edit_text(
        "❌ Вход отклонён. Если это был не ты — всё в порядке, аккаунт в безопасности."
    )
    await callback.answer()
    logger.info(f"QR login {session_id} rejected")
