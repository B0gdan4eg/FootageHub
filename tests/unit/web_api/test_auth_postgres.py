"""Exercise login consumption against PostgreSQL enums and concurrent polling."""
import asyncio
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shared.db.models import Base, BotLinkRequest, QrLoginSession, User
from web_api.auth import router as auth


@pytest.mark.asyncio
async def test_confirmed_logins_commit_with_database_enums_and_issue_once(monkeypatch):
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Dedicated PostgreSQL test database is supplied by CI")
    if make_url(url).database != "footagehub_release_test":
        raise ValueError("Login test requires the dedicated footagehub_release_test database")
    monkeypatch.setattr(auth, "create_access_token", lambda user_id: "test-login-token")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            db.add_all([User(id=901001, credits=0), User(id=901002, credits=0)])
            await db.flush()
            expires = datetime.utcnow() + timedelta(minutes=5)
            db.add(
                QrLoginSession(
                    id=901003,
                    token="postgres-login-test",
                    status="CONFIRMED",
                    user_id=901002,
                    expires_at=expires,
                )
            )
            db.add(
                BotLinkRequest(
                    id=901004,
                    web_user_id=901001,
                    bot_user_id=901002,
                    status="CONFIRMED",
                    expires_at=expires,
                )
            )
            await db.commit()

        async def qr_poll():
            async with sessions() as db:
                return await auth.qr_status("postgres-login-test", db)

        async def link_poll():
            async with sessions() as db:
                return await auth.get_link_status(901004, await db.get(User, 901001), db)

        for poll in [qr_poll, link_poll]:
            results = await asyncio.gather(poll(), poll(), poll())
            assert sum("access_token" in result for result in results) == 1
            assert sorted(result["status"] for result in results) == [
                "CONFIRMED",
                "EXPIRED",
                "EXPIRED",
            ]
        async with sessions() as db:
            assert (await db.get(QrLoginSession, 901003)).status == "EXPIRED"
            assert (await db.get(BotLinkRequest, 901004)).status == "EXPIRED"
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()
