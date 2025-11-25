#!/usr/bin/env python3
"""
Скрипт для конвертации cookies в формат Playwright
Читает из new_cookies.json и создаёт envato_cookies_N.json (где N - следующий номер)
Исправляет проблемы с sameSite и другими полями
"""
import json
import os
from pathlib import Path
import glob

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_COOKIE_FILE = SCRIPT_DIR / "new_cookies.json"

def get_next_cookie_number():
    """Находит следующий доступный номер для envato_cookies_N.json"""
    existing_files = glob.glob(str(SCRIPT_DIR / "envato_cookies_*.json"))

    if not existing_files:
        return 1

    numbers = []
    for file_path in existing_files:
        filename = Path(file_path).name
        # Извлекаем число из имени файла (envato_cookies_1.json -> 1)
        try:
            num_str = filename.replace("envato_cookies_", "").replace(".json", "")
            if num_str.isdigit():
                numbers.append(int(num_str))
        except:
            continue

    return max(numbers) + 1 if numbers else 1

def fix_cookies():
    print("="*70)
    print("🔧 Конвертация cookies в формат Playwright")
    print("="*70)

    if not INPUT_COOKIE_FILE.exists():
        print(f"❌ Файл {INPUT_COOKIE_FILE.name} не найден!")
        print(f"💡 Создайте файл new_cookies.json с cookies из браузера")
        return

    # Определяем номер для нового файла
    next_num = get_next_cookie_number()
    OUTPUT_COOKIE_FILE = SCRIPT_DIR / f"envato_cookies_{next_num}.json"
    BACKUP_FILE = SCRIPT_DIR / "new_cookies.backup.json"

    print(f"📥 Входной файл: {INPUT_COOKIE_FILE.name}")
    print(f"📤 Выходной файл: {OUTPUT_COOKIE_FILE.name}")

    # Создаем бэкап
    try:
        with open(INPUT_COOKIE_FILE, "r", encoding="utf-8") as f:
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
            "domain": cookie.get("domain", ".elements.envato.com"),
            "path": cookie.get("path", "/"),
        }

        # Исправляем sameSite
        same_site = cookie.get("sameSite")
        if same_site is None:
            same_site = ""
        else:
            same_site = str(same_site).strip()

        if same_site in ["Strict", "Lax", "None"]:
            fixed_cookie["sameSite"] = same_site
        elif same_site.lower() == "strict":
            fixed_cookie["sameSite"] = "Strict"
        elif same_site.lower() == "lax":
            fixed_cookie["sameSite"] = "Lax"
        elif same_site.lower() == "none" or same_site.lower() == "no_restriction":
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

    # Сохраняем исправленные cookies в новый файл
    try:
        with open(OUTPUT_COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(fixed_cookies, f, indent=4, ensure_ascii=False)
        print(f"✅ Исправлено {len(fixed_cookies)} cookies")
        print(f"✅ Сохранено в {OUTPUT_COOKIE_FILE.name}")
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

    # Проверяем важные cookies для Envato
    important_names = ['envatoid', 'elements.session.5', '_elements_session_4', 'envato_client_id']
    found_important = [c['name'] for c in fixed_cookies if c['name'] in important_names]

    if found_important:
        print(f"\n🔑 Важные cookies найдены:")
        for name in found_important:
            print(f"   ✅ {name}")
    else:
        print(f"\n⚠️  Важные cookies для Envato не найдены")
        print(f"   Ожидаемые: {', '.join(important_names)}")

    print("\n" + "="*70)
    print(f"✅ Файл {OUTPUT_COOKIE_FILE.name} готов к использованию!")
    print("="*70)
    print(f"\n💡 Совет: Обновите cookie_index.txt если используете ротацию")


if __name__ == "__main__":
    fix_cookies()