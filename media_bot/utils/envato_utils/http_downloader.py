"""Envato HTTP downloads; a short-lived browser owns session refresh/fallback."""

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit
from uuid import UUID

from curl_cffi.requests import AsyncSession, Cookies

# These helpers are provider-neutral; Freepik request/session logic stays separate.
from media_bot.utils.freepik_utils.http_downloader import (
    HTTPFailure,
    clean_headers,
    cookie_jar,
    save_private,
    stop_child,
)
from media_bot.utils.freepik_utils.logger import logger as admin_logger

PROBE_URL = "https://app.envato.com/video-templates/4671289c-05c0-481b-a1b7-98165fbe61c2"
log = logging.getLogger(__name__)


def asset_url(value):
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or p.hostname not in {"app.envato.com", "elements.envato.com"}
        or p.username
        or p.password
        or p.port not in (None, 443)
    ):
        raise ValueError("Unsupported Envato asset")
    if p.hostname == "app.envato.com":
        if not modern_asset(value):
            raise ValueError("Missing Envato item UUID")
    elif not re.fullmatch(r"/(?:[a-z]{2}/)?[\w-]+-[A-Z0-9]{5,12}/?", p.path):
        raise ValueError("Missing Envato item ID")
    return urlunsplit(("https", p.hostname, p.path.rstrip("/"), "", ""))


def modern_asset(value):
    p = urlsplit(value)
    if p.hostname != "app.envato.com":
        return None
    match = re.fullmatch(r"/(?:search/)?([a-z][a-z-]{1,40})/([a-fA-F0-9-]{36})/?", p.path)
    if not match:
        return None
    try:
        return match[1], str(UUID(match[2]))
    except ValueError:
        return None


def first_party(domain):
    domain = domain.lstrip(".").lower()
    return domain == "envato.com" or domain.endswith(".envato.com")


def export_cookies(jar):
    jar.clear_expired_cookies()
    return [
        dict(
            name=c.name,
            value=c.value,
            domain=c.domain,
            path=c.path,
            secure=c.secure,
            expires=c.expires or -1,
            httpOnly=c.has_nonstandard_attr("HttpOnly"),
        )
        for c in jar
        if first_party(c.domain)
    ]


def validate_state(state):
    if (
        state.get("version") != 1
        or not isinstance(state.get("cookies"), list)
        or not state["cookies"]
    ):
        raise ValueError("Invalid Envato session")
    if any(not first_party(c["domain"]) for c in state["cookies"]):
        raise ValueError("Unexpected cookie domain")
    # A session remains attached to its seed account, including during fallback.
    if not re.fullmatch(r"envato_cookies(?:_[\w-]+)?\.json", state.get("account", "")):
        raise ValueError("Invalid Envato account")
    mappings = state.get("mappings", {})
    if not isinstance(mappings, dict) or len(mappings) > 500:
        raise ValueError("Invalid item mappings")
    for source, target in mappings.items():
        asset_url(source)
        if not modern_asset(target):
            raise ValueError("Invalid mapped asset")
    return state


def load_state(path):
    return validate_state(json.loads(Path(path).read_text(encoding="utf-8")))


def download_link(data, expected_item=None):
    # React Router's text/x-script response is a JSON reference table, not JS to execute.
    pending = [data]
    found = set()
    while pending:
        value = pending.pop()
        if isinstance(value, (list, dict)):
            pending.extend(value.values() if isinstance(value, dict) else value)
        elif isinstance(value, str) and value.startswith("https://"):
            p = urlsplit(value)
            try:
                valid = (
                    not p.username
                    and not p.password
                    and p.port in (None, 443)
                    and re.fullmatch(
                        r"[a-z-]*downloads\.elements\.envatousercontent\.com", p.hostname or ""
                    )
                    and (
                        p.path.startswith("/files/")
                        or re.fullmatch(r"/[a-fA-F0-9-]{36}/[^/]+", p.path)
                    )
                    and (
                        not expected_item
                        or not parse_qs(p.query).get("item_id")
                        or parse_qs(p.query)["item_id"] == [expected_item]
                    )
                )
            except ValueError:
                valid = False
            if valid:
                found.add(value)
    return next(iter(found)) if len(found) == 1 else None


