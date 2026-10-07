"""Validate user-supplied asset addresses before browser navigation."""
from urllib.parse import urlsplit

HOSTS = {
    "envato": {"elements.envato.com"},
    "freepik": {"freepik.com", "www.freepik.com"},
    "motion": {"motionarray.com", "www.motionarray.com"},
}


def validate_asset_url(url, platform):
    if not isinstance(url, str) or len(url) > 4096 or any(ord(char) < 32 for char in url):
        raise ValueError("Invalid asset URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid asset URL") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS.get(platform, set())
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or not parsed.path.strip("/")
    ):
        raise ValueError("Only HTTPS asset URLs from the selected provider are allowed")
    return url
