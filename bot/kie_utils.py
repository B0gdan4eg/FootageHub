"""
Kie.ai API integration for NANO BANANA image generation
Documentation: https://docs.kie.ai/market/google/nano-banana
"""
import asyncio
from typing import Any, Dict, Optional

import aiohttp

from bot.config import KIE_AI_API_KEY


class KieAIClient:
    """Client for Kie.ai API"""

    BASE_URL = "https://api.kie.ai/api/v1/jobs"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or KIE_AI_API_KEY
        if not self.api_key:
            raise ValueError("KIE_AI_API_KEY is not set")

    async def create_task(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "2K",
        output_format: str = "png",
        image_input: Optional[list] = None,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create NANO BANANA image generation task

        Args:
            prompt: Text description for image generation
            aspect_ratio: Image aspect ratio (1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, auto)
            resolution: Output resolution (1K, 2K, 4K)
            output_format: Image format (png, jpg)
            image_input: Optional array of input images for editing
            callback_url: Optional webhook URL for completion notifications

        Returns:
            Dict with taskId
        """
        url = f"{self.BASE_URL}/createTask"

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": "google/nano-banana",
            "input": {"prompt": prompt, "image_size": aspect_ratio, "output_format": output_format},
        }

        if image_input:
            payload["input"]["image_input"] = image_input

        if callback_url:
            payload["callBackUrl"] = callback_url

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()

                if result is None:
                    raise Exception("API returned None response")

                # Check for API error codes in response
                code = result.get("code")
                if code and code != 200:
                    msg = result.get("msg", "Unknown error")

                    # User-friendly error messages
                    if code == 402:
                        raise Exception(
                            f"❌ Недостаточно кредитов на Kie.ai аккаунте. Пополните баланс на https://kie.ai/"
                        )
                    elif code == 401:
                        raise Exception(f"❌ Неверный API ключ Kie.ai")
                    elif code == 429:
                        raise Exception(f"❌ Превышен лимит запросов. Попробуйте позже")
                    else:
                        raise Exception(f"Kie.ai API error (code {code}): {msg}")

                if response.status != 200:
                    raise Exception(f"HTTP error (status {response.status}): {result}")

                return result

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and results

        Args:
            task_id: Task ID from create_task

        Returns:
            Dict with task state and results
        """
        url = f"{self.BASE_URL}/recordInfo"

        headers = {"Authorization": f"Bearer {self.api_key}"}

        params = {"taskId": task_id}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                result = await response.json()

                if response.status != 200:
                    raise Exception(f"Kie.ai API error: {result}")

                return result

    async def wait_for_completion(
        self, task_id: str, timeout: int = 300, poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Wait for task completion with polling

        Args:
            task_id: Task ID from create_task
            timeout: Maximum wait time in seconds (default: 300)
            poll_interval: Seconds between status checks (default: 3)

        Returns:
            Dict with final task results
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

            result = await self.get_task_status(task_id)
            data = result.get("data", {})
            state = data.get("state")

            if state == "success":
                return data
            elif state == "fail":
                fail_msg = data.get("failMsg", "Unknown error")
                raise Exception(f"Task failed: {fail_msg}")

            # Adaptive polling based on elapsed time
            if elapsed < 30:
                wait_time = 2
            elif elapsed < 120:
                wait_time = 5
            else:
                wait_time = 10

            await asyncio.sleep(wait_time)

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "2K",
        output_format: str = "png",
        timeout: int = 300,
    ) -> Optional[str]:
        """
        Generate image and wait for completion (convenience method)

        Args:
            prompt: Text description
            aspect_ratio: Image aspect ratio
            resolution: Output resolution
            output_format: Image format
            timeout: Maximum wait time

        Returns:
            Image URL or None if failed
        """
        # Create task
        create_result = await self.create_task(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            output_format=output_format,
        )

        task_id = create_result.get("data", {}).get("taskId")
        if not task_id:
            raise Exception("Failed to get taskId from response")

        # Wait for completion (returns data object directly)
        data = await self.wait_for_completion(task_id, timeout=timeout)

        # Parse result URLs
        import json

        result_json = data.get("resultJson", "{}")

        if not result_json:
            return None

        result_data = json.loads(result_json)
        result_urls = result_data.get("resultUrls", [])

        if result_urls:
            return result_urls[0]

        return None


class KlingVideoClient:
    """Client for Kling 2.6 Video Generation via Kie.ai"""

    BASE_URL = "https://api.kie.ai/api/v1/jobs"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or KIE_AI_API_KEY
        if not self.api_key:
            raise ValueError("KIE_AI_API_KEY is not set")

    async def create_video_task(
        self,
        prompt: str,
        sound: bool = False,
        aspect_ratio: str = "16:9",
        duration: str = "5",
        image_urls: Optional[list] = None,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create Kling text-to-video generation task

        Args:
            prompt: Text description for video generation (max 1000 chars)
            sound: Whether generated video contains audio (default: False)
            aspect_ratio: Video aspect ratio - "1:1", "16:9", "9:16" (default: "16:9")
            duration: Video duration in seconds - "5" or "10" (default: "5")
            image_urls: Optional array of image URLs for image-to-video mode
            callback_url: Optional webhook URL for completion notifications

        Returns:
            Dict with taskId
        """
        url = f"{self.BASE_URL}/createTask"

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": "kling-2.6/text-to-video",
            "input": {
                "prompt": prompt[:1000],  # Enforce max length
                "sound": sound,
                "aspect_ratio": aspect_ratio,
                "duration": duration,
            },
        }

        if image_urls:
            payload["input"]["image_urls"] = image_urls

        if callback_url:
            payload["callBackUrl"] = callback_url

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()

                if result is None:
                    raise Exception("API returned None response")

                # Check for API error codes in response
                code = result.get("code")
                if code and code != 200:
                    msg = result.get("msg", "Unknown error")

                    # User-friendly error messages
                    if code == 402:
                        raise Exception(
                            f"❌ Недостаточно кредитов на Kie.ai аккаунте. Пополните баланс на https://kie.ai/"
                        )
                    elif code == 401:
                        raise Exception(f"❌ Неверный API ключ Kie.ai")
                    elif code == 429:
                        raise Exception(f"❌ Превышен лимит запросов. Попробуйте позже")
                    else:
                        raise Exception(f"Kie.ai API error (code {code}): {msg}")

                if response.status != 200:
                    raise Exception(f"HTTP error (status {response.status}): {result}")

                return result

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status and results"""
        url = f"{self.BASE_URL}/recordInfo"

        headers = {"Authorization": f"Bearer {self.api_key}"}

        params = {"taskId": task_id}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                result = await response.json()

                if response.status != 200:
                    raise Exception(f"Kie.ai API error: {result}")

                return result

    async def wait_for_completion(
        self, task_id: str, timeout: int = 600, poll_interval: int = 5
    ) -> Dict[str, Any]:
        """Wait for video generation completion with polling"""
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

            result = await self.get_task_status(task_id)

            # Debug: check if result is None
            if result is None:
                raise Exception(f"get_task_status returned None for task {task_id}")

            data = result.get("data", {})

            # Debug: check if data is None
            if data is None:
                raise Exception(f"No 'data' field in result: {result}")

            state = data.get("state")

            if state == "success":
                return data
            elif state == "fail":
                fail_msg = data.get("failMsg", "Unknown error")
                raise Exception(f"Task failed: {fail_msg}")

            # Video generation takes longer, use adaptive polling
            if elapsed < 60:
                wait_time = 5
            elif elapsed < 300:
                wait_time = 10
            else:
                wait_time = 15

            await asyncio.sleep(wait_time)

    async def generate_video(
        self,
        prompt: str,
        sound: bool = False,
        aspect_ratio: str = "16:9",
        duration: str = "5",
        timeout: int = 600,
    ) -> Optional[str]:
        """Generate video and wait for completion (convenience method)"""
        # Create task
        create_result = await self.create_video_task(
            prompt=prompt, sound=sound, aspect_ratio=aspect_ratio, duration=duration
        )

        # Debug: check create_result
        if create_result is None:
            raise Exception("create_video_task returned None")

        # Debug: check if data field exists
        data_field = create_result.get("data")
        if data_field is None:
            raise Exception(f"No 'data' field in create_result: {create_result}")

        task_id = data_field.get("taskId")
        if not task_id:
            raise Exception(f"Failed to get taskId from response. Data field: {data_field}")

        # Wait for completion (returns data object directly)
        data = await self.wait_for_completion(task_id, timeout=timeout)

        # Debug: check if data is None
        if data is None:
            raise Exception("wait_for_completion returned None")

        # Parse result URLs
        import json

        result_json = data.get("resultJson", "{}")

        if not result_json or result_json == "{}":
            raise Exception(f"No resultJson in data: {data}")

        result_data = json.loads(result_json)
        result_urls = result_data.get("resultUrls", [])

        if result_urls:
            return result_urls[0]

        return None


def get_kie_client() -> KieAIClient:
    """Get Kie.ai NANO BANANA client instance"""
    return KieAIClient()


def get_kling_client() -> KlingVideoClient:
    """Get Kling video generation client instance"""
    return KlingVideoClient()
