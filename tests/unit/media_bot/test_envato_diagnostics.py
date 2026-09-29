import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from media_bot.utils.envato_utils import envato_playwright as browser
from media_bot.utils.envato_utils.asset_identity import describe_requested
from media_bot.utils.envato_utils.browser_http import BrowserHTTP
from media_bot.utils.envato_utils.envato_playwright import EnvatoDownloader
from media_bot.utils.envato_utils.http_downloader import PROBE_URL, modern_asset

UUID_A = modern_asset(PROBE_URL)[1]
UUID_B = "2d884f9d-9cff-4bc6-be7d-3cfdb247c4f3"
URL_B = f"https://app.envato.com/video-templates/{UUID_B}"


def make_browser_page(identifier, *, title="", content="", link=None):
    attrs = {
        "data-analytics-item_id": identifier,
        "data-analytics-item_type": "video-templates",
    }
    button = SimpleNamespace(get_attribute=AsyncMock(side_effect=lambda n: attrs.get(n)))
    handlers = {}
    page = SimpleNamespace(
        url=PROBE_URL,
        route=AsyncMock(),
        goto=AsyncMock(),
        close=AsyncMock(),
        screenshot=AsyncMock(),
        wait_for_selector=AsyncMock(return_value=button),
        wait_for_url=AsyncMock(),
        title=AsyncMock(return_value=title),
        content=AsyncMock(return_value=content),
        on=Mock(side_effect=lambda name, handler: handlers.update({name: handler})),
    )

    async def click(*args, **kwargs):
        if link:
            page.handlers["response"](
                SimpleNamespace(
                    url=(
                        "https://app.envato.com/download.data"
                        f"?itemUuid={identifier}&itemType=video-templates"
                    ),
                    status=200,
                    json=AsyncMock(return_value=[{"url": link}]),
                    request=SimpleNamespace(all_headers=AsyncMock(return_value={})),
                )
            )
            await asyncio.sleep(0)
        else:
            await handlers["download"](
                SimpleNamespace(url="https://example.test/file", cancel=AsyncMock())
            )

    page.click = AsyncMock(side_effect=click)
    button.click = page.click
    button.evaluate = AsyncMock()
    page.button = button
    page.handlers = handlers
    return page


class ClassifyTests(unittest.TestCase):
    def test_cloudflare_markers(self):
        self.assertEqual(
            browser.classify_static_failure(
                "https://app.envato.com/x", "Just a moment...", "Verifying you are human"
            ),
            "cloudflare_challenge",
        )

    def test_auth_markers(self):
        self.assertEqual(
            browser.classify_static_failure(
                "https://app.envato.com/login", "Login", "Subscribe to download"
            ),
            "auth_required",
        )

    def test_not_found_markers(self):
        self.assertEqual(
            browser.classify_static_failure(
                "https://app.envato.com/x", "404", "This page could not find it"
            ),
            "item_unavailable",
        )

    def test_plain_timeout_is_not_cloudflare(self):
        self.assertEqual(
            browser.classify_static_failure("https://app.envato.com/x", "Item", "<html/>"), ""
        )

    def test_describe_requested_has_no_secrets(self):
        modern = describe_requested(PROBE_URL)
        self.assertEqual(modern["uuid"], UUID_A)
        legacy = describe_requested("https://elements.envato.com/item-ABCDE")
        self.assertEqual(legacy["legacy_id"], "ABCDE")
        self.assertEqual(describe_requested("https://evil.test/")["format"], "invalid")


class ItemButtonDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_with_cloudflare_content_reports_challenge(self):
        from playwright.async_api import TimeoutError as PwTimeout

        page = SimpleNamespace(
            url=PROBE_URL,
            route=AsyncMock(),
            goto=AsyncMock(),
            close=AsyncMock(),
            screenshot=AsyncMock(),
            wait_for_selector=AsyncMock(side_effect=PwTimeout("timeout")),
            wait_for_url=AsyncMock(),
            title=AsyncMock(return_value="Just a moment..."),
            content=AsyncMock(return_value="Verifying you are human"),
            on=Mock(),
        )
        d = EnvatoDownloader()
        d.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
        d._notify_manual_check = AsyncMock()
        with patch.object(browser.logger, "error", new_callable=AsyncMock):
            self.assertIsNone(await d.get_download_url(PROBE_URL, task_id="task1"))
        self.assertEqual(d.last_failure, "item_button_cloudflare_challenge")
        d._notify_manual_check.assert_awaited_once()

    async def test_timeout_without_markers_is_not_cloudflare(self):
        from playwright.async_api import TimeoutError as PwTimeout

        page = SimpleNamespace(
            url=PROBE_URL,
            route=AsyncMock(),
            goto=AsyncMock(),
            close=AsyncMock(),
            screenshot=AsyncMock(),
            wait_for_selector=AsyncMock(side_effect=PwTimeout("timeout")),
            wait_for_url=AsyncMock(),
            title=AsyncMock(return_value="Item page"),
            content=AsyncMock(return_value="<html>loading</html>"),
            on=Mock(),
        )
        d = EnvatoDownloader()
        d.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
        d._notify_manual_check = AsyncMock()
        with patch.object(browser.logger, "error", new_callable=AsyncMock):
            self.assertIsNone(await d.get_download_url(PROBE_URL, task_id="task2"))
        self.assertEqual(d.last_failure, "item_button_timeout")
        d._notify_manual_check.assert_not_awaited()

    async def test_identity_mismatch_never_clicks(self):
        page = make_browser_page(UUID_B)
        d = EnvatoDownloader()
        d.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
        with patch.object(browser.logger, "error", new_callable=AsyncMock):
            self.assertIsNone(await d.get_download_url(PROBE_URL, task_id="task3"))
        self.assertEqual(d.last_failure, "identity_mismatch")
        page.click.assert_not_awaited()


class ParallelIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_tasks_do_not_mix_items(self):
        link_a = "https://video-downloads.elements.envatousercontent.com/files/1/a.zip"
        link_b = "https://video-downloads.elements.envatousercontent.com/files/2/b.zip"
        page_a = make_browser_page(UUID_A, link=link_a)
        page_b = make_browser_page(UUID_B, link=link_b)
        # Rewrite page B URL/identity to URL_B request
        page_b.url = URL_B

        d = EnvatoDownloader()
        calls = {"n": 0}

        async def new_page():
            calls["n"] += 1
            return page_a if calls["n"] == 1 else page_b

        d.context = SimpleNamespace(new_page=new_page, cookies=AsyncMock(return_value=[]))
        with patch.object(browser.logger, "error", new_callable=AsyncMock):
            res_a, res_b = await asyncio.gather(
                d.get_download_url(PROBE_URL, task_id="aaa"),
                d.get_download_url(URL_B, task_id="bbb"),
            )
        self.assertEqual(res_a, link_a)
        self.assertEqual(res_b, link_b)


class RestartSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_restart_deferred_while_active(self):
        from media_bot.utils.envato_utils.test_env import LinkProcessor

        lp = LinkProcessor(max_workers=1, restart_after=1)
        lp.envato_http_enabled = False
        lp.envato_request_count = 5
        lp.envato_downloader = SimpleNamespace(
            __aexit__=AsyncMock(), active_tasks=AsyncMock(return_value=0)
        )
        await lp._enter("envato")
        with patch("media_bot.utils.envato_utils.test_env.EnvatoDownloader") as factory:
            factory.return_value.__aenter__ = AsyncMock()
            await lp._restart_envato_browser_if_needed()
            factory.assert_not_called()
        await lp._leave("envato")

    async def test_manager_restart_reports_busy(self):
        from media_bot.utils.envato_utils.test_env import LinkProcessor

        lp = LinkProcessor(max_workers=1, restart_after=50)
        lp.envato_http_enabled = False
        lp.envato_downloader = SimpleNamespace(__aexit__=AsyncMock())
        await lp._enter("envato")
        ok, status = await lp.restart_envato_now()
        self.assertFalse(ok)
        self.assertEqual(status, "busy")
        await lp._leave("envato")


class BrowserHTTPFreshLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_signed_link_each_time_and_no_link_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            c = BrowserHTTP(directory)
            await c.remember(
                "https://elements.envato.com/item-ABCDE",
                ("video-templates", UUID_A),
                {"Accept": "*/*"},
                [{"name": "a", "value": "v", "domain": ".envato.com", "path": "/"}],
            )
            signed = (
                "https://video-downloads.elements.envatousercontent.com/files/1/a.zip?token=one"
            )
            c.session = SimpleNamespace(cookies=SimpleNamespace(jar=[]), close=AsyncMock())
            with (
                patch(
                    "media_bot.utils.envato_utils.browser_http.new_session",
                    return_value=c.session,
                ),
                patch(
                    "media_bot.utils.envato_utils.browser_http.request_link",
                    new_callable=AsyncMock,
                    return_value=signed,
                ) as req,
                patch(
                    "media_bot.utils.envato_utils.browser_http.export_cookies",
                    return_value=[],
                ),
            ):
                self.assertEqual(
                    await c.get("https://elements.envato.com/item-ABCDE", task_id="t1"),
                    signed,
                )
                self.assertEqual(
                    await c.get("https://elements.envato.com/item-ABCDE", task_id="t2"),
                    signed,
                )
                self.assertEqual(req.await_count, 2)
            from pathlib import Path as _Path

            self.assertNotIn("token=one", _Path(c.path).read_text())


if __name__ == "__main__":
    unittest.main()
