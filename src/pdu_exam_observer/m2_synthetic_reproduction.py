"""Strict same-revision reproduction for canonical M2-S2D evidence."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.m2_d1_contract import (
    D1FailureCode,
    DeviceGateDecision,
    EvidenceKind,
    PrivacyDecision,
    RunKind,
    ValidationOutcome,
)
from pdu_exam_observer.m2_persistence import M2PersistenceStore, PlatformUnsupported
from pdu_exam_observer.m2_synthetic_environment import (
    current_synthetic_environment_bindings,
    synthetic_environment_binding_digest,
)
from pdu_exam_observer.m2_synthetic_evidence import (
    MAX_EVIDENCE_BYTES,
    SyntheticEvidenceError,
    VerifiedSyntheticEvidenceSource,
    build_synthetic_evidence_bundle,
    load_verified_synthetic_evidence_bytes,
)
from pdu_exam_observer.m2_synthetic_integration import (
    IntegrationStatus,
    M2SyntheticNominalCore,
    M2SyntheticPreflightCore,
    SyntheticEnvironmentBindings,
    SyntheticNominalRequest,
    SyntheticPreflightRequest,
)
from pdu_exam_observer.m2_synthetic_nominal_fixture import (
    BUILTIN_RUN_ID as NOMINAL_RUN_ID,
)
from pdu_exam_observer.m2_synthetic_nominal_fixture import build_builtin_nominal_bundle
from pdu_exam_observer.m2_synthetic_preflight_fixture import (
    BUILTIN_RUN_ID as PREFLIGHT_RUN_ID,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import build_builtin_preflight_bundle

STATUS = (
    "M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
NOT_VERIFIED_STATUS = "M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_NOT_VERIFIED"
ARTIFACT_KIND = "M2_SYNTHETIC_EVIDENCE_REPRODUCTION_RECEIPT"
MISMATCH_FIELDS = frozenset(
    {
        "artifact_sha256",
        "bundle_sha256",
        "d1_failure_code",
        "d1_outcome",
        "d1_receipt_digest",
        "integration_result_digest",
        "observation_count",
        "observation_digest",
    }
)


class ReproductionClassification(StrEnum):
    EXACTLY_REPRODUCED = "EXACTLY_REPRODUCED"
    SOURCE_REVISION_MISMATCH = "SOURCE_REVISION_MISMATCH"
    SEMANTIC_RESULT_MISMATCH = "SEMANTIC_RESULT_MISMATCH"
    REPRODUCTION_FAILED = "REPRODUCTION_FAILED"


class ReproductionFailureCode(StrEnum):
    INPUT_INVALID = "INPUT_INVALID"
    SOURCE_EVIDENCE_REJECTED = "SOURCE_EVIDENCE_REJECTED"
    CURRENT_BINDING_UNAVAILABLE = "CURRENT_BINDING_UNAVAILABLE"
    REPLAY_NOT_PERSISTED = "REPLAY_NOT_PERSISTED"
    REPLAY_EVIDENCE_INVALID = "REPLAY_EVIDENCE_INVALID"
    AUTHORITY_CEILING_VIOLATION = "AUTHORITY_CEILING_VIOLATION"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    TEMP_CLEANUP_FAILED = "TEMP_CLEANUP_FAILED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


class TemporaryWorkspaceState(StrEnum):
    NOT_CREATED = "NOT_CREATED"
    REMOVED = "REMOVED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


@dataclass(frozen=True, slots=True)
class SyntheticReproductionReceipt:
    schema_version: int
    artifact_kind: str
    classification: ReproductionClassification
    status: str
    failure_code: ReproductionFailureCode | None
    run_kind: RunKind | None
    source_bundle_sha256: str | None
    reproduced_bundle_sha256: str | None
    source_environment_binding_digest: str | None
    current_environment_binding_digest: str | None
    source_observation_count: int | None
    reproduced_observation_count: int | None
    source_observation_digest: str | None
    reproduced_observation_digest: str | None
    source_d1_outcome: ValidationOutcome | None
    reproduced_d1_outcome: ValidationOutcome | None
    source_d1_failure_code: D1FailureCode | None
    reproduced_d1_failure_code: D1FailureCode | None
    source_d1_receipt_digest: str | None
    reproduced_d1_receipt_digest: str | None
    source_artifact_sha256: str | None
    reproduced_artifact_sha256: str | None
    source_result_digest: str | None
    reproduced_result_digest: str | None
    mismatch_fields: tuple[str, ...]
    temporary_workspace_state: TemporaryWorkspaceState
    evidence_kind: EvidenceKind
    device_gate_decision: DeviceGateDecision
    d1_go: bool
    authority_status: str
    production_reconciler_implemented: bool
    production_reconciler_real_storage_verified: bool
    real_data_deletion_authorized: bool
    execution_authorized: bool
    physical_camera_access_authorized: bool
    participant_collection_authorized: bool
    research_ready: bool
    collection_authorized: bool
    package_contains_integration: bool
    result_digest: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "artifact_kind": self.artifact_kind,
            "authority_status": self.authority_status,
            "classification": self.classification.value,
            "collection_authorized": self.collection_authorized,
            "current_environment_binding_digest": self.current_environment_binding_digest,
            "d1_go": self.d1_go,
            "device_gate_decision": self.device_gate_decision.value,
            "evidence_kind": self.evidence_kind.value,
            "execution_authorized": self.execution_authorized,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "mismatch_fields": list(self.mismatch_fields),
            "package_contains_integration": self.package_contains_integration,
            "participant_collection_authorized": self.participant_collection_authorized,
            "physical_camera_access_authorized": self.physical_camera_access_authorized,
            "production_reconciler_implemented": self.production_reconciler_implemented,
            "production_reconciler_real_storage_verified": (
                self.production_reconciler_real_storage_verified
            ),
            "real_data_deletion_authorized": self.real_data_deletion_authorized,
            "reproduced_artifact_sha256": self.reproduced_artifact_sha256,
            "reproduced_bundle_sha256": self.reproduced_bundle_sha256,
            "reproduced_d1_failure_code": (
                self.reproduced_d1_failure_code.value
                if self.reproduced_d1_failure_code
                else None
            ),
            "reproduced_d1_outcome": (
                self.reproduced_d1_outcome.value if self.reproduced_d1_outcome else None
            ),
            "reproduced_d1_receipt_digest": self.reproduced_d1_receipt_digest,
            "reproduced_observation_count": self.reproduced_observation_count,
            "reproduced_observation_digest": self.reproduced_observation_digest,
            "reproduced_result_digest": self.reproduced_result_digest,
            "research_ready": self.research_ready,
            "run_kind": self.run_kind.value if self.run_kind else None,
            "schema_version": self.schema_version,
            "source_artifact_sha256": self.source_artifact_sha256,
            "source_bundle_sha256": self.source_bundle_sha256,
            "source_d1_failure_code": (
                self.source_d1_failure_code.value if self.source_d1_failure_code else None
            ),
            "source_d1_outcome": self.source_d1_outcome.value if self.source_d1_outcome else None,
            "source_d1_receipt_digest": self.source_d1_receipt_digest,
            "source_environment_binding_digest": self.source_environment_binding_digest,
            "source_observation_count": self.source_observation_count,
            "source_observation_digest": self.source_observation_digest,
            "source_result_digest": self.source_result_digest,
            "status": self.status,
            "temporary_workspace_state": self.temporary_workspace_state.value,
        }

    def recompute_digest(self) -> str:
        return _digest(self.canonical_payload())

    def as_dict(self) -> dict[str, object]:
        return {**self.canonical_payload(), "result_digest": self.result_digest}


class _ReproductionError(RuntimeError):
    def __init__(
        self,
        code: ReproductionFailureCode,
        workspace_state: TemporaryWorkspaceState = TemporaryWorkspaceState.NOT_CREATED,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.workspace_state = workspace_state


class _Lease:
    def __init__(self) -> None:
        self._held = False

    def acquire(self) -> bool:
        if self._held:
            return False
        self._held = True
        return True

    def release(self) -> None:
        self._held = False


class _Privacy:
    def inspect(self, _observation: object) -> PrivacyDecision:
        return PrivacyDecision.CLEAR


def _digest(value: object) -> str:
    import json

    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _comparison_fields(
    source: VerifiedSyntheticEvidenceSource,
    reproduced: VerifiedSyntheticEvidenceSource,
) -> tuple[str, ...]:
    comparisons = {
        "artifact_sha256": source.artifact_sha256 == reproduced.artifact_sha256,
        "bundle_sha256": source.bundle_sha256 == reproduced.bundle_sha256,
        "d1_failure_code": source.d1_failure_code is reproduced.d1_failure_code,
        "d1_outcome": source.d1_outcome is reproduced.d1_outcome,
        "d1_receipt_digest": source.d1_receipt_digest == reproduced.d1_receipt_digest,
        "integration_result_digest": (
            source.source_result_digest == reproduced.source_result_digest
        ),
        "observation_count": source.observation_count == reproduced.observation_count,
        "observation_digest": source.observation_digest == reproduced.observation_digest,
    }
    return tuple(sorted(name for name, matches in comparisons.items() if not matches))


def _make_receipt(
    *,
    classification: ReproductionClassification,
    failure_code: ReproductionFailureCode | None,
    source: VerifiedSyntheticEvidenceSource | None,
    reproduced: VerifiedSyntheticEvidenceSource | None,
    current_environment_binding_digest: str | None,
    mismatch_fields: tuple[str, ...] = (),
    workspace_state: TemporaryWorkspaceState = TemporaryWorkspaceState.NOT_CREATED,
    source_bundle_sha256: str | None = None,
) -> SyntheticReproductionReceipt:
    receipt = SyntheticReproductionReceipt(
        schema_version=1,
        artifact_kind=ARTIFACT_KIND,
        classification=classification,
        status=(
            STATUS
            if classification is ReproductionClassification.EXACTLY_REPRODUCED
            else NOT_VERIFIED_STATUS
        ),
        failure_code=failure_code,
        run_kind=source.run_kind if source else None,
        source_bundle_sha256=(source.bundle_sha256 if source else source_bundle_sha256),
        reproduced_bundle_sha256=reproduced.bundle_sha256 if reproduced else None,
        source_environment_binding_digest=(
            source.environment_binding_digest if source else None
        ),
        current_environment_binding_digest=current_environment_binding_digest,
        source_observation_count=source.observation_count if source else None,
        reproduced_observation_count=reproduced.observation_count if reproduced else None,
        source_observation_digest=source.observation_digest if source else None,
        reproduced_observation_digest=reproduced.observation_digest if reproduced else None,
        source_d1_outcome=source.d1_outcome if source else None,
        reproduced_d1_outcome=reproduced.d1_outcome if reproduced else None,
        source_d1_failure_code=source.d1_failure_code if source else None,
        reproduced_d1_failure_code=reproduced.d1_failure_code if reproduced else None,
        source_d1_receipt_digest=source.d1_receipt_digest if source else None,
        reproduced_d1_receipt_digest=reproduced.d1_receipt_digest if reproduced else None,
        source_artifact_sha256=source.artifact_sha256 if source else None,
        reproduced_artifact_sha256=reproduced.artifact_sha256 if reproduced else None,
        source_result_digest=source.source_result_digest if source else None,
        reproduced_result_digest=reproduced.source_result_digest if reproduced else None,
        mismatch_fields=mismatch_fields,
        temporary_workspace_state=workspace_state,
        evidence_kind=EvidenceKind.SIMULATED,
        device_gate_decision=DeviceGateDecision.UNVERIFIED,
        d1_go=False,
        authority_status="AUTHORITY_NOT_ISSUED",
        production_reconciler_implemented=False,
        production_reconciler_real_storage_verified=False,
        real_data_deletion_authorized=False,
        execution_authorized=False,
        physical_camera_access_authorized=False,
        participant_collection_authorized=False,
        research_ready=False,
        collection_authorized=False,
        package_contains_integration=False,
        result_digest="",
    )
    return replace(receipt, result_digest=receipt.recompute_digest())


def _replay_verified_source(
    source: VerifiedSyntheticEvidenceSource,
    bindings: SyntheticEnvironmentBindings,
) -> tuple[VerifiedSyntheticEvidenceSource, TemporaryWorkspaceState]:
    temporary = tempfile.TemporaryDirectory(prefix="pdu-m2-s2e-")
    root = Path(temporary.name)
    backend: M1Backend | None = None
    store: M2PersistenceStore | None = None
    reproduced: VerifiedSyntheticEvidenceSource | None = None
    pending_error: BaseException | None = None
    try:
        backend = M1Backend(root, encryption_status="UNVERIFIED", acl_status="UNVERIFIED")
        study = backend.create_study("m2-s2e", idempotency_key="study-m2-s2e")
        participant = backend.create_participant(
            str(study["study_id"]), idempotency_key="participant-m2-s2e"
        )
        session = backend.create_research_session(
            str(study["study_id"]),
            str(participant["participant_id"]),
            idempotency_key="session-m2-s2e",
            retention_policy_reference="synthetic-reproduction-lifetime-only",
        )
        session_id = str(session["session_id"])
        backend.store.close()
        backend = None
        store = M2PersistenceStore(root)
        artifact_id = source.integration_receipt.artifact_id
        if artifact_id is None:
            raise _ReproductionError(ReproductionFailureCode.REPLAY_EVIDENCE_INVALID)
        intent_id = f"intent-s2e-{source.source_result_digest[:32]}"
        if source.run_kind is RunKind.PREFLIGHT_60S:
            preflight_fixture = build_builtin_preflight_bundle(bindings.pose_engine_digest)
            receipt = M2SyntheticPreflightCore(
                runner=preflight_fixture.runner,
                privacy_guard=_Privacy(),
                owner_lease=_Lease(),
                persistence_store=store,
                environment_bindings=bindings,
            ).execute(
                SyntheticPreflightRequest(
                    session_id=session_id,
                    intent_id=intent_id,
                    artifact_id=artifact_id,
                    run_id=PREFLIGHT_RUN_ID,
                    fixtures=preflight_fixture.fixtures,
                )
            )
        elif source.run_kind is RunKind.NOMINAL_20M:
            nominal_fixture = build_builtin_nominal_bundle(bindings.pose_engine_digest)
            receipt = M2SyntheticNominalCore(
                runner=nominal_fixture.runner,
                privacy_guard=_Privacy(),
                owner_lease=_Lease(),
                persistence_store=store,
                environment_bindings=bindings,
            ).execute(
                SyntheticNominalRequest(
                    session_id=session_id,
                    intent_id=intent_id,
                    artifact_id=artifact_id,
                    run_id=NOMINAL_RUN_ID,
                    fixtures=nominal_fixture.fixtures,
                )
            )
        else:
            raise _ReproductionError(ReproductionFailureCode.REPLAY_EVIDENCE_INVALID)
        if (
            receipt.integration_status is not IntegrationStatus.PERSISTED
            or receipt.artifact_id is None
            or receipt.integration_failure_code is not None
        ):
            raise _ReproductionError(ReproductionFailureCode.REPLAY_NOT_PERSISTED)
        artifact = store.read_verified_artifact(
            receipt.artifact_id,
            maximum_bytes=MAX_EVIDENCE_BYTES,
        )
        record = {
            "job_status": "TERMINAL",
            "receipt": receipt.as_dict(),
            "request_id": source.request_id,
            "run_kind": source.run_kind.value,
            "run_sequence": source.run_sequence,
            "schema_version": 1,
            "service_failure_code": None,
        }
        exported = build_synthetic_evidence_bundle(record, artifact)
        reproduced = load_verified_synthetic_evidence_bytes(exported.payload)
    except (PlatformUnsupported, _ReproductionError, SyntheticEvidenceError) as exc:
        pending_error = exc
    except Exception as exc:
        pending_error = _ReproductionError(ReproductionFailureCode.UNEXPECTED_FAILURE)
        pending_error.__cause__ = exc
    finally:
        try:
            if store is not None:
                store.close()
            if backend is not None:
                backend.store.close()
        finally:
            try:
                temporary.cleanup()
            except Exception as exc:
                raise _ReproductionError(
                    ReproductionFailureCode.TEMP_CLEANUP_FAILED,
                    TemporaryWorkspaceState.CLEANUP_FAILED,
                ) from exc
    if root.exists():
        raise _ReproductionError(
            ReproductionFailureCode.TEMP_CLEANUP_FAILED,
            TemporaryWorkspaceState.CLEANUP_FAILED,
        )
    if pending_error is not None:
        raise pending_error
    if reproduced is None:
        raise _ReproductionError(ReproductionFailureCode.REPLAY_EVIDENCE_INVALID)
    return reproduced, TemporaryWorkspaceState.REMOVED


def _all_reproduced_values_present(receipt: SyntheticReproductionReceipt) -> bool:
    return all(
        value is not None
        for value in (
            receipt.reproduced_bundle_sha256,
            receipt.reproduced_observation_count,
            receipt.reproduced_observation_digest,
            receipt.reproduced_d1_outcome,
            receipt.reproduced_d1_receipt_digest,
            receipt.reproduced_artifact_sha256,
            receipt.reproduced_result_digest,
        )
    )


def _receipt_comparison_fields(receipt: SyntheticReproductionReceipt) -> tuple[str, ...]:
    comparisons = {
        "artifact_sha256": (
            receipt.source_artifact_sha256 == receipt.reproduced_artifact_sha256
        ),
        "bundle_sha256": receipt.source_bundle_sha256 == receipt.reproduced_bundle_sha256,
        "d1_failure_code": (
            receipt.source_d1_failure_code is receipt.reproduced_d1_failure_code
        ),
        "d1_outcome": receipt.source_d1_outcome is receipt.reproduced_d1_outcome,
        "d1_receipt_digest": (
            receipt.source_d1_receipt_digest == receipt.reproduced_d1_receipt_digest
        ),
        "integration_result_digest": (
            receipt.source_result_digest == receipt.reproduced_result_digest
        ),
        "observation_count": (
            receipt.source_observation_count == receipt.reproduced_observation_count
        ),
        "observation_digest": (
            receipt.source_observation_digest == receipt.reproduced_observation_digest
        ),
    }
    return tuple(sorted(name for name, matches in comparisons.items() if not matches))


def verify_reproduction_receipt_semantics(receipt: object) -> bool:
    if not isinstance(receipt, SyntheticReproductionReceipt):
        return False
    false_fields = (
        receipt.d1_go,
        receipt.production_reconciler_implemented,
        receipt.production_reconciler_real_storage_verified,
        receipt.real_data_deletion_authorized,
        receipt.execution_authorized,
        receipt.physical_camera_access_authorized,
        receipt.participant_collection_authorized,
        receipt.research_ready,
        receipt.collection_authorized,
        receipt.package_contains_integration,
    )
    if (
        receipt.schema_version != 1
        or receipt.artifact_kind != ARTIFACT_KIND
        or receipt.evidence_kind is not EvidenceKind.SIMULATED
        or receipt.device_gate_decision is not DeviceGateDecision.UNVERIFIED
        or receipt.authority_status != "AUTHORITY_NOT_ISSUED"
        or any(value is not False for value in false_fields)
        or receipt.result_digest != receipt.recompute_digest()
        or tuple(sorted(set(receipt.mismatch_fields))) != receipt.mismatch_fields
        or not set(receipt.mismatch_fields) <= MISMATCH_FIELDS
    ):
        return False
    if receipt.classification is ReproductionClassification.EXACTLY_REPRODUCED:
        return (
            receipt.status == STATUS
            and receipt.failure_code is None
            and receipt.temporary_workspace_state is TemporaryWorkspaceState.REMOVED
            and receipt.mismatch_fields == ()
            and _all_reproduced_values_present(receipt)
            and receipt.source_bundle_sha256 == receipt.reproduced_bundle_sha256
            and receipt.source_observation_count == receipt.reproduced_observation_count
            and receipt.source_observation_digest == receipt.reproduced_observation_digest
            and receipt.source_d1_outcome is receipt.reproduced_d1_outcome
            and receipt.source_d1_failure_code is receipt.reproduced_d1_failure_code
            and receipt.source_d1_receipt_digest == receipt.reproduced_d1_receipt_digest
            and receipt.source_artifact_sha256 == receipt.reproduced_artifact_sha256
            and receipt.source_result_digest == receipt.reproduced_result_digest
            and receipt.source_environment_binding_digest
            == receipt.current_environment_binding_digest
        )
    if receipt.classification is ReproductionClassification.SOURCE_REVISION_MISMATCH:
        return (
            receipt.status == NOT_VERIFIED_STATUS
            and receipt.failure_code is None
            and receipt.temporary_workspace_state is TemporaryWorkspaceState.NOT_CREATED
            and receipt.mismatch_fields == ()
            and receipt.source_environment_binding_digest is not None
            and receipt.current_environment_binding_digest is not None
            and receipt.source_environment_binding_digest
            != receipt.current_environment_binding_digest
            and receipt.reproduced_bundle_sha256 is None
        )
    if receipt.classification is ReproductionClassification.SEMANTIC_RESULT_MISMATCH:
        return (
            receipt.status == NOT_VERIFIED_STATUS
            and receipt.failure_code is None
            and receipt.temporary_workspace_state is TemporaryWorkspaceState.REMOVED
            and bool(receipt.mismatch_fields)
            and receipt.mismatch_fields == _receipt_comparison_fields(receipt)
            and _all_reproduced_values_present(receipt)
            and receipt.source_environment_binding_digest
            == receipt.current_environment_binding_digest
        )
    return (
        receipt.classification is ReproductionClassification.REPRODUCTION_FAILED
        and receipt.status == NOT_VERIFIED_STATUS
        and receipt.failure_code is not None
        and receipt.mismatch_fields == ()
    )


def reproduce_synthetic_evidence_bytes(payload: bytes) -> SyntheticReproductionReceipt:
    source_bundle_sha256 = (
        hashlib.sha256(payload).hexdigest() if isinstance(payload, bytes) and payload else None
    )
    if not isinstance(payload, bytes) or not payload:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.INPUT_INVALID,
            source=None,
            reproduced=None,
            current_environment_binding_digest=None,
            source_bundle_sha256=source_bundle_sha256,
        )
    try:
        source = load_verified_synthetic_evidence_bytes(payload)
    except SyntheticEvidenceError:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.SOURCE_EVIDENCE_REJECTED,
            source=None,
            reproduced=None,
            current_environment_binding_digest=None,
            source_bundle_sha256=source_bundle_sha256,
        )
    except Exception:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.SOURCE_EVIDENCE_REJECTED,
            source=None,
            reproduced=None,
            current_environment_binding_digest=None,
            source_bundle_sha256=source_bundle_sha256,
        )
    try:
        bindings = current_synthetic_environment_bindings()
        current_digest = synthetic_environment_binding_digest(bindings)
    except Exception:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.CURRENT_BINDING_UNAVAILABLE,
            source=source,
            reproduced=None,
            current_environment_binding_digest=None,
        )
    if source.environment_binding_digest != current_digest:
        return _make_receipt(
            classification=ReproductionClassification.SOURCE_REVISION_MISMATCH,
            failure_code=None,
            source=source,
            reproduced=None,
            current_environment_binding_digest=current_digest,
        )
    try:
        reproduced, workspace_state = _replay_verified_source(source, bindings)
    except PlatformUnsupported:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.PLATFORM_UNSUPPORTED,
            source=source,
            reproduced=None,
            current_environment_binding_digest=current_digest,
        )
    except SyntheticEvidenceError:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.REPLAY_EVIDENCE_INVALID,
            source=source,
            reproduced=None,
            current_environment_binding_digest=current_digest,
        )
    except _ReproductionError as exc:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=exc.code,
            source=source,
            reproduced=None,
            current_environment_binding_digest=current_digest,
            workspace_state=exc.workspace_state,
        )
    except Exception:
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.UNEXPECTED_FAILURE,
            source=source,
            reproduced=None,
            current_environment_binding_digest=current_digest,
        )
    if (
        reproduced.run_kind is not source.run_kind
        or reproduced.environment_binding_digest != current_digest
    ):
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.REPLAY_EVIDENCE_INVALID,
            source=source,
            reproduced=None,
            current_environment_binding_digest=current_digest,
            workspace_state=workspace_state,
        )
    mismatches = _comparison_fields(source, reproduced)
    receipt = _make_receipt(
        classification=(
            ReproductionClassification.EXACTLY_REPRODUCED
            if not mismatches
            else ReproductionClassification.SEMANTIC_RESULT_MISMATCH
        ),
        failure_code=None,
        source=source,
        reproduced=reproduced,
        current_environment_binding_digest=current_digest,
        mismatch_fields=mismatches,
        workspace_state=workspace_state,
    )
    if not verify_reproduction_receipt_semantics(receipt):
        return _make_receipt(
            classification=ReproductionClassification.REPRODUCTION_FAILED,
            failure_code=ReproductionFailureCode.AUTHORITY_CEILING_VIOLATION,
            source=source,
            reproduced=None,
            current_environment_binding_digest=current_digest,
            workspace_state=workspace_state,
        )
    return receipt
