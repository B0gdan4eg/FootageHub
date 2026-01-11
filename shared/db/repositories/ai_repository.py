"""
AI Repository - управление логами AI генераций.

Реализует паттерн Repository для работы с моделью AIGenerationLog.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import AIGenerationLog, AIGenerationStatus, AIGenerationType
from shared.db.repositories.base import BaseRepository


class AIRepository(BaseRepository[AIGenerationLog]):
    """Репозиторий для управления AI генерациями"""

    def __init__(self, session: AsyncSession):
        super().__init__(AIGenerationLog, session)

    async def create_generation_log(
        self,
        user_id: int,
        provider: str,
        model: str,
        generation_type: AIGenerationType,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None,
        ai_credits_spent: int = 1,
    ) -> AIGenerationLog:
        """
        Создать лог AI генерации.

        Args:
            user_id: ID пользователя
            provider: Провайдер (KIE_AI, KLING, VEO)
            model: Модель (nano-banana, kling-2.6, veo-3.1)
            generation_type: Тип генерации (IMAGE, VIDEO, IMAGE_TO_VIDEO)
            prompt: Промпт для генерации
            parameters: Параметры генерации (JSON)
            ai_credits_spent: Количество потраченных AI кредитов

        Returns:
            Созданный лог
        """
        log = AIGenerationLog(
            user_id=user_id,
            provider=provider,
            model=model,
            generation_type=generation_type,
            prompt=prompt,
            parameters=parameters or {},
            status=AIGenerationStatus.PENDING,
            ai_credits_spent=ai_credits_spent,
        )

        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def update_generation_log(
        self,
        log_id: int,
        status: AIGenerationStatus,
        result_url: Optional[str] = None,
        error_message: Optional[str] = None,
        processing_time_seconds: Optional[int] = None,
    ) -> AIGenerationLog:
        """
        Обновить статус генерации.

        Args:
            log_id: ID лога
            status: Новый статус
            result_url: URL результата
            error_message: Сообщение об ошибке
            processing_time_seconds: Время обработки в секундах

        Returns:
            Обновленный лог
        """
        log = await self.get_by_id(log_id)
        if not log:
            raise ValueError(f"Generation log {log_id} not found")

        log.status = status

        if result_url:
            log.result_url = result_url

        if error_message:
            log.error_message = error_message

        if processing_time_seconds is not None:
            log.processing_time_seconds = processing_time_seconds

        if status in (AIGenerationStatus.SUCCESS, AIGenerationStatus.FAILED):
            log.completed_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def mark_as_processing(self, log_id: int) -> AIGenerationLog:
        """
        Отметить генерацию как обрабатывающуюся.

        Args:
            log_id: ID лога

        Returns:
            Обновленный лог
        """
        return await self.update_generation_log(log_id=log_id, status=AIGenerationStatus.PROCESSING)

    async def mark_as_success(
        self, log_id: int, result_url: str, processing_time_seconds: Optional[int] = None
    ) -> AIGenerationLog:
        """
        Отметить генерацию как успешную.

        Args:
            log_id: ID лога
            result_url: URL результата
            processing_time_seconds: Время обработки

        Returns:
            Обновленный лог
        """
        return await self.update_generation_log(
            log_id=log_id,
            status=AIGenerationStatus.SUCCESS,
            result_url=result_url,
            processing_time_seconds=processing_time_seconds,
        )

    async def mark_as_failed(
        self, log_id: int, error_message: str, processing_time_seconds: Optional[int] = None
    ) -> AIGenerationLog:
        """
        Отметить генерацию как провалившуюся.

        Args:
            log_id: ID лога
            error_message: Сообщение об ошибке
            processing_time_seconds: Время обработки

        Returns:
            Обновленный лог
        """
        return await self.update_generation_log(
            log_id=log_id,
            status=AIGenerationStatus.FAILED,
            error_message=error_message,
            processing_time_seconds=processing_time_seconds,
        )

    # ==================== ПОЛУЧЕНИЕ ЛОГОВ ====================

    async def get_user_generations(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        status: Optional[AIGenerationStatus] = None,
        generation_type: Optional[AIGenerationType] = None,
    ) -> List[AIGenerationLog]:
        """
        Получить генерации пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            offset: Смещение
            status: Фильтр по статусу
            generation_type: Фильтр по типу генерации

        Returns:
            Список логов генераций
        """
        query = select(AIGenerationLog).where(AIGenerationLog.user_id == user_id)

        if status:
            query = query.where(AIGenerationLog.status == status)

        if generation_type:
            query = query.where(AIGenerationLog.generation_type == generation_type)

        query = query.order_by(desc(AIGenerationLog.created_at)).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent_generations(self, user_id: int, hours: int = 24) -> List[AIGenerationLog]:
        """
        Получить последние генерации пользователя за период.

        Args:
            user_id: ID пользователя
            hours: Период в часах

        Returns:
            Список логов генераций
        """
        since = datetime.utcnow() - timedelta(hours=hours)

        query = (
            select(AIGenerationLog)
            .where(and_(AIGenerationLog.user_id == user_id, AIGenerationLog.created_at >= since))
            .order_by(desc(AIGenerationLog.created_at))
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pending_generations(
        self, user_id: Optional[int] = None, older_than_minutes: int = 60
    ) -> List[AIGenerationLog]:
        """
        Получить зависшие генерации (pending/processing дольше заданного времени).

        Args:
            user_id: ID пользователя (опционально)
            older_than_minutes: Период в минутах

        Returns:
            Список зависших генераций
        """
        since = datetime.utcnow() - timedelta(minutes=older_than_minutes)

        conditions = [
            AIGenerationLog.status.in_([AIGenerationStatus.PENDING, AIGenerationStatus.PROCESSING]),
            AIGenerationLog.created_at < since,
        ]

        if user_id:
            conditions.append(AIGenerationLog.user_id == user_id)

        query = select(AIGenerationLog).where(and_(*conditions))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ==================== СТАТИСТИКА ====================

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику AI генераций пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой
        """
        # Всего генераций
        query_total = select(func.count(AIGenerationLog.id)).where(
            AIGenerationLog.user_id == user_id
        )
        result_total = await self.session.execute(query_total)
        total_generations = result_total.scalar() or 0

        # Успешные генерации
        query_success = select(func.count(AIGenerationLog.id)).where(
            and_(
                AIGenerationLog.user_id == user_id,
                AIGenerationLog.status == AIGenerationStatus.SUCCESS,
            )
        )
        result_success = await self.session.execute(query_success)
        successful_generations = result_success.scalar() or 0

        # Провалившиеся генерации
        query_failed = select(func.count(AIGenerationLog.id)).where(
            and_(
                AIGenerationLog.user_id == user_id,
                AIGenerationLog.status == AIGenerationStatus.FAILED,
            )
        )
        result_failed = await self.session.execute(query_failed)
        failed_generations = result_failed.scalar() or 0

        # Всего потрачено AI кредитов
        query_credits = select(func.sum(AIGenerationLog.ai_credits_spent)).where(
            and_(
                AIGenerationLog.user_id == user_id,
                AIGenerationLog.status == AIGenerationStatus.SUCCESS,
            )
        )
        result_credits = await self.session.execute(query_credits)
        total_ai_credits_spent = result_credits.scalar() or 0

        # Статистика по типам генерации
        query_by_type = (
            select(AIGenerationLog.generation_type, func.count(AIGenerationLog.id).label("count"))
            .where(AIGenerationLog.user_id == user_id)
            .group_by(AIGenerationLog.generation_type)
        )

        result_by_type = await self.session.execute(query_by_type)
        by_type = {row[0].value: row[1] for row in result_by_type.all()}

        # Среднее время обработки
        query_avg_time = select(func.avg(AIGenerationLog.processing_time_seconds)).where(
            and_(
                AIGenerationLog.user_id == user_id,
                AIGenerationLog.processing_time_seconds.isnot(None),
            )
        )
        result_avg_time = await self.session.execute(query_avg_time)
        avg_processing_time = result_avg_time.scalar()

        return {
            "total_generations": total_generations,
            "successful_generations": successful_generations,
            "failed_generations": failed_generations,
            "total_ai_credits_spent": total_ai_credits_spent,
            "generations_by_type": by_type,
            "average_processing_time_seconds": int(avg_processing_time)
            if avg_processing_time
            else 0,
            "success_rate": round(successful_generations / total_generations * 100, 2)
            if total_generations > 0
            else 0,
        }

    async def get_global_stats(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Получить глобальную статистику по всем генерациям.

        Args:
            since: Начало периода (опционально)

        Returns:
            Словарь со статистикой
        """
        conditions = []
        if since:
            conditions.append(AIGenerationLog.created_at >= since)

        where_clause = and_(*conditions) if conditions else True

        # Всего генераций
        query_total = select(func.count(AIGenerationLog.id)).where(where_clause)
        result_total = await self.session.execute(query_total)
        total_generations = result_total.scalar() or 0

        # По провайдерам
        query_by_provider = (
            select(AIGenerationLog.provider, func.count(AIGenerationLog.id).label("count"))
            .where(where_clause)
            .group_by(AIGenerationLog.provider)
        )

        result_by_provider = await self.session.execute(query_by_provider)
        by_provider = {row[0]: row[1] for row in result_by_provider.all()}

        # По моделям
        query_by_model = (
            select(AIGenerationLog.model, func.count(AIGenerationLog.id).label("count"))
            .where(where_clause)
            .group_by(AIGenerationLog.model)
        )

        result_by_model = await self.session.execute(query_by_model)
        by_model = {row[0]: row[1] for row in result_by_model.all()}

        # Всего потрачено AI кредитов
        query_credits = select(func.sum(AIGenerationLog.ai_credits_spent)).where(where_clause)
        result_credits = await self.session.execute(query_credits)
        total_credits = result_credits.scalar() or 0

        return {
            "total_generations": total_generations,
            "by_provider": by_provider,
            "by_model": by_model,
            "total_ai_credits_spent": total_credits,
        }

    async def get_total_user_generations(self, user_id: int) -> int:
        """
        Получить общее количество генераций пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество генераций
        """
        query = select(func.count(AIGenerationLog.id)).where(AIGenerationLog.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_total_user_ai_credits_spent(self, user_id: int) -> int:
        """
        Получить общее количество потраченных AI кредитов пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество потраченных AI кредитов
        """
        query = select(func.sum(AIGenerationLog.ai_credits_spent)).where(
            and_(
                AIGenerationLog.user_id == user_id,
                AIGenerationLog.status == AIGenerationStatus.SUCCESS,
            )
        )
        result = await self.session.execute(query)
        return result.scalar() or 0
