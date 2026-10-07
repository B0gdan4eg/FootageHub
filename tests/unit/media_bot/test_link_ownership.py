from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from media_bot.handlers.link_account import owns_link_request


@pytest.mark.asyncio
async def test_link_confirmation_requires_target_telegram_owner():
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(tg_id=123)
    req = SimpleNamespace(bot_user_id=456)
    assert await owns_link_request(session, req, 123)
    assert not await owns_link_request(session, req, 789)
    session.get.return_value = None
    assert not await owns_link_request(session, req, 123)
