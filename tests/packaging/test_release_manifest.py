import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
from release_manifest import (  # noqa: E402
    ManifestError,
    build_manifest,
    canonical_json_bytes,
    verify_manifest,
)


def _metadata() -> dict[str, object]:
    return {
        "product_version": "0.1.0-m0",
        "schema_version": "release-manifest.v1",
        "target_os": "Windows 11",
        "target_architecture": "x64",
        "build_time_utc": "2026-08-24T00:00:00Z",
        "source_revision": "UNVERIFIED",
        "python_lock_sha256": "0" * 64,
        "frontend_lock_sha256": "1" * 64,
        "known_limitations": ["Unsigned trial package; clean-machine portability is UNVERIFIED."],
    }


def test_manifest_hashes_payload_and_detached_copy_is_byte_identical(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "PDUExamObserver.exe").write_bytes(b"demo executable")
    (bundle / "assets").mkdir()
    (bundle / "assets" / "index.html").write_text("<main>demo</main>", encoding="utf-8")

    bundled, detached = build_manifest(bundle, _metadata(), tmp_path / "RELEASE_MANIFEST.json")

    assert bundled.read_bytes() == detached.read_bytes()
    document = json.loads(bundled.read_text(encoding="utf-8"))
    assert [entry["path"] for entry in document["files"]] == [
        "PDUExamObserver.exe",
        "assets/index.html",
    ]
    assert document["files"][0]["sha256"] == hashlib.sha256(b"demo executable").hexdigest()
    assert verify_manifest(bundle, bundled, detached) is True


def test_verify_fails_closed_for_missing_extra_and_wrong_hash(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "payload.bin").write_bytes(b"payload")
    bundled, detached = build_manifest(bundle, _metadata(), tmp_path / "RELEASE_MANIFEST.json")

    (bundle / "payload.bin").write_bytes(b"tampered")
    with pytest.raises(ManifestError, match="(size|hash) mismatch"):
        verify_manifest(bundle, bundled, detached)

    (bundle / "payload.bin").write_bytes(b"payload")
    (bundle / "extra.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ManifestError, match="file set mismatch"):
        verify_manifest(bundle, bundled, detached)

    (bundle / "extra.txt").unlink()
    document = json.loads(bundled.read_text(encoding="utf-8"))
    document["files"] = []
    bundled.write_bytes(canonical_json_bytes(document))
    detached.write_bytes(bundled.read_bytes())
    with pytest.raises(ManifestError, match="file set mismatch"):
        verify_manifest(bundle, bundled, detached)


def test_manifest_rejects_symlink_escape_and_traversal_entry(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    link = bundle / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(ManifestError, match="symlink"):
        build_manifest(bundle, _metadata(), tmp_path / "RELEASE_MANIFEST.json")

    link.unlink()
    (bundle / "payload.txt").write_text("ok", encoding="utf-8")
    bundled, detached = build_manifest(bundle, _metadata(), tmp_path / "RELEASE_MANIFEST.json")
    document = json.loads(bundled.read_text(encoding="utf-8"))
    document["files"][0]["path"] = "../outside.txt"
    bundled.write_bytes(canonical_json_bytes(document))
    detached.write_bytes(bundled.read_bytes())
    with pytest.raises(ManifestError, match="unsafe manifest path"):
        verify_manifest(bundle, bundled, detached)


def test_canonical_json_is_stable_and_manifest_bytes_are_canonical() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}\n'
