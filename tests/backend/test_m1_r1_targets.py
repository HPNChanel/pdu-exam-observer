from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m1 import M1Store
from pdu_exam_observer.m1_r1 import (
    M1R1Backend,
    MigrationAuthority,
    ResearchStoreV3,
    TargetRegistrationError,
    check_migration_readiness,
    migrate_to_v3,
)
from pdu_exam_observer.m2_persistence import ArtifactIntent, StaticArtifactSource


@dataclass(frozen=True)
class _Authority:
    root_identity_digest: str
    readiness_digest: str

    def permits_migration(self, *, root_identity_digest: str, readiness_digest: str) -> bool:
        return (
            root_identity_digest == self.root_identity_digest
            and readiness_digest == self.readiness_digest
        )


def _v3(root: Path) -> ResearchStoreV3:
    legacy = M1Store(root)
    legacy.close()
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _Authority(
        readiness.root_identity_digest, readiness.readiness_digest
    )
    return migrate_to_v3(
        root,
        expected_readiness_digest=readiness.readiness_digest,
        authority=authority,
    )


def _research(backend: M1R1Backend, code: str) -> tuple[str, str]:
    study = backend.create_study(code, idempotency_key=f"study-{code}")
    participant = backend.create_participant(
        str(study["study_id"]), idempotency_key=f"participant-{code}"
    )
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key=f"session-{code}",
        retention_policy_reference="synthetic-policy",
    )
    return str(participant["participant_id"]), str(session["session_id"])


def _intent(artifact_id: str, session_id: str) -> ArtifactIntent:
    return ArtifactIntent(
        intent_id=f"intent-{artifact_id}",
        artifact_id=artifact_id,
        session_id=session_id,
        artifact_kind="TECHNICAL_FIXTURE",
        technical_input_kind="DETERMINISTIC_FIXTURE",
        capture_profile_version="fixture-profile-v1",
        monotonic_timing_origin="synthetic-monotonic-v1",
        processing_version="fixture-generator-v1",
    )