def new_session(state):
    return AsyncSession(
        impersonate="chrome150",
        default_headers=False,
        cookies=cookie_jar(state["cookies"]),
        max_clients=1,
    )


async def request_link(session, state, url):
    url = asset_url(url)
    item = modern_asset(url) or modern_asset(state.get("mappings", {}).get(url, ""))
    if not item:
        raise HTTPFailure("unresolved_legacy_asset")
    kind, identifier = item
    headers = clean_headers(state.get("headers", {}))
    headers.update(
        {
            "accept": "*/*",
            "referer": f"https://app.envato.com/{kind}/{identifier}",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
    )
    body = bytearray()

    def collect(chunk):
        if len(body) + len(chunk) > 1024 * 1024:
            raise ValueError("Envato response too large")
        body.extend(chunk)

    response = await session.get(
        "https://app.envato.com/download.data",
        params={"itemUuid": identifier, "itemType": kind, "_routes": "routes/download/route"},
        headers=headers,
        timeout=12,
        allow_redirects=False,
        content_callback=collect,
    )
    mime = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if response.status_code != 200 or mime not in {"application/json", "text/x-script"}:
        raise HTTPFailure("security_check_or_http_error", response.status_code)
    link = download_link(json.loads(body), expected_item=identifier)
    if not link:
        raise HTTPFailure("missing_file_link", response.status_code)
    return link


class EnvatoHTTPDownloader:
    def __init__(self, directory=None):
        self.directory = Path(
            directory or os.getenv("ENVATO_STATE_DIR", Path(__file__).parent / ".session")
        )
        self.path = self.directory / "session.json"
        self.state = self.session = None
        self.lock = asyncio.Lock()
        self.last_alert = 0
        self.events = log

    def event(self, event, **fields):
        self.events.info(json.dumps({"event": event, "time": time.time(), **fields}))

    async def __aenter__(self):
        directory = self.directory / "logs"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.events = logging.getLogger(
            __name__ + "." + hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:12]
        )
        self.events.setLevel(logging.INFO)
        if not self.events.handlers:
            handler = RotatingFileHandler(
                directory / "downloads.jsonl",
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
                delay=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.events.addHandler(handler)
        try:
            self.state = load_state(self.path)
            self.session = new_session(self.state)
        except (OSError, ValueError, KeyError, TypeError):
            self.event("session_unavailable")
        self.event("started", session_ready=bool(self.session))
        return self

    async def __aexit__(self, *args):
        async with self.lock:
            if self.session:
                await self.session.close()
                self.session = None
            for handler in self.events.handlers[:]:
                handler.close()
                self.events.removeHandler(handler)

    async def alert(self, message):
        log.error(message)
        if not self.last_alert or time.monotonic() - self.last_alert > 3600:
            self.last_alert = time.monotonic()
            await admin_logger.error(message)

    async def get_download_url(self, url, task_id=None):
        return await self._download(url, licensed=False, task_id=task_id)

    async def get_download_url_with_license(self, url, task_id=None):
        return await self._download(url, licensed=True, task_id=task_id)

    async def _download(self, url, licensed, task_id=None):
        import uuid as _uuid

        task = task_id or _uuid.uuid4().hex[:8]
        try:
            url = asset_url(url)
        except (ValueError, TypeError):
            self.event("invalid_resource", task=task)
            return None
        started = time.monotonic()
        async with self.lock:
            if not licensed:
                http_started = time.monotonic()
                try:
                    if not self.session:
                        raise HTTPFailure("session_unavailable")
                    link = await request_link(self.session, self.state, url)
                    self.state = {
                        **self.state,
                        "cookies": export_cookies(self.session.cookies.jar),
                        "updated_at": time.time(),
                    }
                    try:
                        save_private(self.path, self.state)
                    except OSError:
                        await self.alert("[ENVATO] Cannot persist session cookies.")
                    self.event(
                        "http_success",
                        task=task,
                        seconds=round(time.monotonic() - started, 3),
                        http_seconds=round(time.monotonic() - http_started, 3),
                    )
                    return link
                except Exception as exc:
                    if self.session and self.state:
                        self.session.cookies = Cookies(cookie_jar(self.state["cookies"]))
                    self.event(
                        "http_failed",
                        task=task,
                        error=type(exc).__name__,
                        reason=getattr(exc, "reason", "request_error"),
                        status=getattr(exc, "status", 0),
                        seconds=round(time.monotonic() - http_started, 3),
                    )
            link = await self._browser_run(url, "fallback", licensed, task_id=task)
            self.event(
                "download_finished",
                task=task,
                success=bool(link),
                licensed=licensed,
                seconds=round(time.monotonic() - started, 3),
            )
            if not link:
                await self.alert("[ENVATO] Download failed; see Envato session logs.")
            return link

    async def refresh_session(self):
        async with self.lock:
            return bool(await self._browser_run(PROBE_URL, "refresh", False))

    async def _browser_run(self, url, purpose, licensed=False, task_id=None):
        import uuid as _uuid

        task = task_id or _uuid.uuid4().hex[:8]
        paths = {
            name: self.directory / (name + ".json")
            for name in ("refresh-input", "candidate", "browser-result")
        }
        process = None
        link = None
        started = time.monotonic()
        try:
            state = self.state or {}
            try:
                browser = load_state(self.directory / "browser-session.json")
                if browser.get("updated_at", 0) > state.get("updated_at", 0):
                    state = browser
            except (OSError, ValueError, KeyError, TypeError):
                pass
            save_private(paths["refresh-input"], {"state": state, "url": url, "licensed": licensed})
            paths["candidate"].unlink(missing_ok=True)
            paths["browser-result"].unlink(missing_ok=True)
            self.event("browser_started", task=task, purpose=purpose, licensed=licensed)
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "media_bot.utils.envato_utils.refresh_session",
                str(self.directory.resolve()),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            await asyncio.wait_for(process.wait(), timeout=85 if purpose == "fallback" else 150)
            if process.returncode:
                failure = "worker_failed"
                if paths["browser-result"].exists():
                    result = json.loads(paths["browser-result"].read_text(encoding="utf-8"))
                    value = result.get("failure", "")
                    if re.fullmatch(r"[a-zA-Z0-9_]{1,80}", value):
                        failure = value
                raise HTTPFailure(failure)
            result = json.loads(paths["browser-result"].read_text(encoding="utf-8"))
            link = download_link(result.get("link"))
            self.event(
                "browser_exited",
                task=task,
                success=bool(link),
                seconds=round(time.monotonic() - started, 3),
            )
            if not link:
                raise HTTPFailure("browser_download_failed")
            candidate = load_state(paths["candidate"])
            save_private(self.directory / "browser-session.json", candidate)
            # Licensed requests never trigger an additional unlicensed download.
            if licensed:
                return link
            candidate_session = new_session(candidate)
            try:
                verified_link = await request_link(candidate_session, candidate, url)
                if urlsplit(verified_link).path != urlsplit(link).path:
                    link = None
                    raise HTTPFailure("browser_http_file_mismatch")
                candidate["cookies"] = export_cookies(candidate_session.cookies.jar)
                save_private(self.path, candidate)
            except BaseException:
                await candidate_session.close()
                raise
            previous = self.session
            self.session, self.state = candidate_session, candidate
            if previous:
                await previous.close()
            self.event("session_refreshed", task=task, purpose=purpose)
            return True if purpose == "refresh" else link
        except Exception as exc:
            self.event(
                "browser_or_refresh_failed",
                task=task,
                purpose=purpose,
                error=type(exc).__name__,
                reason=getattr(exc, "reason", "worker_error"),
                browser_link_received=bool(link),
            )
            if purpose == "refresh":
                await self.alert("[ENVATO] Nightly refresh failed; previous session retained.")
            return False if purpose == "refresh" else link
        finally:
            if process and process.returncode is None:
                await stop_child(process)
            for path in paths.values():
                path.unlink(missing_ok=True)
            self.event("browser_cleanup_finished", task=task, purpose=purpose)


def schedule_refresh(scheduler, downloader):
    scheduler.add_job(
        downloader.refresh_session,
        "cron",
        hour=5,
        minute=15,
        timezone="Europe/Minsk",
        id="envato-nightly-refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )


async def maintenance():
    async with EnvatoHTTPDownloader() as downloader:
        return await downloader.refresh_session()


if __name__ == "__main__":
    if sys.argv[1:] != ["--refresh"]:
        sys.exit("Usage: python -m media_bot.utils.envato_utils.http_downloader --refresh")
    sys.exit(0 if asyncio.run(maintenance()) else 1)
