"""
Эксперимент: Freepik с ПЕРСИСТЕНТНЫМ профилем (подход из Trade/ADR-002).

Персистентный профиль уже встроен в FreepikDownloader.__aenter__ (uc.start с
user_data_dir=.profile/). Этот скрипт прогоняет РЕАЛЬНЫЙ путь скачивания два
раза подряд, чтобы увидеть эффект «холодный профиль → тёплый»:
  - 1-й проход: профиль может быть холодным (возможен Cloudflare/Akamai-челлендж);
  - 2-й проход: cf_clearance/_abck уже осели → должно быть быстрее/стабильнее.

Чтобы проверить переживание профиля между ПЕРЕЗАПУСКАМИ процесса — запусти
скрипт дважды: на втором запуске поле "Профиль уже существует" будет True.

Запуск из корня проекта:
    python -m media_bot.utils.freepik_utils.test_persistent
    python -m media_bot.utils.freepik_utils.test_persistent <url1> <url2> ...
"""

import asyncio
import os
import sys
import time
import warnings

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    sys.path.insert(0, project_root)

from media_bot.utils.freepik_utils.freepik import (
    PROFILE_DIR,
    FreepikDownloader,
    get_next_cookie_file,
)

# nodriver на Windows сыпет ResourceWarning при закрытии — глушим
warnings.filterwarnings("ignore", category=ResourceWarning)

DEFAULT_TEST_URLS = [
    "https://www.freepik.com/free-photo/young-student-learning-library_21138972.htm",
]


async def _run_pass(downloader: FreepikDownloader, urls: list[str], pass_no: int):
    print("\n" + "-" * 60)
    print(f"ПРОХОД #{pass_no} ({'холодный профиль' if pass_no == 1 else 'тёплый профиль'})")
    print("-" * 60)
    results = []
    for idx, url in enumerate(urls, 1):
        print(f"\n  [{idx}] {url[:70]}")
        start = time.time()
        link = await downloader.get_download_url(url)
        elapsed = time.time() - start
        if link:
            print(f"  [{idx}] ✅ {elapsed:.2f}с — {link[:90]}")
        else:
            print(f"  [{idx}] ❌ нет ссылки ({elapsed:.2f}с)")
        results.append((bool(link), elapsed))
    return results


async def run(urls: list[str]):
    print("=" * 64)
    print("ЭКСПЕРИМЕНТ: Freepik persistent profile")
    print(f"Профиль: {PROFILE_DIR}")
    print(f"Профиль уже существует (тёплый между запусками): {os.path.isdir(PROFILE_DIR)}")
    print("=" * 64)

    try:
        cf = get_next_cookie_file()
        print(f"Cookie-файл для seed: {os.path.basename(cf)}")
    except FileNotFoundError as e:
        print(f"❌ Нет файлов с куками: {e}")
        return

    async with FreepikDownloader() as downloader:
        pass1 = await _run_pass(downloader, urls, 1)
        await asyncio.sleep(1)
        pass2 = await _run_pass(downloader, urls, 2)

    print("\n" + "=" * 64)
    print("ИТОГ (сравнение холодный vs тёплый)")
    print("=" * 64)
    for i, (url, r1, r2) in enumerate(zip(urls, pass1, pass2), 1):
        ok1, t1 = r1
        ok2, t2 = r2
        print(
            f"  [{i}] проход1: {'OK' if ok1 else 'FAIL'} {t1:.2f}с  →  "
            f"проход2: {'OK' if ok2 else 'FAIL'} {t2:.2f}с"
        )
    s1 = sum(1 for ok, _ in pass1 if ok)
    s2 = sum(1 for ok, _ in pass2 if ok)
    print(f"\n  Успешно: проход1 {s1}/{len(urls)}, проход2 {s2}/{len(urls)}")
    print("  (профиль сохранён — запусти скрипт ещё раз, чтобы проверить тёплый старт)")


def main():
    urls = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TEST_URLS
    asyncio.run(run(urls))


if __name__ == "__main__":
    main()
