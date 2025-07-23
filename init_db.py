from db.models import Base
from db.session import engine
import asyncio

async def recreate_tables():
    async with engine.begin() as conn:
        # Удаляем все таблицы
        await conn.run_sync(Base.metadata.drop_all)
        # Создаем все таблицы заново
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(recreate_tables())
