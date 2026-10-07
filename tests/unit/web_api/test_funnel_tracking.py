from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest

from shared import funnel_tracking as tracking
from web_api.routers import payments

ANONYMOUS = "019a31f2-1234-7000-8000-123456789abc"
ORDER = "WEBUSER_123_monthly_50_webpay_0123456789abcdef" + tracking.attribution_suffix(ANONYMOUS)


def test_attribution_is_optional_and_not_an_account_identifier():
    assert tracking.attribution_suffix(None) == ""
    assert tracking.attribution_suffix(ANONYMOUS) == "_PH_" + UUID(ANONYMOUS).hex
    with pytest.raises(ValueError):
        tracking.attribution_suffix("phone-or-token")


def test_outbound_payment_event_strips_private_properties():
    event = tracking.sanitize_event(
        {
            "event": "payment_completed",
            "distinct_id": ANONYMOUS,
            "properties": {
                "plan": "monthly_50",
                "provider": "webpay",
                "order_id": ORDER,
                "user_id": 123,
                "phone": "PRIVATE",
            },
            "request": "PRIVATE",
        }
    )
    assert event["distinct_id"] == ANONYMOUS
    assert "PRIVATE" not in str(event) and ORDER not in str(event)
    assert tracking.sanitize_event({"event": "unexpected"}) is None


def test_capture_is_anonymous_stable_and_optional(monkeypatch):
    client = Mock()
    monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "phc_test")
    monkeypatch.setattr(tracking, "_client", client)
    tracking.payment_completed(ORDER, "monthly_50", "webpay")
    first = client.capture.call_args
    tracking.payment_completed(ORDER, "monthly_50", "webpay")
    assert client.capture.call_args == first
    assert first.kwargs["distinct_id"] == ANONYMOUS
    tracking.payment_completed("WEBUSER_legacy", "monthly_50", "webpay")
    assert client.capture.call_count == 2
    client.capture.side_effect = RuntimeError("tracking unavailable")
    tracking.payment_completed(ORDER, "monthly_50", "webpay")


@pytest.mark.asyncio
async def test_completion_emitted_only_after_commit_and_never_on_duplicate():
    payment = SimpleNamespace(
        id=1, user_id=2, plan_key="monthly_50", status="pending", currency="BYN", amount=10
    )
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: payment),
        SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=2)),
    ]
    capture = Mock(side_effect=lambda *args: db.commit.assert_awaited_once())
    with patch.object(tracking, "payment_completed", capture), patch.object(
        payments.SubscriptionRepository, "create_subscription_from_plan", AsyncMock()
    ):
        await payments._process_web_payment(ORDER, db, "webpay", "10", "BYN")
        capture.assert_called_once_with(ORDER, "monthly_50", "webpay")
        db.execute.side_effect = [SimpleNamespace(scalar_one_or_none=lambda: payment)]
        await payments._process_web_payment(ORDER, db, "webpay", "10", "BYN")
        assert capture.call_count == 1
