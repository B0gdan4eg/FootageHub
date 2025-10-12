from playwright.async_api import async_playwright
import json
import os

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "envato_cookies.json")

async def get_envato_direct_download_url(asset_url: str) -> str | None:
    if not os.path.exists(COOKIE_FILE):
        print(f"Файл {COOKIE_FILE} не найден. Пожалуйста, сохраните cookies перед использованием.")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        
        context = await browser.new_context(
            accept_downloads=True,
            # Отключаем ненужное для ускорения
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            # Блокируем тяжелые ресурсы
            service_workers='block',
        )
        
        # Блокируем ненужные ресурсы
        await context.route("**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}", lambda route: route.abort())
        

        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print(f"Cookies загружены из {COOKIE_FILE}")

        page = await context.new_page()
        # Устанавливаем таймаут загрузки страницы
        await page.goto(asset_url, wait_until='domcontentloaded', timeout=10000)

        try:
            print("Ожидаем кнопку загрузки...")
            
            # Параллельно ждем обе кнопки сразу
            download_button = page.locator("button[data-testid='button-download']").first
            await download_button.wait_for(state='visible', timeout=10000)
            await download_button.click()

            print("Ожидаем кнопку 'Скачать без лицензии'...")
            license_button = page.locator("button[data-testid='download-without-license-button']")
            
            # Перехватываем запрос на скачивание ДО клика
            async with page.expect_download(timeout=10000) as download_info:
                await license_button.wait_for(state='visible', timeout=10000)
                await license_button.click()

            download = await download_info.value
            print("✅ Прямая ссылка получена:", download.url)
            return download.url

        except Exception as e:
            print("❌ Ошибка при получении ссылки:", e)
            return None
        finally:
            await browser.close()