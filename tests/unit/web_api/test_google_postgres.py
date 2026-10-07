import asyncio
import os
from datetime import datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from shared.db.models import AuthIdentity, Base, GoogleOAuthState, User
from web_api.auth import google


@pytest.mark.asyncio
async def test_additive_migration_and_concurrent_google_sign_in(monkeypatch):
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Dedicated PostgreSQL database is supplied by CI")
    if make_url(url).database != "footagehub_release_test":
        raise ValueError("Google migration test requires the dedicated test database")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(google.config, "GOOGLE_AUTH_ENABLED", True)
    monkeypatch.setattr(google.config, "GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(google.config, "GOOGLE_CLIENT_SECRET", "test-secret")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            old_tables = [
                table
                for table in Base.metadata.sorted_tables
                if table.name not in {"auth_identities", "google_oauth_states"}
            ]
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=old_tables)
            )
        async with sessions() as db:
            db.add(User(id=123456, tg_id=123456, credits=47, ai_credits=9))
            await db.commit()
        await asyncio.to_thread(command.stamp, Config("alembic.ini"), "f1a2b3c4d5e6")
        await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "ab12cd34ef56")
        claims = {"sub": "concurrent-google-subject", "email": "user@example.test"}

        async def sign_in():
            async with sessions() as db:
                return (await google.attach_identity(db, claims)).id

        ids = await asyncio.gather(sign_in(), sign_in(), sign_in())
        assert len(set(ids)) == 1
        async with sessions() as db:
            assert await db.scalar(select(func.count()).select_from(AuthIdentity)) == 1
            assert await db.scalar(select(func.count()).select_from(User)) == 2
            original = await db.get(User, 123456)
            assert (original.credits, original.ai_credits, original.tg_id) == (47, 9, 123456)
            db.add(
                GoogleOAuthState(
                    state_hash=google.digest("state"),
                    binding_hash=google.digest("binding"),
                    nonce="nonce",
                    verifier="verifier",
                    return_path="/dashboard",
                    expires_at=datetime.utcnow() + timedelta(minutes=5),
                )
            )
            await db.commit()

        async def callback():
            async with sessions() as db:
                request = Request(
                    {"type": "http", "headers": [(b"cookie", b"google_binding=binding")]}
                )
                result = await google.google_callback(request, "state", "", "access_denied", db)
                return result.headers["location"]

        results = await asyncio.gather(callback(), callback())
        assert sorted(results) == [
            "/auth?google_error=cancelled",
            "/auth?google_error=invalid_session",
        ]
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await engine.dispose()
