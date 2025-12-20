import asyncio
import json
import os
import time
from playwright.async_api import async_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "envato_cookies_1.json")


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
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )

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
        Get direct download URL using download event interception.
        Similar to Freepik approach.

        Args:
            asset_url: URL of the Envato Elements asset page

        Returns:
            Direct download URL or None if failed
        """
        page = None
        start_time = time.time()
        download_url = None

        try:
            page = await self.context.new_page()

            # Перехватываем download event
            download_info = {}

            async def handle_download(download):
                try:
                    download_info['url'] = download.url
                    print(f"[DEBUG] ✅ Download event captured: {download.url}")
                    # Отменяем скачивание, нам нужна только ссылка
                    await download.cancel()
                except Exception as e:
                    print(f"[DEBUG] ⚠️ Error in download handler: {e}")

            page.on("download", handle_download)

            # Navigate to asset page - wait for redirect to complete
            print("[DEBUG] Navigating to asset page...")
            await page.goto(asset_url, wait_until="load", timeout=30000)

            # Wait for redirect to app.envato.com if needed
            redirected = False
            if "elements.envato.com" in page.url:
                print("[DEBUG] Waiting for redirect to app.envato.com...")
                try:
                    await page.wait_for_url("**/app.envato.com/**", timeout=1500)
                    redirected = True
                    print(f"[DEBUG] ✅ Redirected to: {page.url}")
                except:
                    print(f"[DEBUG] ⚠️ No redirect after 1.5s, staying on: {page.url}")

            print(f"[DEBUG] Final URL: {page.url}")

            # Click download button - универсальный селектор
            print("[DEBUG] Clicking download button...")

            # Пробуем найти кнопку по разным селекторам
            download_button_selectors = [
                "button:has-text('Скачать')",  # Универсальный по тексту
                "button[data-analytics-name='download']",  # Новый формат
                "button[data-testid='button-download']"  # Старый формат
            ]

            button_clicked = False
            for selector in download_button_selectors:
                try:
                    await page.wait_for_selector(selector, state="visible", timeout=3000)
                    await page.click(selector, delay=0)
                    print(f"[DEBUG] Clicked button with selector: {selector}")
                    button_clicked = True
                    break
                except Exception as e:
                    print(f"[DEBUG] Selector '{selector}' not found, trying next...")
                    continue

            if not button_clicked:
                print("[DEBUG] ❌ No download button found with any known selector")
                raise Exception("Download button not found")

            # Для старого формата нужен дополнительный клик
            if "elements.envato.com" in page.url:
                try:
                    await asyncio.sleep(0.5)
                    await page.click("button[data-testid='download-without-license-button']", delay=0)
                    print("[DEBUG] Clicked 'download without license' button")
                except:
                    pass

            print("[DEBUG] Button clicked, waiting for download event...")

            # Wait for download event with timeout
            max_wait = 5
            for i in range(max_wait * 10):  # Check every 0.1 seconds
                if download_info.get('url'):
                    print(f"[DEBUG] ✅ Download URL received after {i/10:.1f}s")
                    break
                await asyncio.sleep(0.1)
            else:
                print(f"[DEBUG] ❌ No download event after {max_wait}s, taking screenshot...")
                # Take screenshot for debugging if failed
                await page.screenshot(path="debug_after_click.png")
                print("[DEBUG] Screenshot saved: debug_after_click.png")

            # Get download URL
            download_url = download_info.get('url')

            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"   ✅ {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"   ❌ Download event не сработал")

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"   ❌ Ошибка: {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")
            return None

        finally:
            # Close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass


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
    test_url = "https://elements.envato.com/ru/smartphone-R8WRCX8"
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