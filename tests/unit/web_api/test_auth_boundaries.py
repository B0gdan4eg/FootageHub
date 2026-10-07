from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from shared.db.models import UserRole
from web_api.auth import router as auth
from web_api.routers import admin


def database(record):
    db = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = record
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PENDING", "CONFIRMED"])
async def test_expired_qr_cannot_mint_tokens(status, monkeypatch):
    record = SimpleNamespace(
        status=status, expires_at=datetime.utcnow() - timedelta(seconds=1), user_id=123
    )
    mint = Mock()
    monkeypatch.setattr(auth, "create_access_token", mint)
    result = await auth.qr_status("opaque-token", database(record))
    assert result == {"status": "EXPIRED"}
    mint.assert_not_called()


@pytest.mark.asyncio
async def test_confirmed_qr_is_consumed_once_under_row_lock(monkeypatch):
    record = SimpleNamespace(
        status="CONFIRMED", expires_at=datetime.utcnow() + timedelta(minutes=1), user_id=123
    )
    db = database(record)
    user = SimpleNamespace(
        id=123,
        phone_number=None,
        username=None,
        credits=0,
        ai_credits=0,
        role=UserRole.USER,
        referral_code=None,
    )
    repository = Mock()
    repository.get_by_id = AsyncMock(return_value=user)
    monkeypatch.setattr(auth, "UserRepository", Mock(return_value=repository))
    mint = Mock(return_value="issued-token")
    monkeypatch.setattr(auth, "create_access_token", mint)
    first = await auth.qr_status("opaque-token", db)
    assert first["status"] == "CONFIRMED" and first["access_token"] == "issued-token"
    assert record.status == "EXPIRED"
    assert await auth.qr_status("opaque-token", db) == {"status": "EXPIRED"}
    mint.assert_called_once()
    assert db.execute.call_args.args[0]._for_update_arg is not None


@pytest.mark.asyncio
async def test_expired_confirmed_bot_link_cannot_mint_tokens(monkeypatch):
    record = SimpleNamespace(
        status="CONFIRMED", expires_at=datetime.utcnow() - timedelta(seconds=1), bot_user_id=123
    )
    mint = Mock()
    monkeypatch.setattr(auth, "create_access_token", mint)
    assert await auth.get_link_status(1, SimpleNamespace(id=5), database(record)) == {
        "status": "EXPIRED"
    }
    mint.assert_not_called()


@pytest.mark.asyncio
async def test_manager_cannot_promote_self_to_admin(monkeypatch):
    user = SimpleNamespace(id=123, role=UserRole.MANAGER, credits=0, ai_credits=0)
    repository = Mock()
    repository.get_by_id = AsyncMock(return_value=user)
    monkeypatch.setattr(admin, "UserRepository", Mock(return_value=repository))
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await admin.update_user(123, admin.UpdateUserRequest(role="ADMIN"), user, db)
    assert exc.value.status_code == 403
    assert user.role == UserRole.MANAGER
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_manager_router_requires_current_privileged_role(monkeypatch):
    from media_bot.handlers import manager

    monkeypatch.setattr(manager, "is_admin", AsyncMock(return_value=False))
    role_check = AsyncMock(return_value=False)
    monkeypatch.setattr(manager, "is_manager", role_check)
    event = SimpleNamespace(from_user=SimpleNamespace(id=123))
    assert not await manager.ManagerAccessFilter()(event)
    role_check.return_value = True
    assert await manager.ManagerAccessFilter()(event)
