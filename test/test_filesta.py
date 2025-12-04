"""
Тестовый скрипт для проверки работы Filesta downloader
"""

import asyncio
from filesta_playwright import get_filesta_download_url


async def test_filesta():
    # Тестовая ссылка на Envato Elements (замените на реальную)
    test_url = "https://elements.envato.com/ru/clean-sticker-for-text-and-a-brush-on-the-backgrou-4KF38R2"

    print("=" * 70)
    print("🧪 ТЕСТ FILESTA DOWNLOADER")
    print("=" * 70)
    print(f"\nТестовая ссылка: {test_url}")
    print("\n⚠️  ВАЖНО: Замените test_url на реальную ссылку Envato Elements\n")

    # Получаем прямую ссылку
    download_url = await get_filesta_download_url(test_url)

    if download_url:
        print("\n" + "=" * 70)
        print("✅ УСПЕХ!")
        print("=" * 70)
        print(f"\n📥 Прямая ссылка на скачивание:")
        print(f"{download_url}\n")
    else:
        print("\n" + "=" * 70)
        print("❌ ОШИБКА!")
        print("=" * 70)
        print("\nВозможные причины:")
        print("1. Неверная ссылка на Envato Elements")
        print("2. Проблемы с cookies (требуется логин)")
        print("3. Изменилась структура сайта Filesta.com")
        print("4. Проблемы с сетью\n")


if __name__ == "__main__":
    asyncio.run(test_filesta())
