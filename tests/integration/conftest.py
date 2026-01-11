"""
Fixtures for integration tests.

These fixtures set up a real database with all tables and seed data.
"""

import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from shared.db.models import Base

# Load environment variables from .env file
load_dotenv()

# Use PostgreSQL for integration tests (same as production)
# Get from environment or use default test database
# Priority: TEST_DATABASE_URL > DATABASE_URL > default
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/footagehub_test"
    ),
)

# Global engine - created once for all tests
_global_engine = None


async def get_global_engine():
    """Get or create global engine."""
    global _global_engine
    if _global_engine is None:
        _global_engine = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=10,
            max_overflow=20,
        )
        # Create all tables once
        async with _global_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    return _global_engine


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Get the shared async engine for integration testing."""
    engine = await get_global_engine()
    yield engine
    # Don't dispose - we reuse it


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine):
    """Create async session for integration testing."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        # Clean up all tables before each test
        # Use TRUNCATE CASCADE to handle foreign keys
        try:
            await session.execute(text("TRUNCATE TABLE ai_logs CASCADE"))
            await session.execute(text("TRUNCATE TABLE user_bonuses CASCADE"))
            await session.execute(text("TRUNCATE TABLE bonus_types CASCADE"))
            await session.execute(text("TRUNCATE TABLE referral_logs CASCADE"))
            await session.execute(text("TRUNCATE TABLE referral_rewards CASCADE"))
            await session.execute(text("TRUNCATE TABLE credit_transactions CASCADE"))
            await session.execute(text("TRUNCATE TABLE users CASCADE"))
            await session.execute(text("TRUNCATE TABLE subscription_plans CASCADE"))
            await session.commit()
        except Exception as e:
            # Tables might not exist yet, that's okay
            await session.rollback()

        yield session

        # Rollback any uncommitted changes
        await session.rollback()
