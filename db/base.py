import subprocess
import os
from datetime import datetime
from alembic import command
from alembic.config import Config
import asyncio

BACKUP_DIR = os.path.join(os.getcwd(), "backups")  # папка backups в текущей директории

def _backup_database_sync():
    # Настройки подключения — замени на свои реальные данные
    db_user = "botuser"
    db_password = "Marli5450005"
    db_host = "db"
    db_port = "5432"
    db_name = "botdb"

    os.makedirs(BACKUP_DIR, exist_ok=True)

    filename = f"{db_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.sql"
    filepath = os.path.join(BACKUP_DIR, filename)

    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    # Запускаем pg_dump
    subprocess.run(
        [
            "pg_dump",
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-F", "c",  # custom format (сжатый)
            "-b",       # большие объекты
            "-f", filepath,
            db_name
        ],
        env=env,
        check=True
    )

    print(f"✅ Резервная копия базы создана: {filepath}")

async def backup_database():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _backup_database_sync)


def _run_migrations_sync():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

async def run_migrations():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_migrations_sync)
