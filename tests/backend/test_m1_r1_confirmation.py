from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app
from pdu_exam_observer.m1 import M1Store
from pdu_exam_observer.m1_r1 import (
    M1R1Backend,
    MigrationAuthority,
    ResearchStoreV3,
    _root_identity_digest,
    check_migration_readiness,
    migrate_to_v3,
)
from pdu_exam_observer.m2_persistence import ArtifactIntent, StaticArtifactSource
from pdu_exam_observer.reconciliation import (
    ChallengeRejected,
    ConfirmationService,
    ExternalAttestationAuthority,
    ProcedureAuthorityNotIssued,
    ProcedureGovernanceAuthority,
    ReconciliationBlocked,
    ReconciliationPlanner,
)
from pdu_exam_observer.reconciliation_execution import ReconciliationFinalizer
from pdu_exam_observer.services.core import ReviewerAuthenticator


class _Clock:
    def __init__(self, value: float = 1_800_000_000.0) -> None:
        self.value = value
        self.monotonic_value = 1_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds

    def monotonic(self) -> float:
        return self.monotonic_value

    def advance_monotonic(self, seconds: float) -> None:
        self.monotonic_value += seconds


class _ArmableClock(_Clock):
    def __init__(self, value: float = 1_800_000_000.0) -> None:
        super().__init__(value)
        self._finite_calls_before_nan: int | None = None

    def arm_nan_after(self, finite_calls: int) -> None:
        self._finite_calls_before_nan = finite_calls

    def __call__(self) -> float:
        if self._finite_calls_before_nan is None:
            return self.value
        if self._finite_calls_before_nan > 0:
            self._finite_calls_before_nan -= 1
            return self.value
        return float("nan")


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
class _ProcedureAuthority:
    reference: str
    source_document_sha256: str

    def permits_procedure_import(
        self, *, authority_reference: str, source_document_sha256: str
    ) -> bool:
        return (
            authority_reference == self.reference
            and source_document_sha256 == self.source_document_sha256
        )


@dataclass(frozen=True)
class _ExternalAttestationAuthority:
    root_identity_digest: str
    challenge_id: str
    plan_sha256: str
    target_id: str
    procedure_authority_id: str

    def permits_external_attestation(
        self,
        *,
        root_identity_digest: str,
        challenge_id: str,
        plan_sha256: str,
        target_id: str,
        procedure_authority_id: str,
    ) -> bool:
        return (
            root_identity_digest == self.root_identity_digest
            and challenge_id == self.challenge_id
            and plan_sha256 == self.plan_sha256
            and target_id == self.target_id
            and procedure_authority_id == self.procedure_authority_id
        )


def _system(
    tmp_path: Path,
) -> tuple[ResearchStoreV3, M1R1Backend, ConfirmationService, _Clock, str, str, str]:
    clock = _Clock()
    root = tmp_path / "root"
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
    backend.clock = clock
    study = backend.create_study("confirmation", idempotency_key="study-confirmation")
    participant = backend.create_participant(
        str(study["study_id"]), idempotency_key="participant-confirmation"
    )
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key="session-confirmation",
        retention_policy_reference="synthetic-policy",
    )
    session_id = str(session["session_id"])
    store.clock = clock
    store.persist(
        ArtifactIntent(
            intent_id="intent-confirmation",
            artifact_id="artifact-confirmation",
            session_id=session_id,
            artifact_kind="TECHNICAL_FIXTURE",
            technical_input_kind="DETERMINISTIC_FIXTURE",
            capture_profile_version="fixture-profile-v1",
            monotonic_timing_origin="synthetic-monotonic-v1",
            processing_version="fixture-generator-v1",
        ),
        StaticArtifactSource(b"confirmation-fixture"),
    )
    external_target_id = store.register_external_target(
        "artifact-confirmation",
        export_id="export-confirmation",
        manifest_sha256=store.manifest_binding_sha256("artifact-confirmation"),
    )
    backend.withdraw(session_id, idempotency_key="withdraw-confirmation")
    reviewer_token = backend.issue_reviewer_token()
    service = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        clock=clock,
    )
    return (
        store,
        backend,
        service,
        clock,
        reviewer_token,
        session_id,
        external_target_id,
    )


