"""
Subscription Service для MediaBot

Бизнес-логика управления подписками.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.core.exceptions import (
    InsufficientCreditsError,
    SubscriptionException,
    UserNotFoundError,
)
from shared.core.logger import get_logger
from shared.db.models import ServiceType, Subscription
from shared.db.repositories.subscription_repository import SubscriptionRepository
from shared.db.repositories.user_repository import UserRepository

logger = get_logger(__name__)


class SubscriptionService:
    """
    Сервис управления подписками

    Проверка лимитов, доступности скачивания, статистики.
    """

    def __init__(self, user_repo: UserRepository, subscription_repo: SubscriptionRepository):
        self._user_repo = user_repo
        self._subscription_repo = subscription_repo

    async def check_can_download(self, user_id: int, service_type: Optional[str] = None) -> bool:
        """
        Проверка возможности загрузки

        Args:
            user_id: Telegram ID пользователя
            service_type: Тип сервиса (ENVATO, FREEPIK, MOTION, ALL)

        Returns:
            True если пользователь может загружать
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return False

        # Если service_type не указан, проверяем наличие любой активной подписки
        if not service_type:
            subscription = await self._subscription_repo.get_active_by_user_id(user.id)
            return subscription is not None

        return await self._subscription_repo.can_download(
            user_id=user.id, service_type=service_type
        )

    async def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """
        Получить активную подписку пользователя

        Args:
            user_id: Telegram ID пользователя

        Returns:
            Subscription или None
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return None

        return await self._subscription_repo.get_active_by_user_id(user.id)

    async def get_all_active_subscriptions(self, user_id: int) -> List[Subscription]:
        """
        Получить все активные подписки пользователя

        Args:
            user_id: Telegram ID пользователя

        Returns:
            Список подписок
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return []

        return await self._subscription_repo.get_all_active_by_user_id(user.id)

    async def get_subscription_status(self, user_id: int) -> Dict[str, Any]:
        """
        Получить детальный статус подписки

        Returns:
            Dict с информацией о подписке:
            {
                "has_subscription": bool,
                "service_type": str,
                "downloads_remaining": int,
                "daily_remaining": int,
                "expires_in_days": int,
                "expires_at": datetime,
                "is_expired": bool
            }
        """
        subscription = await self.get_active_subscription(user_id)

        if not subscription:
            return {
                "has_subscription": False,
                "service_type": None,
                "downloads_remaining": 0,
                "daily_remaining": 0,
                "expires_in_days": 0,
                "expires_at": None,
                "is_expired": True,
            }

        remaining = await self._subscription_repo.get_remaining_downloads(subscription.id)

        daily_remaining = 0
        if subscription.daily_limit:
            daily_remaining = max(0, subscription.daily_limit - subscription.daily_downloads_used)

        days_remaining = (subscription.expires_at - datetime.utcnow()).days

        return {
            "has_subscription": True,
            "service_type": subscription.service_type.value,
            "downloads_remaining": remaining,
            "daily_remaining": daily_remaining,
            "expires_in_days": max(0, days_remaining),
            "expires_at": subscription.expires_at,
            "is_expired": not subscription.is_active,
        }

    async def increment_download_count(self, user_id: int) -> None:
        """
        Увеличить счетчик использования подписки

        Args:
            user_id: Telegram ID пользователя

        Raises:
            SubscriptionException: Нет активной подписки
        """
        subscription = await self.get_active_subscription(user_id)

        if not subscription:
            raise SubscriptionException("No active subscription")

        await self._subscription_repo.increment_usage(subscription.id)

        logger.info(
            f"Download count incremented for subscription {subscription.id}. "
            f"New usage: {subscription.downloads_used + 1}"
        )

    async def reset_daily_limits(self) -> int:
        """
        Сброс дневных лимитов для всех подписок

        Должен вызываться планировщиком раз в день.

        Returns:
            Количество обновленных подписок
        """
        logger.info("Resetting daily limits for all subscriptions")

        # Получаем все активные подписки
        # TODO: Добавить метод get_all_active в SubscriptionRepository
        # Пока используем обходной путь
        count = 0

        # В реальности здесь должен быть SQL запрос для массового обновления
        # UPDATE subscriptions SET daily_downloads_used = 0 WHERE is_active = true

        logger.info(f"Daily limits reset for {count} subscriptions")
        return count

    async def check_expiration_warning(
        self, user_id: int, warning_days: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Проверка приближения окончания подписки

        Args:
            user_id: Telegram ID пользователя
            warning_days: За сколько дней предупреждать

        Returns:
            Dict с информацией если подписка скоро истекает, иначе None
        """
        subscription = await self.get_active_subscription(user_id)

        if not subscription:
            return None

        days_remaining = (subscription.expires_at - datetime.utcnow()).days

        if 0 < days_remaining <= warning_days:
            return {
                "days_remaining": days_remaining,
                "expires_at": subscription.expires_at,
                "service_type": subscription.service_type.value,
            }

        return None

    async def get_usage_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику использования подписки

        Returns:
            Dict со статистикой
        """
        subscription = await self.get_active_subscription(user_id)

        if not subscription:
            return {
                "has_subscription": False,
                "total_downloads": 0,
                "downloads_remaining": 0,
                "usage_percentage": 0,
            }

        remaining = await self._subscription_repo.get_remaining_downloads(subscription.id)

        usage_percentage = 0
        if subscription.downloads_limit > 0:
            usage_percentage = subscription.downloads_used / subscription.downloads_limit * 100

        return {
            "has_subscription": True,
            "total_downloads": subscription.downloads_used,
            "downloads_remaining": remaining,
            "downloads_limit": subscription.downloads_limit,
            "usage_percentage": round(usage_percentage, 2),
            "daily_used": subscription.daily_downloads_used,
            "daily_limit": subscription.daily_limit,
        }

    async def validate_service_access(self, user_id: int, requested_service: str) -> bool:
        """
        Проверка доступа к конкретному сервису

        Args:
            user_id: Telegram ID пользователя
            requested_service: Запрашиваемый сервис (ENVATO, FREEPIK, MOTION)

        Returns:
            True если доступ разрешен
        """
        subscription = await self.get_active_subscription(user_id)

        if not subscription:
            return False

        # Если подписка ALL - доступ ко всем сервисам
        if subscription.service_type == ServiceType.ALL:
            return True

        # Проверка совпадения типа сервиса
        return subscription.service_type.value == requested_service
