"""
AI Bot Handlers

Message and callback handlers for AI Bot
"""
from aiogram import Router

from .admin import router as admin_router
from .credits import router as credits_router
from .image_generation import router as image_router
from .start import router as start_router
from .video_generation import router as video_router


def setup_handlers() -> Router:
    """Setup all handlers"""
    main_router = Router()

    # Include all routers (admin first for priority)
    main_router.include_router(admin_router)
    main_router.include_router(start_router)
    main_router.include_router(credits_router)
    main_router.include_router(image_router)
    main_router.include_router(video_router)

    return main_router
