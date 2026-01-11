"""
Download Service для MediaBot

Бизнес-логика загрузок с dependency injection.
Следует принципам SOLID:
- Single Responsibility: только управление загрузками
- Dependency Inversion: зависит от абстракций (repositories)
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from media_bot.downloaders.base import AbstractDownloader
from media_bot.downloaders.envato import EnvatoDownloader
from media_bot.downloaders.freepik import FreepikDownloader
from media_bot.downloaders.motion import MotionDownloader
from shared.core.exceptions import (
    DownloadException,
    InsufficientCreditsError,
    InvalidUrlError,
    SubscriptionRequiredError,
)
from shared.core.logger import get_logger
from shared.db.repositories.subscription_repository import SubscriptionRepository
from shared.db.repositories.user_repository import UserRepository

logger = get_logger(__name__)


@dataclass
class DownloadResult:
    """Результат загрузки"""

    success: bool
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    remaining_credits: int = 0
    credits_spent: int = 0


class DownloadService:
    """
    Сервис управления загрузками

    Координирует проверку подписки, списание кредитов и процесс загрузки.
    """

    def __init__(self, user_repo: UserRepository, subscription_repo: SubscriptionRepository):
        self._user_repo = user_repo
        self._subscription_repo = subscription_repo

        # Мапа провайдеров загрузки
        self._downloaders: Dict[str, AbstractDownloader] = {
            "ENVATO": EnvatoDownloader(),
            "FREEPIK": FreepikDownloader(),
            "MOTION": MotionDownloader(),
        }

    async def process_download(self, user_id: int, url: str, provider: str) -> DownloadResult:
        """
        Обработка загрузки с проверкой прав и списанием кредитов

        Args:
            user_id: Telegram ID пользователя
            url: URL для загрузки
            provider: Провайдер загрузки (ENVATO, FREEPIK, MOTION)

        Returns:
            DownloadResult с результатом загрузки

        Raises:
            InvalidUrlError: Неверный URL
            InsufficientCreditsError: Недостаточно кредитов
            SubscriptionRequiredError: Требуется подписка
            DownloadException: Ошибка загрузки
        """
        logger.info(f"Processing download for user {user_id}, provider: {provider}")

        # 1. Получение пользователя
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise DownloadException("User not found")

        # 2. Проверка подписки и лимитов
        can_download = await self._subscription_repo.can_download(
            user_id=user.id, service_type=provider
        )

        if not can_download:
            # Проверяем, есть ли хоть какая-то подписка
            subscription = await self._subscription_repo.get_active_by_user_id(user.id)
            if subscription:
                raise InsufficientCreditsError(
                    f"Недостаточно кредитов. Осталось: {subscription.downloads_left}"
                )
            else:
                raise SubscriptionRequiredError("Для загрузки требуется активная подписка")

        # 3. Получение загрузчика
        downloader = self._downloaders.get(provider)
        if not downloader:
            raise DownloadException(f"Unknown provider: {provider}")

        # 4. Проверка авторизации загрузчика
        if not await downloader.check_auth():
            logger.error(f"{provider} downloader is not authenticated")
            raise DownloadException(f"Ошибка авторизации {provider}. Обратитесь к администратору.")

        # 5. Загрузка файла
        try:
            download_url = await downloader.download(url)

            if not download_url:
                raise DownloadException("Не удалось загрузить файл")

            # 6. Списание кредита
            subscription = await self._subscription_repo.get_active_by_user_id(user.id)
            await self._subscription_repo.increment_usage(subscription.id)

            # 7. Получение оставшихся кредитов
            remaining = await self._subscription_repo.get_remaining_downloads(subscription.id)

            logger.info(
                f"Download successful for user {user_id}. " f"Remaining credits: {remaining}"
            )

            return DownloadResult(
                success=True,
                download_url=download_url,
                remaining_credits=remaining,
                credits_spent=1,
            )

        except InvalidUrlError:
            raise
        except Exception as e:
            logger.error(f"Download failed for user {user_id}: {e}")
            raise DownloadException(f"Ошибка загрузки: {str(e)}")

    async def check_download_availability(self, user_id: int, provider: str) -> Dict[str, Any]:
        """
        Проверка возможности загрузки без фактической загрузки

        Returns:
            Dict с информацией о доступности:
            {
                "can_download": bool,
                "remaining_credits": int,
                "subscription_active": bool,
                "reason": str  # если can_download = False
            }
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return {
                "can_download": False,
                "remaining_credits": 0,
                "subscription_active": False,
                "reason": "User not found",
            }

        subscription = await self._subscription_repo.get_active_by_user_id(user.id)
        if not subscription:
            return {
                "can_download": False,
                "remaining_credits": 0,
                "subscription_active": False,
                "reason": "No active subscription",
            }

        can_download = await self._subscription_repo.can_download(
            user_id=user.id, service_type=provider
        )

        remaining = await self._subscription_repo.get_remaining_downloads(subscription.id)

        return {
            "can_download": can_download,
            "remaining_credits": remaining,
            "subscription_active": True,
            "reason": "" if can_download else "Insufficient credits",
        }

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику загрузок пользователя

        Returns:
            Dict со статистикой
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return {}

        subscription = await self._subscription_repo.get_active_by_user_id(user.id)

        if not subscription:
            return {"has_subscription": False, "total_downloads": 0, "remaining_downloads": 0}

        remaining = await self._subscription_repo.get_remaining_downloads(subscription.id)

        return {
            "has_subscription": True,
            "total_downloads": subscription.downloads_used,
            "remaining_downloads": remaining,
            "subscription_type": subscription.service_type.value,
            "daily_limit": subscription.daily_limit,
            "daily_used": subscription.daily_downloads_used,
        }
