from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from shared.asset_urls import validate_asset_url
from shared.internal_auth import internal_headers, require_internal_auth


@pytest.mark.parametrize(
    "url,provider",
    [
        ("https://elements.envato.com/asset-ABC123", "envato"),
        ("https://www.freepik.com/premium-photo/asset_123.htm", "freepik"),
        ("https://motionarray.com/stock-video/asset-123/", "motion"),
    ],
)
def test_supported_asset_urls(url, provider):
    assert validate_asset_url(url, provider) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://elements.envato.com/a",
        "https://127.0.0.1/a",
        "https://169.254.169.254/latest/meta-data",
        "https://elements.envato.com.evil.example/a",
        "https://user:pass@elements.envato.com/a",
        "https://elements.envato.com:8080/a",
        "https://elements.envato.com/",
        "file:///etc/passwd",
        "https://elements.envato.com\n/a",
    ],
)
def test_server_rejects_private_and_spoofed_asset_urls(url):
    with pytest.raises(ValueError):
        validate_asset_url(url, "envato")


@pytest.mark.asyncio
async def test_internal_route_requires_configured_matching_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "x" * 64)
    for value in ["", "Bearer wrong", "Bearer \u00e9"]:
        request = Request({"type": "http", "headers": [(b"authorization", value.encode("latin1"))]})
        with pytest.raises(HTTPException) as exc:
            await require_internal_auth(request)
        assert exc.value.status_code == 403
    header = internal_headers()["Authorization"]
    await require_internal_auth(
        Request({"type": "http", "headers": [(b"authorization", header.encode())]})
    )
    monkeypatch.delenv("INTERNAL_API_SECRET")
    with pytest.raises(HTTPException) as exc:
        await require_internal_auth(Request({"type": "http", "headers": []}))
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_unsigned_bot_crypto_notification_rejected_before_payment_lookup():
    from media_bot.webhook.cryptobot import webhook

    request = SimpleNamespace(body=AsyncMock(return_value=b"{}"), headers={})
    with pytest.raises(HTTPException) as exc:
        await webhook(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_filter_rechecks_database_role_for_callbacks_and_messages(monkeypatch):
    from media_bot.handlers import admin

    role_check = AsyncMock(return_value=False)
    monkeypatch.setattr(admin, "is_admin", role_check)
    event = SimpleNamespace(from_user=SimpleNamespace(id=123))
    assert not await admin.AdminAccessFilter()(event)
    role_check.return_value = True
    assert await admin.AdminAccessFilter()(event)


def test_webpay_bot_callback_matches_expected_user_plan_and_converted_amount():
    from media_bot.webhook.webpay import validate_payment

    payment = SimpleNamespace(
        user_id=1, plan_key="monthly_50", amount=100, currency="RUB", status="pending"
    )
    validate_payment(payment, 1, "monthly_50", "3.70", "BYN")
    for user_id, plan, amount, currency in [
        (2, "monthly_50", "3.70", "BYN"),
        (1, "monthly_150", "3.70", "BYN"),
        (1, "monthly_50", "0.01", "BYN"),
        (1, "monthly_50", "3.70", "USD"),
    ]:
        with pytest.raises(HTTPException):
            validate_payment(payment, user_id, plan, amount, currency)
