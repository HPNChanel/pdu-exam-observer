from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from pdu_exam_observer.m1 import M1Store, SchemaIntegrityError
from pdu_exam_observer.m1_r1 import (
    M1R1Backend,
    MigrationAuthority,
    ResearchStoreV3,
    check_migration_readiness,
    migrate_to_v3,
)
from pdu_exam_observer.m2_persistence import ArtifactIntent, StaticArtifactSource
from pdu_exam_observer.reconciliation import (
    ConfirmationService,
    ReconciliationBlocked,
    ReconciliationPlanner,
)
from pdu_exam_observer.reconciliation_execution import (
    DeletionBlocked,
    DeletionOutcome,
    ExecutionAuthority,
    LocalDeletionTarget,
    PredeleteSnapshot,
    ReconciliationAuthorityNotIssued,
    ReconciliationCoordinator,
    ReconciliationFinalizer,
    WindowsHandleDeletionPrimitive,
)
from pdu_exam_observer.services.core import ReviewerAuthenticator


def _target(root: Path, relative_path: str, payload: bytes) -> LocalDeletionTarget:
    del root
    return LocalDeletionTarget(
        target_id="target-synthetic",
        root_scope="RESEARCH_ROOT",
        relative_path=relative_path,
        expected_byte_size=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_retained_handle_deletes_only_exact_verified_leaf_and_preserves_sentinel(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    artifact_dir = root / "artifacts" / "m2"
    artifact_dir.mkdir(parents=True)
    payload = b"synthetic-owned-target"
    owned = artifact_dir / "owned.bin"
    sentinel = artifact_dir / "sentinel.bin"
    owned.write_bytes(payload)
    sentinel.write_bytes(b"must-survive")
    snapshots: list[object] = []

    outcome = WindowsHandleDeletionPrimitive(root).delete(
        _target(root, "artifacts/m2/owned.bin", payload),
        on_verified=snapshots.append,
    )

    assert outcome.absence_verified is True
    assert len(snapshots) == 1
    assert snapshots[0].byte_size == len(payload)
    assert snapshots[0].sha256 == hashlib.sha256(payload).hexdigest()
    assert not owned.exists()
    assert sentinel.read_bytes() == b"must-survive"


def test_parent_handles_remain_held_through_absence_verification(tmp_path: Path) -> None:
    root = tmp_path / "root"
    artifact_dir = root / "artifacts" / "m2"
    artifact_dir.mkdir(parents=True)
    payload = b"synthetic-owned-target"
    owned = artifact_dir / "owned.bin"
    owned.write_bytes(payload)
    rename_results: list[int] = []

    def attempt_parent_rename(parent: Path) -> None:
        script = (
            "import os,sys; os.rename(sys.argv[1], sys.argv[1] + '-replacement')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script, str(parent)],
            check=False,
            capture_output=True,
        )
        rename_results.append(completed.returncode)

    outcome = WindowsHandleDeletionPrimitive(
        root, before_absence_check=attempt_parent_rename
    ).delete(
        _target(root, "artifacts/m2/owned.bin", payload),
        on_verified=lambda _snapshot: None,
    )

    assert outcome.absence_verified is True
    assert rename_results and rename_results[0] != 0
    assert artifact_dir.is_dir()
    assert not artifact_dir.with_name("m2-replacement").exists()


def test_hash_mismatch_and_multiple_hard_links_fail_before_disposition(tmp_path: Path) -> None:
    root = tmp_path / "root"
    artifact_dir = root / "artifacts" / "m2"
    artifact_dir.mkdir(parents=True)
    payload = b"synthetic-owned-target"
    owned = artifact_dir / "owned.bin"
    owned.write_bytes(payload)
    wrong = LocalDeletionTarget(
        target_id="target-wrong-hash",
        root_scope="RESEARCH_ROOT",
        relative_path="artifacts/m2/owned.bin",
        expected_byte_size=len(payload),
        expected_sha256="0" * 64,
    )

    with pytest.raises(DeletionBlocked, match="TARGET_HASH_MISMATCH"):
        WindowsHandleDeletionPrimitive(root).delete(wrong, on_verified=lambda _snapshot: None)
    assert owned.read_bytes() == payload

    alias = artifact_dir / "alias.bin"
    os.link(owned, alias)
    with pytest.raises(DeletionBlocked, match="TARGET_MULTIPLE_LINKS"):
        WindowsHandleDeletionPrimitive(root).delete(
            _target(root, "artifacts/m2/owned.bin", payload),
            on_verified=lambda _snapshot: None,
        )
    assert owned.read_bytes() == payload
    assert alias.read_bytes() == payload


def test_replacement_attempt_while_retained_handle_is_open_cannot_redirect_delete(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    artifact_dir = root / "artifacts" / "m2"
    artifact_dir.mkdir(parents=True)
    payload = b"synthetic-owned-target"
    owned = artifact_dir / "owned.bin"
    replacement = artifact_dir / "replacement.bin"
    owned.write_bytes(payload)
    replacement.write_bytes(b"replacement")

    def attempt_replacement(_snapshot: object) -> None:
        os.replace(replacement, owned)

    with pytest.raises(DeletionBlocked, match="VERIFIED_CALLBACK_FAILED"):
        WindowsHandleDeletionPrimitive(root).delete(
            _target(root, "artifacts/m2/owned.bin", payload),
            on_verified=attempt_replacement,
        )
    assert owned.read_bytes() == payload
    assert replacement.read_bytes() == b"replacement"


@dataclass(frozen=True)
class _MigrationAuthority:
    root_identity_digest: str
    readiness_digest: str

    def permits_migration(self, *, root_identity_digest: str, readiness_digest: str) -> bool:
        return (
            root_identity_digest == self.root_identity_digest
            and readiness_digest == self.readiness_digest
        )


@dataclass(frozen=True)
class _ExecutionAuthority:
    root_identity_digest: str
    execution_id: str
    plan_sha256: str
    target_ids: tuple[str, ...]

    def permits_execution(
        self,
        *,
        root_identity_digest: str,
        execution_id: str,
        plan_sha256: str,
        target_ids: tuple[str, ...],
    ) -> bool:
        return (
            root_identity_digest == self.root_identity_digest
            and execution_id == self.execution_id
            and plan_sha256 == self.plan_sha256
            and target_ids == self.target_ids
        )


def _coordinator_system(
    tmp_path: Path,
) -> tuple[ResearchStoreV3, M1R1Backend, ConfirmationService, str, str, Path]:
    root = tmp_path / "coordinator-root"
    M1Store(root).close()
    readiness = check_migration_readiness(root)
    migration_authority: MigrationAuthority = _MigrationAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )
    store = migrate_to_v3(
        root,
        expected_readiness_digest=readiness.readiness_digest,
        authority=migration_authority,
    )
    backend = M1R1Backend(
        root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    study = backend.create_study("coordinator", idempotency_key="study-coordinator")
    participant = backend.create_participant(
        str(study["study_id"]), idempotency_key="participant-coordinator"
    )
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key="session-coordinator",
        retention_policy_reference="synthetic-policy",
    )
    session_id = str(session["session_id"])
    store.persist(
        ArtifactIntent(
            intent_id="intent-coordinator",
            artifact_id="artifact-coordinator",
            session_id=session_id,
            artifact_kind="TECHNICAL_FIXTURE",
            technical_input_kind="DETERMINISTIC_FIXTURE",
            capture_profile_version="fixture-profile-v1",
            monotonic_timing_origin="synthetic-monotonic-v1",
            processing_version="fixture-generator-v1",
        ),
        StaticArtifactSource(b"coordinator-fixture"),
    )
    backend.withdraw(session_id, idempotency_key="withdraw-coordinator")
    token = backend.issue_reviewer_token()
    confirmation = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
    )
    sentinel = root / "sentinel.bin"
    sentinel.write_bytes(b"survive")
    return store, backend, confirmation, token, session_id, sentinel


def test_coordinator_requires_bound_authority_then_deletes_and_finalizes_atomically(
    tmp_path: Path,
) -> None:
    store, _backend, confirmation, token, session_id, sentinel = _coordinator_system(
        tmp_path
    )
    try:
        issued = confirmation.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="coordinator-tab",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )
        consumed = confirmation.consume_challenge(
            session_id=session_id,
            reviewer_token=token,
            challenge_token=issued.challenge_token,
            confirmation_phrase=issued.confirmation_phrase,
        )
        coordinator = ReconciliationCoordinator(store)
        target = store.connection.execute(
            "SELECT relative_path FROM reconciliation_targets "
            "WHERE target_kind='LOCAL_RESEARCH_FILE'"
        ).fetchone()
        owned = store.root.joinpath(*str(target["relative_path"]).split("/"))

        with pytest.raises(ReconciliationAuthorityNotIssued, match="AUTHORITY_NOT_ISSUED"):
            coordinator.run_local(consumed, authority=None)
        assert owned.is_file()
        binding = coordinator.authority_binding(consumed)
        authority: ExecutionAuthority = _ExecutionAuthority(
            binding.root_identity_digest,
            binding.execution_id,
            binding.plan_sha256,
            binding.target_ids,
        )
        run = coordinator.run_local(consumed, authority=authority)

        assert run["state"] == "COMPLETED"
        assert not owned.exists()
        assert sentinel.read_bytes() == b"survive"
        assert store.connection.execute(
            "SELECT state FROM withdrawal_task_targets"
        ).fetchone()[0] == "LOCAL_DELETION_VERIFIED"
        assert store.connection.execute(
            "SELECT stage FROM reconciliation_attempts"
        ).fetchone()[0] == "ABSENCE_VERIFIED"

        receipt = ReconciliationFinalizer(store).finalize(session_id)
        replay = ReconciliationFinalizer(store).finalize(session_id)
        assert receipt == replay
        assert receipt.body["complete"] is True
        assert receipt.body["local_deletion_verified_total"] == 1
        assert store.connection.execute(
            "SELECT status FROM withdrawal_tasks"
        ).fetchone()[0] == "COMPLETED"
        assert store.connection.execute(
            "SELECT body_sha256 FROM reconciliation_receipts"
        ).fetchone()[0] == receipt.body_sha256
    finally:
        store.close()


