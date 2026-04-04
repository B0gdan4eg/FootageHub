"""Downloads router: media download from Envato/Freepik/Motion Array."""

import logging
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import User
from web_api.adapters.download_adapter import WebDownloadAdapter
from web_api.dependencies import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Временное хранилище токенов для файлов (token -> file_path, TTL 5 мин)
_file_tokens: dict[str, tuple[str, float]] = {}


def _detect_provider(url: str) -> str:
    """Определить платформу по URL."""
    url_lower = url.lower()
    if "elements.envato.com" in url_lower or "envato" in url_lower:
        return "ENVATO"
    if "freepik.com" in url_lower:
        return "FREEPIK"
    if "motionarray.com" in url_lower:
        return "MOTION_ARRAY"
    raise ValueError("Неподдерживаемый URL. Поддерживаются: Envato Elements, Freepik, Motion Array")


class DownloadRequest(BaseModel):
    url: str
    provider: str | None = None  # если не указан — определяется автоматически


@router.post("/")
async def download_media(
    body: DownloadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Скачать медиафайл по URL.

    Возвращает download_url (прямую ссылку или токен для /file/{token}).
    """
    provider = body.provider
    if not provider:
        try:
            provider = _detect_provider(body.url)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    adapter = WebDownloadAdapter(current_user.id, db)
    try:
        result = await adapter.process_download(body.url, provider)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))
    except ValueError as e:
        logger.error("Download error for user=%s url=%s: %s", current_user.id, body.url, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка скачивания. Проверьте ссылку и попробуйте снова.",
        )
    except Exception as e:
        logger.error(
            "Unexpected download error for user=%s url=%s: %s", current_user.id, body.url, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка скачивания. Попробуйте позже.",
        )

    return result


@router.get("/file/{token}")
async def serve_file(token: str):
    """Отдать локальный файл по временному токену (TTL 5 мин)."""
    import time

    entry = _file_tokens.get(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Токен недействителен или истёк")

    file_path, expires_at = entry
    if time.time() > expires_at:
        del _file_tokens[token]
        raise HTTPException(status_code=404, detail="Токен истёк")

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(
        path=file_path,
        filename=path.name,
        media_type="application/octet-stream",
    )


def create_file_token(file_path: str) -> str:
    """Создать временный токен для скачивания файла."""
    import time

    token = secrets.token_urlsafe(32)
    _file_tokens[token] = (file_path, time.time() + 300)  # TTL 5 мин
    return token
