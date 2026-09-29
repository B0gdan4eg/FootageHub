import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from media_bot.utils.envato_utils import envato_playwright as browser
from media_bot.utils.envato_utils.envato_playwright import EnvatoDownloader
from media_bot.utils.envato_utils.http_downloader import PROBE_URL, modern_asset


class ButtonTests(unittest.IsolatedAsyncioTestCase):
    def test_seed_does_not_replace_refreshed_profile_session(self):
        old = {
            "name": "session",
            "domain": ".envato.com",
            "path": "/",
            "value": "old",
            "expires": 200,
        }
        current = dict(old, value="refreshed", expires=300)
        self.assertEqual(browser.missing_seed_cookies([old], [current], now=100), [])
        self.assertEqual(browser.missing_seed_cookies([old], [], now=100), [old])
        self.assertEqual(browser.missing_seed_cookies([old], [], now=250), [])
        self.assertEqual(
            browser.missing_seed_cookies([old], [dict(current, expires=50)], now=100), [old]
        )

    def make_page(self, identifier):
        attrs = {
            "data-analytics-item_id": identifier,
            "data-analytics-item_type": "video-templates",
        }
        button = SimpleNamespace(get_attribute=AsyncMock(side_effect=lambda name: attrs.get(name)))
        handlers = {}
        page = SimpleNamespace(
            url=PROBE_URL,
            route=AsyncMock(),
            goto=AsyncMock(),
            close=AsyncMock(),
            screenshot=AsyncMock(),
            wait_for_selector=AsyncMock(return_value=button),
            on=Mock(side_effect=lambda name, handler: handlers.update({name: handler})),
        )

        async def click(*args, **kwargs):
            await handlers["download"](
                SimpleNamespace(url="https://example.test/file", cancel=AsyncMock())
            )

        page.click = AsyncMock(side_effect=click)
        button.click = page.click
        button.evaluate = AsyncMock()
        page.button = button
        page.handlers = handlers
        return page

    async def test_only_item_detail_button_not_recommendations(self):
        page = self.make_page(modern_asset(PROBE_URL)[1])
        d = EnvatoDownloader()
        d.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
        with (
            patch.object(browser.logger, "error", new_callable=AsyncMock),
            patch.object(browser.asyncio, "sleep", new_callable=AsyncMock),
        ):
            self.assertIsNone(await d.get_download_url(PROBE_URL))
        page.button.click.assert_awaited_once()
        self.assertEqual(d.last_asset, modern_asset(PROBE_URL))
        page.close.assert_awaited_once()

    async def test_wrong_item_is_never_clicked(self):
        page = self.make_page("2d884f9d-9cff-4bc6-be7d-3cfdb247c4f3")
        d = EnvatoDownloader()
        d.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
        with patch.object(browser.logger, "error", new_callable=AsyncMock):
            self.assertIsNone(await d.get_download_url(PROBE_URL))
        page.click.assert_not_awaited()
        self.assertIsNone(d.last_asset)
        page.close.assert_awaited_once()

    async def test_matching_response_works_without_download_event(self):
        identifier = modern_asset(PROBE_URL)[1]
        page = self.make_page(identifier)
        link = (
            "https://video-downloads.elements.envatousercontent.com/files/123/test.zip?token=test"
        )

        async def click(*args, **kwargs):
            page.handlers["response"](
                SimpleNamespace(
                    url=f"https://app.envato.com/download.data?itemUuid={identifier}&itemType=video-templates",
                    status=200,
                    json=AsyncMock(return_value=[{"url": link}]),
                )
            )
            await asyncio.sleep(0)

        page.click = AsyncMock(side_effect=click)
        page.button.click = page.click
        d = EnvatoDownloader()
        d.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
        self.assertEqual(await d.get_download_url(PROBE_URL), link)

    async def test_screenshot_failure_preserves_original_error(self):
        page = self.make_page(modern_asset(PROBE_URL)[1])
        page.goto.side_effect = RuntimeError("navigation failed")
        page.screenshot.side_effect = TimeoutError("screenshot failed")
        d = EnvatoDownloader()
        d.context = SimpleNamespace(new_page=AsyncMock(return_value=page))
        with patch.object(browser.logger, "error", new_callable=AsyncMock) as log:
            self.assertIsNone(await d.get_download_url(PROBE_URL))
        self.assertIn("navigation failed", log.await_args.args[0])
        self.assertEqual(d.last_failure, "navigation_RuntimeError")
        self.assertEqual(page.screenshot.await_args.kwargs["timeout"], 5000)
        page.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
