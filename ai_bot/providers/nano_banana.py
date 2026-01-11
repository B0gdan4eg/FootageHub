"""
Nano Banana Provider

Google Nano Banana image generation via Kie.ai
Documentation: https://docs.kie.ai/market/google/nano-banana
"""
from typing import Any, Dict, Optional

from .base import AbstractAIProvider, GenerationType
from .kie_ai_client import KieAIClient


class NanoBananaProvider(AbstractAIProvider):
    """Provider for Nano Banana image generation"""

    def __init__(self, api_key: Optional[str] = None, pricing_service=None):
        super().__init__(api_key, pricing_service)
        self._client = KieAIClient(api_key)

    @property
    def provider_name(self) -> str:
        return "KIE_AI"

    @property
    def model_name(self) -> str:
        return "google/nano-banana"

    @property
    def generation_type(self) -> GenerationType:
        return GenerationType.IMAGE

    def get_cost(self) -> int:
        """Nano Banana costs 1 AI credit per image"""
        return 1

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "2K",
        output_format: str = "png",
        timeout: int = 300,
        **kwargs,
    ) -> Optional[str]:
        """
        Generate image using Nano Banana

        Args:
            prompt: Text description for image generation
            aspect_ratio: Image aspect ratio (1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, auto)
            resolution: Output resolution (1K, 2K, 4K)
            output_format: Image format (png, jpg)
            timeout: Maximum wait time in seconds
            **kwargs: Additional parameters

        Returns:
            Image URL or None if failed
        """
        # Prepare input parameters
        input_params = {
            "prompt": prompt,
            "image_size": aspect_ratio,
            "output_format": output_format,
        }

        # Optional: support for image editing
        image_input = kwargs.get("image_input")
        if image_input:
            input_params["image_input"] = image_input

        # Create task
        create_result = await self._client.create_task(
            model=self.model_name,
            input_params=input_params,
            callback_url=kwargs.get("callback_url"),
        )

        task_id = create_result.get("data", {}).get("taskId")
        if not task_id:
            raise Exception("Failed to get taskId from response")

        # Wait for completion
        data = await self._client.wait_for_completion(task_id, timeout=timeout)

        # Extract result URL
        return self._client.parse_result_urls(data)

    async def check_status(self, task_id: str) -> Dict[str, Any]:
        """Check image generation task status"""
        result = await self._client.get_task_status(task_id)
        data = result.get("data", {})

        return {
            "task_id": task_id,
            "state": data.get("state"),
            "progress": data.get("progress", 0),
            "result_url": self._client.parse_result_urls(data)
            if data.get("state") == "success"
            else None,
            "error": data.get("failMsg") if data.get("state") == "fail" else None,
        }
