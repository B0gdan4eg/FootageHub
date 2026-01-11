"""
Setup and initialize staging database with test data.

This script:
1. Applies all Alembic migrations
2. Seeds bonus types
3. Creates test users with different configurations
4. Creates test subscriptions
5. Sets up referral relationships

Usage:
    python scripts/setup_staging_db.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shared.core.logger import get_logger
from shared.db.models import (
    AIGenerationLog,
    BonusType,
    ReferralReward,
    Subscription,
    User,
    UserBonus,
)

logger = get_logger(__name__)


async def get_session() -> AsyncSession:
    """Create database session."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")

    engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


async def create_test_users(session: AsyncSession):
    """Create test users with different configurations."""
    logger.info("Creating test users...")

    test_users = [
        # Admin user
        {
            "user_id": 111111111,
            "username": "staging_admin",
            "credits": 1000,
            "ai_credits": 500,
            "role": "admin",
        },
        # Regular users with various states
        {
            "user_id": 222222222,
            "username": "test_user_1",
            "credits": 100,
            "ai_credits": 50,
        },
        {
            "user_id": 333333333,
            "username": "test_user_2",
            "credits": 50,
            "ai_credits": 25,
        },
        {
            "user_id": 444444444,
            "username": "test_user_3",
            "credits": 10,
            "ai_credits": 5,
        },
        # User with no credits (for testing credit purchase)
        {
            "user_id": 555555555,
            "username": "poor_user",
            "credits": 0,
            "ai_credits": 0,
        },
        # User with subscription
        {
            "user_id": 666666666,
            "username": "vip_user",
            "credits": 500,
            "ai_credits": 200,
        },
        # Referrer user
        {
            "user_id": 777777777,
            "username": "referrer",
            "credits": 200,
            "ai_credits": 100,
        },
        # Referred user
        {
            "user_id": 888888888,
            "username": "referred",
            "credits": 50,
            "ai_credits": 25,
        },
    ]

    for user_data in test_users:
        # Check if user already exists
        result = await session.execute(select(User).where(User.tg_id == user_data["user_id"]))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.info(f"User {user_data['username']} already exists, skipping...")
            continue

        # Rename user_id to tg_id for User model and filter only valid fields
        from shared.db.models import UserRole

        user_dict = {
            "tg_id": user_data["user_id"],
            "username": user_data.get("username"),
            "credits": user_data.get("credits", 0),
            "ai_credits": user_data.get("ai_credits", 0),
            "ai_credits_used": 0,
        }

        # Set role if specified
        if "role" in user_data:
            user_dict["role"] = UserRole[user_data["role"].upper()]

        user = User(**user_dict)
        session.add(user)
        logger.info(f"Created user: {user_data['username']} (ID: {user_data['user_id']})")

    await session.commit()
    logger.info(f"✅ Created {len(test_users)} test users")


async def create_test_subscriptions(session: AsyncSession):
    """Create test subscriptions for some users."""
    logger.info("Creating test subscriptions...")

    # Get VIP user by tg_id
    result = await session.execute(select(User).where(User.tg_id == 666666666))
    vip_user = result.scalar_one_or_none()

    if vip_user:
        from shared.db.models import SubscriptionType

        # VIP user gets MONTHLY_50 subscription
        vip_subscription = Subscription(
            user_id=vip_user.id,
            subscription_type=SubscriptionType.MONTHLY_50,
            is_active=True,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            total_limit=50,
            used_total=0,
        )
        session.add(vip_subscription)
        logger.info(f"Created subscription for VIP user")

    await session.commit()
    logger.info("✅ Created test subscriptions")


