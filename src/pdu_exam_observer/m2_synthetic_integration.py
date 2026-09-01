"""Synthetic-only M2 vertical slice; never a physical-device authority path."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import StrEnum

from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m2_d1_contract import (
    CANONICAL_PROPOSAL_SHA256,
    DEPENDENCY_ARTIFACT_NAME,
    DEPENDENCY_ARTIFACT_SHA256,
    REPRODUCTION_INVOCATION,
    AuthorityReceipt,
    D1FailureCode,
    D1Receipt,
    DeviceGateDecision,
    DiskEvidence,
    DropReason,
    EncoderDurabilityEvidence,
    EnvironmentReceipt,
    EvidenceKind,
    ExclusiveOwnerLease,
    FrameDisposition,
    InputKind,
    InputProvenanceReceipt,
    Observation,
    PrivacyGuard,
    ReproductionReceipt,
    RunKind,
    RunPlan,
    StageState,
    ThroughputSample,
    ValidationInput,
    ValidationOutcome,
    canonical_evaluation_digest,
    canonical_input_digest,
    evaluate,
    verify_receipt_semantics,
)
from pdu_exam_observer.m2_persistence import (
    ArtifactIntent,
    M2PersistenceStore,
    PersistenceFailure,
    PlatformUnsupported,
    StaticArtifactSource,
)
from pdu_exam_observer.m2_synthetic import (
    FixtureInput,
    ProcessingState,
    QualityState,
    ReservedNoHumanDeviceScene,
    SyntheticRunner,
    TechnicalFailureCode,
    TechnicalInputKind,
    TechnicalObservation,
    fixture_input_digest,
)

SCHEMA_VERSION = 1
STATUS = (
    "M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
NOMINAL_STATUS = (
    "M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
_OPAQUE_CHARACTERS = frozenset("-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


class IntegrationStatus(StrEnum):
    PERSISTED = "PERSISTED"
    NOT_PERSISTED = "NOT_PERSISTED"


class IntegrationFailureCode(StrEnum):
    REQUEST_INVALID = "REQUEST_INVALID"
    RUNNER_REJECTED = "RUNNER_REJECTED"
    D1_INPUT_INVALID = "D1_INPUT_INVALID"
    D1_RECEIPT_INVALID = "D1_RECEIPT_INVALID"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


@dataclass(frozen=True, slots=True)
class SyntheticEnvironmentBindings:
    application_revision_digest: str
    release_manifest_digest: str
    pose_engine_digest: str
    encoder_policy_digest: str
    injected_failure_codes: tuple[D1FailureCode, ...] = ()


@dataclass(frozen=True, slots=True)
class SyntheticPreflightRequest:
    session_id: str
    intent_id: str
    artifact_id: str
    run_id: str
    fixtures: tuple[FixtureInput, ...]
    parent_artifact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SyntheticNominalRequest:
    session_id: str
    intent_id: str
    artifact_id: str
    run_id: str
    fixtures: tuple[FixtureInput, ...]
    parent_artifact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SyntheticIntegrationReceipt:
    schema_version: int
    status: str
    integration_status: IntegrationStatus
    evidence_kind: EvidenceKind
    run_kind: RunKind
    d1_outcome: ValidationOutcome | None
    d1_failure_code: D1FailureCode | None
    integration_failure_code: IntegrationFailureCode | None
    device_gate_decision: DeviceGateDecision
    d1_go: bool
    authority_status: str
    physical_camera_access_authorized: bool
    participant_collection_authorized: bool
    collection_authorized: bool
    observation_count: int
    observation_digest: str | None
    d1_receipt_digest: str | None
    artifact_id: str | None
    artifact_sha256: str | None
    manifest_schema_version: int | None
    package_contains_integration: bool
    result_digest: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_sha256": self.artifact_sha256,
            "authority_status": self.authority_status,
            "collection_authorized": self.collection_authorized,
            "d1_failure_code": self.d1_failure_code.value if self.d1_failure_code else None,
            "d1_go": self.d1_go,
            "d1_outcome": self.d1_outcome.value if self.d1_outcome else None,
            "d1_receipt_digest": self.d1_receipt_digest,
            "device_gate_decision": self.device_gate_decision.value,
            "evidence_kind": self.evidence_kind.value,
            "integration_failure_code": (
                self.integration_failure_code.value if self.integration_failure_code else None
            ),
            "integration_status": self.integration_status.value,
            "manifest_schema_version": self.manifest_schema_version,
            "observation_count": self.observation_count,
            "observation_digest": self.observation_digest,
            "package_contains_integration": self.package_contains_integration,
            "participant_collection_authorized": self.participant_collection_authorized,
            "physical_camera_access_authorized": self.physical_camera_access_authorized,
            "run_kind": self.run_kind.value,
            "schema_version": self.schema_version,
            "status": self.status,
        }

    def recompute_digest(self) -> str:
        return _digest(self.canonical_payload())

    def as_dict(self) -> dict[str, object]:
        return {**self.canonical_payload(), "result_digest": self.result_digest}


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def map_technical_observation(value: TechnicalObservation) -> Observation:
    if (
        not isinstance(value, TechnicalObservation)
        or value.result_digest != value.recompute_result_digest()
    ):
        raise ValueError("technical observation is malformed")
    source_kind = _input_kind(value.technical_input_kind)
    if value.processing_state is ProcessingState.PROCESSED:
        quality_insufficient = (
            value.quality_state is QualityState.INSUFFICIENT
            or value.failure_code is TechnicalFailureCode.QUALITY_INSUFFICIENT
        )
        if value.failure_code not in {None, TechnicalFailureCode.QUALITY_INSUFFICIENT}:
            raise ValueError("processed observation carries an invalid failure")
        return Observation(
            source_kind=source_kind,
            captured_monotonic_ns=value.captured_monotonic_ns,
            processed_monotonic_ns=value.processed_monotonic_ns,
            disposition=FrameDisposition.PROCESSED,
            quality_insufficient=quality_insufficient,
            failure_code=None,
            drop_reason=None,
        )
    if value.processing_state is ProcessingState.DROPPED_EXPLICIT:
        return Observation(
            source_kind=source_kind,
            captured_monotonic_ns=value.captured_monotonic_ns,
            processed_monotonic_ns=None,
            disposition=FrameDisposition.DROPPED_EXPLICIT,
            quality_insufficient=False,
            failure_code=None,
            drop_reason=DropReason.BACKPRESSURE,
        )
    if value.processing_state is ProcessingState.FAILED and value.failure_code is not None:
        return Observation(
            source_kind=source_kind,
            captured_monotonic_ns=value.captured_monotonic_ns,
            processed_monotonic_ns=None,
            disposition=FrameDisposition.FAILED,
            quality_insufficient=False,
            failure_code=D1FailureCode(value.failure_code.value),
            drop_reason=None,
        )
    raise ValueError("technical observation state is malformed")


@dataclass(frozen=True, slots=True)
class _SyntheticRunContract:
    run_kind: RunKind
    requested_duration_seconds: int
    success_status: str
    failure_status: str
    artifact_kind: str
    deterministic_capture_profile: str


_PREFLIGHT_CONTRACT = _SyntheticRunContract(
    run_kind=RunKind.PREFLIGHT_60S,
    requested_duration_seconds=60,
    success_status=STATUS,
    failure_status="M2_S2A_SYNTHETIC_PREFLIGHT_NOT_PERSISTED",
    artifact_kind="M2_SYNTHETIC_PREFLIGHT_RECEIPT",
    deterministic_capture_profile="fixture-profile-v1",
)
_NOMINAL_CONTRACT = _SyntheticRunContract(
    run_kind=RunKind.NOMINAL_20M,
    requested_duration_seconds=1200,
    success_status=NOMINAL_STATUS,
    failure_status="M2_S2B_SYNTHETIC_NOMINAL_20M_NOT_PERSISTED",
    artifact_kind="M2_SYNTHETIC_NOMINAL_RECEIPT",
    deterministic_capture_profile="fixture-profile-v1",
)


class _M2SyntheticRunEngine:
    def __init__(
        self,
        *,
        runner: SyntheticRunner,
        privacy_guard: PrivacyGuard,
        owner_lease: ExclusiveOwnerLease,
        persistence_store: M2PersistenceStore,
        environment_bindings: SyntheticEnvironmentBindings,
    ) -> None:
        self._runner = runner
        self._privacy_guard = privacy_guard
        self._owner_lease = owner_lease
        self._store = persistence_store
        self._bindings = environment_bindings

    def execute(
        self,
        request: SyntheticPreflightRequest | SyntheticNominalRequest,
        contract: _SyntheticRunContract,
    ) -> SyntheticIntegrationReceipt:
        if not _request_is_valid(request) or not _bindings_are_valid(self._bindings):
            return _failure_receipt(IntegrationFailureCode.REQUEST_INVALID, contract=contract)
        observations: list[TechnicalObservation] = []
        try:
            for fixture in request.fixtures:
                observation = self._runner.process(fixture)
                if (
                    observation.run_id != request.run_id
                    or observation.frame_seq != fixture.frame_seq
                    or observation.fixture_id != fixture.fixture_id
                    or observation.fixture_version != fixture.fixture_version
                    or observation.fixture_input_hash != fixture_input_digest(fixture)
                    or observation.result_digest != observation.recompute_result_digest()
                    or (
                        observation.processing_state is ProcessingState.PROCESSED
                        and observation.quality_state is QualityState.VALID
                        and observation.failure_code is None
                        and observation.result_digest
                        != observation.golden_expected_output_digest
                    )
                ):
                    raise ValueError("runner observation binding is malformed")
                observations.append(observation)
            mapped = tuple(map_technical_observation(item) for item in observations)
        except (ReservedNoHumanDeviceScene, Exception):
            return _failure_receipt(
                IntegrationFailureCode.RUNNER_REJECTED,
                contract=contract,
                observation_count=len(observations),
            )
        try:
            validation = _build_validation_input(mapped, self._bindings, contract)
            d1_receipt = evaluate(
                validation,
                privacy_guard=self._privacy_guard,
                owner_lease=self._owner_lease,
            )
        except Exception:
            return _failure_receipt(
                IntegrationFailureCode.D1_INPUT_INVALID,
                contract=contract,
                observation_count=len(observations),
                observation_digest=_observation_digest(observations),
            )
        if not verify_receipt_semantics(d1_receipt):
            return _failure_receipt(
                IntegrationFailureCode.D1_RECEIPT_INVALID,
                contract=contract,
                observation_count=len(observations),
                observation_digest=_observation_digest(observations),
            )
        observation_digest = _observation_digest(observations)
        payload = _artifact_payload(observations, d1_receipt, self._bindings, contract)
        kind = request.fixtures[0].technical_input_kind
        intent = ArtifactIntent(
            intent_id=request.intent_id,
            artifact_id=request.artifact_id,
            session_id=request.session_id,
            artifact_kind="TECHNICAL_FIXTURE",
            technical_input_kind=kind.value,
            capture_profile_version=(
                contract.deterministic_capture_profile
                if kind is TechnicalInputKind.DETERMINISTIC_FIXTURE
                else "ai-rendered-profile-v1"
            ),
            monotonic_timing_origin=(
                "synthetic-monotonic-v1"
                if kind is TechnicalInputKind.DETERMINISTIC_FIXTURE
                else "ai-rendered-monotonic-v1"
            ),
            processing_version=(
                "fixture-generator-v1"
                if kind is TechnicalInputKind.DETERMINISTIC_FIXTURE
                else "ai-renderer-v1"
            ),
            parent_ids=request.parent_artifact_ids,
            technical_failure_code=(
                d1_receipt.failure_code.value if d1_receipt.failure_code else None
            ),
        )
        try:
            persisted = self._store.persist(intent, StaticArtifactSource(payload))
        except PlatformUnsupported:
            return _failure_receipt(
                IntegrationFailureCode.PLATFORM_UNSUPPORTED,
                contract=contract,
                observation_count=len(observations),
                observation_digest=observation_digest,
                d1_receipt=d1_receipt,
            )
        except (PersistenceFailure, InvalidTransition, Exception):
            return _failure_receipt(
                IntegrationFailureCode.PERSISTENCE_FAILED,
                contract=contract,
                observation_count=len(observations),
                observation_digest=observation_digest,
                d1_receipt=d1_receipt,
            )
        artifact_id = persisted.get("artifact_id")
        artifact_sha256 = persisted.get("sha256")
        manifest_schema_version = persisted.get("manifest_schema_version")
        if (
            not isinstance(artifact_id, str)
            or not _opaque(artifact_id)
            or not isinstance(artifact_sha256, str)
            or not _sha256(artifact_sha256)
            or type(manifest_schema_version) is not int
        ):
            return _failure_receipt(
                IntegrationFailureCode.PERSISTENCE_FAILED,
                contract=contract,
                observation_count=len(observations),
                observation_digest=observation_digest,
                d1_receipt=d1_receipt,
            )
        receipt = SyntheticIntegrationReceipt(
            schema_version=SCHEMA_VERSION,
            status=contract.success_status,
            integration_status=IntegrationStatus.PERSISTED,
            evidence_kind=EvidenceKind.SIMULATED,
            run_kind=contract.run_kind,
            d1_outcome=d1_receipt.outcome,
            d1_failure_code=d1_receipt.failure_code,
            integration_failure_code=None,
            device_gate_decision=DeviceGateDecision.UNVERIFIED,
            d1_go=False,
            authority_status="AUTHORITY_NOT_ISSUED",
            physical_camera_access_authorized=False,
            participant_collection_authorized=False,
            collection_authorized=False,
            observation_count=len(observations),
            observation_digest=observation_digest,
            d1_receipt_digest=d1_receipt.result_digest,
            artifact_id=artifact_id,
            artifact_sha256=artifact_sha256,
            manifest_schema_version=manifest_schema_version,
            package_contains_integration=False,
            result_digest="",
        )
        return replace(receipt, result_digest=receipt.recompute_digest())


class M2SyntheticPreflightCore:
    def __init__(
        self,
        *,
        runner: SyntheticRunner,
        privacy_guard: PrivacyGuard,
        owner_lease: ExclusiveOwnerLease,
        persistence_store: M2PersistenceStore,
        environment_bindings: SyntheticEnvironmentBindings,
    ) -> None:
        self._engine = _M2SyntheticRunEngine(
            runner=runner,
            privacy_guard=privacy_guard,
            owner_lease=owner_lease,
            persistence_store=persistence_store,
            environment_bindings=environment_bindings,
        )

    def execute(self, request: SyntheticPreflightRequest) -> SyntheticIntegrationReceipt:
        if not isinstance(request, SyntheticPreflightRequest):
            return _failure_receipt(
                IntegrationFailureCode.REQUEST_INVALID, contract=_PREFLIGHT_CONTRACT
            )
        return self._engine.execute(request, _PREFLIGHT_CONTRACT)


class M2SyntheticNominalCore:
    def __init__(
        self,
        *,
        runner: SyntheticRunner,
        privacy_guard: PrivacyGuard,
        owner_lease: ExclusiveOwnerLease,
        persistence_store: M2PersistenceStore,
        environment_bindings: SyntheticEnvironmentBindings,
    ) -> None:
        self._engine = _M2SyntheticRunEngine(
            runner=runner,
            privacy_guard=privacy_guard,
            owner_lease=owner_lease,
            persistence_store=persistence_store,
            environment_bindings=environment_bindings,
        )

    def execute(self, request: SyntheticNominalRequest) -> SyntheticIntegrationReceipt:
        if not isinstance(request, SyntheticNominalRequest):
            return _failure_receipt(
                IntegrationFailureCode.REQUEST_INVALID, contract=_NOMINAL_CONTRACT
            )
        return self._engine.execute(request, _NOMINAL_CONTRACT)


def _request_is_valid(request: object) -> bool:
    if (
        not isinstance(request, SyntheticPreflightRequest | SyntheticNominalRequest)
        or not request.fixtures
    ):
        return False
    identifiers = (
        request.session_id,
        request.intent_id,
        request.artifact_id,
        request.run_id,
        *request.parent_artifact_ids,
    )
    if not all(_opaque(value) for value in identifiers):
        return False
    if len(set(request.parent_artifact_ids)) != len(request.parent_artifact_ids):
        return False
    kinds = {
        item.technical_input_kind
        for item in request.fixtures
        if isinstance(item, FixtureInput)
    }
    if len(kinds) != 1 or not kinds.issubset(
        {TechnicalInputKind.DETERMINISTIC_FIXTURE, TechnicalInputKind.AI_RENDERED_FIXTURE}
    ):
        return False
    previous = -1
    fixture_ids: set[tuple[str, str]] = set()
    for fixture in request.fixtures:
        if (
            not isinstance(fixture, FixtureInput)
            or fixture.run_id != request.run_id
            or fixture.frame_seq <= previous
            or (fixture.fixture_id, fixture.fixture_version) in fixture_ids
        ):
            return False
        previous = fixture.frame_seq
        fixture_ids.add((fixture.fixture_id, fixture.fixture_version))
    return True


def _bindings_are_valid(value: object) -> bool:
    return isinstance(value, SyntheticEnvironmentBindings) and all(
        _sha256(item)
        for item in (
            value.application_revision_digest,
            value.release_manifest_digest,
            value.pose_engine_digest,
            value.encoder_policy_digest,
        )
    ) and all(isinstance(code, D1FailureCode) for code in value.injected_failure_codes)


def _build_validation_input(
    observations: tuple[Observation, ...],
    bindings: SyntheticEnvironmentBindings,
    contract: _SyntheticRunContract,
) -> ValidationInput:
    if not observations or len({item.source_kind for item in observations}) != 1:
        raise ValueError("preflight observations must have one input kind")
    input_kind = observations[0].source_kind
    run_end = max(
        observations[-1].captured_monotonic_ns + 10_000_000,
        max(
            (
                item.processed_monotonic_ns
                for item in observations
                if item.processed_monotonic_ns is not None
            ),
            default=0,
        ),
    )
    plan = RunPlan(
        run_kind=contract.run_kind,
        width=1280,
        height=720,
        frames_per_second=15,
        requested_duration_seconds=contract.requested_duration_seconds,
        warmup_seconds=5,
        run_end_monotonic_ns=run_end,
    )
    disk = DiskEvidence(
        free_bytes=3 * 1024**3,
        encoded_byte_count=max(1, (run_end - observations[0].captured_monotonic_ns) // 1_000),
        encoded_byte_rate=1_000_000.0,
        throughput_samples=tuple(ThroughputSample(index, 3_000_000.0) for index in range(60)),
        stages=EncoderDurabilityEvidence(
            StageState.SUCCEEDED,
            StageState.SUCCEEDED,
            StageState.SUCCEEDED,
            StageState.SUCCEEDED,
        ),
    )
    provenance_values = {
        InputKind.TEST_CHART: (
            "chart-v1",
            "d1-fixture-generator-v1",
            "d1-baseline-v1",
            ("mutant-ledger-v1",),
        ),
        InputKind.SYNTHETIC_VIDEO: (
            "video-v1",
            "d1-video-generator-v1",
            "d1-video-baseline-v1",
            ("video-mutant-ledger-v1",),
        ),
    }
    source_version, generator_id, baseline_id, mutant_ids = provenance_values[input_kind]
    input_digest = canonical_input_digest(plan, observations, disk)
    provenance = InputProvenanceReceipt(
        schema_version=1,
        source_kind=input_kind,
        source_version=source_version,
        generator_id=generator_id,
        canonical_input_digest=input_digest,
        frame_count=len(observations),
        simulated_no_human=True,
        dataset_use_prohibited=True,
        leakage_statement="N/A",
        deterministic_seed="N/A",
        baseline_id=baseline_id,
        mutant_ids=mutant_ids,
    )
    authority = AuthorityReceipt(
        schema_version=1,
        receipt_kind="D1_C1_AUTHORITY",
        decision_date="2026-08-26",
        decision_owner="root",
        proposal_sha256=CANONICAL_PROPOSAL_SHA256,
        readiness_version="0.4",
        p1_accepted=True,
        d1_authorized=True,
        physical_camera_access_authorized=False,
        participant_collection_authorized=False,
        model_evaluation_authorized=False,
        m1_recording_or_persistence_export_authorized=False,
    )
    environment = EnvironmentReceipt(
        schema_version=1,
        receipt_kind="D1_C1_INJECTED_ENVIRONMENT",
        application_revision_digest=bindings.application_revision_digest,
        release_manifest_digest=bindings.release_manifest_digest,
        pose_engine_digest=bindings.pose_engine_digest,
        encoder_digest=bindings.encoder_policy_digest,
        operating_system="SIMULATED-N/A",
        locale="N/A",
        timezone="N/A",
        offline=True,
        injected_only=True,
        camera_not_accessed=True,
        driver_unverified=True,
        audio_prohibited=True,
    )
    reproduction = ReproductionReceipt(
        schema_version=1,
        receipt_kind="D1_C1_REPRODUCTION",
        noninteractive_invocation=REPRODUCTION_INVOCATION,
        dependency_artifact=DEPENDENCY_ARTIFACT_NAME,
        lock_digest=DEPENDENCY_ARTIFACT_SHA256,
        source_digest=input_digest,
        deterministic_seed="N/A",
        threshold_version="d1-thresholds-v1",
        baseline_id=baseline_id,
        mutant_ids=mutant_ids,
        uncertainty_statement="SIMULATED_EVALUATOR_ONLY",
        input_digest=input_digest,
        expected_evaluation_digest="0" * 64,
    )
    draft = ValidationInput(
        schema_version=1,
        evidence_kind=EvidenceKind.SIMULATED,
        input_kind=input_kind,
        plan=plan,
        observations=observations,
        disk=disk,
        injected_failures=bindings.injected_failure_codes,
        authority=authority,
        provenance=provenance,
        environment=environment,
        reproduction=reproduction,
    )
    return replace(
        draft,
        reproduction=replace(
            reproduction,
            expected_evaluation_digest=canonical_evaluation_digest(draft),
        ),
    )


def _artifact_payload(
    observations: list[TechnicalObservation],
    receipt: D1Receipt,
    bindings: SyntheticEnvironmentBindings,
    contract: _SyntheticRunContract,
) -> bytes:
    result_digests = [item.result_digest for item in observations]
    return canonical_json_bytes(
        {
            "artifact_kind": contract.artifact_kind,
            "authority_ceiling": {
                "authority_status": "AUTHORITY_NOT_ISSUED",
                "collection_authorized": False,
                "d1_go": False,
                "device_gate_decision": "UNVERIFIED",
                "participant_collection_authorized": False,
                "physical_camera_access_authorized": False,
                "research_ready": False,
            },
            "d1_receipt": {**receipt.canonical_payload(), "result_digest": receipt.result_digest},
            "environment_binding_digest": _digest(
                {
                    "application_revision_digest": bindings.application_revision_digest,
                    "encoder_policy_digest": bindings.encoder_policy_digest,
                    "pose_engine_digest": bindings.pose_engine_digest,
                    "release_manifest_digest": bindings.release_manifest_digest,
                }
            ),
            "evidence_kind": "SIMULATED",
            "observation_digest": _digest(result_digests),
            "observation_result_digests": result_digests,
            "package_contains_integration": False,
            "schema_version": 1,
        }
    )


def _failure_receipt(
    code: IntegrationFailureCode,
    *,
    contract: _SyntheticRunContract,
    observation_count: int = 0,
    observation_digest: str | None = None,
    d1_receipt: D1Receipt | None = None,
) -> SyntheticIntegrationReceipt:
    receipt = SyntheticIntegrationReceipt(
        schema_version=SCHEMA_VERSION,
        status=contract.failure_status,
        integration_status=IntegrationStatus.NOT_PERSISTED,
        evidence_kind=EvidenceKind.SIMULATED,
        run_kind=contract.run_kind,
        d1_outcome=d1_receipt.outcome if d1_receipt else None,
        d1_failure_code=d1_receipt.failure_code if d1_receipt else None,
        integration_failure_code=code,
        device_gate_decision=DeviceGateDecision.UNVERIFIED,
        d1_go=False,
        authority_status="AUTHORITY_NOT_ISSUED",
        physical_camera_access_authorized=False,
        participant_collection_authorized=False,
        collection_authorized=False,
        observation_count=observation_count,
        observation_digest=observation_digest,
        d1_receipt_digest=d1_receipt.result_digest if d1_receipt else None,
        artifact_id=None,
        artifact_sha256=None,
        manifest_schema_version=None,
        package_contains_integration=False,
        result_digest="",
    )
    return replace(receipt, result_digest=receipt.recompute_digest())


def _input_kind(kind: TechnicalInputKind) -> InputKind:
    if kind is TechnicalInputKind.DETERMINISTIC_FIXTURE:
        return InputKind.TEST_CHART
    if kind is TechnicalInputKind.AI_RENDERED_FIXTURE:
        return InputKind.SYNTHETIC_VIDEO
    raise ValueError("reserved input kind")


def _observation_digest(observations: list[TechnicalObservation]) -> str:
    return _digest([item.result_digest for item in observations])


def _opaque(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 128 and set(value) <= _OPAQUE_CHARACTERS


def _sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
