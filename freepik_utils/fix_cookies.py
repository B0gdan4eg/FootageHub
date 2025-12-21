#!/usr/bin/env python3
"""
Скрипт для конвертации Freepik cookies в формат Playwright.
Использует универсальную утилиту из utils.cookie_fixer.
"""
from pathlib import Path
import json
import sys

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.cookie_fixer import fix_cookies_file, print_cookie_stats

COOKIE_FILE = Path(__file__).resolve().parent / "freepik_cookies.json"

# Важные cookies для Freepik
IMPORTANT_COOKIES = ['_fprom_sess', 'gr_user_id', 'user_id', 'session']


def main():
    print("=" * 70)
    print("🔧 Конвертация Freepik cookies в формат Playwright")
    print("=" * 70)

    if not COOKIE_FILE.exists():
        print(f"❌ Файл {COOKIE_FILE.name} не найден!")
        print(f"💡 Создайте файл freepik_cookies.json с cookies из браузера")
        return

    try:
        # Исправляем cookies
        fixed_count, total_count = fix_cookies_file(
            cookie_file=COOKIE_FILE,
            backup=True,
            default_domain=".freepik.com"
        )

        print(f"✅ Исправлено {fixed_count} из {total_count} cookies")
        print(f"✅ Сохранено в {COOKIE_FILE.name}")

        # Загружаем и показываем статистику
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        print_cookie_stats(cookies, IMPORTANT_COOKIES)

        print("\n" + "=" * 70)
        print("✅ Cookies готовы к использованию!")
        print("=" * 70)

    except FileNotFoundError as e:
        print(f"❌ Ошибка: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")


if __name__ == "__main__":
    main()