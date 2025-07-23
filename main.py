import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN
from bot.handlers import start, download, info
from fastapi import FastAPI
from bot.webhook import cryptobot
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI()
app.include_router(cryptobot.router)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start.router)
dp.include_router(info.router)
dp.include_router(download.router)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())