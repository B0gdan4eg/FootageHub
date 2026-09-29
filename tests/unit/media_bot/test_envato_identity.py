import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from media_bot.utils.envato_utils.asset_identity import checked_identity
from media_bot.utils.envato_utils.browser_http import BrowserHTTP
from media_bot.utils.envato_utils.http_downloader import download_link

UUID = "6e39616e-15cb-46c4-b9ed-dbe7a8404b4c"
URL = f"https://app.envato.com/stock-video/{UUID}"
OLD = "https://elements.envato.com/hospital-hands-and-doctor-with-patient-signing-and-5UJ38NW"
LINK = f"https://video-downloads.elements.envatousercontent.com/076d9f49-07de-48ba-8978-f4a0fac67f0c/3374259.mov?item_id={UUID}"


class IdentityTests(unittest.TestCase):
    def test_stock_video_cdn_format(self):
        self.assertEqual(download_link([LINK], expected_item=UUID), LINK)

    def test_other_item_link_rejected(self):
        self.assertIsNone(download_link([LINK], expected_item="other"))

    def test_button_must_belong_to_current_page(self):
        with self.assertRaises(ValueError):
            checked_identity(OLD, URL, "stock-video", "other")

    def test_modern_redirect_cannot_change_item(self):
        with self.assertRaises(ValueError):
            checked_identity(
                URL, URL.replace(UUID, "6235b645-a723-4a5e-a456-184be6035b9c"), "stock-video", UUID
            )

    def test_old_redirect_stays_same_item(self):
        with self.assertRaises(ValueError):
            checked_identity(OLD, OLD.replace("5UJ38NW", "F5WR8EM"), None, None)

    def test_valid_redirect_identity(self):
        self.assertEqual(checked_identity(OLD, URL, "stock-video", UUID), ("stock-video", UUID))


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_asset_does_not_send_guess(self):
        with tempfile.TemporaryDirectory() as directory:
            c = BrowserHTTP(directory)
            with patch(
                "media_bot.utils.envato_utils.browser_http.request_link", new_callable=AsyncMock
            ) as request:
                self.assertIsNone(await c.get(OLD))
            request.assert_not_awaited()

    async def test_remember_only_verified_identity_and_no_signed_link(self):
        with tempfile.TemporaryDirectory() as directory:
            c = BrowserHTTP(directory)
            await c.remember(
                OLD,
                ("stock-video", UUID),
                {"Cookie": "secret", "Accept": "*/*"},
                [{"name": "auth", "value": "cookie", "domain": ".envato.com", "path": "/"}],
            )
            self.assertEqual(c.state["mappings"][OLD], URL)
            self.assertNotIn("cookie", c.state["headers"])
            restored = BrowserHTTP(directory)
            self.assertEqual(restored.state["mappings"][OLD], URL)
            self.assertNotIn(LINK, Path(c.path).read_text())

    async def test_http_error_returns_to_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            c = BrowserHTTP(directory)
            c.state = {"mappings": {OLD: URL}, "cookies": []}
            session = AsyncMock()
            c.session = session
            with patch(
                "media_bot.utils.envato_utils.browser_http.request_link",
                new_callable=AsyncMock,
                side_effect=RuntimeError,
            ):
                self.assertIsNone(await c.get(OLD))
            session.close.assert_awaited_once()
            self.assertIsNone(c.session)
