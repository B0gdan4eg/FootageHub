"""
Утилита для конвертации cookies из формата браузерных расширений
(EditThisCookie, Cookie Editor) в формат Playwright.

Использование:
    python convert_cookies.py input_file.json output_file.json
"""

import json
import sys


def convert_extension_cookies_to_playwright(extension_cookies):
    """
    Конвертирует cookies из формата расширения в формат Playwright.

    Формат расширения (EditThisCookie):
    {
        "domain": ".example.com",
        "expirationDate": 1234567890,
        "hostOnly": false,
        "httpOnly": false,
        "name": "cookie_name",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": true,
        "session": false,
        "value": "cookie_value"
    }

    Формат Playwright:
    {
        "name": "cookie_name",
        "value": "cookie_value",
        "domain": ".example.com",
        "path": "/",
        "expires": 1234567890,
        "httpOnly": false,
        "secure": true,
        "sameSite": "None"
    }
    """
    playwright_cookies = []

    for cookie in extension_cookies:
        # Конвертируем sameSite
        same_site_map = {
            "no_restriction": "None",
            "lax": "Lax",
            "strict": "Strict",
            None: "None"
        }

        playwright_cookie = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie["domain"],
            "path": cookie["path"],
            "httpOnly": cookie.get("httpOnly", False),
            "secure": cookie.get("secure", False),
        }

        # Добавляем expires только если cookie не session
        if not cookie.get("session", False) and "expirationDate" in cookie:
            # expirationDate может быть float или int - конвертируем в int
            playwright_cookie["expires"] = int(cookie["expirationDate"])

        # Добавляем sameSite если есть
        same_site = cookie.get("sameSite")
        if same_site is not None:
            playwright_cookie["sameSite"] = same_site_map.get(same_site, "None")

        playwright_cookies.append(playwright_cookie)

    return playwright_cookies


def main():
    if len(sys.argv) < 2:
        print("Использование: python convert_cookies.py input_file.json [output_file.json]")
        print("\nЕсли output_file не указан, результат будет записан в input_file")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file

    # Читаем исходные cookies
    with open(input_file, "r", encoding="utf-8") as f:
        extension_cookies = json.load(f)

    # Конвертируем
    playwright_cookies = convert_extension_cookies_to_playwright(extension_cookies)

    # Сохраняем
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(playwright_cookies, f, indent=4, ensure_ascii=False)

    print(f"[OK] Конвертировано {len(playwright_cookies)} cookies")
    print(f"[SAVE] Сохранено в: {output_file}")


if __name__ == "__main__":
    main()