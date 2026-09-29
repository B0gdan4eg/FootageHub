import asyncio
import unittest
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, mock_open, patch

from media_bot.utils.freepik_utils import freepik
from media_bot.utils.freepik_utils.freepik import FreepikDownloader


class FreepikButtonTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_button_after_hydration(self):
        button = object()
        tab = SimpleNamespace(
            evaluate=AsyncMock(side_effect=[False, False, True]),
            select=AsyncMock(return_value=button),
            find=AsyncMock(),
        )
        result = await FreepikDownloader()._find_button(tab, timeout=2)
        self.assertIs(result, button)
        self.assertEqual(tab.evaluate.await_count, 3)
        tab.select.assert_awaited_once()
        tab.find.assert_not_awaited()

    async def test_retries_when_document_changes_during_selection(self):
        button = object()
        tab = SimpleNamespace(
            evaluate=AsyncMock(return_value=True),
            select=AsyncMock(side_effect=[RuntimeError("document replaced"), button]),
            find=AsyncMock(),
        )
        result = await FreepikDownloader()._find_button(tab, timeout=2)
        self.assertIs(result, button)
        self.assertEqual(tab.select.await_count, 2)

    async def test_missing_button_finishes_without_selecting_unready_node(self):
        tab = SimpleNamespace(
            evaluate=AsyncMock(return_value=False),
            select=AsyncMock(),
            find=AsyncMock(return_value=None),
        )
        result = await FreepikDownloader()._find_button(tab, timeout=0.01)
        self.assertIsNone(result)
        tab.select.assert_not_awaited()

    async def test_click_reuses_ready_button(self):
        downloader = FreepikDownloader()
        downloader._find_button = AsyncMock()
        button = SimpleNamespace(click=AsyncMock())
        self.assertTrue(await downloader._click_download(object(), button=button))
        button.click.assert_awaited_once()
        downloader._find_button.assert_not_awaited()

    async def test_click_refetches_stale_button(self):
        downloader = FreepikDownloader()
        stale = SimpleNamespace(click=AsyncMock(side_effect=RuntimeError("stale node")))
        fresh = SimpleNamespace(click=AsyncMock())
        downloader._find_button = AsyncMock(return_value=fresh)
        tab = object()
        self.assertTrue(await downloader._click_download(tab, button=stale))
        downloader._find_button.assert_awaited_once_with(tab, timeout=5)
        fresh.click.assert_awaited_once()


class FreepikDownloadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.downloader = FreepikDownloader()
        self.commands = []
        self.handlers = defaultdict(list)
        self.unrelated = Mock()
        self.handlers[freepik.cdp.page.DownloadWillBegin].append(self.unrelated)
        self.tab = SimpleNamespace(
            get=AsyncMock(),
            send=AsyncMock(side_effect=lambda command: self.commands.append(next(command))),
            handlers=self.handlers,
            add_handler=lambda event, handler: self.handlers[event].append(handler),
        )
        self.downloader.browser = SimpleNamespace(get=AsyncMock(return_value=self.tab))
        self.downloader._find_button = AsyncMock(return_value=object())
        self.downloader._click_download = AsyncMock(side_effect=self.deliver_download)
        self.url = "https://www.magnific.com/premium-psd/example_123.htm"
        self.direct_url = "https://cdn.example.test/archive.zip"

    async def deliver_download(self, *args, **kwargs):
        for handler in self.handlers[freepik.cdp.page.DownloadWillBegin]:
            handler(SimpleNamespace(url=self.direct_url))
        return True

    async def download(self):
        with patch.object(freepik, "get_next_cookie_file", return_value="cookies.json"), patch(
            "builtins.open", mock_open(read_data="[]")
        ):
            return await self.downloader.get_download_url(self.url + "#fromView=search")

    async def test_immediate_event_and_repeated_download_cleanup(self):
        for _ in range(2):
            self.assertEqual(await self.download(), self.direct_url)
            self.assertEqual(self.handlers[freepik.cdp.page.DownloadWillBegin], [self.unrelated])
            self.assertEqual(self.commands[-1]["method"], "Page.navigate")
            self.assertEqual(self.commands[-1]["params"]["url"], "about:blank")
        self.assertEqual(self.tab.get.await_count, 4)
        for call in self.tab.get.await_args_list:
            self.assertEqual(call.args, (self.url,))

    async def test_event_timeout_still_retries_click(self):
        real_wait_for = asyncio.wait_for
        download_waits = 0

        async def wait_for(awaitable, timeout):
            nonlocal download_waits
            if timeout == 10:
                download_waits += 1
                if download_waits == 1:
                    awaitable.close()
                    raise asyncio.TimeoutError
            return await real_wait_for(awaitable, timeout)

        async def click(*args, **kwargs):
            if self.downloader._click_download.await_count == 2:
                await self.deliver_download()
            return True

        self.downloader._click_download.side_effect = click
        with patch.object(freepik.asyncio, "wait_for", side_effect=wait_for):
            self.assertEqual(await self.download(), self.direct_url)
        self.assertEqual(self.downloader._click_download.await_count, 2)
        self.assertEqual(download_waits, 2)
        self.assertEqual(self.handlers[freepik.cdp.page.DownloadWillBegin], [self.unrelated])


if __name__ == "__main__":
    unittest.main()
