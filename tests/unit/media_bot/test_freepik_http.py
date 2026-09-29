import asyncio
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from curl_cffi.requests import Cookies

from media_bot.utils.freepik_utils import http_downloader as http


def sample_state():
    return {
        "version": 1,
        "endpoint": "https://www.magnific.com/api/regular/download",
        "wallet_id": "test-wallet",
        "locale": "en",
        "headers": {},
        "cookies": [
            {
                "name": "session",
                "value": "test-secret",
                "domain": ".magnific.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "expires": -1,
            }
        ],
        "refreshed_at": 100,
    }


class StateTests(unittest.TestCase):
    def test_asset_validation(self):
        self.assertEqual(http.asset_parts(http.PROBE_URL + "?x=y#tracking")[0], "21138972")
        for url in (
            "http://www.freepik.com/file_1.htm",
            "https://freepik.com.evil.test/a_1.htm",
            "https://u@freepik.com/a_1.htm",
            "https://freepik.com:8080/a_1.htm",
            "https://127.0.0.1/a_1.htm",
            "https://freepik.com/no-id",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                http.asset_parts(url)

    def test_only_download_cdn_links(self):
        good = "https://downloadscdn5.magnific.com/file.zip?signature=test"
        self.assertEqual(http.download_link({"url": good}), good)
        video = "https://videocdn.cdnpk.net/example.mp4"
        self.assertEqual(http.download_link({"url": video}), video)
        for url in (
            "https://www.magnific.com/login",
            "https://downloadscdn5.magnific.com.evil.test/file",
            "http://downloadscdn5.magnific.com/file",
            "https://localhost/file",
        ):
            self.assertIsNone(http.download_link({"url": url}))

    def test_localized_video_resource(self):
        url = "https://ru.freepik.com/premium-video/example_6236100"
        self.assertEqual(http.asset_parts(url), ("6236100", url))

    def test_cookie_roundtrip_preserves_attributes(self):
        cookies = sample_state()["cookies"]
        self.assertEqual(http.export_cookies(http.cookie_jar(cookies)), cookies)

    def test_atomic_write_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            http.save_private(path, sample_state())
            before = path.read_bytes()
            with patch.object(http.os, "replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    http.save_private(path, {"bad": True})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_rejects_untrusted_state(self):
        state = sample_state()
        state["endpoint"] = "https://example.com/api/regular/download"
        with self.assertRaises(ValueError):
            http.validate_state(state)
        state = sample_state()
        state["cookies"][0]["domain"] = ".example.com"
        with self.assertRaises(ValueError):
            http.validate_state(state)

    def test_no_cookie_or_navigation_headers_in_state(self):
        self.assertEqual(
            http.clean_headers(
                {
                    "Cookie": "secret",
                    "Host": "wrong",
                    "Sec-Fetch-User": "?1",
                    "Accept": "application/json",
                }
            ),
            {"accept": "application/json"},
        )

    def test_schedule_is_daily_minsk_five(self):
        async def _refresh():
            return True

        scheduler = AsyncIOScheduler()
        http.schedule_refresh(scheduler, SimpleNamespace(refresh_session=_refresh))
        job = scheduler.get_job("freepik-nightly-refresh")
        now = datetime(2026, 9, 9, 23, 0, tzinfo=ZoneInfo("Europe/Minsk"))
        self.assertEqual(
            job.trigger.get_next_fire_time(None, now),
            datetime(2026, 9, 10, 5, 0, tzinfo=ZoneInfo("Europe/Minsk")),
        )
        self.assertEqual(job.max_instances, 1)


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = http.FreepikHTTPDownloader(self.temp.name)
        self.client.state = sample_state()
        self.client.session = SimpleNamespace(
            cookies=Cookies(http.cookie_jar(sample_state()["cookies"])), close=AsyncMock()
        )
        self.client.alert = AsyncMock()
        http.save_private(self.client.path, self.client.state)

    async def test_startup_does_not_open_browser_but_missing_session_falls_back(self):
        client = http.FreepikHTTPDownloader(Path(self.temp.name) / "missing")
        with patch.object(asyncio, "create_subprocess_exec") as start:
            async with client:
                client.alert = AsyncMock()
                start.assert_not_called()
                with patch.object(
                    client, "_browser_run", AsyncMock(return_value="browser-link")
                ) as fallback:
                    self.assertEqual(await client.get_download_url(http.PROBE_URL), "browser-link")
                    fallback.assert_awaited_once_with(http.PROBE_URL, purpose="fallback")
            start.assert_not_called()

    async def test_success_persists_rotating_cookies(self):
        self.client.session.cookies.set("rotated", "new", domain=".magnific.com", path="/")
        with patch.object(http, "request_link", AsyncMock(return_value="link")):
            self.assertEqual(await self.client.get_download_url(http.PROBE_URL), "link")
        restored = http.load_state(self.client.path)
        self.assertIn("rotated", [c["name"] for c in restored["cookies"]])
        self.assertEqual(restored["refreshed_at"], 100)

    async def test_failure_retains_state_and_uses_browser_once(self):
        before = self.client.path.read_bytes()
        with (
            patch.object(http, "request_link", AsyncMock(side_effect=RuntimeError("secret"))),
            patch.object(self.client, "_browser_run", AsyncMock(return_value=None)) as fallback,
        ):
            self.assertIsNone(await self.client.get_download_url(http.PROBE_URL))
            fallback.assert_awaited_once_with(http.PROBE_URL, purpose="fallback")
        self.assertEqual(self.client.path.read_bytes(), before)
        self.assertNotIn("secret", self.client.alert.call_args.args[0])

    async def test_invalid_url_never_opens_browser(self):
        with patch.object(self.client, "_browser_run", AsyncMock()) as fallback:
            self.assertIsNone(await self.client.get_download_url("https://example.com/a_1.htm"))
            fallback.assert_not_called()

    async def test_browser_link_survives_session_capture_failure(self):
        link = "https://downloadscdn5.magnific.com/file.zip"

        async def spawn(*args, **kwargs):
            http.save_private(self.client.directory / "browser-result.json", {"url": link})
            return SimpleNamespace(wait=AsyncMock(return_value=0), returncode=0)

        with patch.object(asyncio, "create_subprocess_exec", spawn):
            self.assertEqual(await self.client._browser_run(http.PROBE_URL, "fallback"), link)
        self.assertFalse((self.client.directory / "browser-result.json").exists())

    async def test_logs_do_not_contain_session_secrets(self):
        async with http.FreepikHTTPDownloader(self.temp.name) as client:
            client.alert = AsyncMock()
            with (
                patch.object(
                    http, "request_link", AsyncMock(side_effect=RuntimeError("test-secret"))
                ),
                patch.object(client, "_browser_run", AsyncMock(return_value="private-signed-url")),
            ):
                self.assertEqual(
                    await client.get_download_url(http.PROBE_URL), "private-signed-url"
                )
        content = (Path(self.temp.name) / "logs/downloads.jsonl").read_text(encoding="utf-8")
        self.assertIn("http_failed", content)
        self.assertIn("download_finished", content)
        for secret in ("test-secret", "test-wallet", "private-signed-url"):
            self.assertNotIn(secret, content)

    async def test_storage_error_does_not_discard_valid_download(self):
        before = self.client.path.read_bytes()
        with (
            patch.object(http, "request_link", AsyncMock(return_value="link")),
            patch.object(http, "save_private", side_effect=OSError("disk full")),
        ):
            self.assertEqual(await self.client.get_download_url(http.PROBE_URL), "link")
        self.assertEqual(self.client.path.read_bytes(), before)
        self.client.alert.assert_awaited_once()

    async def test_successful_refresh_replaces_and_closes_old_session(self):
        previous = self.client.session

        async def spawn(*args, **kwargs):
            candidate = sample_state()
            candidate["refreshed_at"] = 200
            http.save_private(self.client.directory / "candidate.json", candidate)
            return SimpleNamespace(wait=AsyncMock(return_value=0), returncode=0)

        candidate_session = SimpleNamespace(
            cookies=Cookies(http.cookie_jar(sample_state()["cookies"])), close=AsyncMock()
        )
        with (
            patch.object(asyncio, "create_subprocess_exec", spawn),
            patch.object(http, "new_session", return_value=candidate_session),
            patch.object(http, "request_link", AsyncMock(return_value="link")),
        ):
            self.assertTrue(await self.client.refresh_session())
        self.assertEqual(http.load_state(self.client.path)["refreshed_at"], 200)
        self.assertIs(self.client.session, candidate_session)
        previous.close.assert_awaited_once()

    async def test_cancelled_refresh_stops_browser_and_preserves_state(self):
        before = self.client.path.read_bytes()
        process = SimpleNamespace(
            wait=AsyncMock(side_effect=asyncio.CancelledError()), returncode=None
        )
        with (
            patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)),
            patch.object(http, "stop_child", AsyncMock()) as stop,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.client.refresh_session()
        stop.assert_awaited_once_with(process)
        self.assertEqual(self.client.path.read_bytes(), before)

    async def test_html_200_is_not_a_download(self):
        session = SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(status_code=200, headers={"content-type": "text/html"})
            )
        )
        with self.assertRaises(RuntimeError):
            await http.request_link(session, sample_state(), http.PROBE_URL)

    async def test_video_does_not_use_image_api(self):
        session = SimpleNamespace(get=AsyncMock())
        with self.assertRaises(http.HTTPFailure) as error:
            await http.request_link(
                session, sample_state(), "https://ru.freepik.com/premium-video/example_6236100"
            )
        self.assertEqual(error.exception.reason, "browser_only_resource")
        session.get.assert_not_called()

    async def test_json_and_fetch_headers(self):
        link = "https://downloadscdn5.magnific.com/file.zip"

        async def get(url, **kwargs):
            self.assertFalse(kwargs["allow_redirects"])
            self.assertEqual(kwargs["headers"]["sec-fetch-dest"], "empty")
            self.assertEqual(kwargs["params"]["resource"], "21138972")
            kwargs["content_callback"](json.dumps({"url": link}).encode())
            return SimpleNamespace(status_code=200, headers={"content-type": "application/json"})

        self.assertEqual(
            await http.request_link(SimpleNamespace(get=get), sample_state(), http.PROBE_URL), link
        )

    async def test_refresh_failure_retains_state_and_removes_temp(self):
        process = SimpleNamespace(wait=AsyncMock(return_value=1), returncode=1)
        before = self.client.path.read_bytes()
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)):
            self.assertFalse(await self.client.refresh_session())
        self.assertEqual(self.client.path.read_bytes(), before)
        self.assertFalse((self.client.directory / "refresh-input.json").exists())

    async def test_refresh_promotes_only_after_http_validation(self):
        async def spawn(*args, **kwargs):
            candidate = sample_state()
            candidate["refreshed_at"] = 200
            http.save_private(self.client.directory / "candidate.json", candidate)
            return SimpleNamespace(wait=AsyncMock(return_value=0), returncode=0)

        candidate_session = SimpleNamespace(
            cookies=Cookies(http.cookie_jar(sample_state()["cookies"])), close=AsyncMock()
        )
        with (
            patch.object(asyncio, "create_subprocess_exec", spawn),
            patch.object(http, "new_session", return_value=candidate_session),
            patch.object(
                http, "request_link", AsyncMock(side_effect=RuntimeError("security check"))
            ),
        ):
            self.assertFalse(await self.client.refresh_session())
        self.assertEqual(http.load_state(self.client.path)["refreshed_at"], 100)
        candidate_session.close.assert_awaited_once()

    async def test_refresh_timeout_stops_owned_process(self):
        process = SimpleNamespace(wait=AsyncMock(side_effect=TimeoutError()), returncode=None)
        with (
            patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)),
            patch.object(http, "stop_child", AsyncMock()) as stop,
        ):
            self.assertFalse(await self.client.refresh_session())
        stop.assert_awaited_once_with(process)


if __name__ == "__main__":
    unittest.main()
