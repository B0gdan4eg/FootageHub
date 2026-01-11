"""Database initialization and migration utilities."""
import asyncio
import os
import subprocess
from datetime import datetime
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config

from shared.db.models import Base
from shared.db.session import async_engine

# Use /app/backups for Docker container (mounted to host ./backups)
BACKUP_DIR = os.getenv("BACKUP_DIR", "/opt/backups")


def _backup_database_sync():
    """
    Create PostgreSQL backup using pg_dump.
    Credentials are loaded from DATABASE_URL environment variable.
    Backups are saved to BACKUP_DIR (mounted volume outside container).
    """
    # Parse DATABASE_URL to extract connection parameters
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    # Parse URL: postgresql+asyncpg://user:password@host:port/dbname
    parsed = urlparse(database_url.replace("postgresql+asyncpg://", "postgresql://"))

    db_user = parsed.username or os.getenv("POSTGRES_USER", "postgres")
    db_password = parsed.password or os.getenv("POSTGRES_PASSWORD")
    db_host = parsed.hostname or "db"
    db_port = parsed.port or 5432
    db_name = parsed.path.lstrip("/") or os.getenv("POSTGRES_DB", "botdb")

    if not db_password:
        raise ValueError("Database password not found in DATABASE_URL or POSTGRES_PASSWORD")

    os.makedirs(BACKUP_DIR, exist_ok=True)

    filename = f"{db_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql"
    filepath = os.path.join(BACKUP_DIR, filename)

    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    print(f"🔄 Creating database backup: {filename}")
    print(f"📁 Backup location: {filepath}")

    # Run pg_dump
    subprocess.run(
        [
            "pg_dump",
            "-h",
            db_host,
            "-p",
            str(db_port),
            "-U",
            db_user,
            "-F",
            "c",  # custom format (compressed)
            "-b",  # include large objects
            "-f",
            filepath,
            db_name,
        ],
        env=env,
        check=True,
    )

    # Get file size
    file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
    print(f"✅ Backup created successfully: {filepath} ({file_size:.2f} MB)")

    return filepath


async def backup_database():
    """Create database backup asynchronously."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _backup_database_sync)


def _run_migrations_sync():
    """Run Alembic migrations synchronously."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


async def run_migrations():
    """Run database migrations asynchronously."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_migrations_sync)


async def create_tables():
    """Create all tables if they don't exist."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
