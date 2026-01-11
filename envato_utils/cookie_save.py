#!/usr/bin/env python3
"""
Universal cookie saver for all download services (Envato, Freepik, Motion Array).

Usage:
    python cookie_save.py envato [number]
    python cookie_save.py freepik [number]
    python cookie_save.py motion [number]

Examples:
    python cookie_save.py envato          # Save to envato_utils/envato_cookies.json
    python cookie_save.py envato 1        # Save to envato_utils/envato_cookies_1.json
    python cookie_save.py freepik 2       # Save to freepik_utils/freepik_cookies_2.json
    python cookie_save.py motion 1        # Save to motion_utils/motion_cookies_1.json
"""

import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

SERVICES = {
    "envato": {
        "login_url": "https://elements.envato.com/ru/sign-in",
        "success_url": "https://elements.envato.com",
        "alt_success_url": "https://app.envato.com",
        "output_dir": "envato_utils",
        "cookie_prefix": "envato_cookies",
    },
    "freepik": {
        "login_url": "https://www.freepik.com/log-in?client_id=freepik&lang=en",
        "success_url": "https://www.freepik.com",
        "alt_success_url": None,
        "output_dir": "freepik_utils",
        "cookie_prefix": "freepik_cookies",
    },
    "motion": {
        "login_url": "https://motionarray.com/account/login/",
        "success_url": "https://motionarray.com",
        "alt_success_url": "https://motionarray.com/browse",
        "output_dir": "motion_utils",
        "cookie_prefix": "motion_cookies",
    },
}


async def save_cookies_after_login(service: str, number: int = None):
    """
    Save cookies after manual login for specified service.

    Args:
        service: Service name (envato, freepik, motion)
        number: Optional number for cookie rotation (e.g., 1, 2, 3)
    """
    if service not in SERVICES:
        print(f"[ERROR] Unknown service: {service}")
        print(f"Available services: {', '.join(SERVICES.keys())}")
        sys.exit(1)

    config = SERVICES[service]

    # Determine output file path
    if number:
        cookie_file = f"{config['cookie_prefix']}_{number}.json"
    else:
        cookie_file = f"{config['cookie_prefix']}.json"

    # Prepare output paths: service directory + test directory
    service_output_path = os.path.join(config["output_dir"], cookie_file)
    test_output_path = os.path.join("test", cookie_file)

    # Create output directories if they don't exist
    Path(config["output_dir"]).mkdir(parents=True, exist_ok=True)
    Path("test").mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        print(f"\n{'='*70}")
        print(f"[*] Cookie Saver for {service.upper()}")
        print(f"{'='*70}")
        print(f"\n1. Откроется браузер со страницей: {config['login_url']}")
        print(f"2. Войдите в аккаунт вручную")
        print(f"3. Дождитесь полной загрузки главной страницы")
        print(f"4. Cookies будут автоматически сохранены в:")
        print(f"   - {service_output_path}")
        print(f"   - {test_output_path}")
        print(f"\n[*] Ожидание входа (макс. 5 минут)...\n")

        await page.goto(config["login_url"])

        # Wait for successful login (check main page URL)
        success_urls = [config["success_url"]]
        if config["alt_success_url"]:
            success_urls.append(config["alt_success_url"])

        try:
            # Wait for any of the success URLs
            await page.wait_for_url(f"**{config['success_url']}**", timeout=300000)
        except Exception:
            # Try alternative success URL if available
            if config["alt_success_url"]:
                try:
                    await page.wait_for_url(f"**{config['alt_success_url']}**", timeout=5000)
                except Exception:
                    pass

        # Give time for all cookies to be set
        print("[+] Вход выполнен! Ожидание загрузки cookies...")
        import asyncio

        await asyncio.sleep(3)

        # Get all cookies from current context
        cookies = await context.cookies()

        # Save cookies to both locations
        with open(service_output_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        with open(test_output_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*70}")
        print(f"[SUCCESS] Cookies успешно сохранены!")
        print(f"[FILES]:")
        print(f"   - {service_output_path}")
        print(f"   - {test_output_path}")
        print(f"[INFO] Количество cookies: {len(cookies)}")
        print(f"{'='*70}\n")

        await browser.close()


def print_usage():
    print(__doc__)
    print("\nДоступные сервисы:")
    for service, config in SERVICES.items():
        print(f"  • {service:8} - {config['login_url']}")
    print("\nПримеры использования:")
    print("  python cookie_save.py envato")
    print("  python cookie_save.py freepik 1")
    print("  python cookie_save.py motion 2")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Не указан сервис!")
        print_usage()
        sys.exit(1)

    service = sys.argv[1].lower()

    if service in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)

    # Parse optional number argument
    number = None
    if len(sys.argv) >= 3:
        try:
            number = int(sys.argv[2])
        except ValueError:
            print(f"[ERROR] Неверный номер: {sys.argv[2]}")
            print("Номер должен быть целым числом (например: 1, 2, 3)")
            sys.exit(1)

    import asyncio

    asyncio.run(save_cookies_after_login(service, number))
