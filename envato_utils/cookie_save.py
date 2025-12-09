from playwright.async_api import async_playwright
import json

# COOKIE_FILE = "freepik_cookies.json"
# LOGIN_URL = "https://www.freepik.com/log-in"
# https://www.freepik.com/?log-in=email
COOKIE_FILE = "envato_cookies.json"
LOGIN_URL = "https://elements.envato.com/ru/sign-in"


async def save_cookies_after_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False чтобы видеть браузер и логиниться
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Откройте страницу и залогиньтесь: {LOGIN_URL}")
        await page.goto(LOGIN_URL)

        # Ждем, пока пользователь вручную залогинится и попадет на главную
        # Можно подождать пока URL поменяется, например на https://envato.com или другую страницу после логина
        await page.wait_for_url("https://www.freepik.com/?log-in=email", timeout=300000)  # ждем до 5 минут

        # Получаем все куки из текущего контекста
        cookies = await context.cookies()
        # Сохраняем куки в файл
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f, indent=4)

        print(f"Cookies сохранены в {COOKIE_FILE}")
        await browser.close()


import asyncio
asyncio.run(save_cookies_after_login())
