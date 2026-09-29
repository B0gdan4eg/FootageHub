"""HTTP-first Freepik downloads with a bounded browser fallback and nightly refresh."""

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import time
from http.cookiejar import Cookie, CookieJar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from curl_cffi.requests import AsyncSession, Cookies

from .logger import logger as admin_logger

log = logging.getLogger(__name__)
PROBE_URL = "https://www.freepik.com/free-photo/young-student-learning-library_21138972.htm"
ALLOWED_HOSTS = {"www.freepik.com", "freepik.com", "www.magnific.com", "magnific.com"}
RESOURCE_HOSTS = ALLOWED_HOSTS | {
    language + "." + root
    for language in (
        "ru",
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "br",
        "pl",
        "nl",
        "ja",
        "jp",
        "ko",
        "kr",
    )
    for root in ("freepik.com", "magnific.com")
}
HEADER_NAMES = {
    "accept",
    "accept-language",
    "user-agent",
    "referer",
    "origin",
    "sec-fetch-dest",
    "sec-fetch-mode",
    "sec-fetch-site",
}


class HTTPFailure(RuntimeError):
    def __init__(self, reason, status=0):
        super().__init__(reason)
        self.reason, self.status = reason, status


def state_directory():
    return Path(os.environ.get("FREEPIK_STATE_DIR", Path(__file__).parent / ".session"))


def asset_parts(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in RESOURCE_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Unsupported Freepik resource URL")
    match = re.search(r"_(\d+)(?:\.html?)?/?$", parsed.path)
    if not match:
        raise ValueError("Freepik resource ID missing")
    return match[1], urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def first_party(domain):
    domain = domain.lstrip(".").lower()
    return any(
        domain == root or domain.endswith("." + root) for root in ("freepik.com", "magnific.com")
    )


def clean_headers(headers):
    return {
        k.lower(): str(v)
        for k, v in headers.items()
        if k.lower() in HEADER_NAMES or k.lower().startswith("sec-ch-ua")
    }


def validate_state(state):
    endpoint = urlsplit(state["endpoint"])
    if (
        state.get("version") != 1
        or endpoint.scheme != "https"
        or endpoint.hostname not in ALLOWED_HOSTS
        or endpoint.username
        or endpoint.password
        or endpoint.port not in (None, 443)
        or endpoint.path != "/api/regular/download"
        or endpoint.query
        or endpoint.fragment
        or not isinstance(state.get("wallet_id"), str)
        or not state["wallet_id"]
        or not isinstance(state.get("cookies"), list)
        or not state["cookies"]
    ):
        raise ValueError("Invalid Freepik session")
    if any(not first_party(c["domain"]) for c in state["cookies"]):
        raise ValueError("Unexpected cookie domain")
    return state


def save_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".session-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def load_state(path):
    with Path(path).open(encoding="utf-8") as stream:
        return validate_state(json.load(stream))


def cookie_jar(cookies):
    jar = CookieJar()
    for c in cookies:
        expires = c.get("expires", -1)
        expires = int(expires) if expires and expires > 0 else None
        jar.set_cookie(
            Cookie(
                version=0,
                name=c["name"],
                value=c["value"],
                port=None,
                port_specified=False,
                domain=c["domain"],
                domain_specified=c["domain"].startswith("."),
                domain_initial_dot=c["domain"].startswith("."),
                path=c.get("path", "/"),
                path_specified=True,
                secure=c.get("secure", True),
                expires=expires,
                discard=expires is None,
                comment=None,
                comment_url=None,
                rest={"HttpOnly": None} if c.get("httpOnly") else {},
                rfc2109=False,
            )
        )
    return jar


def export_cookies(jar):
    jar.clear_expired_cookies()
    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": c.secure,
            "expires": c.expires or -1,
            "httpOnly": c.has_nonstandard_attr("HttpOnly"),
        }
        for c in jar
        if first_party(c.domain)
    ]


def download_link(data):
    if not isinstance(data, dict):
        return None
    for key in ("url", "signedUrl"):
        value = data.get(key)
        if isinstance(value, str):
            parsed = urlsplit(value)
            if (
                parsed.scheme == "https"
                and not parsed.username
                and not parsed.password
                and parsed.port in (None, 443)
                and (
                    parsed.hostname == "videocdn.cdnpk.net"
                    or re.fullmatch(
                        r"downloads(?:cdn\d*)?\.(?:freepik|magnific)\.com", parsed.hostname or ""
                    )
                )
            ):
                return value
    return None


