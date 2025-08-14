import uvicorn
from fastapi import FastAPI
from bot.webhook import cryptobot

# Создаём FastAPI приложение
app = FastAPI()
app.include_router(cryptobot.router)

async def start_server():
    """Запуск FastAPI сервера с SSL."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=443,
        ssl_certfile="/app/ssl/cert.pem",
        ssl_keyfile="/app/ssl/key.pem",
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()
