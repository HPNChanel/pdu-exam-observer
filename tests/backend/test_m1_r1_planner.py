from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pdu_exam_observer.m1 import M1Store
from pdu_exam_observer.m1_r1 import (
    M1R1Backend,
    MigrationAuthority,
    ResearchStoreV3,
    check_migration_readiness,
    migrate_to_v3,
)
from pdu_exam_observer.m2_persistence import ArtifactIntent, StaticArtifactSource
from pdu_exam_observer.reconciliation import (
    ReconciliationPlanner,
    ReconciliationReceipt,
)


@dataclass(frozen=True)
class _Authority:
    root_identity_digest: str
    readiness_digest: str

    def permits_migration(self, *, root_identity_digest: str, readiness_digest: str) -> bool:
        return (
            root_identity_digest == self.root_identity_digest
            and readiness_digest == self.readiness_digest
        )


def _system(tmp_path: Path, code: str) -> tuple[ResearchStoreV3, M1R1Backend, str, str]:
    root = tmp_path / "root"
    M1Store(root).close()
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _Authority(
        readiness.root_identity_digest, readiness.readiness_digest
    )
    store = migrate_to_v3(
        root,
        expected_readiness_digest=readiness.readiness_digest,
        authority=authority,
    )
    backend = M1R1Backend(
        root,
        store=store,
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
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
    return (
        store,
        backend,
        str(participant["participant_id"]),
        str(session["session_id"]),
    )


def _seal(store: ResearchStoreV3, session_id: str, artifact_id: str) -> None:
    store.persist(
        ArtifactIntent(
            intent_id=f"intent-{artifact_id}",
            artifact_id=artifact_id,
            session_id=session_id,
            artifact_kind="TECHNICAL_FIXTURE",
            technical_input_kind="DETERMINISTIC_FIXTURE",
            capture_profile_version="fixture-profile-v1",
            monotonic_timing_origin="synthetic-monotonic-v1",
            processing_version="fixture-generator-v1",
        ),
        StaticArtifactSource(("fixture-" + artifact_id).encode()),
    )


def test_plan_is_canonical_stably_ordered_and_redacted(tmp_path: Path) -> None:
    store, backend, participant_id, session_id = _system(tmp_path, "canonical-plan")
    try:
        _seal(store, session_id, "artifact-z")
        _seal(store, session_id, "artifact-a")
        store.register_external_target(
            "artifact-a",
            export_id="export-a",
            manifest_sha256=store.manifest_binding_sha256("artifact-a"),
        )
        backend.withdraw(session_id, idempotency_key="withdraw-canonical")

        planner = ReconciliationPlanner(store)
        first = planner.plan_for_session(session_id)
        second = planner.plan_for_session(session_id)

        assert first == second
        assert first.participant_id == participant_id
        assert first.plan_sha256 == second.plan_sha256
        assert first.body["task_total"] == 2
        assert first.body["local_target_total"] == 2
        assert first.body["external_target_total"] == 1
        assert first.body["blocker_codes"] == []
        target_ids = [target["target_id"] for target in first.body["targets"]]
        assert target_ids == sorted(target_ids)
        encoded = first.canonical_json
        assert str(store.root).casefold() not in encoded.casefold()
        assert "artifacts/m2" not in encoded
        assert "relative_path" not in encoded
        assert "expected_sha256" not in encoded
        assert json.loads(encoded) == first.body
    finally:
        store.close()


def test_missing_target_is_a_blocker_and_withdrawal_remains_terminal(tmp_path: Path) -> None:
    store, backend, participant_id, session_id = _system(tmp_path, "missing-plan-target")
    try:
        with store.transaction() as connection:
            connection.execute(
                "INSERT INTO artifact_registry(id,session_id,status,created_at) "
                "VALUES('missing-target',?,'VALID',0)",
                (session_id,),
            )
        withdrawal = backend.withdraw(session_id, idempotency_key="withdraw-missing-plan")

        plan = ReconciliationPlanner(store).plan_for_session(session_id)
        assert plan.body["blocker_codes"] == ["TARGET_BINDING_MISSING"]
        assert plan.body["complete"] is False
        assert withdrawal["terminal"] is True
        assert store.connection.execute(
            "SELECT withdrawn_at FROM participants WHERE id=?", (participant_id,)
        ).fetchone()[0] is not None
    finally:
        store.close()


def test_target_state_or_active_intent_changes_the_plan_and_blocks(tmp_path: Path) -> None:
    store, backend, _participant_id, session_id = _system(tmp_path, "plan-drift")
    try:
        _seal(store, session_id, "artifact-drift")
        backend.withdraw(session_id, idempotency_key="withdraw-drift")
        planner = ReconciliationPlanner(store)
        initial = planner.plan_for_session(session_id)

        with store.transaction() as connection:
            connection.execute(
                "UPDATE withdrawal_task_targets SET state='BLOCKED',state_version=state_version+1,"
                "blocker_code='TARGET_MISSING_UNEXPLAINED'"
            )
        changed = planner.plan_for_session(session_id)
        assert changed.plan_sha256 != initial.plan_sha256
        assert changed.target_state_version != initial.target_state_version
        assert "TARGET_MISSING_UNEXPLAINED" in changed.body["blocker_codes"]

        with store.transaction() as connection:
            connection.execute(
                "INSERT INTO m2_write_intents(id,session_id,artifact_id,partial_relative_path,"
                "final_relative_path,request_hash,status,created_at,terminal_at) "
                "VALUES('pending-intent',?,'pending-artifact','staging/pending.part',"
                "'artifacts/m2/pending.bin','request','PENDING',0,NULL)",
                (session_id,),
            )
        active = planner.plan_for_session(session_id)
        assert "ACTIVE_WRITE_INTENT" in active.body["blocker_codes"]
        with store.transaction() as connection:
            connection.execute(
                "UPDATE m2_write_intents SET status='QUARANTINED',terminal_at=1 "
                "WHERE id='pending-intent'"
            )
        quarantined = planner.plan_for_session(session_id)
        assert "QUARANTINED_WRITE_INTENT_UNRESOLVED" in quarantined.body["blocker_codes"]
    finally:
        store.close()


def test_canonical_receipt_counts_terminal_basis_and_never_claims_collection(
    tmp_path: Path,
) -> None:
    store, backend, _participant_id, session_id = _system(tmp_path, "receipt")
    try:
        _seal(store, session_id, "artifact-receipt")
        store.register_external_target(
            "artifact-receipt",
            export_id="export-receipt",
            manifest_sha256=store.manifest_binding_sha256("artifact-receipt"),
        )
        backend.withdraw(session_id, idempotency_key="withdraw-receipt")
        with store.transaction() as connection:
            connection.execute(
                "UPDATE withdrawal_task_targets SET state=CASE target_kind "
                "WHEN 'EXTERNAL_COPY' THEN 'EXTERNAL_DELETION_ATTESTED' "
                "ELSE 'LOCAL_DELETION_VERIFIED' END,state_version=state_version+1"
            )
        plan = ReconciliationPlanner(store).plan_for_session(session_id)
        receipt = ReconciliationReceipt.from_plan(plan)

        assert set(receipt.body) == {
            "receipt_schema_version",
            "operational_ledger_version",
            "withdrawal_receipt_id",
            "participant_pseudonym",
            "plan_sha256",
            "task_total",
            "task_completed",
            "local_target_total",
            "local_deletion_verified_total",
            "external_target_total",
            "external_deletion_attested_total",
            "blocked_target_total",
            "recovery_required_total",
            "completion_basis",
            "complete",
            "human_review_required",
            "collection_authorized",
            "research_ready",
            "real_data_deletion_authorized_for_this_run",
        }
        assert receipt.body["complete"] is True
        assert receipt.body["task_completed"] == 1
        assert receipt.body["completion_basis"] == [
            "EXTERNAL_DELETION_ATTESTED",
            "LOCAL_DELETION_VERIFIED",
        ]
        assert receipt.body["collection_authorized"] is False
        assert receipt.body["research_ready"] is False
        assert receipt.body["real_data_deletion_authorized_for_this_run"] is False
        assert json.loads(receipt.canonical_json) == receipt.body
        assert len(receipt.body_sha256) == 64
    finally:
        store.close()
