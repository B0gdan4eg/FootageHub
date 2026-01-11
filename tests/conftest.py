"""
Global pytest fixtures for all tests.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from shared.db.models import Base

# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Removed deprecated event_loop fixture - pytest-asyncio handles this automatically


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async session for testing."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_telegram_user():
    """Mock Telegram user data."""
    return {
        "id": 123456789,
        "username": "test_user",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def mock_envato_url():
    """Mock Envato URL for testing."""
    return "https://elements.envato.com/test-item-12345"


@pytest.fixture
def mock_freepik_url():
    """Mock Freepik URL for testing."""
    return "https://www.freepik.com/premium-vector/test-vector-12345"
