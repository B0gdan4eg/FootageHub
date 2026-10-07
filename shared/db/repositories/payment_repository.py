"""
Payment Repository - управление платежами.

Реализует паттерн Repository для работы с моделью Payment.
"""

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Payment
from shared.db.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Репозиторий для управления платежами"""

    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)

    async def create_payment(
        self,
        user_id: int,
        amount: float,
        currency: str,
        plan_key: str,
        invoice_id: str,
    ) -> Payment:
        """
        Создать платеж для подписки.

        Args:
            user_id: ID пользователя
            amount: Сумма платежа
            currency: Валюта (USDT, BTC, etc.)
            plan_key: Ключ плана (monthly_150, daily_30)
            invoice_id: ID инвойса из CryptoPay

        Returns:
            Created payment object
        """
        payment = Payment(
            user_id=user_id,
            amount=amount,
            currency=currency,
            plan_key=plan_key,
            invoice_id=invoice_id,
            status="pending",
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_by_invoice_id(self, invoice_id: str, *, lock: bool = False) -> Optional[Payment]:
        """
        Получить платеж по invoice_id.

        Args:
            invoice_id: Invoice ID from payment provider

        Returns:
            Payment or None if not found
        """
        query = select(Payment).where(Payment.invoice_id == invoice_id)
        if lock:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().first()

    async def update_status(self, invoice_id: str, status: str) -> None:
        """
        Обновить статус платежа.

        Args:
            invoice_id: Invoice ID
            status: New payment status
        """
        await self.session.execute(
            update(Payment).where(Payment.invoice_id == invoice_id).values(status=status)
        )
        await self.session.commit()

    async def mark_success(self, invoice_id: str) -> None:
        """
        Пометить платеж как успешный.

        Args:
            invoice_id: Invoice ID
        """
        await self.session.execute(
            update(Payment).where(Payment.invoice_id == invoice_id).values(status="success")
        )
        await self.session.commit()
