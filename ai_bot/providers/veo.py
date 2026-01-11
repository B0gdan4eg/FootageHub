"""
VEO 3.1 Provider

Google VEO 3.1 video generation via Kie.ai
Advanced video generation with high quality and understanding
"""
from typing import Any, Dict, List, Optional

from .base import AbstractAIProvider, GenerationType
from .kie_ai_client import KieAIClient


class VeoProvider(AbstractAIProvider):
    """Provider for VEO 3.1 video generation"""

    def __init__(self, api_key: Optional[str] = None, pricing_service=None):
        super().__init__(api_key, pricing_service)
        self._client = KieAIClient(api_key)

    @property
    def provider_name(self) -> str:
        return "VEO"

    @property
    def model_name(self) -> str:
        return "google/veo-3.1"

    @property
    def generation_type(self) -> GenerationType:
        return GenerationType.VIDEO

    def get_cost(self) -> int:
        """VEO 3.1 costs 5 AI credits per video"""
        return 5

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration: str = "5",
        image_urls: Optional[List[str]] = None,
        timeout: int = 600,
        **kwargs,
    ) -> Optional[str]:
        """
        Generate video using VEO 3.1

        Args:
            prompt: Text description for video generation
            aspect_ratio: Video aspect ratio - "1:1", "16:9", "9:16" (default: "16:9")
            duration: Video duration in seconds - typically "5" or "10" (default: "5")
            image_urls: Optional array of image URLs for image-to-video mode
            timeout: Maximum wait time in seconds (default: 600 = 10 min)
            **kwargs: Additional parameters

        Returns:
            Video URL or None if failed
        """
        # Prepare input parameters
        input_params = {"prompt": prompt, "aspect_ratio": aspect_ratio, "duration": duration}

        # Optional: image-to-video mode
        if image_urls:
            input_params["image_urls"] = image_urls

        # Create task
        create_result = await self._client.create_task(
            model=self.model_name,
            input_params=input_params,
            callback_url=kwargs.get("callback_url"),
        )

        task_id = create_result.get("data", {}).get("taskId")
        if not task_id:
            raise Exception("Failed to get taskId from response")

        # Wait for completion (video generation takes longer)
        data = await self._client.wait_for_completion(task_id, timeout=timeout)

        # Extract result URL
        return self._client.parse_result_urls(data)

    async def check_status(self, task_id: str) -> Dict[str, Any]:
        """Check video generation task status"""
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
