from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_session
from db.models import User, Payment
import json
from datetime import datetime, timedelta
from decimal import Decimal
import os

CRYPTO_BOT_SECRET = os.getenv("CRYPTO_BOT_SECRET")

router = APIRouter()

@router.post("/webhook/cryptobot")
async def handle_crypto_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.body()

    data = json.loads(body)

    if data.get("update_type") != "invoice_paid":
        return {"status": "ignored (not invoice_paid)"}

    invoice = data.get("payload")
    if not invoice or invoice.get("status") != "paid":
        return {"status": "ignored (not paid)"}

    # Достаём payload: "123456:credits"
    raw_payload = invoice.get("payload")
    try:
        user_id_str, purchase_type = raw_payload.split(":")
        user_id = int(user_id_str)
    except Exception:
        return {"status": "invalid payload format"}

    user = await session.get(User, user_id)
    if not user:
        return {"status": "user not found"}

    # Сохраняем платёж
    payment = Payment(
        user_id=user.id,
        amount=Decimal(invoice["paid_amount"]),
        currency=invoice["paid_asset"],
        type=purchase_type,
        status="success",
        invoice_id=str(invoice["invoice_id"]),
    )
    session.add(payment)

    # Обработка логики покупки
    if purchase_type == "subscription":
        now = datetime.utcnow()
        new_until = now + timedelta(days=30)
        if user.subscription_until and user.subscription_until > now:
            user.subscription_until += timedelta(days=30)
        else:
            user.subscription_until = new_until
        user.is_subscribed = True

    elif purchase_type == "credits":
        price_to_credits = {
            0.39: 1,
            1.69: 5,
            4.59: 15,
            7.99: 30,
            14.59: 60,
        }
        amount = float(invoice["paid_amount"])
        credits = price_to_credits.get(round(amount, 2), 0)
        user.credits += credits

    await session.commit()
    return {"status": "ok"}
