"""
Abstract AI Provider

Base class for all AI generation providers
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from enum import Enum


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
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name (e.g., 'nano-banana', 'kling-2.6')"""
        pass

    @property
    @abstractmethod
    def generation_type(self) -> GenerationType:
        """Type of generation this provider supports"""
        pass

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
        pass

    @abstractmethod
    async def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check generation task status

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with task status information
        """
        pass

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
