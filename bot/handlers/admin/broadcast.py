"""
Broadcast messaging functionality for admin panel.
"""

from aiogram import Bot, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.state import AdminStates
from db.models import User
from db.session import get_session

# Create a separate router for broadcast functions
router = Router()


@router.callback_query(lambda c: c.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    """Начало рассылки сообщений"""
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.message.answer(
        "📝 Введите текст оповещения, который нужно отправить всем пользователям:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast_text)
async def send_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    """Отправка рассылки всем пользователям"""
    text = message.text.strip()

    if text.lower() in {"отмена", "cancel"}:
        await state.clear()
        return await message.answer("❌ Рассылка отменена.")

    sent = 0
    failed = 0

    async for session in get_session():
        users = await session.execute(select(User.tg_id))
        tg_ids = [u[0] for u in users.all()]

    for tg_id in tg_ids:
        try:
            await bot.send_message(tg_id, text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"✅ Рассылка завершена!\n📬 Отправлено: {sent}\n⚠️ Ошибок: {failed}")
    await state.clear()
