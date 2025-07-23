from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import Optional
import datetime

from db.models import Payment


async def create_payment(
    session: AsyncSession,
    user_id: int,
    amount: float,
    currency: str,
    payment_type: str,
    invoice_id: str,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        amount=amount,
        currency=currency,
        type=payment_type,
        invoice_id=invoice_id,
        status="pending",
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def get_payment_by_invoice_id(session: AsyncSession, invoice_id: str) -> Optional[Payment]:
    result = await session.execute(select(Payment).where(Payment.invoice_id == invoice_id))
    return result.scalars().first()


async def update_payment_status(session: AsyncSession, invoice_id: str, status: str) -> None:
    await session.execute(
        update(Payment)
        .where(Payment.invoice_id == invoice_id)
        .values(status=status)
    )
    await session.commit()

async def mark_payment_success(session: AsyncSession, invoice_id: str) -> None:
    await session.execute(
        update(Payment)
        .where(Payment.invoice_id == invoice_id)
        .values(status="success")
    )
    await session.commit()
    
async def get_payment_by_id(session: AsyncSession, payment_id: int) -> Optional[Payment]:
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalars().first()

async def mark_payment_as_paid(session: AsyncSession, payment: Payment) -> None:
    payment.status = "paid"
    payment.paid_at = datetime.datetime.utcnow()
    session.add(payment)
