from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_session  # твой dependency
from db.models import User, Payment
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
import os

CRYPTO_BOT_API_KEY = os.getenv("CRYPTO_BOT_API_KEY")  # или захардкожен

router = APIRouter()

@router.post("/webhook/cryptobot")
async def handle_crypto_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.body()
    headers = request.headers

    # Проверка подписи (если задана)
    if CRYPTO_BOT_API_KEY:
        signature = headers.get("X-CryptoPay-Signature")
        expected_sig = hmac.new(
            CRYPTO_BOT_API_KEY.encode(), body, hashlib.sha256
        ).hexdigest()
        if signature != expected_sig:
            return {"status": "invalid signature"}

    data = json.loads(body)

    if data.get("status") != "paid":
        return {"status": "ignored (not paid)"}

    # Разбор payload
    try:
        payload = data.get("payload", "")
        user_id_str, purchase_type = payload.split(":")
        user_id = int(user_id_str)
    except Exception:
        return {"status": "invalid payload"}

    # Поиск пользователя
    user = await session.get(User, user_id)
    if not user:
        return {"status": "user not found"}

    # Сохранение платежа
    payment = Payment(
        user_id=user.id,
        amount=Decimal(data["amount"]),
        currency=data["asset"],
        type=purchase_type,
        status="success",
        invoice_id=str(data["invoice_id"]),
    )
    session.add(payment)

    # Назначение подписки или кредитов
    if purchase_type == "subscription":
        # Например, подписка на 30 дней
        now = datetime.utcnow()
        new_until = now + timedelta(days=30)
        if user.subscription_until and user.subscription_until > now:
            user.subscription_until += timedelta(days=30)
        else:
            user.subscription_until = new_until
        user.is_subscribed = True

    elif purchase_type == "credits":
        # Добавь кредиты на основе цены
        # Примерно так:
        price_to_credits = {
            0.39: 1,
            1.69: 5,
            4.59: 15,
            7.99: 30,
            14.59: 60,
        }
        amount = float(data["amount"])
        credits = price_to_credits.get(round(amount, 2), 0)
        user.credits += credits

    await session.commit()
    return {"status": "ok"}