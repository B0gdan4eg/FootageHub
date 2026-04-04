"""
Subscription Repository - управление подписками пользователей.

Реализует паттерн Repository для работы с моделью Subscription.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import ServiceType, Subscription, SubscriptionType
from shared.db.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    """Репозиторий для управления подписками"""

    def __init__(self, session: AsyncSession):
        super().__init__(Subscription, session)

    async def get_active_by_user_id(self, user_id: int) -> Optional[Subscription]:
        """
        Получить активную подписку пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Активная подписка или None
        """
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.is_active,
                    Subscription.end_date > datetime.utcnow(),
                )
            )
            .order_by(Subscription.end_date.desc())
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_active_by_user_id(self, user_id: int) -> List[Subscription]:
        """
        Получить все активные подписки пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список активных подписок
        """
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.is_active,
                    Subscription.end_date > datetime.utcnow(),
                )
            )
            .order_by(Subscription.end_date.desc())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_payment_id(self, payment_id: int) -> Optional[Subscription]:
        """
        Получить подписку по ID платежа.

        Args:
            payment_id: ID платежа

        Returns:
            Подписка или None
        """
        query = select(Subscription).where(Subscription.payment_id == payment_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_subscription(
        self,
        user_id: int,
        subscription_type: SubscriptionType,
        service_type: ServiceType,
        total_limit: Optional[int],
        daily_limit: Optional[int],
        end_date: datetime,
        payment_id: Optional[int] = None,
    ) -> Subscription:
        """
        Создать новую подписку.

        Args:
            user_id: ID пользователя
            subscription_type: Тип подписки
            service_type: Тип сервиса
            total_limit: Общий лимит загрузок
            daily_limit: Дневной лимит
            end_date: Дата окончания
            payment_id: ID платежа (опционально)

        Returns:
            Созданная подписка
        """
        subscription = Subscription(
            user_id=user_id,
            subscription_type=subscription_type,
            service_type=service_type,
            total_limit=total_limit,
            daily_limit=daily_limit,
            used_total=0,
            used_today=0,
            start_date=datetime.utcnow(),
            end_date=end_date,
            is_active=True,
            payment_id=payment_id,
        )

        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def increment_usage(self, subscription_id: int, amount: int = 1) -> Subscription:
        """
        Увеличить счетчики использования подписки.

        Args:
            subscription_id: ID подписки
            amount: Количество использований (по умолчанию 1)

        Returns:
            Обновленная подписка
        """
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        # Сброс дневного счетчика если нужно
        today = datetime.utcnow().date()
        if subscription.last_reset_date != today:
            subscription.used_today = 0
            subscription.last_reset_date = today

        subscription.used_total += amount
        subscription.used_today += amount
        subscription.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def reset_daily_usage(self, subscription_id: int) -> Subscription:
        """
        Сбросить дневной счетчик использования.

        Args:
            subscription_id: ID подписки

        Returns:
            Обновленная подписка
        """
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        subscription.used_today = 0
        subscription.last_reset_date = datetime.utcnow().date()
        subscription.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def deactivate(self, subscription_id: int) -> Subscription:
        """
        Деактивировать подписку.

        Args:
            subscription_id: ID подписки

        Returns:
            Обновленная подписка
        """
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        subscription.is_active = False
        subscription.updated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def get_expired_subscriptions(self) -> List[Subscription]:
        """
        Получить список истекших активных подписок.

        Returns:
            Список истекших подписок
        """
        query = select(Subscription).where(
            and_(Subscription.is_active, Subscription.end_date <= datetime.utcnow())
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_subscriptions_needing_daily_reset(self) -> List[Subscription]:
        """
        Получить подписки, которым нужен сброс дневного счетчика.

        Returns:
            Список подписок для сброса
        """
        today = datetime.utcnow().date()
        query = select(Subscription).where(
            and_(
                Subscription.is_active,
                Subscription.daily_limit.isnot(None),
                Subscription.last_reset_date < today,
            )
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def can_download(self, subscription_id: int, service_type: ServiceType) -> bool:
        """
        Проверить, может ли подписка использоваться для загрузки.

        Args:
            subscription_id: ID подписки
            service_type: Тип сервиса для загрузки

        Returns:
            True если можно скачивать
        """
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            return False

        # Проверка активности
        if not subscription.is_active:
            return False

        # Проверка срока действия
        if subscription.end_date <= datetime.utcnow():
            return False

        # Проверка типа сервиса
        if (
            subscription.service_type != ServiceType.ALL
            and subscription.service_type != service_type
        ):
            return False

        # Проверка лимитов
        # Сброс дневного счетчика если нужно
        today = datetime.utcnow().date()
        if subscription.last_reset_date != today:
            subscription.used_today = 0
            subscription.last_reset_date = today
            await self.session.flush()

        # Проверка общего лимита
        if subscription.total_limit is not None:
            if subscription.used_total >= subscription.total_limit:
                return False

        # Проверка дневного лимита
        if subscription.daily_limit is not None:
            if subscription.used_today >= subscription.daily_limit:
                return False

        return True

    async def get_user_subscription_count(self, user_id: int) -> int:
        """
        Получить количество подписок пользователя (всего).

        Args:
            user_id: ID пользователя

        Returns:
            Количество подписок
        """
        query = select(func.count(Subscription.id)).where(Subscription.user_id == user_id)

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_user_active_subscription_count(self, user_id: int) -> int:
        """
        Получить количество активных подписок пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество активных подписок
        """
        query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.user_id == user_id,
                Subscription.is_active,
                Subscription.end_date > datetime.utcnow(),
            )
        )

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_total_downloads_used(self, subscription_id: int) -> int:
        """
        Получить количество использованных загрузок.

        Args:
            subscription_id: ID подписки

        Returns:
            Количество использованных загрузок
        """
        subscription = await self.get_by_id(subscription_id)
        return subscription.used_total if subscription else 0

    async def get_remaining_downloads(self, subscription_id: int) -> Optional[int]:
        """
        Получить количество оставшихся загрузок.

        Args:
            subscription_id: ID подписки

        Returns:
            Количество оставшихся загрузок или None если безлимит
        """
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            return 0

        if subscription.total_limit is None:
            return None  # Безлимит

        return max(0, subscription.total_limit - subscription.used_total)

    async def count_active_subs(self) -> int:
        """
        Подсчитать количество активных подписок.

        Returns:
            Количество активных подписок
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(Subscription)
            .where(and_(Subscription.is_active, Subscription.end_date > datetime.utcnow()))
        )
        return result.scalar()

    async def check_download_limit(self, subscription: Subscription) -> tuple[bool, str]:
        """
        Проверить лимиты скачивания для подписки.

        Args:
            subscription: Объект подписки

        Returns:
            Tuple (можно_скачать, сообщение_об_ошибке)
        """
        # Проверка срока действия
        if subscription.end_date < datetime.utcnow():
            return False, "Подписка истекла"

        # Проверка общего лимита
        if subscription.total_limit and subscription.used_total >= subscription.total_limit:
            return False, "Достигнут общий лимит подписки"

        # Сброс дневного счётчика если новый день
        today = datetime.utcnow().date()
        if subscription.last_reset_date < today:
            subscription.used_today = 0
            subscription.last_reset_date = today
            await self.session.commit()

        # Проверка дневного лимита
        if subscription.daily_limit and subscription.used_today >= subscription.daily_limit:
            return False, "Достигнут дневной лимит подписки"

        return True, ""

    async def get_user_subscriptions(
        self, user_id: int, include_expired: bool = False
    ) -> list[Subscription]:
        """
        Получить все подписки пользователя.

        Args:
            user_id: ID пользователя
            include_expired: Включить истекшие подписки

        Returns:
            Список подписок
        """
        query = select(Subscription).where(Subscription.user_id == user_id)

        if not include_expired:
            query = query.where(
                and_(Subscription.is_active, Subscription.end_date > datetime.utcnow())
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def extend_subscription(self, subscription_id: int, days: int) -> Subscription:
        """
        Продлить подписку на указанное количество дней.

        Args:
            subscription_id: ID подписки
            days: Количество дней для продления

        Returns:
            Обновлённая подписка

        Raises:
            ValueError: If subscription not found
        """
        from datetime import timedelta

        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        subscription.end_date = subscription.end_date + timedelta(days=days)
        subscription.updated_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def delete_all_subscriptions(self) -> int:
        """
        Удалить все подписки из базы данных.

        Warning: Это опасная операция, используйте осторожно!

        Returns:
            Количество удалённых подписок
        """
        from sqlalchemy import delete as sql_delete

        result = await self.session.execute(select(Subscription))
        count = len(result.scalars().all())

        await self.session.execute(sql_delete(Subscription))
        await self.session.commit()

        return count

    async def create_subscription_with_credits(
        self,
        user_id: int,
        subscription_type: SubscriptionType,
        service_type: ServiceType = ServiceType.ALL,
        total_limit: Optional[int] = None,
        daily_limit: Optional[int] = None,
        days: int = 30,
        payment_id: Optional[int] = None,
    ) -> Subscription:
        """
        Создать подписку и начислить кредиты пользователю.

        Args:
            user_id: ID пользователя
            subscription_type: Тип подписки
            service_type: Тип сервиса
            total_limit: Общий лимит скачиваний
            daily_limit: Дневной лимит
            days: Длительность подписки в днях
            payment_id: ID платежа (опционально)

        Returns:
            Созданная подписка
        """
        from datetime import timedelta

        from shared.db.models import User

        subscription = Subscription(
            user_id=user_id,
            subscription_type=subscription_type,
            service_type=service_type,
            total_limit=total_limit,
            daily_limit=daily_limit,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=days),
            payment_id=payment_id,
            is_active=True,
        )

        self.session.add(subscription)

        # Получаем пользователя для начисления кредитов
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user:
            # Для MONTHLY_150: добавляем total_limit к текущим кредитам
            if total_limit:
                user.credits += total_limit
                print(f"[SUBSCRIPTION] Начислено {total_limit} кредитов пользователю {user_id}")

            # Для DAILY_30: устанавливаем кредиты равными daily_limit
            elif daily_limit:
                user.credits = daily_limit
                print(f"[SUBSCRIPTION] Установлено {daily_limit} кредитов пользователю {user_id}")

        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription
