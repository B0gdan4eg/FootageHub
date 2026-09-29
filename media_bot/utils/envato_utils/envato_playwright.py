import asyncio
import json
import logging
import os
import time
import uuid
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from media_bot.utils.freepik_utils.logger import logger

from .asset_identity import checked_identity, describe_requested, legacy_asset

audit = logging.getLogger(__name__)

# --- Diagnostics: distinct failure causes, never lump every timeout as Cloudflare.
# Markers are intentionally narrow; unknown pages stay "page_changed/timeout".
CLOUDFLARE_MARKERS = (
    "just a moment",
    "verifying you are human",
    "cf-challenge",
    "challenge-platform",
    "checking your browser",
    "attention required",
    "security verification",
    "challenges.cloudflare.com",
    "cdn-cgi/challenge",
)
AUTH_URL_MARKERS = ("/login", "/sign-in", "signin", "auth.envato")
AUTH_PAGE_MARKERS = (
    "sign in to download",
    "log in to download",
    "subscribe to download",
    "you need a subscription",
    "join envato elements",
    "choose a plan",
)
NOT_FOUND_MARKERS = (
    "page not found",
    "couldn't find",
    "could not find",
    "item unavailable",
    "has been removed",
    "no longer available",
    "error 404",
)
# Admin is notified at most once per hour per downloader for manual checks.
MANUAL_ALERT_INTERVAL = 3600.0
SCREENSHOT_TIMEOUT_MS = 5000


def _new_task_id() -> str:
    return uuid.uuid4().hex[:8]


def _contains_any(haystack: str, needles) -> bool:
    hay = haystack.lower()
    return any(n in hay for n in needles)


def classify_static_failure(page_url: str, title: str, content: str) -> str:
    """Map page state to a narrow failure reason (no cookies/tokens involved)."""
    blob = f"{page_url}\n{title}\n{content[:60000]}"
    if _contains_any(blob, CLOUDFLARE_MARKERS):
        return "cloudflare_challenge"
    if _contains_any(page_url, AUTH_URL_MARKERS) or _contains_any(
        f"{title}\n{content[:20000]}", AUTH_PAGE_MARKERS
    ):
        return "auth_required"
    if _contains_any(blob, NOT_FOUND_MARKERS):
        return "item_unavailable"
    return ""


async def _inspect_page(page, timeout_ms: int = 3000) -> dict:
    """Best-effort snapshot for failure classification; never raises."""
    info: dict = {"url": "", "title": "", "content": ""}
    if page is None:
        return info
    try:
        info["url"] = page.url or ""
    except Exception:
        pass
    try:
        info["title"] = await asyncio.wait_for(page.title(), timeout=timeout_ms / 1000)
    except Exception:
        pass
    try:
        content = await asyncio.wait_for(page.content(), timeout=timeout_ms / 1000)
        info["content"] = content or ""
    except Exception:
        pass
    return info


async def _take_debug_screenshot(page, prefix: str = "error") -> str | None:
    """Bounded screenshot helper; failures never mask the original error."""
    if page is None:
        return None
    try:
        screenshot_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"{prefix}_{int(time.time())}.png")
        await page.screenshot(path=screenshot_path, full_page=False, timeout=SCREENSHOT_TIMEOUT_MS)
        return screenshot_path
    except Exception as screenshot_error:
        print(f"[ENVATO] Failed to save screenshot: {screenshot_error}")
        return None


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


# Персистентные профили браузера: по одному на cookie-файл (= на аккаунт).
# Тёплый профиль хранит cf_clearance от Cloudflare и историю → повторный
# челлендж не прилетает (подход из Trade/ADR-002). Профиль НЕ чистится между
# запусками; auth-куки аккаунта подсыпаются заново каждый раз (seed).
PROFILE_BASE = os.path.join(COOKIE_DIR, ".profiles")

# Один persistent-профиль нельзя открыть двумя процессами Chromium сразу.
# При MAX_CONCURRENT_DOWNLOADS>1 два скачивания одного аккаунта должны
# сериализоваться на своём профиле; разные аккаунты идут параллельно.
_PROFILE_LOCKS: dict[str, asyncio.Lock] = {}


