"""Item identity validation independent of the HTTP-first feature flag."""

import re
from urllib.parse import urlsplit
from uuid import UUID


def modern_asset(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname != "app.envato.com" or p.username or p.password:
        return None
    match = re.fullmatch(r"/(?:search/)?([a-z0-9-]+)/([a-fA-F0-9-]{36})/?", p.path)
    if not match:
        return None
    try:
        return match[1], str(UUID(match[2]))
    except ValueError:
        return None


def legacy_asset(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname != "elements.envato.com":
        return None
    match = re.search(r"-([A-Z0-9]{5,12})/?$", p.path)
    return match[1] if match else None


def checked_identity(requested_url, page_url, item_type, item_id):
    requested, current = modern_asset(requested_url), modern_asset(page_url)
    if requested and current and requested != current:
        raise ValueError("Envato page identity mismatch")
    if current:
        if (item_type, item_id) != current:
            raise ValueError("Envato button identity mismatch")
        return current
    if requested or item_id or item_type:
        raise ValueError("Envato page identity unavailable")
    old = legacy_asset(requested_url)
    if not old or old != legacy_asset(page_url):
        raise ValueError("Envato legacy identity mismatch")
    return None


def describe_requested(url):
    """Short non-secret label for diagnostics: format + UUID/legacy id only."""
    try:
        modern = modern_asset(url)
    except Exception:
        modern = None
    if modern:
        return {"format": "modern", "type": modern[0], "uuid": modern[1]}
    try:
        legacy = legacy_asset(url)
    except Exception:
        legacy = None
    if legacy:
        return {"format": "legacy", "legacy_id": legacy}
    return {"format": "invalid"}
