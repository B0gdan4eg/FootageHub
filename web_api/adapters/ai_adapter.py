"""
AI generation adapter for web API.

Wraps ai_bot.services.AIService for use with web users.
Handles async generation lifecycle: PENDING → PROCESSING → SUCCESS/FAILED.
"""

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import AIGenerationLog, AIGenerationStatus, AIGenerationType
from shared.db.repositories.user_repository import UserRepository
from web_api.config import config


class WebAIAdapter:
    """
    Адаптер AI-генерации для web API.

    Создаёт AIGenerationLog (PENDING), запускает генерацию в фоне,
    позволяет проверять статус через poll_and_update().
    """

    # Стоимость генерации в AI-кредитах
    COSTS = {
        ("IMAGE", "nano-banana"): 4,
        ("VIDEO", "kling"): 100,
        ("VIDEO", "veo"): 80,
        ("VIDEO", "veo-quality"): 400,
        ("IMAGE_TO_VIDEO", "kling"): 100,
    }

    def __init__(self, db_user_id: int, db: AsyncSession):
        self._user_id = db_user_id
        self._db = db
        from ai_bot.services.ai_service import AIService  # noqa: PLC0415

        self._ai_service = AIService(api_key=config.KIE_AI_API_KEY)

    def _get_cost(self, gen_type: str, provider: str) -> int:
        """Получить стоимость генерации."""
        key = (gen_type.upper(), provider.lower())
        return self.COSTS.get(
            key, self.COSTS.get((gen_type.upper(), provider.split("-")[0].lower()), 4)
        )

    def _get_model_name(self, provider: str) -> str:
        mapping = {
            "nano-banana": "nano-banana-pro",
            "kling": "kling-2.6",
            "veo": "veo-3.1-fast",
            "veo-quality": "veo-3.1-quality",
        }
        return mapping.get(provider.lower(), provider)

    async def start_generation(
        self,
        gen_type: str,
        provider: str,
        prompt: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict:
        """
        Запустить генерацию в фоне.

        Returns:
            {task_id, status, credits_spent, estimated_seconds}
        """
        gen_type = gen_type.upper()
        if gen_type not in ("IMAGE", "VIDEO", "IMAGE_TO_VIDEO"):
            raise ValueError(f"Неизвестный тип генерации: {gen_type}")

        cost = self._get_cost(gen_type, provider)

        # Проверяем AI-кредиты
        user_repo = UserRepository(self._db)
        user = await user_repo.get_by_id(self._user_id)
        if not user:
            raise ValueError("Пользователь не найден")
        if user.ai_credits < cost:
            raise ValueError(f"Недостаточно AI-кредитов: нужно {cost}, у вас {user.ai_credits}")

        # Списываем кредиты
        await user_repo.deduct_ai_credits(self._user_id, cost)

        # Создаём запись в БД
        try:
            gen_type_enum = AIGenerationType(gen_type)
        except ValueError:
            gen_type_enum = AIGenerationType.IMAGE

        log = AIGenerationLog(
            user_id=self._user_id,
            provider=provider,
            model=self._get_model_name(provider),
            generation_type=gen_type_enum,
            prompt=prompt,
            parameters=parameters or {},
            status=AIGenerationStatus.PENDING,
            ai_credits_spent=cost,
        )
        self._db.add(log)
        await self._db.commit()
        await self._db.refresh(log)

        # Запускаем генерацию в фоне (asyncio task)
        asyncio.create_task(
            self._run_generation(log.id, gen_type, provider, prompt, parameters or {})
        )

        estimated = {"IMAGE": 30, "VIDEO": 120, "IMAGE_TO_VIDEO": 90}.get(gen_type, 60)

        return {
            "task_id": log.id,
            "status": "PENDING",
            "credits_spent": cost,
            "estimated_seconds": estimated,
        }

    async def _run_generation(
        self,
        log_id: int,
        gen_type: str,
        provider: str,
        prompt: str,
        parameters: dict,
    ) -> None:
        """Фоновая задача: выполнить генерацию и обновить лог."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession as AS
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker

        # Создаём отдельную сессию для фоновой задачи
        engine = create_async_engine(config.DATABASE_URL, echo=False)
        session_factory = sessionmaker(engine, class_=AS, expire_on_commit=False)

        async with session_factory() as session:
            result = await session.execute(
                select(AIGenerationLog).where(AIGenerationLog.id == log_id)
            )
            log = result.scalar_one_or_none()
            if not log:
                return

            log.status = AIGenerationStatus.PROCESSING
            await session.commit()

            try:
                if gen_type == "IMAGE":
                    result = await self._ai_service.generate_image(
                        prompt=prompt,
                        aspect_ratio=parameters.get("aspect_ratio", "1:1"),
                        resolution=parameters.get("resolution", "2K"),
                        output_format=parameters.get("output_format", "png"),
                    )
                else:
                    result = await self._ai_service.generate_video(
                        prompt=prompt,
                        provider_name=provider.split("-")[0],
                        sound=parameters.get("sound", False),
                        aspect_ratio=parameters.get("aspect_ratio", "16:9"),
                        duration=parameters.get("duration", "5"),
                        image_urls=parameters.get("image_urls"),
                    )

                if result.get("success"):
                    log.status = AIGenerationStatus.SUCCESS
                    log.result_url = result.get("result_url")
                    log.completed_at = datetime.utcnow()
                    log.processing_time_seconds = result.get("processing_time", 0)
                else:
                    log.status = AIGenerationStatus.FAILED
                    log.error_message = result.get("error", "Unknown error")
                    # Возвращаем кредиты
                    await self._refund_credits(session, log)

            except Exception as e:
                log.status = AIGenerationStatus.FAILED
                log.error_message = str(e)
                await self._refund_credits(session, log)

            await session.commit()
        await engine.dispose()

    async def _refund_credits(self, session: AsyncSession, log: AIGenerationLog) -> None:
        """Вернуть AI-кредиты при ошибке генерации."""
        from sqlalchemy import select as sa_select

        from shared.db.models import User

        result = await session.execute(sa_select(User).where(User.id == log.user_id))
        user = result.scalar_one_or_none()
        if user and log.ai_credits_spent:
            user.ai_credits += log.ai_credits_spent
            if user.ai_credits_used >= log.ai_credits_spent:
                user.ai_credits_used -= log.ai_credits_spent

    async def poll_and_update(self, log: AIGenerationLog) -> None:
        """
        Обновить статус генерации из Kie.ai API (вызывается при polling с фронтенда).

        Примечание: основная логика обновления происходит в фоновой задаче _run_generation.
        Этот метод нужен только если фоновая задача не завершила работу (перезапуск сервера).
        """
        # Если лог уже в финальном состоянии — ничего не делаем
        if log.status in (AIGenerationStatus.SUCCESS, AIGenerationStatus.FAILED):
            return

        # Если задача зависла (PROCESSING > 15 мин) — помечаем как FAILED
        if log.status == AIGenerationStatus.PROCESSING and log.created_at:
            elapsed = (datetime.utcnow() - log.created_at).total_seconds()
            if elapsed > 900:  # 15 минут
                log.status = AIGenerationStatus.FAILED
                log.error_message = "Превышено время ожидания генерации"
                await self._db.commit()
