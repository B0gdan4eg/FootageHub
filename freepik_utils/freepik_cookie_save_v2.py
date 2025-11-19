#!/usr/bin/env python3
import json
from pathlib import Path
import browser_cookie3

OUT_PATH = Path(__file__).resolve().parent / "freepik_cookies.json"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Домен(ы) для фильтрации
DOMAINS = ["freepik.com", ".freepik.com", "www.freepik.com"]

def cookie_to_dict(c):
    # cookie — объект http.cookiejar.Cookie
    return {
        "name": c.name,
        "value": c.value,
        "domain": c.domain,
        "path": c.path,
        "expires": c.expires,        # может быть None
        "secure": bool(getattr(c, "secure", False)),
        "httpOnly": bool(c.__dict__.get("rest", {}).get("HttpOnly") or c.__dict__.get("httponly", False))
    }

def main(profile: str | None = None):
    """
    Если у вас нестандартный профиль Chrome (не Default), передайте его в profile,
    например: profile='Profile 1'. Иначе используем стандартный профиль.
    """
    print("="*70)
    print("🍪 Извлечение cookies Freepik из Chrome")
    print("="*70)

    try:
        # Попробуем получить куки из Chrome (browser_cookie3 сам подбирает путь)
        if profile:
            print(f"📂 Используем профиль Chrome: {profile}")
            cj = browser_cookie3.chrome(cookie_file=None, profile=profile)
        else:
            print(f"📂 Используем стандартный профиль Chrome")
            cj = browser_cookie3.chrome()
    except Exception as e:
        print(f"❌ Ошибка при чтении куки из Chrome: {e}")
        print("\n💡 ВОЗМОЖНЫЕ РЕШЕНИЯ:")
        print("   1. Убедитесь, что Chrome полностью закрыт")
        print("   2. Проверьте, что вы вошли в аккаунт Freepik в Chrome")
        print("   3. Попробуйте запустить от имени администратора")
        print("   4. Укажите конкретный профиль Chrome в коде")
        return

    freepik_cookies = []
    for c in cj:
        # Фильтрация по домену
        if any(d in c.domain for d in DOMAINS):
            freepik_cookies.append(cookie_to_dict(c))

    if not freepik_cookies:
        print("❌ Куки для Freepik не найдены.")
        print("\n💡 УБЕДИТЕСЬ:")
        print("   1. Вы вошли в аккаунт Freepik в Chrome")
        print("   2. Используете правильный профиль Chrome")
        print("   3. Chrome полностью закрыт перед запуском скрипта")
    else:
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(freepik_cookies, f, indent=4, ensure_ascii=False)

        print(f"\n✅ Сохранено {len(freepik_cookies)} cookies в {OUT_PATH}")

        # Показываем важные cookies
        important_names = ['_fprom_sess', 'gr_user_id', 'user_id', 'session', '_ga', 'OptanonConsent']
        important_cookies = [c for c in freepik_cookies if c.get('name') in important_names]

        if important_cookies:
            print(f"🔑 Важные cookies найдены:")
            for c in important_cookies:
                print(f"   - {c['name']}")

        print(f"\n📋 Полный список cookies:")
        for c in freepik_cookies:
            secure_flag = "🔒" if c.get('secure') else "🔓"
            print(f"   {secure_flag} {c['name']} (domain: {c['domain']})")

if __name__ == "__main__":
    # Если нужно указать конкретный профиль Chrome, измените None на строку, например "Profile 1"
    main(profile=None)
