"""Authentication router: phone + SMS + Telegram Login Widget + JWT + bot account linking."""

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import BotLinkRequest, QrLoginSession, User
from shared.db.repositories.user_repository import UserRepository
from web_api.auth.jwt_handler import create_access_token
from web_api.auth.sms_client import send_verification_sms, verify_sms_code
from web_api.config import config
from web_api.dependencies import get_current_user, get_db

router = APIRouter()

PHONE_RE = re.compile(r"^\+7\d{10}$")


def _normalize_phone(phone: str) -> str:
    """Normalize phone to +7XXXXXXXXXX format."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return "+" + digits
    raise ValueError("Неверный формат номера телефона. Используйте +7XXXXXXXXXX")


# ─── Schemas ─────────────────────────────────────────────────────────────────


class SendCodeRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return _normalize_phone(v)
        except ValueError as e:
            raise ValueError(str(e)) from e


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return _normalize_phone(v)
        except ValueError as e:
            raise ValueError(str(e)) from e


class LinkBotRequest(BaseModel):
    referral_code: str


class UserResponse(BaseModel):
    id: int
    phone_number: str | None
    username: str | None
    credits: int
    ai_credits: int
    role: str
    referral_code: str | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


def _build_user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        phone_number=user.phone_number,
        username=user.username,
        credits=user.credits,
        ai_credits=user.ai_credits,
        role=user.role.value,
        referral_code=user.referral_code,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/send-code")
async def send_code(body: SendCodeRequest, db: AsyncSession = Depends(get_db)):
    """Отправить SMS-код подтверждения на телефон."""
    try:
        result = await send_verification_sms(db, body.phone)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    return result


@router.post("/verify-code", response_model=TokenResponse)
async def verify_code(body: VerifyCodeRequest, db: AsyncSession = Depends(get_db)):
    """Проверить SMS-код и выдать JWT. Создать аккаунт если нет."""
    valid = await verify_sms_code(db, body.phone, body.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или устаревший код",
        )

    repo = UserRepository(db)
    user, _ = await repo.get_or_create_by_phone(body.phone)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_build_user_response(user))


@router.post("/link-bot")
async def link_bot_account(
    body: LinkBotRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Запросить привязку существующего бот-аккаунта.

    Поток:
    1. Web-пользователь вводит реф-код своего аккаунта из бота
    2. API создаёт BotLinkRequest и отправляет сообщение в Telegram боте
    3. Бот-пользователь подтверждает в боте
    4. Web-пользователь опрашивает /link-status/{request_id}
    """
    repo = UserRepository(db)
    bot_user = await repo.get_by_referral_code(body.referral_code)

    if not bot_user:
        raise HTTPException(status_code=404, detail="Реферальный код не найден")

    if bot_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя привязать аккаунт к самому себе")

    if bot_user.phone_number is not None:
        raise HTTPException(
            status_code=400,
            detail="Этот аккаунт уже привязан к номеру телефона",
        )

    if bot_user.tg_id is None:
        raise HTTPException(
            status_code=400,
            detail="Аккаунт по этому реф-коду не является аккаунтом бота",
        )

    # Проверяем, нет ли активного запроса
    existing = await db.execute(
        select(BotLinkRequest).where(
            and_(
                BotLinkRequest.web_user_id == current_user.id,
                BotLinkRequest.status == "PENDING",
                BotLinkRequest.expires_at > datetime.utcnow(),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Уже есть активный запрос привязки")

    expires_at = datetime.utcnow() + timedelta(minutes=config.LINK_REQUEST_TTL_MINUTES)
    link_request = BotLinkRequest(
        web_user_id=current_user.id,
        bot_user_id=bot_user.id,
        status="PENDING",
        expires_at=expires_at,
    )
    db.add(link_request)
    await db.commit()
    await db.refresh(link_request)

    # Отправляем сообщение пользователю в Telegram
    if config.BOT_TOKEN and bot_user.tg_id:
        text = (
            "🔗 Кто-то хочет привязать ваш аккаунт FootageHub к веб-сайту.\n\n"
            "Если это вы — нажмите <b>Подтвердить</b>. Если нет — нажмите <b>Отклонить</b>.\n\n"
            "Запрос действителен 10 минут."
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Подтвердить",
                        "callback_data": f"link_confirm:{link_request.id}",
                    },
                    {
                        "text": "❌ Отклонить",
                        "callback_data": f"link_reject:{link_request.id}",
                    },
                ]
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": bot_user.tg_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": keyboard,
                    },
                )
        except Exception:
            pass  # Не критично — статус можно проверить позже

    return {"request_id": link_request.id, "expires_at": expires_at.isoformat()}


