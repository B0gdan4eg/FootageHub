#!/usr/bin/env python3
"""
Script to restore PostgreSQL database from backup.

Usage:
    python scripts/restore_backup.py backups/botdb_2025-11-18_12-00-00.sql
"""
import subprocess
import os
import sys
from urllib.parse import urlparse
from pathlib import Path


def restore_database(backup_file: str):
    """
    Restore PostgreSQL database from backup file.

    Args:
        backup_file: Path to backup file (.sql)
    """
    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        sys.exit(1)

    # Parse DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)

    parsed = urlparse(database_url.replace("postgresql+asyncpg://", "postgresql://"))

    db_user = parsed.username or os.getenv("POSTGRES_USER", "postgres")
    db_password = parsed.password or os.getenv("POSTGRES_PASSWORD")
    db_host = parsed.hostname or "db"
    db_port = parsed.port or 5432
    db_name = parsed.path.lstrip("/") or os.getenv("POSTGRES_DB", "botdb")

    if not db_password:
        print("❌ Database password not found")
        sys.exit(1)

    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    print(f"🔄 Restoring database from: {backup_file}")
    print(f"📊 Database: {db_name}")
    print(f"🖥️  Host: {db_host}:{db_port}")
    print()
    print("⚠️  WARNING: This will DROP and recreate the database!")

    # Ask for confirmation
    if os.isatty(sys.stdin.fileno()):  # If running interactively
        response = input("Continue? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            print("❌ Restore cancelled")
            sys.exit(0)

    try:
        # Drop existing database
        print("🗑️  Dropping existing database...")
        subprocess.run(
            [
                "psql",
                "-h", db_host,
                "-p", str(db_port),
                "-U", db_user,
                "-d", "postgres",  # Connect to postgres DB to drop target DB
                "-c", f"DROP DATABASE IF EXISTS {db_name};"
            ],
            env=env,
            check=True,
            capture_output=True
        )

        # Create new database
        print("🔨 Creating new database...")
        subprocess.run(
            [
                "psql",
                "-h", db_host,
                "-p", str(db_port),
                "-U", db_user,
                "-d", "postgres",
                "-c", f"CREATE DATABASE {db_name};"
            ],
            env=env,
            check=True,
            capture_output=True
        )

        # Restore from backup
        print(f"📥 Restoring from backup...")
        subprocess.run(
            [
                "pg_restore",
                "-h", db_host,
                "-p", str(db_port),
                "-U", db_user,
                "-d", db_name,
                "-v",  # Verbose
                backup_file
            ],
            env=env,
            check=True
        )

        # Get file size
        file_size = os.path.getsize(backup_file) / (1024 * 1024)  # MB
        print()
        print(f"✅ Database restored successfully from {backup_file} ({file_size:.2f} MB)")

    except subprocess.CalledProcessError as e:
        print(f"❌ Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore_backup.py <backup_file>")
        print()
        print("Available backups:")
        backup_dir = Path("backups")
        if backup_dir.exists():
            backups = sorted(backup_dir.glob("*.sql"), reverse=True)
            for backup in backups[:10]:  # Show last 10 backups
                size_mb = backup.stat().st_size / (1024 * 1024)
                print(f"  - {backup.name} ({size_mb:.2f} MB)")
        else:
            print("  No backups found in ./backups/")
        sys.exit(1)

    backup_file = sys.argv[1]
    restore_database(backup_file)
