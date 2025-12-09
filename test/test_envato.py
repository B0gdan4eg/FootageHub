import asyncio
import json
import os
import time
from playwright.async_api import async_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "envato_cookies.json")


class EnvatoDownloader:
    """
    Advanced Envato Elements downloader using CDP (Chrome DevTools Protocol).
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
                print(f"⚠️ Ошибка при закрытии контекста: {e}")

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                print(f"⚠️ Ошибка при закрытии браузера: {e}")

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                print(f"⚠️ Ошибка при остановке playwright: {e}")

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
            asset_url: URL of the Envato Elements asset page

        Returns:
            Direct download URL or None if failed
        """
        page = None
        client = None
        start_time = time.time()
        download_url = None

        try:
            page = await self.context.new_page()

            # Enable CDP session for network monitoring
            client = await self.context.new_cdp_session(page)
            await client.send("Network.enable")

            captured_responses = []

            def on_response(event):
                url = event.get("response", {}).get("url", "")
                if "download_and_license" in url:
                    captured_responses.append(event)

            client.on("Network.responseReceived", on_response)

            # Navigate to asset page
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=30000)

            # Click download button
            await page.click("button[data-testid='button-download']", timeout=15000)

            # Click download without license
            await page.click("button[data-testid='download-without-license-button']", timeout=15000)

            # Wait for download URL from intercepted network responses
            download_url = await self._wait_for_download_url(client, captured_responses, timeout=10)

            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"   ✅ {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"   ❌ Не получен URL")

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"   ❌ Ошибка: {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")
            return None

        finally:
            # IMPORTANT: Close CDP session first to prevent resource leaks
            if client:
                try:
                    await client.detach()
                except Exception:
                    pass

            # Then close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass


    async def _wait_for_download_url(self, client, captured_responses, timeout=10) -> str | None:
        """
        Wait for download URL to appear in intercepted network responses.
        Non-blocking approach using asyncio.sleep instead of time.sleep.

        Args:
            client: CDP client session
            captured_responses: List of captured network responses
            timeout: Maximum wait time in seconds

        Returns:
            Download URL or None if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            for resp in captured_responses:
                try:
                    body = await client.send("Network.getResponseBody", {"requestId": resp["requestId"]})
                    data = json.loads(body["body"])
                    url = data.get("data", {}).get("attributes", {}).get("downloadUrl")
                    if url:
                        return url
                except:
                    continue
            await asyncio.sleep(0.1)
        return None


# Main API function for bot integration
async def get_envato_direct_download_url(asset_url: str) -> str | None:
    """
    Get direct download URL for a single Envato Elements asset.
    This is the main function used by the bot.

    Args:
        asset_url: URL of the Envato Elements asset page

    Returns:
        Direct download URL or None if failed

    Example:
        url = await get_envato_direct_download_url("https://elements.envato.com/ru/...")
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
            async with EnvatoDownloader() as downloader:
                link = await downloader.get_download_url(asset_url)

                if link:
                    print(f"✅ Прямая ссылка получена")
                    return link
                else:
                    print("❌ Не удалось получить ссылку")
                    return None
    else:
        async with EnvatoDownloader() as downloader:
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
    test_url = "https://elements.envato.com/ru/young-woman-lying-in-the-bed-at-night-and-having-i-2ZBFRTB"
    print("="*70)
    print("🚀 Получение прямой ссылки на скачивание")
    print("="*70)
    print(f"🔗 URL: {test_url}\n")

    result = await get_envato_direct_download_url(test_url)

    if result:
        print(f"\n✅ Прямая ссылка получена!")
        print(f"🔗 {result}")
    else:
        print(f"\n❌ Не удалось получить ссылку")

if __name__ == "__main__":
    asyncio.run(test_single_url())