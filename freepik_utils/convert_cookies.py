#!/usr/bin/env python3
"""
Конвертирует cookies из формата расширения Chrome в формат Playwright
"""
import json
import os

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "freepik_cookies.json")
BACKUP_FILE = os.path.join(os.path.dirname(__file__), "freepik_cookies_backup.json")

def convert_cookies():
    if not os.path.exists(COOKIE_FILE):
        print(f"ERROR: {COOKIE_FILE} not found")
        return

    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    # Backup
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    print(f"Backup created: {BACKUP_FILE}")

    converted = []
    for cookie in cookies:
        playwright_cookie = {
            "name": cookie.get("name", ""),
            "value": cookie.get("value", ""),
            "domain": cookie.get("domain", ".freepik.com"),
            "path": cookie.get("path", "/"),
        }

        # Convert sameSite
        same_site = cookie.get("sameSite", "Lax")
        if same_site in ["Strict", "Lax", "None"]:
            playwright_cookie["sameSite"] = same_site
        else:
            playwright_cookie["sameSite"] = "Lax"

        # Convert expires - Chrome extension uses expirationDate
        if "expirationDate" in cookie:
            playwright_cookie["expires"] = int(cookie["expirationDate"])
        elif "expires" in cookie and cookie["expires"] != -1:
            playwright_cookie["expires"] = int(cookie["expires"])

        # Add flags
        if "httpOnly" in cookie:
            playwright_cookie["httpOnly"] = bool(cookie["httpOnly"])
        if "secure" in cookie:
            playwright_cookie["secure"] = bool(cookie["secure"])

        converted.append(playwright_cookie)

    # Save converted
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2)

    print(f"\nConverted {len(converted)} cookies")
    print(f"Saved to: {COOKIE_FILE}")

    # Show important cookies
    important = [c for c in converted if any(x in c["name"].lower() for x in ["session", "auth", "token", "user", "gr_"])]
    if important:
        print(f"\nAuth cookies found:")
        for c in important:
            print(f"  - {c['name']}")
    else:
        print("\nWARNING: No auth cookies found!")
        print("You may not be logged in to Freepik")

if __name__ == "__main__":
    convert_cookies()