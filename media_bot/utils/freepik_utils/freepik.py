import asyncio
import glob
import json
import os
import time

import nodriver as uc
from nodriver import cdp
from nodriver.core.connection import ProtocolException

from shared.provider_storage import cookie_directory

from .logger import logger

COOKIE_DIR = cookie_directory("freepik", os.path.dirname(__file__))
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


# Персистентный профиль браузера (подход из Trade/ADR-002): тёплый профиль хранит
# cf_clearance (Cloudflare) и Akamai-куки (_abck, bm_sz, ak_bmsc) между перезапусками
# процесса → reload-трюк от Akamai-сенсора проходит надёжнее, меньше 403.
# Профиль ОДИН (общий), т.к. браузер тут singleton (см. _shared_downloader ниже);
# auth-куки конкретного аккаунта всё равно подменяются per-download через CDP.
PROFILE_DIR = os.path.join(os.path.dirname(__file__), ".profile")


def _cleanup_singleton_locks(profile_dir: str) -> None:
    """Снимаем lock-файлы от прошлого краша Chromium (иначе 'profile in use')."""
    for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            os.unlink(os.path.join(profile_dir, lock_name))
        except FileNotFoundError:
            pass
        except Exception:
            pass


class FreepikDownloader:
    """
    Freepik downloader using nodriver (undetected Chrome, bypasses Cloudflare).
    """

    def __init__(self, *, cookies=None, profile_dir=None):
        self.browser = None
        self.cookies = cookies
        self.profile_dir = profile_dir or PROFILE_DIR
        self.total_time = 0
        self.success_count = 0
        self.fail_count = 0

    async def __aenter__(self):
        # sandbox=False нужен для запуска в Docker (root без песочницы)
        # Если системный Chrome не найден — используем Chromium от Playwright
        chromium_path = find_chromium_executable()
        # Тёплый персистентный профиль: cf_clearance/Akamai-куки переживают рестарт.
        os.makedirs(self.profile_dir, exist_ok=True)
        _cleanup_singleton_locks(self.profile_dir)
        self.browser = await uc.start(
            headless=False,
            sandbox=False,
            browser_executable_path=chromium_path,  # None = автопоиск системного Chrome
            user_data_dir=self.profile_dir,  # persistent → cf_clearance не сбрасывается
        )
        return self

    async def __aexit__(self, *args):
        if self.browser:
            try:
                self.browser.stop()
            except Exception as e:
                print(f"⚠️ [FREEPIK] Ошибка при закрытии браузера: {e}")

    async def _find_button(self, tab, timeout: float = 15):
        """Находит кнопку скачивания заново (свежий node id, без переиспользования)."""
        deadline = time.monotonic() + timeout
        # Hydration can replace the document before nodriver's selector wait completes.
        # Poll the live DOM and resolve a fresh node only after the button is ready.
        while time.monotonic() < deadline:
            try:
                ready = await tab.evaluate(
                    "(() => { const b = document.querySelector('button[data-cy=\"download-button\"]');"
                    " return !!b && !b.disabled && b.getClientRects().length > 0; })()"
                )
                if ready:
                    btn = await tab.select('button[data-cy="download-button"]', timeout=1)
                    if btn:
                        return btn
            except (StopIteration, RuntimeError, ProtocolException):
                pass
            await asyncio.sleep(0.25)
        for text in ("Download", "Скачать"):
            try:
                btn = await tab.find(text, best_match=True, timeout=5)
                if btn and btn.tag_name in ("button", "a"):
                    return btn
            except (StopIteration, RuntimeError, ProtocolException):
                continue
        return None

    async def _click_download(self, tab, button=None) -> bool:
        """
        Кликает по найденной кнопке, перезапрашивая её при повторной попытке.
        Защита от ProtocolException "-32000 Could not find node with given id":
        React-SPA перерисовывает DOM после гидрации, и старый хэндл протухает.
        """
        for attempt in range(3):
            btn = button if attempt == 0 else None
            if btn is None:
                btn = await self._find_button(tab, timeout=15 if attempt == 0 else 5)
            if not btn:
                return False
            try:
                await btn.click()
                return True
            except (StopIteration, RuntimeError, ProtocolException) as e:
                print(f"[FREEPIK] клик #{attempt + 1} не удался ({e}), переищем кнопку")
                await asyncio.sleep(0.5)
        return False

    async def get_download_url(self, asset_url: str) -> str | None:
        """
        Get direct download URL using network request interception.

        Простая стратегия: загружаем куки → открываем URL напрямую →
        если 403, ждём (Akamai sensor работает на 403-странице) → перезагружаем.
        """
        tab = None
        on_download = None
        start_time = time.time()
        download_url = None

        try:
            raw_cookies = self.cookies
            if raw_cookies is None:
                cookie_file = get_next_cookie_file()
                with open(cookie_file, "r") as f:
                    raw_cookies = json.load(f)

            # Открываем about:blank и загружаем куки
            tab = await self.browser.get("about:blank")
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

            # Очищаем URL от Akamai bm-verify параметра
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(asset_url)
            clean_params = {
                k: v
                for k, v in parse_qs(parsed.query).items()
                if not k.startswith("bm-verify") and not k.startswith("bm_")
            }
            clean_query = urlencode(clean_params, doseq=True)
            # Search fragments are tracking metadata, not part of the asset address.
            asset_url = urlunparse(parsed._replace(query=clean_query, fragment=""))

            # Открываем ссылку напрямую
            print(f"[FREEPIK] 📄 Открываем страницу ресурса...")
            nav_done = asyncio.Event()

            async def _navigate():
                try:
                    await tab.get(asset_url)
                except Exception:
                    pass
                nav_done.set()

            asyncio.create_task(_navigate())
            try:
                await asyncio.wait_for(nav_done.wait(), timeout=20)
            except asyncio.TimeoutError:
                print("[FREEPIK] ⏳ Таймаут навигации, продолжаем...")

            # Сразу перезагружаем — Akamai sensor успевает отработать
            # на первой загрузке, вторая проходит без 403
            await asyncio.sleep(0.1)
            print("[FREEPIK] 🔄 Перезагружаем страницу...")
            reload_done = asyncio.Event()

            async def _reload():
                try:
                    await tab.get(asset_url)
                except Exception:
                    pass
                reload_done.set()

            asyncio.create_task(_reload())
            try:
                await asyncio.wait_for(reload_done.wait(), timeout=20)
            except asyncio.TimeoutError:
                print("[FREEPIK] ⏳ Таймаут перезагрузки, продолжаем...")

            # Перехватываем событие начала скачивания — содержит прямой URL
            download_info = {}
            download_ready = asyncio.Event()

            def handle_download(evt: cdp.page.DownloadWillBegin):
                if not download_info.get("url"):
                    download_info["url"] = evt.url
                    download_ready.set()

            on_download = handle_download
            tab.add_handler(cdp.page.DownloadWillBegin, on_download)

            # Запрещаем реальное скачивание файла — нам нужна только ссылка
            await tab.send(
                cdp.browser.set_download_behavior(
                    behavior="deny",
                    browser_context_id=None,
                )
            )

            # Ищем кнопку скачивания (первичная проверка, что она вообще есть)
            btn = await self._find_button(tab, timeout=15)
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

            # Reuse the fresh node; the helper resolves it again if hydration invalidates it.
            await self._click_download(tab, button=btn)

            # Ждём URL скачивания (до 10 секунд)
            try:
                await asyncio.wait_for(download_ready.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

            # Если не нашли — повторный клик
            if not download_info.get("url"):
                print(f"[FREEPIK] Download URL не найден, повторный клик...")
                await self._click_download(tab)
                try:
                    await asyncio.wait_for(download_ready.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass

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
                # nodriver's remove_handler also removes other callbacks for this event.
                callbacks = tab.handlers.get(cdp.page.DownloadWillBegin, [])
                if on_download in callbacks:
                    callbacks.remove(on_download)
                try:
                    # Не закрываем таб — закрытие последнего таба убивает браузер.
                    # Навигируем на about:blank для очистки.
                    # Wait for navigation acknowledgement without Tab.get's idle delay.
                    await tab.send(cdp.page.navigate("about:blank"))
                except Exception:
                    pass


# Синглтон — один браузер на весь процесс.
# nodriver не переживает повторные uc.start()/browser.stop() циклы.
_shared_downloader: FreepikDownloader | None = None
_downloader_lock = asyncio.Lock()


async def _get_shared_downloader() -> FreepikDownloader:
    """Возвращает (или создаёт) общий FreepikDownloader."""
    global _shared_downloader
    async with _downloader_lock:
        if _shared_downloader is None or _shared_downloader.browser is None:
            _shared_downloader = FreepikDownloader()
            await _shared_downloader.__aenter__()
            print("[FREEPIK] 🚀 Браузер запущен (singleton)")
        return _shared_downloader


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
    if os.getenv("FREEPIK_HTTP_ENABLED", "0") == "1":
        from media_bot.services import BotServices

        if BotServices.link_processor:
            return await BotServices.link_processor.submit(asset_url, platform="freepik")
        return None

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
        semaphore = None

    async def _do_download() -> str | None:
        try:
            downloader = await _get_shared_downloader()
            return await downloader.get_download_url(asset_url)
        except Exception as e:
            # Если браузер умер — сбрасываем синглтон, следующий вызов пересоздаст
            global _shared_downloader
            if _shared_downloader is not None:
                try:
                    await _shared_downloader.__aexit__(None, None, None)
                except Exception:
                    pass
                _shared_downloader = None
            print(f"❌ [FREEPIK] Браузер упал, сброс: {e}")
            return None

    if semaphore:
        async with semaphore:
            link = await _do_download()
    else:
        link = await _do_download()

    if link:
        print(f"✅ [FREEPIK] Прямая ссылка получена")
    else:
        print("❌ [FREEPIK] Не удалось получить ссылку")
    return link
