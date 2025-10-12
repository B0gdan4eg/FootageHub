from playwright.async_api import async_playwright
import json
import os
import asyncio

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "envato_cookies.json")

async def get_envato_direct_download_url(asset_url: str) -> str | None:
    if not os.path.exists(COOKIE_FILE):
        print(f"Файл {COOKIE_FILE} не найден. Пожалуйста, сохраните cookies перед использованием.")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Включаем headful для отладки
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        context = await browser.new_context(
            accept_downloads=True,
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            service_workers='block',
        )
        
        # НЕ блокируем ресурсы при отладке - это может ломать функционал
        # await context.route("**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}", lambda route: route.abort())
        
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print(f"Cookies загружены из {COOKIE_FILE}")

        page = await context.new_page()
        
        try:
            print(f"Переходим на {asset_url}...")
            await page.goto(asset_url, wait_until='networkidle', timeout=30000)
            
            # Ждём немного для загрузки динамического контента
            await asyncio.sleep(2)
            
            print("Ищем кнопку Download...")
            download_button = page.locator("button[data-testid='button-download']").first
            await download_button.wait_for(state='visible', timeout=15000)
            
            print("Кликаем на Download...")
            await download_button.click()
            
            # Ждём появления модального окна
            await asyncio.sleep(2)
            
            print("Ищем все кнопки в модальном окне...")
            # Попробуем найти все возможные варианты кнопки
            possible_selectors = [
                "button[data-testid='download-without-license-button']",
                "button:has-text('Download without')",
                "button:has-text('without license')",
                "button:has-text('Free download')",
                "a[data-testid='download-without-license-button']",
                "[data-testid='download-without-license-button']",
            ]
            
            license_button = None
            for selector in possible_selectors:
                try:
                    print(f"Пробуем селектор: {selector}")
                    btn = page.locator(selector).first
                    await btn.wait_for(state='visible', timeout=5000)
                    license_button = btn
                    print(f"✅ Найдена кнопка с селектором: {selector}")
                    break
                except:
                    continue
            
            if not license_button:
                # Выводим HTML модального окна для анализа
                print("\n📋 HTML модального окна:")
                modal_html = await page.locator("[role='dialog'], .modal, [class*='modal']").first.inner_html()
                print(modal_html[:1000])
                raise Exception("Не найдена кнопка скачивания без лицензии")
            
            print("Перехватываем скачивание...")
            async with page.expect_download(timeout=30000) as download_info:
                await license_button.click()
                print("Кнопка нажата, ждём скачивание...")

            download = await download_info.value
            print(f"✅ Прямая ссылка получена: {download.url}")
            return download.url

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            
            # Сохраняем скриншот для анализа
            screenshot_path = "error_screenshot.png"
            await page.screenshot(path=screenshot_path)
            print(f"📸 Скриншот сохранён: {screenshot_path}")
            
            return None
        finally:
            await browser.close()


# Тестирование
async def main():
    url = "YOUR_ENVATO_URL_HERE"  # Замените на реальный URL
    result = await get_envato_direct_download_url(url)
    if result:
        print(f"\n🎉 Успех! Ссылка: {result}")
    else:
        print("\n❌ Не удалось получить ссылку")

if __name__ == "__main__":
    asyncio.run(main())