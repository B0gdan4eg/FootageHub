#!/usr/bin/env python3
"""
Скрипт для конвертации Envato cookies в формат Playwright.
Использует универсальную утилиту из utils.cookie_fixer.
Читает из new_cookies.json и создаёт envato_cookies_N.json (где N - следующий номер).
"""
import glob
import json
import sys
from pathlib import Path

from utils.cookie_fixer import fix_cookies_file, print_cookie_stats

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_COOKIE_FILE = SCRIPT_DIR / "new_cookies.json"

# Важные cookies для Envato
IMPORTANT_COOKIES = ["envatoid", "elements.session.5", "_elements_session_4", "envato_client_id"]


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
        except Exception:
            continue

    return max(numbers) + 1 if numbers else 1


def main():
    print("=" * 70)
    print("🔧 Конвертация Envato cookies в формат Playwright")
    print("=" * 70)

    if not INPUT_COOKIE_FILE.exists():
        print(f"❌ Файл {INPUT_COOKIE_FILE.name} не найден!")
        print(f"💡 Создайте файл new_cookies.json с cookies из браузера")
        return

    # Определяем номер для нового файла
    next_num = get_next_cookie_number()
    output_file = SCRIPT_DIR / f"envato_cookies_{next_num}.json"

    print(f"📥 Входной файл: {INPUT_COOKIE_FILE.name}")
    print(f"📤 Выходной файл: {output_file.name}")

    try:
        # Исправляем cookies с использованием универсальной утилиты
        fixed_count, total_count = fix_cookies_file(
            cookie_file=INPUT_COOKIE_FILE,
            output_file=output_file,
            backup=True,
            default_domain=".elements.envato.com",
        )

        print(f"✅ Исправлено {fixed_count} из {total_count} cookies")
        print(f"✅ Сохранено в {output_file.name}")

        # Загружаем и показываем статистику
        with open(output_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        print_cookie_stats(cookies, IMPORTANT_COOKIES)

        print("\n" + "=" * 70)
        print(f"✅ Файл {output_file.name} готов к использованию!")
        print("=" * 70)
        print(f"\n💡 Совет: Обновите cookie_index.txt если используете ротацию")

    except FileNotFoundError as e:
        print(f"❌ Ошибка: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")


if __name__ == "__main__":
    main()
