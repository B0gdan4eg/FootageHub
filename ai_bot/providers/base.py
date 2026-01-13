"""
Abstract AI Provider

Base class for all AI generation providers
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional


class GenerationType(Enum):
    """AI generation types"""

    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class AbstractAIProvider(ABC):
    """Abstract base class for AI providers"""

    def __init__(self, api_key: str, pricing_service=None):
        self.api_key = api_key
        self._pricing_service = pricing_service

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name (e.g., 'KIE_AI', 'KLING')"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name (e.g., 'nano-banana', 'kling-2.6')"""

    @property
    @abstractmethod
    def generation_type(self) -> GenerationType:
        """Type of generation this provider supports"""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """
        Generate content based on prompt

        Args:
            prompt: Text description for generation
            **kwargs: Provider-specific parameters

        Returns:
            URL to generated content or None if failed
        """

    @abstractmethod
    async def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check generation task status

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with task status information
        """

    def get_cost(self) -> int:
        """
        Get AI credits cost for this provider

        Returns from pricing service if available, otherwise uses default

        Returns:
            Number of AI credits required
        """
        if self._pricing_service:
            try:
                return self._pricing_service.get_model_price(self.model_name)
            except (ValueError, AttributeError):
                pass
        return 1  # Default cost
