"""
Setup test database for integration tests.

This script creates the test database if it doesn't exist.
"""

import asyncio
import os

import asyncpg


async def setup_test_database():
    """Create test database if it doesn't exist."""
    # Connection params from environment or defaults
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    test_db_name = "footagehub_test"

    try:
        # Connect to default postgres database
        conn = await asyncpg.connect(
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database="postgres",
        )

        print(f"✓ Connected to PostgreSQL at {db_host}:{db_port}")

        # Check if test database exists
        result = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", test_db_name)

        if result:
            print(f"✓ Test database '{test_db_name}' already exists")
        else:
            # Create test database
            await conn.execute(f"CREATE DATABASE {test_db_name}")
            print(f"✓ Created test database '{test_db_name}'")

        await conn.close()
        print("\n✓ Test database is ready!")
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure PostgreSQL is running and credentials are correct.")
        print(f"Trying to connect to: {db_host}:{db_port} as user '{db_user}'")
        return False


if __name__ == "__main__":
    success = asyncio.run(setup_test_database())
    exit(0 if success else 1)
