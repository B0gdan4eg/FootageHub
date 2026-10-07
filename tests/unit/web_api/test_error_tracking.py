import asyncio
import json
from unittest.mock import Mock

import pytest

from shared import error_tracking as tracking


def test_exception_redaction_strips_credentials_and_personal_data(monkeypatch):
    monkeypatch.setattr(tracking, "_service", "web-api")
    event = {
        "event": "$exception",
        "distinct_id": "private-phone",
        "properties": {
            "headers": {"authorization": "SECRET"},
            "request_body": "SECRET",
            "$session_id": "SECRET",
            "$exception_list": [
                {
                    "type": "ValueError",
                    "value": "SECRET",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "/private/username/app.py",
                                "abs_path": "/private/username/app.py",
                                "function": "handler",
                                "lineno": 10,
                                "vars": {"token": "SECRET"},
                                "context_line": "password='SECRET'",
                                "pre_context": ["SECRET"],
                                "post_context": ["SECRET"],
                            }
                        ]
                    },
                }
            ],
            "service": "web-api",
            "release": "a" * 40,
        },
    }
    safe = tracking.sanitize_event(event)
    text = json.dumps(safe)
    assert "SECRET" not in text and "private" not in text
    assert safe["distinct_id"] == "service:web-api"
    assert safe["properties"]["$exception_list"][0]["stacktrace"]["frames"][0]["lineno"] == 10
    assert tracking.sanitize_event({"event": "other"}) is None


def test_repeated_errors_are_bounded_and_client_failure_does_not_break_app(monkeypatch):
    client = Mock()
    monkeypatch.setattr(tracking, "_client", client)
    monkeypatch.setattr(tracking, "_limits", {})
    for _ in range(20):
        tracking.report_exception(ValueError("SECRET"))
    assert client.capture_exception.call_count == 5
    client.capture_exception.side_effect = RuntimeError("offline")
    tracking.report_exception(TypeError("SECRET"))
    tracking.report_exception(asyncio.CancelledError())
    assert client.capture_exception.call_count == 6


@pytest.mark.asyncio
async def test_telegram_middleware_tracks_and_preserves_failure(monkeypatch):
    capture = Mock()
    monkeypatch.setattr(tracking, "report_exception", capture)

    async def handler(event, data):
        raise RuntimeError("failed")

    with pytest.raises(RuntimeError):
        await tracking.TrackingMiddleware()(handler, None, {})
    capture.assert_called_once()
