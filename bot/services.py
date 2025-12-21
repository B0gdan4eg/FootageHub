"""
Global bot services container.
This module is imported by both main.py and handlers to avoid circular imports.
"""
import asyncio
from bot.config import MAX_CONCURRENT_DOWNLOADS

class BotServices:
    """Container for global bot services"""
    bot = None  # Bot instance for sending messages
    link_processor = None
    # Семафор для ограничения параллельных скачиваний (защита от перегрузки памяти)
    download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
