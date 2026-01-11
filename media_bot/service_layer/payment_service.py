"""
Payment Service для MediaBot

Бизнес-логика обработки платежей и создания подписок.
Интегрирует ReferralService для начисления реферальных наград.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from shared.core.exceptions import PaymentException, UserNotFoundError
from shared.core.logger import get_logger
from shared.db.models import ServiceType
from shared.db.repositories.subscription_repository import SubscriptionRepository
from shared.db.repositories.user_repository import UserRepository
from shared.services.credit_service import CreditService
from shared.services.referral_service import ReferralService

logger = get_logger(__name__)


@dataclass
class PaymentResult:
    """Результат обработки платежа"""

    success: bool
    subscription_id: Optional[int] = None
    error_message: Optional[str] = None
    referral_bonus_triggered: bool = False


@dataclass
class SubscriptionPlan:
    """План подписки"""

    service_type: ServiceType
    duration_days: int
    downloads_limit: int
    daily_limit: Optional[int] = None
    price: float = 0.0


class PaymentService:
    """
    Сервис управления платежами

    Координирует создание подписок, начисление реферальных бонусов
    и обновление статусов платежей.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        subscription_repo: SubscriptionRepository,
        referral_service: ReferralService,
        credit_service: CreditService,
    ):
        self._user_repo = user_repo
        self._subscription_repo = subscription_repo
        self._referral_service = referral_service
        self._credit_service = credit_service

    async def process_payment(
        self,
        user_id: int,
        plan: SubscriptionPlan,
        payment_method: str = "WEBPAY",
        payment_metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentResult:
        """
        Обработка платежа и создание подписки

        Args:
            user_id: Telegram ID пользователя
            plan: План подписки
            payment_method: Метод оплаты (WEBPAY, CRYPTOBOT)
            payment_metadata: Метаданные платежа (transaction_id, amount, etc.)

        Returns:
            PaymentResult с результатом обработки

        Raises:
            UserNotFoundError: Пользователь не найден
            PaymentException: Ошибка обработки платежа
        """
        logger.info(
            f"Processing payment for user {user_id}, "
            f"plan: {plan.service_type.value}, method: {payment_method}"
        )

        # 1. Получение пользователя
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        # 2. Проверка первого платежа (для реферальной системы)
        is_first_payment = await self._user_repo.get_payment_count(user.id) == 0

        try:
            # 3. Создание подписки
            expires_at = datetime.utcnow() + timedelta(days=plan.duration_days)

            subscription = await self._subscription_repo.create_subscription(
                user_id=user.id,
                service_type=plan.service_type,
                downloads_limit=plan.downloads_limit,
                daily_limit=plan.daily_limit,
                expires_at=expires_at,
            )

            logger.info(f"Subscription created: ID={subscription.id}, " f"expires_at={expires_at}")

            # 4. Триггер реферальных наград
            referral_bonus_triggered = False

            if is_first_payment:
                # Первый платеж - начисляем бонус рефереру
                try:
                    await self._referral_service.trigger_first_payment(
                        referred_user_id=user.id,
                        payment_amount=plan.price,
                        payment_metadata=payment_metadata or {},
                    )
                    referral_bonus_triggered = True
                    logger.info(f"Referral bonus triggered for user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to trigger referral bonus for user {user_id}: {e}")

            # Триггер подписки (не зависит от первого платежа)
            try:
                await self._referral_service.trigger_subscription(
                    referred_user_id=user.id,
                    subscription_type=plan.service_type.value,
                    subscription_metadata={
                        "subscription_id": subscription.id,
                        "duration_days": plan.duration_days,
                        "price": plan.price,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to trigger subscription event for user {user_id}: {e}")

            # 5. Проверка milestone наград
            try:
                milestone_reward = await self._referral_service.check_milestone_rewards(
                    user_id=user.id
                )
                if milestone_reward:
                    logger.info(
                        f"Milestone reward granted to user {user_id}: " f"{milestone_reward}"
                    )
            except Exception as e:
                logger.error(f"Failed to check milestone rewards for user {user_id}: {e}")

            return PaymentResult(
                success=True,
                subscription_id=subscription.id,
                referral_bonus_triggered=referral_bonus_triggered,
            )

        except Exception as e:
            logger.error(f"Payment processing failed for user {user_id}: {e}")
            raise PaymentException(f"Ошибка обработки платежа: {str(e)}")

    async def extend_subscription(self, user_id: int, plan: SubscriptionPlan) -> PaymentResult:
        """
        Продление существующей подписки

        Args:
            user_id: Telegram ID пользователя
            plan: План подписки

        Returns:
            PaymentResult с результатом
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        # Получаем текущую подписку
        current_subscription = await self._subscription_repo.get_active_by_user_id(user.id)

        if current_subscription:
            # Продление: добавляем дни к текущей дате окончания
            new_expires_at = current_subscription.expires_at + timedelta(days=plan.duration_days)

            # Обновляем лимиты (если изменились)
            # TODO: Добавить метод update_subscription в SubscriptionRepository

            logger.info(
                f"Subscription extended for user {user_id}, " f"new expires_at: {new_expires_at}"
            )
        else:
            # Нет активной подписки - создаем новую
            return await self.process_payment(user_id, plan)

        return PaymentResult(success=True)

    async def cancel_subscription(
        self, user_id: int, subscription_id: int, reason: str = "User requested"
    ) -> bool:
        """
        Отмена подписки

        Args:
            user_id: Telegram ID пользователя
            subscription_id: ID подписки
            reason: Причина отмены

        Returns:
            True если успешно отменена
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        try:
            await self._subscription_repo.deactivate(subscription_id)
            logger.info(
                f"Subscription {subscription_id} cancelled for user {user_id}. " f"Reason: {reason}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to cancel subscription {subscription_id} " f"for user {user_id}: {e}"
            )
            return False

    async def get_subscription_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о подписке пользователя

        Returns:
            Dict с информацией или None если нет подписки
        """
        user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return None

        subscription = await self._subscription_repo.get_active_by_user_id(user.id)
        if not subscription:
            return None

        remaining = await self._subscription_repo.get_remaining_downloads(subscription.id)

        return {
            "subscription_id": subscription.id,
            "service_type": subscription.service_type.value,
            "downloads_limit": subscription.downloads_limit,
            "downloads_used": subscription.downloads_used,
            "remaining_downloads": remaining,
            "daily_limit": subscription.daily_limit,
            "daily_used": subscription.daily_downloads_used,
            "expires_at": subscription.expires_at,
            "is_active": subscription.is_active,
            "days_remaining": (subscription.expires_at - datetime.utcnow()).days,
        }

    async def check_and_deactivate_expired(self) -> int:
        """
        Проверка и деактивация истекших подписок

        Returns:
            Количество деактивированных подписок
        """
        expired = await self._subscription_repo.get_expired_subscriptions()

        count = 0
        for subscription in expired:
            try:
                await self._subscription_repo.deactivate(subscription.id)
                count += 1
                logger.info(
                    f"Deactivated expired subscription {subscription.id} "
                    f"for user {subscription.user_id}"
                )
            except Exception as e:
                logger.error(f"Failed to deactivate subscription {subscription.id}: {e}")

        if count > 0:
            logger.info(f"Deactivated {count} expired subscriptions")

        return count


# Предопределенные планы подписок
class SubscriptionPlans:
    """Предопределенные планы подписок"""

    ENVATO_MONTHLY = SubscriptionPlan(
        service_type=ServiceType.ENVATO,
        duration_days=30,
        downloads_limit=100,
        daily_limit=10,
        price=10.0,
    )

    FREEPIK_MONTHLY = SubscriptionPlan(
        service_type=ServiceType.FREEPIK,
        duration_days=30,
        downloads_limit=100,
        daily_limit=10,
        price=10.0,
    )

    ALL_MONTHLY = SubscriptionPlan(
        service_type=ServiceType.ALL,
        duration_days=30,
        downloads_limit=200,
        daily_limit=20,
        price=15.0,
    )

    @classmethod
    def get_plan(cls, plan_name: str) -> Optional[SubscriptionPlan]:
        """Получить план по имени"""
        plans = {
            "envato_monthly": cls.ENVATO_MONTHLY,
            "freepik_monthly": cls.FREEPIK_MONTHLY,
            "all_monthly": cls.ALL_MONTHLY,
        }
        return plans.get(plan_name.lower())
