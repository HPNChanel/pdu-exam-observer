from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pdu_exam_observer.research_runtime.authority_cli import (
    AuthorityInstallError,
    install_authority,
)
from pdu_exam_observer.research_runtime.service import ResearchRuntimeService


def _write(path: Path, value: bytes) -> str:
    path.write_bytes(value)
    return hashlib.sha256(value).hexdigest()


def _record(
    root: Path, approval: str, consent: str, retention: str, storage: str
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "authority_reference": "study-approval-2026",
        "status": "APPROVED",
        "cohort": "PILOT",
        "protocol_version": "protocol-2026-v1",
        "participant_pseudonym": "participant-9c1d",
        "session_pseudonym": "7bf2ca29-52d1-4b34-a483-23402ef3d38d",
        "native_root_digest": ResearchRuntimeService.root_digest(root),
        "consent_status": "CONFIRMED",
        "consent_policy_sha256": consent,
        "institutional_approval_sha256": approval,
        "retention_record_sha256": retention,
        "retention_expires_at": 4_102_444_800,
        "storage_status": {
            "root_digest": ResearchRuntimeService.root_digest(root),
            "root_validation_state": "OBSERVED",
            "encryption_evidence_state": "USER_ATTESTED",
            "acl_evidence_state": "USER_ATTESTED",
            "evidence_sha256": storage,
        },
    }


def test_installer_writes_only_hash_verified_native_record(tmp_path: Path) -> None:
    root = (tmp_path / "research").resolve()
    root.mkdir()
    approval = _write(tmp_path / "approval.pdf", b"approved-by-human")
    consent = _write(tmp_path / "consent.pdf", b"consent-v1")
    retention = _write(tmp_path / "retention.pdf", b"retention-v1")
    storage = _write(tmp_path / "storage.json", b"native storage attestation")
    installed = install_authority(
        root=root,
        record=_record(root, approval, consent, retention, storage),
        approval_file=tmp_path / "approval.pdf",
        consent_file=tmp_path / "consent.pdf",
        retention_file=tmp_path / "retention.pdf",
        storage_evidence_file=tmp_path / "storage.json",
    )
    destination = root / ".pdu_exam_observer" / "collection-authority.v1.json"
    assert installed == destination
    saved = json.loads(destination.read_text(encoding="utf-8"))
    assert saved["participant_pseudonym"] == "participant-9c1d"
    assert saved["institutional_approval_sha256"] == approval
    assert "approval.pdf" not in destination.read_text(encoding="utf-8")
    with pytest.raises(AuthorityInstallError, match="AUTHORITY_REPLACEMENT_STALE"):
        install_authority(
            root,
            _record(root, approval, consent, retention, storage),
            tmp_path / "approval.pdf",
            tmp_path / "consent.pdf",
            tmp_path / "retention.pdf",
            storage_evidence_file=tmp_path / "storage.json",
        )


