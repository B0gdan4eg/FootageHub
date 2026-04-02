"""
Авто-обновление GR_TOKEN для Freepik.

Freepik использует Firebase Auth: GR_TOKEN — короткоживущий JWT (1 час),
GR_REFRESH — долгоживущий Firebase refresh token (29 дней).

При истечении GR_TOKEN запускает отдельный nodriver-браузер,
загружает страницу Freepik с валидным GR_REFRESH, перехватывает
ответ securetoken.googleapis.com и сохраняет новый токен в cookie-файл.

Если API-ключ Firebase уже закэширован — делает рефреш напрямую
через REST без запуска браузера.
"""

import asyncio
import base64
import glob
import json
import os
import time

import nodriver as uc
from nodriver import cdp

COOKIE_DIR = os.path.dirname(__file__)
_API_KEY_CACHE_FILE = os.path.join(COOKIE_DIR, ".firebase_api_key")
_refresh_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_jwt_exp(token: str) -> float:
    """Возвращает exp из JWT без проверки подписи."""
    try:
        payload = base64.b64decode(token.split(".")[1] + "==")
        return float(json.loads(payload).get("exp", 0))
    except Exception:
        return 0.0


def _find_chromium() -> str | None:
    patterns = [
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/home/*/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/ms-playwright/chromium-*/chrome-linux/chrome",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def _load_api_key() -> str | None:
    try:
        with open(_API_KEY_CACHE_FILE) as f:
            key = f.read().strip()
            return key if key.startswith("AIza") else None
    except FileNotFoundError:
        return None


def _save_api_key(key: str) -> None:
    with open(_API_KEY_CACHE_FILE, "w") as f:
        f.write(key)
    print(f"[TOKEN REFRESH] Firebase API key сохранён")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_token_expired(cookie_file: str, buffer_seconds: int = 120) -> bool:
    """
    Проверяет, истёк ли GR_TOKEN (с буфером buffer_seconds).
    buffer_seconds=120 — обновляем за 2 минуты до истечения.
    """
    try:
        with open(cookie_file) as f:
            cookies = json.load(f)
        gr = next((c for c in cookies if c["name"] == "GR_TOKEN"), None)
        if not gr:
            return True
        exp = float(gr.get("expires", 0))
        if exp <= 0:
            exp = _decode_jwt_exp(gr["value"])
        return time.time() > exp - buffer_seconds
    except Exception:
        return True


async def refresh_token(cookie_file: str) -> bool:
    """
    Обновляет GR_TOKEN в cookie_file.

    Сначала пробует прямой Firebase REST вызов (если API-ключ закэширован),
    иначе запускает браузер и перехватывает запрос.

    Возвращает True при успехе.
    """
    async with _refresh_lock:
        # Проверяем ещё раз внутри лока — вдруг другая корутина уже обновила
        if not is_token_expired(cookie_file):
            return True

        api_key = _load_api_key()
        if api_key:
            ok = await _refresh_direct(cookie_file, api_key)
            if ok:
                return True
            print("[TOKEN REFRESH] Прямой рефреш не удался, пробуем через браузер")

        return await _refresh_via_browser(cookie_file)


async def ensure_token_valid(cookie_file: str) -> bool:
    """
    Проверяет токен и обновляет при необходимости.
    Возвращает True если токен валиден.
    """
    if not is_token_expired(cookie_file):
        return True
    print(f"[TOKEN REFRESH] GR_TOKEN истёк — обновляем...")
    return await refresh_token(cookie_file)


# ---------------------------------------------------------------------------
# Implementation: direct REST refresh
# ---------------------------------------------------------------------------

async def _refresh_direct(cookie_file: str, api_key: str) -> bool:
    """Обновляет токен через Firebase REST API без браузера."""
    import urllib.request
    import urllib.parse
    import urllib.error

    with open(cookie_file) as f:
        cookies = json.load(f)

    gr_refresh = next((c for c in cookies if c["name"] == "GR_REFRESH"), None)
    if not gr_refresh:
        return False

    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": gr_refresh["value"],
    }).encode()

    try:
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"https": proxy, "http": proxy})
            )
        else:
            opener = urllib.request.build_opener()

        with opener.open(req, timeout=15) as resp:
            data = json.loads(resp.read())

        id_token = data.get("id_token")
        new_refresh = data.get("refresh_token")
        if not id_token:
            print(f"[TOKEN REFRESH] REST ответ без id_token: {list(data.keys())}")
            return False

        _apply_new_token(cookies, id_token, new_refresh)
        with open(cookie_file, "w") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print("[TOKEN REFRESH] ✅ Прямой рефреш успешен")
        return True

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        print(f"[TOKEN REFRESH] REST HTTP {e.code}: {body[:200]}")
        return False
    except Exception as e:
        print(f"[TOKEN REFRESH] REST ошибка: {e}")
        return False


# ---------------------------------------------------------------------------
# Implementation: browser-based refresh
# ---------------------------------------------------------------------------

