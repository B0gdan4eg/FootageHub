import asyncio
import json
import os
import time
from playwright.async_api import async_playwright
from .logger import logger

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "freepik_cookies.json")


class FreepikDownloader:
    """
    Advanced Freepik downloader using CDP (Chrome DevTools Protocol).
    Supports both single and batch processing with URL interception.
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.total_time = 0
        self.success_count = 0
        self.fail_count = 0

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()

        if not os.path.exists(COOKIE_FILE):
            raise FileNotFoundError(f"Cookies file not found: {COOKIE_FILE}")

        with open(COOKIE_FILE, "r") as f:
            await self.context.add_cookies(json.load(f))

        return self

    async def __aexit__(self, *args):
        # Закрываем контекст перед браузером для корректной очистки
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                print(f"⚠️ [FREEPIK] Ошибка при закрытии контекста: {e}")

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                print(f"⚠️ [FREEPIK] Ошибка при закрытии браузера: {e}")

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                print(f"⚠️ [FREEPIK] Ошибка при остановке playwright: {e}")

    async def get_download_url(self, asset_url: str) -> str | None:
        """
        Get direct download URL using download event interception.
        Fastest and most reliable method.

        Args:
            asset_url: URL of the Freepik asset page

        Returns:
            Direct download URL or None if failed
        """
        page = None
        start_time = time.time()
        download_url = None

        try:
            page = await self.context.new_page()

            # Перехватываем только download event - самый быстрый и надежный способ
            download_info = {}

            async def handle_download(download):
                try:
                    download_info['url'] = download.url
                    # Отменяем скачивание, нам нужна только ссылка
                    await download.cancel()
                except Exception as e:
                    print(f"⚠️ [FREEPIK] Ошибка: {e}")

            page.on("download", handle_download)

            # Navigate to asset page
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=30000)

            # Click download button
            await page.click("button[data-cy='download-button']", timeout=15000)

            # Ждём download event (обычно срабатывает за 1-2 секунды)
            await asyncio.sleep(2)

            # Получаем ссылку
            download_url = download_info.get('url')

            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"✅ [FREEPIK] Ссылка получена за {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"❌ [FREEPIK] Download event не сработал")
                await logger.error(f"❌ [FREEPIK] Download event не сработал\nURL: {asset_url}")

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"❌ [FREEPIK] Ошибка: {e}")
            await logger.error(f"❌ [FREEPIK] Ошибка: {e}\nURL: {asset_url}")
            return None

        finally:
            # Close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass


# Main API function for bot integration
async def get_freepik_direct_download_url(asset_url: str) -> str | None:
    """
    Get direct download URL for a single Freepik asset.
    This is the main function used by the bot.

    Args:
        asset_url: URL of the Freepik asset page

    Returns:
        Direct download URL or None if failed

    Example:
        url = await get_freepik_direct_download_url("https://www.freepik.com/...")
    """
    if not os.path.exists(COOKIE_FILE):
        print(f"❌ Cookies file not found: {COOKIE_FILE}")
        return None

    # Используем семафор для ограничения параллельных скачиваний
    try:
        from bot.services import BotServices
        semaphore = BotServices.download_semaphore
    except:
        # Если запускается не из бота (тесты), семафор не нужен
        semaphore = None

    print(f"🚀 [FREEPIK] Загружаем: {asset_url}")

    if semaphore:
        async with semaphore:
            async with FreepikDownloader() as downloader:
                link = await downloader.get_download_url(asset_url)

                if link:
                    print(f"✅ [FREEPIK] Прямая ссылка получена")
                    return link
                else:
                    print("❌ [FREEPIK] Не удалось получить ссылку")
                    return None
    else:
        async with FreepikDownloader() as downloader:
            link = await downloader.get_download_url(asset_url)

            if link:
                print(f"✅ [FREEPIK] Прямая ссылка получена")
                return link
            else:
                print("❌ [FREEPIK] Не удалось получить ссылку")
                return None