async def request_link(session, state, asset_url):
    resource, referer = asset_parts(asset_url)
    path = urlsplit(asset_url).path
    if not path.endswith(".htm") or re.search(r"/(?:premium|free)-video/", path):
        raise HTTPFailure("browser_only_resource")
    # Freepik resource pages currently redirect to the endpoint's canonical host.
    referer = urlunsplit(urlsplit(referer)._replace(netloc=urlsplit(state["endpoint"]).netloc))
    headers = clean_headers(state.get("headers", {}))
    # Document-navigation metadata causes the API to return a JS challenge.
    headers.update(
        {
            "accept": "application/json",
            "referer": referer,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
    )
    body = bytearray()

    def collect(chunk):
        if len(body) + len(chunk) > 1024 * 1024:
            raise ValueError("Freepik response too large")
        body.extend(chunk)

    response = await session.get(
        state["endpoint"],
        params={
            "resource": resource,
            "action": "download",
            "walletId": state["wallet_id"],
            "locale": state.get("locale", "en"),
        },
        headers=headers,
        timeout=12,
        allow_redirects=False,
        content_callback=collect,
    )
    if (
        response.status_code != 200
        or "json" not in response.headers.get("content-type", "").lower()
    ):
        raise HTTPFailure("security_check_or_http_error", response.status_code)
    link = download_link(json.loads(body))
    if not link:
        raise HTTPFailure("missing_file_link", response.status_code)
    return link


def new_session(state):
    return AsyncSession(
        impersonate="chrome150",
        default_headers=False,
        cookies=cookie_jar(state["cookies"]),
        max_clients=1,
    )


async def stop_child(process):
    """Kill only this refresh worker and its owned browser tree, including on timeout."""
    import psutil

    try:
        parent = psutil.Process(process.pid)
        owned = parent.children(recursive=True) + [parent]
        for child in owned:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        await asyncio.to_thread(psutil.wait_procs, owned, timeout=5)
    except psutil.NoSuchProcess:
        pass
    await process.wait()


class FreepikHTTPDownloader:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else state_directory()
        self.path = self.directory / "session.json"
        self.state = None
        self.session = None
        self.lock = asyncio.Lock()
        self.last_alert = 0
        self.events = log

    def event(self, event, *, level=logging.INFO, **fields):
        self.events.log(level, json.dumps({"event": event, "time": time.time(), **fields}))

    async def __aenter__(self):
        try:
            log_dir = self.directory / "logs"
            log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            name = hashlib.sha256(str(log_dir.resolve()).encode()).hexdigest()[:12]
            self.events = logging.getLogger(__name__ + "." + name)
            self.events.setLevel(logging.INFO)
            if not self.events.handlers:
                handler = RotatingFileHandler(
                    log_dir / "downloads.jsonl",
                    maxBytes=5 * 1024 * 1024,
                    backupCount=3,
                    encoding="utf-8",
                    delay=True,
                )
                handler.setFormatter(logging.Formatter("%(message)s"))
                self.events.addHandler(handler)
        except OSError:
            log.warning("Freepik file logging unavailable; using container logs")
        # Startup never launches Chrome. Bootstrap is an explicit maintenance command.
        try:
            self.state = load_state(self.path)
            self.session = new_session(self.state)
        except (OSError, ValueError, KeyError, TypeError):
            self.event("session_unavailable", level=logging.WARNING)
        self.event(
            "started", session_ready=bool(self.session), refresh_hour=5, timezone="Europe/Minsk"
        )
        return self

    async def __aexit__(self, *args):
        async with self.lock:
            if self.session:
                await self.session.close()
                self.session = None
            for handler in self.events.handlers[:]:
                if isinstance(handler, RotatingFileHandler):
                    handler.close()
                    self.events.removeHandler(handler)

    async def alert(self, message):
        log.error(message)
        if not self.last_alert or time.monotonic() - self.last_alert > 3600:
            self.last_alert = time.monotonic()
            await admin_logger.error(message)

    async def get_download_url(self, asset_url):
        try:
            resource, asset_url = asset_parts(asset_url)
        except (ValueError, TypeError):
            self.event("invalid_resource", level=logging.WARNING)
            return None
        started = time.monotonic()
        async with self.lock:
            try:
                if not self.session or not self.state:
                    raise HTTPFailure("session_unavailable")
                link = await request_link(self.session, self.state, asset_url)
                updated = {
                    **self.state,
                    "cookies": export_cookies(self.session.cookies.jar),
                    "updated_at": time.time(),
                }
                # Persist rotating Set-Cookie values after each successful response.
                self.state = updated
                try:
                    save_private(self.path, updated)
                except OSError:
                    await self.alert(
                        "[FREEPIK] Cannot persist updated cookies; check session storage."
                    )
                self.event(
                    "http_success", resource=resource, seconds=round(time.monotonic() - started, 3)
                )
                return link
            except Exception as exc:
                if self.session and self.state:
                    self.session.cookies = Cookies(cookie_jar(self.state["cookies"]))
                self.event(
                    "http_failed",
                    level=logging.WARNING,
                    resource=resource,
                    error=type(exc).__name__,
                    reason=getattr(exc, "reason", "request_error"),
                    status=getattr(exc, "status", 0),
                    seconds=round(time.monotonic() - started, 3),
                )
            # The same lock bounds browser count to one and protects cookie promotion.
            link = await self._browser_run(asset_url, purpose="fallback")
            if not link:
                await self.alert(
                    "[FREEPIK] HTTP and browser download failed. See Freepik download logs."
                )
            self.event(
                "download_finished",
                resource=resource,
                method="browser",
                success=bool(link),
                seconds=round(time.monotonic() - started, 3),
            )
            return link

    async def refresh_session(self):
        async with self.lock:
            return bool(await self._browser_run(PROBE_URL, purpose="refresh"))

    async def _browser_run(self, asset_url, purpose):
        started = time.monotonic()
        resource, _ = asset_parts(asset_url)
        self.event("browser_started", purpose=purpose, resource=resource)
        candidate_path = self.directory / "candidate.json"
        snapshot_path = self.directory / "refresh-input.json"
        result_path = self.directory / "browser-result.json"
        process = None
        stage = "browser"
        browser_link = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            browser_state = self.state or {}
            try:
                saved_browser = load_state(self.directory / "browser-session.json")
                if saved_browser.get("updated_at", 0) > browser_state.get("updated_at", 0):
                    browser_state = saved_browser
            except (OSError, ValueError, KeyError, TypeError):
                pass
            save_private(snapshot_path, {"state": browser_state, "asset_url": asset_url})
            candidate_path.unlink(missing_ok=True)
            result_path.unlink(missing_ok=True)
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "media_bot.utils.freepik_utils.refresh_session",
                str(self.directory.resolve()),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            await asyncio.wait_for(process.wait(), timeout=85 if purpose == "fallback" else 150)
            if process.returncode:
                raise RuntimeError("Browser refresh failed")
            if result_path.exists():
                with result_path.open(encoding="utf-8") as stream:
                    browser_link = download_link(json.load(stream))
            self.event(
                "browser_exited",
                purpose=purpose,
                resource=resource,
                success=bool(browser_link),
                seconds=round(time.monotonic() - started, 3),
            )
            if not candidate_path.exists() and browser_link and purpose == "fallback":
                self.event("browser_success", resource=resource, session_updated=False)
                return browser_link
            candidate = load_state(candidate_path)
            if browser_link:
                # Retain authenticated browser cookies even if HTTP is still challenged.
                save_private(self.directory / "browser-session.json", candidate)
            stage = "HTTP verification after browser exit"
            candidate_session = new_session(candidate)
            try:
                await request_link(candidate_session, candidate, PROBE_URL)
                candidate["cookies"] = export_cookies(candidate_session.cookies.jar)
                save_private(self.path, candidate)
            except BaseException:
                await candidate_session.close()
                raise
            previous = self.session
            self.session, self.state = candidate_session, candidate
            if previous:
                await previous.close()
            self.event("session_refreshed", purpose=purpose, cookies=len(candidate["cookies"]))
            return browser_link if purpose == "fallback" else True
        except Exception as exc:
            self.event(
                "browser_or_refresh_failed",
                level=logging.WARNING,
                purpose=purpose,
                stage=stage,
                resource=resource,
                error=type(exc).__name__,
                browser_link_received=bool(browser_link),
                seconds=round(time.monotonic() - started, 3),
            )
            if purpose == "refresh":
                await self.alert(
                    "[FREEPIK] Nightly session refresh failed; previous session retained."
                )
            # A valid browser link is still delivered if HTTP session validation failed.
            return browser_link if purpose == "fallback" else False
        finally:
            if process and process.returncode is None:
                await stop_child(process)
            candidate_path.unlink(missing_ok=True)
            snapshot_path.unlink(missing_ok=True)
            result_path.unlink(missing_ok=True)
            self.event("browser_cleanup_finished", purpose=purpose)


def schedule_refresh(scheduler, downloader):
    scheduler.add_job(
        downloader.refresh_session,
        "cron",
        hour=5,
        minute=0,
        timezone="Europe/Minsk",
        id="freepik-nightly-refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )


async def maintenance():
    async with FreepikHTTPDownloader() as downloader:
        return await downloader.refresh_session()


if __name__ == "__main__":
    if sys.argv[1:] != ["--refresh"]:
        sys.exit("Usage: python -m media_bot.utils.freepik_utils.http_downloader --refresh")
    sys.exit(0 if asyncio.run(maintenance()) else 1)
