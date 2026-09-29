"""Optional fast path using identities learned by the existing browser owner."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from .asset_identity import describe_requested
from .http_downloader import (
    asset_url,
    clean_headers,
    export_cookies,
    first_party,
    modern_asset,
    new_session,
    request_link,
    save_private,
)

log = logging.getLogger(__name__)


def _task_id(value: str | None) -> str:
    return value or uuid.uuid4().hex[:8]


class BrowserHTTP:
    """Per-account fast path: mappings source->UUID, fresh signed link per request.

    Signed CDN links are never persisted; only verified source->item mappings
    (max 500) plus first-party cookies/headers are stored.
    """

    def __init__(self, directory):
        self.path = Path(directory) / "http-cache.json"
        self.lock = asyncio.Lock()
        self.state = None
        self.session = None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                data.get("version") == 1
                and data.get("cookies")
                and len(data.get("mappings", {})) <= 500
            ):
                if all(first_party(c["domain"]) for c in data["cookies"]):
                    self.state = data
        except (OSError, ValueError, KeyError, TypeError):
            pass

    async def get(self, url, task_id: str | None = None):
        task = _task_id(task_id)
        requested = describe_requested(url)
        started = time.monotonic()
        async with self.lock:
            try:
                url = asset_url(url)
                if not self.state or not (
                    modern_asset(url) or url in self.state.get("mappings", {})
                ):
                    log.info(
                        "Envato HTTP skip task=%s requested=%s reason=no_mapping seconds=%.3f",
                        task,
                        requested,
                        time.monotonic() - started,
                    )
                    return None
                if not self.session:
                    self.session = new_session(self.state)
                link = await request_link(self.session, self.state, url)
                self.state["cookies"] = export_cookies(self.session.cookies.jar)
                try:
                    save_private(self.path, self.state)
                except OSError:
                    log.warning("Envato HTTP cookie persistence failed task=%s", task)
                log.info(
                    "Envato HTTP success task=%s requested=%s seconds=%.3f",
                    task,
                    requested,
                    time.monotonic() - started,
                )
                return link
            except Exception as exc:
                log.info(
                    "Envato HTTP fallback task=%s requested=%s reason=%s status=%s seconds=%.3f",
                    task,
                    requested,
                    getattr(exc, "reason", type(exc).__name__),
                    getattr(exc, "status", 0),
                    time.monotonic() - started,
                )
                if self.session:
                    try:
                        await self.session.close()
                    except Exception:
                        pass
                    self.session = None
                return None

    async def remember(self, url, item, headers, cookies, task_id: str | None = None):
        task = _task_id(task_id)
        async with self.lock:
            url = asset_url(url)
            target = f"https://app.envato.com/{item[0]}/{item[1]}"
            if modern_asset(target) != item:
                raise ValueError("Invalid Envato item identity")
            mappings = dict((self.state or {}).get("mappings", {}))
            mappings.pop(url, None)
            mappings[url] = target
            data = {
                "version": 1,
                "mappings": dict(list(mappings.items())[-500:]),
                "headers": clean_headers(headers),
                "cookies": [c for c in cookies if first_party(c["domain"])],
                "updated_at": time.time(),
            }
            if self.session:
                try:
                    await self.session.close()
                except Exception:
                    pass
                self.session = None
            self.state = data
            save_private(self.path, data)
            log.info(
                "Envato mapping remembered task=%s requested=%s item=%s type=%s total=%s",
                task,
                describe_requested(url),
                item[1],
                item[0],
                len(data["mappings"]),
            )

    async def close(self):
        async with self.lock:
            if self.session:
                await self.session.close()
                self.session = None
