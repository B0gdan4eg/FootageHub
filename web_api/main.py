"""
FootageHub Web API

FastAPI application for the web version of FootageHub.
Runs separately from the Telegram bots on port 8080.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared import error_tracking, funnel_tracking
from web_api.auth.router import router as auth_router
from web_api.config import config, validate_security_config
from web_api.routers.admin import router as admin_router
from web_api.routers.ai import router as ai_router
from web_api.routers.downloads import router as downloads_router
from web_api.routers.payments import router as payments_router
from web_api.routers.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security_config()
    error_tracking.configure("web-api")
    try:
        yield
    finally:
        await error_tracking.shutdown()
        await funnel_tracking.shutdown()


app = FastAPI(
    title="FootageHub Web API",
    version="1.0.0",
    lifespan=lifespan,
    description="REST API для веб-версии FootageHub",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
app.add_middleware(error_tracking.TrackingHTTPMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(downloads_router, prefix="/api/downloads", tags=["downloads"])
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
app.include_router(payments_router, prefix="/api/payments", tags=["payments"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "footagehub-web-api"}


# Запуск: uvicorn web_api.main:app --host 0.0.0.0 --port 8080 --reload
