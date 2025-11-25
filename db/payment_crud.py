from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import Optional

from db.models import Payment


async def create_payment(
    session: AsyncSession,
    user_id: int,
    amount: float,
    currency: str,
    plan_key: str,
    invoice_id: str,
) -> Payment:
    """
    Создает платеж для подписки.

    Args:
        session: Database session
        user_id: ID пользователя
        amount: Сумма платежа
        currency: Валюта (USDT, BTC, etc.)
        plan_key: Ключ плана (monthly_150, daily_30)
        invoice_id: ID инвойса из CryptoPay

    Returns:
        Payment object
    """
    payment = Payment(
        user_id=user_id,
        amount=amount,
        currency=currency,
        plan_key=plan_key,
        invoice_id=invoice_id,
        status="pending",
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def get_payment_by_invoice_id(session: AsyncSession, invoice_id: str) -> Optional[Payment]:
    """Получить платеж по invoice_id."""
    result = await session.execute(select(Payment).where(Payment.invoice_id == invoice_id))
    return result.scalars().first()


async def update_payment_status(session: AsyncSession, invoice_id: str, status: str) -> None:
    """Обновить статус платежа."""
    await session.execute(
        update(Payment)
        .where(Payment.invoice_id == invoice_id)
        .values(status=status)
    )
    await session.commit()


async def mark_payment_success(session: AsyncSession, invoice_id: str) -> None:
    """Пометить платеж как успешный."""
    await session.execute(
        update(Payment)
        .where(Payment.invoice_id == invoice_id)
        .values(status="success")
    )
    await session.commit()


async def get_payment_by_id(session: AsyncSession, payment_id: int) -> Optional[Payment]:
    """Получить платеж по ID."""
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalars().first()