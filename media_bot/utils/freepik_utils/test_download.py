"""
Тестовый скрипт для проверки загрузки с Freepik.

Запуск из корня проекта:
    python -m media_bot.utils.freepik_utils.test_download
    python -m media_bot.utils.freepik_utils.test_download <url1> <url2> ...
"""

import asyncio
import os
import sys
import time
import warnings

from media_bot.utils.freepik_utils.freepik import FreepikDownloader, get_next_cookie_file

# Подавляем мусорные предупреждения от nodriver при закрытии браузера на Windows
warnings.filterwarnings("ignore", category=ResourceWarning)

# Добавляем корень проекта в PYTHONPATH если запускаем напрямую
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    sys.path.insert(0, project_root)


# URL для теста по умолчанию (бесплатный ресурс)в
DEFAULT_TEST_URLS = [
    "https://www.freepik.com/free-photo/young-student-learning-library_21138972.htm",
]


def check_cookie_files():
    """Проверяет наличие и состояние файлов с куками"""
    print("\n" + "=" * 60)
    print("1. ПРОВЕРКА ФАЙЛОВ КУКОВ")
    print("=" * 60)

    cookie_dir = os.path.dirname(__file__)
    cookie_files = []

    for filename in sorted(os.listdir(cookie_dir)):
        if filename.startswith("freepik_cookies") and filename.endswith(".json"):
            path = os.path.join(cookie_dir, filename)
            size = os.path.getsize(path)
            cookie_files.append((filename, path, size))

    if not cookie_files:
        print("❌ Файлы с куками не найдены!")
        print(f"   Директория: {cookie_dir}")
        print("   Ожидаются файлы: freepik_cookies.json или freepik_cookies_N.json")
        return False

    print(f"✅ Найдено файлов с куками: {len(cookie_files)}")
    for filename, path, size in cookie_files:
        print(f"   - {filename} ({size} байт)")

    # Читаем текущий индекс
    index_file = os.path.join(cookie_dir, "freepik_cookie_index.txt")
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            current_index = f.read().strip()
        print(f"\n   Текущий индекс ротации: {current_index}")
    else:
        print("\n   Индекс ротации: файл не найден (будет использован индекс 0)")

    try:
        next_file = get_next_cookie_file()
        print(f"\n✅ Следующий файл для использования: {os.path.basename(next_file)}")
    except FileNotFoundError as e:
        print(f"\n❌ Ошибка ротации куков: {e}")
        return False

    return True


async def test_single_url(downloader: FreepikDownloader, url: str, idx: int) -> bool:
    """Тестирует загрузку одного URL"""
    print(f"\n  [{idx}] URL: {url[:70]}...")
    start = time.time()

    result = await downloader.get_download_url(url)
    elapsed = time.time() - start

    if result:
        print(f"  [{idx}] ✅ Ссылка получена за {elapsed:.2f} сек")
        print(f"  [{idx}] 🔗 {result[:100]}...")
        return True
    else:
        print(f"  [{idx}] ❌ Не удалось получить ссылку ({elapsed:.2f} сек)")
        return False


async def run_tests(urls: list[str]):
    """Основная тестовая функция"""
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАГРУЗКИ FREEPIK")
    print("=" * 60)

    # 1. Проверка куков
    if not check_cookie_files():
        print("\n❌ Тест прерван: нет файлов с куками")
        return

    # 2. Тест загрузки URL
    print("\n" + "=" * 60)
    print(f"2. ТЕСТ ЗАГРУЗКИ ({len(urls)} URL)")
    print("=" * 60)

    success = 0
    fail = 0
    total_start = time.time()

    async with FreepikDownloader() as downloader:
        for idx, url in enumerate(urls, 1):
            ok = await test_single_url(downloader, url, idx)
            if ok:
                success += 1
            else:
                fail += 1

    total_elapsed = time.time() - total_start

    # 3. Итог
    print("\n" + "=" * 60)
    print("ИТОГ")
    print("=" * 60)
    print(f"  Успешно:  {success}/{len(urls)}")
    print(f"  Ошибки:   {fail}/{len(urls)}")
    print(f"  Время:    {total_elapsed:.2f} сек")
    if success > 0:
        print(f"  Среднее:  {total_elapsed / len(urls):.2f} сек/URL")

    if success == len(urls):
        print("\n✅ Все тесты прошли успешно!")
    elif success > 0:
        print(f"\n⚠️  Частичный успех: {success} из {len(urls)}")
    else:
        print("\n❌ Все тесты провалились. Проверьте куки и доступ к Freepik.")


def main():
    urls = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TEST_URLS

    if not urls:
        print(
            "Использвание: python -m media_bot.utils.freepik_utils.test_download [url1] [url2] ..."
        )
        print(f"По умолчанию используется: {DEFAULT_TEST_URLS[0]}")
        urls = DEFAULT_TEST_URLS

    asyncio.run(run_tests(urls))


if __name__ == "__main__":
    main()
