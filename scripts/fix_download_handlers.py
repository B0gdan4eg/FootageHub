"""Fix download handlers - replace CRUD calls with Repository methods."""
import re
from pathlib import Path


def fix_file(file_path: Path):
    """Fix a single download handler file."""
    content = file_path.read_text(encoding="utf-8")
    original = content

    # Replace get_user_by_telegram_id
    content = re.sub(
        r"(\s+)user = await get_user_by_telegram_id\(session, telegram_id\)",
        r"\1user_repo = UserRepository(session)\n\1user = await user_repo.get_by_telegram_id(telegram_id)",
        content,
    )

    # Replace create_media
    content = re.sub(
        r"media = await create_media\(session, url=url, file_type=([^)]+)\)",
        r"media_repo = MediaRepository(session)\n            media = await media_repo.get_or_create(url=url, file_type=\1)",
        content,
    )

    # Replace create_download
    content = re.sub(
        r"await create_download\(session, user\.id, media\.id, service_type=([^)]+)\)",
        r"download_repo = DownloadRepository(session)\n            await download_repo.create_download(user_id=user.id, media_id=media.id, service_type=\1)",
        content,
    )

    # Replace get_active_subscription
    content = re.sub(
        r"subscription = await get_active_subscription\(session, user\.id\)",
        r"subscription_repo = SubscriptionRepository(session)\n            subscription = await subscription_repo.get_active_by_user_id(user.id)",
        content,
    )

    # Replace increment_download_count
    content = re.sub(
        r"await increment_download_count\(session, subscription\.id\)",
        r"await subscription_repo.increment_usage(subscription.id)",
        content,
    )

    if content != original:
        file_path.write_text(content, encoding="utf-8")
        print(f"  Fixed: {file_path.name}")
        return True
    return False


def main():
    root = Path(__file__).parent.parent
    handlers_dir = root / "media_bot" / "handlers" / "download"

    files = ["envato.py", "freepik.py", "motion.py"]

    print("Fixing download handlers...")
    for filename in files:
        file_path = handlers_dir / filename
        if file_path.exists():
            if fix_file(file_path):
                print(f"  OK: {filename}")
            else:
                print(f"  SKIP: {filename}")
        else:
            print(f"  NOT FOUND: {filename}")

    print("\nDone!")


if __name__ == "__main__":
    main()
