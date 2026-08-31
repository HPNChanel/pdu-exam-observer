"""Native no-path M1-R1 commands and one synthetic rehearsal."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pdu_exam_observer.configuration import load_native_config
from pdu_exam_observer.m1 import M1Store
from pdu_exam_observer.m1_r1 import (
    M1R1Backend,
    MigrationAuthority,
    _root_identity_digest,
    check_migration_readiness,
    migrate_to_v3,
)
from pdu_exam_observer.m2_persistence import ArtifactIntent, StaticArtifactSource
from pdu_exam_observer.reconciliation import (
    ConfirmationService,
    ExternalAttestationAuthority,
    ProcedureGovernanceAuthority,
    ReconciliationPlanner,
)
from pdu_exam_observer.reconciliation_execution import (
    ExecutionAuthority,
    ReconciliationCoordinator,
    ReconciliationFinalizer,
)
from pdu_exam_observer.services.core import ReviewerAuthenticator


@dataclass(frozen=True)
class _MigrationCapability:
    root_identity_digest: str
    readiness_digest: str

    def permits_migration(self, *, root_identity_digest: str, readiness_digest: str) -> bool:
        return (
            root_identity_digest == self.root_identity_digest
            and readiness_digest == self.readiness_digest
        )


@dataclass(frozen=True)
class _ExecutionCapability:
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


@dataclass(frozen=True)
class _ProcedureCapability:
    authority_reference: str
    source_document_sha256: str

    def permits_procedure_import(
        self, *, authority_reference: str, source_document_sha256: str
    ) -> bool:
        return (
            authority_reference == self.authority_reference
            and source_document_sha256 == self.source_document_sha256
        )


@dataclass(frozen=True)
class _ExternalAttestationCapability:
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


def _report(receipt_sha256: str) -> dict[str, object]:
    return {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "collection_authorized": False,
        "participant_collection_authorized": False,
        "production_reconciler_implemented": False,
        "production_reconciler_real_storage_verified": False,
        "production_reconciler_source_implemented": True,
        "real_data_deletion_authorized": False,
        "research_ready": False,
        "status": "M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY",
        "synthetic_receipt_sha256": receipt_sha256,
    }


def rehearse_r1() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="pdu-m1r1-rehearsal-") as temporary:
        root = Path(temporary) / "root"
        M1Store(root).close()
        readiness = check_migration_readiness(root)
        migration_authority: MigrationAuthority = _MigrationCapability(
            readiness.root_identity_digest, readiness.readiness_digest
        )
        store = migrate_to_v3(
            root,
            expected_readiness_digest=readiness.readiness_digest,
            authority=migration_authority,
        )
        try:
            backend = M1R1Backend(
                root,
                store=store,
                encryption_status="VERIFIED",
                acl_status="VERIFIED",
            )
            study = backend.create_study("synthetic-rehearsal", idempotency_key="study")
            participant = backend.create_participant(
                str(study["study_id"]), idempotency_key="participant"
            )
            session = backend.create_research_session(
                str(study["study_id"]),
                str(participant["participant_id"]),
                idempotency_key="session",
                retention_policy_reference="synthetic-only",
            )
            session_id = str(session["session_id"])
            store.persist(
                ArtifactIntent(
                    intent_id="intent-synthetic",
                    artifact_id="artifact-synthetic",
                    session_id=session_id,
                    artifact_kind="TECHNICAL_FIXTURE",
                    technical_input_kind="DETERMINISTIC_FIXTURE",
                    capture_profile_version="fixture-profile-v1",
                    monotonic_timing_origin="synthetic-monotonic-v1",
                    processing_version="fixture-generator-v1",
                ),
                StaticArtifactSource(b"m1-r1-synthetic-rehearsal"),
            )
            external_target = store.register_external_target(
                "artifact-synthetic",
                export_id="synthetic-export",
                manifest_sha256=store.manifest_binding_sha256("artifact-synthetic"),
            )
            sentinel = root / "sentinel.bin"
            sentinel.write_bytes(b"must-survive")
            backend.withdraw(session_id, idempotency_key="withdraw")
            token = backend.issue_reviewer_token()
            confirmation = ConfirmationService(
                store=store,
                planner=ReconciliationPlanner(store),
                authenticator=ReviewerAuthenticator("739251"),
                reviewer_session_digest=backend.reviewer_session_digest,
                register_reviewer_session_revocation=(
                    backend.register_reviewer_session_revocation
                ),
            )
            local = confirmation.create_challenge(
                session_id=session_id,
                reviewer_token=token,
                pin="739251",
                client_key="synthetic-rehearsal",
                action="EXECUTE_LOCAL_RECONCILIATION",
                target_id=None,
            )
            consumed = confirmation.consume_challenge(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=local.challenge_token,
                confirmation_phrase=local.confirmation_phrase,
            )
            coordinator = ReconciliationCoordinator(store)
            binding = coordinator.authority_binding(consumed)
            execution_authority: ExecutionAuthority = _ExecutionCapability(
                binding.root_identity_digest,
                binding.execution_id,
                binding.plan_sha256,
                binding.target_ids,
            )
            coordinator.run_local(consumed, authority=execution_authority)
            source_sha256 = "b" * 64
            procedure_authority: ProcedureGovernanceAuthority = _ProcedureCapability(
                "SYNTHETIC-PROCEDURE", source_sha256
            )
            confirmation.import_procedure_authority(
                authority_id="procedure-synthetic",
                authority_reference="SYNTHETIC-PROCEDURE",
                source_document_sha256=source_sha256,
                authority=procedure_authority,
            )
            external = confirmation.create_challenge(
                session_id=session_id,
                reviewer_token=token,
                pin="739251",
                client_key="synthetic-rehearsal-external",
                action="ATTEST_EXTERNAL_DELETION",
                target_id=external_target,
            )
            external_authority: ExternalAttestationAuthority = (
                _ExternalAttestationCapability(
                    _root_identity_digest(store.root),
                    external.challenge_id,
                    external.plan_sha256,
                    external_target,
                    "procedure-synthetic",
                )
            )
            confirmation.attest_external_deletion(
                session_id=session_id,
                reviewer_token=token,
                challenge_token=external.challenge_token,
                confirmation_phrase=external.confirmation_phrase,
                procedure_authority_id="procedure-synthetic",
                authority=external_authority,
            )
            receipt = ReconciliationFinalizer(store).finalize(session_id)
            if not receipt.body["complete"] or sentinel.read_bytes() != b"must-survive":
                raise RuntimeError("synthetic rehearsal verification failed")
            return _report(receipt.body_sha256)
        finally:
            store.close()


def cli_main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdu-exam-observer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    migrate = subparsers.add_parser("migrate-r1")
    mode = migrate.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    migrate.add_argument("--expected-readiness-digest")
    subparsers.add_parser("rehearse-r1")
    options = parser.parse_args(arguments)
    if options.command == "rehearse-r1":
        try:
            print(json.dumps(rehearse_r1(), sort_keys=True, separators=(",", ":")))
            return 0
        except Exception:
            print('{"code":"UNEXPECTED_FAILURE"}', file=sys.stderr)
            return 1
    if options.apply:
        if options.expected_readiness_digest is None:
            parser.error("--apply requires --expected-readiness-digest")
        print('{"authority_status":"AUTHORITY_NOT_ISSUED"}')
        return 3
    if options.expected_readiness_digest is not None:
        parser.error("--expected-readiness-digest is valid only with --apply")
    try:
        native = load_native_config(require_writable=False)
        readiness = check_migration_readiness(native.root)
        print(
            json.dumps(
                readiness.body() | {"readiness_body_sha256": readiness.readiness_digest},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except Exception:
        print('{"code":"MIGRATION_CHECK_FAILED"}', file=sys.stderr)
        return 1
