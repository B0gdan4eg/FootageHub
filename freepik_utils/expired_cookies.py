import json
import os
from datetime import datetime, timezone

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "freepik_cookies.json")

def check_cookie_expiry(cookie_file: str):
    if not os.path.exists(cookie_file):
        print(f"❌ Файл {cookie_file} не найден.")
        return

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    now = datetime.now(timezone.utc)
    expired_count = 0

    for cookie in cookies:
        name = cookie.get("name")
        expires = cookie.get("expires")

        if expires:
            exp_time = datetime.fromtimestamp(expires, tz=timezone.utc)
            delta = exp_time - now
            if delta.total_seconds() > 0:
                print(f"✅ Кука '{name}' истекает через {delta}. ({exp_time.isoformat()})")
            else:
                print(f"⚠️ Кука '{name}' уже истекла {abs(delta)} назад. ({exp_time.isoformat()})")
                expired_count += 1
        else:
            print(f"ℹ️ Кука '{name}' не содержит поля 'expires'.")

    print(f"\n📊 Всего куков: {len(cookies)}. Истекших: {expired_count}")

check_cookie_expiry(COOKIE_FILE)
