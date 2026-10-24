from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import sys
import zipfile


VERSION = "0.4.0"
EDITIONS = ("Free", "Free-with-Ads", "Supporter", "Pro")
ZIP_NAMES = tuple(
    f"Quasar-{platform}-{edition}-{VERSION}.zip"
    for platform in ("Windows", "Android")
    for edition in EDITIONS
)
MANIFEST_NAME = "SHA256SUMS.txt"


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_zip(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            files = [name for name in archive.namelist() if not name.endswith("/")]
            if not files:
                fail(f"{path.name} is empty")
            for name in files:
                member = PurePosixPath(name)
                if member.is_absolute() or ".." in member.parts:
                    fail(f"{path.name} contains unsafe path {name!r}")

            if "-Android-" in path.name:
                expected_apk = path.stem + ".apk"
                apks = [PurePosixPath(name).name for name in files if name.lower().endswith(".apk")]
                if apks != [expected_apk]:
                    fail(
                        f"{path.name} must contain exactly one same-label APK "
                        f"named {expected_apk}; found {apks or 'none'}"
                    )
    except zipfile.BadZipFile:
        fail(f"{path.name} is not a valid ZIP archive")


def validate_inputs(directory: Path) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    expected = set(ZIP_NAMES)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        fail(f"draft assets do not match contract; missing={missing}, extra={extra}")

    for name in ZIP_NAMES:
        validate_zip(directory / name)


def write_manifest(directory: Path) -> None:
    manifest = directory / MANIFEST_NAME
    manifest.write_text(
        "".join(f"{sha256(directory / name)}  {name}\n" for name in ZIP_NAMES),
        encoding="ascii",
        newline="\n",
    )


def validate_signed_outputs(directory: Path) -> None:
    expected = set(ZIP_NAMES) | {MANIFEST_NAME}
    expected |= {f"{name}.sigstore.json" for name in expected}
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        fail(f"signed outputs do not match contract; missing={missing}, extra={extra}")

    manifest_lines = (directory / MANIFEST_NAME).read_text(encoding="ascii").splitlines()
    expected_lines = [f"{sha256(directory / name)}  {name}" for name in ZIP_NAMES]
    if manifest_lines != expected_lines:
        fail("SHA256SUMS.txt does not match the exact release ZIP bytes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("inputs", "manifest", "signed"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()

    if not args.directory.is_dir():
        fail(f"release directory does not exist: {args.directory}")

    if args.mode == "inputs":
        validate_inputs(args.directory)
    elif args.mode == "manifest":
        validate_inputs(args.directory)
        write_manifest(args.directory)
    else:
        validate_signed_outputs(args.directory)


if __name__ == "__main__":
    main()
