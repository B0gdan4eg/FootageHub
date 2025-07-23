import os
import aiohttp
import json

COOKIE_FILE = "envato_cookies.json"

async def download_envato_file(download_url: str, filename: str, save_dir: str = "downloads") -> str | None:
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, filename)

    # Загружаем куки из JSON
    if not os.path.exists(COOKIE_FILE):
        print(f"❌ Файл {COOKIE_FILE} не найден.")
        return None

    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookie_list = json.load(f)
        # Преобразуем список cookies (как из Playwright/Chrome) в словарь {name: value}
        cookies = {cookie["name"]: cookie["value"] for cookie in cookie_list if "name" in cookie and "value" in cookie}
    except Exception as e:
        print(f"❌ Ошибка при загрузке cookies: {e}")
        return None

    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "*/*"
    }

    async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
        async with session.get(download_url) as resp:
            if resp.status == 200:
                content = await resp.read()
                loop = aiohttp.helpers.get_running_loop()
                await loop.run_in_executor(None, lambda: open(file_path, "wb").write(content))
                print(f"✅ Файл успешно загружен: {file_path}")
                return file_path
            else:
                print(f"❌ Ошибка при скачивании с Envato: HTTP {resp.status}")
                return None
