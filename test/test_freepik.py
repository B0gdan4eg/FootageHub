import asyncio
import json
import os
import time
from playwright.async_api import async_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "freepik_cookies.json")


class FreepikDownloader:
    """
    Advanced Freepik downloader using CDP (Chrome DevTools Protocol).
    Supports both single and batch processing with URL interception.
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.total_time = 0
        self.success_count = 0
        self.fail_count = 0

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()

        if not os.path.exists(COOKIE_FILE):
            raise FileNotFoundError(f"Cookies file not found: {COOKIE_FILE}")

        with open(COOKIE_FILE, "r") as f:
            await self.context.add_cookies(json.load(f))

        return self

    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        total = self.success_count + self.fail_count
        if total > 0:
            avg_time = self.total_time / total
            print("\n" + "="*70)
            print("📊 СТАТИСТИКА:")
            print(f"   ✅ Успешно: {self.success_count}")
            print(f"   ❌ Провалов: {self.fail_count}")
            print(f"   ⏱️  Общее время: {self.total_time:.2f} сек")
            print(f"   ⏱️  Среднее время: {avg_time:.2f} сек/ссылка")
            print("="*70)

    async def get_download_url(self, asset_url: str) -> str | None:
        """
        Get direct download URL using CDP network interception.
        Faster and more reliable than waiting for downloads.

        Args:
            asset_url: URL of the Freepik asset page

        Returns:
            Direct download URL or None if failed
        """
        page = None
        client = None
        start_time = time.time()
        download_url = None

        try:
            page = await self.context.new_page()

            # Enable CDP session for network monitoring
            client = await self.context.new_cdp_session(page)
            await client.send("Network.enable")

            captured_responses = []
            all_responses = []  # Для отладки
            download_initiated = []  # Перехват начала скачивания

            # Также пробуем перехватить через событие download
            download_info = {}

            async def handle_download(download):
                try:
                    download_url = download.url
                    print(f"📥 [DOWNLOAD EVENT] Обнаружено скачивание: {download_url}")
                    download_info['url'] = download_url
                    # Отменяем скачивание, нам нужна только ссылка
                    await download.cancel()
                except Exception as e:
                    print(f"⚠️ Ошибка в handle_download: {e}")

            page.on("download", handle_download)

            def on_response(event):
                response = event.get("response", {})
                url = response.get("url", "")
                status = response.get("status", 0)
                headers = response.get("headers", {})
                mime_type = response.get("mimeType", "")

                all_responses.append(url)  # Логируем все запросы

                # Перехватываем редиректы на файлы (301, 302, 303, 307, 308)
                if status in [301, 302, 303, 307, 308]:
                    location = headers.get("location", headers.get("Location", ""))
                    if location and not location.endswith(".txt"):
                        # Проверяем, что это не redirect на analytics или tracking
                        if not any(x in location.lower() for x in ["analytics", "tracking", "pixel", "beacon"]):
                            print(f"↪️ Редирект на: {location[:100]}")
                            download_initiated.append(location)

                # Перехватываем Content-Disposition (прямое скачивание файла)
                content_disposition = headers.get("content-disposition", headers.get("Content-Disposition", ""))
                if "attachment" in content_disposition and "filename=" in content_disposition:
                    # Проверяем что это не .txt файл и не 1px image
                    content_type = headers.get("content-type", headers.get("Content-Type", ""))
                    content_length = headers.get("content-length", headers.get("Content-Length", "0"))

                    # Игнорируем маленькие файлы (меньше 1KB - вероятно tracking pixel)
                    try:
                        file_size = int(content_length)
                    except:
                        file_size = 0

                    if file_size > 1024:
                        if not url.endswith(".txt"):
                            print(f"📥 Скачивание файла (размер: {file_size} bytes): {url[:100]}")
                            download_initiated.append(url)
                    else:
                        print(f"⚠️ Игнорируем маленький файл ({file_size} bytes): {url[:100]}")

                # Ищем API запросы для скачивания
                # Freepik API обычно возвращает JSON с download URL
                if "/api/" in url or "/download" in url:
                    # Проверяем что это JSON ответ
                    if "application/json" in mime_type or status == 200:
                        print(f"🔍 Перехвачен API запрос (mime: {mime_type}): {url[:100]}")
                        captured_responses.append(event)

            client.on("Network.responseReceived", on_response)

            # Navigate to asset page
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=30000)

            # Click download button
            await page.click("button[data-cy='download-button']", timeout=15000)

            # Ждём чтобы собрать все запросы (даём время на все редиректы и API запросы)
            print("⏳ Ожидание сбора всех запросов...")
            await asyncio.sleep(5)  # Даём время на завершение всех запросов

            # Wait for download URL from intercepted network responses
            download_url = await self._wait_for_download_url(client, captured_responses, download_initiated, download_info, timeout=15)

            elapsed = time.time() - start_time
            self.total_time += elapsed

            if download_url:
                self.success_count += 1
                print(f"   ✅ {elapsed:.2f} сек")
            else:
                self.fail_count += 1
                print(f"   ❌ Не получен URL")

                # Отладка: показываем все запросы
                print(f"\n🔍 ОТЛАДКА: Всего перехвачено {len(all_responses)} запросов")
                print(f"📋 Найдено прямых ссылок: {len(download_initiated)}")
                print(f"📋 Перехвачено API ответов: {len(captured_responses)}")

                if download_initiated:
                    print("\n📋 Прямые ссылки на скачивание:")
                    for url in download_initiated:
                        print(f"   • {url}")

                print("\n📋 Ключевые запросы (download, api, etc):")
                for url in all_responses:
                    if any(word in url.lower() for word in ["download", "api", "video", "content", "file"]):
                        print(f"   • {url[:200]}")

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            self.total_time += elapsed
            self.fail_count += 1
            print(f"   ❌ Ошибка: {e}")
            print(f"   ⏱️  {elapsed:.2f} сек")
            return None

        finally:
            # IMPORTANT: Close CDP session first to prevent resource leaks
            if client:
                try:
                    await client.detach()
                except Exception:
                    pass

            # Then close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def _wait_for_download_url(self, client, captured_responses, download_initiated, download_info, timeout=15) -> str | None:
        """
        Wait for download URL to appear in intercepted network responses.
        Non-blocking approach using asyncio.sleep instead of time.sleep.

        Args:
            client: CDP client session
            captured_responses: List of captured network responses
            download_initiated: List of direct download URLs from headers
            download_info: Dict with download event info
            timeout: Maximum wait time in seconds

        Returns:
            Download URL or None if timeout
        """
        # Собираем все возможные URL-кандидаты
        candidates = []

        # 1. Проверяем download event
        if download_info.get('url'):
            url = download_info['url']
            print(f"✅ Кандидат из download event: {url[:100]}")
            candidates.append(('download_event', url, 100))  # Высокий приоритет

        # 2. Проверяем прямые ссылки (редиректы и Content-Disposition)
        for url in download_initiated:
            print(f"✅ Кандидат из прямой ссылки: {url[:100]}")
            candidates.append(('direct_link', url, 90))  # Средний приоритет

        # 3. Проверяем API ответы
        print(f"\n📋 Анализ {len(captured_responses)} API ответов...")
        for resp in captured_responses:
            try:
                request_id = resp.get("requestId")
                if not request_id:
                    continue

                body = await client.send("Network.getResponseBody", {"requestId": request_id})
                body_text = body.get("body", "")

                if not body_text:
                    continue

                # Пытаемся распарсить JSON
                try:
                    data = json.loads(body_text)
                except json.JSONDecodeError:
                    continue

                # Логируем структуру JSON для отладки
                print(f"📋 JSON структура: {list(data.keys()) if isinstance(data, dict) else type(data)}")

                # Ищем URL в разных возможных местах
                url = None

                # Вариант 1: прямой ключ "url"
                if isinstance(data, dict):
                    url = data.get("url") or data.get("download_url") or data.get("downloadUrl")

                    # Вариант 2: вложенная структура data.data.url
                    if not url and "data" in data:
                        nested_data = data["data"]
                        if isinstance(nested_data, dict):
                            url = nested_data.get("url") or nested_data.get("download_url") or nested_data.get("downloadUrl")

                            # Вариант 3: data.data.attributes.url
                            if not url and "attributes" in nested_data:
                                attrs = nested_data["attributes"]
                                if isinstance(attrs, dict):
                                    url = attrs.get("url") or attrs.get("download_url") or attrs.get("downloadUrl")

                # Добавляем URL в кандидаты если нашли
                if url and not url.endswith(".txt"):
                    print(f"✅ Кандидат из JSON: {url[:100]}")
                    candidates.append(('json_api', url, 80))  # Низкий приоритет
                elif url:
                    print(f"⚠️ Пропускаем .txt файл из JSON: {url[:100]}")

            except Exception as e:
                print(f"⚠️ Ошибка при парсинге ответа: {e}")
                continue

        # Теперь выбираем лучший кандидат
        print(f"\n📊 Всего найдено кандидатов: {len(candidates)}")

        if not candidates:
            print("❌ Не найдено ни одного кандидата")
            return None

        # Сортируем по приоритету (больше = лучше)
        candidates.sort(key=lambda x: x[2], reverse=True)

        # Выводим все кандидаты
        print("\n📋 Список кандидатов (по приоритету):")
        for i, (source, url, priority) in enumerate(candidates, 1):
            print(f"   {i}. [{priority}] {source}: {url[:150]}")

        # Возвращаем лучший
        best_source, best_url, best_priority = candidates[0]
        print(f"\n✅ Выбран лучший: {best_source} (приоритет: {best_priority})")
        return best_url


# Main API function for bot integration
async def get_freepik_direct_download_url(asset_url: str) -> str | None:
    """
    Get direct download URL for a single Freepik asset.
    This is the main function used by the bot.

    Args:
        asset_url: URL of the Freepik asset page

    Returns:
        Direct download URL or None if failed

    Example:
        url = await get_freepik_direct_download_url("https://www.freepik.com/...")
    """
    if not os.path.exists(COOKIE_FILE):
        print(f"❌ Cookies file not found: {COOKIE_FILE}")
        return None

    # Используем семафор для ограничения параллельных скачиваний
    try:
        from bot.services import BotServices
        semaphore = BotServices.download_semaphore
    except:
        # Если запускается не из бота (тесты), семафор не нужен
        semaphore = None

    print(f"🚀 Загружаем: {asset_url}")

    if semaphore:
        async with semaphore:
            async with FreepikDownloader() as downloader:
                link = await downloader.get_download_url(asset_url)

                if link:
                    print(f"✅ Прямая ссылка получена")
                    return link
                else:
                    print("❌ Не удалось получить ссылку")
                    return None
    else:
        async with FreepikDownloader() as downloader:
            link = await downloader.get_download_url(asset_url)

            if link:
                print(f"✅ Прямая ссылка получена")
                return link
            else:
                print("❌ Не удалось получить ссылку")
                return None


# Test/debug functions
async def test_single_url():
    """Test single URL download"""
    test_url = "https://www.freepik.com/premium-vector/full-moon-black-white-concept_26371617.htm"
    print("="*70)
    print("🚀 Получение прямой ссылки на скачивание")
    print("="*70)
    print(f"🔗 URL: {test_url}\n")

    result = await get_freepik_direct_download_url(test_url)

    if result:
        print(f"\n✅ Прямая ссылка получена!")
        print(f"🔗 {result[:100]}...")
    else:
        print(f"\n❌ Не удалось получить ссылку")

if __name__ == "__main__":
    asyncio.run(test_single_url())