def test_step_up_and_challenge_store_only_digests_and_consume_one_typed_execution(
    tmp_path: Path,
) -> None:
    store, _backend, service, _clock, token, session_id, external_target_id = _system(
        tmp_path
    )
    try:
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )
        row = store.connection.execute(
            "SELECT c.token_digest,c.action,c.target_id,s.expires_at-s.verified_at ttl,"
            "s.reviewer_session_digest FROM reconciliation_challenges c "
            "JOIN reviewer_step_up_authentications s ON s.id=c.step_up_authentication_id"
        ).fetchone()
        assert row is not None
        assert row["token_digest"] != issued.challenge_token
        assert len(row["token_digest"]) == 64
        assert row["action"] == "EXECUTE_LOCAL_RECONCILIATION"
        assert row["target_id"] is None
        assert 0 < row["ttl"] <= 120
        assert len(row["reviewer_session_digest"]) == 64

        consumed = service.consume_challenge(
            session_id=session_id,
            reviewer_token=token,
            challenge_token=issued.challenge_token,
            confirmation_phrase=issued.confirmation_phrase,
        )
        assert consumed.execution_kind == "LOCAL_RUN"
        with pytest.raises(ChallengeRejected, match="CHALLENGE_ALREADY_CONSUMED"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_executions"
        ).fetchone()[0] == 1
        assert store.connection.execute(
            "SELECT target_id FROM reconciliation_challenges WHERE id=?", (issued.challenge_id,)
        ).fetchone()[0] is None
        assert external_target_id
    finally:
        store.close()


def test_challenge_rejects_wrong_kind_target_phrase_session_and_plan_drift(
    tmp_path: Path,
) -> None:
    store, backend, service, _clock, token, session_id, external_target_id = _system(tmp_path)
    try:
        with pytest.raises(ChallengeRejected, match="LOCAL_CHALLENGE_MUST_NOT_BIND_TARGET"):
            service.create_challenge(
                session_id=session_id,
                reviewer_token=token,
                pin="123456",
                client_key="monitor-tab",
                action="EXECUTE_LOCAL_RECONCILIATION",
                target_id=external_target_id,
            )
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab",
            action="ATTEST_EXTERNAL_DELETION",
            target_id=external_target_id,
        )
        with pytest.raises(ChallengeRejected, match="CONFIRMATION_PHRASE_MISMATCH"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase="DOI_SOAT wrong",
            )

        replacement_token = backend.issue_reviewer_token()
        with pytest.raises(ChallengeRejected, match="REVIEWER_SESSION_INVALID"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )
        replacement = service.create_challenge(
            session_id=session_id,
            reviewer_token=replacement_token,
            pin="123456",
            client_key="monitor-tab-2",
            action="ATTEST_EXTERNAL_DELETION",
            target_id=external_target_id,
        )
        with store.transaction() as connection:
            connection.execute(
                "UPDATE withdrawal_task_targets SET state_version=state_version+1 "
                "WHERE target_id=?",
                (external_target_id,),
            )
        with pytest.raises(ChallengeRejected, match="PLAN_CHANGED"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=replacement_token,
                challenge_token=replacement.challenge_token,
                confirmation_phrase=replacement.confirmation_phrase,
            )
    finally:
        store.close()


def test_challenge_expires_at_step_up_boundary_and_bearer_rollback_fails_closed(
    tmp_path: Path,
) -> None:
    store, _backend, service, clock, token, session_id, external_target_id = _system(tmp_path)
    try:
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab",
            action="ATTEST_EXTERNAL_DELETION",
            target_id=external_target_id,
        )
        clock.advance(120)
        with pytest.raises(ChallengeRejected, match="CHALLENGE_EXPIRED"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )

        clock.advance(-121)
        with pytest.raises(ChallengeRejected, match="REVIEWER_SESSION_INVALID"):
            service.create_challenge(
                session_id=session_id,
                reviewer_token=token,
                pin="123456",
                client_key="monitor-tab-rollback",
                action="ATTEST_EXTERNAL_DELETION",
                target_id=external_target_id,
            )
    finally:
        store.close()


