"""Build and verify canonical release manifests without importing the app."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "RELEASE_MANIFEST.json"
DETACHED_MANIFEST_NAME = "RELEASE_MANIFEST.detached.json"
REQUIRED_METADATA = {
    "product_version",
    "schema_version",
    "target_os",
    "target_architecture",
    "build_time_utc",
    "source_revision",
    "python_lock_sha256",
    "frontend_lock_sha256",
    "known_limitations",
}


class ManifestError(ValueError):
    """Raised for any unsafe, malformed, or inconsistent release manifest."""


def canonical_json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _safe_manifest_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ManifestError(f"unsafe manifest path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or ":" in path.parts[0]:
        raise ManifestError(f"unsafe manifest path: {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise ManifestError(f"unsafe manifest path: {value!r}")
    return normalized


def _root_path(root: Path) -> Path:
    root = root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise ManifestError(f"bundle root is not a real directory: {root}")
    return root.resolve(strict=True)


def _payload_files(root: Path) -> dict[str, Path]:
    root = _root_path(root)
    result: dict[str, Path] = {}
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in dirs:
            candidate = current_path / dirname
            if candidate.is_symlink():
                raise ManifestError(f"symlink in release bundle: {candidate}")
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs
        for filename in files:
            candidate = current_path / filename
            if candidate.is_symlink():
                raise ManifestError(f"symlink in release bundle: {candidate}")
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, ValueError) as exc:
                raise ManifestError(f"path escapes bundle root: {candidate}") from exc
            relative = candidate.relative_to(root).as_posix()
            _safe_manifest_path(relative)
            if relative in {MANIFEST_NAME, DETACHED_MANIFEST_NAME}:
                continue
            result[relative] = candidate
    return dict(sorted(result.items()))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(bundle_root: Path, metadata: dict[str, Any], detached_path: Path) -> tuple[Path, Path]:
    root = _root_path(Path(bundle_root))
    missing = REQUIRED_METADATA - set(metadata)
    if missing:
        raise ManifestError(f"manifest metadata missing: {', '.join(sorted(missing))}")
    files = [
        {"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)}
        for relative, path in _payload_files(root).items()
    ]
    document = dict(metadata)
    document["files"] = files
    payload = canonical_json_bytes(document)
    bundled_path = root / MANIFEST_NAME
    bundled_path.write_bytes(payload)
    detached_path = Path(detached_path)
    detached_path.parent.mkdir(parents=True, exist_ok=True)
    detached_path.write_bytes(payload)
    return bundled_path, detached_path


def _strict_json(raw: bytes, source: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ManifestError(f"duplicate manifest key: {key}")
            result[key] = value
        return result

    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"invalid manifest JSON: {source}") from exc
    if not isinstance(document, dict):
        raise ManifestError("manifest root must be an object")
    if canonical_json_bytes(document) != raw:
        raise ManifestError("manifest is not canonical JSON")
    missing = REQUIRED_METADATA - set(document)
    if missing:
        raise ManifestError(f"manifest metadata missing: {', '.join(sorted(missing))}")
    return document


def verify_manifest(bundle_root: Path, bundled_path: Path, detached_path: Path) -> bool:
    root = _root_path(Path(bundle_root))
    bundled_path = Path(bundled_path)
    detached_path = Path(detached_path)
    if bundled_path.resolve() != (root / MANIFEST_NAME).resolve():
        raise ManifestError("bundled manifest is not inside bundle at the canonical path")
    if bundled_path.resolve() == detached_path.resolve():
        raise ManifestError("detached manifest must be a distinct copy")
    bundled_bytes = bundled_path.read_bytes()
    if bundled_bytes != detached_path.read_bytes():
        raise ManifestError("bundled and detached manifests differ")
    document = _strict_json(bundled_bytes, bundled_path)
    entries = document.get("files")
    if not isinstance(entries, list):
        raise ManifestError("manifest files must be a list")
    listed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}:
            raise ManifestError("manifest file entry has invalid shape")
        relative = _safe_manifest_path(entry["path"])
        if relative in listed:
            raise ManifestError(f"duplicate manifest file entry: {relative}")
        if not isinstance(entry["size"], int) or entry["size"] < 0:
            raise ManifestError(f"invalid size for: {relative}")
        if not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64 or any(
            char not in "0123456789abcdef" for char in entry["sha256"]
        ):
            raise ManifestError(f"invalid sha256 for: {relative}")
        listed[relative] = entry
    actual = _payload_files(root)
    if set(listed) != set(actual):
        raise ManifestError("file set mismatch between manifest and bundle")
    for relative, path in actual.items():
        entry = listed[relative]
        if path.stat().st_size != entry["size"]:
            raise ManifestError(f"size mismatch for: {relative}")
        if _sha256(path) != entry["sha256"]:
            raise ManifestError(f"hash mismatch for: {relative}")
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--bundle-root", type=Path, required=True)
    build.add_argument("--metadata-json", type=Path, required=True)
    build.add_argument("--detached", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--bundle-root", type=Path, required=True)
    verify.add_argument("--bundled", type=Path, required=True)
    verify.add_argument("--detached", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "build":
        metadata = json.loads(args.metadata_json.read_text(encoding="utf-8"))
        bundled, detached = build_manifest(args.bundle_root, metadata, args.detached)
        print(f"manifest built: {bundled}")
        print(f"detached manifest: {detached}")
        return 0
    verify_manifest(args.bundle_root, args.bundled, args.detached)
    print("manifest verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
