"""Build and verify the deterministic M2-S3E clean-environment handoff."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_m2_s3b_candidate as base  # noqa: E402
from scripts import build_m2_s3d_candidate as s3d  # noqa: E402
from scripts import release_manifest  # noqa: E402

STATUS = (
    "M2_S3E_A_SAME_HOST_ISOLATED_PORTABILITY_LOCALLY_VERIFIED_"
    "CLEAN_ENVIRONMENT_HANDOFF_READY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)
HANDOFF_STATUS = (
    "M2_S3E_CLEAN_ENVIRONMENT_HANDOFF_DETERMINISTICALLY_BUILT_"
    "PENDING_EXTERNAL_EXECUTION_NO_RELEASE_AUTHORITY"
)

PACKAGING_ROOT = ROOT / "packaging"
HANDOFF_ROOT = PACKAGING_ROOT / "handoffs" / "m2-s3e-clean-environment"
HANDOFF_ZIP = HANDOFF_ROOT / "M2-S3E-CLEAN-ENVIRONMENT-HANDOFF.zip"
HANDOFF_VALIDATION = HANDOFF_ROOT / "M2_S3E_HANDOFF_BUILD_VALIDATION.json"
README_SOURCE = PACKAGING_ROOT / "README_M2_S3E_HANDOFF.txt"
POWERSHELL_SOURCE = PACKAGING_ROOT / "VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1"
RESPONSE_TEMPLATE = PACKAGING_ROOT / "M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.template.json"

S3D_CANDIDATE_ROOT = PACKAGING_ROOT / "candidates" / "m2-s3d-round-trip"
S3D_BUNDLE_ROOT = S3D_CANDIDATE_ROOT / "PDU-Exam-Observer"
S3D_BUILD_VALIDATION = S3D_CANDIDATE_ROOT / "M2_S3D_BUILD_VALIDATION.json"
S3D_DETACHED_MANIFEST = S3D_CANDIDATE_ROOT / "RELEASE_MANIFEST.json"
S3D_BUNDLED_MANIFEST = S3D_BUNDLE_ROOT / "RELEASE_MANIFEST.json"
S3D_EXECUTABLE = S3D_BUNDLE_ROOT / "PDUExamObserver.exe"
S3D_ROUND_TRIP_RECEIPT = ROOT / "docs" / "ai" / "M2_S3D_PACKAGED_EVIDENCE_ROUND_TRIP.json"

S3D_HASHES: dict[str, str] = {
    "build_validation_sha256": "432c906b2a32d84d5d82509d27cfa3882500657ce97e544e7fb71513b0754b94",
    "executable_sha256": "9d9aabe6b6176fabb1db423924d8c27a8ee9478d302b421680dc8bfc989c66aa",
    "manifest_sha256": "8702963dddd8b9d2761120fce8875d9fd181177eb15f1576e72e7354ad3ae216",
    "round_trip_receipt_sha256": "4d8a862408aec0470d86b084f1abdc9baa323a3ee53cb57dfe780c3d6e2258ed",
    "tree_sha256": "64686518c09679f98b6f3c01805535ca9aad50413781424a08020c2460d017e1",
}
S3D_SOURCE_REVISION: dict[str, str] = {
    "binding_schema_exact_bytes_sha256": (
        "7125de572f5a78b986a768b484315b818e1c630d10ada48ea31bd0915c300058"
    ),
    "candidate_exact_bytes_sha256": (
        "ced85d39533de902da652c4a7f56ea85eaf4891a5d8b27946badf8aebcae5c79"
    ),
    "static_bindings_digest": "034eb3e19f88377529f5ffc37c077938b42563a447d1d6e6a481c1b635cbf607",
}

ZIP_TIMESTAMP = (2026, 9, 2, 0, 0, 0)
ZIP_FILE_EXTERNAL_ATTR = 0o100644 << 16
MAX_HANDOFF_BYTES = 100_000_000


class HandoffError(RuntimeError):
    """Bounded handoff failure."""


def canonical_bytes(document: object, *, trailing_lf: bool = True) -> bytes:
    payload = json.dumps(
        document, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return payload + (b"\n" if trailing_lf else b"")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise HandoffError("SOURCE_ARTIFACT_MISMATCH") from exc
    return digest.hexdigest()


def _safe_member(name: str) -> str:
    if not name or "\\" in name or "\x00" in name or ":" in name:
        raise HandoffError("ZIP_ENTRY_INVALID")
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise HandoffError("ZIP_ENTRY_INVALID")
    return name


def build_zip_bytes(entries: dict[str, bytes]) -> bytes:
    if not entries:
        raise HandoffError("HANDOFF_FILE_SET_MISMATCH")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
        for name in sorted(entries):
            safe = _safe_member(name)
            info = zipfile.ZipInfo(safe, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ZIP_FILE_EXTERNAL_ATTR
            info.flag_bits |= 0x800
            archive.writestr(
                info,
                entries[name],
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    payload = output.getvalue()
    if len(payload) > MAX_HANDOFF_BYTES:
        raise HandoffError("HANDOFF_FILE_SET_MISMATCH")
    return payload


def inspect_zip_bytes(payload: bytes) -> dict[str, bytes]:
    if not payload or len(payload) > MAX_HANDOFF_BYTES:
        raise HandoffError("ZIP_ENTRY_INVALID")
    observed: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            for info in archive.infolist():
                name = _safe_member(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if name in observed or info.is_dir() or mode == stat.S_IFLNK:
                    raise HandoffError("ZIP_ENTRY_INVALID")
                observed[name] = archive.read(info)
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, HandoffError):
            raise
        raise HandoffError("ZIP_ENTRY_INVALID") from exc
    return dict(sorted(observed.items()))


def current_s3d_tree_sha256() -> str:
    try:
        records = s3d._candidate_records()
        return base._tree_digest(records)
    except Exception as exc:
        raise HandoffError("CANDIDATE_INPUT_MISMATCH") from exc


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(code) from exc
    if not isinstance(value, dict) or raw != canonical_bytes(value):
        raise HandoffError(code)
    return value


def _validate_sources() -> dict[str, str]:
    if os.name != "nt":
        raise HandoffError("PLATFORM_UNSUPPORTED")
    actual = {
        "build_validation_sha256": _sha256_file(S3D_BUILD_VALIDATION),
        "executable_sha256": _sha256_file(S3D_EXECUTABLE),
        "manifest_sha256": _sha256_file(S3D_DETACHED_MANIFEST),
        "round_trip_receipt_sha256": _sha256_file(S3D_ROUND_TRIP_RECEIPT),
        "tree_sha256": current_s3d_tree_sha256(),
    }
    if actual != S3D_HASHES:
        raise HandoffError("S3D_EVIDENCE_MISMATCH")
    try:
        release_manifest.verify_manifest(
            S3D_BUNDLE_ROOT, S3D_BUNDLED_MANIFEST, S3D_DETACHED_MANIFEST
        )
    except Exception as exc:
        raise HandoffError("RELEASE_MANIFEST_MISMATCH") from exc
    validation = _load_json(S3D_BUILD_VALIDATION, "S3D_EVIDENCE_MISMATCH")
    body = validation.get("body")
    if not isinstance(body, dict) or body.get("source_revision") != S3D_SOURCE_REVISION:
        raise HandoffError("S3D_EVIDENCE_MISMATCH")
    for source in (README_SOURCE, POWERSHELL_SOURCE, RESPONSE_TEMPLATE):
        if not source.is_file() or base._is_link_or_reparse(source):
            raise HandoffError("SOURCE_ARTIFACT_MISMATCH")
    return actual


def _current_rp2() -> dict[str, str]:
    try:
        value = base._load_rp2()
    except Exception as exc:
        raise HandoffError("RP2_INVALID") from exc
    if set(value) != {
        "binding_schema_exact_bytes_sha256",
        "candidate_exact_bytes_sha256",
        "static_bindings_digest",
    }:
        raise HandoffError("RP2_INVALID")
    return value


def _source_entries() -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    try:
        records = base._tree_records(S3D_BUNDLE_ROOT)
        for record in records:
            relative = str(record["path"])
            entries[f"PDU-Exam-Observer/{relative}"] = (S3D_BUNDLE_ROOT / relative).read_bytes()
        entries["RELEASE_MANIFEST.json"] = S3D_DETACHED_MANIFEST.read_bytes()
        entries["M2_S3E_S3D_BUILD_VALIDATION.json"] = S3D_BUILD_VALIDATION.read_bytes()
        entries["M2_S3E_S3D_ROUND_TRIP_RECEIPT.json"] = S3D_ROUND_TRIP_RECEIPT.read_bytes()
        entries["README_M2_S3E_HANDOFF.txt"] = README_SOURCE.read_bytes()
        entries["VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1"] = POWERSHELL_SOURCE.read_bytes()
        entries["M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.template.json"] = RESPONSE_TEMPLATE.read_bytes()
    except OSError as exc:
        raise HandoffError("SOURCE_ARTIFACT_MISMATCH") from exc
    artifacts = [
        {"path": name, "sha256": _sha256_bytes(payload), "size": len(payload)}
        for name, payload in sorted(entries.items())
    ]
    body: dict[str, object] = {
        "artifacts": artifacts,
        "authority_ceiling": {
            "authority_status": "AUTHORITY_NOT_ISSUED",
            "clean_machine_verified": False,
            "distribution_ready": False,
            "release_authorized": False,
        },
        "handoff_kind": "M2_S3E_CLEAN_ENVIRONMENT_HANDOFF",
        "s3d_binding": S3D_HASHES | {"source_revision": S3D_SOURCE_REVISION},
        "schema_version": 1,
    }
    manifest = {
        "artifact_kind": "M2_S3E_HANDOFF_MANIFEST",
        "body": body,
        "body_sha256": _sha256_bytes(canonical_bytes(body, trailing_lf=False)),
        "schema_version": 1,
    }
    entries["M2_S3E_HANDOFF_MANIFEST.json"] = canonical_bytes(manifest)
    return entries


def _validate_entries(entries: dict[str, bytes]) -> dict[str, Any]:
    manifest_raw = entries.get("M2_S3E_HANDOFF_MANIFEST.json")
    if manifest_raw is None:
        raise HandoffError("HANDOFF_MANIFEST_INVALID")
    try:
        manifest = json.loads(manifest_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError("HANDOFF_MANIFEST_INVALID") from exc
    if not isinstance(manifest, dict) or manifest_raw != canonical_bytes(manifest):
        raise HandoffError("HANDOFF_MANIFEST_INVALID")
    body = manifest.get("body")
    if (
        set(manifest) != {"artifact_kind", "body", "body_sha256", "schema_version"}
        or manifest.get("artifact_kind") != "M2_S3E_HANDOFF_MANIFEST"
        or manifest.get("schema_version") != 1
        or not isinstance(body, dict)
        or manifest.get("body_sha256") != _sha256_bytes(canonical_bytes(body, trailing_lf=False))
    ):
        raise HandoffError("HANDOFF_MANIFEST_INVALID")
    expected_records = body.get("artifacts")
    observed_records = [
        {"path": name, "sha256": _sha256_bytes(payload), "size": len(payload)}
        for name, payload in sorted(entries.items())
        if name != "M2_S3E_HANDOFF_MANIFEST.json"
    ]
    if expected_records != observed_records:
        raise HandoffError("HANDOFF_FILE_SET_MISMATCH")
    return manifest


def _validation(zip_payload: bytes, entries: dict[str, bytes]) -> dict[str, object]:
    body: dict[str, object] = {
        "authority_ceiling": {
            "clean_environment_handoff_ready": True,
            "clean_machine_verified": False,
            "distribution_ready": False,
            "release_authorized": False,
            "authority_status": "AUTHORITY_NOT_ISSUED",
        },
        "handoff": {
            "entry_count": len(entries),
            "manifest_sha256": _sha256_bytes(entries["M2_S3E_HANDOFF_MANIFEST.json"]),
            "zip_sha256": _sha256_bytes(zip_payload),
            "zip_size": len(zip_payload),
        },
        "observed_on": "2026-09-02",
        "reproducibility": {
            "build_a_sha256": _sha256_bytes(zip_payload),
            "build_b_sha256": _sha256_bytes(zip_payload),
            "byte_identical": True,
        },
        "result": "HANDOFF_PACK_BUILT",
        "s3d_binding": S3D_HASHES | {"source_revision": S3D_SOURCE_REVISION},
        "source_revision": _current_rp2(),
    }
    return {
        "artifact_kind": "M2_S3E_HANDOFF_BUILD_VALIDATION",
        "body": body,
        "body_sha256": _sha256_bytes(canonical_bytes(body, trailing_lf=False)),
        "schema_version": 1,
        "status": HANDOFF_STATUS,
    }


def check_handoff_pack() -> dict[str, object]:
    _validate_sources()
    try:
        zip_payload = HANDOFF_ZIP.read_bytes()
    except OSError as exc:
        raise HandoffError("HANDOFF_FILE_SET_MISMATCH") from exc
    entries = inspect_zip_bytes(zip_payload)
    _validate_entries(entries)
    expected = _validation(zip_payload, entries)
    observed = _load_json(HANDOFF_VALIDATION, "HANDOFF_MANIFEST_INVALID")
    if observed != expected:
        raise HandoffError("HANDOFF_MANIFEST_INVALID")
    return {"failure_code": None, "result": "HANDOFF_PACK_BUILT", "status": HANDOFF_STATUS}


def build_handoff_pack() -> dict[str, object]:
    _validate_sources()
    entries = _source_entries()
    _validate_entries(entries)
    first = build_zip_bytes(entries)
    second = build_zip_bytes(entries)
    if first != second:
        raise HandoffError("ZIP_REPRODUCIBILITY_MISMATCH")
    validation = canonical_bytes(_validation(first, entries))
    try:
        HANDOFF_ROOT.mkdir(parents=True, exist_ok=True)
        if HANDOFF_ZIP.exists() or HANDOFF_VALIDATION.exists():
            if (
                not HANDOFF_ZIP.is_file()
                or not HANDOFF_VALIDATION.is_file()
                or HANDOFF_ZIP.read_bytes() != first
                or HANDOFF_VALIDATION.read_bytes() != validation
            ):
                raise HandoffError("HANDOFF_EXISTS_MISMATCH")
        else:
            temporary = Path(tempfile.mkdtemp(prefix=".pdu-m2-s3e-build-", dir=HANDOFF_ROOT))
            try:
                zip_leaf = temporary / HANDOFF_ZIP.name
                receipt_leaf = temporary / HANDOFF_VALIDATION.name
                zip_leaf.write_bytes(first)
                receipt_leaf.write_bytes(validation)
                os.replace(zip_leaf, HANDOFF_ZIP)
                os.replace(receipt_leaf, HANDOFF_VALIDATION)
            finally:
                shutil.rmtree(temporary, ignore_errors=False)
    except HandoffError:
        raise
    except OSError as exc:
        raise HandoffError("OUTPUT_WRITE_FAILED") from exc
    return check_handoff_pack()


def parse_mode(argv: list[str]) -> str:
    if argv == [] or argv == ["--check"]:
        return "check"
    if argv == ["--build"]:
        return "build"
    raise HandoffError("REQUEST_INVALID")


def failure_document(code: str) -> dict[str, object]:
    return {"failure_code": code, "result": "HANDOFF_PACK_NOT_VERIFIED", "status": None}


def _emit(document: dict[str, object], exit_code: int) -> NoReturn:
    sys.stdout.buffer.write(canonical_bytes(document))
    raise SystemExit(exit_code)


def main(argv: list[str] | None = None) -> NoReturn:
    try:
        mode = parse_mode(list(sys.argv[1:] if argv is None else argv))
        result = build_handoff_pack() if mode == "build" else check_handoff_pack()
    except HandoffError as exc:
        _emit(failure_document(str(exc)), 2)
    except Exception:
        _emit(failure_document("UNEXPECTED_FAILURE"), 2)
    _emit(result, 0)


if __name__ == "__main__":
    main()
