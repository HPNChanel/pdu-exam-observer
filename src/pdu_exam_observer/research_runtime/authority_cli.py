"""Native-only installation of a byte-bound collection authority record.

This command verifies supplied local documents against a caller-provided
record.  It does not decide whether those documents constitute consent or
institutional approval, and it never accepts values from browser requests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from collections.abc import Mapping
from pathlib import Path

from .service import DEVICE_GATE_DECISIONS, ResearchRuntimeService


class AuthorityInstallError(ValueError):
    pass


_REFERENCE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DESTINATION = Path(".pdu_exam_observer") / "collection-authority.v1.json"


def _digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise AuthorityInstallError("EVIDENCE_FILE_UNAVAILABLE")
    content = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            content.update(block)
    return content.hexdigest()


def _has_reparse_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        attributes = getattr(metadata, "st_file_attributes", 0)
        if bool(attributes & 0x400):
            return True
    return False


def _safe_root(root: Path) -> Path:
    if not root.is_absolute():
        raise AuthorityInstallError("ROOT_MUST_BE_ABSOLUTE")
    if os.name == "nt" and str(root).startswith("\\\\"):
        raise AuthorityInstallError("ROOT_MUST_BE_LOCAL")
    if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
        raise AuthorityInstallError("ROOT_SYMLINK_FORBIDDEN")
    if _has_reparse_component(root):
        raise AuthorityInstallError("ROOT_REPARSE_FORBIDDEN")
    resolved = root.resolve()
    bundle_raw = getattr(sys, "_MEIPASS", None)
    bundle = Path(bundle_raw).resolve() if bundle_raw else None
    package_root = Path(__file__).resolve().parents[2]
    if (
        (bundle is not None and (resolved == bundle or bundle in resolved.parents))
        or resolved == package_root
        or package_root in resolved.parents
    ):
        raise AuthorityInstallError("ROOT_BUNDLE_FORBIDDEN")
    if not resolved.is_dir():
        raise AuthorityInstallError("ROOT_UNAVAILABLE")
    return resolved


def _expect(record: Mapping[str, object], field: str, actual: str, code: str) -> None:
    value = record.get(field)
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value != actual:
        raise AuthorityInstallError(code)


def _validate_record(root: Path, record: Mapping[str, object]) -> dict[str, object]:
    required = {
        "schema_version",
        "authority_reference",
        "status",
        "cohort",
        "protocol_version",
        "participant_pseudonym",
        "session_pseudonym",
        "native_root_digest",
        "consent_status",
        "consent_policy_sha256",
        "institutional_approval_sha256",
        "retention_record_sha256",
        "retention_expires_at",
        "consent_receipt_id",
        "consent_version",
        "operator_pseudonym",
        "device_gate_decision",
    }
    if not required.issubset(record) or record.get("schema_version") != 1:
        raise AuthorityInstallError("RECORD_SCHEMA_INVALID")
    reference = record.get("authority_reference")
    participant = record.get("participant_pseudonym")
    session = record.get("session_pseudonym")
    if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
        raise AuthorityInstallError("AUTHORITY_REFERENCE_INVALID")
    if not isinstance(participant, str) or not _REFERENCE.fullmatch(participant):
        raise AuthorityInstallError("PARTICIPANT_PSEUDONYM_INVALID")
    if record.get("cohort") not in {"PILOT", "CONFIRMATORY"}:
        raise AuthorityInstallError("COHORT_INVALID")
    protocol_version = record.get("protocol_version")
    if not isinstance(protocol_version, str) or not _REFERENCE.fullmatch(protocol_version):
        raise AuthorityInstallError("PROTOCOL_VERSION_INVALID")
    for field in ("consent_receipt_id", "consent_version", "operator_pseudonym"):
        value = record.get(field)
        if not isinstance(value, str) or not _REFERENCE.fullmatch(value):
            raise AuthorityInstallError(f"{field.upper()}_INVALID")
    # The recorded gate outcome must be an honest vocabulary value; a
    # fabricated GO is not accepted at install or at collection time.
    if record.get("device_gate_decision") not in DEVICE_GATE_DECISIONS:
        raise AuthorityInstallError("DEVICE_GATE_DECISION_INVALID")
    if not isinstance(session, str):
        raise AuthorityInstallError("SESSION_PSEUDONYM_INVALID")
    try:
        uuid.UUID(session)
    except ValueError as exc:
        raise AuthorityInstallError("SESSION_PSEUDONYM_INVALID") from exc
    status = record.get("status")
    consent_status = record.get("consent_status")
    if status not in {"APPROVED", "REVOKED"} or consent_status not in {"CONFIRMED", "WITHDRAWN"}:
        raise AuthorityInstallError("AUTHORITY_STATUS_INVALID")
    if status == "REVOKED" and consent_status != "WITHDRAWN":
        raise AuthorityInstallError("REVOCATION_CONSENT_INVALID")
    if record.get("native_root_digest") != ResearchRuntimeService.root_digest(root):
        raise AuthorityInstallError("ROOT_BINDING_INVALID")
    expiry = record.get("retention_expires_at")
    deletion_purpose = (
        record.get("withdrawal_decision")
        in {"DELETE_OWNED_RUNTIME_ARTIFACTS", "QUARANTINE_RUNTIME_ARTIFACTS"}
        and _SHA256.fullmatch(str(record.get("withdrawal_authority_sha256", ""))) is not None
    )
    if consent_status == "WITHDRAWN" and not deletion_purpose:
        raise AuthorityInstallError("WITHDRAWAL_PURPOSE_REQUIRED")
    if not isinstance(expiry, int | float) or (
        float(expiry) <= time.time() and not deletion_purpose
    ):
        raise AuthorityInstallError("RETENTION_EXPIRED")
    result = dict(record)
    return result


def install_authority(
    root: Path,
    record: Mapping[str, object],
    approval_file: Path,
    consent_file: Path,
    retention_file: Path,
    deletion_file: Path | None = None,
    *,
    storage_evidence_file: Path,
    expected_current_sha256: str | None = None,
) -> Path:
    """Verify local source bytes and atomically install the fixed authority record."""
    root = _safe_root(Path(root))
    installed = _validate_record(root, record)
    _expect(
        installed, "institutional_approval_sha256", _digest(approval_file), "APPROVAL_HASH_MISMATCH"
    )
    _expect(installed, "consent_policy_sha256", _digest(consent_file), "CONSENT_HASH_MISMATCH")
    _expect(
        installed, "retention_record_sha256", _digest(retention_file), "RETENTION_HASH_MISMATCH"
    )
    storage = installed.get("storage_status")
    if not isinstance(storage, Mapping):
        raise AuthorityInstallError("STORAGE_STATUS_INVALID")
    if storage.get("root_digest") != ResearchRuntimeService.root_digest(root):
        raise AuthorityInstallError("STORAGE_ROOT_BINDING_INVALID")
    if storage.get("root_validation_state") != "OBSERVED":
        raise AuthorityInstallError("STORAGE_ROOT_PROOF_INVALID")
    states = {"USER_ATTESTED", "OBSERVED"}
    if (
        storage.get("encryption_evidence_state") not in states
        or storage.get("acl_evidence_state") not in states
    ):
        raise AuthorityInstallError("STORAGE_EVIDENCE_STATE_INVALID")
    _expect(storage, "evidence_sha256", _digest(storage_evidence_file), "STORAGE_HASH_MISMATCH")
    if deletion_file is None:
        if "withdrawal_authority_sha256" in installed or "withdrawal_decision" in installed:
            raise AuthorityInstallError("DELETION_FILE_REQUIRED")
    else:
        decision = installed.get("withdrawal_decision")
        if decision not in {"DELETE_OWNED_RUNTIME_ARTIFACTS", "QUARANTINE_RUNTIME_ARTIFACTS"}:
            raise AuthorityInstallError("WITHDRAWAL_DECISION_INVALID")
        _expect(
            installed,
            "withdrawal_authority_sha256",
            _digest(deletion_file),
            "DELETION_HASH_MISMATCH",
        )
    destination = root / _DESTINATION
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    if destination.is_symlink() or _has_reparse_component(destination.parent):
        raise AuthorityInstallError("DESTINATION_UNSAFE")
    if destination.exists():
        actual = _digest(destination)
        if (
            expected_current_sha256 is None
            or _SHA256.fullmatch(expected_current_sha256) is None
            or expected_current_sha256 != actual
        ):
            raise AuthorityInstallError("AUTHORITY_REPLACEMENT_STALE")
    elif expected_current_sha256 is not None:
        raise AuthorityInstallError("AUTHORITY_REPLACEMENT_STALE")
    temporary = destination.with_name(destination.name + ".partial")
    if temporary.exists():
        temporary.unlink()
    payload = json.dumps(installed, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(destination)
    return destination


def _record_argument(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AuthorityInstallError("RECORD_JSON_INVALID") from exc
    if not isinstance(parsed, dict):
        raise AuthorityInstallError("RECORD_JSON_INVALID")
    return parsed


def authority_template(root: Path, session_id: str) -> dict[str, object]:
    """Return a non-authorizing draft record for an already-created session."""
    root = _safe_root(root)
    try:
        session = str(uuid.UUID(session_id))
    except ValueError as exc:
        raise AuthorityInstallError("SESSION_PSEUDONYM_INVALID") from exc
    return {
        "schema_version": 1,
        "authority_reference": "REPLACE_WITH_NATIVE_REFERENCE",
        "status": "DRAFT",
        "cohort": "REPLACE_WITH_PILOT_OR_CONFIRMATORY",
        "protocol_version": "REPLACE_WITH_FROZEN_PROTOCOL_VERSION",
        "participant_pseudonym": "REPLACE_WITH_PSEUDONYM",
        "session_pseudonym": session,
        "native_root_digest": ResearchRuntimeService.root_digest(root),
        "consent_status": "DRAFT",
        "consent_receipt_id": "REPLACE_WITH_RECEIPT_ID",
        "consent_version": "REPLACE_WITH_CONSENT_VERSION",
        "operator_pseudonym": "REPLACE_WITH_OPERATOR_PSEUDONYM",
        "device_gate_decision": "UNVERIFIED",
        "consent_policy_sha256": "REPLACE_WITH_SHA256",
        "institutional_approval_sha256": "REPLACE_WITH_SHA256",
        "retention_record_sha256": "REPLACE_WITH_SHA256",
        "retention_expires_at": "REPLACE_WITH_UTC_EPOCH",
        "storage_status": {
            "root_digest": ResearchRuntimeService.root_digest(root),
            "root_validation_state": "OBSERVED",
            "encryption_evidence_state": "REPLACE_WITH_USER_ATTESTED_OR_OBSERVED",
            "acl_evidence_state": "REPLACE_WITH_USER_ATTESTED_OR_OBSERVED",
            "evidence_sha256": "REPLACE_WITH_SHA256",
        },
    }


def template_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdu-exam-observer authority-template")
    parser.add_argument("--root", required=True)
    parser.add_argument("--session-id", required=True)
    arguments = parser.parse_args(argv)
    try:
        print(json.dumps(authority_template(Path(arguments.root), arguments.session_id)))
    except AuthorityInstallError as exc:
        parser.error(str(exc))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdu-exam-observer install-authority")
    parser.add_argument("--root", required=True)
    parser.add_argument("--record", required=True, help="native JSON authority record")
    parser.add_argument("--approval-file", required=True)
    parser.add_argument("--consent-file", required=True)
    parser.add_argument("--retention-file", required=True)
    parser.add_argument("--storage-evidence-file", required=True)
    parser.add_argument("--deletion-file")
    parser.add_argument("--expected-current-sha256")
    arguments = parser.parse_args(argv)
    try:
        destination = install_authority(
            Path(arguments.root),
            _record_argument(arguments.record),
            Path(arguments.approval_file),
            Path(arguments.consent_file),
            Path(arguments.retention_file),
            Path(arguments.deletion_file) if arguments.deletion_file else None,
            storage_evidence_file=Path(arguments.storage_evidence_file),
            expected_current_sha256=arguments.expected_current_sha256,
        )
    except AuthorityInstallError as exc:
        parser.error(str(exc))
    print(json.dumps({"installed": True, "authority_record": str(destination)}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