def test_challenge_expires_by_elapsed_time_after_wall_clock_rollback(tmp_path: Path) -> None:
    store, backend, _service, clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    service = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        clock=clock,
        monotonic_clock=clock.monotonic,
    )
    try:
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab-monotonic-expiry",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )
        clock.advance(30)
        clock.advance_monotonic(120)

        with pytest.raises(ChallengeRejected, match="CHALLENGE_EXPIRED"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )

        row = store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()
        assert row is not None
        assert row["status"] == "EXPIRED"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_executions"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_confirmation_service_restart_expires_all_preexisting_issued_challenges(
    tmp_path: Path,
) -> None:
    store, backend, service, clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    try:
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab-before-restart",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )
        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()[0] == "ISSUED"

        restarted = ConfirmationService(
            store=store,
            planner=ReconciliationPlanner(store),
            authenticator=ReviewerAuthenticator("123456"),
            reviewer_session_digest=backend.reviewer_session_digest,
            clock=clock,
            monotonic_clock=clock.monotonic,
        )

        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()[0] == "EXPIRED"
        with pytest.raises(ChallengeRejected, match="CHALLENGE_NOT_ACTIVE"):
            restarted.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )
    finally:
        store.close()


def test_challenge_revokes_when_monotonic_clock_moves_backwards(tmp_path: Path) -> None:
    store, backend, _service, clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    service = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        clock=clock,
        monotonic_clock=clock.monotonic,
    )
    try:
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab-monotonic-rollback",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )
        clock.advance_monotonic(-1)

        with pytest.raises(ChallengeRejected, match="MONOTONIC_CLOCK_INVALID"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )

        row = store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()
        assert row is not None
        assert row["status"] == "REVOKED"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_executions"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_challenge_creation_rejects_nonfinite_wall_clock(tmp_path: Path) -> None:
    store, backend, _service, _clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    service_clock = _Clock(float("nan"))
    service = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        clock=service_clock,
        monotonic_clock=service_clock.monotonic,
    )
    try:
        with pytest.raises(ChallengeRejected, match="CLOCK_INVALID"):
            service.create_challenge(
                session_id=session_id,
                reviewer_token=token,
                pin="123456",
                client_key="monitor-tab-nonfinite-create",
                action="EXECUTE_LOCAL_RECONCILIATION",
                target_id=None,
            )
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_challenges"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_challenge_creation_rechecks_reviewer_session_after_planning(
    tmp_path: Path,
) -> None:
    store, backend, service, _clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    original_plan = service.planner.plan_for_session

    def revoking_plan(current_session_id: str):  # type: ignore[no-untyped-def]
        plan = original_plan(current_session_id)
        backend.revoke_reviewer_token(token)
        return plan

    service.planner.plan_for_session = revoking_plan  # type: ignore[method-assign]
    try:
        with pytest.raises(ChallengeRejected, match="REVIEWER_SESSION_INVALID"):
            service.create_challenge(
                session_id=session_id,
                reviewer_token=token,
                pin="123456",
                client_key="monitor-tab-revoked-during-create-plan",
                action="EXECUTE_LOCAL_RECONCILIATION",
                target_id=None,
            )
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_challenges"
        ).fetchone()[0] == 0
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reviewer_step_up_authentications"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_challenge_creation_rechecks_step_up_expiry_after_planning(
    tmp_path: Path,
) -> None:
    store, backend, _service, clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    planner = ReconciliationPlanner(store)
    service = ConfirmationService(
        store=store,
        planner=planner,
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        clock=clock,
        monotonic_clock=clock.monotonic,
    )
    original_plan = planner.plan_for_session

    def delayed_plan(current_session_id: str):  # type: ignore[no-untyped-def]
        plan = original_plan(current_session_id)
        clock.advance(120)
        clock.advance_monotonic(120)
        return plan

    planner.plan_for_session = delayed_plan  # type: ignore[method-assign]
    try:
        with pytest.raises(ChallengeRejected, match="CHALLENGE_EXPIRED"):
            service.create_challenge(
                session_id=session_id,
                reviewer_token=token,
                pin="123456",
                client_key="monitor-tab-expired-during-create-plan",
                action="EXECUTE_LOCAL_RECONCILIATION",
                target_id=None,
            )
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_challenges"
        ).fetchone()[0] == 0
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reviewer_step_up_authentications"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_challenge_consumption_revokes_on_nonfinite_wall_clock(tmp_path: Path) -> None:
    store, backend, _service, service_clock, token, session_id, _external_target_id = (
        _system(tmp_path)
    )
    service = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        clock=service_clock,
        monotonic_clock=service_clock.monotonic,
    )
    issued = service.create_challenge(
        session_id=session_id,
        reviewer_token=token,
        pin="123456",
        client_key="monitor-tab-nonfinite-consume",
        action="EXECUTE_LOCAL_RECONCILIATION",
        target_id=None,
    )
    service.clock = lambda: float("nan")
    try:
        with pytest.raises(ChallengeRejected, match="CLOCK_INVALID"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )
        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()[0] == "REVOKED"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_executions"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_challenge_rechecks_expiry_after_planning_delay(tmp_path: Path) -> None:
    store, backend, _service, clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    planner = ReconciliationPlanner(store)
    service = ConfirmationService(
        store=store,
        planner=planner,
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        clock=clock,
        monotonic_clock=clock.monotonic,
    )
    issued = service.create_challenge(
        session_id=session_id,
        reviewer_token=token,
        pin="123456",
        client_key="monitor-tab-planning-delay",
        action="EXECUTE_LOCAL_RECONCILIATION",
        target_id=None,
    )
    original_plan = planner.plan_for_session

    def delayed_plan(current_session_id: str):  # type: ignore[no-untyped-def]
        plan = original_plan(current_session_id)
        clock.advance(120)
        clock.advance_monotonic(120)
        return plan

    planner.plan_for_session = delayed_plan  # type: ignore[method-assign]
    try:
        with pytest.raises(ChallengeRejected, match="CHALLENGE_EXPIRED"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )

        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()[0] == "EXPIRED"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_executions"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_challenge_rechecks_reviewer_session_after_planning(tmp_path: Path) -> None:
    store, backend, service, _clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    issued = service.create_challenge(
        session_id=session_id,
        reviewer_token=token,
        pin="123456",
        client_key="monitor-tab-revoked-during-plan",
        action="EXECUTE_LOCAL_RECONCILIATION",
        target_id=None,
    )
    original_plan = service.planner.plan_for_session

    def revoking_plan(current_session_id: str):  # type: ignore[no-untyped-def]
        plan = original_plan(current_session_id)
        backend.revoke_reviewer_token(token)
        return plan

    service.planner.plan_for_session = revoking_plan  # type: ignore[method-assign]
    try:
        with pytest.raises(ChallengeRejected, match="REVIEWER_SESSION_INVALID"):
            service.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
            )

        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()[0] == "REVOKED"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_executions"
        ).fetchone()[0] == 0
    finally:
        store.close()


