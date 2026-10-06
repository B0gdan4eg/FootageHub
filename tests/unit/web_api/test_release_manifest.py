"""Reject incomplete or mutable releases before any server mutation."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "deploy_release", Path(__file__).resolve().parents[3] / "scripts" / "deploy_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def manifest():
    return {
        "revision": "a" * 40,
        "images": {
            service: f"ghcr.io/b0gdan4eg/footagehub-{service}@sha256:{'b' * 64}"
            for service in release.SERVICES
        },
    }


def test_exact_release_accepted():
    release.validate_manifest(manifest())


@pytest.mark.parametrize("invalid", ["latest", "a" * 39, "a" * 40 + ";echo x"])
def test_invalid_revision_rejected(invalid):
    value = manifest()
    value["revision"] = invalid
    with pytest.raises(ValueError):
        release.validate_manifest(value)


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/b0gdan4eg/footagehub-frontend:latest",
        f"ghcr.io/other/footagehub-frontend@sha256:{'b' * 64}",
        f"ghcr.io/b0gdan4eg/footagehub-web-api@sha256:{'b' * 64}",
    ],
)
def test_mutable_or_wrong_image_rejected(image):
    value = manifest()
    value["images"]["frontend"] = image
    with pytest.raises(ValueError):
        release.validate_manifest(value)


def test_partial_release_rejected():
    value = manifest()
    del value["images"]["media-bot"]
    with pytest.raises(ValueError):
        release.validate_manifest(value)
