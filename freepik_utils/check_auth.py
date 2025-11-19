import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "freepik_cookies.json")

async def check_freepik_auth():
    """Check if cookies provide valid authentication to Freepik"""

    if not os.path.exists(COOKIE_FILE):
        print(f"ERROR: Cookie file not found: {COOKIE_FILE}")
        return

    print("="*70)
    print("Checking Freepik authentication")
    print("="*70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False to see what happens
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )

        # Load cookies
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)

        await context.add_cookies(cookies)
        print(f"\nLoaded {len(cookies)} cookies")

        # Show auth-related cookies
        auth_cookies = [c for c in cookies if any(x in c.get('name', '').lower()
                       for x in ['token', 'session', 'auth', 'user', 'gr_'])]
        print(f"\nAuth cookies ({len(auth_cookies)}):")
        for c in auth_cookies:
            print(f"  - {c['name']}: {c['value'][:20]}...")

        page = await context.new_page()

        # Go to main page
        print("\n1. Loading Freepik homepage...")
        await page.goto("https://www.freepik.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Check if logged in by looking for profile/logout elements
        try:
            # Try to find user profile button
            profile_selectors = [
                "button[data-cy='user-button']",
                "a[data-cy='user-button']",
                "[data-testid='user-menu']",
                ".user-menu",
                "button:has-text('Log out')",
                "a:has-text('Log out')"
            ]

            profile_found = False
            for selector in profile_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        print(f"\n✅ LOGGED IN! Found profile element: {selector}")
                        profile_found = True
                        break
                except:
                    continue

            if not profile_found:
                # Check if login button exists (means NOT logged in)
                try:
                    login_btn = await page.wait_for_selector("button:has-text('Log in'), a:has-text('Log in')", timeout=5000)
                    if login_btn:
                        print("\n❌ NOT LOGGED IN - Login button found")
                        print("   You need to login and save cookies again")
                except:
                    pass

            # Try JavaScript check
            is_logged_in = await page.evaluate("""
                () => {
                    // Check for common auth indicators
                    const hasLogout = document.body.innerText.includes('Log out');
                    const hasProfile = document.querySelector('[data-cy*="user"]') !== null;
                    const hasLogin = document.body.innerText.includes('Log in');

                    return {
                        hasLogout,
                        hasProfile,
                        hasLogin,
                        bodyText: document.body.innerText.substring(0, 500)
                    };
                }
            """)

            print(f"\n2. JavaScript check:")
            print(f"   Has 'Log out': {is_logged_in['hasLogout']}")
            print(f"   Has profile element: {is_logged_in['hasProfile']}")
            print(f"   Has 'Log in': {is_logged_in['hasLogin']}")

            if is_logged_in['hasLogout'] or is_logged_in['hasProfile']:
                print("\n✅ RESULT: You are LOGGED IN")
            elif is_logged_in['hasLogin']:
                print("\n❌ RESULT: You are NOT LOGGED IN")
            else:
                print("\n⚠️  RESULT: Cannot determine login status")

        except Exception as e:
            print(f"\n❌ Error checking auth: {e}")

        # Test download button on a free photo
        print("\n3. Testing download button on free photo...")
        test_url = "https://www.freepik.com/free-photo/young-student-learning-library_21138972.htm"
        await page.goto(test_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Check for download button
        try:
            download_btn = await page.wait_for_selector("button[data-cy='download-button']", timeout=10000)
            if download_btn:
                print("   ✅ Download button found!")

                # Check button text
                btn_text = await download_btn.text_content()
                print(f"   Button text: {btn_text}")

                # Try to click
                try:
                    await download_btn.click(timeout=5000)
                    await asyncio.sleep(2)
                    print("   ✅ Download button clicked successfully!")
                    print("   If you can see download modal - authentication works!")
                except Exception as e:
                    print(f"   ⚠️  Could not click: {e}")
            else:
                print("   ❌ Download button not found")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print("\n" + "="*70)
        print("Check the browser window to see if you're logged in")
        print("Press Enter to close...")
        print("="*70)
        input()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_freepik_auth())