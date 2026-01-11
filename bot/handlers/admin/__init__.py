"""
Admin handlers module.

This module combines all admin functionality from separate sub-modules.
"""

from aiogram import Router

# Import from individual modules
from bot.handlers.admin import (
    broadcast,
    cookies,
    core,
    database,
    limits,
    prices,
    roles,
    stats,
    subscriptions,
)
from bot.handlers.admin.broadcast import send_broadcast, start_broadcast
from bot.handlers.admin.cookies import receive_cookies_json, upload_cookies

# Re-export commonly used functions
from bot.handlers.admin.core import admin_panel, get_chat_id_command, is_admin
from bot.handlers.admin.database import (
    cancel_restore_db,
    export_db_callback,
    export_full_db_and_send,
    receive_restore_xlsx,
    restore_db_start,
)
from bot.handlers.admin.limits import ask_download_limit, set_download_limit
from bot.handlers.admin.prices import receive_price_json, upload_prices
from bot.handlers.admin.roles import assign_manager, assign_manager_start
from bot.handlers.admin.stats import show_stats
from bot.handlers.admin.subscriptions import (
    cancel_delete_subscriptions,
    confirm_delete_all_subscriptions,
    create_subscription_for_user,
    delete_all_subs_confirmed,
    give_subscription_start,
    receive_subscription_user_id,
)

# Combine all routers into one
router = Router()
router.include_router(core.router)
router.include_router(stats.router)
router.include_router(subscriptions.router)
router.include_router(roles.router)
router.include_router(prices.router)
router.include_router(database.router)
router.include_router(cookies.router)
router.include_router(limits.router)
router.include_router(broadcast.router)

__all__ = [
    "router",
    "is_admin",
    "show_stats",
    "give_subscription_start",
    "receive_subscription_user_id",
    "create_subscription_for_user",
    "get_chat_id_command",
    "admin_panel",
    "assign_manager_start",
    "assign_manager",
    "upload_prices",
    "receive_price_json",
    "export_full_db_and_send",
    "export_db_callback",
    "upload_cookies",
    "receive_cookies_json",
    "ask_download_limit",
    "set_download_limit",
    "start_broadcast",
    "send_broadcast",
    "confirm_delete_all_subscriptions",
    "delete_all_subs_confirmed",
    "cancel_delete_subscriptions",
    "restore_db_start",
    "receive_restore_xlsx",
    "cancel_restore_db",
]
