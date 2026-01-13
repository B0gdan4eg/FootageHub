import asyncio
import json
import os
import time

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from media_bot.utils.freepik_utils.logger import logger

COOKIE_DIR = os.path.dirname(__file__)
COOKIE_INDEX_FILE = os.path.join(COOKIE_DIR, "cookie_index.txt")


def get_next_cookie_file():
    """
    Получает следующий файл с куками из списка доступных файлов.
    Использует ротацию: cookie_1.json -> cookie_2.json -> cookie_3.json -> cookie_1.json...
    """
    # Находим все файлы envato_cookies_*.json
    cookie_files = []
    for filename in os.listdir(COOKIE_DIR):
        if filename.startswith("envato_cookies") and filename.endswith(".json"):
            cookie_files.append(os.path.join(COOKIE_DIR, filename))

    # Если нет файлов с паттерном envato_cookies_*.json, используем старый файл
    if not cookie_files:
        legacy_file = os.path.join(COOKIE_DIR, "envato_cookies.json")
        if os.path.exists(legacy_file):
            return legacy_file
        raise FileNotFoundError("No cookie files found in envato_utils/")

    # Сортируем файлы для предсказуемого порядка
    cookie_files.sort()

    # Читаем текущий индекс
    current_index = 0
    if os.path.exists(COOKIE_INDEX_FILE):
        try:
            with open(COOKIE_INDEX_FILE, "r") as f:
                current_index = int(f.read().strip())
        except (ValueError, IOError) as e:
            print(f"[COOKIE] Failed to read cookie index, using 0: {e}")
            current_index = 0

    # Выбираем следующий файл (с оборачиванием)
    next_index = (current_index + 1) % len(cookie_files)
    selected_file = cookie_files[next_index]

    # Сохраняем новый индекс
    with open(COOKIE_INDEX_FILE, "w") as f:
        f.write(str(next_index))

    print(
        f"[ENVATO] 🔄 Using cookie file: {os.path.basename(selected_file)} ({next_index + 1}/{len(cookie_files)})"
    )
    return selected_file


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
        self.context = await self.browser.new_context(viewport={"width": 1920, "height": 1080})

        # Получаем следующий файл с куками (ротация)
        cookie_file = get_next_cookie_file()

        with open(cookie_file, "r") as f:
            await self.context.add_cookies(json.load(f))

        return self

    async def __aexit__(self, *args):
        # Закрываем контекст перед браузером для корректной очистки
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                print(f"⚠️ [ENVATO] Ошибка при закрытии контекста: {e}")

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                print(f"⚠️ [ENVATO] Ошибка при закрытии браузера: {e}")

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                print(f"⚠️ [ENVATO] Ошибка при остановке playwright: {e}")

        total = self.success_count + self.fail_count
        if total > 0:
            avg_time = self.total_time / total
            print("\n" + "=" * 70)
            print("📊 [ENVATO] СТАТИСТИКА:")
            print(f"   ✅ Успешно: {self.success_count}")
            print(f"   ❌ Провалов: {self.fail_count}")
            print(f"   ⏱️  Общее время: {self.total_time:.2f} сек")
            print(f"   ⏱️  Среднее время: {avg_time:.2f} сек/ссылка")
            print("=" * 70)

    async def get_download_url(self, asset_url: str) -> str | None:
        """
        Get direct download URL using download event interception.
        Supports both old (elements.envato.com) and new (app.envato.com) site formats.

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
                    download_info["url"] = download.url
                    # Отменяем скачивание, нам нужна только ссылка
                    await download.cancel()
                except Exception as e:
                    print(f"[ENVATO] ⚠️ Error in download handler: {e}")

            page.on("download", handle_download)

            # Navigate to asset page
            await page.goto(asset_url, wait_until="load", timeout=15000)

            # Wait for redirect to app.envato.com if needed
            if "elements.envato.com" in page.url:
                try:
                    await page.wait_for_url("**/app.envato.com/**", timeout=3000)
                except Exception:
                    # No redirect happened - staying on old format (elements.envato.com)
                    pass

            # Click download button - универсальный селектор для обоих форматов
            download_button_selectors = [
                "button:has-text('Скачать')",  # Универсальный по тексту
                "button[data-analytics-name='download']",  # Новый формат
                "button[data-testid='button-download']",  # Старый формат
            ]

            button_clicked = False
            for selector in download_button_selectors:
                try:
                    await page.wait_for_selector(selector, state="visible", timeout=2000)
                    await page.click(selector, delay=0)
                    button_clicked = True
                    break
                except Exception:
                    continue

            if not button_clicked:
                raise Exception("Download button not found")

            # Для старого формата нужен дополнительный клик
            if "elements.envato.com" in page.url:
                try:
                    await asyncio.sleep(0.5)
                    await page.click(
                        "button[data-testid='download-without-license-button']", delay=0
                    )
                except BaseException:
                    pass

            # Wait for download event with timeout
            max_wait = 5
            for i in range(max_wait * 10):  # Check every 0.1 seconds
                if download_info.get("url"):
                    break
                await asyncio.sleep(0.1)

            # Get download URL
            download_url = download_info.get("url")

            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"   ✅ {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"   ❌ Download event не сработал")

                # Делаем скриншот для отладки
                import os

                screenshot_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                await page.screenshot(path=screenshot_path, full_page=False)

                await logger.error(
                    f"❌ [ENVATO] Download event не сработал\n" f"URL: {asset_url}",
                    screenshot_path=screenshot_path,
                )

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"   ❌ Ошибка: {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")

            # Делаем скриншот при ошибке, если страница доступна
            screenshot_path = None
            if page:
                try:
                    import os

                    screenshot_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                    await page.screenshot(path=screenshot_path, full_page=False)
                except Exception as e:
                    print(f"[ENVATO] Failed to save screenshot: {e}")
                    screenshot_path = None

            await logger.error(
                f"❌ [ENVATO] Ошибка при скачивании\n" f"URL: {asset_url}\n" f"Ошибка: {e}",
                screenshot_path=screenshot_path,
            )
            return None

        finally:
            # Close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def get_download_url_with_license(self, asset_url: str) -> str | None:
        """
        Get direct download URL WITH license using CDP network interception.
        This method clicks "Download with license" button instead of "without license".
        Based on test results from test_envato_lisence.py

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
                if (
                    "download_and_license" in url
                    or "video-downloads.elements.envatousercontent.com" in url
                ):
                    captured_responses.append(event)

            client.on("Network.responseReceived", on_response)

            # Navigate to asset page
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=15000)

            # Close cookie banner if it appears - click "Reject All"
            try:
                # Wait for cookie dialog and click reject button
                await page.wait_for_selector("#CybotCookiebotDialog", timeout=1000)
                await page.click(
                    ".CybotCookiebotDialogBodyButton:has-text('Отклонить все')", timeout=1000
                )
                await asyncio.sleep(0.2)
            except (PlaywrightTimeoutError, TimeoutError):
                pass  # Cookie banner not found, continue

            # Step 1: Click download button to open modal
            await page.click("button[data-testid='button-download']", timeout=10000)
            await asyncio.sleep(1)  # Wait for modal to appear

            # Step 2: Click radio button to select project (from recorded_actions.json)
            await page.click(
                "input[type='radio'][name='project-list-radio-button-item']", timeout=10000
            )
            await asyncio.sleep(0.5)  # Wait for button to become enabled

            # Step 3: Click "Download with license" button (from recorded_actions.json)
            await page.click("button[data-testid='add-download-button']", timeout=10000)

            # Step 4: Wait for download URL from intercepted network responses
            download_url = await self._wait_for_download_url(client, captured_responses, timeout=5)

            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"   ✅ {elapsed:.2f} сек (WITH LICENSE)")
            else:
                self.fail_count += 1
                print(f"   ❌ Не получен URL (WITH LICENSE)")
                await logger.error(
                    f"❌ [ENVATO] Download URL не получен (WITH LICENSE)\nURL: {asset_url}"
                )

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"   ❌ Ошибка (WITH LICENSE): {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")

            # Делаем скриншот при ошибке, если страница доступна
            screenshot_path = None
            if page:
                try:
                    import os

                    screenshot_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                    await page.screenshot(path=screenshot_path, full_page=False)
                except Exception as e:
                    print(f"[ENVATO] Failed to save screenshot: {e}")
                    screenshot_path = None

            await logger.error(
                f"❌ [ENVATO] Ошибка при скачивании (WITH LICENSE)\n"
                f"URL: {asset_url}\n"
                f"Ошибка: {e}",
                screenshot_path=screenshot_path,
            )
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

    async def _wait_for_download_url(self, client, captured_responses, timeout=5) -> str | None:
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
                    body = await client.send(
                        "Network.getResponseBody", {"requestId": resp["requestId"]}
                    )
                    data = json.loads(body["body"])
                    url = data.get("data", {}).get("attributes", {}).get("downloadUrl")
                    if url:
                        return url
                except (json.JSONDecodeError, KeyError, Exception):
                    continue  # Try next response
            await asyncio.sleep(0.1)
        return None

    async def _wait_for_download_url_from_license(
        self, client, captured_responses, timeout=5
    ) -> str | None:
        """
        Wait for download URL to appear in intercepted network responses.
        Specifically looks for download_and_license API response.
        """
        start = time.time()
        while time.time() - start < timeout:
            for resp in captured_responses:
                try:
                    body = await client.send(
                        "Network.getResponseBody", {"requestId": resp["requestId"]}
                    )
                    data = json.loads(body["body"])

                    # Look for download URL in response body
                    url = (
                        data.get("data", {}).get("attributes", {}).get("downloadUrl")
                        or data.get("downloadUrl")
                        or data.get("url")
                    )

                    if url and (
                        "video-downloads.elements.envatousercontent.com" in url or "download" in url
                    ):
                        return url
                except Exception:
                    continue
            await asyncio.sleep(0.1)
        return None


