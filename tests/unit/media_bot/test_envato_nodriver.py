import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from media_bot.utils.envato_utils.nodriver_downloader import BrowserFailure, EnvatoDownloader

URL = "https://app.envato.com/stock-video/1111f4fa-5b8c-4734-9582-ff71de6dbef3"
ITEM = ("stock-video", "1111f4fa-5b8c-4734-9582-ff71de6dbef3")
LINK = "https://video-downloads.elements.envatousercontent.com/files/1/file.mov"


class RetryTests(unittest.IsolatedAsyncioTestCase):
    def downloader(self):
        d = EnvatoDownloader()
        d.http_fast = SimpleNamespace(get=AsyncMock(return_value=None))
        d._notify_manual_check = AsyncMock()
        return d

    async def test_challenge_then_success_returns_link_without_error_notification(self):
        d = self.downloader()
        d.attempt = AsyncMock(
            side_effect=[BrowserFailure("cloudflare_challenge", 403), (LINK, ITEM)]
        )
        with patch(
            "media_bot.utils.envato_utils.nodriver_downloader.asyncio.sleep", new_callable=AsyncMock
        ):
            self.assertEqual(await d.get_download_url(URL, task_id="retry-test"), LINK)
        self.assertEqual(d.attempt.await_count, 2)
        self.assertEqual(d.success_count, 1)
        self.assertEqual(d.fail_count, 0)
        d._notify_manual_check.assert_not_awaited()
        self.assertEqual(await d.active_tasks(), 0)

    async def test_repeated_request_uses_fresh_http_link_without_browser(self):
        d = self.downloader()
        d.http_fast.get.side_effect = ["fresh-link-one", "fresh-link-two"]
        d.attempt = AsyncMock()
        self.assertEqual(await d.get_download_url(URL), "fresh-link-one")
        self.assertEqual(await d.get_download_url(URL), "fresh-link-two")
        d.attempt.assert_not_awaited()

    async def test_persistent_challenge_is_bounded_and_alerted_only_after_retries(self):
        d = self.downloader()
        d.attempt = AsyncMock(side_effect=BrowserFailure("cloudflare_challenge", 403))
        with patch(
            "media_bot.utils.envato_utils.nodriver_downloader.asyncio.sleep", new_callable=AsyncMock
        ):
            self.assertIsNone(await d.get_download_url(URL))
        self.assertEqual(d.attempt.await_count, 3)
        d._notify_manual_check.assert_awaited_once()
        self.assertEqual(d.fail_count, 1)

    async def test_wrong_item_and_expired_auth_are_not_retried(self):
        for reason in (
            "identity_mismatch",
            "auth_required",
            "item_unavailable",
            "download_missing_verified_link",
        ):
            d = self.downloader()
            d.attempt = AsyncMock(side_effect=BrowserFailure(reason))
            self.assertIsNone(await d.get_download_url(URL))
            d.attempt.assert_awaited_once()

    async def test_parallel_tasks_keep_their_own_results(self):
        d = self.downloader()

        async def attempt(url, *args):
            await asyncio.sleep(0)
            return "link-for-" + url, ITEM

        d.attempt = attempt
        other = URL.replace(ITEM[1], "0d51145f-fab2-45d2-b683-a7572e06e4b9")
        result = await asyncio.gather(d.get_download_url(URL), d.get_download_url(other))
        self.assertEqual(result, ["link-for-" + URL, "link-for-" + other])

    async def test_cancelled_request_releases_active_tracking(self):
        d = self.downloader()
        d.attempt = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await d.get_download_url(URL)
        self.assertEqual(await d.active_tasks(), 0)


if __name__ == "__main__":
    unittest.main()
