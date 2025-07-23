from fastapi import APIRouter, Request
from db.session import get_session
from db.payment_crud import get_payment_by_invoice_id, mark_payment_success
from db.user_crud import get_user_by_telegram_id
from datetime import datetime, timedelta

router = APIRouter()


@router.post("/cryptobot/webhook")
async def cryptobot_webhook(request: Request):
    payload = await request.json()

    # Проверка типа события
    if payload.get("event") != "invoice_paid":
        return {"status": "ignored"}

    invoice_id = str(payload["invoice_id"])

    async for session in get_session():
        payment = await get_payment_by_invoice_id(session, invoice_id)
        if not payment:
            return {"status": "payment_not_found"}

        if payment.status == "success":
            return {"status": "already_processed"}

        # Обновляем статус платежа
        await mark_payment_success(session, invoice_id)

        # Обновляем подписку пользователя
        user = await get_user_by_telegram_id(session, payment.user_id)
        if not user:
            return {"status": "user_not_found"}

        now = datetime.utcnow()
        if user.subscription_until and user.subscription_until > now:
            user.subscription_until += timedelta(days=30)
        else:
            user.subscription_until = now + timedelta(days=30)

        user.is_subscribed = True
        await session.commit()

        return {"status": "ok"}