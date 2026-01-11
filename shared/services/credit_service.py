"""
Credit Service - централизованное управление кредитами.

Управляет обычными кредитами и AI кредитами пользователей.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.exceptions import (
    InsufficientAICreditsError,
    InsufficientCreditsError,
    UserNotFoundException,
)
from shared.db.repositories.user_repository import UserRepository

CreditType = Literal["credits", "ai_credits", "both"]


class CreditService:
    """
    Сервис управления кредитами пользователей.

    Основные возможности:
    - Начисление кредитов (обычных и AI)
    - Списание кредитов
    - Проверка баланса
    - Возврат кредитов (refund)
    - Статистика использования
    """

    def __init__(self, session: AsyncSession, user_repo: UserRepository):
        self.session = session
        self._user_repo = user_repo

    # ==================== НАЧИСЛЕНИЕ КРЕДИТОВ ====================

    async def add_credits(
        self,
        user_id: int,
        amount: int,
        credit_type: CreditType = "credits",
        reason: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Начислить кредиты пользователю.

        Args:
            user_id: ID пользователя
            amount: Количество кредитов
            credit_type: Тип кредитов ("credits", "ai_credits", "both")
            reason: Причина начисления (для логирования)

        Returns:
            Словарь с новым балансом

        Raises:
            UserNotFoundException: Если пользователь не найден
        """
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(f"User {user_id} not found")

        if credit_type == "credits":
            await self._user_repo.add_credits(user_id=user_id, credits=amount, ai_credits=0)
            new_balance = {"credits": user.credits + amount, "ai_credits": user.ai_credits}

        elif credit_type == "ai_credits":
            await self._user_repo.add_credits(user_id=user_id, credits=0, ai_credits=amount)
            new_balance = {"credits": user.credits, "ai_credits": user.ai_credits + amount}

        elif credit_type == "both":
            await self._user_repo.add_credits(user_id=user_id, credits=amount, ai_credits=amount)
            new_balance = {"credits": user.credits + amount, "ai_credits": user.ai_credits + amount}

        else:
            raise ValueError(f"Invalid credit_type: {credit_type}")

        # Логирование (опционально)
        if reason:
            print(
                f"Credits added: user_id={user_id}, amount={amount}, type={credit_type}, reason={reason}"
            )

        return new_balance

    async def add_ai_credits(self, user_id: int, amount: int, reason: Optional[str] = None) -> int:
        """
        Начислить AI кредиты пользователю.

        Args:
            user_id: ID пользователя
            amount: Количество AI кредитов
            reason: Причина начисления

        Returns:
            Новый баланс AI кредитов

        Raises:
            UserNotFoundException: Если пользователь не найден
        """
        result = await self.add_credits(
            user_id=user_id, amount=amount, credit_type="ai_credits", reason=reason
        )
        return result["ai_credits"]

    async def add_regular_credits(
        self, user_id: int, amount: int, reason: Optional[str] = None
    ) -> int:
        """
        Начислить обычные кредиты пользователю.

        Args:
            user_id: ID пользователя
            amount: Количество кредитов
            reason: Причина начисления

        Returns:
            Новый баланс кредитов

        Raises:
            UserNotFoundException: Если пользователь не найден
        """
        result = await self.add_credits(
            user_id=user_id, amount=amount, credit_type="credits", reason=reason
        )
        return result["credits"]

    # ==================== СПИСАНИЕ КРЕДИТОВ ====================

    async def deduct_credits(
        self,
        user_id: int,
        amount: int,
        credit_type: CreditType = "credits",
        reason: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Списать кредиты у пользователя.

        Args:
            user_id: ID пользователя
            amount: Количество кредитов для списания
            credit_type: Тип кредитов
            reason: Причина списания

        Returns:
            Словарь с новым балансом

        Raises:
            UserNotFoundException: Если пользователь не найден
            InsufficientCreditsError: Если недостаточно обычных кредитов
            InsufficientAICreditsError: Если недостаточно AI кредитов
        """
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(f"User {user_id} not found")

        # Проверка баланса
        if credit_type == "credits":
            if user.credits < amount:
                raise InsufficientCreditsError(
                    f"User {user_id} has only {user.credits} credits, required {amount}"
                )
            await self._user_repo.deduct_credits(user_id=user_id, credits=amount)
            new_balance = {"credits": user.credits - amount, "ai_credits": user.ai_credits}

        elif credit_type == "ai_credits":
            if user.ai_credits < amount:
                raise InsufficientAICreditsError(
                    f"User {user_id} has only {user.ai_credits} AI credits, required {amount}"
                )
            await self._user_repo.deduct_ai_credits(user_id=user_id, ai_credits=amount)
            new_balance = {"credits": user.credits, "ai_credits": user.ai_credits - amount}

        elif credit_type == "both":
            if user.credits < amount:
                raise InsufficientCreditsError(
                    f"User {user_id} has only {user.credits} credits, required {amount}"
                )
            if user.ai_credits < amount:
                raise InsufficientAICreditsError(
                    f"User {user_id} has only {user.ai_credits} AI credits, required {amount}"
                )
            await self._user_repo.deduct_credits(user_id=user_id, credits=amount)
            await self._user_repo.deduct_ai_credits(user_id=user_id, ai_credits=amount)
            new_balance = {"credits": user.credits - amount, "ai_credits": user.ai_credits - amount}

        else:
            raise ValueError(f"Invalid credit_type: {credit_type}")

        # Логирование
        if reason:
            print(
                f"Credits deducted: user_id={user_id}, amount={amount}, type={credit_type}, reason={reason}"
            )

        return new_balance

    async def deduct_ai_credits(
        self, user_id: int, amount: int, reason: Optional[str] = None
    ) -> int:
        """
        Списать AI кредиты у пользователя.

        Args:
            user_id: ID пользователя
            amount: Количество AI кредитов
            reason: Причина списания

        Returns:
            Новый баланс AI кредитов

        Raises:
            UserNotFoundException: Если пользователь не найден
            InsufficientAICreditsError: Если недостаточно AI кредитов
        """
        result = await self.deduct_credits(
            user_id=user_id, amount=amount, credit_type="ai_credits", reason=reason
        )
        return result["ai_credits"]

    async def deduct_regular_credits(
        self, user_id: int, amount: int, reason: Optional[str] = None
    ) -> int:
        """
        Списать обычные кредиты у пользователя.

        Args:
            user_id: ID пользователя
            amount: Количество кредитов
            reason: Причина списания

        Returns:
            Новый баланс кредитов

        Raises:
            UserNotFoundException: Если пользователь не найден
            InsufficientCreditsError: Если недостаточно кредитов
        """
        result = await self.deduct_credits(
            user_id=user_id, amount=amount, credit_type="credits", reason=reason
        )
        return result["credits"]

    # ==================== ВОЗВРАТ КРЕДИТОВ (REFUND) ====================

    async def refund_credits(
        self,
        user_id: int,
        amount: int,
        credit_type: CreditType = "credits",
        reason: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Вернуть кредиты пользователю (refund).

        Аналогично add_credits, но с явным указанием причины возврата.

        Args:
            user_id: ID пользователя
            amount: Количество кредитов для возврата
            credit_type: Тип кредитов
            reason: Причина возврата

        Returns:
            Словарь с новым балансом
        """
        return await self.add_credits(
            user_id=user_id,
            amount=amount,
            credit_type=credit_type,
            reason=f"REFUND: {reason}" if reason else "REFUND",
        )

    async def refund_ai_credits(
        self, user_id: int, amount: int, reason: Optional[str] = None
    ) -> int:
        """
        Вернуть AI кредиты пользователю.

        Args:
            user_id: ID пользователя
            amount: Количество AI кредитов
            reason: Причина возврата

        Returns:
            Новый баланс AI кредитов
        """
        await self._user_repo.refund_ai_credits(user_id=user_id, ai_credits=amount)

        user = await self._user_repo.get_by_id(user_id)
        if reason:
            print(f"AI credits refunded: user_id={user_id}, amount={amount}, reason={reason}")

        return user.ai_credits if user else 0

    # ==================== ПРОВЕРКА БАЛАНСА ====================

    async def get_balance(self, user_id: int) -> Dict[str, int]:
        """
        Получить баланс пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь с балансом кредитов и AI кредитов

        Raises:
            UserNotFoundException: Если пользователь не найден
        """
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(f"User {user_id} not found")

        return {"credits": user.credits, "ai_credits": user.ai_credits}

    async def get_ai_credits_balance(self, user_id: int) -> int:
        """
        Получить баланс AI кредитов.

        Args:
            user_id: ID пользователя

        Returns:
            Количество AI кредитов

        Raises:
            UserNotFoundException: Если пользователь не найден
        """
        balance = await self.get_balance(user_id)
        return balance["ai_credits"]

    async def get_regular_credits_balance(self, user_id: int) -> int:
        """
        Получить баланс обычных кредитов.

        Args:
            user_id: ID пользователя

        Returns:
            Количество кредитов

        Raises:
            UserNotFoundException: Если пользователь не найден
        """
        balance = await self.get_balance(user_id)
        return balance["credits"]

    async def has_sufficient_credits(
        self, user_id: int, amount: int, credit_type: CreditType = "credits"
    ) -> bool:
        """
        Проверить наличие достаточного количества кредитов.

        Args:
            user_id: ID пользователя
            amount: Требуемое количество
            credit_type: Тип кредитов

        Returns:
            True если кредитов достаточно
        """
        try:
            balance = await self.get_balance(user_id)

            if credit_type == "credits":
                return balance["credits"] >= amount
            elif credit_type == "ai_credits":
                return balance["ai_credits"] >= amount
            elif credit_type == "both":
                return balance["credits"] >= amount and balance["ai_credits"] >= amount

            return False

        except UserNotFoundException:
            return False

    # ==================== СТАТИСТИКА ====================

    async def get_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получить статистику использования кредитов.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой

        Raises:
            UserNotFoundException: Если пользователь не найден
        """
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(f"User {user_id} not found")

        return {
            "credits": {
                "current": user.credits,
                "used": 0,  # TODO: добавить tracking использованных кредитов
            },
            "ai_credits": {"current": user.ai_credits, "used": user.ai_credits_used},
        }

    async def transfer_credits(
        self, from_user_id: int, to_user_id: int, amount: int, credit_type: CreditType = "credits"
    ) -> Dict[str, Any]:
        """
        Перевести кредиты от одного пользователя другому.

        Args:
            from_user_id: ID отправителя
            to_user_id: ID получателя
            amount: Количество кредитов
            credit_type: Тип кредитов

        Returns:
            Словарь с результатом перевода

        Raises:
            UserNotFoundException: Если пользователь не найден
            InsufficientCreditsError: Если недостаточно кредитов
        """
        # Списать у отправителя
        await self.deduct_credits(
            user_id=from_user_id,
            amount=amount,
            credit_type=credit_type,
            reason=f"Transfer to user {to_user_id}",
        )

        # Начислить получателю
        await self.add_credits(
            user_id=to_user_id,
            amount=amount,
            credit_type=credit_type,
            reason=f"Transfer from user {from_user_id}",
        )

        return {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "amount": amount,
            "credit_type": credit_type,
            "transferred_at": datetime.utcnow().isoformat(),
        }
