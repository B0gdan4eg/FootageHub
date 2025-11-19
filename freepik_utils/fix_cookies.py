#!/usr/bin/env python3
"""
Скрипт для конвертации cookies в формат Playwright
Исправляет проблемы с sameSite и другими полями
"""
import json
import os
from pathlib import Path

COOKIE_FILE = Path(__file__).resolve().parent / "freepik_cookies.json"
BACKUP_FILE = Path(__file__).resolve().parent / "freepik_cookies.backup.json"

def fix_cookies():
    print("="*70)
    print("🔧 Конвертация cookies в формат Playwright")
    print("="*70)

    if not COOKIE_FILE.exists():
        print(f"❌ Файл {COOKIE_FILE} не найден!")
        return

    # Создаем бэкап
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            original_cookies = json.load(f)

        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(original_cookies, f, indent=4, ensure_ascii=False)
        print(f"✅ Создан бэкап: {BACKUP_FILE.name}")
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return

    # Конвертируем cookies
    fixed_cookies = []
    for cookie in original_cookies:
        if not isinstance(cookie, dict):
            continue

        # Создаем новый cookie с правильными полями
        fixed_cookie = {
            "name": cookie.get("name", ""),
            "value": cookie.get("value", ""),
            "domain": cookie.get("domain", ".freepik.com"),
            "path": cookie.get("path", "/"),
        }

        # Исправляем sameSite
        same_site = cookie.get("sameSite", "").strip()
        if same_site in ["Strict", "Lax", "None"]:
            fixed_cookie["sameSite"] = same_site
        elif same_site.lower() == "strict":
            fixed_cookie["sameSite"] = "Strict"
        elif same_site.lower() == "lax":
            fixed_cookie["sameSite"] = "Lax"
        elif same_site.lower() == "none":
            fixed_cookie["sameSite"] = "None"
        else:
            # По умолчанию Lax если не указано
            fixed_cookie["sameSite"] = "Lax"

        # Добавляем expires (если есть)
        if "expires" in cookie or "expirationDate" in cookie:
            expires = cookie.get("expires") or cookie.get("expirationDate")
            if expires and expires != -1:
                # Playwright ожидает expires в секундах (Unix timestamp)
                fixed_cookie["expires"] = int(expires) if expires > 0 else -1

        # Добавляем httpOnly
        if "httpOnly" in cookie:
            fixed_cookie["httpOnly"] = bool(cookie["httpOnly"])

        # Добавляем secure
        if "secure" in cookie:
            fixed_cookie["secure"] = bool(cookie["secure"])

        fixed_cookies.append(fixed_cookie)

    # Сохраняем исправленные cookies
    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(fixed_cookies, f, indent=4, ensure_ascii=False)
        print(f"✅ Исправлено {len(fixed_cookies)} cookies")
        print(f"✅ Сохранено в {COOKIE_FILE.name}")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return

    # Показываем статистику
    print(f"\n📊 Статистика:")
    same_site_stats = {}
    for cookie in fixed_cookies:
        ss = cookie.get("sameSite", "None")
        same_site_stats[ss] = same_site_stats.get(ss, 0) + 1

    for ss, count in same_site_stats.items():
        print(f"   sameSite={ss}: {count} cookies")

    # Проверяем важные cookies
    important_names = ['_fprom_sess', 'gr_user_id', 'user_id', 'session']
    found_important = [c['name'] for c in fixed_cookies if c['name'] in important_names]

    if found_important:
        print(f"\n🔑 Важные cookies найдены:")
        for name in found_important:
            print(f"   ✅ {name}")
    else:
        print(f"\n⚠️  Важные cookies не найдены")

    print("\n" + "="*70)
    print("✅ Cookies готовы к использованию!")
    print("="*70)


if __name__ == "__main__":
    fix_cookies()