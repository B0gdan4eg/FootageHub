import asyncio
import logging
from typing import NamedTuple

from envato_utils.envato_playwright import EnvatoDownloader
from freepik_utils.freepik import FreepikDownloader
from media_bot.config import BROWSER_RESTART_AFTER
from motion_utils.motion import MotionDownloader

# Setup logging
logger = logging.getLogger(__name__)


class LinkTask(NamedTuple):
    url: str
    future: asyncio.Future
    with_license: bool = False
    platform: str = "envato"  # "envato" or "freepik"


class LinkProcessor:
    """
    Queue-based link processor for handling multiple download requests efficiently.
    Uses a pool of workers to process Envato, Freepik, and Motion Array URLs concurrently.
    Supports both WITH and WITHOUT license downloads for Envato.
    """

    def __init__(self, max_workers=5, restart_after=None):
        """
        Args:
            max_workers: Number of concurrent workers (default: 5, reduced from 10 to prevent resource exhaustion)
            restart_after: Restart browser context after N requests to prevent memory leaks (default: from config.BROWSER_RESTART_AFTER)
        """
        if restart_after is None:
            restart_after = BROWSER_RESTART_AFTER
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.restart_after = restart_after
        self.envato_request_count = 0
        self.freepik_request_count = 0
        self.motion_request_count = 0
        self.envato_downloader = None
        self.freepik_downloader = None
        self.motion_downloader = None
        self.workers = []
        self._envato_restart_lock = asyncio.Lock()
        self._freepik_restart_lock = asyncio.Lock()
        self._motion_restart_lock = asyncio.Lock()

    async def start(self):
        """Initialize browsers and start worker pool"""
        try:
            print(
                f"[LinkProcessor] Starting with {self.max_workers} workers (Envato + Freepik + Motion Array)..."
            )
            logger.info(
                f"Starting LinkProcessor with {self.max_workers} workers (Envato + Freepik + Motion Array)..."
            )

            # Initialize all downloaders
            self.envato_downloader = await EnvatoDownloader().__aenter__()
            self.freepik_downloader = await FreepikDownloader().__aenter__()
            self.motion_downloader = await MotionDownloader().__aenter__()

            self.workers = [asyncio.create_task(self.worker(i)) for i in range(self.max_workers)]
            print(f"[LinkProcessor] Started successfully! Workers: {len(self.workers)}")
            logger.info("LinkProcessor started successfully")
        except Exception as e:
            print(f"[LinkProcessor] ERROR: {e}")
            logger.error(f"Failed to start LinkProcessor: {e}")
            raise

    async def stop(self):
        """Stop workers and close browsers"""
        logger.info("Stopping LinkProcessor...")
        if self.envato_downloader:
            await self.envato_downloader.__aexit__(None, None, None)
        if self.freepik_downloader:
            await self.freepik_downloader.__aexit__(None, None, None)
        if self.motion_downloader:
            await self.motion_downloader.__aexit__(None, None, None)
        for w in self.workers:
            w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("LinkProcessor stopped")

    async def _restart_envato_browser_if_needed(self):
        """Restart Envato browser context if request limit reached to prevent memory leaks"""
        async with self._envato_restart_lock:
            if self.envato_request_count >= self.restart_after:
                print(
                    f"[LinkProcessor] Restarting Envato browser after {self.envato_request_count} requests..."
                )
                logger.info(
                    f"Restarting Envato browser context after {self.envato_request_count} requests"
                )

                # Close old downloader
                if self.envato_downloader:
                    await self.envato_downloader.__aexit__(None, None, None)

                # Create new downloader
                self.envato_downloader = await EnvatoDownloader().__aenter__()
                self.envato_request_count = 0

                print(f"[LinkProcessor] Envato browser restarted successfully")
                logger.info("Envato browser context restarted successfully")

    async def _restart_freepik_browser_if_needed(self):
        """Restart Freepik browser context if request limit reached to prevent memory leaks"""
        async with self._freepik_restart_lock:
            if self.freepik_request_count >= self.restart_after:
                print(
                    f"[LinkProcessor] Restarting Freepik browser after {self.freepik_request_count} requests..."
                )
                logger.info(
                    f"Restarting Freepik browser context after {self.freepik_request_count} requests"
                )

                # Close old downloader
                if self.freepik_downloader:
                    await self.freepik_downloader.__aexit__(None, None, None)

                # Create new downloader
                self.freepik_downloader = await FreepikDownloader().__aenter__()
                self.freepik_request_count = 0

                print(f"[LinkProcessor] Freepik browser restarted successfully")
                logger.info("Freepik browser context restarted successfully")

    async def _restart_motion_browser_if_needed(self):
        """Restart Motion Array browser context if request limit reached to prevent memory leaks"""
        async with self._motion_restart_lock:
            if self.motion_request_count >= self.restart_after:
                print(
                    f"[LinkProcessor] Restarting Motion Array browser after {self.motion_request_count} requests..."
                )
                logger.info(
                    f"Restarting Motion Array browser context after {self.motion_request_count} requests"
                )

                # Close old downloader
                if self.motion_downloader:
                    await self.motion_downloader.__aexit__(None, None, None)

                # Create new downloader
                self.motion_downloader = await MotionDownloader().__aenter__()
                self.motion_request_count = 0

                print(f"[LinkProcessor] Motion Array browser restarted successfully")
                logger.info("Motion Array browser context restarted successfully")

    async def worker(self, idx):
        """Worker coroutine that processes tasks from queue"""
        print(f"[Worker {idx}] Started")
        logger.info(f"Worker {idx} started")
        while True:
            try:
                task: LinkTask = await self.queue.get()
                print(f"[Worker {idx}] Processing ({task.platform}): {task.url[:50]}...")
                logger.info(f"Worker {idx} processing ({task.platform}): {task.url}")
                try:
                    result = None

                    # Process based on platform
                    if task.platform == "freepik":
                        # Check if Freepik browser needs restart
                        await self._restart_freepik_browser_if_needed()
                        # Get Freepik download URL
                        result = await self.freepik_downloader.get_download_url(task.url)
                        self.freepik_request_count += 1

                    elif task.platform == "motion":
                        # Check if Motion Array browser needs restart
                        await self._restart_motion_browser_if_needed()
                        # Get Motion Array download URL
                        result = await self.motion_downloader.get_download_url(task.url)
                        self.motion_request_count += 1

                    else:  # envato
                        # Check if Envato browser needs restart
                        await self._restart_envato_browser_if_needed()
                        # Use appropriate method based on license flag
                        if task.with_license:
                            result = await self.envato_downloader.get_download_url_with_license(
                                task.url
                            )
                        else:
                            result = await self.envato_downloader.get_download_url(task.url)
                        self.envato_request_count += 1

                    if result:
                        platform_info = f"{task.platform.upper()}"
                        license_info = (
                            f" (WITH LICENSE)"
                            if task.with_license and task.platform == "envato"
                            else ""
                        )
                        print(f"[Worker {idx}] ✅ Success ({platform_info}{license_info})!")
                        logger.info(
                            f"Worker {idx} success ({platform_info}{license_info}): {task.url[:50]}... -> {result[:50]}..."
                        )
                    else:
                        print(f"[Worker {idx}] ❌ Failed - No URL")
                        logger.warning(
                            f"Worker {idx} failed: {task.url[:50]}... -> No URL returned"
                        )
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

    async def submit(self, url: str, with_license: bool = False, platform: str = "envato") -> str:
        """
        Submit a URL for processing and wait for result.

        Args:
            url: URL to process (Envato, Freepik, or Motion Array)
            with_license: If True, downloads WITH license (only for Envato)
            platform: "envato", "freepik", or "motion" (default: "envato")

        Returns:
            Direct download URL or None if failed
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put(
            LinkTask(url=url, future=future, with_license=with_license, platform=platform)
        )

        try:
            result = await future
            platform_info = f"{platform.upper()}"
            license_info = f" (WITH LICENSE)" if with_license and platform == "envato" else ""
            logger.info(
                f"URL processing completed ({platform_info}{license_info}): {url[:50]}... -> {'Success' if result else 'Failed'}"
            )
            return result
        except Exception as e:
            print(f"[LinkProcessor] ERROR: {e}")
            logger.error(f"URL processing failed: {url[:50]}... -> {e}")
            return None
