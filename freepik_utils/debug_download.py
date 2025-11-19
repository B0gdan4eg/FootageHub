import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "freepik_cookies.json")

async def debug_download():
    """Debug what happens when clicking download button"""

    print("="*70)
    print("Debug Freepik Download Process")
    print("="*70)

    async with async_playwright() as p:
        # Use new headless mode (less detectable)
        browser = await p.chromium.launch(
            headless=False,  # Must be False - Freepik detects headless mode. Use Xvfb on server.
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--window-size=1280,720'
            ]
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            ignore_https_errors=True,
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation']
        )

        # Advanced stealth - hide all automation traces
        await context.add_init_script("""
            // Overwrite the `plugins` property to use a custom getter.
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Overwrite the `plugins` property to use a custom getter.
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Overwrite the `plugins` property to use a custom getter.
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Pass the Chrome Test.
            window.chrome = {
                runtime: {}
            };

            // Pass the Permissions Test.
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        # Load cookies
        with open(COOKIE_FILE, "r") as f:
            await context.add_cookies(json.load(f))

        page = await context.new_page()

        # Enable CDP for network monitoring
        client = await context.new_cdp_session(page)
        await client.send("Network.enable")

        all_responses = []

        def on_response(event):
            url = event.get("response", {}).get("url", "")
            status = event.get("response", {}).get("status", 0)
            all_responses.append({
                "url": url,
                "status": status,
                "requestId": event.get("requestId")
            })
            # Print все запросы с download в URL
            if "download" in url.lower():
                print(f"\n[NETWORK] Download URL detected:")
                print(f"  URL: {url}")
                print(f"  Status: {status}")

        client.on("Network.responseReceived", on_response)

        # Navigate to test page
        test_url = "https://www.freepik.com/free-photo/young-student-learning-library_21138972.htm"
        print(f"\nNavigating to: {test_url}")
        await page.goto(test_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        print("\nSearching for download button...")
        try:
            download_btn = await page.wait_for_selector("button[data-cy='download-button']", timeout=10000)
            print("Download button found!")

            # Click and wait
            print("\nClicking download button...")
            await download_btn.click()
            await asyncio.sleep(3)  # Wait for network requests

            print("\n" + "="*70)
            print("CAPTURED NETWORK RESPONSES:")
            print("="*70)

            # Show all responses with 'download' in URL
            download_responses = [r for r in all_responses if "download" in r["url"].lower()]
            print(f"\nFound {len(download_responses)} responses with 'download' in URL:")

            for i, resp in enumerate(download_responses, 1):
                print(f"\n{i}. URL: {resp['url'][:100]}...")
                print(f"   Status: {resp['status']}")

                # Try to get response body
                try:
                    body = await client.send("Network.getResponseBody", {"requestId": resp["requestId"]})
                    print(f"   Body: {body['body'][:200]}...")

                    # Try parse JSON
                    try:
                        data = json.loads(body["body"])
                        print(f"   JSON Keys: {list(data.keys())}")
                        print(f"   JSON: {json.dumps(data, indent=2)[:500]}...")
                    except:
                        print("   Not JSON response")
                except Exception as e:
                    print(f"   Could not get body: {e}")

        except Exception as e:
            print(f"Error: {e}")

        print("\n" + "="*70)
        print("Done!")
        print("="*70)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_download())