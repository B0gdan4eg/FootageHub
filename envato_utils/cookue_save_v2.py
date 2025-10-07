#!/usr/bin/env python3
import json
from pathlib import Path
import browser_cookie3

OUT_PATH = Path(__file__).resolve().parent / "envato_cookies.json"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Домен(ы) для фильтрации
DOMAINS = ["elements.envato.com", ".envato.com", "envato.com"]

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
    try:
        # Попробуем получить куки из Chrome (browser_cookie3 сам подбирает путь)
        if profile:
            cj = browser_cookie3.chrome(cookie_file=None, profile=profile)
        else:
            cj = browser_cookie3.chrome()
    except Exception as e:
        print("Ошибка при чтении куки из Chrome:", e)
        return

    envato_cookies = []
    for c in cj:
        # Фильтрация по домену
        if any(d in c.domain for d in DOMAINS):
            envato_cookies.append(cookie_to_dict(c))

    if not envato_cookies:
        print("Куки для Envato не найдены. Убедитесь, что вы вошли в Chrome в тот же профиль.")
    else:
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(envato_cookies, f, indent=4, ensure_ascii=False)
        print(f"✅ Сохранено {len(envato_cookies)} куки в {OUT_PATH}")

if __name__ == "__main__":
    # Если нужно указать конкретный профиль Chrome, измените None на строку, например "Profile 1"
    main(profile=None)
