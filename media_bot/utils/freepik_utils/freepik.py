import asyncio
import glob
import json
import os
import time

import nodriver as uc
from nodriver import cdp

from .logger import logger

COOKIE_DIR = os.path.dirname(__file__)
COOKIE_INDEX_FILE = os.path.join(COOKIE_DIR, "freepik_cookie_index.txt")


def find_chromium_executable() -> str | None:
    """Ищет Chromium от Playwright если системный Chrome не найден."""
    patterns = [
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/home/*/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/ms-playwright/chromium-*/chrome-linux/chrome",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


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
    Freepik downloader using nodriver (undetected Chrome, bypasses Cloudflare).
    """

    def __init__(self):
        self.browser = None
        self.total_time = 0
        self.success_count = 0
        self.fail_count = 0

    async def __aenter__(self):
        # sandbox=False нужен для запуска в Docker (root без песочницы)
        # Если системный Chrome не найден — используем Chromium от Playwright
        chromium_path = find_chromium_executable()
        self.browser = await uc.start(
            headless=False,
            sandbox=False,
            browser_executable_path=chromium_path,  # None = автопоиск системного Chrome
        )
        return self

    async def __aexit__(self, *args):
        if self.browser:
            try:
                self.browser.stop()
            except Exception as e:
                print(f"⚠️ [FREEPIK] Ошибка при закрытии браузера: {e}")

    async def get_download_url(self, asset_url: str) -> str | None:
        """
        Get direct download URL using network request interception.

        Args:
            asset_url: URL of the Freepik asset page

        Returns:
            Direct download URL or None if failed
        """
        tab = None
        start_time = time.time()
        download_url = None

        try:
            tab = await self.browser.get("about:blank")

            # Загружаем куки через CDP
            cookie_file = get_next_cookie_file()
            with open(cookie_file, "r") as f:
                raw_cookies = json.load(f)

            for c in raw_cookies:
                try:
                    await tab.send(
                        cdp.network.set_cookie(
                            name=c["name"],
                            value=c["value"],
                            domain=c.get("domain", ".freepik.com"),
                            path=c.get("path", "/"),
                            secure=c.get("secure", False),
                            http_only=c.get("httpOnly", False),
                        )
                    )
                except Exception:
                    pass

            # Перехватываем событие начала скачивания — содержит прямой URL
            download_info = {}

            def on_download(evt: cdp.page.DownloadWillBegin):
                if not download_info.get("url"):
                    download_info["url"] = evt.url

            tab.add_handler(cdp.page.DownloadWillBegin, on_download)

            # Запрещаем реальное скачивание файла — нам нужна только ссылка
            await tab.send(
                cdp.browser.set_download_behavior(
                    behavior="deny",
                    browser_context_id=None,
                )
            )

            # Переходим на страницу ресурса
            # nodriver бросает StopIteration (-> RuntimeError в async) при проблемах навигации
            try:
                await tab.get(asset_url)
            except (StopIteration, RuntimeError) as e:
                if "StopIteration" in str(type(e).__name__) or "StopIteration" in str(e):
                    print(f"⚠️ [FREEPIK] Retry navigation after StopIteration...")
                    await asyncio.sleep(1)
                    await tab.get(asset_url)
                else:
                    raise

            # Ищем кнопку скачивания
            # nodriver бросает StopIteration (-> RuntimeError в async) если элемент не найден
            btn = None
            # 1) По data-cy атрибуту
            try:
                btn = await tab.select('button[data-cy="download-button"]', timeout=15)
            except (StopIteration, RuntimeError):
                pass
            # 2) Фоллбэк: ищем по тексту "Download" / "Скачать"
            if not btn:
                for text in ("Download", "Скачать"):
                    try:
                        btn = await tab.find(text, best_match=True, timeout=5)
                        if btn and btn.tag_name in ("button", "a"):
                            break
                        btn = None
                    except (StopIteration, RuntimeError):
                        btn = None
            if not btn:
                self.fail_count += 1
                elapsed = time.time() - start_time
                self.total_time += elapsed
                print(f"❌ [FREEPIK] Кнопка скачивания не найдена ({elapsed:.2f} сек)")

                screenshot_dir = os.path.join(COOKIE_DIR, "debug_screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                try:
                    await tab.save_screenshot(screenshot_path)
                except Exception:
                    screenshot_path = None

                await logger.error(
                    f"❌ [FREEPIK] Кнопка скачивания не найдена\nURL: {asset_url}",
                    screenshot_path=screenshot_path,
                )
                return None

            try:
                await btn.click()
            except (StopIteration, RuntimeError):
                # nodriver иногда бросает StopIteration при клике
                await asyncio.sleep(0.5)
                try:
                    await btn.click()
                except (StopIteration, RuntimeError):
                    pass

            # Ждём URL скачивания (до 10 секунд)
            for _ in range(100):
                if download_info.get("url"):
                    break
                await asyncio.sleep(0.1)

            # Если не нашли — повторный клик
            if not download_info.get("url"):
                print(f"[FREEPIK] Download URL не найден, повторный клик...")
                try:
                    await btn.click()
                except (StopIteration, RuntimeError):
                    pass
                for _ in range(100):
                    if download_info.get("url"):
                        break
                    await asyncio.sleep(0.1)

            download_url = download_info.get("url")
            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"✅ [FREEPIK] Ссылка получена за {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"❌ [FREEPIK] Download URL не найден")

                screenshot_dir = os.path.join(COOKIE_DIR, "debug_screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                await tab.save_screenshot(screenshot_path)

                await logger.error(
                    f"❌ [FREEPIK] Download URL не найден\nURL: {asset_url}",
                    screenshot_path=screenshot_path,
                )

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"❌ [FREEPIK] Ошибка: {e}")

            screenshot_path = None
            if tab:
                try:
                    screenshot_dir = os.path.join(COOKIE_DIR, "debug_screenshots")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                    await tab.save_screenshot(screenshot_path)
                except Exception:
                    screenshot_path = None

            await logger.error(
                f"❌ [FREEPIK] Ошибка: {e}\nURL: {asset_url}",
                screenshot_path=screenshot_path,
            )
            return None

        finally:
            if tab:
                try:
                    # Не закрываем таб — закрытие последнего таба убивает браузер,
                    # и следующий вызов get_download_url падает с StopIteration.
                    # Вместо этого просто навигируем на пустую страницу.
                    await tab.get("about:blank")
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
