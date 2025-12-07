import asyncio
import logging
from typing import NamedTuple
from filesta.filesta_playwright import FilestaDownloader

# Setup logging
logger = logging.getLogger(__name__)


class LinkTask(NamedTuple):
    url: str
    future: asyncio.Future
    with_license: bool = False  # Kept for compatibility, but ignored (Filesta doesn't support licensing)


class LinkProcessor:
    """
    Queue-based link processor for handling multiple download requests efficiently via Filesta.com.
    Uses a pool of workers to process Envato URLs concurrently while reusing a single browser instance.
    Note: Downloads are always WITHOUT license (Filesta limitation).
    """

    def __init__(self, max_workers=3, restart_after=50):
        """
        Args:
            max_workers: Number of concurrent workers (default: 3, reduced from 10 to prevent resource exhaustion)
            restart_after: Restart browser context after N requests to prevent memory leaks (default: 50)
        """
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.restart_after = restart_after
        self.request_count = 0
        self.downloader = None
        self.workers = []
        self._restart_lock = asyncio.Lock()

    async def start(self):
        """Initialize browser and start worker pool"""
        try:
            print(f"[LinkProcessor] Starting with {self.max_workers} workers (Filesta)...")
            logger.info(f"Starting LinkProcessor with {self.max_workers} workers (Filesta)...")
            self.downloader = await FilestaDownloader().__aenter__()
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

    async def _restart_browser_if_needed(self):
        """Restart browser context if request limit reached to prevent memory leaks"""
        async with self._restart_lock:
            if self.request_count >= self.restart_after:
                print(f"[LinkProcessor] Restarting browser after {self.request_count} requests...")
                logger.info(f"Restarting browser context after {self.request_count} requests")

                # Close old downloader
                if self.downloader:
                    await self.downloader.__aexit__(None, None, None)

                # Create new downloader
                self.downloader = await FilestaDownloader().__aenter__()
                self.request_count = 0

                print(f"[LinkProcessor] Browser restarted successfully")
                logger.info("Browser context restarted successfully")

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
                    # Check if browser needs restart
                    await self._restart_browser_if_needed()

                    # Filesta always downloads without license (ignoring with_license flag)
                    result = await self.downloader.get_download_url(task.url)
                    self.request_count += 1

                    if task.with_license:
                        print(f"[Worker {idx}] ⚠️ License requested but Filesta doesn't support licensing - downloading without license")
                        logger.warning(f"Worker {idx}: License requested for {task.url[:50]}... but Filesta doesn't support it")

                    if result:
                        print(f"[Worker {idx}] ✅ Success (via Filesta)!")
                        logger.info(f"Worker {idx} success (Filesta): {task.url[:50]}... -> {result[:50]}...")
                    else:
                        print(f"[Worker {idx}] ❌ Failed - No URL")
                        logger.warning(f"Worker {idx} failed (Filesta): {task.url[:50]}... -> No URL returned")
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

    async def submit(self, url: str, with_license: bool = False) -> str:
        """
        Submit a URL for processing and wait for result.

        Args:
            url: Envato Elements URL to process via Filesta.com
            with_license: Kept for compatibility but IGNORED (Filesta doesn't support licensing)

        Returns:
            Direct download URL or None if failed
        """
        if with_license:
            logger.warning(f"License requested for {url[:50]}... but Filesta doesn't support licensing - will download without license")

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put(LinkTask(url=url, future=future, with_license=with_license))

        try:
            result = await future
            logger.info(f"URL processing completed (Filesta): {url[:50]}... -> {'Success' if result else 'Failed'}")
            return result
        except Exception as e:
            print(f"[LinkProcessor] ERROR (Filesta): {e}")
            logger.error(f"URL processing failed (Filesta): {url[:50]}... -> {e}")
            return None
