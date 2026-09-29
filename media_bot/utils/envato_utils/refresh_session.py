"""Isolated Envato browser worker. Never run against a live owner's state directory."""

import asyncio
import contextlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import psutil

from media_bot.utils.freepik_utils.logger import logger

from .envato_playwright import COOKIE_DIR, EnvatoDownloader, get_next_cookie_file
from .http_downloader import (
    asset_url,
    clean_headers,
    download_link,
    first_party,
    save_private,
    validate_state,
)


async def run(directory):
    incoming = json.loads((directory / "refresh-input.json").read_text(encoding="utf-8"))
    url = asset_url(incoming["url"])
    state = incoming.get("state") or {}
    if state:
        validate_state(state)
    account = state.get("account") or Path(get_next_cookie_file()).name
    cookie_file = Path(COOKIE_DIR) / account
    headers = dict(state.get("headers", {}))
    tasks = []

    async def capture(request):
        p = urlsplit(request.url)
        if p.hostname == "app.envato.com" and p.path == "/download.data":
            headers.update(clean_headers(await request.all_headers()))

    logger.disable()  # The owner sends throttled errors, never worker URLs/tokens.
    async with EnvatoDownloader(
        cookie_file=str(cookie_file),
        profile_dir=str(directory / "profiles" / Path(account).stem),
        cookies=state.get("cookies"),
    ) as browser:
        browser.context.on(
            "request", lambda request: tasks.append(asyncio.create_task(capture(request)))
        )
        if incoming.get("licensed"):
            link = await browser.get_download_url_with_license(url)
        else:
            link = await browser.get_download_url(url)
        await asyncio.gather(*tasks, return_exceptions=True)
        if not download_link(link):
            save_private(
                directory / "browser-result.json",
                {"failure": browser.last_failure or "no_verified_link"},
            )
            raise RuntimeError("No verified browser file")
        mappings = dict(state.get("mappings", {}))
        if browser.last_asset and not incoming.get("licensed"):
            kind, identifier = browser.last_asset
            mappings.pop(url, None)
            mappings[url] = f"https://app.envato.com/{kind}/{identifier}"
            mappings = dict(list(mappings.items())[-500:])
        candidate = validate_state(
            {
                "version": 1,
                "account": account,
                "cookies": [c for c in await browser.context.cookies() if first_party(c["domain"])],
                "headers": clean_headers(headers),
                "mappings": mappings,
                "updated_at": time.time(),
            }
        )
    # Publish only after Chromium and its driver have actually exited.
    await cleanup()
    save_private(directory / "candidate.json", candidate)
    save_private(directory / "browser-result.json", {"link": link})


async def cleanup():
    children = psutil.Process().children(recursive=True)
    _, alive = await asyncio.to_thread(psutil.wait_procs, children, timeout=3)
    for child in alive:
        with contextlib.suppress(psutil.NoSuchProcess):
            child.kill()
    await asyncio.to_thread(psutil.wait_procs, alive, timeout=5)


async def main():
    try:
        await run(Path(sys.argv[1]))
    finally:
        await cleanup()


if __name__ == "__main__":
    asyncio.run(main())
