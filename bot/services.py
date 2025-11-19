"""
Global bot services container.
This module is imported by both main.py and handlers to avoid circular imports.
"""
import asyncio

class BotServices:
    """Container for global bot services"""
    link_processor = None
    # Семафор для ограничения параллельных скачиваний (защита от перегрузки памяти)
    download_semaphore = asyncio.Semaphore(3)  # Максимум 3 одновременных браузера
