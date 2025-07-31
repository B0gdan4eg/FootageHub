import sys
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI
import uvicorn

from bot.config import BOT_TOKEN
from bot.handlers import start, download, info, admin, payment
from bot.webhook import cryptobot
from init_db import recreate_tables

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI()
app.include_router(cryptobot.router)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(info.router)
dp.include_router(download.router)
dp.include_router(payment.router)


async def start_uvicorn():
    """Запуск Uvicorn в асинхронном режиме"""
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info", ssl_certfile="cert.pem", ssl_keyfile="key.pem")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await recreate_tables()

    # Запускаем FastAPI и aiogram параллельно
    await asyncio.gather(
        start_uvicorn(),
        dp.start_polling(bot)
    )


if __name__ == "__main__":
    asyncio.run(main())