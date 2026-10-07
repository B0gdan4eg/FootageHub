"""Authorized Envato browser fallback with task-local identity and bounded retries."""
import asyncio
import json
import logging
import os
import time
from urllib.parse import urlencode, urlsplit

import nodriver as uc
import nodriver.cdp as cdp

from media_bot.utils.freepik_utils.freepik import find_chromium_executable

from .asset_identity import checked_identity, describe_requested
from .browser_http import BrowserHTTP
from .envato_playwright import EnvatoDownloader as PlaywrightDownloader
from .envato_playwright import (
    _get_profile_lock,
    _new_task_id,
    _profile_dir_for,
    classify_static_failure,
    get_next_cookie_file,
    missing_seed_cookies,
)
from .http_downloader import asset_url, download_link

log = logging.getLogger(__name__)


class BrowserFailure(Exception):
    def __init__(self, reason, status=0):
        self.reason, self.status = reason, status
        super().__init__(reason)


def cookie_dict(cookie):
    return dict(
        name=cookie.name,
        value=cookie.value,
        domain=cookie.domain,
        path=cookie.path,
        secure=cookie.secure,
        httpOnly=cookie.http_only,
        expires=cookie.expires,
    )


class EnvatoDownloader(PlaywrightDownloader):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._slots = asyncio.Semaphore(2)
        self._licensed_lock = asyncio.Lock()

    def event(self, task, stage, started, **fields):
        log.info(
            "Envato nodriver %s",
            json.dumps(
                dict(task=task, stage=stage, seconds=round(time.monotonic() - started, 3), **fields)
            ),
        )

    async def cookies(self):
        return [cookie_dict(c) for c in await self.browser.cookies.get_all()]

    async def browser_healthy(self):
        if not self.browser:
            return False
        try:
            await asyncio.wait_for(self.browser.main_tab.send(cdp.browser.get_version()), timeout=3)
            return True
        except Exception:
            return False

    async def __aenter__(self):
        self.cookie_file = self.cookie_file or get_next_cookie_file()
        self.profile_dir = self.profile_override or _profile_dir_for(self.cookie_file)
        self._profile_lock = _get_profile_lock(self.profile_dir)
        await asyncio.wait_for(self._profile_lock.acquire(), timeout=60)
        self._lock_acquired = True
        try:
            self.browser = await asyncio.wait_for(
                uc.start(
                    headless=False,
                    sandbox=False,
                    user_data_dir=self.profile_dir,
                    browser_executable_path=find_chromium_executable(),
                ),
                timeout=30,
            )
            tab = await self.browser.get("about:blank")
            seed = self.seed_cookies
            if seed is None:
                with open(self.cookie_file, encoding="utf-8") as stream:
                    seed = json.load(stream)
                seed = missing_seed_cookies(seed, await self.cookies())
            for cookie in seed:
                await tab.send(
                    cdp.network.set_cookie(
                        name=cookie["name"],
                        value=cookie["value"],
                        domain=cookie["domain"],
                        path=cookie.get("path", "/"),
                        secure=cookie.get("secure", False),
                        http_only=cookie.get("httpOnly", False),
                    )
                )
            directory = os.getenv("ENVATO_BROWSER_HTTP_STATE_DIR", self.profile_dir)
            self.http_fast = BrowserHTTP(
                os.path.join(directory, os.path.basename(self.cookie_file))
            )
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, *args):
        try:
            if self.http_fast:
                await self.http_fast.close()
            if self.browser:
                try:
                    await asyncio.wait_for(
                        self.browser.main_tab.send(cdp.browser.close()), timeout=5
                    )
                except Exception:
                    pass
                self.browser.stop()
                await asyncio.sleep(0.5)
        finally:
            self.browser = None
            if self._lock_acquired:
                self._profile_lock.release()
                self._lock_acquired = False

    async def snapshot(self, tab):
        value = await asyncio.wait_for(
            tab.evaluate(
                """JSON.stringify({
          url:location.href,title:document.title,text:document.body?.innerText.slice(0,2500),
          buttons:[...document.querySelectorAll("button[data-cy='idp-download-button'],button[data-testid='button-download']")]
          .filter(b=>b.getClientRects().length).map(b=>({id:b.getAttribute('data-analytics-item_id'),type:b.getAttribute('data-analytics-item_type')}))
        })"""
            ),
            timeout=4,
        )
        return json.loads(value)

    async def attempt(self, url, task, attempt, started):
        tab = None
        phase = "navigation"
        status = 0
        headers = {}
        challenge_response = False
        try:
            tab = await asyncio.wait_for(self.browser.get("about:blank", new_tab=True), timeout=8)
            await tab.send(cdp.network.enable())

            def response(event):
                nonlocal status, challenge_response
                parsed = urlsplit(event.response.url)
                if event.type_ == cdp.network.ResourceType.DOCUMENT and parsed.hostname in (
                    "app.envato.com",
                    "elements.envato.com",
                ):
                    status = int(event.response.status)
                    challenge_response = event.response.headers.get("cf-mitigated") == "challenge"

            def request(event):
                parsed = urlsplit(event.request.url)
                if parsed.hostname == "app.envato.com" and parsed.path == "/download.data":
                    headers.update(event.request.headers)

            tab.add_handler(cdp.network.ResponseReceived, response)
            tab.add_handler(cdp.network.RequestWillBeSent, request)
            await asyncio.wait_for(tab.get(url), timeout=15)
            phase = "identity"
            deadline = time.monotonic() + 18
            identity = None
            last_reason = ""
            waited = time.monotonic()
            while time.monotonic() < deadline:
                info = await self.snapshot(tab)
                last_reason = classify_static_failure(
                    info["url"], info["title"], info.get("text") or ""
                )
                if last_reason in ("auth_required", "item_unavailable"):
                    raise BrowserFailure(last_reason, status)
                # Give the normal browser check a short opportunity to finish, then
                # retry internally with a fresh navigation rather than failing the user.
                if (
                    last_reason == "cloudflare_challenge" or challenge_response
                ) and time.monotonic() - waited > 5:
                    raise BrowserFailure("cloudflare_challenge", status)
                if len(info["buttons"]) == 1:
                    button = info["buttons"][0]
                    try:
                        identity = checked_identity(url, info["url"], button["type"], button["id"])
                    except ValueError:
                        # A legacy page may be in the middle of its genuine redirect.
                        if urlsplit(info["url"]).hostname == "app.envato.com":
                            raise BrowserFailure("identity_mismatch", status)
                    if identity:
                        break
                await asyncio.sleep(0.25)
            if not identity:
                raise BrowserFailure(last_reason or "identity_unavailable", status)
            self.event(
                task,
                phase,
                started,
                attempt=attempt,
                item=identity[1],
                item_type=identity[0],
                status=status,
            )
            phase = "download_response"
            query = urlencode(
                {
                    "itemUuid": identity[1],
                    "itemType": identity[0],
                    "_routes": "routes/download/route",
                }
            )
            fetch_call = "fetch(" + json.dumps("/download.data?" + query)
            response_script = (
                ",{credentials:'include'}).then(async r=>JSON.stringify({status:r.status,"
                "mime:r.headers.get('content-type'),challenge:r.headers.get('cf-mitigated'),"
                "body:await r.text()}))"
            )
            expression = fetch_call + response_script
            value = await asyncio.wait_for(tab.evaluate(expression, await_promise=True), timeout=12)
            data = json.loads(value)
            status = data["status"]
            if data.get("challenge") == "challenge":
                raise BrowserFailure("cloudflare_challenge", status)
            if status in (401,):
                raise BrowserFailure("auth_required", status)
            if status in (404, 410):
                raise BrowserFailure("item_unavailable", status)
            if status != 200:
                raise BrowserFailure("download_http_error", status)
            try:
                link = download_link(json.loads(data["body"]), expected_item=identity[1])
            except (ValueError, TypeError):
                raise BrowserFailure("download_invalid_response", status)
            if not link:
                raise BrowserFailure("download_missing_verified_link", status)
            headers["user-agent"] = await asyncio.wait_for(
                tab.evaluate("navigator.userAgent"), timeout=3
            )
            try:
                await asyncio.wait_for(
                    self.http_fast.remember(
                        url, identity, headers, await self.cookies(), task_id=task
                    ),
                    timeout=4,
                )
            except Exception as exc:
                self.event(task, "cache_save_failed", started, error=type(exc).__name__)
            self.event(
                task, phase, started, attempt=attempt, item=identity[1], status=status, success=True
            )
            return link, identity
        except asyncio.TimeoutError:
            raise BrowserFailure(phase + "_timeout", status)
        finally:
            if tab:
                try:
                    await asyncio.wait_for(tab.close(), timeout=3)
                except Exception:
                    pass

    async def get_download_url(self, url, task_id=None):
        task = task_id or _new_task_id()
        started = time.monotonic()
        requested = describe_requested(url)
        reason = "request_timeout"
        await self._track_start()
        try:
            url = asset_url(url)
            async with asyncio.timeout(85):
                link = await self.http_fast.get(url, task_id=task)
                if link:
                    self.event(task, "http_success", started, requested=requested)
                    await self._record_result(True, time.monotonic() - started)
                    return link
                async with self._slots:
                    for attempt in range(1, 4):
                        try:
                            link, item = await self.attempt(url, task, attempt, started)
                            self.last_asset, self.last_failure = item, None
                            await self._record_result(True, time.monotonic() - started)
                            self.event(
                                task,
                                "finished",
                                started,
                                attempt=attempt,
                                requested=requested,
                                success=True,
                            )
                            return link
                        except BrowserFailure as exc:
                            reason = exc.reason
                            self.event(
                                task,
                                "attempt_failed",
                                started,
                                attempt=attempt,
                                reason=reason,
                                status=exc.status,
                                requested=requested,
                            )
                            retryable = {
                                "cloudflare_challenge",
                                "navigation_timeout",
                                "identity_timeout",
                                "identity_unavailable",
                                "download_response_timeout",
                                "download_http_error",
                            }
                            if reason not in retryable or attempt == 3:
                                break
                            await asyncio.sleep(1)
        except asyncio.TimeoutError:
            reason = "request_timeout"
        except Exception as exc:
            reason = type(exc).__name__
        finally:
            await self._track_finish()
        self.last_failure = reason
        await self._record_result(False, time.monotonic() - started)
        self.event(task, "finished", started, reason=reason, requested=requested, success=False)
        if reason in ("cloudflare_challenge", "auth_required", "request_timeout"):
            await self._notify_manual_check(task, reason, requested)
        return None

    async def get_download_url_with_license(self, url, task_id=None):
        # Keep the established licensed flow, using a separate persistent profile
        # and current cookies so it cannot close another task's browser.
        async with self._licensed_lock:
            async with PlaywrightDownloader(
                cookie_file=self.cookie_file,
                profile_dir=self.profile_dir + "-licensed",
                cookies=await self.cookies(),
            ) as downloader:
                return await downloader.get_download_url_with_license(url, task_id=task_id)
