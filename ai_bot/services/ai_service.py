"""
AI Service

Main service for AI generation operations
Coordinates providers, credits, and logging
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from ai_bot.config import config
from ai_bot.providers import KlingProvider, NanoBananaProvider, VeoProvider
from ai_bot.providers.base import AbstractAIProvider
from ai_bot.services.pricing_service import PricingService
from shared.error_tracking import report_exception


class AIService:
    """Service for AI content generation"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.KIE_AI_API_KEY

        # Initialize pricing service
        self.pricing_service = PricingService(self.api_key)

        # Initialize providers with pricing service
        self._providers: Dict[str, AbstractAIProvider] = {
            "nano-banana": NanoBananaProvider(self.api_key, self.pricing_service),
            "kling": KlingProvider(self.api_key, self.pricing_service),
            "veo": VeoProvider(self.api_key, self.pricing_service),
        }

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "2K",
        output_format: str = "png",
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Generate image using Nano Banana

        Args:
            prompt: Text description for image generation
            aspect_ratio: Image aspect ratio
            resolution: Output resolution
            output_format: Image format
            timeout: Maximum wait time

        Returns:
            Dict with generation result
        """
        provider = self._providers["nano-banana"]

        try:
            start_time = datetime.now()

            result_url = await provider.generate(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                output_format=output_format,
                timeout=timeout,
            )

            processing_time = (datetime.now() - start_time).seconds

            return {
                "success": True,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "result_url": result_url,
                "processing_time": processing_time,
                "credits_spent": provider.get_cost(),
                "parameters": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution,
                    "output_format": output_format,
                },
            }

        except Exception as e:
            report_exception(e)
            return {
                "success": False,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "error": str(e),
                "credits_spent": 0,
            }

    async def generate_video(
        self,
        prompt: str,
        provider_name: str = "kling",
        sound: bool = False,
        aspect_ratio: str = "16:9",
        duration: str = "5",
        image_urls: Optional[List[str]] = None,
        timeout: int = 600,
    ) -> Dict[str, Any]:
        """
        Generate video using Kling or VEO

        Args:
            prompt: Text description for video generation
            provider_name: Provider to use ('kling' or 'veo')
            sound: Whether video contains audio (Kling only)
            aspect_ratio: Video aspect ratio
            duration: Video duration
            image_urls: Optional reference images for image-to-video
            timeout: Maximum wait time

        Returns:
            Dict with generation result
        """
        if provider_name not in ["kling", "veo"]:
            return {
                "success": False,
                "error": f"Unknown provider: {provider_name}. Use 'kling' or 'veo'",
            }

        provider = self._providers[provider_name]

        try:
            start_time = datetime.now()

            # Prepare kwargs based on provider
            kwargs = {
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "image_urls": image_urls,
                "timeout": timeout,
            }

            # Kling-specific parameter
            if provider_name == "kling":
                kwargs["sound"] = sound

            result_url = await provider.generate(prompt=prompt, **kwargs)

            processing_time = (datetime.now() - start_time).seconds

            return {
                "success": True,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "result_url": result_url,
                "processing_time": processing_time,
                "credits_spent": provider.get_cost(),
                "parameters": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "duration": duration,
                    "sound": sound if provider_name == "kling" else None,
                    "image_urls": image_urls,
                },
            }

        except Exception as e:
            report_exception(e)
            return {
                "success": False,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "error": str(e),
                "credits_spent": 0,
            }

    async def check_task_status(self, task_id: str, provider_name: str) -> Dict[str, Any]:
        """
        Check generation task status

        Args:
            task_id: Task identifier
            provider_name: Provider name ('nano-banana', 'kling', 'veo')

        Returns:
            Dict with task status
        """
        if provider_name not in self._providers:
            return {"error": f"Unknown provider: {provider_name}"}

        provider = self._providers[provider_name]

        try:
            status = await provider.check_status(task_id)
            return {"success": True, **status}
        except Exception as e:
            report_exception(e)
            return {"success": False, "error": str(e)}

    def get_provider_cost(self, provider_name: str) -> int:
        """Get AI credits cost for a provider"""
        if provider_name not in self._providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        return self._providers[provider_name].get_cost()

    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available providers"""
        return {
            name: {
                "provider_name": provider.provider_name,
                "model_name": provider.model_name,
                "generation_type": provider.generation_type.value,
                "cost": provider.get_cost(),
            }
            for name, provider in self._providers.items()
        }
