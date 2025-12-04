import asyncio
import json
import os
import time
from playwright.async_api import async_playwright

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
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        total = self.success_count + self.fail_count
        if total > 0:
            avg_time = self.total_time / total
            print("\n" + "="*70)
            print("📊 СТАТИСТИКА:")
            print(f"   ✅ Успешно: {self.success_count}")
            print(f"   ❌ Провалов: {self.fail_count}")
            print(f"   ⏱️  Общее время: {self.total_time:.2f} сек")
            print(f"   ⏱️  Среднее время: {avg_time:.2f} сек/ссылка")
            print("="*70)

    async def get_download_url(self, asset_url: str) -> str | None:
        """
        Get direct download URL using CDP network interception.
        Faster and more reliable than waiting for downloads.

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
                    print(f"⚠️ Ошибка: {e}")

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
                print(f"✅ Ссылка получена за {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"❌ Download event не сработал")

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"❌ Ошибка: {e}")
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

    print(f"🚀 Загружаем: {asset_url}")

    if semaphore:
        async with semaphore:
            async with FreepikDownloader() as downloader:
                link = await downloader.get_download_url(asset_url)

                if link:
                    print(f"✅ Прямая ссылка получена")
                    return link
                else:
                    print("❌ Не удалось получить ссылку")
                    return None
    else:
        async with FreepikDownloader() as downloader:
            link = await downloader.get_download_url(asset_url)

            if link:
                print(f"✅ Прямая ссылка получена")
                return link
            else:
                print("❌ Не удалось получить ссылку")
                return None


# Test/debug functions
async def test_single_url():
    """Test single URL download"""
    test_url = "https://www.freepik.com/premium-video/animation-cyber-monday-text-cardboard-boxes-conveyor-belts-warehouse_4565453#fromView=subhome"
    print("="*70)
    print("🚀 Получение прямой ссылки на скачивание")
    print("="*70)
    print(f"🔗 URL: {test_url}\n")

    result = await get_freepik_direct_download_url(test_url)

    if result:
        print(f"\n✅ Прямая ссылка получена!")
        print(f"🔗 {result[:100]}...")
    else:
        print(f"\n❌ Не удалось получить ссылку")

if __name__ == "__main__":
    asyncio.run(test_single_url())

