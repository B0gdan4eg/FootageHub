"""Admin router: user management, statistics."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Download, Payment, Subscription, User, UserRole
from shared.db.repositories.user_repository import UserRepository
from web_api.dependencies import get_admin_user, get_db

router = APIRouter()


class UpdateUserRequest(BaseModel):
    role: str | None = None
    credits: int | None = None
    ai_credits: int | None = None


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str | None = None,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Список пользователей с поиском."""
    query = select(User).order_by(User.created_at.desc())

    if search:
        query = query.where(
            User.username.ilike(f"%{search}%") | User.phone_number.ilike(f"%{search}%")
        )

    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    users = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": u.id,
                "tg_id": u.tg_id,
                "phone_number": u.phone_number,
                "username": u.username,
                "role": u.role.value,
                "credits": u.credits,
                "ai_credits": u.ai_credits,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Детали пользователя."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return {
        "id": user.id,
        "tg_id": user.tg_id,
        "phone_number": user.phone_number,
        "username": user.username,
        "role": user.role.value,
        "credits": user.credits,
        "ai_credits": user.ai_credits,
        "ai_credits_used": user.ai_credits_used,
        "referral_code": user.referral_code,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновить роль и/или кредиты пользователя."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if body.role:
        try:
            user.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Неверная роль: {body.role}")

    if body.credits is not None:
        user.credits += body.credits

    if body.ai_credits is not None:
        user.ai_credits += body.ai_credits

    await db.commit()
    return {"ok": True, "user_id": user_id}


@router.get("/stats")
async def get_stats(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Общая статистика платформы."""
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Всего пользователей
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

    # Скачиваний сегодня
    downloads_today = (
        await db.execute(
            select(func.count()).select_from(Download).where(Download.downloaded_at >= today_start)
        )
    ).scalar() or 0

    # Активных подписок
    active_subs = (
        await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(
                Subscription.is_active == True,  # noqa: E712
                Subscription.end_date > now,
            )
        )
    ).scalar() or 0

    # Доход за последние 30 дней
    revenue_30d = (
        await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "success",
                Payment.created_at >= now - timedelta(days=30),
            )
        )
    ).scalar() or 0

    return {
        "total_users": total_users,
        "downloads_today": downloads_today,
        "active_subscriptions": active_subs,
        "revenue_30d": float(revenue_30d),
    }
