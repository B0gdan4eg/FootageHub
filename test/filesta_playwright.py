import asyncio
import json
import os
import time
from playwright.async_api import async_playwright

COOKIE_DIR = os.path.dirname(__file__)
COOKIE_INDEX_FILE = os.path.join(COOKIE_DIR, "filesta_cookie_index.txt")


def get_next_cookie_file():
    """
    Получает следующий файл с куками из списка доступных файлов.
    Использует ротацию: cookie_1.json -> cookie_2.json -> cookie_3.json -> cookie_1.json...
    """
    # Находим все файлы filesta_cookies_*.json
    cookie_files = []
    for filename in os.listdir(COOKIE_DIR):
        if filename.startswith("filesta_cookies") and filename.endswith(".json"):
            cookie_files.append(os.path.join(COOKIE_DIR, filename))

    # Если нет файлов с паттерном filesta_cookies_*.json, используем старый файл
    if not cookie_files:
        legacy_file = os.path.join(COOKIE_DIR, "filesta_cookies.json")
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
        except:
            current_index = 0

    # Выбираем следующий файл (с оборачиванием)
    next_index = (current_index + 1) % len(cookie_files)
    selected_file = cookie_files[next_index]

    # Сохраняем новый индекс
    with open(COOKIE_INDEX_FILE, "w") as f:
        f.write(str(next_index))

    print(f"[FILESTA] 🔄 Using cookie file: {os.path.basename(selected_file)} ({next_index + 1}/{len(cookie_files)})")
    return selected_file


class FilestaDownloader:
    """
    Filesta.com downloader using CDP (Chrome DevTools Protocol).
    Supports URL interception to capture direct download links.
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
                print(f"⚠️ [FILESTA] Ошибка при закрытии контекста: {e}")

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                print(f"⚠️ [FILESTA] Ошибка при закрытии браузера: {e}")

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                print(f"⚠️ [FILESTA] Ошибка при остановке playwright: {e}")

        total = self.success_count + self.fail_count
        if total > 0:
            avg_time = self.total_time / total
            print("\n" + "="*70)
            print("📊 [FILESTA] СТАТИСТИКА:")
            print(f"   ✅ Успешно: {self.success_count}")
            print(f"   ❌ Провалов: {self.fail_count}")
            print(f"   ⏱️  Общее время: {self.total_time:.2f} сек")
            print(f"   ⏱️  Среднее время: {avg_time:.2f} сек/ссылка")
            print("="*70)

    async def get_download_url(self, envato_url: str) -> str | None:
        """
        Get direct download URL using CDP network interception.

        Args:
            envato_url: URL of the Envato Elements asset to download via Filesta

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
                # Ищем ответы, которые могут содержать ссылку на скачивание
                if "download" in url.lower() or "envato" in url.lower():
                    captured_responses.append(event)

            client.on("Network.responseReceived", on_response)

            # Navigate to Filesta page
            await page.goto("https://www.filesta.com/envato", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1)  # Wait for page to fully load

            # Fill input field with Envato URL
            await page.fill("input#envatoFile", envato_url, timeout=15000)
            await asyncio.sleep(1)  # Wait for input to be processed

            # Wait for button to be visible and clickable
            await page.wait_for_selector("a#envatoDownload", state="visible", timeout=15000)

            # Try multiple click methods
            try:
                # Method 1: Regular click
                await page.click("a#envatoDownload", timeout=5000)
            except:
                try:
                    # Method 2: Force click (ignore if covered by other elements)
                    await page.click("a#envatoDownload", force=True, timeout=5000)
                except:
                    # Method 3: JavaScript click as last resort
                    await page.evaluate("document.getElementById('envatoDownload').click()")

            # Wait for download URL from intercepted network responses or page navigation
            download_url = await self._wait_for_download_url(client, page, captured_responses, timeout=30)

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

    async def _wait_for_download_url(self, client, page, captured_responses, timeout=30) -> str | None:
        """
        Wait for download URL to appear in intercepted network responses or as a download event.

        Args:
            client: CDP client session
            page: Playwright page instance
            captured_responses: List of captured network responses
            timeout: Maximum wait time in seconds

        Returns:
            Download URL or None if timeout
        """
        start = time.time()
        download_url = None

        # Set up download handler
        async def handle_download(download):
            nonlocal download_url
            download_url = download.url

        page.on("download", handle_download)

        while time.time() - start < timeout:
            # Check if download started
            if download_url:
                return download_url

            # Check captured network responses for redirect or direct download links
            for resp in captured_responses:
                try:
                    url = resp.get("response", {}).get("url", "")

                    # Check if response is a redirect to download
                    status = resp.get("response", {}).get("status", 0)
                    if status in [301, 302, 303, 307, 308]:
                        headers = resp.get("response", {}).get("headers", {})
                        location = headers.get("location") or headers.get("Location")
                        if location and ("download" in location.lower() or "elements.envatousercontent.com" in location):
                            return location

                    # Check if this is a direct download URL
                    if "elements.envatousercontent.com" in url or "video-downloads" in url:
                        return url

                    # Try to get response body
                    try:
                        body = await client.send("Network.getResponseBody", {"requestId": resp["requestId"]})
                        data = json.loads(body["body"])

                        # Look for download URL in various possible keys
                        url_candidates = [
                            data.get("downloadUrl"),
                            data.get("url"),
                            data.get("data", {}).get("downloadUrl"),
                            data.get("data", {}).get("url"),
                        ]

                        for candidate in url_candidates:
                            if candidate and ("download" in candidate.lower() or "elements.envatousercontent.com" in candidate):
                                return candidate
                    except:
                        continue
                except Exception:
                    continue

            await asyncio.sleep(0.2)

        return None


# Main API function for bot integration
async def get_filesta_download_url(envato_url: str) -> str | None:
    """
    Get direct download URL for an Envato Elements asset via Filesta.com.
    This is the main function used by the bot.

    Args:
        envato_url: URL of the Envato Elements asset page

    Returns:
        Direct download URL or None if failed

    Example:
        url = await get_filesta_download_url("https://elements.envato.com/ru/...")
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
    except:
        # Если запускается не из бота (тесты), семафор не нужен
        semaphore = None

    print(f"🚀 [FILESTA] Загружаем через Filesta.com: {envato_url}")

    if semaphore:
        async with semaphore:
            async with FilestaDownloader() as downloader:
                link = await downloader.get_download_url(envato_url)

                if link:
                    print(f"✅ [FILESTA] Прямая ссылка получена")
                    return link
                else:
                    print(f"❌ [FILESTA] Не удалось получить ссылку")
                    return None
    else:
        async with FilestaDownloader() as downloader:
            link = await downloader.get_download_url(envato_url)

            if link:
                print(f"✅ [FILESTA] Прямая ссылка получена")
                return link
            else:
                print(f"❌ [FILESTA] Не удалось получить ссылку")
                return None
