from playwright.async_api import async_playwright
import json

COOKIE_FILE = "freepik_cookies.json"
# Используем главную страницу вместо прямого логина
START_URL = "https://www.freepik.com"

async def save_cookies_after_login():
    async with async_playwright() as p:
        # Добавляем user-agent чтобы выглядеть как обычный браузер
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled'
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU'
        )

        # Скрываем признаки автоматизации
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()

        print("="*70)
        print(f"🌐 Открываем Freepik: {START_URL}")
        print("="*70)
        await page.goto(START_URL, wait_until="networkidle")

        print("\n📝 ИНСТРУКЦИЯ:")
        print("1. Нажмите кнопку 'Log in' в правом верхнем углу")
        print("2. Войдите в свой аккаунт Freepik (email/пароль или через Google)")
        print("3. Дождитесь полной загрузки главной страницы после входа")
        print("4. Убедитесь, что видите свой профиль (иконку) вместо кнопки 'Log in'")
        print("5. Нажмите Enter в этом окне консоли для сохранения cookies")
        print("="*70)
        print("\n💡 СОВЕТ: Если кнопка Log in не работает, попробуйте:")
        print("   - Обновить страницу (F5)")
        print("   - Вручную перейти на https://www.freepik.com/login")
        print("   - Войти через Google/Facebook если есть аккаунт")
        print("="*70)

        # Ждем подтверждения от пользователя
        input("\n⏸️  Нажмите Enter после успешного входа в аккаунт...")

        # Получаем все куки из текущего контекста
        cookies = await context.cookies()

        # Сохраняем куки в файл
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=4, ensure_ascii=False)

        print(f"\n✅ Cookies сохранены в {COOKIE_FILE}")
        print(f"📊 Всего cookies: {len(cookies)}")

        # Показываем основные cookies для проверки
        important_cookies = [c for c in cookies if c.get('name') in ['_fprom_sess', 'gr_user_id', 'user_id', 'session']]
        if important_cookies:
            print(f"🔑 Важные cookies найдены: {[c['name'] for c in important_cookies]}")
        else:
            print("⚠️  ВНИМАНИЕ: Не найдены стандартные cookies авторизации!")
            print("   Убедитесь, что вы действительно вошли в аккаунт")

        await browser.close()


import asyncio
asyncio.run(save_cookies_after_login())
