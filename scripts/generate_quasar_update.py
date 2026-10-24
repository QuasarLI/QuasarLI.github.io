from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

from validate_quasar_release import EDITIONS, VERSION, validate_inputs


REPOSITORY = "https://github.com/QuasarLI/QuasarLI.github.io"
RELEASE_BASE = f"{REPOSITORY}/releases/download/v{VERSION}"
EDITION_IDS = {
    "Free": "free",
    "Free-with-Ads": "free-ads",
    "Supporter": "supporter",
    "Pro": "pro",
}
LEGACY_ANDROID = {
    "version": "0.3.2",
    "versionCode": 5,
    "url": (
        "https://github.com/QuasarLI/QuasarLI.github.io/releases/download/"
        "v0.3.3/Quasar-Android-0.3.2.apk"
    ),
    "sha256": "6940b502a6d5449416dfce5d6db452a60ea58a1a39aca8c2828c5e9d5eaf0994",
}


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_url(filename: str) -> str:
    return f"{RELEASE_BASE}/{filename}"


def windows_entry(directory: Path, label: str) -> dict[str, object]:
    filename = f"Quasar-Windows-{label}-{VERSION}.zip"
    return {
        "version": VERSION,
        "url": release_url(filename),
        "sha256": digest_file(directory / filename),
        "sigstoreBundle": release_url(f"{filename}.sigstore.json"),
    }


def android_entry(directory: Path, label: str) -> dict[str, object]:
    filename = f"Quasar-Android-{label}-{VERSION}.zip"
    apk_filename = f"Quasar-Android-{label}-{VERSION}.apk"
    archive_path = directory / filename
    with zipfile.ZipFile(archive_path) as archive:
        matches = [
            name
            for name in archive.namelist()
            if PurePosixPath(name).name == apk_filename
        ]
        if len(matches) != 1:
            fail(f"{filename} must contain exactly one {apk_filename}")
        apk_sha256 = digest_bytes(archive.read(matches[0]))

    return {
        "version": VERSION,
        "versionCode": 6,
        "url": release_url(filename),
        "sha256": digest_file(archive_path),
        "apkFile": apk_filename,
        "apkSha256": apk_sha256,
        "sigstoreBundle": release_url(f"{filename}.sigstore.json"),
    }


def build_manifest(directory: Path) -> dict[str, object]:
    validate_inputs(directory)
    windows_editions = {
        EDITION_IDS[label]: windows_entry(directory, label) for label in EDITIONS
    }
    android_editions = {
        EDITION_IDS[label]: android_entry(directory, label) for label in EDITIONS
    }
    free_windows = windows_editions["free"]
    return {
        "schemaVersion": 2,
        "version": VERSION,
        "windows": {
            "version": VERSION,
            "url": free_windows["url"],
            "sha256": free_windows["sha256"],
            "editions": windows_editions,
        },
        "android": {
            **LEGACY_ANDROID,
            "editions": android_editions,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_directory", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="site root containing latest.json",
    )
    args = parser.parse_args()

    manifest = build_manifest(args.release_directory)
    rendered = json.dumps(manifest, indent=2) + "\n"
    outputs = (
        args.root / "latest.json",
        args.root / "quasar" / "updates" / "latest.json",
    )
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
        print(output)


if __name__ == "__main__":
    main()
