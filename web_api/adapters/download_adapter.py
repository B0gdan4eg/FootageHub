"""
Download adapter for web API.

Wraps media_bot downloaders to work with web users identified by DB primary key
instead of tg_id.
"""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from media_bot.downloaders.envato import EnvatoDownloader
from media_bot.downloaders.freepik import FreepikDownloader
from media_bot.downloaders.motion import MotionDownloader
from shared.db.models import Download, Media, ServiceType
from shared.db.repositories.subscription_repository import SubscriptionRepository
from shared.db.repositories.user_repository import UserRepository


class WebDownloadAdapter:
    """
    Адаптер для скачивания медиа через web API.

    Отличие от DownloadService: идентифицирует пользователя по DB user.id,
    а не по tg_id — что необходимо для web-пользователей без Telegram.
    """

    _downloaders = {
        "ENVATO": EnvatoDownloader,
        "FREEPIK": FreepikDownloader,
        "MOTION_ARRAY": MotionDownloader,
    }

    _service_types = {
        "ENVATO": ServiceType.ENVATO,
        "FREEPIK": ServiceType.FREEPIK,
        "MOTION_ARRAY": ServiceType.MOTION_ARRAY,
    }

    def __init__(self, db_user_id: int, db: AsyncSession):
        self._user_id = db_user_id
        self._db = db

    async def process_download(self, url: str, provider: str) -> dict:
        """
        Скачать медиафайл для web-пользователя.

        Args:
            url: URL медиафайла
            provider: ENVATO | FREEPIK | MOTION_ARRAY

        Returns:
            {
                "download_url": str,  # прямая ссылка или токен
                "remaining_credits": int,
                "is_file_token": bool  # True если это токен для /file/{token}
            }

        Raises:
            ValueError: Если URL некорректен или провайдер неизвестен
            PermissionError: Если недостаточно кредитов или нет подписки
        """
        provider = provider.upper()
        if provider not in self._downloaders:
            raise ValueError(
                f"Неизвестный провайдер: {provider}. Используйте: {list(self._downloaders.keys())}"
            )

        # Проверяем пользователя
        user_repo = UserRepository(self._db)
        user = await user_repo.get_by_id(self._user_id)
        if not user:
            raise ValueError("Пользователь не найден")

        # Проверяем подписку/кредиты
        sub_repo = SubscriptionRepository(self._db)
        service_type = self._service_types[provider]

        # Проверяем активную подписку для данного сервиса
        has_sub = await sub_repo.has_active_subscription(user.id, service_type)
        if not has_sub:
            # Проверяем бесплатные кредиты
            if user.credits <= 0:
                raise PermissionError(
                    "Недостаточно кредитов. Купите подписку или пополните баланс."
                )

        # Скачиваем файл
        downloader = self._downloaders[provider]()
        result_url = await downloader.download(url)

        if not result_url:
            raise ValueError("Не удалось скачать файл. Проверьте URL и попробуйте снова.")

        # Определяем — это прямая ссылка или путь к файлу
        is_file_token = False
        download_url = result_url

        if not result_url.startswith("http"):
            # Это локальный путь к файлу — создаём временный токен
            if os.path.exists(result_url):
                from web_api.routers.downloads import create_file_token

                token = create_file_token(result_url)
                download_url = f"/api/downloads/file/{token}"
                is_file_token = True
            else:
                raise ValueError("Файл не найден после скачивания")

        # Списываем кредиты / обновляем счётчик подписки
        if has_sub:
            await sub_repo.increment_usage(user.id, service_type)
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
            paid=not has_sub,
        )
        self._db.add(download)
        await self._db.commit()

        return {
            "download_url": download_url,
            "remaining_credits": user.credits,
            "is_file_token": is_file_token,
        }
