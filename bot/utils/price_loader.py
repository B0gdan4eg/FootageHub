"""
Price list loader utility.

Provides centralized functions for loading subscription plans from prices_list.json.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from bot.config import PRICE_LIST_PATH

logger = logging.getLogger(__name__)


def load_subscription_plans() -> Dict[str, Any]:
    """
    Загружает конфигурацию подписок из prices_list.json

    Returns:
        Dict[str, Any]: Словарь с планами подписок или пустой словарь при ошибке

    Raises:
        FileNotFoundError: Если файл prices_list.json не найден
        json.JSONDecodeError: Если файл содержит некорректный JSON
    """
    if not PRICE_LIST_PATH.exists():
        raise FileNotFoundError(f"Price list file not found: {PRICE_LIST_PATH}")

    try:
        with open(PRICE_LIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("subscription_plans", {})
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse price list JSON: {e}")
        raise


def get_plan_config(plan_key: str) -> Optional[Dict[str, Any]]:
    """
    Получает конфигурацию конкретного плана подписки

    Args:
        plan_key: Ключ плана (например, "monthly_150", "daily_30")

    Returns:
        Optional[Dict[str, Any]]: Конфигурация плана или None если план не найден
    """
    plans = load_subscription_plans()
    return plans.get(plan_key)


def save_subscription_plans(plans: Dict[str, Any]) -> None:
    """
    Сохраняет обновлённые планы подписок в prices_list.json

    Args:
        plans: Словарь с планами подписок

    Raises:
        IOError: Если не удалось записать файл
    """
    data = {"subscription_plans": plans}

    try:
        with open(PRICE_LIST_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Successfully saved price list to {PRICE_LIST_PATH}")
    except IOError as e:
        logger.error(f"Failed to save price list: {e}")
        raise