async def create_test_referrals(session: AsyncSession):
    """Create test referral relationships."""
    logger.info("Creating test referrals...")

    # Get users by tg_id
    result = await session.execute(select(User).where(User.tg_id == 777777777))
    referrer = result.scalar_one_or_none()

    result = await session.execute(select(User).where(User.tg_id == 888888888))
    referred = result.scalar_one_or_none()

    if referrer and referred:
        from shared.db.models import ReferralRewardStatus, ReferralTriggerType

        # User 777777777 (referrer) referred user 888888888
        referral = ReferralReward(
            referrer_id=referrer.id,
            referred_id=referred.id,
            status=ReferralRewardStatus.COMPLETED,
            reward_type="credits",
            reward_value=10,
            trigger_type=ReferralTriggerType.REGISTRATION,
            condition_met=True,
            created_at=datetime.utcnow() - timedelta(days=5),
            completed_at=datetime.utcnow() - timedelta(days=5),
            rewarded_at=datetime.utcnow() - timedelta(days=5),
        )
        session.add(referral)
        logger.info(f"Created referral relationship")

    await session.commit()
    logger.info("✅ Created test referrals")


async def create_test_bonuses(session: AsyncSession):
    """Create test bonus records for users."""
    logger.info("Creating test bonuses...")

    # Get bonus types
    result = await session.execute(select(BonusType))
    bonus_types = {bt.code: bt for bt in result.scalars().all()}

    if not bonus_types:
        logger.warning("No bonus types found! Run migrations first.")
        return

    # Get test users by tg_id
    result = await session.execute(select(User).where(User.tg_id == 222222222))
    test_user_1 = result.scalar_one_or_none()

    result = await session.execute(select(User).where(User.tg_id == 333333333))
    test_user_2 = result.scalar_one_or_none()

    # Give FIRST_LOGIN bonus to test_user_1
    if test_user_1 and "FIRST_LOGIN" in bonus_types:
        from shared.db.models import BonusStatus

        bonus = UserBonus(
            user_id=test_user_1.id,
            bonus_type_id=bonus_types["FIRST_LOGIN"].id,
            status=BonusStatus.COMPLETED,
            credits_granted=bonus_types["FIRST_LOGIN"].credits_amount,
            ai_credits_granted=bonus_types["FIRST_LOGIN"].ai_credits_amount,
            created_at=datetime.utcnow() - timedelta(days=3),
            completed_at=datetime.utcnow() - timedelta(days=3),
        )
        session.add(bonus)

    # Give CHANNEL_SUBSCRIPTION bonus to test_user_2
    if test_user_2 and "CHANNEL_SUBSCRIPTION" in bonus_types:
        from shared.db.models import BonusStatus

        bonus = UserBonus(
            user_id=test_user_2.id,
            bonus_type_id=bonus_types["CHANNEL_SUBSCRIPTION"].id,
            status=BonusStatus.COMPLETED,
            credits_granted=bonus_types["CHANNEL_SUBSCRIPTION"].credits_amount,
            ai_credits_granted=bonus_types["CHANNEL_SUBSCRIPTION"].ai_credits_amount,
            extra_data={"channel_id": "@footagehub_staging_channel"},
            created_at=datetime.utcnow() - timedelta(days=1),
            completed_at=datetime.utcnow() - timedelta(days=1),
        )
        session.add(bonus)

    await session.commit()
    logger.info("✅ Created test bonuses")