def test_atomic_replacement_requires_current_digest_and_preserves_record_on_bad_docs(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "research").resolve()
    root.mkdir()
    approval = _write(tmp_path / "approval.pdf", b"approved")
    consent = _write(tmp_path / "consent.pdf", b"consent")
    retention = _write(tmp_path / "retention.pdf", b"retention")
    storage = _write(tmp_path / "storage.json", b"native storage attestation")
    deletion = _write(tmp_path / "deletion.pdf", b"withdrawal")
    record = _record(root, approval, consent, retention, storage)
    destination = install_authority(
        root,
        record,
        tmp_path / "approval.pdf",
        tmp_path / "consent.pdf",
        tmp_path / "retention.pdf",
        storage_evidence_file=tmp_path / "storage.json",
    )
    original = destination.read_bytes()
    current = hashlib.sha256(original).hexdigest()
    revoked = record | {
        "status": "REVOKED",
        "consent_status": "WITHDRAWN",
        "retention_expires_at": 1,
        "withdrawal_authority_sha256": deletion,
        "withdrawal_decision": "QUARANTINE_RUNTIME_ARTIFACTS",
    }
    with pytest.raises(AuthorityInstallError, match="AUTHORITY_REPLACEMENT_STALE"):
        install_authority(
            root,
            revoked,
            tmp_path / "approval.pdf",
            tmp_path / "consent.pdf",
            tmp_path / "retention.pdf",
            tmp_path / "deletion.pdf",
            storage_evidence_file=tmp_path / "storage.json",
            expected_current_sha256="0" * 64,
        )
    revoked["withdrawal_authority_sha256"] = "0" * 64
    with pytest.raises(AuthorityInstallError, match="DELETION_HASH_MISMATCH"):
        install_authority(
            root,
            revoked,
            tmp_path / "approval.pdf",
            tmp_path / "consent.pdf",
            tmp_path / "retention.pdf",
            tmp_path / "deletion.pdf",
            storage_evidence_file=tmp_path / "storage.json",
            expected_current_sha256=current,
        )
    assert destination.read_bytes() == original


def test_installer_rejects_hash_mismatch_expired_record_and_unsafe_root(tmp_path: Path) -> None:
    root = (tmp_path / "research").resolve()
    root.mkdir()
    approval = _write(tmp_path / "approval.pdf", b"approved-by-human")
    consent = _write(tmp_path / "consent.pdf", b"consent-v1")
    retention = _write(tmp_path / "retention.pdf", b"retention-v1")
    storage = _write(tmp_path / "storage.json", b"native storage attestation")
    record = _record(root, approval, consent, retention, storage)
    record["consent_policy_sha256"] = "0" * 64
    with pytest.raises(AuthorityInstallError, match="CONSENT_HASH_MISMATCH"):
        install_authority(
            root,
            record,
            tmp_path / "approval.pdf",
            tmp_path / "consent.pdf",
            tmp_path / "retention.pdf",
            storage_evidence_file=tmp_path / "storage.json",
        )

    record = _record(root, approval, consent, retention, storage)
    record["retention_expires_at"] = 1
    with pytest.raises(AuthorityInstallError, match="RETENTION_EXPIRED"):
        install_authority(
            root,
            record,
            tmp_path / "approval.pdf",
            tmp_path / "consent.pdf",
            tmp_path / "retention.pdf",
            storage_evidence_file=tmp_path / "storage.json",
        )

    with pytest.raises(AuthorityInstallError, match="ROOT_MUST_BE_ABSOLUTE"):
        install_authority(
            Path("relative"),
            record,
            tmp_path / "approval.pdf",
            tmp_path / "consent.pdf",
            tmp_path / "retention.pdf",
            storage_evidence_file=tmp_path / "storage.json",
        )


def test_installer_accepts_optional_deletion_receipt_only_when_hash_matches(tmp_path: Path) -> None:
    root = (tmp_path / "research").resolve()
    root.mkdir()
    approval = _write(tmp_path / "approval.pdf", b"approved")
    consent = _write(tmp_path / "consent.pdf", b"consent")
    retention = _write(tmp_path / "retention.pdf", b"retention")
    storage = _write(tmp_path / "storage.json", b"native storage attestation")
    deletion = _write(tmp_path / "deletion.pdf", b"withdrawal procedure")
    record = _record(root, approval, consent, retention, storage) | {
        "withdrawal_authority_sha256": deletion,
        "withdrawal_decision": "QUARANTINE_RUNTIME_ARTIFACTS",
    }
    install_authority(
        root,
        record,
        tmp_path / "approval.pdf",
        tmp_path / "consent.pdf",
        tmp_path / "retention.pdf",
        tmp_path / "deletion.pdf",
        storage_evidence_file=tmp_path / "storage.json",
    )
    assert (root / ".pdu_exam_observer" / "collection-authority.v1.json").is_file()