@pytest.mark.parametrize("revocation_mode", ["logout", "replacement"])
def test_reviewer_session_change_durably_revokes_issued_challenges(
    tmp_path: Path, revocation_mode: str
) -> None:
    store, backend, _service, clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    service = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        register_reviewer_session_revocation=backend.register_reviewer_session_revocation,
        clock=clock,
        monotonic_clock=clock.monotonic,
    )
    try:
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab-before-logout",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )

        if revocation_mode == "logout":
            backend.revoke_reviewer_token(token)
        else:
            backend.issue_reviewer_token()

        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()[0] == "REVOKED"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_executions"
        ).fetchone()[0] == 0
    finally:
        store.close()


def test_replacement_confirmation_service_supersedes_closed_revocation_callback(
    tmp_path: Path,
) -> None:
    store, backend, _service, clock, token, session_id, _external_target_id = _system(
        tmp_path
    )
    root = store.root
    first_service = ConfirmationService(
        store=store,
        planner=ReconciliationPlanner(store),
        authenticator=ReviewerAuthenticator("123456"),
        reviewer_session_digest=backend.reviewer_session_digest,
        register_reviewer_session_revocation=backend.register_reviewer_session_revocation,
        clock=clock,
        monotonic_clock=clock.monotonic,
    )
    first = first_service.create_challenge(
        session_id=session_id,
        reviewer_token=token,
        pin="123456",
        client_key="monitor-tab-first-service",
        action="EXECUTE_LOCAL_RECONCILIATION",
        target_id=None,
    )
    backend.revoke_reviewer_token(token)
    assert store.connection.execute(
        "SELECT status FROM reconciliation_challenges WHERE id=?", (first.challenge_id,)
    ).fetchone()[0] == "REVOKED"
    store.close()

    reopened = ResearchStoreV3(root)
    try:
        second_service = ConfirmationService(
            store=reopened,
            planner=ReconciliationPlanner(reopened),
            authenticator=ReviewerAuthenticator("123456"),
            reviewer_session_digest=backend.reviewer_session_digest,
            register_reviewer_session_revocation=(
                backend.register_reviewer_session_revocation
            ),
            clock=clock,
            monotonic_clock=clock.monotonic,
        )
        replacement_token = backend.issue_reviewer_token()
        second = second_service.create_challenge(
            session_id=session_id,
            reviewer_token=replacement_token,
            pin="123456",
            client_key="monitor-tab-second-service",
            action="EXECUTE_LOCAL_RECONCILIATION",
            target_id=None,
        )

        backend.revoke_reviewer_token(replacement_token)

        assert reopened.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (second.challenge_id,),
        ).fetchone()[0] == "REVOKED"
    finally:
        reopened.close()


