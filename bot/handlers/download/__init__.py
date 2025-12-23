"""
Download handlers module.

This module combines download functionality for Envato and Freepik.
"""

from aiogram import Router

# Import from individual modules
from bot.handlers.download import validators
from bot.handlers.download import envato
from bot.handlers.download import freepik

# Re-export commonly used functions
from bot.handlers.download.validators import auto_delete_download_link, check_user_eligibility
from bot.handlers.download.envato import ask_for_link, handle_link, download_more
from bot.handlers.download.freepik import (
    ask_for_freepik_link,
    handle_freepik_link,
    download_more_freepik,
)

# Combine all routers into one
router = Router()
router.include_router(envato.router)
router.include_router(freepik.router)

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
]
