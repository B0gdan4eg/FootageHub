"""Users router: profile, history, subscriptions."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import AIGenerationLog, Download, Media, Subscription, User
from web_api.dependencies import get_current_user, get_db

router = APIRouter()


class UserProfile(BaseModel):
    id: int
    phone_number: str | None
    username: str | None
    credits: int
    ai_credits: int
    ai_credits_used: int
    role: str
    referral_code: str | None

    model_config = {"from_attributes": True}


class DownloadItem(BaseModel):
    id: int
    url: str
    service_type: str | None
    downloaded_at: str

    model_config = {"from_attributes": True}


class SubscriptionItem(BaseModel):
    id: int
    subscription_type: str
    service_type: str
    used_total: int
    total_limit: int | None
    used_today: int
    daily_limit: int | None
    end_date: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Профиль текущего пользователя."""
    return UserProfile(
        id=current_user.id,
        phone_number=current_user.phone_number,
        username=current_user.username,
        credits=current_user.credits,
        ai_credits=current_user.ai_credits,
        ai_credits_used=current_user.ai_credits_used,
        role=current_user.role.value,
        referral_code=current_user.referral_code,
    )


@router.get("/me/downloads")
async def get_download_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История скачиваний текущего пользователя."""
    offset = (page - 1) * per_page
    result = await db.execute(
        select(Download, Media)
        .join(Media, Download.media_id == Media.id)
        .where(Download.user_id == current_user.id)
        .order_by(Download.downloaded_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = result.all()
    items = [
        {
            "id": d.id,
            "url": m.url,
            "service_type": d.service_type.value if d.service_type else None,
            "downloaded_at": d.downloaded_at.isoformat() if d.downloaded_at else None,
        }
        for d, m in rows
    ]
    return {"items": items, "page": page, "per_page": per_page}


@router.get("/me/subscriptions")
async def get_subscriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Активные подписки текущего пользователя."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.is_active == True,  # noqa: E712
            Subscription.end_date > datetime.utcnow(),
        )
    )
    subs = result.scalars().all()
    return [
        {
            "id": s.id,
            "subscription_type": s.subscription_type.value,
            "service_type": s.service_type.value,
            "used_total": s.used_total,
            "total_limit": s.total_limit,
            "used_today": s.used_today,
            "daily_limit": s.daily_limit,
            "end_date": s.end_date.isoformat(),
            "is_active": s.is_active,
        }
        for s in subs
    ]


@router.get("/me/ai-generations")
async def get_ai_generations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История AI генераций текущего пользователя."""
    offset = (page - 1) * per_page
    result = await db.execute(
        select(AIGenerationLog)
        .where(AIGenerationLog.user_id == current_user.id)
        .order_by(AIGenerationLog.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": item.id,
                "provider": item.provider,
                "model": item.model,
                "generation_type": item.generation_type.value,
                "prompt": item.prompt,
                "status": item.status.value,
                "result_url": item.result_url,
                "ai_credits_spent": item.ai_credits_spent,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            for item in items
        ],
        "page": page,
        "per_page": per_page,
    }
