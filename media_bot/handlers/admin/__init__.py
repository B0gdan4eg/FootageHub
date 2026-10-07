"""
Admin handlers module.

This module combines all admin functionality from separate sub-modules.
"""

from aiogram import Router
from aiogram.filters import BaseFilter

# Import from individual modules
from media_bot.handlers.admin import (
    bonuses,
    broadcast,
    cookies,
    core,
    credits,
    database,
    limits,
    prices,
    roles,
    stats,
    subscriptions,
)
from media_bot.handlers.admin.broadcast import broadcast_start, send_broadcast
from media_bot.handlers.admin.cookies import receive_cookies_json, upload_cookies

# Re-export commonly used functions
from media_bot.handlers.admin.core import admin_panel, get_chat_id_command, is_admin
from media_bot.handlers.admin.database import (
    cancel_restore_db,
    export_db_callback,
    export_full_db_and_send,
    receive_restore_xlsx,
    restore_db_start,
)
from media_bot.handlers.admin.limits import ask_download_limit, set_download_limit
from media_bot.handlers.admin.prices import receive_price_json, upload_prices
from media_bot.handlers.admin.roles import assign_manager_start
from media_bot.handlers.admin.stats import show_stats
from media_bot.handlers.admin.subscriptions import (
    cancel_delete_subscriptions,
    confirm_delete_all_subscriptions,
    create_subscription_for_user,
    delete_all_subs_confirmed,
    give_subscription_start,
    receive_subscription_user_id,
)


# Combine all routers into one
class AdminAccessFilter(BaseFilter):
    async def __call__(self, event):
        return bool(event.from_user and await is_admin(event.from_user.id))


router = Router()
router.message.filter(AdminAccessFilter())
router.callback_query.filter(AdminAccessFilter())
router.include_router(core.router)
router.include_router(stats.router)
router.include_router(credits.router)
router.include_router(bonuses.router)
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
    "upload_prices",
    "receive_price_json",
    "export_full_db_and_send",
    "export_db_callback",
    "upload_cookies",
    "receive_cookies_json",
    "ask_download_limit",
    "set_download_limit",
    "broadcast_start",
    "send_broadcast",
    "confirm_delete_all_subscriptions",
    "delete_all_subs_confirmed",
    "cancel_delete_subscriptions",
    "restore_db_start",
    "receive_restore_xlsx",
    "cancel_restore_db",
]
