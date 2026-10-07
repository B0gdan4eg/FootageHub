"""Payments router: plans, invoice creation, webhooks for web users."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared import funnel_tracking
from shared.db.models import Payment, User
from shared.db.repositories.subscription_repository import SubscriptionRepository
from web_api.config import config
from web_api.dependencies import get_current_user, get_db
from web_api.payment_validation import (
    positive_amount,
    verify_crypto_signature,
    verify_webpay_signature,
    webpay_amount,
)

router = APIRouter()


def _load_plans() -> dict:
    """Загрузить список тарифов из JSON файла (тот же что у бота)."""
    plans_path = Path(__file__).parent.parent.parent / "media_bot" / "handlers" / "prices_list.json"
    if plans_path.exists():
        with open(plans_path, encoding="utf-8") as f:
            data = json.load(f)
            plans = data.get("subscription_plans", data)
            for plan in plans.values():
                plan.setdefault("currency", "RUB")
            return plans
    # fallback
    return {
        "monthly_50": {"name": "Lite", "price": 9.99, "currency": "USD"},
        "monthly_150": {"name": "Standard", "price": 24.99, "currency": "USD"},
        "monthly_400": {"name": "Pro", "price": 49.99, "currency": "USD"},
    }


class CreateInvoiceRequest(BaseModel):
    plan_key: str
    provider: Literal["webpay", "cryptobot"]
    analytics_id: UUID | None = None


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

    positive_amount(plan.get("price", 0))
    # Формат order_id для web-пользователей
    order_id = f"WEBUSER_{current_user.id}_{body.plan_key}_{body.provider}_{uuid.uuid4().hex[:16]}"
    if body.analytics_id is not None:
        # Keep attributed orders below WebPay's 64-character merchant order limit.
        # User, plan and provider are already stored in the Payment row.
        order_id = (
            "WEBUSER_"
            + uuid.uuid4().hex[:16]
            + funnel_tracking.attribution_suffix(body.analytics_id)
        )

    # Сохраняем платёж в БД
    payment = Payment(
        user_id=current_user.id,
        amount=webpay_amount(plan["price"])
        if body.provider == "webpay"
        else positive_amount(plan["price"]),
        currency="BYN" if body.provider == "webpay" else "USDT",
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
    """Создать invoice в WebPay через тот же JSON API, что использует Telegram-бот."""
    from media_bot.webpay_utils import get_webpay_api

    base_url = "https://envato-freepik-download.store"
    webpay_api = get_webpay_api()
    result = await webpay_api.create_invoice(
        order_id=order_id,
        amount=float(plan.get("price", 0)),
        description=f"FootageHub: {plan.get('name', order_id)}",
        return_url=f"{base_url}/dashboard?payment=success",
        cancel_url=f"{base_url}/payment?payment=cancel",
        notify_url=f"{base_url}/api/payments/webhook/webpay",
    )
    invoice_url = result.get("invoiceUrl")
    if not invoice_url:
        raise HTTPException(status_code=500, detail="Ошибка создания инвойса WebPay")
    return invoice_url


@router.post("/webhook/cryptobot")
async def cryptobot_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    if not verify_crypto_signature(
        body, request.headers.get("crypto-pay-api-signature", ""), config.CRYPTO_BOT_API_KEY
    ):
        raise HTTPException(status_code=403, detail="Invalid payment signature")
    try:
        data = json.loads(body)
        sent = datetime.fromisoformat(data["request_date"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if sent.tzinfo is None or not now - timedelta(days=3, minutes=5) <= sent <= now + timedelta(
            minutes=5
        ):
            raise ValueError("Invalid callback date")
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid payment notification")
    if data.get("update_type") != "invoice_paid":
        return {"ok": True}
    invoice = data.get("payload", {})
    if not isinstance(invoice, dict):
        raise HTTPException(status_code=400, detail="Invalid invoice")
    order_id = invoice.get("payload", "")
    if not isinstance(order_id, str) or not order_id.startswith("WEBUSER_"):
        return {"ok": True}
    if invoice.get("status") != "paid" or invoice.get("asset") != "USDT":
        raise HTTPException(status_code=400, detail="Invalid paid invoice")
    await _process_web_payment(order_id, db, "cryptobot", invoice.get("amount"), "USDT")
    return {"ok": True}


@router.post("/webhook/webpay")
async def webpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    if any(len(form.getlist(key)) != 1 for key in form):
        raise HTTPException(status_code=400, detail="Duplicate payment fields")
    params = dict(form)
    if any(not isinstance(value, str) for value in params.values()):
        raise HTTPException(status_code=400, detail="Invalid payment fields")
    if not verify_webpay_signature(params, config.WEBPAY_SIGNING_KEY):
        raise HTTPException(status_code=403, detail="Invalid payment signature")
    order_id = params.get("site_order_id", "")
    if not order_id.startswith("WEBUSER_"):
        return {"status": "ok"}
    if params.get("payment_type") in {"1", "4"}:
        if params.get("payment_method") == "test" and not config.WEBPAY_SANDBOX:
            raise HTTPException(status_code=400, detail="Test payment rejected")
        await _process_web_payment(
            order_id, db, "webpay", params.get("amount"), params.get("currency_id", "")
        )
    return {"status": "ok"}


async def _process_web_payment(
    order_id: str, db: AsyncSession, provider: str, amount, currency: str
) -> None:
    # Lock the payment until activation and status update commit together.
    result = await db.execute(
        select(Payment).where(Payment.invoice_id == order_id).with_for_update()
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    expected_currency = "BYN" if provider == "webpay" else "USDT"
    if payment.currency in {"BYN", "USDT"}:
        if payment.currency != expected_currency:
            raise HTTPException(status_code=400, detail="Payment provider mismatch")
        expected_amount = payment.amount
    else:
        # Legacy invoices stored plan prices rather than the charged currency.
        expected_amount = webpay_amount(payment.amount) if provider == "webpay" else payment.amount
    try:
        valid_amount = positive_amount(amount) == positive_amount(expected_amount)
    except ValueError:
        valid_amount = False
    if currency != expected_currency or not valid_amount:
        raise HTTPException(status_code=400, detail="Payment amount or currency mismatch")
    if payment.status == "success":
        return  # Signed provider retries must not activate or credit twice.
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail="Payment is not pending")
    result = await db.execute(select(User).where(User.id == payment.user_id).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Payment user not found")
    try:
        await SubscriptionRepository(db).create_subscription_from_plan(
            user.id, payment.plan_key, payment.id, commit=False
        )
        payment.status = "success"
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    funnel_tracking.payment_completed(order_id, payment.plan_key, provider)


@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История платежей текущего пользователя."""
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
