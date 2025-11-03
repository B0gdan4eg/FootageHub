import asyncio
import logging
from typing import NamedTuple
from envato_utils.envato_playwright import EnvatoDownloader

# Setup logging
logger = logging.getLogger(__name__)


class LinkTask(NamedTuple):
    url: str
    future: asyncio.Future


class LinkProcessor:
    """
    Queue-based link processor for handling multiple download requests efficiently.
    Uses a pool of workers to process URLs concurrently while reusing a single browser instance.
    """

    def __init__(self, max_workers=10):
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.downloader = None
        self.workers = []

    async def start(self):
        """Initialize browser and start worker pool"""
        try:
            print(f"[LinkProcessor] Starting with {self.max_workers} workers...")
            logger.info(f"Starting LinkProcessor with {self.max_workers} workers...")
            self.downloader = await EnvatoDownloader().__aenter__()
            self.workers = [asyncio.create_task(self.worker(i)) for i in range(self.max_workers)]
            print(f"[LinkProcessor] Started successfully! Workers: {len(self.workers)}")
            logger.info("LinkProcessor started successfully")
        except Exception as e:
            print(f"[LinkProcessor] ERROR: {e}")
            logger.error(f"Failed to start LinkProcessor: {e}")
            raise

    async def stop(self):
        """Stop workers and close browser"""
        logger.info("Stopping LinkProcessor...")
        if self.downloader:
            await self.downloader.__aexit__(None, None, None)
        for w in self.workers:
            w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("LinkProcessor stopped")

    async def worker(self, idx):
        """Worker coroutine that processes tasks from queue"""
        print(f"[Worker {idx}] Started")
        logger.info(f"Worker {idx} started")
        while True:
            try:
                task: LinkTask = await self.queue.get()
                print(f"[Worker {idx}] Processing: {task.url[:50]}...")
                logger.info(f"Worker {idx} processing: {task.url}")
                try:
                    result = await self.downloader.get_download_url(task.url)
                    if result:
                        print(f"[Worker {idx}] ✅ Success!")
                        logger.info(f"Worker {idx} success: {task.url[:50]}... -> {result[:50]}...")
                    else:
                        print(f"[Worker {idx}] ❌ Failed - No URL")
                        logger.warning(f"Worker {idx} failed: {task.url[:50]}... -> No URL returned")
                    task.future.set_result(result)
                except Exception as e:
                    print(f"[Worker {idx}] ❌ Error: {e}")
                    logger.error(f"Worker {idx} error for {task.url[:50]}...: {e}")
                    task.future.set_exception(e)
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                print(f"[Worker {idx}] Cancelled")
                logger.info(f"Worker {idx} cancelled")
                break
            except Exception as e:
                print(f"[Worker {idx}] Unexpected error: {e}")
                logger.error(f"Worker {idx} unexpected error: {e}")

    async def submit(self, url: str) -> str:
        """
        Submit a URL for processing and wait for result.

        Args:
            url: Envato Elements URL to process

        Returns:
            Direct download URL or None if failed
        """
        print(f"[LinkProcessor] Submitting URL: {url[:50]}...")
        logger.info(f"Submitting URL to queue: {url[:50]}...")
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put(LinkTask(url=url, future=future))

        try:
            print(f"[LinkProcessor] Waiting for result...")
            result = await future
            print(f"[LinkProcessor] Result: {'✅ Success' if result else '❌ Failed'}")
            logger.info(f"URL processing completed: {url[:50]}... -> {'Success' if result else 'Failed'}")
            return result
        except Exception as e:
            print(f"[LinkProcessor] ERROR: {e}")
            logger.error(f"URL processing failed: {url[:50]}... -> {e}")
            return None
