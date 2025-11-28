import asyncio
import json
import os
import time
from playwright.async_api import async_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "..", "envato_utils", "envato_cookies.json")


class EnvatoDownloaderDebug:
    """
    Debug version of Envato downloader with headless=False for manual testing.
    Records all user interactions for automation script.
    """

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.recorded_actions = []

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        # headless=False for debugging - you can see browser actions
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()

        if not os.path.exists(COOKIE_FILE):
            raise FileNotFoundError(f"Cookies file not found: {COOKIE_FILE}")

        with open(COOKIE_FILE, "r") as f:
            await self.context.add_cookies(json.load(f))

        return self

    async def __aexit__(self, *args):
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                print(f"⚠️ Error closing context: {e}")

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                print(f"⚠️ Error closing browser: {e}")

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                print(f"⚠️ Error stopping playwright: {e}")

    async def manual_download_with_recording(self, asset_url: str):
        """
        Opens the page and waits for you to manually click all buttons.
        Records all network requests to find the download URL pattern.
        """
        page = None
        client = None

        try:
            page = await self.context.new_page()

            # Enable CDP session for network monitoring
            client = await self.context.new_cdp_session(page)
            await client.send("Network.enable")

            captured_responses = []
            all_requests = []

            def on_request(event):
                """Record all requests"""
                url = event.get("request", {}).get("url", "")
                method = event.get("request", {}).get("method", "")
                all_requests.append({"url": url, "method": method})

            def on_response(event):
                """Record responses that might contain download URL"""
                url = event.get("response", {}).get("url", "")
                if "download" in url.lower() or "license" in url.lower():
                    captured_responses.append(event)
                    print(f"🔍 [RECORD] Captured response: {url[:80]}...")

            client.on("Network.requestWillBeSent", on_request)
            client.on("Network.responseReceived", on_response)

            # Navigate to asset page
            print(f"\n{'='*70}")
            print(f"🌐 [MANUAL] Opening page: {asset_url}")
            print(f"{'='*70}\n")
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=30000)
            print("✅ [MANUAL] Page loaded")

            print("\n" + "="*70)
            print("👆 [MANUAL MODE] Now YOU do the following:")
            print("="*70)
            print("1. Click the DOWNLOAD button")
            print("2. Check any checkboxes if needed")
            print("3. Click 'Download WITH license' button")
            print("4. Wait for download to start or complete")
            print("5. Press Enter in this console when done")
            print("="*70 + "\n")

            # Wait for user input
            await asyncio.get_event_loop().run_in_executor(
                None,
                input,
                "Press ENTER when you've finished all clicks... "
            )

            print("\n📊 [RECORD] Analyzing captured data...")

            # Try to find download URL in captured responses
            download_url = None
            for i, resp in enumerate(captured_responses):
                try:
                    body = await client.send("Network.getResponseBody", {"requestId": resp["requestId"]})
                    data = json.loads(body["body"])

                    # Try different paths where download URL might be
                    url = (
                        data.get("data", {}).get("attributes", {}).get("downloadUrl") or
                        data.get("downloadUrl") or
                        data.get("url")
                    )

                    if url and ("download" in url or "elements.envato.com" in url):
                        print(f"\n✅ [FOUND] Download URL in response #{i+1}:")
                        print(f"   URL: {url[:100]}...")
                        print(f"   Full response structure:")
                        print(f"   {json.dumps(data, indent=2)[:500]}...\n")
                        if not download_url:
                            download_url = url
                except Exception as e:
                    continue

            # Print all captured requests for analysis
            print(f"\n📋 [RECORD] Total requests captured: {len(all_requests)}")
            print("🔍 [RECORD] Requests with 'download' or 'license' in URL:")
            for req in all_requests:
                if "download" in req["url"].lower() or "license" in req["url"].lower():
                    print(f"   {req['method']} {req['url'][:80]}...")

            # Print summary
            print(f"\n{'='*70}")
            print("📊 [SUMMARY]")
            print(f"{'='*70}")
            print(f"Total captured responses: {len(captured_responses)}")
            print(f"Total requests: {len(all_requests)}")
            if download_url:
                print(f"✅ Found download URL: {download_url[:80]}...")
            else:
                print("❌ No download URL found in responses")
            print(f"{'='*70}\n")

            # Save recorded actions to file for analysis
            record_file = os.path.join(os.path.dirname(__file__), "recorded_actions.json")
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump({
                    "url": asset_url,
                    "captured_responses_count": len(captured_responses),
                    "all_requests": all_requests[-50:],  # Last 50 requests
                    "download_url": download_url
                }, f, indent=2, ensure_ascii=False)

            print(f"💾 [RECORD] Saved recording to: {record_file}\n")

            return download_url

        except Exception as e:
            print(f"❌ [ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            # Keep browser open a bit longer so you can see the result
            print("⏸️  [DEBUG] Keeping browser open for 10 seconds...")
            await asyncio.sleep(10)

            # Close CDP session first
            if client:
                try:
                    await client.detach()
                except Exception:
                    pass

            # Then close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def get_download_url_with_license(self, asset_url: str) -> str | None:
        """
        AUTOMATED version: Get direct download URL WITH license using CDP network interception.
        Based on manual recording findings:
        - Radio button: input[type="radio"][name="project-list-radio-button-item"]
        - License button: button[data-testid='add-download-button']
        - API endpoint: download_and_license_to_workspace.json
        """
        page = None
        client = None
        start_time = time.time()
        download_url = None

        try:
            page = await self.context.new_page()

            # Enable CDP session for network monitoring
            client = await self.context.new_cdp_session(page)
            await client.send("Network.enable")

            captured_responses = []

            def on_response(event):
                url = event.get("response", {}).get("url", "")
                if "download_and_license" in url or "video-downloads.elements.envatousercontent.com" in url:
                    captured_responses.append(event)
                    print(f"🔍 [AUTO] Captured response: {url[:80]}...")

            client.on("Network.responseReceived", on_response)

            # Navigate to asset page
            print(f"🌐 [AUTO] Opening page: {asset_url[:60]}...")
            await page.goto(asset_url, wait_until="domcontentloaded", timeout=30000)
            print("✅ [AUTO] Page loaded")

            # Step 1: Click download button to open modal
            print("🖱️  [AUTO] Step 1: Clicking download button...")
            await page.click("button[data-testid='button-download']", timeout=15000)
            await asyncio.sleep(1)  # Wait for modal to appear

            # Step 2: Click radio button to select project
            print("🖱️  [AUTO] Step 2: Selecting project (radio button)...")
            await page.click("input[type='radio'][name='project-list-radio-button-item']", timeout=15000)
            await asyncio.sleep(0.5)  # Wait for button to become enabled

            # Step 3: Click "Download with license" button
            print("🖱️  [AUTO] Step 3: Clicking 'Лицензировать и скачать' button...")
            await page.click("button[data-testid='add-download-button']", timeout=15000)

            # Step 4: Wait for download URL from intercepted network responses
            print("⏳ [AUTO] Step 4: Waiting for download URL...")
            download_url = await self._wait_for_download_url_from_license(client, captured_responses, timeout=10)

            elapsed = time.time() - start_time

            if download_url:
                print(f"✅ [AUTO] SUCCESS! Got download URL in {elapsed:.2f} sec")
                print(f"🔗 [AUTO] URL: {download_url[:80]}...")
            else:
                print(f"❌ [AUTO] FAILED - No URL received in {elapsed:.2f} sec")

            return download_url

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ [AUTO] ERROR: {e}")
            print(f"⏱️  [AUTO] {elapsed:.2f} sec")
            import traceback
            traceback.print_exc()
            return None

        finally:
            # Keep browser open for debugging
            print("⏸️  [AUTO] Keeping browser open for 10 seconds...")
            await asyncio.sleep(10)

            # Close CDP session first
            if client:
                try:
                    await client.detach()
                except Exception:
                    pass

            # Then close the page
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def _wait_for_download_url_from_license(self, client, captured_responses, timeout=10) -> str | None:
        """
        Wait for download URL to appear in intercepted network responses.
        Specifically looks for download_and_license API response.
        """
        start = time.time()
        while time.time() - start < timeout:
            for resp in captured_responses:
                try:
                    body = await client.send("Network.getResponseBody", {"requestId": resp["requestId"]})
                    data = json.loads(body["body"])

                    # Look for download URL in response body
                    url = (
                        data.get("data", {}).get("attributes", {}).get("downloadUrl") or
                        data.get("downloadUrl") or
                        data.get("url")
                    )

                    if url and ("video-downloads.elements.envatousercontent.com" in url or "download" in url):
                        print(f"✅ [FOUND] Download URL in API response!")
                        return url
                except Exception:
                    continue
            await asyncio.sleep(0.1)
        return None


async def test_manual_recording(asset_url: str):
    """
    Manual test - you click all buttons, script records everything.
    """
    print("="*70)
    print("🧪 [TEST] MANUAL RECORDING MODE")
    print("="*70)
    print(f"🔗 URL: {asset_url}\n")
    print("You will click all buttons manually.")
    print("The script will record all network activity.\n")

    async with EnvatoDownloaderDebug() as downloader:
        result = await downloader.manual_download_with_recording(asset_url)

        if result:
            print("\n" + "="*70)
            print(f"✅ [TEST] SUCCESS! Found download URL:")
            print(f"🔗 {result}")
            print("="*70)
        else:
            print("\n" + "="*70)
            print(f"⚠️  [TEST] No URL found automatically")
            print(f"Check recorded_actions.json for analysis")
            print("="*70)

        return result


async def test_automated_with_license(asset_url: str):
    """
    Automated test - script clicks all buttons automatically WITH license.
    """
    print("="*70)
    print("🤖 [TEST] AUTOMATED MODE - WITH LICENSE")
    print("="*70)
    print(f"🔗 URL: {asset_url}\n")
    print("Script will click all buttons automatically.")
    print("Browser will open in visible mode so you can watch.\n")

    async with EnvatoDownloaderDebug() as downloader:
        result = await downloader.get_download_url_with_license(asset_url)

        if result:
            print("\n" + "="*70)
            print(f"🎉 [TEST] AUTOMATED SUCCESS!")
            print(f"✅ Download URL obtained WITH license:")
            print(f"🔗 {result}")
            print("="*70)
        else:
            print("\n" + "="*70)
            print(f"❌ [TEST] AUTOMATED FAILED")
            print(f"No download URL received")
            print("="*70)

        return result


if __name__ == "__main__":
    # URL for testing
    test_url = "https://elements.envato.com/ru/breathtaking-valley-nature-landscape-YFR4FBV"

    # Choose test mode
    print("\n" + "="*70)
    print("ENVATO LICENSE DOWNLOAD TESTER")
    print("="*70)
    print("\nChoose test mode:")
    print("1. MANUAL - You click buttons, script records (for debugging)")
    print("2. AUTOMATED - Script clicks everything (test automation)")
    print("="*70)

    mode = input("\nEnter choice (1 or 2): ").strip()

    if mode == "1":
        print(f"\n🚀 Starting MANUAL RECORDING test\n")
        print("Browser will open in visible mode.")
        print("You will click all buttons manually.")
        print("Script will record everything for automation.\n")
        result = asyncio.run(test_manual_recording(test_url))

        if result:
            print(f"\n💾 To download the file use:\nwget '{result}' -O filename.zip")
        else:
            print(f"\n📋 Check 'recorded_actions.json' for analysis")
            print("We'll use this data to create the automation script")

    elif mode == "2":
        print(f"\n🤖 Starting AUTOMATED test WITH LICENSE\n")
        print("Browser will open in visible mode.")
        print("Script will automatically click all buttons.")
        print("Watch the browser to verify the automation.\n")
        result = asyncio.run(test_automated_with_license(test_url))

        if result:
            print(f"\n💾 To download the file use:\nwget '{result}' -O filename.zip")
            print("\n✅ Automation works! Ready to move to production.")
        else:
            print(f"\n❌ Automation failed. Check the console output for errors.")

    else:
        print("\n❌ Invalid choice. Please run again and select 1 or 2.")