def test_external_attestation_requires_persisted_current_procedure_authority(
    tmp_path: Path,
) -> None:
    store, _backend, service, _clock, token, session_id, external_target_id = _system(
        tmp_path
    )
    source_sha256 = "a" * 64
    try:
        with pytest.raises(ProcedureAuthorityNotIssued, match="AUTHORITY_NOT_ISSUED"):
            service.import_procedure_authority(
                authority_id="procedure-1",
                authority_reference="PROC-001",
                source_document_sha256=source_sha256,
                authority=None,
            )
        governance: ProcedureGovernanceAuthority = _ProcedureAuthority(
            "PROC-001", source_sha256
        )
        service.import_procedure_authority(
            authority_id="procedure-1",
            authority_reference="PROC-001",
            source_document_sha256=source_sha256,
            authority=governance,
        )
        issued = service.create_challenge(
            session_id=session_id,
            reviewer_token=token,
            pin="123456",
            client_key="monitor-tab",
            action="ATTEST_EXTERNAL_DELETION",
            target_id=external_target_id,
        )
        with pytest.raises(ProcedureAuthorityNotIssued, match="AUTHORITY_NOT_ISSUED"):
            service.attest_external_deletion(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=issued.challenge_token,
                confirmation_phrase=issued.confirmation_phrase,
                procedure_authority_id="procedure-1",
                authority=None,
            )
        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.challenge_id,),
        ).fetchone()[0] == "ISSUED"
        authority: ExternalAttestationAuthority = _ExternalAttestationAuthority(
            _root_identity_digest(store.root),
            issued.challenge_id,
            issued.plan_sha256,
            external_target_id,
            "procedure-1",
        )
        attestation = service.attest_external_deletion(
            session_id=session_id,
            reviewer_token=token,
            challenge_token=issued.challenge_token,
            confirmation_phrase=issued.confirmation_phrase,
            procedure_authority_id="procedure-1",
            authority=authority,
        )
        assert attestation["state"] == "EXTERNAL_DELETION_ATTESTED"
        assert store.connection.execute(
            "SELECT state FROM withdrawal_task_targets WHERE target_id=?",
            (external_target_id,),
        ).fetchone()[0] == "EXTERNAL_DELETION_ATTESTED"
        assert store.connection.execute(
            "SELECT COUNT(*) FROM external_deletion_attestations"
        ).fetchone()[0] == 1
        plan = service.planner.plan_for_session(session_id)
        external_only = replace(
            plan,
            body={
                **plan.body,
                "targets": [
                    target
                    for target in plan.body["targets"]
                    if target["target_kind"] == "EXTERNAL_COPY"
                ],
            },
        )
        with store.transaction() as connection:
            connection.execute(
                "UPDATE approved_procedure_authorities SET status='REVOKED',revoked_at=? "
                "WHERE id='procedure-1'",
                (_clock(),),
            )
        with store.transaction() as connection:
            with pytest.raises(
                ReconciliationBlocked, match="TERMINAL_EVIDENCE_BINDING_INVALID"
            ):
                ReconciliationFinalizer._require_terminal_evidence(
                    connection, external_only
                )
    finally:
        store.close()


