"""Exercise real PostgreSQL row locks, not SQLite's ignored FOR UPDATE clauses."""
import asyncio
import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shared.db.models import Base, Payment, Subscription, User
from web_api.routers.payments import _process_web_payment


@pytest.mark.asyncio
async def test_simultaneous_provider_retries_credit_once():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Dedicated PostgreSQL test database is supplied by CI")
    if make_url(url).database != "footagehub_release_test":
        raise ValueError("Concurrency test requires the dedicated footagehub_release_test database")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add(User(id=900100, credits=0))
            await db.flush()
            db.add(
                Payment(
                    id=900200,
                    user_id=900100,
                    amount=10,
                    currency="USDT",
                    status="pending",
                    invoice_id="WEBUSER_concurrency_test",
                    plan_key="monthly_50",
                )
            )
            await db.commit()

        async def deliver():
            async with sessions() as db:
                await _process_web_payment(
                    "WEBUSER_concurrency_test", db, "cryptobot", "10", "USDT"
                )

        await asyncio.gather(deliver(), deliver(), deliver())
        async with sessions() as db:
            assert (await db.get(User, 900100)).credits == 50
            assert (await db.get(Payment, 900200)).status == "success"
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Subscription)
                    .where(Subscription.payment_id == 900200)
                )
                == 1
            )
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()
