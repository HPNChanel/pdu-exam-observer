"""Build and verify the non-authorizing GOV-P3 advisor decision receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = (
    ROOT / "research" / "institutional_submission" / "advisor_decision" / "v1"
)

SOURCE_NAME = "advisor-verbal-confirmation.record.v1.json"
MANIFEST_NAME = "gov-p3-advisor-decision.manifest.v1.json"
VALIDATION_NAME = "gov-p3-advisor-decision.validation.v1.json"
GENERATED_NAMES = (MANIFEST_NAME, VALIDATION_NAME)
ALL_NAMES = frozenset((SOURCE_NAME, *GENERATED_NAMES))

STATUS = (
    "GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_"
    "READY_FOR_INSTITUTIONAL_ROUTING"
)


@dataclass(frozen=True)
class Upstream:
    path: Path
    relative_path: str
    sha256: str


UPSTREAMS = {
    "gov_p2_decision_matrix": Upstream(
        path=ROOT
        / "research"
        / "institutional_submission"
        / "v1"
        / "decision-request-matrix.v1.json",
        relative_path="research/institutional_submission/v1/decision-request-matrix.v1.json",
        sha256="dcdff3aa61062f9fe0e37919141e9c591eeac751f8f52c296f6bf11f6fb4b9e4",
    ),
    "gov_p2_manifest": Upstream(
        path=ROOT
        / "research"
        / "institutional_submission"
        / "v1"
        / "gov-p2-submission.manifest.v1.json",
        relative_path=(
            "research/institutional_submission/v1/"
            "gov-p2-submission.manifest.v1.json"
        ),
        sha256="1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e",
    ),
    "gov_p2_validation": Upstream(
        path=ROOT
        / "research"
        / "institutional_submission"
        / "v1"
        / "gov-p2-submission.validation.v1.json",
        relative_path=(
            "research/institutional_submission/v1/"
            "gov-p2-submission.validation.v1.json"
        ),
        sha256="19b9502d357528322b51a18719760ef6eb7e082b187f2dd1047a9073635952e6",
    ),
}

AUTHORITY_CEILING: dict[str, object] = {
    "authority_status": "AUTHORITY_NOT_ISSUED",
    "collection_authorized": False,
    "d1_go": False,
    "device_gate_decision": "UNVERIFIED",
    "execution_authorized": False,
    "participant_collection_authorized": False,
    "physical_camera_access_authorized": False,
    "production_reconciler_implemented": False,
    "production_reconciler_real_storage_verified": False,
    "real_data_deletion_authorized": False,
    "research_ready": False,
}

BLOCKING_GATES = (
    "ACL_NOT_VERIFIED",
    "ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY",
    "B0_3_CUSTODIAN_UNAVAILABLE",
    "B0_3_EXECUTION_AUTHORITY_NOT_ISSUED",
    "CONSENT_FORM_NOT_INSTITUTIONALLY_APPROVED",
    "ENCRYPTION_NOT_VERIFIED",
    "INSTITUTIONAL_APPROVAL_NOT_ISSUED",
    "INSTITUTIONAL_REVIEW_ROUTE_NOT_CONFIRMED",
    "LABELBOOK_NOT_FROZEN",
    "M2_DEVICE_EVIDENCE_UNVERIFIED",
    "M3_NOT_OPENED",
    "METHOD_THRESHOLDS_NOT_LOCKED",
    "PRODUCTION_RECONCILER_UNIMPLEMENTED",
    "PROTOCOL_NOT_FROZEN",
    "RESEARCH_COLLECTION_NOT_IMPLEMENTED",
    "RETENTION_DECISION_NOT_ISSUED",
    "STORAGE_ROOT_NOT_APPROVED",
)

EXPECTED_BODY: dict[str, object] = {
    "adv_02_status": "PENDING_EXTERNAL_DECISION",
    "advisor_decision_date": None,
    "advisor_identity_stored": False,
    "advisor_outcome": "READY_FOR_INSTITUTIONAL_ROUTING",
    "advisor_review_gate_status": "SATISFIED_BY_USER_REPORT_UNVERIFIED",
    "authority_effect": "NONE",
    "collection_authorized": False,
    "decision_id": "ADV-01",
    "decision_subject": "PROTOCOL_AND_SCOPE_REVIEW",
    "evidence_classification": "USER_STATED_UNVERIFIED",
    "evidence_mode": "VERBAL_CONFIRMATION_REPORTED_BY_USER",
    "evidence_reference": None,
    "institutional_approval_status": "NOT_ISSUED",
    "institutional_route_confirmed": False,
    "participant_collection_authorized": False,
    "reported_on": "2026-08-31",
    "research_ready": False,
    "submission_state": "NOT_SUBMITTED",
    "written_evidence_available": False,
}


class PackError(ValueError):
    """Bounded validation failure safe for CLI disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: object, *, trailing_newline: bool = True) -> bytes:
    """Return canonical UTF-8 JSON with sorted keys and an optional final LF."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return payload + (b"\n" if trailing_newline else b"")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        stat_result = path.lstat()
    except OSError:
        return False
    attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(os.stat_result, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PackError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _strict_json(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        decoded = payload.decode("utf-8")
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
    except PackError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackError("INVALID_JSON") from exc
    if not isinstance(parsed, dict):
        raise PackError("INVALID_JSON")
    document = cast(dict[str, Any], parsed)
    if payload != canonical_json_bytes(document):
        raise PackError("NONCANONICAL_JSON")
    return document


def _validate_envelope(document: dict[str, Any]) -> dict[str, Any]:
    if set(document) != {
        "artifact_kind",
        "body",
        "body_sha256",
        "schema_version",
        "status",
    }:
        raise PackError("ENVELOPE_INVALID")
    if (
        document["artifact_kind"] != "GOV_P3_ADVISOR_VERBAL_DECISION_RECORD"
        or document["schema_version"] != 1
        or document["status"] != "USER_STATED_UNVERIFIED"
        or not isinstance(document["body"], dict)
        or not isinstance(document["body_sha256"], str)
    ):
        raise PackError("ENVELOPE_INVALID")
    body = cast(dict[str, Any], document["body"])
    actual_hash = _sha256(canonical_json_bytes(body, trailing_newline=False))
    if document["body_sha256"] != actual_hash:
        raise PackError("BODY_HASH_MISMATCH")
    return body


def _validate_record(pack_root: Path) -> None:
    body = _validate_envelope(_strict_json(pack_root / SOURCE_NAME))
    forbidden_authority_fields = {
        "approval_id",
        "approving_unit",
        "institutional_approval_id",
        "issuer",
        "retention_end_date",
        "storage_root",
    }
    if (
        forbidden_authority_fields.intersection(body)
        or body.get("adv_02_status") != "PENDING_EXTERNAL_DECISION"
        or body.get("institutional_route_confirmed") is not False
        or body.get("institutional_approval_status") != "NOT_ISSUED"
        or body.get("authority_effect") != "NONE"
        or body.get("research_ready") is not False
        or body.get("collection_authorized") is not False
        or body.get("participant_collection_authorized") is not False
    ):
        raise PackError("AUTHORITY_CEILING_VIOLATION")
    if body != EXPECTED_BODY:
        raise PackError("ADVISOR_RECORD_INVALID")


def _validate_upstreams() -> None:
    for binding in UPSTREAMS.values():
        expected_path = ROOT / Path(binding.relative_path)
        try:
            if binding.path.resolve(strict=True) != expected_path.resolve(strict=True):
                raise PackError("UPSTREAM_PATH_MISMATCH")
            if _sha256(binding.path.read_bytes()) != binding.sha256:
                raise PackError("UPSTREAM_HASH_MISMATCH")
        except PackError:
            raise
        except OSError as exc:
            raise PackError("UPSTREAM_HASH_MISMATCH") from exc


def _validated_root(pack_root: Path) -> Path:
    try:
        absolute = Path(os.path.abspath(pack_root))
        if _is_reparse(absolute) or not absolute.is_dir():
            raise PackError("PACK_ROOT_INVALID")
        return absolute.resolve(strict=True)
    except PackError:
        raise
    except OSError as exc:
        raise PackError("PACK_ROOT_INVALID") from exc


def _validate_file_set(pack_root: Path, *, require_generated: bool) -> None:
    required = ALL_NAMES if require_generated else frozenset((SOURCE_NAME,))
    try:
        entries = tuple(pack_root.iterdir())
    except OSError as exc:
        raise PackError("FILE_SET_MISMATCH") from exc
    names = frozenset(path.name for path in entries)
    if not required.issubset(names) or not names.issubset(ALL_NAMES):
        raise PackError("FILE_SET_MISMATCH")
    if any(_is_reparse(path) or not path.is_file() for path in entries):
        raise PackError("FILE_SET_MISMATCH")


def _validate_sources(pack_root: Path, *, require_generated: bool) -> Path:
    root = _validated_root(pack_root)
    _validate_file_set(root, require_generated=require_generated)
    _validate_upstreams()
    _validate_record(root)
    return root


def _manifest_document(pack_root: Path) -> dict[str, object]:
    payload = (pack_root / SOURCE_NAME).read_bytes()
    return {
        "artifact_kind": "GOV_P3_ADVISOR_DECISION_MANIFEST",
        "artifacts": [
            {"path": SOURCE_NAME, "sha256": _sha256(payload), "size_bytes": len(payload)}
        ],
        "schema_version": 1,
        "upstream_bindings": {
            name: {"path": binding.relative_path, "sha256": binding.sha256}
            for name, binding in sorted(UPSTREAMS.items())
        },
    }


def _result(manifest_sha256: str) -> dict[str, object]:
    return {
        "advisor_outcome": "READY_FOR_INSTITUTIONAL_ROUTING",
        "advisor_review_status": "SATISFIED_BY_USER_REPORT_UNVERIFIED",
        "authority_ceiling": dict(AUTHORITY_CEILING),
        "blocking_gates": list(BLOCKING_GATES),
        "evidence_classification": "USER_STATED_UNVERIFIED",
        "evidence_mode": "VERBAL_CONFIRMATION_REPORTED_BY_USER",
        "failure_code": None,
        "institutional_approval_status": "NOT_ISSUED",
        "institutional_route_status": "PENDING_EXTERNAL_DECISION",
        "manifest_sha256": manifest_sha256,
        "result": "ADVISOR_DECISION_RECEIPT_VALIDATED",
        "schema_version": 1,
        "status": STATUS,
        "submission_state": "NOT_SUBMITTED",
    }


def _validation_document(manifest_sha256: str) -> dict[str, object]:
    return {"artifact_kind": "GOV_P3_ADVISOR_DECISION_VALIDATION", **_result(manifest_sha256)}


def _write_generated(root: Path, name: str, payload: bytes) -> None:
    target = root / name
    temporary = root / f".{name}.tmp"
    try:
        if target.exists() and (_is_reparse(target) or not target.is_file()):
            raise PackError("OUTPUT_WRITE_FAILED")
        if temporary.exists() or temporary.is_symlink():
            raise PackError("OUTPUT_WRITE_FAILED")
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except PackError:
        raise
    except OSError as exc:
        raise PackError("OUTPUT_WRITE_FAILED") from exc
    finally:
        try:
            if temporary.exists() and not temporary.is_symlink() and temporary.is_file():
                temporary.unlink()
        except OSError:
            pass


def write_pack(pack_root: Path = DEFAULT_PACK_ROOT) -> dict[str, object]:
    """Validate the user-stated record and write fixed generated leaves."""

    root = _validate_sources(Path(pack_root), require_generated=False)
    manifest_bytes = canonical_json_bytes(_manifest_document(root))
    manifest_sha256 = _sha256(manifest_bytes)
    _write_generated(root, MANIFEST_NAME, manifest_bytes)
    _write_generated(
        root,
        VALIDATION_NAME,
        canonical_json_bytes(_validation_document(manifest_sha256)),
    )
    return _result(manifest_sha256)


def check_pack(pack_root: Path = DEFAULT_PACK_ROOT) -> dict[str, object]:
    """Read-only verification of exact GOV-P3 source and generated bytes."""

    root = _validate_sources(Path(pack_root), require_generated=True)
    expected_manifest = canonical_json_bytes(_manifest_document(root))
    try:
        actual_manifest = (root / MANIFEST_NAME).read_bytes()
    except OSError as exc:
        raise PackError("MANIFEST_MISMATCH") from exc
    if actual_manifest != expected_manifest:
        raise PackError("MANIFEST_MISMATCH")
    manifest_sha256 = _sha256(expected_manifest)
    expected_validation = canonical_json_bytes(_validation_document(manifest_sha256))
    try:
        actual_validation = (root / VALIDATION_NAME).read_bytes()
    except OSError as exc:
        raise PackError("VALIDATION_MISMATCH") from exc
    if actual_validation != expected_validation:
        raise PackError("VALIDATION_MISMATCH")
    return _result(manifest_sha256)


def _failure(code: str) -> dict[str, object]:
    return {
        "advisor_outcome": None,
        "advisor_review_status": "UNRECORDED",
        "authority_ceiling": dict(AUTHORITY_CEILING),
        "blocking_gates": list(BLOCKING_GATES),
        "evidence_classification": "USER_STATED_UNVERIFIED",
        "evidence_mode": "VERBAL_CONFIRMATION_REPORTED_BY_USER",
        "failure_code": code,
        "institutional_approval_status": "NOT_ISSUED",
        "institutional_route_status": "PENDING_EXTERNAL_DECISION",
        "manifest_sha256": None,
        "result": "ADVISOR_DECISION_RECEIPT_REJECTED",
        "schema_version": 1,
        "status": "GOV_P3_ADVISOR_DECISION_RECEIPT_REJECTED",
        "submission_state": "NOT_SUBMITTED",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = (
            write_pack(arguments.pack_root)
            if arguments.write
            else check_pack(arguments.pack_root)
        )
    except PackError as exc:
        result = _failure(exc.code)
        exit_code = 2
    except Exception:
        result = _failure("UNEXPECTED_FAILURE")
        exit_code = 2
    else:
        exit_code = 0
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
