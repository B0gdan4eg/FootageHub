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
            # 1️⃣ Ждём появления кнопки Download, но не тормозим весь поток
            print("⚡ Ждём кнопку Download...")
            await page.wait_for_selector("button[data-testid='button-download']", timeout=10000)
            await page.click("button[data-testid='button-download']")
            print("✅ Нажали Download")

            # 2️⃣ Параллельно ждём кнопку "Без лицензии" и кликаем сразу при появлении
            print("⚡ Ждём 'Скачать без лицензии'...")

            async def wait_for_download_button():
                for _ in range(12):  # максимум 12×0.5 = 6 сек ожидания
                    btn = await page.query_selector("button[data-testid='download-without-license-button']")
                    if btn:
                        return btn
                    await asyncio.sleep(0.5)
                return None

            btn = await wait_for_download_button()
            if not btn:
                raise TimeoutError("Кнопка 'Скачать без лицензии' не появилась.")

            async with page.expect_download() as download_info:
                await btn.click()
                print("📦 Клик по 'Без лицензии' выполнен...")

            download = await download_info.value
            print("✅ Прямая ссылка:", download.url)
            return download.url

        except Exception as e:
            print("❌ Ошибка при получении ссылки:", e)
            return None
        finally:
            await browser.close()