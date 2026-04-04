"""Payments router: plans, invoice creation, webhooks for web users."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Payment, User
from shared.db.repositories.user_repository import UserRepository
from web_api.dependencies import get_current_user, get_db

router = APIRouter()


def _load_plans() -> dict:
    """Загрузить список тарифов из JSON файла (тот же что у бота)."""
    plans_path = Path(__file__).parent.parent.parent / "media_bot" / "prices_list.json"
    if plans_path.exists():
        with open(plans_path, encoding="utf-8") as f:
            return json.load(f)
    # fallback
    return {
        "monthly_50": {"name": "Lite", "price": 9.99, "currency": "USD"},
        "monthly_150": {"name": "Standard", "price": 24.99, "currency": "USD"},
        "monthly_400": {"name": "Pro", "price": 49.99, "currency": "USD"},
    }


class CreateInvoiceRequest(BaseModel):
    plan_key: str
    provider: str  # webpay | cryptobot


@router.get("/plans")
async def get_plans():
    """Получить список доступных тарифов."""
    return _load_plans()


@router.post("/create")
async def create_invoice(
    body: CreateInvoiceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создать инвойс для оплаты (WebPay или CryptoBot)."""
    plans = _load_plans()
    plan = plans.get(body.plan_key)
    if not plan:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    # Формат order_id для web-пользователей
    order_id = f"WEBUSER_{current_user.id}_{body.plan_key}_{uuid.uuid4().hex[:8]}"

    # Сохраняем платёж в БД
    payment = Payment(
        user_id=current_user.id,
        amount=plan.get("price", 0),
        currency=plan.get("currency", "USD"),
        status="pending",
        invoice_id=order_id,
        plan_key=body.plan_key,
    )
    db.add(payment)
    await db.commit()

    if body.provider == "cryptobot":
        invoice_url = await _create_cryptobot_invoice(order_id, plan)
    elif body.provider == "webpay":
        invoice_url = await _create_webpay_invoice(order_id, plan, current_user)
    else:
        raise HTTPException(status_code=400, detail="Неизвестный провайдер оплаты")

    return {"invoice_url": invoice_url, "order_id": order_id}


async def _create_cryptobot_invoice(order_id: str, plan: dict) -> str:
    """Создать инвойс в CryptoBot."""
    import httpx

    from web_api.config import config

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": config.CRYPTO_BOT_API_KEY},
            json={
                "asset": "USDT",
                "amount": str(plan.get("price", 0)),
                "description": f"FootageHub: {plan.get('name', order_id)}",
                "payload": order_id,
                "allow_comments": False,
                "allow_anonymous": True,
            },
        )
        data = resp.json()
        if not data.get("ok"):
            raise HTTPException(status_code=500, detail="Ошибка создания инвойса CryptoBot")
        return data["result"]["pay_url"]


async def _create_webpay_invoice(order_id: str, plan: dict, user: User) -> str:
    """Создать форму оплаты WebPay."""
    import hashlib
    import hmac

    from web_api.config import config

    amount = int(plan.get("price", 0) * 100)  # в копейках
    signing_str = f"{config.WEBPAY_RESOURCE_ID}{order_id}{amount}BYR"
    signature = hmac.new(
        config.WEBPAY_SIGNING_KEY.encode(),
        signing_str.encode(),
        hashlib.sha1,
    ).hexdigest()

    # Возвращаем URL с параметрами (фронтенд делает POST-форму)
    params = {
        "resource_id": config.WEBPAY_RESOURCE_ID,
        "order_id": order_id,
        "amount": amount,
        "currency": "BYR",
        "signature": signature,
    }
    return "https://payment.webpay.by/?" + "&".join(f"{k}={v}" for k, v in params.items())


@router.post("/webhook/cryptobot")
async def cryptobot_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Вебхук от CryptoBot для web-пользователей."""
    data = await request.json()

    if data.get("update_type") != "invoice_paid":
        return {"ok": True}

    payload = data.get("payload", {}).get("payload", "")
    if not payload.startswith("WEBUSER_"):
        return {"ok": True}  # это бот-платёж, пропускаем

    await _process_web_payment(payload, db)
    return {"ok": True}


@router.post("/webhook/webpay")
async def webpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Вебхук от WebPay для web-пользователей."""
    form = await request.form()
    order_id = form.get("order_id", "")

    if not order_id.startswith("WEBUSER_"):
        return {"status": "ok"}

    if form.get("payment_status") == "success":
        await _process_web_payment(order_id, db)

    return {"status": "ok"}


async def _process_web_payment(order_id: str, db: AsyncSession) -> None:
    """Обработать успешный платёж от web-пользователя."""
    from sqlalchemy import select

    # order_id формат: WEBUSER_{db_user_id}_{plan_key}_{uuid}
    parts = order_id.split("_", 3)
    if len(parts) < 3:
        return

    try:
        db_user_id = int(parts[1])
    except ValueError:
        return

    # Обновляем статус платежа
    result = await db.execute(select(Payment).where(Payment.invoice_id == order_id))
    payment = result.scalar_one_or_none()
    if not payment:
        return

    payment.status = "success"

    # Активируем подписку
    from shared.db.repositories.subscription_repository import SubscriptionRepository

    sub_repo = SubscriptionRepository(db)
    user_repo = UserRepository(db)

    user = await user_repo.get_by_id(db_user_id)
    if user:
        await sub_repo.create_subscription_from_plan(user.id, payment.plan_key)

    await db.commit()


@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История платежей текущего пользователя."""
    from sqlalchemy import select

    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(50)
    )
    payments = result.scalars().all()
    return [
        {
            "id": p.id,
            "amount": float(p.amount),
            "currency": p.currency,
            "status": p.status,
            "plan_key": p.plan_key,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments
    ]
