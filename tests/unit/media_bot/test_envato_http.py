import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from curl_cffi.requests import Cookies

from media_bot.utils.envato_utils import http_downloader as http

LINK = "https://video-downloads.elements.envatousercontent.com/files/123/test.zip?token=secret"
LEGACY = "https://elements.envato.com/world-cup-bento-JLEY2QK"


def state():
    return {
        "version": 1,
        "account": "envato_cookies_2.json",
        "headers": {},
        "cookies": [
            {
                "name": "auth",
                "value": "secret-cookie",
                "domain": ".envato.com",
                "path": "/",
                "expires": -1,
                "secure": True,
                "httpOnly": True,
            }
        ],
        "mappings": {},
        "updated_at": 1,
    }


class FormatTests(unittest.TestCase):
    def test_asset_formats(self):
        self.assertEqual(http.asset_url(LEGACY + "?tracking=x"), LEGACY)
        self.assertEqual(
            http.modern_asset(http.PROBE_URL),
            http.modern_asset(http.PROBE_URL.replace("/video-", "/search/video-")),
        )
        self.assertEqual(
            http.modern_asset(http.PROBE_URL)[1], "4671289c-05c0-481b-a1b7-98165fbe61c2"
        )

    def test_invalid_asset(self):
        for value in (
            "https://evil.test/abc-ABCDE",
            "https://app.envato.com/login",
            "http://elements.envato.com/file-ABCDE",
            "https://u@app.envato.com/video-templates/4671289c-05c0-481b-a1b7-98165fbe61c2",
            "https://elements.envato.com:8080/file-ABCDE",
            "https://elements.envato.com.evil.test/file-ABCDE",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                http.asset_url(value)

    def test_reference_table_is_data_not_executable(self):
        self.assertEqual(http.download_link([{"_1": 2}, "url", LINK]), LINK)
        self.assertIsNone(http.download_link("alert('hello')"))
        self.assertIsNone(http.download_link([LINK, LINK.replace("test.zip", "other.zip")]))

    def test_untrusted_download_hosts(self):
        for link in (
            LINK.replace("https:", "http:"),
            LINK.replace(".com/", ".com.evil.test/"),
            LINK.replace("https://", "https://user@"),
            "https://app.envato.com/login",
        ):
            self.assertIsNone(http.download_link(link))

    def test_cookie_roundtrip_and_filter(self):
        self.assertEqual(
            http.export_cookies(http.cookie_jar(state()["cookies"])), state()["cookies"]
        )
        self.assertFalse(http.first_party("envato.com.evil.test"))

    def test_invalid_state(self):
        for key, value in (
            ("account", "../secret.json"),
            ("version", 2),
            ("cookies", []),
            ("mappings", {LEGACY: "https://evil.test/x"}),
        ):
            s = state()
            s[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                http.validate_state(s)

    def test_schedule(self):
        async def _refresh():
            return True

        scheduler = AsyncIOScheduler()
        http.schedule_refresh(scheduler, SimpleNamespace(refresh_session=_refresh))
        job = scheduler.get_job("envato-nightly-refresh")
        self.assertEqual(str(job.trigger.timezone), "Europe/Minsk")
        self.assertEqual(str(job.trigger.fields[5]), "5")
        self.assertEqual(str(job.trigger.fields[6]), "15")


class RequestTests(unittest.IsolatedAsyncioTestCase):
    async def response(self, url, **kwargs):
        kwargs["content_callback"](json.dumps([{"url": LINK}]).encode())
        return SimpleNamespace(
            status_code=200, headers={"content-type": "text/x-script; charset=utf-8"}
        )

    async def test_request_uses_requested_uuid(self):
        session = SimpleNamespace(get=AsyncMock(side_effect=self.response))
        self.assertEqual(await http.request_link(session, state(), http.PROBE_URL), LINK)
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "https://app.envato.com/download.data")
        self.assertEqual(kwargs["params"]["itemUuid"], http.modern_asset(http.PROBE_URL)[1])
        self.assertFalse(kwargs["allow_redirects"])

    async def test_unknown_legacy_requires_browser(self):
        session = SimpleNamespace(get=AsyncMock())
        with self.assertRaises(http.HTTPFailure):
            await http.request_link(session, state(), LEGACY)
        session.get.assert_not_awaited()

    async def test_verified_mapping(self):
        s = state()
        s["mappings"][LEGACY] = http.PROBE_URL
        session = SimpleNamespace(get=AsyncMock(side_effect=self.response))
        self.assertEqual(await http.request_link(session, s, LEGACY), LINK)

    async def test_security_page_not_a_file(self):
        session = SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(status_code=200, headers={"content-type": "text/html"})
            )
        )
        with self.assertRaises(http.HTTPFailure):
            await http.request_link(session, state(), http.PROBE_URL)

    async def test_response_limit(self):
        async def huge(url, **kwargs):
            kwargs["content_callback"](b"x" * (1024 * 1024 + 1))

        session = SimpleNamespace(get=AsyncMock(side_effect=huge))
        with self.assertRaises(ValueError):
            await http.request_link(session, state(), http.PROBE_URL)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.d = http.EnvatoHTTPDownloader(self.directory)
        self.d.alert = AsyncMock()

    async def asyncTearDown(self):
        await self.d.__aexit__()
        self.tmp.cleanup()

    async def test_startup_does_not_open_browser(self):
        with patch.object(http.asyncio, "create_subprocess_exec", new_callable=AsyncMock) as spawn:
            await self.d.__aenter__()
        spawn.assert_not_awaited()

    async def test_license_bypasses_http(self):
        self.d._browser_run = AsyncMock(return_value=LINK)
        with patch.object(http, "request_link", new_callable=AsyncMock) as request:
            self.assertEqual(await self.d.get_download_url_with_license(http.PROBE_URL), LINK)
        request.assert_not_awaited()
        self.d._browser_run.assert_awaited_once()
        args, kwargs = self.d._browser_run.await_args
        self.assertEqual(args[:3], (http.PROBE_URL, "fallback", True))

    async def test_fallback_on_failure(self):
        self.d._browser_run = AsyncMock(return_value=LINK)
        self.assertEqual(await self.d.get_download_url(http.PROBE_URL), LINK)
        self.d._browser_run.assert_awaited_once()

    async def test_invalid_resource_never_opens_browser(self):
        self.d._browser_run = AsyncMock()
        self.assertIsNone(await self.d.get_download_url("https://localhost/file"))
        self.d._browser_run.assert_not_awaited()

    async def test_rotating_cookies_persist_and_logs_redacted(self):
        self.d.state = state()
        self.d.session = SimpleNamespace(
            cookies=Cookies(http.cookie_jar(state()["cookies"])), close=AsyncMock()
        )
        self.d.event = events = unittest.mock.Mock()
        with patch.object(http, "request_link", new_callable=AsyncMock, return_value=LINK):
            self.assertEqual(await self.d.get_download_url(http.PROBE_URL), LINK)
        self.assertEqual(http.load_state(self.d.path)["cookies"], state()["cookies"])
        self.assertNotIn("secret", str(events.call_args_list))

    async def test_failed_refresh_preserves_session(self):
        http.save_private(self.d.path, state())
        before = self.d.path.read_bytes()
        process = SimpleNamespace(returncode=1, wait=AsyncMock(return_value=1))
        with patch.object(
            http.asyncio, "create_subprocess_exec", new_callable=AsyncMock, return_value=process
        ):
            self.assertFalse(await self.d.refresh_session())
        self.assertEqual(self.d.path.read_bytes(), before)
        self.assertFalse((self.directory / "refresh-input.json").exists())

    async def test_cancel_kills_worker_and_cleans_input(self):
        process = SimpleNamespace(
            returncode=None, wait=AsyncMock(side_effect=asyncio.CancelledError)
        )
        with (
            patch.object(
                http.asyncio, "create_subprocess_exec", new_callable=AsyncMock, return_value=process
            ),
            patch.object(http, "stop_child", new_callable=AsyncMock) as stop,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.d.refresh_session()
        stop.assert_awaited_once_with(process)
        self.assertFalse((self.directory / "refresh-input.json").exists())

    async def test_browser_link_survives_http_failure(self):
        async def spawn(*args, **kwargs):
            http.save_private(self.directory / "candidate.json", state())
            http.save_private(self.directory / "browser-result.json", {"link": LINK})
            return SimpleNamespace(returncode=0, wait=AsyncMock(return_value=0))

        session = SimpleNamespace(close=AsyncMock())
        with (
            patch.object(http.asyncio, "create_subprocess_exec", side_effect=spawn),
            patch.object(http, "new_session", return_value=session),
            patch.object(
                http,
                "request_link",
                new_callable=AsyncMock,
                side_effect=http.HTTPFailure("challenge"),
            ),
        ):
            self.assertEqual(await self.d._browser_run(http.PROBE_URL, "fallback"), LINK)
        session.close.assert_awaited_once()
        self.assertFalse(self.d.path.exists())

    async def test_wrong_file_never_promoted(self):
        async def spawn(*args, **kwargs):
            http.save_private(self.directory / "candidate.json", state())
            http.save_private(self.directory / "browser-result.json", {"link": LINK})
            return SimpleNamespace(returncode=0, wait=AsyncMock(return_value=0))

        session = SimpleNamespace(close=AsyncMock())
        with (
            patch.object(http.asyncio, "create_subprocess_exec", side_effect=spawn),
            patch.object(http, "new_session", return_value=session),
            patch.object(
                http,
                "request_link",
                new_callable=AsyncMock,
                return_value=LINK.replace("test.zip", "other.zip"),
            ),
        ):
            self.assertIsNone(await self.d._browser_run(http.PROBE_URL, "fallback"))
        self.assertFalse(self.d.path.exists())


if __name__ == "__main__":
    unittest.main()