# Main API function for bot integration
async def get_envato_direct_download_url(asset_url: str, with_license: bool = False) -> str | None:
    """
    Get direct download URL for a single Envato Elements asset.
    This is the main function used by the bot.

    Args:
        asset_url: URL of the Envato Elements asset page
        with_license: If True, downloads WITH license (requires active subscription)

    Returns:
        Direct download URL or None if failed

    Example:
        url = await get_envato_direct_download_url("https://elements.envato.com/ru/...")
        url_licensed = await get_envato_direct_download_url("https://elements.envato.com/ru/...", with_license=True)
    """
    # Проверяем наличие хотя бы одного файла с куками
    try:
        get_next_cookie_file()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return None

    # Используем семафор для ограничения параллельных скачиваний
    try:
        from bot.services import BotServices

        semaphore = BotServices.download_semaphore
    except (ImportError, AttributeError):
        # Если запускается не из бота (тесты), семафор не нужен
        semaphore = None

    license_mode = "WITH LICENSE" if with_license else "WITHOUT LICENSE"
    print(f"🚀 [ENVATO] Загружаем ({license_mode}): {asset_url}")

    if semaphore:
        async with semaphore:
            async with EnvatoDownloader() as downloader:
                if with_license:
                    link = await downloader.get_download_url_with_license(asset_url)
                else:
                    link = await downloader.get_download_url(asset_url)

                if link:
                    print(f"✅ [ENVATO] Прямая ссылка получена ({license_mode})")
                    return link
                else:
                    print(f"❌ [ENVATO] Не удалось получить ссылку ({license_mode})")
                    return None
    else:
        async with EnvatoDownloader() as downloader:
            if with_license:
                link = await downloader.get_download_url_with_license(asset_url)
            else:
                link = await downloader.get_download_url(asset_url)

            if link:
                print(f"✅ [ENVATO] Прямая ссылка получена ({license_mode})")
                return link
            else:
                print(f"❌ [ENVATO] Не удалось получить ссылку ({license_mode})")
                return None
