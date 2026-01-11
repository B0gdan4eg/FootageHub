#!/usr/bin/env python3
"""
Скрипт для проверки cookies Freepik
"""
import json
import os
from pathlib import Path

COOKIE_FILE = Path(__file__).resolve().parent / "freepik_cookies.json"


def check_cookies():
    print("=" * 70)
    print("🍪 Проверка cookies Freepik")
    print("=" * 70)

    if not COOKIE_FILE.exists():
        print(f"❌ Файл {COOKIE_FILE} не найден!")
        print("\n💡 Создайте файл freepik_cookies.json и добавьте туда cookies")
        return

    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        print("\n💡 Проверьте, что файл содержит валидный JSON")
        return

    if not isinstance(cookies, list):
        print(f"❌ Cookies должны быть массивом (list), а не {type(cookies).__name__}")
        return

    if not cookies:
        print("❌ Файл cookies пустой!")
        return

    print(f"\n✅ Загружено {len(cookies)} cookies\n")

    # Проверяем структуру
    required_fields = ["name", "value", "domain"]
    valid_cookies = []
    invalid_cookies = []

    for i, cookie in enumerate(cookies):
        if not isinstance(cookie, dict):
            invalid_cookies.append(f"Cookie #{i+1}: не является объектом")
            continue

        missing_fields = [f for f in required_fields if f not in cookie]
        if missing_fields:
            invalid_cookies.append(
                f"Cookie #{i+1} ({cookie.get('name', '?')}): отсутствуют поля {missing_fields}"
            )
        else:
            valid_cookies.append(cookie)

    # Результаты
    print(f"📊 Статистика:")
    print(f"   ✅ Валидных cookies: {len(valid_cookies)}")
    print(f"   ❌ Невалидных cookies: {len(invalid_cookies)}")

    if invalid_cookies:
        print(f"\n⚠️  Проблемные cookies:")
        for issue in invalid_cookies:
            print(f"   - {issue}")

    # Важные cookies для Freepik
    important_names = [
        "_fprom_sess",  # Сессия Freepik
        "gr_user_id",  # ID пользователя
        "user_id",  # ID пользователя
        "session",  # Сессия
        "_ga",  # Google Analytics
        "OptanonConsent",  # Согласие на cookies
        "freepik_login",  # Логин
        "auth_token",  # Токен авторизации
    ]

    found_important = []
    for cookie in valid_cookies:
        name = cookie.get("name", "")
        if name in important_names or "session" in name.lower() or "auth" in name.lower():
            found_important.append(name)

    print(f"\n🔑 Важные cookies найдены:")
    if found_important:
        for name in found_important:
            print(f"   ✅ {name}")
    else:
        print(f"   ⚠️  Не найдены стандартные cookies авторизации")
        print(f"   💡 Убедитесь, что вы вошли в аккаунт Freepik перед экспортом")

    # Домены
    domains = set(c.get("domain", "?") for c in valid_cookies)
    print(f"\n🌐 Домены cookies:")
    for domain in sorted(domains):
        count = sum(1 for c in valid_cookies if c.get("domain") == domain)
        print(f"   {domain}: {count} cookies")

    # Проверка на freepik.com
    freepik_cookies = [c for c in valid_cookies if "freepik.com" in c.get("domain", "")]
    print(f"\n📌 Cookies для freepik.com: {len(freepik_cookies)}")

    if len(freepik_cookies) < 3:
        print(f"   ⚠️  Слишком мало cookies для Freepik!")
        print(f"   💡 Убедитесь, что вы экспортировали cookies именно с freepik.com")

    print("\n" + "=" * 70)
    if len(valid_cookies) >= 5 and len(freepik_cookies) >= 3:
        print("✅ Cookies выглядят корректно и готовы к использованию!")
    else:
        print("⚠️  Возможно, cookies неполные. Попробуйте экспортировать заново.")
    print("=" * 70)


if __name__ == "__main__":
    check_cookies()
