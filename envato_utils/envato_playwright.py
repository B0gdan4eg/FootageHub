from playwright.async_api import async_playwright
import json
import os

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "envato_cookies.json")

async def get_envato_direct_download_url(asset_url: str) -> str | None:
    if not os.path.exists(COOKIE_FILE):
        print(f"Файл {COOKIE_FILE} не найден. Пожалуйста, сохраните cookies перед использованием.")
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)

        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print(f"Cookies загружены из {COOKIE_FILE}")

        page = await context.new_page()
        await page.goto(asset_url)

        try:
            print("Ожидаем кнопку загрузки...")
            await page.wait_for_selector("button[data-testid='button-download']", timeout=15000)
            await page.click("button[data-testid='button-download']")

            print("Ожидаем кнопку 'Скачать без лицензии'...")
            await page.wait_for_selector("button[data-testid='download-without-license-button']", timeout=15000)

            async with page.expect_download() as download_info:
                await page.click("button[data-testid='download-without-license-button']")

            download = await download_info.value
            print("✅ Прямая ссылка получена:", download.url)
            return download.url

        except Exception as e:
            print("❌ Ошибка при получении ссылки:", e)
            return None
        finally:
            await browser.close()