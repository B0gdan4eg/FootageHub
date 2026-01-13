import asyncio
import json
import os
import time

from playwright.async_api import async_playwright

from .logger import logger

COOKIE_DIR = os.path.dirname(__file__)
COOKIE_INDEX_FILE = os.path.join(COOKIE_DIR, "freepik_cookie_index.txt")


def get_next_cookie_file():
    """
    Получает следующий файл с куками из списка доступных файлов.
    Использует ротацию: cookie_1.json -> cookie_2.json -> cookie_3.json -> cookie_1.json...
    """
    # Находим все файлы freepik_cookies_*.json
    cookie_files = []
    for filename in os.listdir(COOKIE_DIR):
        if filename.startswith("freepik_cookies") and filename.endswith(".json"):
            cookie_files.append(os.path.join(COOKIE_DIR, filename))

    # Если нет файлов с паттерном freepik_cookies_*.json, используем старый файл
    if not cookie_files:
        legacy_file = os.path.join(COOKIE_DIR, "freepik_cookies.json")
        if os.path.exists(legacy_file):
            return legacy_file
        raise FileNotFoundError("No cookie files found in freepik_utils/")

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
        f"[FREEPIK] 🔄 Using cookie file: {os.path.basename(selected_file)} ({next_index + 1}/{len(cookie_files)})"
    )
    return selected_file


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
                    download_info["url"] = download.url
                    # Отменяем скачивание, нам нужна только ссылка
                    await download.cancel()
                except Exception as e:
                    print(f"⚠️ [FREEPIK] Ошибка: {e}")

            page.on("download", handle_download)

            # Navigate to asset page
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=15000)

            # Click download button
            await page.click("button[data-cy='download-button']", timeout=5000)

            # Ждём download event (увеличено до 5 секунд для надежности)
            max_wait = 5
            for i in range(max_wait * 10):
                if download_info.get("url"):
                    break
                await asyncio.sleep(0.1)

            # Если download event не сработал, пробуем кликнуть ещё раз
            if not download_info.get("url"):
                print(f"[FREEPIK] Download event не сработал, повторный клик...")
                await page.click("button[data-cy='download-button']", timeout=5000)

                # Ждём ещё 5 секунд
                for i in range(max_wait * 10):
                    if download_info.get("url"):
                        break
                    await asyncio.sleep(0.1)

            # Получаем ссылку
            download_url = download_info.get("url")

            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"✅ [FREEPIK] Ссылка получена за {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"❌ [FREEPIK] Download event не сработал")

                # Делаем скриншот для отладки
                import os

                screenshot_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                await page.screenshot(path=screenshot_path, full_page=False)

                await logger.error(
                    f"❌ [FREEPIK] Download event не сработал\n" f"URL: {asset_url}",
                    screenshot_path=screenshot_path,
                )

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"❌ [FREEPIK] Ошибка: {e}")

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
                    print(f"[FREEPIK] Failed to save screenshot: {e}")
                    screenshot_path = None

            await logger.error(
                f"❌ [FREEPIK] Ошибка: {e}\n" f"URL: {asset_url}", screenshot_path=screenshot_path
            )
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
