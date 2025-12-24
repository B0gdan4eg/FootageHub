"""
AI Bot Handlers

Message and callback handlers for AI Bot
"""
from aiogram import Router
from .start import router as start_router


def setup_handlers() -> Router:
    """Setup all handlers"""
    main_router = Router()

    # Include all routers
    main_router.include_router(start_router)

    return main_router
