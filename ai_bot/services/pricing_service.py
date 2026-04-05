"""
Pricing Service

Service for managing AI model pricing and credits
Based on Kie.ai documentation and actual costs
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ai_bot.providers.kie_ai_client import KieAIClient


class PricingService:
    """Service for AI model pricing management"""

    # Model pricing in AI credits (based on Kie.ai 2025 pricing)
    # Source: https://kie.ai/ pricing information
    # Credits cost $0.005 each
    MODEL_PRICES = {
        # Image Generation
        "google/nano-banana": {
            "name": "Nano Banana Pro",
            "type": "image",
            "credits": 4,  # 4 credits ($0.02)
            "description": "Gemini 3.0 Pro image generation",
        },
        "seedream-4.0": {
            "name": "Seedream 4.0",
            "type": "image",
            "credits": 4,  # ~3.5 credits ($0.0175), округлим до 4
            "description": "High-quality image generation",
        },
        "midjourney": {
            "name": "Midjourney",
            "type": "image",
            "credits": 2,  # ~$0.01 per image variant
            "description": "Midjourney image generation",
        },
        # Video Generation
        "kling-2.6/text-to-video": {
            "name": "Kling 2.6",
            "type": "video",
            "credits": 100,  # Estimated based on video complexity
            "description": "Text-to-video with audio support",
        },
        "veo-3.1/text-to-video": {
            "name": "VEO 3.1 Fast",
            "type": "video",
            "credits": 80,  # 80 credits ($0.40) for 8s video with audio
            "description": "Google VEO 3 Fast - 8 seconds with audio",
        },
        "veo-3.1/text-to-video-quality": {
            "name": "VEO 3.1 Quality",
            "type": "video",
            "credits": 400,  # 400 credits ($2.00) for 8s quality video
            "description": "Google VEO 3 Quality - 8 seconds with audio",
        },
    }

    def __init__(self, api_key: Optional[str] = None):
        # Only create client if api_key is provided and not empty
        try:
            self._client = KieAIClient(api_key) if api_key and api_key.strip() else None
        except ValueError:
            # API key is not set, client will be None
            self._client = None
        self._cached_credits: Optional[int] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes

    def get_model_price(self, model: str) -> int:
        """
        Get price in AI credits for a specific model

        Args:
            model: Model identifier

        Returns:
            Number of AI credits required

        Raises:
            ValueError: If model is not found
        """
        if model not in self.MODEL_PRICES:
            raise ValueError(f"Unknown model: {model}")

        return self.MODEL_PRICES[model]["credits"]

    def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get detailed information about a model

        Args:
            model: Model identifier

        Returns:
            Dict with model information

        Raises:
            ValueError: If model is not found
        """
        if model not in self.MODEL_PRICES:
            raise ValueError(f"Unknown model: {model}")

        return self.MODEL_PRICES[model].copy()

    def get_all_models(self) -> Dict[str, Dict]:
        """
        Get information about all available models

        Returns:
            Dict mapping model IDs to their information
        """
        return self.MODEL_PRICES.copy()

    def get_models_by_type(self, generation_type: str) -> Dict[str, Dict]:
        """
        Get models filtered by generation type

        Args:
            generation_type: Type of generation ('image', 'video', 'audio')

        Returns:
            Dict of models matching the type
        """
        return {
            model_id: info
            for model_id, info in self.MODEL_PRICES.items()
            if info["type"] == generation_type
        }

    async def get_kie_credits(self, force_refresh: bool = False) -> Optional[int]:
        """
        Get remaining Kie.ai account credits with caching

        Args:
            force_refresh: Force refresh cache

        Returns:
            Number of remaining credits or None if unavailable
        """
        if not self._client:
            return None

        # Check cache
        if not force_refresh and self._cached_credits is not None:
            if self._cache_timestamp and (datetime.now() - self._cache_timestamp < self._cache_ttl):
                return self._cached_credits

        # Fetch fresh data
        try:
            credits = await self._client.get_account_credits()
            self._cached_credits = credits
            self._cache_timestamp = datetime.now()
            return credits
        except Exception as e:
            # Return cached value on error if available
            if self._cached_credits is not None:
                return self._cached_credits
            raise e

    def calculate_cost(self, model: str, quantity: int = 1) -> int:
        """
        Calculate total cost for multiple generations

        Args:
            model: Model identifier
            quantity: Number of generations

        Returns:
            Total AI credits required
        """
        price = self.get_model_price(model)
        return price * quantity

    def credits_to_usd(self, credits: Optional[int]) -> float:
        """
        Convert AI credits to USD

        Args:
            credits: Number of AI credits

        Returns:
            Equivalent value in USD
        """
        if credits is None:
            return 0.0
        return credits * 0.005  # $0.005 per credit

    def usd_to_credits(self, usd: float) -> int:
        """
        Convert USD to AI credits

        Args:
            usd: Amount in USD

        Returns:
            Number of AI credits
        """
        return int(usd / 0.005)
