"""Service-only exception telemetry with a strict outbound data allowlist."""
import asyncio
import logging
import os
import re
import threading
import time
from pathlib import Path

from aiogram import BaseMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

_client = None
_service = "unknown"
_limits = {}
_lock = threading.Lock()


def sanitize_event(event):
    """Keep stack locations; discard messages, source context, locals and identities."""
    if event.get("event") != "$exception":
        return None
    incoming = event.get("properties", {})
    exceptions = []
    for item in incoming.get("$exception_list", [])[:5]:
        frames = []
        for frame in item.get("stacktrace", {}).get("frames", [])[-50:]:
            frames.append(
                {
                    key: frame[key]
                    for key in ["function", "module", "lineno", "in_app", "platform"]
                    if key in frame
                }
            )
            frames[-1]["filename"] = Path(frame.get("filename", "unknown")).name
        kind = str(item.get("type", "Exception"))[:100]
        exceptions.append(
            {"type": kind, "value": kind, "stacktrace": {"type": "raw", "frames": frames}}
        )
    properties = {
        "$exception_list": exceptions,
        "$process_person_profile": False,
        "$geoip_disable": True,
        "$is_server": True,
    }
    for key in ["service", "environment", "release", "$lib", "$lib_version", "$python_version"]:
        if key in incoming:
            properties[key] = incoming[key]
    return {
        key: value
        for key, value in {
            **event,
            "distinct_id": "service:" + _service,
            "properties": properties,
        }.items()
        if key in {"event", "uuid", "timestamp", "distinct_id", "properties"}
    }


def configure(service):
    global _client, _service
    _service = service
    if _client is not None:
        return _client
    token = os.getenv("POSTHOG_PROJECT_TOKEN", "")
    if os.getenv("POSTHOG_ERROR_TRACKING_ENABLED", "1") != "1" or not re.fullmatch(
        r"phc_[A-Za-z0-9_-]+", token
    ):
        return None
    host = os.getenv("POSTHOG_HOST", "https://eu.i.posthog.com")
    if host != "https://eu.i.posthog.com":
        raise ValueError("Server error tracking requires the configured PostHog EU host")
    from posthog import Posthog

    revision = os.getenv("APP_REVISION", "")
    revision = revision if re.fullmatch(r"[0-9a-f]{40}", revision) else "unknown"
    _client = Posthog(
        token,
        host=host,
        before_send=sanitize_event,
        privacy_mode=True,
        capture_exception_code_variables=False,
        enable_exception_autocapture=True,
        enable_exception_autocapture_rate_limiting=True,
        exception_autocapture_bucket_size=5,
        exception_autocapture_refill_rate=5,
        exception_autocapture_refill_interval_seconds=60,
        super_properties={"service": service, "environment": "production", "release": revision},
        enable_local_evaluation=False,
        max_queue_size=100,
        max_retries=1,
        timeout=3,
        flush_at=10,
        flush_interval=5,
    )
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()

    def on_async_error(current_loop, context):
        exception = context.get("exception")
        if exception:
            report_exception(exception)
        if previous:
            previous(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(on_async_error)
    return _client


def report_exception(exception):
    if _client is None or isinstance(
        exception, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)
    ):
        return
    kind = type(exception).__name__
    now = time.monotonic()
    with _lock:
        recent = _limits.get(kind, [])
        recent = [stamp for stamp in recent if now - stamp < 60]
        if len(recent) >= 5:
            return
        if len(_limits) >= 100 and kind not in _limits:
            return
        _limits[kind] = recent + [now]
    revision = os.getenv("APP_REVISION", "")
    revision = revision if re.fullmatch(r"[0-9a-f]{40}", revision) else "unknown"
    try:
        _client.capture_exception(
            exception,
            distinct_id="service:" + _service,
            properties={"service": _service, "environment": "production", "release": revision},
        )
    except Exception:
        logging.getLogger(__name__).warning("Error tracking could not enqueue an exception")


async def shutdown():
    global _client
    if _client is not None:
        client, _client = _client, None
        await asyncio.to_thread(client.shutdown)


class TrackingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as exc:
            report_exception(exc)
            raise


class TrackingHTTPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            report_exception(exc)
            raise
