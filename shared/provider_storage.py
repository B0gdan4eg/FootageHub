"""Keep provider credentials outside application images."""
import os
from pathlib import Path


def cookie_directory(provider: str, fallback: str) -> str:
    root = os.getenv("PROVIDER_COOKIE_ROOT")
    path = Path(root) / provider if root else Path(fallback)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
