"""
Download handlers module.

This module combines download functionality for Envato, Freepik, and Motion Array.
"""

from aiogram import Router

# Import from individual modules
from bot.handlers.download import envato, freepik, motion, validators
from bot.handlers.download.envato import ask_for_link, download_more, handle_link
from bot.handlers.download.freepik import (
    ask_for_freepik_link,
    download_more_freepik,
    handle_freepik_link,
)
from bot.handlers.download.motion import (
    ask_for_motion_link,
    download_more_motion,
    handle_motion_link,
)

# Re-export commonly used functions
from bot.handlers.download.validators import auto_delete_download_link, check_user_eligibility

# Combine all routers into one
router = Router()
router.include_router(envato.router)
router.include_router(freepik.router)
router.include_router(motion.router)

__all__ = [
    "router",
    "auto_delete_download_link",
    "check_user_eligibility",
    "ask_for_link",
    "handle_link",
    "download_more",
    "ask_for_freepik_link",
    "handle_freepik_link",
    "download_more_freepik",
    "ask_for_motion_link",
    "handle_motion_link",
    "download_more_motion",
]
