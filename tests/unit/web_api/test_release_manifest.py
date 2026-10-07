"""Reject incomplete or mutable releases before any server mutation."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.parametrize("failure", ["migration", "health"])
def test_failed_release_restores_configuration_and_retained_images(tmp_path, monkeypatch, failure):
    root = tmp_path / "server"
    incoming = tmp_path / "incoming"
    root.mkdir()
    incoming.mkdir()
    original = "services: original-production-config\n"
    (root / "docker-compose.yml").write_text(original)
    (root / ".env").write_text("PRIVATE=retained\n")
    (incoming / "docker-compose.yml").write_text("services: new-config\n")
    (incoming / "release.json").write_text(json.dumps(manifest()))
    for provider in ["envato", "freepik", "motion"]:
        folder = root / "provider-cookies" / provider
        folder.mkdir(parents=True)
        (folder / "cookies.json").write_text("[]")
    (root / "browser-profiles" / "freepik").mkdir(parents=True)
    commands = []

    def output(args, **kwargs):
        commands.append(args)
        if args[:2] == ("docker", "inspect"):
            return json.dumps([{"Mounts": [], "State": {"Health": {"Status": "healthy"}}}])
        if args[:3] == ("docker", "image", "inspect"):
            return "a" * 40 if "org.opencontainers" in args[-1] else "sha256:" + "c" * 64
        if "psql" in args:
            return "old" if failure == "migration" else "head"
        if "compose" in args and "run" in args:
            return "head"
        return ""

    def run(args, **kwargs):
        commands.append(args)
        if "pg_dump" in args:
            kwargs["stdout"].write(b"simulated backup")
        return SimpleNamespace(returncode=0)

    def unhealthy(*args, **kwargs):
        raise RuntimeError("unhealthy release")

    monkeypatch.setattr(release.subprocess, "check_output", output)
    monkeypatch.setattr(release.subprocess, "run", run)
    monkeypatch.setattr(release.urllib.request, "urlopen", unhealthy)
    monkeypatch.setattr(release.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError):
        release.deploy(root, incoming)
    assert (root / "docker-compose.yml").read_text() == original
    assert (root / ".env").read_text() == "PRIVATE=retained\n"
    assert "rollback-" in (root / ".release.env").read_text()
    assert not (root / "deployed-release.json").exists()
    recreation = [
        command
        for command in commands
        if "compose" in command and "up" in command and "frontend" in command
    ]
    assert len(recreation) == (2 if failure == "health" else 0)
    assert all("postgres" not in command for command in recreation)
    database_updates = [
        command
        for command in commands
        if "compose" in command and "up" in command and "postgres" in command
    ]
    assert len(database_updates) == (2 if failure == "health" else 0)


def test_browser_cleanup_preserves_sessions_and_symlink_targets(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    target = tmp_path / "private-session.json"
    target.write_text("preserved")
    lock = profile / "SingletonLock"
    try:
        lock.symlink_to(target)
    except OSError:
        pytest.skip("Windows symlink creation requires Developer Mode")
    (profile / "Cookies").write_text("browser-cookie-storage")
    release.clear_browser_locks(profile)
    assert not lock.is_symlink()
    assert target.read_text() == "preserved"
    assert (profile / "Cookies").read_text() == "browser-cookie-storage"
