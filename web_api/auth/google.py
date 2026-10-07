"""Google authorization-code login and explicit attachment to an authenticated user."""
import asyncio
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import AuthIdentity, GoogleOAuthState, User
from web_api.auth.jwt_handler import create_access_token, decode_token
from web_api.config import config
from web_api.dependencies import bearer_scheme, get_current_user, get_db

router = APIRouter()
keys = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=5)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def safe_path(value):
    if (
        not isinstance(value, str)
        or len(value) > 1024
        or not value.startswith("/")
        or value.startswith("//")
        or any(ord(c) < 32 for c in value)
        or "\\" in value
        or "%" in value
    ):
        return "/dashboard"
    path = urlsplit(value)
    if path.scheme or path.netloc or path.path.startswith(("/api", "/auth")):
        return "/dashboard"
    return value


def require_enabled():
    if (
        not config.GOOGLE_AUTH_ENABLED
        or not config.GOOGLE_CLIENT_ID
        or not config.GOOGLE_CLIENT_SECRET
    ):
        raise HTTPException(status_code=503, detail="Google sign-in is not enabled")


def check_origin(request):
    if request.headers.get("origin") not in config.CORS_ORIGINS:
        raise HTTPException(status_code=403, detail="Invalid request origin")


@router.get("/google/config")
async def google_config():
    return {
        "enabled": bool(
            config.GOOGLE_AUTH_ENABLED and config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET
        )
    }


class GoogleStart(BaseModel):
    connect: bool = False
    return_path: str = "/dashboard"


