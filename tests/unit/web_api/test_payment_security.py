import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from web_api.config import config, validate_security_config
from web_api.payment_validation import (
    positive_amount,
    verify_crypto_signature,
    verify_webpay_signature,
)
from web_api.routers import payments


def test_crypto_signature_authenticates_exact_body():
    body = b'{"update_type":"invoice_paid"}'
    key = hashlib.sha256(b"test-token").digest()
    signature = hmac.new(key, body, hashlib.sha256).hexdigest()
    assert verify_crypto_signature(body, signature, "test-token")
    assert not verify_crypto_signature(body + b" ", signature, "test-token")
    assert not verify_crypto_signature(body, signature, "")
    assert not verify_crypto_signature(body, "garbage", "test-token")


def test_webpay_signature_and_card_are_authenticated():
    params = dict(
        batch_timestamp="1",
        currency_id="BYN",
        amount="1.00",
        payment_method="cc",
        order_id="123",
        site_order_id="WEBUSER_1_plan",
        transaction_id="456",
        payment_type="1",
        rrn="",
        card="1234xxxx5678",
    )
    text = "".join(params.values()) + "test-secret"
    params["wsb_signature"] = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    assert verify_webpay_signature(params, "test-secret")
    params["amount"] = "10.00"
    assert not verify_webpay_signature(params, "test-secret")
    assert not verify_webpay_signature(params, "")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "text", None])
def test_invalid_amounts_are_rejected(value):
    with pytest.raises(ValueError):
        positive_amount(value)


@pytest.mark.parametrize("key", ["", "short", "change-me-in-production", " " * 40])
def test_unsafe_jwt_configuration_fails(key, monkeypatch):
    monkeypatch.setattr(config, "JWT_SECRET_KEY", key)
    with pytest.raises(RuntimeError):
        validate_security_config()


def test_strong_jwt_configuration_passes(monkeypatch):
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "safe-test-key-" * 4)
    validate_security_config()


def request(body, headers=None):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {"type": "http", "method": "POST", "path": "/", "headers": headers or []}, receive
    )


@pytest.mark.asyncio
async def test_unsigned_callback_cannot_access_database():
    db = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await payments.cryptobot_webhook(request(b"{}"), db)
    assert error.value.status_code == 403
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_signed_crypto_callback_and_stale_timestamp(monkeypatch):
    monkeypatch.setattr(config, "CRYPTO_BOT_API_KEY", "test-token")
    data = {
        "update_type": "invoice_paid",
        "request_date": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "payload": "WEBUSER_1_monthly_50_cryptobot_test",
            "status": "paid",
            "asset": "USDT",
            "amount": "10",
        },
    }

    async def submit():
        body = json.dumps(data).encode()
        signature = hmac.new(
            hashlib.sha256(b"test-token").digest(), body, hashlib.sha256
        ).hexdigest()
        return await payments.cryptobot_webhook(
            request(body, [(b"crypto-pay-api-signature", signature.encode())]), AsyncMock()
        )

    with patch.object(payments, "_process_web_payment", new_callable=AsyncMock) as process:
        assert await submit() == {"ok": True}
        process.assert_awaited_once()
        data["request_date"] = "2000-01-01T00:00:00Z"
        with pytest.raises(HTTPException) as error:
            await submit()
        assert error.value.status_code == 400
        assert process.await_count == 1


def session(payment, user=None):
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: payment),
        SimpleNamespace(scalar_one_or_none=lambda: user),
    ]
    return db


@pytest.mark.asyncio
async def test_duplicate_payment_never_credits_twice():
    payment = SimpleNamespace(status="success", currency="USDT", amount=Decimal("10"))
    db = session(payment)
    with patch.object(
        payments.SubscriptionRepository, "create_subscription_from_plan", new_callable=AsyncMock
    ) as activate:
        await payments._process_web_payment("WEBUSER_test", db, "cryptobot", "10", "USDT")
        activate.assert_not_awaited()
        db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_amount_and_provider_cannot_activate():
    payment = SimpleNamespace(status="pending", currency="BYN", amount=Decimal("10"))
    for provider, amount, currency in [("webpay", "1", "BYN"), ("cryptobot", "10", "USDT")]:
        db = session(payment)
        with pytest.raises(HTTPException):
            await payments._process_web_payment("WEBUSER_test", db, provider, amount, currency)
        db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_activation_and_payment_status_share_one_commit():
    payment = SimpleNamespace(
        id=1,
        user_id=2,
        plan_key="monthly_50",
        status="pending",
        currency="USDT",
        amount=Decimal("10"),
    )
    user = SimpleNamespace(id=2)
    db = session(payment, user)
    with patch.object(
        payments.SubscriptionRepository, "create_subscription_from_plan", new_callable=AsyncMock
    ) as activate:
        await payments._process_web_payment("WEBUSER_test", db, "cryptobot", "10", "USDT")
        activate.assert_awaited_once_with(2, "monthly_50", 1, commit=False)
        assert payment.status == "success"
        db.commit.assert_awaited_once()
        for call in db.execute.await_args_list:
            assert "FOR UPDATE" in str(call.args[0])


@pytest.mark.asyncio
async def test_failed_activation_rolls_back_payment():
    payment = SimpleNamespace(
        id=1,
        user_id=2,
        plan_key="monthly_50",
        status="pending",
        currency="USDT",
        amount=Decimal("10"),
    )
    db = session(payment, SimpleNamespace(id=2))
    with patch.object(
        payments.SubscriptionRepository,
        "create_subscription_from_plan",
        new_callable=AsyncMock,
        side_effect=RuntimeError("failed"),
    ):
        with pytest.raises(RuntimeError):
            await payments._process_web_payment("WEBUSER_test", db, "cryptobot", "10", "USDT")
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    assert payment.status == "pending"
