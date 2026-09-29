"""Short-lived browser worker. The main bot never keeps a Freepik browser open."""

import asyncio
import contextlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

import psutil
from nodriver import cdp

from .freepik import COOKIE_DIR, FreepikDownloader
from .http_downloader import (
    ALLOWED_HOSTS,
    PROBE_URL,
    clean_headers,
    first_party,
    save_private,
    validate_state,
)
from .logger import logger


def raw_command(method, **params):
    result = yield {"method": method, "params": params}
    return result


async def refresh(directory):
    with (directory / "refresh-input.json").open(encoding="utf-8") as stream:
        request = json.load(stream)
    previous = request.get("state", {})
    asset_url = request.get("asset_url", PROBE_URL)
    cookies = previous.get("cookies")
    if not cookies:
        cookie_file = os.environ.get(
            "FREEPIK_COOKIE_FILE", str(Path(COOKIE_DIR) / "freepik_cookies_1.json")
        )
        with open(cookie_file, encoding="utf-8") as stream:
            cookies = json.load(stream)
    downloader = FreepikDownloader(cookies=cookies, profile_dir=str(directory / "profile"))
    logger.disable()
    candidate = None
    try:
        await asyncio.wait_for(downloader.__aenter__(), timeout=30)
        tab = downloader.browser.tabs[0]
        templates = []

        def on_request(event):
            parsed = urlsplit(event.request.url)
            if parsed.hostname in ALLOWED_HOSTS and parsed.path == "/api/regular/download":
                templates.append((parsed, dict(event.request.headers)))

        tab.add_handler(cdp.network.RequestWillBeSent, on_request)
        await tab.send(cdp.network.enable())
        link = await asyncio.wait_for(downloader.get_download_url(asset_url), timeout=100)
        if not link:
            raise RuntimeError("Authenticated refresh probe failed")
        try:
            parsed, headers = templates[-1]
            query = parse_qs(parsed.query)
            # Raw CDP avoids nodriver's outdated Cookie schema on newer Chrome versions.
            raw = await asyncio.wait_for(tab.send(raw_command("Storage.getCookies")), timeout=5)
            candidate = validate_state(
                {
                    "version": 1,
                    "endpoint": urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")),
                    "wallet_id": query["walletId"][0],
                    "locale": query.get("locale", ["en"])[0],
                    "headers": clean_headers(headers),
                    "cookies": [c for c in raw["cookies"] if first_party(c["domain"])],
                    "refreshed_at": time.time(),
                    "updated_at": time.time(),
                }
            )
        except Exception:
            pass
    finally:
        owned = psutil.Process().children(recursive=True)
        await downloader.__aexit__(None, None, None)
        _, alive = await asyncio.to_thread(psutil.wait_procs, owned, timeout=3)
        for child in alive:
            with contextlib.suppress(psutil.NoSuchProcess):
                child.kill()
        _, alive = await asyncio.to_thread(psutil.wait_procs, alive, timeout=5)
        if alive:
            raise RuntimeError("Refresh browser did not exit")
    save_private(directory / "browser-result.json", {"url": link})
    if candidate:
        save_private(directory / "candidate.json", candidate)


if __name__ == "__main__":
    try:
        asyncio.run(refresh(Path(sys.argv[1])))
    except Exception as exc:
        # Exceptions can contain authenticated URLs; only expose the exception class.
        print("Freepik refresh failed: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
