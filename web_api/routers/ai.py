"""AI generation router: image, video, image-to-video."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import AIGenerationLog, User
from web_api.adapters.ai_adapter import WebAIAdapter
from web_api.dependencies import get_current_user, get_db

router = APIRouter()


class GenerateRequest(BaseModel):
    type: str  # IMAGE | VIDEO | IMAGE_TO_VIDEO
    provider: str  # nano-banana | kling | veo
    prompt: str
    parameters: dict = {}


@router.get("/pricing")
async def get_pricing():
    """Получить цены на модели AI (из Kie.ai API)."""
    from ai_bot.services.pricing_service import PricingService
    from web_api.config import config

    pricing = PricingService(config.KIE_AI_API_KEY)
    try:
        prices = await pricing.get_pricing()
    except Exception:
        # fallback к статическим ценам
        prices = {
            "nano-banana": {"IMAGE": 4},
            "kling": {"VIDEO": 100},
            "veo-fast": {"VIDEO": 80},
            "veo-quality": {"VIDEO": 400},
        }
    return prices


@router.post("/generate")
async def generate(
    body: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Запустить AI генерацию. Возвращает task_id для polling."""
    adapter = WebAIAdapter(current_user.id, db)
    try:
        result = await adapter.start_generation(
            gen_type=body.type,
            provider=body.provider,
            prompt=body.prompt,
            parameters=body.parameters,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


@router.get("/status/{task_id}")
async def get_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить статус задачи генерации."""
    result = await db.execute(
        select(AIGenerationLog).where(
            AIGenerationLog.id == task_id,
            AIGenerationLog.user_id == current_user.id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Если задача ещё в процессе — обновляем статус через Kie.ai
    if log.status.value in ("PENDING", "PROCESSING") and log.parameters:
        adapter = WebAIAdapter(current_user.id, db)
        await adapter.poll_and_update(log)

    return {
        "task_id": log.id,
        "status": log.status.value,
        "result_url": log.result_url,
        "error_message": log.error_message,
        "ai_credits_spent": log.ai_credits_spent,
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
    }


@router.get("/history")
async def get_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """История последних 20 генераций."""
    result = await db.execute(
        select(AIGenerationLog)
        .where(AIGenerationLog.user_id == current_user.id)
        .order_by(AIGenerationLog.created_at.desc())
        .limit(20)
    )
    items = result.scalars().all()
    return [
        {
            "task_id": item.id,
            "provider": item.provider,
            "model": item.model,
            "type": item.generation_type.value,
            "status": item.status.value,
            "result_url": item.result_url,
            "ai_credits_spent": item.ai_credits_spent,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]
