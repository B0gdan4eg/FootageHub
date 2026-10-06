"""Deploy a CI-built release by digest, retaining configuration and rollback images."""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

SERVICES = ("media-bot", "ai-bot", "web-api", "frontend")


def validate_manifest(manifest):
    if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("revision", "")):
        raise ValueError("Invalid Git revision")
    if set(manifest.get("images", {})) != set(SERVICES):
        raise ValueError("Release must include all four application images")
    for service, image in manifest["images"].items():
        if not re.fullmatch(
            r"ghcr\.io/b0gdan4eg/footagehub-" + re.escape(service) + r"@sha256:[0-9a-f]{64}", image
        ):
            raise ValueError("Invalid image digest")


def deploy(root, incoming):
    manifest = json.loads((incoming / "release.json").read_text())
    validate_manifest(manifest)
    revision = manifest["revision"]

    def run(*args, capture=False):
        if capture:
            return subprocess.check_output(args, cwd=root, text=True).strip()
        subprocess.run(args, cwd=root, check=True)

    def compose(*args, capture=False):
        options = ["docker", "compose", "--env-file", str(root / ".env")]
        if (root / ".release.env").exists():
            options += ["--env-file", str(root / ".release.env")]
        return run(*options, *args, capture=capture)

    backup = (
        root / ".releases" / (time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + revision[:12])
    )
    backup.mkdir(parents=True, mode=0o700)
    for name in ["docker-compose.yml", ".env", ".release.env"]:
        if (root / name).exists():
            shutil.copy2(root / name, backup / name)
            os.chmod(backup / name, 0o600)
    old_images = {}
    for service in SERVICES:
        # Commit retains historical container edits as well as the underlying image.
        tag = "footagehub-" + service + ":rollback-" + backup.name
        run("docker", "commit", "footagehub-" + service, tag, capture=True)
        old_images[service] = run(
            "docker", "image", "inspect", tag, "--format", "{{.Id}}", capture=True
        )
    (backup / "images.json").write_text(json.dumps(old_images, indent=2))
    # Export sessions before removing them from build inputs; never print their contents.
    storage = root / "provider-cookies"
    for provider, folder in [
        ("envato", "envato_utils"),
        ("freepik", "freepik_utils"),
        ("motion", "motion_utils"),
    ]:
        target = storage / provider
        target.mkdir(parents=True, mode=0o700, exist_ok=True)
        code = (
            "from pathlib import Path; p=Path('/app/media_bot/utils/"
            + folder
            + "'); print('\\n'.join(str(x) for x in p.glob('*cookies*.json')))"
        )
        files = run(
            "docker", "exec", "footagehub-media-bot", "python", "-c", code, capture=True
        ).splitlines()
        for source in files:
            dest = target / Path(source).name
            if not dest.exists():
                run("docker", "cp", "footagehub-media-bot:" + source, str(dest))
                os.chmod(dest, 0o600)
        if not list(target.glob("*cookies*.json")):
            raise RuntimeError("Provider session export missing: " + provider)
    profile = root / "browser-profiles" / "freepik"
    if not profile.exists():
        profile.parent.mkdir(mode=0o700, exist_ok=True)
        exists = (
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "footagehub-media-bot",
                    "test",
                    "-d",
                    "/app/media_bot/utils/freepik_utils/.profile",
                ]
            ).returncode
            == 0
        )
        if exists:
            run(
                "docker",
                "cp",
                "footagehub-media-bot:/app/media_bot/utils/freepik_utils/.profile",
                str(profile),
            )
        else:
            profile.mkdir(mode=0o700)
    # Save and validate a database backup before any migrations or container changes.
    dump = backup / "botdb.dump"
    with dump.open("wb") as output:
        subprocess.run(
            ["docker", "exec", "footagehub-db", "pg_dump", "-U", "botuser", "-d", "botdb", "-Fc"],
            stdout=output,
            check=True,
        )
    os.chmod(dump, 0o600)
    with dump.open("rb") as source:
        subprocess.run(
            ["docker", "exec", "-i", "footagehub-db", "pg_restore", "--list"],
            stdin=source,
            stdout=subprocess.DEVNULL,
            check=True,
        )
    switched = False
    try:
        shutil.copy2(incoming / "docker-compose.yml", root / "docker-compose.yml")
        values = {
            service.replace("-", "_").upper() + "_IMAGE": image
            for service, image in manifest["images"].items()
        }
        (root / ".release.env").write_text(
            "\n".join(key + "=" + value for key, value in values.items()) + "\n"
        )
        os.chmod(root / ".release.env", 0o600)
        compose("config", "--quiet")
        compose("pull", *SERVICES)
        for service, image in manifest["images"].items():
            label = run(
                "docker",
                "image",
                "inspect",
                image,
                "--format",
                '{{index .Config.Labels "org.opencontainers.image.revision"}}',
                capture=True,
            )
            if label != revision:
                raise RuntimeError("Image revision mismatch: " + service)
        # Do not automatically apply an unreviewed schema change with code-only rollback.
        code = "from alembic.config import Config; from alembic.script import ScriptDirectory; print(','.join(sorted(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())))"
        desired = compose("run", "--rm", "--no-deps", "web-api", "python", "-c", code, capture=True)
        current = run(
            "docker",
            "exec",
            "footagehub-db",
            "psql",
            "-U",
            "botuser",
            "-d",
            "botdb",
            "-Atc",
            "SELECT version_num FROM alembic_version ORDER BY version_num",
            capture=True,
        ).replace("\n", ",")
        if current != desired:
            raise RuntimeError(
                "Pending migrations require a separately reviewed migration/rollback procedure"
            )
        switched = True
        compose("up", "-d", "--no-deps", "--force-recreate", *SERVICES)
        for attempt in range(45):
            try:
                for url in [
                    "http://127.0.0.1:8080/api/health",
                    "http://127.0.0.1:3000/en",
                    "http://127.0.0.1:3000/google0dee334ff7a6a8b1.html",
                ]:
                    # Only the hardcoded loopback HTTP health URLs above are used.
                    with urllib.request.urlopen(url, timeout=3) as response:  # nosec B310
                        if response.status != 200:
                            raise RuntimeError("Health check failed")
                for service in SERVICES:
                    state = json.loads(
                        run("docker", "inspect", "footagehub-" + service, capture=True)
                    )[0]
                    if not state["State"]["Running"] or state["RestartCount"]:
                        raise RuntimeError("Container not stable: " + service)
                break
            except Exception:
                if attempt == 44:
                    raise
                time.sleep(2)
        # Bot API credentials/connectivity are checked without sending messages.
        code = "import urllib.request,json,os; r=urllib.request.urlopen('https://api.telegram.org/bot'+os.environ['BOT_TOKEN']+'/getMe',timeout=10); assert json.load(r)['ok']"
        for service in ["media-bot", "ai-bot"]:
            run("docker", "exec", "footagehub-" + service, "python", "-c", code)
        (root / "deployed-release.json").write_text(json.dumps(manifest, indent=2))
        print("DEPLOY_OK revision=" + revision, flush=True)
    except BaseException:
        shutil.copy2(backup / "docker-compose.yml", root / "docker-compose.yml")
        rollback_values = {}
        for service, image in old_images.items():
            tag = "footagehub-" + service + ":rollback-" + backup.name
            rollback_values[service.replace("-", "_").upper() + "_IMAGE"] = tag
            run("docker", "tag", image, "ghcr.io/b0gdan4eg/footagehub-" + service + ":latest")
        # Older compose files use latest directly; newer ones use these retained tags.
        (root / ".release.env").write_text(
            "\n".join(key + "=" + value for key, value in rollback_values.items()) + "\n"
        )
        os.chmod(root / ".release.env", 0o600)
        if switched:
            compose("up", "-d", "--no-deps", "--force-recreate", *SERVICES)
        print("ROLLBACK retained at " + str(backup), flush=True)
        raise


if __name__ == "__main__":
    import fcntl

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/opt/my_bot"))
    parser.add_argument("--incoming", type=Path, required=True)
    args = parser.parse_args()
    with (args.root / ".deployment.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        deploy(args.root.resolve(), args.incoming.resolve())
