"""
Motion Array downloader using CDP (Chrome DevTools Protocol)
"""

import asyncio
import json
import os
import time
from playwright.async_api import async_playwright
from freepik_utils.logger import logger

COOKIE_DIR = os.path.dirname(__file__)
COOKIE_INDEX_FILE = os.path.join(COOKIE_DIR, "motion_cookie_index.txt")


def get_next_cookie_file():
    """
    Получает следующий файл с куками из списка доступных файлов.
    Использует ротацию: motion_cookies_1.json -> motion_cookies_2.json -> ...
    """
    # Находим все файлы motion_cookies_*.json
    cookie_files = []
    for filename in os.listdir(COOKIE_DIR):
        if filename.startswith("motion_cookies") and filename.endswith(".json"):
            cookie_files.append(os.path.join(COOKIE_DIR, filename))

    # Если нет файлов с паттерном motion_cookies_*.json, используем старый файл
    if not cookie_files:
        legacy_file = os.path.join(COOKIE_DIR, "motion_cookies.json")
        if os.path.exists(legacy_file):
            return legacy_file
        raise FileNotFoundError("No cookie files found in motion_utils/")

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

    print(f"[MOTION] 🔄 Using cookie file: {os.path.basename(selected_file)} ({next_index + 1}/{len(cookie_files)})")
    return selected_file


class MotionDownloader:
    """
    Motion Array downloader using CDP (Chrome DevTools Protocol).
    Supports URL interception for direct download links.
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
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Получаем следующий файл с куками (ротация)
        cookie_file = get_next_cookie_file()
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        
        # Stealth mode
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        
        # Load cookies
        with open(cookie_file, "r") as f:
            await self.context.add_cookies(json.load(f))
        
        return self

    async def __aexit__(self, *args):
        # Закрываем контекст перед браузером для корректной очистки
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                print(f"⚠️ [MOTION] Ошибка при закрытии контекста: {e}")

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                print(f"⚠️ [MOTION] Ошибка при закрытии браузера: {e}")

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                print(f"⚠️ [MOTION] Ошибка при остановке playwright: {e}")

        total = self.success_count + self.fail_count
        if total > 0:
            avg_time = self.total_time / total
            print("\n" + "="*70)
            print("📊 [MOTION] СТАТИСТИКА:")
            print(f"   ✅ Успешно: {self.success_count}")
            print(f"   ❌ Провалов: {self.fail_count}")
            print(f"   ⏱️  Общее время: {self.total_time:.2f} сек")
            print(f"   ⏱️  Среднее время: {avg_time:.2f} сек/ссылка")
            print("="*70)

    async def get_download_url(self, asset_url: str) -> str | None:
        """
        Get direct download URL using CDP network interception.
        
        Args:
            asset_url: URL of the Motion Array asset page
            
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
            
            # Перехватываем /download/direct endpoint
            async def on_response(event):
                nonlocal download_url
                url = event.get("response", {}).get("url", "")
                status = event.get("response", {}).get("status", 0)
                
                if '/download/direct' in url and status == 200:
                    try:
                        request_id = event.get("requestId")
                        body = await client.send("Network.getResponseBody", {"requestId": request_id})
                        data = json.loads(body.get("body", "{}"))
                        
                        if data.get("success") and data.get("downloadUrls"):
                            download_url = data["downloadUrls"][0]
                    except Exception as e:
                        print(f"[MOTION] ⚠️ Error in response handler: {e}")
            
            client.on("Network.responseReceived", on_response)
            
            # Открываем страницу
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=15000)
            
            await asyncio.sleep(0.5)
            
            # Кликаем на Download
            button_clicked = False
            
            try:
                selector = "span:has-text('Download')"
                
                # ДОБАВЬ эту строку:
                await page.wait_for_selector(selector, state="visible", timeout=10000)
                
                elements = await page.query_selector_all(selector)
                
                for element in elements:
                    is_visible = await element.is_visible()
                    if is_visible:
                        await element.click(delay=0)
                        button_clicked = True
                        break
                        
            except Exception as e:
                print(f"[MOTION] ⚠️ Error in click handler: {e}")
            
            if not button_clicked:
                raise Exception("Download button not found")
            
            # Ждем ответа от API
            max_wait = 5
            for _ in range(max_wait * 10):
                await asyncio.sleep(0.1)
                if download_url:
                    break
            
            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"   ✅ {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"   ❌ Download URL не получен")
                
                # Делаем скриншот для отладки
                screenshot_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                await page.screenshot(path=screenshot_path, full_page=False)
                
                # ← ДОБАВЬ ЭТО:
                await logger.error(
                    f"❌ [MOTION] Download URL не получен\n"
                    f"URL: {asset_url}",
                    screenshot_path=screenshot_path
                )

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"   ❌ Ошибка: {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")

            # Скриншот
            screenshot_path = None
            if page:
                try:
                    screenshot_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    screenshot_path = os.path.join(screenshot_dir, f"error_{int(time.time())}.png")
                    await page.screenshot(path=screenshot_path, full_page=False)
                except Exception as screenshot_error:
                    print(f"[MOTION] Failed to save screenshot: {screenshot_error}")
                    screenshot_path = None
            
            # ← ДОБАВЬ ЭТО:
            await logger.error(
                f"❌ [MOTION] Ошибка при скачивании\n"
                f"URL: {asset_url}\n"
                f"Ошибка: {e}",
                screenshot_path=screenshot_path
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


# Main API function for bot integration
async def get_motion_direct_download_url(asset_url: str) -> str | None:
    """
    Get direct download URL for a single Motion Array asset.
    This is the main function used by the bot.
    
    Args:
        asset_url: URL of the Motion Array asset page
        
    Returns:
        Direct download URL or None if failed
        
    Example:
        url = await get_motion_direct_download_url("https://motionarray.com/...")
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

    print(f"🚀 [MOTION] Загружаем: {asset_url}")

    if semaphore:
        async with semaphore:
            async with MotionDownloader() as downloader:
                link = await downloader.get_download_url(asset_url)

                if link:
                    print(f"✅ [MOTION] Прямая ссылка получена")
                    return link
                else:
                    print(f"❌ [MOTION] Не удалось получить ссылку")
                    return None
    else:
        async with MotionDownloader() as downloader:
            link = await downloader.get_download_url(asset_url)

            if link:
                print(f"✅ [MOTION] Прямая ссылка получена")
                return link
            else:
                print(f"❌ [MOTION] Не удалось получить ссылку")
                return None