def test_finalizer_rejects_a_canonical_rehashed_but_forged_existing_receipt(
    tmp_path: Path,
) -> None:
    store, _backend, _confirmation, _token, session_id, sentinel = _coordinator_system(
        tmp_path
    )
    try:
        forged_body = {
            "complete": True,
            "receipt_schema_version": 1,
            "arbitrary": "forged",
        }
        canonical = json.dumps(forged_body, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        subject = store.connection.execute(
            "SELECT s.participant_id,wr.id withdrawal_receipt_id FROM sessions s "
            "JOIN withdrawal_receipts wr ON wr.subject_session_id=s.id WHERE s.id=?",
            (session_id,),
        ).fetchone()
        with store.transaction() as connection:
            connection.execute(
                "INSERT INTO reconciliation_receipts("
                "id,participant_id,withdrawal_receipt_id,body_json,body_sha256,created_at) "
                "VALUES('forged-receipt',?,?,?,?,0)",
                (
                    subject["participant_id"],
                    subject["withdrawal_receipt_id"],
                    canonical,
                    digest,
                ),
            )

        with pytest.raises(SchemaIntegrityError, match="receipt .*invalid"):
            ReconciliationFinalizer(store).finalize(session_id)
        assert sentinel.read_bytes() == b"survive"
        assert store.connection.execute(
            "SELECT status FROM withdrawal_tasks"
        ).fetchone()[0] == "PENDING"
    finally:
        store.close()


def test_interrupted_run_is_marked_recovery_required_on_reopen_without_deletion(
    tmp_path: Path,
) -> None:
    store, _backend, confirmation, token, session_id, sentinel = _coordinator_system(
        tmp_path
    )
    issued = confirmation.create_challenge(
        session_id=session_id,
        reviewer_token=token,
        pin="123456",
        client_key="recovery-tab",
        action="EXECUTE_LOCAL_RECONCILIATION",
        target_id=None,
    )
    consumed = confirmation.consume_challenge(
        session_id=session_id,
        reviewer_token=token,
        challenge_token=issued.challenge_token,
        confirmation_phrase=issued.confirmation_phrase,
    )
    coordinator = ReconciliationCoordinator(
        store,
        fault_hook=lambda stage: (_ for _ in ()).throw(RuntimeError("crash"))
        if stage == "after_run_created"
        else None,
    )
    binding = coordinator.authority_binding(consumed)
    authority: ExecutionAuthority = _ExecutionAuthority(
        binding.root_identity_digest,
        binding.execution_id,
        binding.plan_sha256,
        binding.target_ids,
    )
    target = store.connection.execute(
        "SELECT relative_path FROM reconciliation_targets WHERE target_kind='LOCAL_RESEARCH_FILE'"
    ).fetchone()
    owned = store.root.joinpath(*str(target["relative_path"]).split("/"))
    with pytest.raises(RuntimeError, match="crash"):
        coordinator.run_local(consumed, authority=authority)
    assert owned.is_file()
    root = store.root
    store.close()

    reopened = ResearchStoreV3(root)
    try:
        assert reopened.connection.execute(
            "SELECT state FROM reconciliation_runs"
        ).fetchone()[0] == "RECOVERY_REQUIRED"
        assert reopened.connection.execute(
            "SELECT state FROM withdrawal_task_targets"
        ).fetchone()[0] == "RECOVERY_REQUIRED"
        assert owned.is_file()
        assert sentinel.read_bytes() == b"survive"

        reopened_backend = M1R1Backend(
            root,
            store=reopened,
            encryption_status="VERIFIED",
            acl_status="VERIFIED",
        )
        recovery_token = reopened_backend.issue_reviewer_token()
        recovery_confirmation = ConfirmationService(
            store=reopened,
            planner=ReconciliationPlanner(reopened),
            authenticator=ReviewerAuthenticator("123456"),
            reviewer_session_digest=reopened_backend.reviewer_session_digest,
        )
        recovery_challenge = recovery_confirmation.create_challenge(
            session_id=session_id,
            reviewer_token=recovery_token,
            pin="123456",
            client_key="recovery-confirmation-tab",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )
        recovery_consumed = recovery_confirmation.consume_challenge(
            session_id=session_id,
            reviewer_token=recovery_token,
            challenge_token=recovery_challenge.challenge_token,
            confirmation_phrase=recovery_challenge.confirmation_phrase,
        )
        recovery_coordinator = ReconciliationCoordinator(reopened)
        with pytest.raises(ReconciliationBlocked, match="RECOVERY_SNAPSHOT_REQUIRED"):
            recovery_coordinator.authority_binding(recovery_consumed)
        assert owned.is_file()
        assert sentinel.read_bytes() == b"survive"
    finally:
        reopened.close()


def test_recovery_never_deletes_a_same_bytes_replacement_after_snapshot(
    tmp_path: Path,
) -> None:
    store, _backend, confirmation, token, session_id, sentinel = _coordinator_system(
        tmp_path
    )
    issued = confirmation.create_challenge(
        session_id=session_id,
        reviewer_token=token,
        pin="123456",
        client_key="snapshot-crash-tab",
        action="EXECUTE_LOCAL_RECONCILIATION",
        target_id=None,
    )
    consumed = confirmation.consume_challenge(
        session_id=session_id,
        reviewer_token=token,
        challenge_token=issued.challenge_token,
        confirmation_phrase=issued.confirmation_phrase,
    )
    target_row = store.connection.execute(
        "SELECT relative_path FROM reconciliation_targets "
        "WHERE target_kind='LOCAL_RESEARCH_FILE'"
    ).fetchone()
    owned = store.root.joinpath(*str(target_row["relative_path"]).split("/"))
    original_bytes = owned.read_bytes()

    class _CrashAfterSnapshot:
        def __init__(self, root: Path) -> None:
            self.delegate = WindowsHandleDeletionPrimitive(root)

        def delete(
            self,
            target: LocalDeletionTarget,
            *,
            on_verified: Callable[[PredeleteSnapshot], None],
        ) -> DeletionOutcome:
            def persist_then_crash(snapshot: PredeleteSnapshot) -> None:
                on_verified(snapshot)
                raise SystemExit("synthetic crash after durable snapshot")

            return self.delegate.delete(target, on_verified=persist_then_crash)

    crashing = ReconciliationCoordinator(store, primitive=_CrashAfterSnapshot(store.root))  # type: ignore[arg-type]
    binding = crashing.authority_binding(consumed)
    authority: ExecutionAuthority = _ExecutionAuthority(
        binding.root_identity_digest,
        binding.execution_id,
        binding.plan_sha256,
        binding.target_ids,
    )
    with pytest.raises(SystemExit, match="synthetic crash"):
        crashing.run_local(consumed, authority=authority)
    root = store.root
    store.close()

    owned.unlink()
    owned.write_bytes(original_bytes)
    reopened = ResearchStoreV3(root)
    try:
        backend = M1R1Backend(
            root,
            store=reopened,
            encryption_status="VERIFIED",
            acl_status="VERIFIED",
        )
        recovery_token = backend.issue_reviewer_token()
        service = ConfirmationService(
            store=reopened,
            planner=ReconciliationPlanner(reopened),
            authenticator=ReviewerAuthenticator("123456"),
            reviewer_session_digest=backend.reviewer_session_digest,
        )
        challenge = service.create_challenge(
            session_id=session_id,
            reviewer_token=recovery_token,
            pin="123456",
            client_key="replacement-recovery-tab",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )
        recovery = service.consume_challenge(
            session_id=session_id,
            reviewer_token=recovery_token,
            challenge_token=challenge.challenge_token,
            confirmation_phrase=challenge.confirmation_phrase,
        )
        coordinator = ReconciliationCoordinator(reopened)
        recovery_binding = coordinator.authority_binding(recovery)
        recovery_authority: ExecutionAuthority = _ExecutionAuthority(
            recovery_binding.root_identity_digest,
            recovery_binding.execution_id,
            recovery_binding.plan_sha256,
            recovery_binding.target_ids,
        )
        with pytest.raises(DeletionBlocked, match="RECOVERY_TARGET_IDENTITY_CHANGED"):
            coordinator.run_local(recovery, authority=recovery_authority)
        assert owned.read_bytes() == original_bytes
        assert sentinel.read_bytes() == b"survive"
    finally:
        reopened.close()