@router.post("/google/start")
async def google_start(
    body: GoogleStart,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    require_enabled()
    check_origin(request)
    user = await get_current_user(credentials, db, request) if body.connect else None
    if user and user.tg_id is None:
        raise HTTPException(
            status_code=400, detail="Sign in with Telegram before connecting Google"
        )
    state, binding, nonce, verifier = [secrets.token_urlsafe(32) for _ in range(4)]
    await db.execute(
        delete(GoogleOAuthState).where(GoogleOAuthState.expires_at < datetime.utcnow())
    )
    db.add(
        GoogleOAuthState(
            state_hash=digest(state),
            binding_hash=digest(binding),
            nonce=nonce,
            verifier=verifier,
            user_id=user.id if user else None,
            return_path=safe_path(body.return_path),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
    )
    await db.commit()
    response.set_cookie(
        "google_binding",
        binding,
        max_age=600,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api/auth/google",
    )
    response.headers["Cache-Control"] = "no-store"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": config.GOOGLE_CLIENT_ID,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode(),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    return {"url": url}


def validate_id_token(encoded, nonce):
    key = keys.get_signing_key_from_jwt(encoded).key
    claims = jwt.decode(
        encoded,
        key,
        algorithms=["RS256"],
        audience=config.GOOGLE_CLIENT_ID,
        issuer=["accounts.google.com", "https://accounts.google.com"],
        options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
    )
    if not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(claims["nonce"], nonce):
        raise ValueError("Invalid nonce")
    if (
        claims.get("email_verified") is not True
        or not isinstance(claims.get("email"), str)
        or len(claims["email"]) > 320
        or not isinstance(claims["sub"], str)
        or not 0 < len(claims["sub"]) <= 255
    ):
        raise ValueError("Invalid Google identity")
    if claims.get("azp", config.GOOGLE_CLIENT_ID) != config.GOOGLE_CLIENT_ID:
        raise ValueError("Invalid authorized party")
    return claims


async def attach_identity(db, claims, user_id=None):
    existing = (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == "google", AuthIdentity.subject == claims["sub"]
            )
        )
    ).scalar_one_or_none()
    if existing:
        if user_id is not None and existing.user_id != user_id:
            raise HTTPException(
                status_code=409, detail="Google identity already belongs to another account"
            )
        return await db.get(User, existing.user_id)
    if user_id is not None:
        user = (
            await db.execute(select(User).where(User.id == user_id).with_for_update())
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Account no longer exists")
        if (
            await db.execute(
                select(AuthIdentity.id).where(
                    AuthIdentity.user_id == user_id, AuthIdentity.provider == "google"
                )
            )
        ).scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A Google identity is already connected")
    else:
        # Above Telegram IDs, while remaining exact in browser JavaScript numbers.
        user = User(id=secrets.randbelow(2**52) + 2**52, credits=3)
        db.add(user)
        await db.flush()
    db.add(
        AuthIdentity(
            user_id=user.id, provider="google", subject=claims["sub"], email=claims["email"]
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (
            await db.execute(
                select(AuthIdentity).where(
                    AuthIdentity.provider == "google", AuthIdentity.subject == claims["sub"]
                )
            )
        ).scalar_one_or_none()
        if not existing or (user_id is not None and existing.user_id != user_id):
            raise HTTPException(status_code=409, detail="Google identity conflict")
        user = await db.get(User, existing.user_id)
    return user


def finish_redirect(path):
    response = RedirectResponse(path, status_code=303)
    response.delete_cookie(
        "google_binding", path="/api/auth/google", secure=True, httponly=True, samesite="lax"
    )
    response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    state: str = "",
    code: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
):
    require_enabled()
    pending = (
        await db.execute(
            select(GoogleOAuthState)
            .where(GoogleOAuthState.state_hash == digest(state))
            .with_for_update()
        )
    ).scalar_one_or_none()
    binding = request.cookies.get("google_binding", "")
    if (
        not pending
        or pending.expires_at < datetime.utcnow()
        or not binding
        or not hmac.compare_digest(pending.binding_hash, digest(binding))
    ):
        return finish_redirect("/auth?google_error=invalid_session")
    nonce, verifier, user_id, return_path = (
        pending.nonce,
        pending.verifier,
        pending.user_id,
        pending.return_path,
    )
    await db.delete(pending)
    await db.commit()
    if user_id is not None:
        try:
            active_user = decode_token(
                request.cookies.get("access_token") or request.cookies.get("fh_session") or ""
            )
        except Exception:
            active_user = None
        if active_user != user_id:
            return finish_redirect("/auth?google_error=invalid_session")
    if error or not code or len(code) > 4096:
        return finish_redirect(
            "/dashboard?google_error=cancelled" if user_id else "/auth?google_error=cancelled"
        )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            result = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": config.GOOGLE_REDIRECT_URI,
                    "code_verifier": verifier,
                },
            )
            result.raise_for_status()
        claims = await asyncio.to_thread(validate_id_token, result.json()["id_token"], nonce)
        user = await attach_identity(db, claims, user_id)
    except HTTPException:
        await db.rollback()
        return finish_redirect(
            "/dashboard?google_error=conflict" if user_id else "/auth?google_error=conflict"
        )
    except Exception:
        await db.rollback()
        return finish_redirect(
            "/dashboard?google_error=failed" if user_id else "/auth?google_error=failed"
        )
    response = finish_redirect(return_path)
    response.delete_cookie("access_token", path="/")
    response.set_cookie(
        "fh_session",
        create_access_token(user.id),
        max_age=604800,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie("auth_session", "1", max_age=604800, secure=True, samesite="lax", path="/")
    if user_id is None:
        response.set_cookie(
            "google_login_done", "1", max_age=300, secure=True, samesite="lax", path="/"
        )
    return response


@router.get("/google/identity")
async def google_identity(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    identity = (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user.id, AuthIdentity.provider == "google"
            )
        )
    ).scalar_one_or_none()
    return {"connected": bool(identity), "email": identity.email if identity else None}


@router.post("/logout")
async def logout(request: Request):
    check_origin(request)
    response = Response(status_code=204)
    for cookie in ("fh_session", "auth_session", "access_token", "google_login_done"):
        response.delete_cookie(cookie, path="/")
    return response