async def create_test_ai_logs(session: AsyncSession):
    """Create test AI generation logs."""
    logger.info("Creating test AI generation logs...")

    # Get test users by tg_id
    result = await session.execute(select(User).where(User.tg_id == 222222222))
    test_user_1 = result.scalar_one_or_none()

    result = await session.execute(select(User).where(User.tg_id == 333333333))
    test_user_2 = result.scalar_one_or_none()

    if not test_user_1 or not test_user_2:
        logger.warning("Test users not found, skipping AI logs creation")
        return

    from shared.db.models import AIGenerationStatus, AIGenerationType

    # Successful image generation
    log1 = AIGenerationLog(
        user_id=test_user_1.id,
        provider="KIE_AI",
        model="nano-banana",
        generation_type=AIGenerationType.IMAGE,
        prompt="Beautiful sunset over mountains",
        parameters={"aspect_ratio": "16:9", "quality": "high"},
        status=AIGenerationStatus.SUCCESS,
        result_url="https://example.com/generated_image.png",
        ai_credits_spent=2,
        processing_time_seconds=15,
        created_at=datetime.utcnow() - timedelta(hours=2),
        completed_at=datetime.utcnow() - timedelta(hours=2),
    )
    session.add(log1)

    # Successful video generation
    log2 = AIGenerationLog(
        user_id=test_user_1.id,
        provider="KIE_AI",
        model="kling-2.6",
        generation_type=AIGenerationType.VIDEO,
        prompt="A cat playing with a ball",
        parameters={"duration": 5, "resolution": "720p"},
        status=AIGenerationStatus.SUCCESS,
        result_url="https://example.com/generated_video.mp4",
        ai_credits_spent=10,
        processing_time_seconds=120,
        created_at=datetime.utcnow() - timedelta(hours=1),
        completed_at=datetime.utcnow() - timedelta(hours=1),
    )
    session.add(log2)

    # Failed generation
    log3 = AIGenerationLog(
        user_id=test_user_2.id,
        provider="KIE_AI",
        model="veo-3.1",
        generation_type=AIGenerationType.VIDEO,
        prompt="Invalid prompt test",
        parameters={},
        status=AIGenerationStatus.FAILED,
        error_message="API rate limit exceeded",
        ai_credits_spent=0,  # No charge on failure
        processing_time_seconds=5,
        created_at=datetime.utcnow() - timedelta(minutes=30),
    )
    session.add(log3)

    await session.commit()
    logger.info("✅ Created test AI generation logs")


async def verify_setup(session: AsyncSession):
    """Verify that all test data was created successfully."""
    logger.info("\n" + "=" * 60)
    logger.info("VERIFYING STAGING DATABASE SETUP")
    logger.info("=" * 60)

    # Count users
    result = await session.execute(select(User))
    users = result.scalars().all()
    logger.info(f"✅ Users: {len(users)}")

    # Count subscriptions
    result = await session.execute(select(Subscription))
    subscriptions = result.scalars().all()
    logger.info(f"✅ Subscriptions: {len(subscriptions)}")

    # Count referrals
    result = await session.execute(select(ReferralReward))
    referrals = result.scalars().all()
    logger.info(f"✅ Referrals: {len(referrals)}")

    # Count bonuses
    result = await session.execute(select(UserBonus))
    bonuses = result.scalars().all()
    logger.info(f"✅ Bonuses: {len(bonuses)}")

    # Count AI logs
    result = await session.execute(select(AIGenerationLog))
    ai_logs = result.scalars().all()
    logger.info(f"✅ AI Generation Logs: {len(ai_logs)}")

    logger.info("=" * 60)
    logger.info("STAGING DATABASE READY! 🚀")
    logger.info("=" * 60)

    # Print test user credentials
    logger.info("\n📝 TEST USER CREDENTIALS:")
    logger.info("-" * 60)
    for user in users:
        role_name = user.role.value if hasattr(user.role, "value") else str(user.role)
        logger.info(
            f"  {user.username:20} | TG_ID: {user.tg_id} | {role_name} | "
            f"Credits: {user.credits}/{user.ai_credits}"
        )
    logger.info("-" * 60)


async def main():
    """Main setup function."""
    logger.info("🚀 Starting staging database setup...")

    # Get database session
    async for session in get_session():
        try:
            # Create test data
            await create_test_users(session)
            await create_test_subscriptions(session)
            await create_test_referrals(session)
            await create_test_bonuses(session)
            await create_test_ai_logs(session)

            # Verify setup
            await verify_setup(session)

        except Exception as e:
            logger.error(f"❌ Error during setup: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    # Load .env.staging
    from dotenv import load_dotenv

    env_file = project_root / ".env.staging"
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"Loaded environment from {env_file}")
    else:
        logger.warning(f".env.staging not found at {env_file}")

    asyncio.run(main())
