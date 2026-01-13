#!/usr/bin/env python3
"""
Универсальная утилита для конвертации cookies в формат Playwright.
Исправляет проблемы с sameSite, expires и другими полями.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def fix_cookies_file(
    cookie_file: Path,
    output_file: Optional[Path] = None,
    backup: bool = True,
    default_domain: str = ".example.com",
) -> Tuple[int, int]:
    """
    Исправляет формат cookies в файле для совместимости с Playwright.

    Args:
        cookie_file: Путь к файлу с cookies для исправления
        output_file: Путь для сохранения (если None, перезаписывается исходный файл)
        backup: Создавать ли бэкап исходного файла
        default_domain: Домен по умолчанию для cookies без домена

    Returns:
        Tuple[int, int]: (количество исправленных cookies, общее количество)

    Raises:
        FileNotFoundError: Если файл с cookies не найден
        json.JSONDecodeError: Если файл не является валидным JSON
    """
    if not cookie_file.exists():
        raise FileNotFoundError(f"Cookie file not found: {cookie_file}")

    # Если выходной файл не указан, используем исходный
    if output_file is None:
        output_file = cookie_file

    # Создать бэкап если требуется
    if backup and cookie_file == output_file:
        backup_file = cookie_file.with_suffix(
            f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        shutil.copy2(cookie_file, backup_file)
        print(f"✅ Создан бэкап: {backup_file.name}")

    # Загрузить cookies
    with open(cookie_file, "r", encoding="utf-8") as f:
        original_cookies = json.load(f)

    # Конвертировать cookies
    fixed_cookies = []
    for cookie in original_cookies:
        if not isinstance(cookie, dict):
            continue

        fixed_cookie = _fix_single_cookie(cookie, default_domain)
        fixed_cookies.append(fixed_cookie)

    # Сохранить исправленные cookies
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(fixed_cookies, f, indent=4, ensure_ascii=False)

    return len(fixed_cookies), len(original_cookies)


def _fix_single_cookie(cookie: Dict, default_domain: str) -> Dict:
    """
    Исправляет формат одного cookie.

    Args:
        cookie: Исходный cookie словарь
        default_domain: Домен по умолчанию

    Returns:
        Dict: Исправленный cookie
    """
    # Базовые обязательные поля
    fixed_cookie = {
        "name": cookie.get("name", ""),
        "value": cookie.get("value", ""),
        "domain": cookie.get("domain", default_domain),
        "path": cookie.get("path", "/"),
    }

    # Исправляем sameSite
    same_site = cookie.get("sameSite")
    if same_site is None:
        same_site = ""
    else:
        same_site = str(same_site).strip()

    # Нормализуем значение sameSite
    same_site_lower = same_site.lower()
    if same_site in ["Strict", "Lax", "None"]:
        fixed_cookie["sameSite"] = same_site
    elif same_site_lower == "strict":
        fixed_cookie["sameSite"] = "Strict"
    elif same_site_lower == "lax":
        fixed_cookie["sameSite"] = "Lax"
    elif same_site_lower in ["none", "no_restriction"]:
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

    return fixed_cookie


def print_cookie_stats(cookies: List[Dict], important_names: Optional[List[str]] = None):
    """
    Выводит статистику по cookies.

    Args:
        cookies: Список cookies
        important_names: Список важных имен cookies для проверки
    """
    print("\n📊 Статистика:")
    print(f"   Всего cookies: {len(cookies)}")

    # Статистика по sameSite
    same_site_stats = {}
    for cookie in cookies:
        ss = cookie.get("sameSite", "None")
        same_site_stats[ss] = same_site_stats.get(ss, 0) + 1

    for ss, count in same_site_stats.items():
        print(f"   sameSite={ss}: {count} cookies")

    # Проверка важных cookies
    if important_names:
        found_important = [c["name"] for c in cookies if c["name"] in important_names]
        if found_important:
            print("\n🔑 Важные cookies найдены:")
            for name in found_important:
                print(f"   ✅ {name}")
        else:
            print("\n⚠️  Важные cookies не найдены")
            print(f"   Ожидаемые: {', '.join(important_names)}")