@router.get("/link-status/{request_id}")
async def get_link_status(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить статус запроса привязки (polling с фронтенда)."""
    result = await db.execute(
        select(BotLinkRequest).where(
            and_(
                BotLinkRequest.id == request_id,
                BotLinkRequest.web_user_id == current_user.id,
            )
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    # Проверяем истечение
    if req.status == "PENDING" and req.expires_at < datetime.utcnow():
        req.status = "EXPIRED"
        await db.commit()

    response = {"status": req.status}

    # Если подтверждено — выдаём новый токен для бот-аккаунта
    if req.status == "CONFIRMED":
        new_token = create_access_token(req.bot_user_id)
        response["access_token"] = new_token

    return response


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получить текущего пользователя."""
    return _build_user_response(current_user)


# ─── Telegram Login Widget ────────────────────────────────────────────────────


class TelegramAuthData(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


def _verify_telegram_auth(data: TelegramAuthData) -> bool:
    """Verify Telegram Login Widget data using HMAC-SHA256."""
    bot_token = config.BOT_TOKEN
    if not bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN не настроен")

    # Build data-check-string: sorted key=value pairs (excluding hash)
    fields = {
        "id": str(data.id),
        "auth_date": str(data.auth_date),
    }
    if data.first_name:
        fields["first_name"] = data.first_name
    if data.last_name:
        fields["last_name"] = data.last_name
    if data.username:
        fields["username"] = data.username
    if data.photo_url:
        fields["photo_url"] = data.photo_url

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    # Проверяем что данные не старше 24 часов
    if time.time() - data.auth_date > 86400:
        return False

    return hmac.compare_digest(expected_hash, data.hash)


@router.get("/telegram/config")
async def telegram_config():
    """Вернуть bot_username для Telegram Login Widget."""
    if not config.BOT_USERNAME:
        raise HTTPException(status_code=503, detail="Telegram Login не настроен")
    return {"bot_username": config.BOT_USERNAME}


@router.post("/telegram", response_model=TokenResponse)
async def telegram_login(body: TelegramAuthData, db: AsyncSession = Depends(get_db)):
    """
    Авторизация через Telegram Login Widget.

    Принимает данные от виджета, верифицирует подпись,
    создаёт или получает пользователя по tg_id.
    """
    if not _verify_telegram_auth(body):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверная подпись Telegram. Попробуйте снова.",
        )

    repo = UserRepository(db)
    username = body.username or body.first_name or f"tg_{body.id}"
    user = await repo.get_or_create_by_telegram_id(
        telegram_id=body.id,
        username=username,
    )

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=_build_user_response(user))


# ─── Telegram QR Login (Upscale-style: QR → deep-link → подтверждение в боте) ───


class QrStartResponse(BaseModel):
    token: str
    deeplink: str
    expires_at: str


@router.post("/qr/start", response_model=QrStartResponse)
async def qr_start(db: AsyncSession = Depends(get_db)):
    """Создать QR-сессию входа через Telegram.

    Фронт показывает QR с ``deeplink`` и опрашивает ``/qr/status/{token}``.
    """
    if not config.BOT_USERNAME:
        raise HTTPException(status_code=503, detail="Telegram-вход не настроен")

    token = secrets.token_urlsafe(24)
    expires_at = datetime.utcnow() + timedelta(minutes=config.QR_LOGIN_TTL_MINUTES)
    session = QrLoginSession(token=token, status="PENDING", expires_at=expires_at)
    db.add(session)
    await db.commit()

    deeplink = f"https://t.me/{config.BOT_USERNAME}?start=login_{token}"
    return QrStartResponse(token=token, deeplink=deeplink, expires_at=expires_at.isoformat() + "Z")


@router.get("/qr/status/{token}")
async def qr_status(token: str, db: AsyncSession = Depends(get_db)):
    """Поллинг статуса QR-сессии. При CONFIRMED — выдаёт JWT и профиль."""
    result = await db.execute(select(QrLoginSession).where(QrLoginSession.token == token))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Сессия входа не найдена")

    # Помечаем истёкшие
    if session.status == "PENDING" and session.expires_at < datetime.utcnow():
        session.status = "EXPIRED"
        await db.commit()

    response: dict = {"status": session.status}

    if session.status == "CONFIRMED" and session.user_id:
        repo = UserRepository(db)
        user = await repo.get_by_id(session.user_id)
        if user:
            response["access_token"] = create_access_token(user.id)
            response["user"] = _build_user_response(user).model_dump()

    return response
