"""Explicit engine selection; rollback keeps the previous browser available."""
import os


def EnvatoDownloader(**kwargs):
    if os.getenv("ENVATO_BROWSER_ENGINE", "playwright") == "nodriver":
        from .nodriver_downloader import EnvatoDownloader as Downloader
    else:
        from .envato_playwright import EnvatoDownloader as Downloader
    return Downloader(**kwargs)
