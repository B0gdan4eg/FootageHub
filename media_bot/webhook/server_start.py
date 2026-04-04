import uvicorn
from fastapi import FastAPI

from media_bot.webhook import cryptobot, internal, webpay

# Создаём FastAPI приложение
app = FastAPI()
app.include_router(webpay.router)
app.include_router(cryptobot.router)
app.include_router(internal.router)


async def start_server():
    """Запуск FastAPI сервера без SSL (SSL обрабатывает Nginx)."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8443,  # Изменили с 443 на 8443
        # Убрали ssl_certfile и ssl_keyfile
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
