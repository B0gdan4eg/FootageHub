"""
Broadcast messaging functionality for admin panel.
"""

from aiogram import Bot, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from media_bot.handlers.admin.core import is_admin
from media_bot.keyboards import get_cancel_kb
from media_bot.state import AdminStates
from shared.db.models import User
from shared.db.session import get_session

# Create a separate router for broadcast functions
router = Router()


async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало рассылки сообщений"""
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям:\n\n"
        "⚠️ Сообщение будет отправлено всем пользователям бота!",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_broadcast_text)
async def send_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    """Отправка рассылки всем пользователям"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Рассылка отменена")
        return

    text = message.text.strip()

    sent = 0
    failed = 0

    async for session in get_session():
        users = await session.execute(select(User.tg_id))
        tg_ids = [u[0] for u in users.all()]

    status_message = await message.answer(
        f"📤 Рассылка началась...\nВсего пользователей: {len(tg_ids)}"
    )

    for tg_id in tg_ids:
        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await status_message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n✅ Отправлено: {sent}\n❌ Не отправлено: {failed}",
        parse_mode="HTML",
    )
    await state.clear()