def missing_seed_cookies(seed, current, now=None):
    """Keep refreshed profile cookies instead of overwriting them with an old export."""
    now = time.time() if now is None else now
    existing = {
        (c["name"], c["domain"], c.get("path", "/"))
        for c in current
        if c.get("expires", -1) == -1 or c.get("expires", 0) > now
    }
    return [
        c
        for c in seed
        if (c["name"], c["domain"], c.get("path", "/")) not in existing
        and (c.get("expires", -1) == -1 or c.get("expires", 0) > now)
    ]


def _profile_dir_for(cookie_file: str) -> str:
    name = os.path.splitext(os.path.basename(cookie_file))[0]  # envato_cookies_2
    return os.path.join(PROFILE_BASE, name)


def _get_profile_lock(profile_dir: str) -> asyncio.Lock:
    lock = _PROFILE_LOCKS.get(profile_dir)
    if lock is None:
        lock = asyncio.Lock()
        _PROFILE_LOCKS[profile_dir] = lock
    return lock


def _cleanup_singleton_locks(profile_dir: str) -> None:
    """Снимаем lock-файлы от прошлого краша Chromium (иначе 'profile in use')."""
    for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            os.unlink(os.path.join(profile_dir, lock_name))
        except FileNotFoundError:
            pass
        except Exception:
            pass


