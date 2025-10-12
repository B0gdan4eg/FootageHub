from playwright.async_api import async_playwright
import json
import os
import asyncio
import time
from datetime import datetime

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "envato_cookies.json")


# async def get_envato_direct_download_url(asset_url: str) -> str | None:
#     """
#     Получает прямую ссылку на скачивание с Envato Elements.
#     ПРОВЕРЕННАЯ РАБОЧАЯ ВЕРСИЯ.
    
#     Args:
#         asset_url: URL страницы ассета на Envato Elements
        
#     Returns:
#         Прямая ссылка на скачивание или None в случае ошибки
#     """
#     if not os.path.exists(COOKIE_FILE):
#         print(f"❌ Файл cookies не найден: {COOKIE_FILE}")
#         return None

#     start_time = time.time()

#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)
#         context = await browser.new_context(accept_downloads=True)

#         with open(COOKIE_FILE, "r") as f:
#             cookies = json.load(f)
#         await context.add_cookies(cookies)

#         page = await context.new_page()
        
#         try:
#             await page.goto(asset_url, wait_until='networkidle', timeout=60000)
            
#             await page.wait_for_selector("button[data-testid='button-download']", timeout=15000)
#             await page.click("button[data-testid='button-download']")
            
#             await page.wait_for_selector("button[data-testid='download-without-license-button']", timeout=15000)

#             async with page.expect_download(timeout=30000) as download_info:
#                 await page.click("button[data-testid='download-without-license-button']")

#             download = await download_info.value
            
#             elapsed = time.time() - start_time
#             print(f"⏱️  Время выполнения: {elapsed:.2f} сек")
            
#             return download.url

#         except Exception as e:
#             elapsed = time.time() - start_time
#             print(f"❌ Ошибка: {e}")
#             print(f"⏱️  Время до ошибки: {elapsed:.2f} сек")
#             return None
            
#         finally:
#             await browser.close()


# === СТАРЫЙ КЛАСС (для сравнения) ===

class EnvatoDownloader:
    """
    Класс для переиспользования одного браузера (последовательное скачивание).
    """
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.total_time = 0
        self.success_count = 0
        self.fail_count = 0
    
    async def __aenter__(self):
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(accept_downloads=True)
        
        with open(COOKIE_FILE, "r") as f:
            await self.context.add_cookies(json.load(f))
        
        return self
    
    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        if self.success_count + self.fail_count > 0:
            avg_time = self.total_time / (self.success_count + self.fail_count)
            print("\n" + "="*70)
            print("📊 СТАТИСТИКА (последовательное):")
            print(f"   ✅ Успешно: {self.success_count}")
            print(f"   ❌ Провалов: {self.fail_count}")
            print(f"   ⏱️  Общее время: {self.total_time:.2f} сек")
            print(f"   ⏱️  Среднее время: {avg_time:.2f} сек/ссылка")
            print("="*70)
    
    async def get_download_url(self, asset_url: str) -> str | None:
        page = await self.context.new_page()
        start_time = time.time()
        
        try:
            await page.goto(asset_url, wait_until='networkidle', timeout=60000)
            
            await page.wait_for_selector("button[data-testid='button-download']", timeout=15000)
            await page.click("button[data-testid='button-download']")
            
            await page.wait_for_selector("button[data-testid='download-without-license-button']", timeout=15000)
            
            async with page.expect_download(timeout=30000) as download_info:
                await page.click("button[data-testid='download-without-license-button']")
            
            download = await download_info.value
            
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.success_count += 1
            print(f"   ⏱️  {elapsed:.2f} сек")
            
            return download.url
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"   ❌ Ошибка: {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")
            return None
        finally:
            await page.close()




async def get_envato_direct_download_url(asset_url: str):
    """СТАРОЕ: Последовательное скачивание (для сравнения)"""
    urls = [
        "https://elements.envato.com/ru/the-most-useful-transitions-pack-for-premiere-pro-XSNY4PV",
        "https://elements.envato.com/ru/split-object-transitions-for-premiere-pro-CF64CPD",
        "https://elements.envato.com/ru/multiscreen-slideshow-74YYWAU",
        "https://elements.envato.com/ru/text-intro-LBX3JMH",
        "https://elements.envato.com/ru/vertical-carousel-slideshow-92FX73P",
        "https://elements.envato.com/ru/light-transitions-for-premiere-pro-Q6VN9AM",
        "https://elements.envato.com/ru/logo-reveal-U3MQ6DB",
        "https://elements.envato.com/ru/logo-animated-T9TMYG8",
        "https://elements.envato.com/ru/elegant-glossy-logo-7PDZCVD",
        "https://elements.envato.com/ru/simple-minimal-logo-reveal-SEPFCPQ",
        "https://elements.envato.com/ru/the-most-useful-transitions-pack-for-premiere-pro-XSNY4PV",
        "https://elements.envato.com/ru/split-object-transitions-for-premiere-pro-CF64CPD",
        "https://elements.envato.com/ru/multiscreen-slideshow-74YYWAU",
        "https://elements.envato.com/ru/text-intro-LBX3JMH",
        "https://elements.envato.com/ru/vertical-carousel-slideshow-92FX73P",
        "https://elements.envato.com/ru/light-transitions-for-premiere-pro-Q6VN9AM",
        "https://elements.envato.com/ru/logo-reveal-U3MQ6DB",
        "https://elements.envato.com/ru/logo-animated-T9TMYG8",
        "https://elements.envato.com/ru/elegant-glossy-logo-7PDZCVD",
        "https://elements.envato.com/ru/simple-minimal-logo-reveal-SEPFCPQ",
        "https://elements.envato.com/ru/the-most-useful-transitions-pack-for-premiere-pro-XSNY4PV",
        "https://elements.envato.com/ru/split-object-transitions-for-premiere-pro-CF64CPD",
        "https://elements.envato.com/ru/multiscreen-slideshow-74YYWAU",
        "https://elements.envato.com/ru/text-intro-LBX3JMH",
        "https://elements.envato.com/ru/vertical-carousel-slideshow-92FX73P",
        "https://elements.envato.com/ru/light-transitions-for-premiere-pro-Q6VN9AM",
        "https://elements.envato.com/ru/logo-reveal-U3MQ6DB",
        "https://elements.envato.com/ru/logo-animated-T9TMYG8",
        "https://elements.envato.com/ru/elegant-glossy-logo-7PDZCVD",
        "https://elements.envato.com/ru/simple-minimal-logo-reveal-SEPFCPQ",
    ]
    
    print(f"🚀 Последовательное скачивание {len(urls)} ссылок...\n")
    print(f"🕐 Начало: {datetime.now().strftime('%H:%M:%S')}\n")
    
    async with EnvatoDownloader() as downloader:
        for i, url in enumerate(asset_url, 1):
            print(f"[{i}/{len(urls)}] {url}")
            link = await downloader.get_download_url(url)
            
            if link:
                print(f"   ✅ {link[:80]}...\n")
            else:
                print()



# if __name__ == "__main__":
    
#     asyncio.run(main_sequential())     # СТАРОЕ: Последовательно