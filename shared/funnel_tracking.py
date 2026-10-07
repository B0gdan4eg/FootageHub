"""Consent-at-checkout anonymous attribution for verified web payment completion."""
import os
import re
from uuid import NAMESPACE_URL, UUID, uuid5

_client = None
_plans = {"monthly_50", "monthly_150", "monthly_400", "daily_30", "unlimited"}


def attribution_suffix(analytics_id):
    if analytics_id is None:
        return ""
    return "_PH_" + UUID(str(analytics_id)).hex


def sanitize_event(event):
    if event.get("event") != "payment_completed":
        return None
    try:
        anonymous_id = str(UUID(str(event["distinct_id"])))
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    incoming = event.get("properties", {})
    if incoming.get("provider") not in {"webpay", "cryptobot"}:
        return None
    properties = {
        "provider": incoming["provider"],
        "plan": incoming.get("plan") if incoming.get("plan") in _plans else "other",
        "service": "web-api",
        "$process_person_profile": False,
        "$geoip_disable": True,
    }
    return {
        **{k: event[k] for k in ("event", "uuid", "timestamp") if k in event},
        "distinct_id": anonymous_id,
        "properties": properties,
    }


def payment_completed(order_id, plan, provider):
    """Called only after the verified payment transaction commits. Never fails payment."""
    global _client
    match = re.search(r"_PH_([0-9a-f]{32})$", order_id)
    if not match:
        return
    token = os.getenv("POSTHOG_PROJECT_TOKEN", "")
    if not re.fullmatch(r"phc_[A-Za-z0-9_-]+", token):
        return
    try:
        if _client is None:
            from posthog import Posthog

            _client = Posthog(
                token,
                host="https://eu.i.posthog.com",
                before_send=sanitize_event,
                enable_exception_autocapture=False,
                enable_local_evaluation=False,
                max_queue_size=100,
                max_retries=1,
                timeout=3,
                flush_at=1,
            )
        _client.capture(
            "payment_completed",
            distinct_id=str(UUID(match[1])),
            uuid=str(uuid5(NAMESPACE_URL, "footagehub:payment:" + order_id)),
            properties={"plan": plan, "provider": provider},
        )
    except Exception:
        pass  # Telemetry is best effort; money and subscription state are already committed.


async def shutdown():
    if _client is not None:
        import asyncio

        await asyncio.to_thread(_client.shutdown)
