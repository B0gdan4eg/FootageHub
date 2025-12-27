"""
Kie.ai API Client

Base client for all Kie.ai API interactions
Documentation: https://docs.kie.ai/
"""
import aiohttp
import asyncio
import json
from typing import Optional, Dict, Any
from ai_bot.config import config


class KieAIClient:
    """Base client for Kie.ai API"""

    BASE_URL = "https://api.kie.ai/api/v1/jobs"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.KIE_AI_API_KEY
        if not self.api_key:
            raise ValueError("KIE_AI_API_KEY is not set")

    async def create_task(
        self,
        model: str,
        input_params: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a generation task

        Args:
            model: Model identifier (e.g., 'google/nano-banana', 'kling-2.6/text-to-video')
            input_params: Model-specific input parameters
            callback_url: Optional webhook URL for completion notifications

        Returns:
            Dict with taskId and other metadata

        Raises:
            Exception: On API errors
        """
        url = f"{self.BASE_URL}/createTask"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "input": input_params
        }

        if callback_url:
            payload["callBackUrl"] = callback_url

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()

                if result is None:
                    raise Exception("API returned None response")

                # Check for API error codes
                code = result.get("code")
                if code and code != 200:
                    msg = result.get("msg", "Unknown error")
                    raise self._handle_error_code(code, msg)

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

        Raises:
            Exception: On API errors
        """
        url = f"{self.BASE_URL}/recordInfo"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        params = {"taskId": task_id}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                result = await response.json()

                if response.status != 200:
                    raise Exception(f"Kie.ai API error: {result}")

                return result

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Wait for task completion with adaptive polling

        Args:
            task_id: Task ID from create_task
            timeout: Maximum wait time in seconds
            poll_interval: Initial seconds between status checks

        Returns:
            Dict with final task results

        Raises:
            TimeoutError: If task doesn't complete within timeout
            Exception: On task failure
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

            result = await self.get_task_status(task_id)

            if result is None:
                raise Exception(f"get_task_status returned None for task {task_id}")

            data = result.get("data", {})

            if data is None:
                raise Exception(f"No 'data' field in result: {result}")

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

    def _handle_error_code(self, code: int, msg: str) -> Exception:
        """
        Convert API error codes to user-friendly exceptions

        Args:
            code: API error code
            msg: Error message from API

        Returns:
            Exception with user-friendly message
        """
        if code == 402:
            return Exception(
                "Недостаточно кредитов на Kie.ai аккаунте. "
                "Пополните баланс на https://kie.ai/"
            )
        elif code == 401:
            return Exception("Неверный API ключ Kie.ai")
        elif code == 429:
            return Exception("Превышен лимит запросов. Попробуйте позже")
        else:
            return Exception(f"Kie.ai API error (code {code}): {msg}")

    def parse_result_urls(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Extract result URL from task data

        Args:
            data: Task data from wait_for_completion

        Returns:
            First result URL or None if not found
        """
        result_json = data.get("resultJson", "{}")

        if not result_json or result_json == "{}":
            return None

        result_data = json.loads(result_json)
        result_urls = result_data.get("resultUrls", [])

        if result_urls:
            return result_urls[0]

        return None

    async def get_account_credits(self) -> int:
        """
        Get remaining account credits from Kie.ai

        Returns:
            Number of remaining credits

        Raises:
            Exception: On API errors
        """
        url = "https://api.kie.ai/api/v1/chat/credit"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()

                if result is None:
                    raise Exception("API returned None response")

                # Check for API error codes
                code = result.get("code")
                if code and code != 200:
                    msg = result.get("msg", "Unknown error")
                    raise self._handle_error_code(code, msg)

                if response.status != 200:
                    raise Exception(f"HTTP error (status {response.status}): {result}")

                # Extract credits from data field
                credits = result.get("data")
                if credits is None:
                    raise Exception("No credits data in response")

                return int(credits)
