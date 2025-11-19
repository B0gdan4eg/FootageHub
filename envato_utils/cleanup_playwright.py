"""
Utility script to cleanup Playwright temporary files and cache.
Run this periodically on the server to prevent disk space issues.
"""
import os
import shutil
import tempfile
from pathlib import Path


def get_playwright_dirs():
    """Find all Playwright-related temporary directories"""
    temp_dir = Path(tempfile.gettempdir())

    # Common Playwright temp directory patterns
    patterns = [
        "playwright*",
        "playwright_*",
        "chromium*",
        ".playwright-*",
    ]

    playwright_dirs = []
    for pattern in patterns:
        playwright_dirs.extend(temp_dir.glob(pattern))

    return playwright_dirs


def get_dir_size(path):
    """Calculate directory size in MB"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry.path)
    except (PermissionError, FileNotFoundError):
        pass
    return total / (1024 * 1024)  # Convert to MB


def cleanup_playwright_cache():
    """Remove Playwright temporary directories"""
    print("🔍 Searching for Playwright temporary directories...")

    playwright_dirs = get_playwright_dirs()

    if not playwright_dirs:
        print("✅ No Playwright cache directories found")
        return

    total_size = 0
    removed_count = 0

    for dir_path in playwright_dirs:
        try:
            size_mb = get_dir_size(dir_path)
            total_size += size_mb

            print(f"   🗑️  Removing: {dir_path.name} ({size_mb:.2f} MB)")
            shutil.rmtree(dir_path, ignore_errors=True)
            removed_count += 1

        except Exception as e:
            print(f"   ⚠️  Failed to remove {dir_path.name}: {e}")

    print(f"\n✅ Cleanup complete:")
    print(f"   Removed: {removed_count} directories")
    print(f"   Freed: {total_size:.2f} MB")


def show_disk_usage():
    """Show current disk usage"""
    try:
        import psutil
        disk = psutil.disk_usage('/')
        print(f"\n💾 Disk Usage:")
        print(f"   Total: {disk.total / (1024**3):.2f} GB")
        print(f"   Used: {disk.used / (1024**3):.2f} GB ({disk.percent}%)")
        print(f"   Free: {disk.free / (1024**3):.2f} GB")
    except ImportError:
        print("\n💾 Install psutil to see disk usage: pip install psutil")


if __name__ == "__main__":
    print("="*70)
    print("🧹 Playwright Cache Cleanup Tool")
    print("="*70)

    show_disk_usage()
    cleanup_playwright_cache()
    show_disk_usage()

    print("\n" + "="*70)
    print("💡 Recommendation: Run this script periodically (e.g., via cron)")
    print("   Example cron: 0 */6 * * * /path/to/python cleanup_playwright.py")
    print("="*70)
