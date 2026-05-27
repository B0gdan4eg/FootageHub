"""
Эксперимент: Envato через ПЕРСИСТЕНТНЫЙ профиль (подход из Trade/ADR-002).

Отличие от боевого EnvatoDownloader:
  - launch_persistent_context(user_data_dir=...) вместо свежего launch() каждый раз
    → профиль с историей переживает запуски, cf_clearance от Cloudflare сохраняется,
      повторный челлендж не прилетает.
  - --disable-blink-features=AutomationControlled (слабее палимся как бот).
  - Куки из ротации подсыпаются в профиль (seed), но профиль НЕ чистится между прогонами.

Диагностика:
  - детект Cloudflare-челленджа ("Just a moment" / "Verify you are human");
  - лог сетевых запросов к download-эндпоинту (идея ADR-002: ловить XHR, а не клик);
  - перехват download event для получения прямой ссылки.

Запуск из корня проекта:
    python -m media_bot.utils.envato_utils.test_persistent
    python -m media_bot.utils.envato_utils.test_persistent <url1> <url2> ...
"""

import asyncio
import json
import os
import sys
import time

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    sys.path.insert(0, project_root)

from playwright.async_api import async_playwright

from media_bot.utils.envato_utils.envato_playwright import get_next_cookie_file

PROFILE_DIR = os.path.join(os.path.dirname(__file__), ".profile_test")

DEFAULT_TEST_URLS = [
    "https://elements.envato.com/lotus-pose-eneretic-aura-09-DQQCTPE",
]

DOWNLOAD_BUTTON_SELECTORS = [
    "button:has-text('Скачать')",
    "button:has-text('Download')",
    "button[data-analytics-name='download']",
    "button[data-testid='button-download']",
]

CF_MARKERS = ("just a moment", "verify you are human", "checking your browser", "cf-challenge")


async def detect_cloudflare(page) -> bool:
    """True если на странице висит Cloudflare-челлендж."""
    try:
        title = (await page.title()) or ""
        if any(m in title.lower() for m in CF_MARKERS):
            return True
        body = (await page.inner_text("body"))[:2000].lower()
        return any(m in body for m in CF_MARKERS)
    except Exception:
        return False


async def run(urls: list[str]):
    print("=" * 64)
    print("ЭКСПЕРИМЕНТ: Envato persistent profile")
    print(f"Профиль: {PROFILE_DIR}")
    print(f"Профиль уже существует: {os.path.isdir(PROFILE_DIR)}")
    print("=" * 64)

    os.makedirs(PROFILE_DIR, exist_ok=True)
    # Чистим singleton-локи от прошлого краша (как в Trade upscale_session.py:105).
    for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            os.unlink(os.path.join(PROFILE_DIR, lock))
        except FileNotFoundError:
            pass
        except Exception:
            pass

    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        viewport={"width": 1920, "height": 1080},
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )

    # Лог сетевых запросов к download-эндпоинту (диагностика идеи ADR-002).
    def on_request(req):
        url = req.url or ""
        if "download" in url.lower() and "envato" in url.lower():
            print(f"   [net] {req.method} {url[:110]}")

    ctx.on("request", on_request)

    # Seed: подсыпаем auth-куки из ротации в профиль (cf_clearance, если был, остаётся).
    try:
        cookie_file = get_next_cookie_file()
        with open(cookie_file, "r") as f:
            await ctx.add_cookies(json.load(f))
        print(f"✅ Куки подсыпаны из {os.path.basename(cookie_file)}")
    except Exception as e:
        print(f"⚠️  Не удалось подсыпать куки: {e}")

    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # Блокируем только тяжёлое media-превью (как в боевом фиксе).
    await page.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type == "media"
        else route.continue_(),
    )

    download_info = {}

    async def handle_download(download):
        try:
            download_info["url"] = download.url
            await download.cancel()
        except Exception as e:
            print(f"   ⚠️ download handler: {e}")

    page.on("download", handle_download)

    for idx, url in enumerate(urls, 1):
        download_info.clear()
        print(f"\n[{idx}] {url[:70]}")
        start = time.time()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            await asyncio.sleep(1.5)
            if await detect_cloudflare(page):
                print(
                    "   🛑 Cloudflare-челлендж на странице (жду 8с — реши вручную в окне, если можешь)"
                )
                await asyncio.sleep(8)
                if await detect_cloudflare(page):
                    print("   ❌ Челлендж не пройден")
                else:
                    print("   ✅ Челлендж пропал (cf_clearance осядет в профиле)")

            if "elements.envato.com" in page.url:
                try:
                    await page.wait_for_url("**/app.envato.com/**", timeout=3000)
                except Exception:
                    pass

            clicked = False
            for selector in DOWNLOAD_BUTTON_SELECTORS:
                try:
                    btn = await page.wait_for_selector(selector, state="visible", timeout=2000)
                    if btn:
                        try:
                            await page.click(selector, delay=0, timeout=3000)
                        except Exception:
                            await btn.evaluate("el => el.click()")
                        clicked = True
                        print(f"   ✅ Кнопка найдена: {selector}")
                        break
                except Exception:
                    continue

            if not clicked:
                print("   ❌ Кнопка скачивания не найдена/не видна")

            if "elements.envato.com" in page.url:
                try:
                    await asyncio.sleep(0.5)
                    await page.click(
                        "button[data-testid='download-without-license-button']", delay=0
                    )
                except Exception:
                    pass

            for _ in range(50):
                if download_info.get("url"):
                    break
                await asyncio.sleep(0.1)

            elapsed = time.time() - start
            link = download_info.get("url")
            if link:
                print(f"   ✅ Ссылка получена за {elapsed:.2f}с")
                print(f"   🔗 {link[:100]}")
            else:
                print(f"   ❌ Download event не сработал ({elapsed:.2f}с)")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")

    print("\nОкно закроется через 5с (профиль сохранится для следующего запуска)...")
    await asyncio.sleep(5)
    await ctx.close()
    await pw.stop()


def main():
    urls = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TEST_URLS
    asyncio.run(run(urls))


if __name__ == "__main__":
    main()
