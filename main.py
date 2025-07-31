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
app.include_router(cryptobot.app)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start.router)
dp.include_router(admin.router)
dp.include_router(info.router)
dp.include_router(download.router)
dp.include_router(payment.router)


async def main():
    await uvicorn.run("main:app", host="0.0.0.0", port=443, ssl_keyfile="key.pem", ssl_certfile="cert.pem")
    await recreate_tables() 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

