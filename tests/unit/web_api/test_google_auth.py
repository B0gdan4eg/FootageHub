from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Response
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from shared.db.models import AuthIdentity, Base, GoogleOAuthState, User
from web_api.auth import google
from web_api.dependencies import get_current_user


@pytest.mark.parametrize(
    "value",
    ["//evil.test", "https://evil.test", "/\\evil", "/api/auth", "/auth", "/%2f%2fevil", "/a\n"],
)
def test_google_return_path_rejects_redirect_attacks(value):
    assert google.safe_path(value) == "/dashboard"


def test_google_id_token_checks_signature_and_claims(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        google.keys, "get_signing_key_from_jwt", lambda _: SimpleNamespace(key=key.public_key())
    )
    monkeypatch.setattr(google.config, "GOOGLE_CLIENT_ID", "test-client")
    claims = {
        "sub": "google-subject",
        "email": "user@example.test",
        "email_verified": True,
        "iss": "https://accounts.google.com",
        "aud": "test-client",
        "nonce": "test-nonce",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=5),
    }
    assert (
        google.validate_id_token(jwt.encode(claims, key, algorithm="RS256"), "test-nonce")["sub"]
        == "google-subject"
    )
    for field, value in [
        ("aud", "other-client"),
        ("iss", "https://evil.test"),
        ("nonce", "other"),
        ("email_verified", False),
        ("exp", datetime.utcnow() - timedelta(seconds=10)),
        ("azp", "other"),
    ]:
        with pytest.raises((ValueError, jwt.InvalidTokenError)):
            google.validate_id_token(
                jwt.encode({**claims, field: value}, key, algorithm="RS256"), "test-nonce"
            )
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(jwt.InvalidSignatureError):
        google.validate_id_token(jwt.encode(claims, other_key, algorithm="RS256"), "test-nonce")


@pytest.mark.asyncio
async def test_cookie_write_requires_trusted_origin():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [(b"cookie", b"fh_session=fake"), (b"origin", b"https://evil.test")],
        }
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None, AsyncMock(), request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_google_disabled_cannot_start(monkeypatch):
    monkeypatch.setattr(google.config, "GOOGLE_AUTH_ENABLED", False)
    with pytest.raises(HTTPException) as exc:
        await google.google_start(
            google.GoogleStart(),
            Request({"type": "http", "headers": []}),
            Response(),
            AsyncMock(),
            None,
        )
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_linking_preserves_user_and_rejects_conflicts():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with sessions() as db:
            db.add_all(
                [User(id=123, tg_id=123, credits=47, ai_credits=9), User(id=456, credits=10)]
            )
            await db.commit()
            claims = {"sub": "stable-sub", "email": "user@example.test"}
            user = await google.attach_identity(db, claims, 123)
            assert (user.id, user.tg_id, user.credits, user.ai_credits) == (123, 123, 47, 9)
            returning = await google.attach_identity(
                db, {**claims, "email": "changed@example.test"}
            )
            assert returning.id == 123
            with pytest.raises(HTTPException) as exc:
                await google.attach_identity(db, claims, 456)
            assert exc.value.status_code == 409
            with pytest.raises(HTTPException):
                await google.attach_identity(
                    db, {"sub": "different-sub", "email": "user@example.test"}, 123
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_callback_binding_expiry_replay_and_secure_cookie(monkeypatch):
    monkeypatch.setattr(google.config, "GOOGLE_AUTH_ENABLED", True)
    monkeypatch.setattr(google.config, "GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(google.config, "GOOGLE_CLIENT_SECRET", "test-secret")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with sessions() as db:
            db.add(
                GoogleOAuthState(
                    state_hash=google.digest("state"),
                    binding_hash=google.digest("binder"),
                    nonce="nonce",
                    verifier="verifier",
                    return_path="/dashboard",
                    expires_at=datetime.utcnow() + timedelta(minutes=5),
                )
            )
            await db.commit()
            request = Request({"type": "http", "headers": [(b"cookie", b"google_binding=wrong")]})
            result = await google.google_callback(request, "state", "code", "", db)
            assert result.headers["location"] == "/auth?google_error=invalid_session"
            request = Request({"type": "http", "headers": [(b"cookie", b"google_binding=binder")]})
            # A cancelled callback is consumed too; replay cannot exchange a code.
            result = await google.google_callback(request, "state", "", "access_denied", db)
            assert result.headers["location"] == "/auth?google_error=cancelled"
            result = await google.google_callback(request, "state", "code", "", db)
            assert result.headers["location"] == "/auth?google_error=invalid_session"
            db.add(
                GoogleOAuthState(
                    state_hash=google.digest("expired"),
                    binding_hash=google.digest("binder"),
                    nonce="nonce",
                    verifier="verifier",
                    return_path="/dashboard",
                    expires_at=datetime.utcnow() - timedelta(seconds=1),
                )
            )
            await db.commit()
            result = await google.google_callback(request, "expired", "code", "", db)
            assert result.headers["location"] == "/auth?google_error=invalid_session"
            db.add(
                GoogleOAuthState(
                    state_hash=google.digest("success"),
                    binding_hash=google.digest("binder"),
                    nonce="nonce",
                    verifier="verifier",
                    return_path="/dashboard",
                    expires_at=datetime.utcnow() + timedelta(minutes=5),
                )
            )
            await db.commit()
            result_mock = Mock()
            result_mock.json.return_value = {"id_token": "test-id-token"}
            result_mock.raise_for_status.return_value = None
            client = AsyncMock()
            client.__aenter__.return_value = client
            client.post.return_value = result_mock
            monkeypatch.setattr(google.httpx, "AsyncClient", lambda **kwargs: client)
            monkeypatch.setattr(
                google,
                "validate_id_token",
                lambda *args: {"sub": "success-sub", "email": "user@example.test"},
            )
            result = await google.google_callback(request, "success", "code", "", db)
            assert result.headers["location"] == "/dashboard"
            session_cookie = next(
                cookie
                for cookie in result.headers.getlist("set-cookie")
                if cookie.startswith("fh_session=")
            )
            assert (
                "HttpOnly" in session_cookie
                and "Secure" in session_cookie
                and "SameSite=lax" in session_cookie
            )
            assert "access_token=" not in result.headers["location"]
            from sqlalchemy import select

            identity = (
                await db.execute(select(AuthIdentity).where(AuthIdentity.subject == "success-sub"))
            ).scalar_one()
            assert identity.user_id <= 2**53 - 1
            result = await google.google_callback(request, "success", "code", "", db)
            assert result.headers["location"] == "/auth?google_error=invalid_session"
    finally:
        await engine.dispose()
