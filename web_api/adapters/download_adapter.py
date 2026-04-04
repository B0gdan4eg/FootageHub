"""
Download adapter for web API.

Delegates actual downloading to media-bot via internal HTTP API,
since browser automation (nodriver, playwright) runs only in media-bot container.
Both containers share the same Docker network (footagehub-network).
"""

import os

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Download, Media, ServiceType
from shared.db.repositories.subscription_repository import SubscriptionRepository
from shared.db.repositories.user_repository import UserRepository

# media-bot internal API URL — доступен через Docker-сеть footagehub-network
MEDIA_BOT_URL = os.getenv("MEDIA_BOT_INTERNAL_URL", "http://media-bot:8443")

_SERVICE_TYPES = {
    "ENVATO": ServiceType.ENVATO,
    "FREEPIK": ServiceType.FREEPIK,
    "MOTION_ARRAY": ServiceType.MOTION_ARRAY,
}


class WebDownloadAdapter:
    """
    Адаптер для скачивания медиа через web API.

    Идентифицирует пользователя по DB user.id (не по tg_id).
    Делегирует скачивание в media-bot через внутренний HTTP-эндпоинт.
    """

    def __init__(self, db_user_id: int, db: AsyncSession):
        self._user_id = db_user_id
        self._db = db

    async def process_download(self, url: str, provider: str) -> dict:
        """
        Скачать медиафайл для web-пользователя.

        Returns:
            {
                "download_url": str,
                "remaining_credits": int,
                "is_file_token": bool
            }

        Raises:
            ValueError: Если URL некорректен или провайдер неизвестен
            PermissionError: Если недостаточно кредитов или нет подписки
        """
        provider = provider.upper()
        if provider not in _SERVICE_TYPES:
            raise ValueError(
                f"Неизвестный провайдер: {provider}. Используйте: {list(_SERVICE_TYPES.keys())}"
            )

        # Проверяем пользователя
        user_repo = UserRepository(self._db)
        user = await user_repo.get_by_id(self._user_id)
        if not user:
            raise ValueError("Пользователь не найден")

        # Ищем активную подписку на нужный сервис
        sub_repo = SubscriptionRepository(self._db)
        service_type = _SERVICE_TYPES[provider]

        active_sub = None
        all_subs = await sub_repo.get_all_active_by_user_id(user.id)
        for sub in all_subs:
            if sub.service_type == service_type or sub.service_type == ServiceType.ALL:
                can_dl = await sub_repo.can_download(sub.id, service_type)
                if can_dl:
                    active_sub = sub
                    break

        if active_sub is None and user.credits <= 0:
            raise PermissionError("Недостаточно кредитов. Купите подписку или пополните баланс.")

        # Делегируем скачивание в media-bot через внутреннюю сеть Docker
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{MEDIA_BOT_URL}/internal/download",
                    json={"url": url, "provider": provider},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
            raise ValueError(f"Ошибка скачивания: {detail}")
        except httpx.RequestError as e:
            raise ValueError(f"Не удалось связаться с сервисом скачивания: {e}")

        download_url = data["download_url"]

        # Списываем кредиты / обновляем счётчик подписки
        if active_sub is not None:
            await sub_repo.increment_usage(active_sub.id)
        else:
            user.credits -= 1

        # Записываем в историю
        media_result = await self._db.execute(select(Media).where(Media.url == url))
        media = media_result.scalar_one_or_none()
        if not media:
            media = Media(url=url)
            self._db.add(media)
            await self._db.flush()

        download = Download(
            user_id=user.id,
            media_id=media.id,
            service_type=service_type,
            paid=active_sub is None,
        )
        self._db.add(download)
        await self._db.commit()

        return {
            "download_url": download_url,
            "remaining_credits": user.credits,
            "is_file_token": False,
        }