class EnvatoDownloader:
    """
    Advanced Envato Elements downloader using CDP (Chrome DevTools Protocol).
    Supports both single and batch processing with URL interception.
    """

    def __init__(self, *, cookie_file=None, profile_dir=None, cookies=None):
        self.cookie_file = cookie_file
        self.profile_override = profile_dir
        self.seed_cookies = cookies
        self.last_asset = None
        self.last_failure = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.profile_dir = None
        self._profile_lock = None
        self._lock_acquired = False
        self.total_time = 0
        self.success_count = 0
        self.fail_count = 0
        self.http_fast = None
        # Per-request isolation: shared counters guard against concurrent updates;
        # last_asset/last_failure remain "last completed" for backwards compat,
        # task-scoped details go to structured audit logs with task_id.
        self._stats_lock = asyncio.Lock()
        self._active_lock = asyncio.Lock()
        self._active = 0
        self._last_manual_alert = 0.0

    async def _track_start(self) -> None:
        async with self._active_lock:
            self._active += 1

    async def _track_finish(self) -> None:
        async with self._active_lock:
            self._active = max(0, self._active - 1)

    async def active_tasks(self) -> int:
        async with self._active_lock:
            return self._active

    async def _record_result(self, success: bool, elapsed: float) -> None:
        async with self._stats_lock:
            self.total_time += elapsed
            if success:
                self.success_count += 1
            else:
                self.fail_count += 1

    async def _notify_manual_check(self, task_id: str, reason: str, requested: dict) -> None:
        now = time.monotonic()
        if now - self._last_manual_alert < MANUAL_ALERT_INTERVAL:
            return
        self._last_manual_alert = now
        try:
            await logger.error(
                f"❌ [ENVATO] Требуется ручная проверка: {reason}\n"
                f"task={task_id} requested={requested}"
            )
        except Exception:
            pass

    async def __aenter__(self):
        self.playwright = await async_playwright().start()

        # Получаем следующий файл с куками (ротация) и его персистентный профиль
        cookie_file = self.cookie_file or get_next_cookie_file()
        self.cookie_file = cookie_file
        self.profile_dir = self.profile_override or _profile_dir_for(cookie_file)

        # Лочим профиль: два процесса Chromium на одном user_data_dir = краш.
        # Ждём ограниченное время, чтобы не зависать вечно при занятом профиле.
        self._profile_lock = _get_profile_lock(self.profile_dir)
        try:
            await asyncio.wait_for(self._profile_lock.acquire(), timeout=120)
        except asyncio.TimeoutError as exc:
            await self.playwright.stop()
            self.playwright = None
            raise RuntimeError(f"Envato profile busy: {self.profile_dir}") from exc
        self._lock_acquired = True

        try:
            os.makedirs(self.profile_dir, exist_ok=True)
            _cleanup_singleton_locks(self.profile_dir)

            # Персистентный контекст: тёплый профиль с сохранённым cf_clearance.
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                headless=False,
                viewport={"width": 1920, "height": 1080},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            # Подсыпаем auth-куки аккаунта. cf_clearance в профиле НЕ затирается
            # (его нет в файле кук), поэтому остаётся тёплым между запусками.
            if self.seed_cookies is not None:
                await self.context.add_cookies(self.seed_cookies)
            else:
                with open(cookie_file, "r") as f:
                    seed = json.load(f)
                missing = missing_seed_cookies(seed, await self.context.cookies())
                if missing:
                    await self.context.add_cookies(missing)
        except Exception:
            # __aexit__ не вызовется если __aenter__ упал — чистим сами
            if self._lock_acquired and self._profile_lock:
                self._profile_lock.release()
                self._lock_acquired = False
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None
            raise

        if os.getenv("ENVATO_BROWSER_HTTP_ENABLED", "0") == "1":
            from .browser_http import BrowserHTTP

            directory = os.getenv("ENVATO_BROWSER_HTTP_STATE_DIR", self.profile_dir)
            self.http_fast = BrowserHTTP(os.path.join(directory, os.path.basename(cookie_file)))
        return self

    async def __aexit__(self, *args):
        if self.http_fast:
            await self.http_fast.close()
        # launch_persistent_context не создаёт отдельный browser — закрываем контекст
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                print(f"⚠️ [ENVATO] Ошибка при закрытии контекста: {e}")
        self.context = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                print(f"⚠️ [ENVATO] Ошибка при остановке playwright: {e}")
        self.playwright = None

        # Освобождаем профиль для следующего скачивания этого аккаунта
        if self._lock_acquired and self._profile_lock:
            self._profile_lock.release()
            self._lock_acquired = False

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

    async def get_download_url(self, asset_url: str, task_id: str | None = None) -> str | None:
        """
        Get direct download URL using download event interception.
        Supports both old (elements.envato.com) and new (app.envato.com) site formats.

        Only the item-detail button is eligible; its UUID/type must match the
        requested item (or the server redirect for legacy URLs). Recommendations
        or generic matches are never used.

        Args:
            asset_url: URL of the Envato Elements asset page
            task_id: optional correlation id for structured diagnostics

        Returns:
            Direct download URL or None if failed
        """
        task = task_id or _new_task_id()
        requested = describe_requested(asset_url)
        overall_start = time.monotonic()
        stage_marks: dict[str, float] = {}

        def _mark(name: str) -> None:
            stage_marks[name] = round(time.monotonic() - overall_start, 3)

        def _exc_suffix(exc: BaseException) -> str:
            if isinstance(exc, (PlaywrightTimeoutError, asyncio.TimeoutError, TimeoutError)):
                return "timeout"
            return type(exc).__name__

        page = None
        start_time = time.time()
        download_url = None
        self.last_asset = None
        self.last_failure = None
        stage = "navigation"
        response_tasks = []
        selected_asset = None
        legacy_verified = False

        if self.http_fast:
            http_started = time.monotonic()
            try:
                link = await self.http_fast.get(asset_url, task_id=task)
            except TypeError:
                link = await self.http_fast.get(asset_url)
            if link:
                _mark("http_hit")
                audit.info(
                    "Envato http_hit task=%s requested=%s seconds=%.3f",
                    task,
                    requested,
                    round(time.monotonic() - http_started, 3),
                )
                return link
            audit.info(
                "Envato http_miss task=%s requested=%s seconds=%.3f",
                task,
                requested,
                round(time.monotonic() - http_started, 3),
            )

        await self._track_start()
        try:
            page = await self.context.new_page()

            # Блокируем только тяжёлое превью-видео (media, те самые ~1.5ГБ).
            # CSS/картинки/шрифты НЕ трогаем: без них страница рендерится сломанной,
            # кнопка скачивания становится "невидимой" для Playwright (нулевой размер),
            # а пустой профиль ресурсов — сильный бот-сигнал для Cloudflare.
            await page.route(
                "**/*",
                lambda route: (
                    route.abort() if route.request.resource_type == "media" else route.continue_()
                ),
            )

            # Перехватываем download event
            download_info: dict = {"url": None, "seen": 0, "last_status": 0, "invalid": 0}

            async def handle_download(download):
                try:
                    if legacy_verified and not selected_asset:
                        download_info["url"] = download.url
                    # Отменяем скачивание, нам нужна только ссылка
                    await download.cancel()
                except Exception as e:
                    print(f"[ENVATO] ⚠️ Error in download handler: {e}")

            page.on("download", handle_download)

            async def handle_response(response):
                parsed = urlsplit(response.url)
                if parsed.hostname != "app.envato.com" or parsed.path != "/download.data":
                    return
                download_info["seen"] = int(download_info.get("seen", 0)) + 1
                try:
                    download_info["last_status"] = int(response.status)
                except Exception:
                    pass
                params = parse_qs(parsed.query)
                if not selected_asset or (
                    params.get("itemUuid") != [selected_asset[1]]
                    or params.get("itemType") != [selected_asset[0]]
                ):
                    return
                try:
                    from .http_downloader import download_link

                    link = (
                        download_link(await response.json(), expected_item=selected_asset[1])
                        if response.status == 200
                        else None
                    )
                    if link:
                        if self.http_fast:
                            try:
                                await self.http_fast.remember(
                                    asset_url,
                                    selected_asset,
                                    await response.request.all_headers(),
                                    await self.context.cookies(),
                                )
                            except Exception as exc:
                                audit.warning(
                                    "Envato mapping persistence failed error=%s", type(exc).__name__
                                )
                        download_info["url"] = link
                        audit.info(
                            "Envato item resolved task=%s legacy=%s item=%s type=%s",
                            task,
                            legacy_asset(asset_url),
                            selected_asset[1],
                            selected_asset[0],
                        )
                    else:
                        download_info["invalid"] = int(download_info.get("invalid", 0)) + 1
                except Exception:
                    download_info["invalid"] = int(download_info.get("invalid", 0)) + 1

            page.on(
                "response",
                lambda response: response_tasks.append(
                    asyncio.create_task(handle_response(response))
                ),
            )

            # Navigate to asset page
            _mark("goto_start")
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=45000)
            _mark("navigated")
            final_url = ""
            try:
                final_url = page.url or ""
            except Exception:
                pass
            redirected = "elements.envato.com" not in final_url

            # Wait for redirect to app.envato.com if needed
            if "elements.envato.com" in page.url:
                try:
                    await page.wait_for_url("**/app.envato.com/**", timeout=3000)
                except Exception:
                    # No redirect happened - staying on old format (elements.envato.com)
                    pass
            _mark("redirect_checked")

            # Click download button - универсальный селектор для обоих форматов
            # Используем JS-клик чтобы обойти overlay-попапы (New plans, Easier way to find licenses)
            # Recommendation cards also have Download buttons. Only the item-detail
            # control is eligible, and its UUID must match the requested item.
            stage = "item_button"
            # Cloudflare-проверка иногда проходит со 2-й попытки (визит греет
            # челлендж-профиль): при cloudflare_challenge перезагружаем страницу,
            # максимум 2 повтора с паузами. Остальные причины — сразу в ошибку.
            primary = None
            challenge_retries = 0
            button_timeout = 30000
            while True:
                try:
                    primary = await page.wait_for_selector(
                        "button[data-cy='idp-download-button'], button[data-testid='button-download']",
                        state="visible",
                        timeout=button_timeout,
                    )
                    break
                except Exception as exc:
                    # Раздельная диагностика: Cloudflare / auth / 404 / page change / timeout.
                    info = await _inspect_page(page)
                    refined = classify_static_failure(info["url"], info["title"], info["content"])
                    if refined == "cloudflare_challenge" and challenge_retries < 2:
                        challenge_retries += 1
                        _mark(f"challenge_retry_{challenge_retries}")
                        audit.info(
                            "Envato challenge_retry task=%s requested=%s attempt=%s",
                            task,
                            requested,
                            challenge_retries,
                        )
                        try:
                            await page.reload(wait_until="domcontentloaded", timeout=30000)
                        except Exception:
                            pass
                        await asyncio.sleep(3)
                        button_timeout = 20000
                        continue
                    suffix = refined or _exc_suffix(exc)
                    self.last_failure = f"item_button_{suffix}"
                    await self._record_result(False, time.time() - start_time)
                    _mark("item_button_failed")
                    screenshot_path = await _take_debug_screenshot(page, prefix="error")
                    if suffix in ("cloudflare_challenge", "auth_required"):
                        await self._notify_manual_check(task, suffix, requested)
                    audit.info(
                        "Envato browser_failed task=%s requested=%s stage=%s reason=%s "
                        "challenge_retries=%s page_url=%s title=%.80s seconds=%s",
                        task,
                        requested,
                        stage,
                        self.last_failure,
                        challenge_retries,
                        (info["url"] or "")[:200],
                        (info["title"] or ""),
                        stage_marks.get("item_button_failed"),
                    )
                    await logger.error(
                        f"❌ [ENVATO] Кнопка скачивания не найдена\n"
                        f"URL: {asset_url}\n"
                        f"task={task} reason={self.last_failure}",
                        screenshot_path=screenshot_path,
                    )
                    return None
            if challenge_retries:
                _mark("challenge_passed")
            # Old Elements can render its button before redirecting to the new app.
            if "elements.envato.com" in page.url:
                try:
                    await page.wait_for_url("**/app.envato.com/**", timeout=3000)
                    primary = await page.wait_for_selector(
                        "button[data-cy='idp-download-button']", state="visible", timeout=15000
                    )
                except PlaywrightTimeoutError:
                    pass
            item_id = await primary.get_attribute("data-analytics-item_id")
            item_type = await primary.get_attribute("data-analytics-item_type")
            try:
                selected_asset = checked_identity(asset_url, page.url, item_type, item_id)
            except ValueError as exc:
                self.last_failure = "identity_mismatch"
                await self._record_result(False, time.time() - start_time)
                _mark("identity_failed")
                audit.info(
                    "Envato identity_mismatch task=%s requested=%s page_url=%s "
                    "button_type=%s button_id=%s error=%s",
                    task,
                    requested,
                    (page.url or "")[:200],
                    item_type,
                    item_id,
                    type(exc).__name__,
                )
                screenshot_path = await _take_debug_screenshot(page, prefix="error")
                await logger.error(
                    f"❌ [ENVATO] Несоответствие товара (чужой файл исключён)\n"
                    f"URL: {asset_url}\n"
                    f"task={task} reason=identity_mismatch",
                    screenshot_path=screenshot_path,
                )
                return None
            self.last_asset = selected_asset
            legacy_verified = selected_asset is None
            _mark("identity_ok")
            download_button_selectors = [
                (
                    "button[data-cy='idp-download-button']"
                    if item_id
                    else "button[data-testid='button-download']"
                )
            ]

            stage = "click"
            button_clicked = False
            for selector in download_button_selectors:
                try:
                    btn = await page.wait_for_selector(selector, state="visible", timeout=2000)
                    if btn:
                        try:
                            await primary.click(delay=0, timeout=3000)
                        except Exception:
                            # Если overlay блокирует клик — кликаем через JS
                            await primary.evaluate("el => el.click()")
                        button_clicked = True
                        break
                except Exception:
                    continue
            _mark("clicked")

            if not button_clicked:
                self.last_failure = "click_button_not_found"
                await self._record_result(False, time.time() - start_time)
                info = await _inspect_page(page)
                refined = classify_static_failure(info["url"], info["title"], info["content"])
                if refined:
                    self.last_failure = f"click_{refined}"
                    if refined in ("cloudflare_challenge", "auth_required"):
                        await self._notify_manual_check(task, refined, requested)
                screenshot_path = await _take_debug_screenshot(page, prefix="error")
                audit.info(
                    "Envato browser_failed task=%s requested=%s stage=%s reason=%s seconds=%s",
                    task,
                    requested,
                    stage,
                    self.last_failure,
                    stage_marks.get("clicked"),
                )
                await logger.error(
                    f"❌ [ENVATO] Кнопка скачивания не нажата\n"
                    f"URL: {asset_url}\n"
                    f"task={task} reason={self.last_failure}",
                    screenshot_path=screenshot_path,
                )
                return None

            # Для старого формата нужен дополнительный клик
            if "elements.envato.com" in page.url:
                try:
                    await asyncio.sleep(0.5)
                    await page.click(
                        "button[data-testid='download-without-license-button']", delay=0
                    )
                except Exception:
                    pass

            # Wait for download event with timeout
            stage = "download_response"
            max_wait = 5
            for i in range(max_wait * 10):  # Check every 0.1 seconds
                if download_info.get("url"):
                    break
                await asyncio.sleep(0.1)
            _mark("response_waited")

            # Get download URL
            download_url = download_info.get("url")

            elapsed = time.time() - start_time

            if download_url:
                await self._record_result(True, elapsed)
                _mark("done")
                audit.info(
                    "Envato browser_success task=%s requested=%s item=%s type=%s "
                    "redirected=%s stages=%s seconds=%.3f",
                    task,
                    requested,
                    (selected_asset or (None, None))[1],
                    (selected_asset or (None, None))[0],
                    redirected,
                    stage_marks,
                    elapsed,
                )
                print(f"   ✅ {elapsed:.2f} сек")
            else:
                seen = int(download_info.get("seen", 0))
                invalid = int(download_info.get("invalid", 0))
                last_status = int(download_info.get("last_status", 0) or 0)
                info = await _inspect_page(page)
                refined = classify_static_failure(info["url"], info["title"], info["content"])
                if refined in ("cloudflare_challenge", "auth_required", "item_unavailable"):
                    self.last_failure = f"download_response_{refined}"
                    await self._notify_manual_check(task, refined, requested)
                elif seen and last_status and last_status != 200:
                    self.last_failure = f"download_response_http_{last_status}"
                elif seen and invalid:
                    self.last_failure = "download_response_invalid_file_link"
                elif seen:
                    self.last_failure = "download_response_item_mismatch"
                else:
                    self.last_failure = "missing_download_response"
                await self._record_result(False, elapsed)
                print("   ❌ Download event не сработал")

                screenshot_path = await _take_debug_screenshot(page, prefix="error")
                audit.info(
                    "Envato browser_failed task=%s requested=%s stage=%s reason=%s "
                    "seen=%s invalid=%s http_status=%s stages=%s seconds=%.3f",
                    task,
                    requested,
                    stage,
                    self.last_failure,
                    seen,
                    invalid,
                    last_status,
                    stage_marks,
                    elapsed,
                )

                await logger.error(
                    f"❌ [ENVATO] Download event не сработал\n"
                    f"URL: {asset_url}\n"
                    f"task={task} reason={self.last_failure} "
                    f"seen={seen} http_status={last_status}",
                    screenshot_path=screenshot_path,
                )

            return download_url

        except Exception as e:
            suffix = _exc_suffix(e)
            # Не считаем любой таймаут блокировкой Cloudflare: уточняем по странице.
            refined = ""
            page_info: dict | None = None
            if page is not None and stage in ("navigation", "click", "download_response"):
                try:
                    page_info = await _inspect_page(page)
                    refined = classify_static_failure(
                        page_info["url"], page_info["title"], page_info["content"]
                    )
                except Exception:
                    refined = ""
            # ValueError идентификации уже обработан выше; здесь только прочие сбои.
            if isinstance(e, ValueError) and stage == "item_button":
                self.last_failure = "identity_mismatch"
            elif refined in ("cloudflare_challenge", "auth_required", "item_unavailable"):
                self.last_failure = f"{stage}_{refined}"
                await self._notify_manual_check(task, refined, requested)
            else:
                # Совместимость: прежний формат stage + имя исключения,
                # таймауты помечаем явно как timeout.
                self.last_failure = stage + "_" + suffix
            elapsed = time.time() - start_time
            await self._record_result(False, elapsed)
            print(f"   ❌ Ошибка: {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")
            audit.info(
                "Envato browser_failed task=%s requested=%s stage=%s reason=%s "
                "error=%s seconds=%.3f",
                task,
                requested,
                stage,
                self.last_failure,
                type(e).__name__,
                elapsed,
            )

            # Делаем скриншот при ошибке; его сбой не скрывает исходную ошибку.
            screenshot_path = await _take_debug_screenshot(page, prefix="error")

            await logger.error(
                f"❌ [ENVATO] Ошибка при скачивании\n"
                f"URL: {asset_url}\n"
                f"task={task} reason={self.last_failure} Ошибка: {e}",
                screenshot_path=screenshot_path,
            )
            return None

        finally:
            await self._track_finish()
            for task_item in response_tasks:
                if not task_item.done():
                    task_item.cancel()
            await asyncio.gather(*response_tasks, return_exceptions=True)
            # Close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def get_download_url_with_license(
        self, asset_url: str, task_id: str | None = None
    ) -> str | None:
        """
        Get direct download URL WITH license using CDP network interception.
        This method clicks "Download with license" button instead of "without license".
        Based on test results from test_envato_lisence.py

        Args:
            asset_url: URL of the Envato Elements asset page
            task_id: optional correlation id for structured diagnostics

        Returns:
            Direct download URL or None if failed
        """
        task = task_id or _new_task_id()
        requested = describe_requested(asset_url)
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
            # JS-клик чтобы обойти overlay-попапы (New plans, Easier way to find licenses)
            try:
                await page.click("button[data-testid='button-download']", timeout=3000)
            except Exception:
                btn = await page.wait_for_selector(
                    "button[data-testid='button-download']", state="visible", timeout=5000
                )
                if btn:
                    await btn.evaluate("el => el.click()")
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
            await self._record_result(bool(download_url), elapsed)

            if download_url:
                audit.info(
                    "Envato licensed_success task=%s requested=%s seconds=%.3f",
                    task,
                    requested,
                    elapsed,
                )
                print(f"   ✅ {elapsed:.2f} сек (WITH LICENSE)")
            else:
                self.last_failure = "licensed_missing_download_response"
                audit.info(
                    "Envato licensed_failed task=%s requested=%s reason=%s seconds=%.3f",
                    task,
                    requested,
                    self.last_failure,
                    elapsed,
                )
                print("   ❌ Не получен URL (WITH LICENSE)")
                await logger.error(
                    f"❌ [ENVATO] Download URL не получен (WITH LICENSE)\n"
                    f"URL: {asset_url}\ntask={task} reason={self.last_failure}"
                )

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            await self._record_result(False, elapsed)
            self.last_failure = "licensed_" + (
                "timeout"
                if isinstance(e, (PlaywrightTimeoutError, asyncio.TimeoutError, TimeoutError))
                else type(e).__name__
            )
            print(f"   ❌ Ошибка (WITH LICENSE): {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")
            audit.info(
                "Envato licensed_failed task=%s requested=%s reason=%s error=%s seconds=%.3f",
                task,
                requested,
                self.last_failure,
                type(e).__name__,
                elapsed,
            )

            # Делаем скриншот при ошибке; его сбой не скрывает исходную ошибку.
            screenshot_path = await _take_debug_screenshot(page, prefix="error")

            await logger.error(
                f"❌ [ENVATO] Ошибка при скачивании (WITH LICENSE)\n"
                f"URL: {asset_url}\n"
                f"task={task} reason={self.last_failure} Ошибка: {e}",
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