async def _refresh_via_browser(cookie_file: str) -> bool:
    """
    Запускает отдельный Chrome, загружает Freepik с куками,
    перехватывает ответ securetoken.googleapis.com.
    """
    with open(cookie_file) as f:
        cookies = json.load(f)

    gr_refresh = next((c for c in cookies if c["name"] == "GR_REFRESH"), None)
    if not gr_refresh:
        print("[TOKEN REFRESH] GR_REFRESH не найден")
        return False

    browser = None
    try:
        browser = await uc.start(
            headless=False,
            sandbox=False,
            browser_executable_path=_find_chromium(),
        )
        tab = await browser.get("about:blank")

        # Включаем мониторинг сети
        await tab.send(cdp.network.enable())

        # Устанавливаем куки
        for c in cookies:
            try:
                await tab.send(cdp.network.set_cookie(
                    name=c["name"],
                    value=c["value"],
                    domain=c.get("domain", ".freepik.com"),
                    path=c.get("path", "/"),
                    secure=c.get("secure", False),
                    http_only=c.get("httpOnly", False),
                ))
            except Exception:
                pass

        token_data: dict = {}
        api_key_found: list[str] = []

        # Перехватываем запросы к Firebase
        async def on_request(evt: cdp.network.RequestWillBeSent):
            if "securetoken.googleapis.com" not in evt.request.url:
                return
            import re
            m = re.search(r"[?&]key=([A-Za-z0-9_\-]+)", evt.request.url)
            if m and not api_key_found:
                key = m.group(1)
                api_key_found.append(key)
                print(f"[TOKEN REFRESH] Firebase API key перехвачен: {key[:20]}...")

        async def on_response(evt: cdp.network.ResponseReceived):
            if "securetoken.googleapis.com" not in evt.response.url:
                return
            if evt.response.status != 200:
                print(f"[TOKEN REFRESH] Firebase ответил {evt.response.status}")
                return
            try:
                await asyncio.sleep(0.2)
                body = await tab.send(
                    cdp.network.get_response_body(request_id=evt.request_id)
                )
                data = json.loads(body.body)
                if "id_token" in data:
                    token_data["id_token"] = data["id_token"]
                    token_data["refresh_token"] = data.get("refresh_token", "")
                    print("[TOKEN REFRESH] ✅ Новый Firebase токен получен")
            except Exception as e:
                print(f"[TOKEN REFRESH] Ошибка чтения ответа: {e}")

        tab.add_handler(cdp.network.RequestWillBeSent, on_request)
        tab.add_handler(cdp.network.ResponseReceived, on_response)

        # Открываем Freepik — Firebase SDK должен автообновить токен
        print("[TOKEN REFRESH] Открываем Freepik...")
        try:
            await tab.get("https://www.freepik.com")
        except Exception:
            pass

        # Ждём до 20 секунд
        for _ in range(200):
            if token_data.get("id_token"):
                break
            await asyncio.sleep(0.1)

        # Кэшируем API ключ для будущих прямых рефрешей
        if api_key_found:
            _save_api_key(api_key_found[0])

        if not token_data.get("id_token"):
            print("[TOKEN REFRESH] ❌ Токен не получен за 20с")
            # Если API ключ перехватили, попробуем прямой рефреш
            if api_key_found:
                print("[TOKEN REFRESH] Пробуем прямой рефреш с перехваченным ключом...")
                ok = await _refresh_direct(cookie_file, api_key_found[0])
                return ok
            return False

        # Обновляем cookie-файл
        _apply_new_token(cookies, token_data["id_token"], token_data.get("refresh_token"))

        # Читаем актуальные короткоживущие куки из браузера
        try:
            all_cookies = await tab.send(cdp.network.get_all_cookies())
            short_lived = {"XSRF-TOKEN", "pikaso_session", "ak_bmsc", "__cf_bm",
                           "_hjSession_1331604", "_cfuvid", "_dd_s"}
            browser_cookie_map = {bc.name: bc for bc in all_cookies.cookies}
            for c in cookies:
                if c["name"] in short_lived and c["name"] in browser_cookie_map:
                    bc = browser_cookie_map[c["name"]]
                    c["value"] = bc.value
                    if bc.expires and bc.expires > 0:
                        c["expires"] = bc.expires
        except Exception as e:
            print(f"[TOKEN REFRESH] Не удалось прочитать куки браузера: {e}")

        with open(cookie_file, "w") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print(f"[TOKEN REFRESH] ✅ Куки сохранены → {os.path.basename(cookie_file)}")
        return True

    except Exception as e:
        print(f"[TOKEN REFRESH] Критическая ошибка: {e}")
        return False
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _apply_new_token(cookies: list, id_token: str, refresh_token: str | None) -> None:
    """Обновляет GR_TOKEN и GR_REFRESH в списке кук."""
    new_exp = _decode_jwt_exp(id_token)
    for c in cookies:
        if c["name"] == "GR_TOKEN":
            c["value"] = id_token
            c["expires"] = new_exp
        elif c["name"] == "GR_REFRESH" and refresh_token:
            c["value"] = refresh_token
            c["expires"] = time.time() + 29 * 24 * 3600