def test_v3_rejects_legacy_valid_artifact_registration_without_targets(tmp_path: Path) -> None:
    store = _v3(tmp_path / "root")
    backend = M1R1Backend(
        store.root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    _participant_id, session_id = _research(backend, "target-required")
    try:
        with pytest.raises(InvalidTransition, match="TARGET_REGISTRATION_REQUIRED"):
            backend.register_artifact("artifact-no-target", session_id)
        assert store.connection.execute(
            "SELECT 1 FROM artifact_registry WHERE id='artifact-no-target'"
        ).fetchone() is None
    finally:
        store.close()


def test_sealing_atomically_registers_one_server_derived_local_target(tmp_path: Path) -> None:
    store = _v3(tmp_path / "root")
    backend = M1R1Backend(
        store.root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    _participant_id, session_id = _research(backend, "local-target")
    try:
        store.persist(_intent("artifact-local", session_id), StaticArtifactSource(b"fixture"))
        row = store.connection.execute(
            "SELECT target_kind,root_scope,relative_path,export_id,expected_byte_size,"
            "expected_sha256,manifest_sha256,registration_version "
            "FROM reconciliation_targets WHERE artifact_id='artifact-local'"
        ).fetchone()
        assert row is not None
        assert row["target_kind"] == "LOCAL_RESEARCH_FILE"
        assert row["root_scope"] == "RESEARCH_ROOT"
        assert row["relative_path"] == "artifacts/m2/artifact-local.bin"
        assert row["export_id"] is None
        assert row["expected_byte_size"] == 7
        assert len(row["expected_sha256"]) == 64
        assert len(row["manifest_sha256"]) == 64
        assert row["registration_version"] == 1
        assert str(store.root).casefold() not in str(tuple(row)).casefold()
    finally:
        store.close()


def test_external_target_accepts_only_opaque_export_binding_and_is_idempotent(
    tmp_path: Path,
) -> None:
    store = _v3(tmp_path / "root")
    backend = M1R1Backend(
        store.root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    _participant_id, session_id = _research(backend, "external-target")
    try:
        store.persist(_intent("artifact-external", session_id), StaticArtifactSource(b"fixture"))
        manifest = store.manifest("artifact-external")
        manifest_sha256 = store.manifest_binding_sha256("artifact-external")
        first = store.register_external_target(
            "artifact-external",
            export_id="export-001",
            manifest_sha256=manifest_sha256,
        )
        assert store.register_external_target(
            "artifact-external",
            export_id="export-001",
            manifest_sha256=manifest_sha256,
        ) == first
        assert manifest["sha256"]
        with pytest.raises(TargetRegistrationError, match="invalid export id"):
            store.register_external_target(
                "artifact-external",
                export_id="../outside",
                manifest_sha256=manifest_sha256,
            )
        with pytest.raises(TargetRegistrationError, match="manifest binding"):
            store.register_external_target(
                "artifact-external",
                export_id="export-002",
                manifest_sha256="0" * 64,
            )
    finally:
        store.close()


def test_local_target_casefold_collision_is_rejected_before_file_replacement(
    tmp_path: Path,
) -> None:
    store = _v3(tmp_path / "root")
    backend = M1R1Backend(
        store.root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    _participant_id, session_id = _research(backend, "casefold")
    try:
        store.persist(_intent("Artifact-Case", session_id), StaticArtifactSource(b"first"))
        first_path = store.root / "artifacts" / "m2" / "Artifact-Case.bin"
        assert first_path.read_bytes() == b"first"

        with pytest.raises(TargetRegistrationError, match="case-fold collision"):
            store.persist(_intent("artifact-case", session_id), StaticArtifactSource(b"second"))

        assert first_path.read_bytes() == b"first"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM artifact_registry WHERE lower(id)=lower('artifact-case')"
        ).fetchone()[0] == 1
    finally:
        store.close()


def test_withdrawal_maps_every_registered_target_in_the_same_transaction(tmp_path: Path) -> None:
    store = _v3(tmp_path / "root")
    backend = M1R1Backend(
        store.root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    participant_id, session_id = _research(backend, "withdraw-map")
    try:
        store.persist(_intent("artifact-map", session_id), StaticArtifactSource(b"fixture"))
        manifest_sha256 = store.manifest_binding_sha256("artifact-map")
        store.register_external_target(
            "artifact-map", export_id="export-map", manifest_sha256=manifest_sha256
        )

        receipt = backend.withdraw(session_id, idempotency_key="withdraw-map")
        rows = store.connection.execute(
            "SELECT wtt.participant_id,wtt.withdrawal_receipt_id,wtt.target_kind,wtt.root_scope,"
            "wtt.state,wt.status FROM withdrawal_task_targets wtt "
            "JOIN withdrawal_tasks wt ON wt.id=wtt.withdrawal_task_id "
            "ORDER BY wtt.target_kind"
        ).fetchall()
        assert receipt["terminal"] is True
        assert len(rows) == 2
        assert {row["target_kind"] for row in rows} == {
            "LOCAL_RESEARCH_FILE",
            "EXTERNAL_COPY",
        }
        assert all(row["participant_id"] == participant_id for row in rows)
        assert all(row["withdrawal_receipt_id"] == receipt["withdrawal_receipt_id"] for row in rows)
        assert all(row["state"] == "PENDING_CONFIRMATION" for row in rows)
        assert all(row["status"] == "PENDING" for row in rows)
    finally:
        store.close()


def test_missing_target_never_rolls_back_terminal_withdrawal(tmp_path: Path) -> None:
    store = _v3(tmp_path / "root")
    backend = M1R1Backend(
        store.root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    participant_id, session_id = _research(backend, "missing-target")
    try:
        with store.transaction() as connection:
            connection.execute(
                "INSERT INTO artifact_registry(id,session_id,status,created_at) "
                "VALUES('legacy-without-target',?,'VALID',0)",
                (session_id,),
            )

        receipt = backend.withdraw(session_id, idempotency_key="withdraw-missing")
        assert receipt["terminal"] is True
        assert store.connection.execute(
            "SELECT withdrawn_at FROM participants WHERE id=?", (participant_id,)
        ).fetchone()[0] is not None
        assert store.connection.execute(
            "SELECT status FROM withdrawal_tasks WHERE artifact_id='legacy-without-target'"
        ).fetchone()[0] == "PENDING"
        assert store.connection.execute(
            "SELECT 1 FROM withdrawal_task_targets WHERE target_id IN "
            "(SELECT id FROM reconciliation_targets WHERE artifact_id='legacy-without-target')"
        ).fetchone() is None
    finally:
        store.close()


def test_cross_participant_withdrawal_target_mapping_is_rejected_by_v3_constraints(
    tmp_path: Path,
) -> None:
    store = _v3(tmp_path / "root")
    backend = M1R1Backend(
        store.root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    _participant_a, session_a = _research(backend, "participant-a")
    participant_b, _session_b = _research(backend, "participant-b")
    try:
        store.persist(_intent("artifact-a", session_a), StaticArtifactSource(b"fixture"))
        receipt = backend.withdraw(session_a, idempotency_key="withdraw-a")
        mapping = store.connection.execute(
            "SELECT * FROM withdrawal_task_targets"
        ).fetchone()
        assert mapping is not None
        with pytest.raises(sqlite3.IntegrityError):
            with store.transaction() as connection:
                connection.execute(
                    "UPDATE withdrawal_task_targets SET participant_id=? "
                    "WHERE withdrawal_task_id=? AND target_id=?",
                    (participant_b, mapping["withdrawal_task_id"], mapping["target_id"]),
                )
        assert receipt["terminal"] is True
    finally:
        store.close()
