from playwright.async_api import async_playwright
import json
import os
import asyncio
import time
from datetime import datetime

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "envato_cookies.json")


async def get_envato_direct_download_url(asset_url: str) -> str | None:
    """
    Получает прямую ссылку на скачивание с Envato Elements.
    ПРОВЕРЕННАЯ РАБОЧАЯ ВЕРСИЯ.
    
    Args:
        asset_url: URL страницы ассета на Envato Elements
        
    Returns:
        Прямая ссылка на скачивание или None в случае ошибки
    """
    if not os.path.exists(COOKIE_FILE):
        print(f"❌ Файл cookies не найден: {COOKIE_FILE}")
        return None

    start_time = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)

        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)

        page = await context.new_page()
        
        try:
            await page.goto(asset_url, wait_until='networkidle', timeout=60000)
            
            await page.wait_for_selector("button[data-testid='button-download']", timeout=15000)
            await page.click("button[data-testid='button-download']")
            
            await page.wait_for_selector("button[data-testid='download-without-license-button']", timeout=15000)

            async with page.expect_download(timeout=30000) as download_info:
                await page.click("button[data-testid='download-without-license-button']")

            download = await download_info.value
            
            elapsed = time.time() - start_time
            print(f"⏱️  Время выполнения: {elapsed:.2f} сек")
            
            return download.url

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Ошибка: {e}")
            print(f"⏱️  Время до ошибки: {elapsed:.2f} сек")
            return None
            
        finally:
            await browser.close()


# === НОВЫЙ КЛАСС: ПАРАЛЛЕЛЬНЫЕ БРАУЗЕРЫ ===