def test_reconciliation_http_surface_exists_only_on_monitor_and_normal_execution_denies(
    tmp_path: Path,
) -> None:
    store, backend, _service, _clock, _token, session_id, _external_target_id = _system(
        tmp_path
    )
    config = AppConfig(
        reviewer_pin="123456",
        exam_origin="http://exam.local",
        monitor_origin="http://monitor.local",
        allowed_hosts=("exam.local", "monitor.local"),
        backend=backend,
    )
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    exam = TestClient(create_exam_app(config), base_url=config.exam_origin)
    try:
        login = monitor.post(
            "/api/v1/reviewer/login",
            json={"pin": "123456"},
            headers={"Origin": config.monitor_origin},
        )
        token = str(login.json()["access_token"])
        headers = {
            "Origin": config.monitor_origin,
            "Authorization": f"Bearer {token}",
        }
        path = f"/api/v1/research/sessions/{session_id}/reconciliation"

        assert monitor.get(path).status_code == 401
        plan = monitor.get(path, headers={"Authorization": f"Bearer {token}"})
        assert plan.status_code == 200
        assert len(plan.json()["plan_sha256"]) == 64
        encoded = plan.text.casefold()
        assert str(store.root).casefold() not in encoded
        assert "relative_path" not in encoded
        assert exam.get(path).status_code == 404

        extra = monitor.post(
            path + "/challenges",
            json={
                "pin": "123456",
                "action": "EXECUTE_LOCAL_RECONCILIATION",
                "target_id": None,
                "path": "C:/forbidden",
            },
            headers=headers,
        )
        assert extra.status_code == 422
        wrong_type = monitor.post(
            path + "/challenges",
            content="{}",
            headers={**headers, "Content-Type": "text/plain"},
        )
        assert wrong_type.status_code == 415
        chunked = monitor.post(
            path + "/challenges",
            content=(chunk for chunk in (b'{"pin":"', b"7" * 70_000, b'"}')),
            headers={**headers, "Content-Type": "application/json"},
        )
        assert chunked.status_code == 413
        issued = monitor.post(
            path + "/challenges",
            json={
                "pin": "123456",
                "action": "EXECUTE_LOCAL_RECONCILIATION",
                "target_id": None,
            },
            headers=headers,
        )
        assert issued.status_code == 201

        denied = monitor.post(
            path + "/executions",
            json={
                "challenge_token": issued.json()["challenge_token"],
                "confirmation_phrase": issued.json()["confirmation_phrase"],
            },
            headers=headers,
        )
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "AUTHORITY_NOT_ISSUED"
        assert store.connection.execute(
            "SELECT status FROM reconciliation_challenges WHERE id=?",
            (issued.json()["challenge_id"],),
        ).fetchone()[0] == "ISSUED"
    finally:
        store.close()


def test_reconciliation_challenge_maps_clock_fault_to_technical_insufficient(
    tmp_path: Path,
) -> None:
    store, backend, _service, clock, _token, session_id, _external_target_id = _system(
        tmp_path
    )
    armable_clock = _ArmableClock(clock.value)
    backend.clock = armable_clock
    config = AppConfig(
        reviewer_pin="123456",
        exam_origin="http://exam.local",
        monitor_origin="http://monitor.local",
        allowed_hosts=("exam.local", "monitor.local"),
        backend=backend,
    )
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    try:
        login = monitor.post(
            "/api/v1/reviewer/login",
            json={"pin": "123456"},
            headers={"Origin": config.monitor_origin},
        )
        token = str(login.json()["access_token"])
        armable_clock.arm_nan_after(2)

        response = monitor.post(
            f"/api/v1/research/sessions/{session_id}/reconciliation/challenges",
            json={
                "pin": "123456",
                "action": "EXECUTE_LOCAL_RECONCILIATION",
                "target_id": None,
            },
            headers={
                "Origin": config.monitor_origin,
                "Authorization": f"Bearer {token}",
            },
        )

        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "TECHNICAL_INSUFFICIENT"}}
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_challenges"
        ).fetchone()[0] == 0
    finally:
        store.close()