class ParallelEnvatoDownloader:
    """
    Класс для параллельного скачивания с несколькими браузерами.
    Каждый браузер работает независимо = максимальная скорость!
    
    Использование:
        downloader = ParallelEnvatoDownloader(max_browsers=5)
        results = await downloader.download_all(urls)
    """
    
    def __init__(self, max_browsers: int = 3):
        """
        Args:
            max_browsers: Количество параллельных браузеров (по умолчанию 3)
        """
        self.max_browsers = max_browsers
        self.semaphore = asyncio.Semaphore(max_browsers)
        self.results = {}
        self.success_count = 0
        self.fail_count = 0
        self.total_time = 0
    
    async def download_single(self, url: str, index: int, total: int) -> tuple[str, str | None, float]:
        """Скачивает одну ссылку в отдельном браузере"""
        async with self.semaphore:
            start_time = time.time()
            
            print(f"[{index}/{total}] 🚀 Запуск: {url}")
            
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(accept_downloads=True)
                    
                    with open(COOKIE_FILE, "r") as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                    
                    page = await context.new_page()
                    
                    try:
                        await page.goto(url, wait_until='networkidle', timeout=60000)
                        
                        await page.wait_for_selector("button[data-testid='button-download']", timeout=15000)
                        await page.click("button[data-testid='button-download']")
                        
                        await page.wait_for_selector("button[data-testid='download-without-license-button']", timeout=15000)
                        
                        async with page.expect_download(timeout=30000) as download_info:
                            await page.click("button[data-testid='download-without-license-button']")
                        
                        download = await download_info.value
                        download_url = download.url
                        
                        elapsed = time.time() - start_time
                        self.success_count += 1
                        
                        print(f"[{index}/{total}] ✅ Успех за {elapsed:.2f} сек")
                        print(f"           {download_url[:80]}...")
                        
                        return url, download_url, elapsed
                        
                    finally:
                        await browser.close()
                        
            except Exception as e:
                elapsed = time.time() - start_time
                self.fail_count += 1
                
                print(f"[{index}/{total}] ❌ Провал за {elapsed:.2f} сек: {e}")
                
                return url, None, elapsed
    
    async def download_all(self, urls: list[str]) -> dict[str, str | None]:
        """
        Скачивает все ссылки параллельно.
        
        Args:
            urls: Список URL для скачивания
            
        Returns:
            Словарь {url: download_link или None}
        """
        print(f"🚀 Запуск {len(urls)} параллельных браузеров (макс. {self.max_browsers} одновременно)")
        print(f"🕐 Начало: {datetime.now().strftime('%H:%M:%S')}\n")
        
        start_time = time.time()
        
        # Создаём задачи для всех URL
        tasks = [
            self.download_single(url, i+1, len(urls)) 
            for i, url in enumerate(urls)
        ]
        
        # Запускаем все параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self.total_time = time.time() - start_time
        
        # Собираем результаты
        output = {}
        for item in results:
            if isinstance(item, tuple) and len(item) == 3:
                url, link, _ = item
                output[url] = link
            else:
                # Обработка исключений
                print(f"⚠️ Необработанное исключение: {item}")
        
        # Выводим статистику
        print("\n" + "="*70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   ✅ Успешно: {self.success_count}")
        print(f"   ❌ Провалов: {self.fail_count}")
        print(f"   ⏱️  Общее время: {self.total_time:.2f} сек")
        
        if len(urls) > 0:
            avg_time = self.total_time / len(urls)
            print(f"   ⏱️  Среднее время: {avg_time:.2f} сек/ссылка")
            
            # Эффективность параллелизма
            if self.success_count > 0:
                theoretical_time = 12.0 * len(urls)  # Примерно 12 сек на ссылку последовательно
                speedup = theoretical_time / self.total_time
                print(f"   🚀 Ускорение: {speedup:.1f}x (vs последовательное)")
        
        print(f"   🕐 Завершено: {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        return output


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


# === ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ===

async def main_parallel():
    """НОВОЕ: Параллельное скачивание с несколькими браузерами"""
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
    
    # Создаём downloader с 5 параллельными браузерами
    downloader = ParallelEnvatoDownloader(max_browsers=5)
    results = await downloader.download_all(urls)
    
    # Выводим результаты
    print("\n📋 ССЫЛКИ:")
    for i, (url, link) in enumerate(results.items(), 1):
        if link:
            print(f"{i}. ✅ {url}")
            print(f"   {link}\n")
        else:
            print(f"{i}. ❌ {url}\n")


async def main_sequential():
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
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url}")
            link = await downloader.get_download_url(url)
            
            if link:
                print(f"   ✅ {link[:80]}...\n")
            else:
                print()


async def compare_methods():
    """Сравнение параллельного и последовательного методов"""
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
    
    print("="*70)
    print("🔬 СРАВНЕНИЕ МЕТОДОВ")
    print("="*70)
    
    # Тест 1: Параллельное
    print("\n1️⃣  ПАРАЛЛЕЛЬНОЕ (5 браузеров)\n")
    start = time.time()
    downloader_parallel = ParallelEnvatoDownloader(max_browsers=5)
    results_parallel = await downloader_parallel.download_all(urls)
    time_parallel = time.time() - start
    
    # Тест 2: Последовательное
    print("\n2️⃣  ПОСЛЕДОВАТЕЛЬНОЕ (1 браузер)\n")
    start = time.time()
    async with EnvatoDownloader() as downloader_seq:
        results_seq = {}
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url}")
            link = await downloader_seq.get_download_url(url)
            results_seq[url] = link
    time_sequential = time.time() - start
    
    # Сравнение
    print("\n" + "="*70)
    print("🏆 ИТОГОВОЕ СРАВНЕНИЕ:")
    print("="*70)
    print(f"⏱️  Параллельное:      {time_parallel:.2f} сек")
    print(f"⏱️  Последовательное:  {time_sequential:.2f} сек")
    print(f"🚀 Ускорение:          {time_sequential/time_parallel:.1f}x")
    print("="*70)


if __name__ == "__main__":
    # Выберите нужный вариант:
    
    # asyncio.run(main_parallel())         # НОВОЕ: Параллельно с несколькими браузерами
    asyncio.run(main_sequential())     # СТАРОЕ: Последовательно
    # asyncio.run(compare_methods())     # Сравнение обоих методов