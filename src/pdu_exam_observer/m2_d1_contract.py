"""Pure D1-C1 aggregate evaluator. It has no runtime device or storage adapter."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

CANONICAL_PROPOSAL_SHA256 = "2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5"
REPRODUCTION_INVOCATION = "python -m pytest tests/backend/test_m2_d1_contract.py"
DEPENDENCY_ARTIFACT_NAME = "uv.lock"
DEPENDENCY_ARTIFACT_SHA256 = "baf657e935bd76c34e097c6d7f02ebed902758b965148e5585f1cc7cad8b608c"


class InputKind(StrEnum):
    TEST_CHART = "TEST_CHART"
    SYNTHETIC_VIDEO = "SYNTHETIC_VIDEO"


_PROVENANCE_ALLOWLIST = {
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


class EvidenceKind(StrEnum):
    SIMULATED = "SIMULATED"


class RunKind(StrEnum):
    PREFLIGHT_60S = "PREFLIGHT_60S"
    NOMINAL_20M = "NOMINAL_20M"


class PrivacyDecision(StrEnum):
    CLEAR = "CLEAR"
    UNSAFE = "UNSAFE"
    UNKNOWN = "UNKNOWN"


class FrameDisposition(StrEnum):
    PROCESSED = "PROCESSED"
    DROPPED_EXPLICIT = "DROPPED_EXPLICIT"
    FAILED = "FAILED"


class DropReason(StrEnum):
    BACKPRESSURE = "BACKPRESSURE"


class StageState(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class ValidationOutcome(StrEnum):
    BACKEND_CONTRACT_PASS = "BACKEND_CONTRACT_PASS"
    NO_GO = "NO_GO"


class DeviceGateDecision(StrEnum):
    UNVERIFIED = "UNVERIFIED"


class D1FailureCode(StrEnum):
    INPUT_UNAVAILABLE = "INPUT_UNAVAILABLE"
    INPUT_MALFORMED = "INPUT_MALFORMED"
    FRAME_STALLED = "FRAME_STALLED"
    CLOCK_REGRESSION = "CLOCK_REGRESSION"
    POSE_ENGINE_UNAVAILABLE = "POSE_ENGINE_UNAVAILABLE"
    POSE_ENGINE_EXCEPTION = "POSE_ENGINE_EXCEPTION"
    POSE_OUTPUT_INVALID = "POSE_OUTPUT_INVALID"
    QUALITY_INSUFFICIENT = "QUALITY_INSUFFICIENT"
    ENCODER_UNAVAILABLE = "ENCODER_UNAVAILABLE"
    ENCODER_WRITE_FAILED = "ENCODER_WRITE_FAILED"
    ENCODER_FINALIZE_FAILED = "ENCODER_FINALIZE_FAILED"
    DISK_UNAVAILABLE = "DISK_UNAVAILABLE"
    DISK_SPACE_INSUFFICIENT = "DISK_SPACE_INSUFFICIENT"
    DISK_THROUGHPUT_INSUFFICIENT = "DISK_THROUGHPUT_INSUFFICIENT"
    DISK_FSYNC_FAILED = "DISK_FSYNC_FAILED"
    ATOMIC_RENAME_FAILED = "ATOMIC_RENAME_FAILED"
    MANIFEST_VALIDATION_FAILED = "MANIFEST_VALIDATION_FAILED"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"
    PRIVACY_STOP = "PRIVACY_STOP"
    UNKNOWN_TECHNICAL_FAILURE = "UNKNOWN_TECHNICAL_FAILURE"


@dataclass(frozen=True, slots=True)
class RunPlan:
    run_kind: RunKind
    width: int
    height: int
    frames_per_second: int
    requested_duration_seconds: int
    warmup_seconds: int
    run_end_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class Observation:
    source_kind: InputKind
    captured_monotonic_ns: int
    processed_monotonic_ns: int | None
    disposition: FrameDisposition
    quality_insufficient: bool
    failure_code: D1FailureCode | None
    drop_reason: DropReason | None


@dataclass(frozen=True, slots=True)
class ThroughputSample:
    second_index: int
    bytes_per_second: float


@dataclass(frozen=True, slots=True)
class EncoderDurabilityEvidence:
    encoder_open: StageState
    encoder_write: StageState
    encoder_finalize: StageState
    durability: StageState


@dataclass(frozen=True, slots=True)
class DiskEvidence:
    free_bytes: int
    encoded_byte_count: int
    encoded_byte_rate: float
    throughput_samples: tuple[ThroughputSample, ...]
    stages: EncoderDurabilityEvidence


@dataclass(frozen=True, slots=True)
class AuthorityReceipt:
    schema_version: int
    receipt_kind: str
    decision_date: str
    decision_owner: str
    proposal_sha256: str
    readiness_version: str
    p1_accepted: bool
    d1_authorized: bool
    physical_camera_access_authorized: bool
    participant_collection_authorized: bool
    model_evaluation_authorized: bool
    m1_recording_or_persistence_export_authorized: bool


@dataclass(frozen=True, slots=True)
class InputProvenanceReceipt:
    schema_version: int
    source_kind: InputKind
    source_version: str
    generator_id: str
    canonical_input_digest: str
    frame_count: int
    simulated_no_human: bool
    dataset_use_prohibited: bool
    leakage_statement: str
    deterministic_seed: str
    baseline_id: str
    mutant_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EnvironmentReceipt:
    schema_version: int
    receipt_kind: str
    application_revision_digest: str
    release_manifest_digest: str
    pose_engine_digest: str
    encoder_digest: str
    operating_system: str
    locale: str
    timezone: str
    offline: bool
    injected_only: bool
    camera_not_accessed: bool
    driver_unverified: bool
    audio_prohibited: bool


@dataclass(frozen=True, slots=True)
class ReproductionReceipt:
    schema_version: int
    receipt_kind: str
    noninteractive_invocation: str
    dependency_artifact: str
    lock_digest: str
    source_digest: str
    deterministic_seed: str
    threshold_version: str
    baseline_id: str
    mutant_ids: tuple[str, ...]
    uncertainty_statement: str
    input_digest: str
    expected_evaluation_digest: str


@dataclass(frozen=True, slots=True)
class ValidationInput:
    schema_version: int
    evidence_kind: EvidenceKind
    input_kind: InputKind
    plan: RunPlan
    observations: tuple[Observation, ...]
    disk: DiskEvidence
    injected_failures: tuple[D1FailureCode, ...]
    authority: AuthorityReceipt
    provenance: InputProvenanceReceipt
    environment: EnvironmentReceipt
    reproduction: ReproductionReceipt


class PrivacyGuard(Protocol):
    def inspect(self, observation: Observation) -> PrivacyDecision: ...


class ExclusiveOwnerLease(Protocol):
    def acquire(self) -> bool: ...

    def release(self) -> None: ...


@dataclass(frozen=True, slots=True)
class Accounting:
    delivered_frames: int
    inter_frame_gaps: int
    processed: int
    dropped_explicit: int
    failed: int
    quality_insufficient: int
    drop_reasons: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class MetricSummary:
    first_capture_monotonic_ns: int
    run_end_monotonic_ns: int
    measured_total_seconds: float
    measured_post_warmup_seconds: float
    delivered_frames_per_second: float
    p95_inter_frame_gap_ms: float | None
    p95_pose_latency_ms: float | None
    p99_pose_latency_ms: float | None
    p10_preflight_throughput_bytes_per_second: float | None
    backlog_ms: float | None


@dataclass(frozen=True, slots=True)
class D1Receipt:
    schema_version: int
    outcome: ValidationOutcome
    device_gate_decision: DeviceGateDecision
    evidence_kind: EvidenceKind
    failure_code: D1FailureCode | None
    failure_counts: tuple[tuple[str, int], ...]
    run_kind: RunKind
    width: int
    height: int
    frames_per_second: int
    requested_duration_seconds: int
    warmup_seconds: int
    privacy_checked_frames: int
    privacy_stop_count: int
    warmup_accounting: Accounting
    accounting: Accounting
    metrics: MetricSummary
    required_bytes: int
    free_bytes: int
    encoded_byte_count: int
    encoded_byte_rate: float
    throughput_sample_count: int
    throughput_digest: str
    stages: EncoderDurabilityEvidence
    seal_attempted: bool
    export_attempted: bool
    authority_digest: str
    input_digest: str
    provenance_digest: str
    environment_digest: str
    reproduction_digest: str
    evaluation_core_digest: str
    result_digest: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "accounting": _accounting_payload(self.accounting),
            "authority_digest": self.authority_digest,
            "device_gate_decision": (
                self.device_gate_decision.value
                if isinstance(self.device_gate_decision, DeviceGateDecision)
                else None
            ),
            "encoded_byte_count": self.encoded_byte_count,
            "encoded_byte_rate": self.encoded_byte_rate,
            "environment_digest": self.environment_digest,
            "evaluation_core_digest": self.evaluation_core_digest,
            "evidence_kind": (
                self.evidence_kind.value if isinstance(self.evidence_kind, EvidenceKind) else None
            ),
            "export_attempted": self.export_attempted,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "failure_counts": [list(item) for item in self.failure_counts],
            "frames_per_second": self.frames_per_second,
            "free_bytes": self.free_bytes,
            "input_digest": self.input_digest,
            "metrics": _metrics_payload(self.metrics),
            "outcome": self.outcome.value if isinstance(self.outcome, ValidationOutcome) else None,
            "privacy_checked_frames": self.privacy_checked_frames,
            "privacy_stop_count": self.privacy_stop_count,
            "provenance_digest": self.provenance_digest,
            "reproduction_digest": self.reproduction_digest,
            "required_bytes": self.required_bytes,
            "requested_duration_seconds": self.requested_duration_seconds,
            "run_kind": self.run_kind.value if isinstance(self.run_kind, RunKind) else None,
            "schema_version": self.schema_version,
            "seal_attempted": self.seal_attempted,
            "stages": _stage_payload(self.stages),
            "throughput_digest": self.throughput_digest,
            "throughput_sample_count": self.throughput_sample_count,
            "warmup_accounting": _accounting_payload(self.warmup_accounting),
            "warmup_seconds": self.warmup_seconds,
            "width": self.width,
            "height": self.height,
        }

    def recompute_digest(self) -> str:
        return _digest(self.canonical_payload())


def evaluate(
    request: ValidationInput, *, privacy_guard: PrivacyGuard, owner_lease: ExclusiveOwnerLease
) -> D1Receipt:
    _validate_request(request)
    try:
        acquired = owner_lease.acquire()
    except Exception:
        return _failure_receipt(request, D1FailureCode.SCHEMA_INCOMPATIBLE)
    if acquired is not True:
        return _failure_receipt(request, D1FailureCode.SCHEMA_INCOMPATIBLE)
    try:
        result = _evaluate_under_lease(request, privacy_guard)
    except Exception:
        result = _failure_receipt(request, D1FailureCode.UNKNOWN_TECHNICAL_FAILURE)
    try:
        owner_lease.release()
    except Exception:
        return _failure_receipt(request, D1FailureCode.SCHEMA_INCOMPATIBLE)
    return result


def nearest_rank(values: tuple[float, ...], percentile: int) -> float:
    if not values or not isinstance(percentile, int) or not 1 <= percentile <= 100:
        raise ValueError("percentile requires nonempty values and a 1..100 rank")
    if not all(isinstance(value, int | float) and math.isfinite(value) for value in values):
        raise ValueError("percentile values must be finite")
    ranked = sorted(float(value) for value in values)
    return ranked[math.ceil(percentile * len(ranked) / 100) - 1]


def canonical_input_digest(
    plan: RunPlan, observations: tuple[Observation, ...], disk: DiskEvidence
) -> str:
    return _digest(_input_core_payload(plan, observations, disk))


def canonical_evaluation_digest(request: ValidationInput) -> str:
    return _digest(
        {
            "core_version": 1,
            "input_digest": canonical_input_digest(
                request.plan, request.observations, request.disk
            ),
            "input_kind": request.input_kind.value
            if isinstance(request.input_kind, InputKind)
            else None,
            "injected_failures": [
                value.value if isinstance(value, D1FailureCode) else None
                for value in request.injected_failures
            ],
        }
    )


def verify_receipt_semantics(receipt: D1Receipt) -> bool:
    if not isinstance(receipt, D1Receipt) or receipt.schema_version != 1:
        return False
    if receipt.evidence_kind is not EvidenceKind.SIMULATED:
        return False
    if receipt.device_gate_decision is not DeviceGateDecision.UNVERIFIED:
        return False
    if receipt.seal_attempted or receipt.export_attempted:
        return False
    if not _accounting_is_semantic(receipt.warmup_accounting) or not _accounting_is_semantic(
        receipt.accounting
    ):
        return False
    counts = receipt.failure_counts
    if not _failure_counts_are_semantic(counts):
        return False
    required_duration = {RunKind.PREFLIGHT_60S: 60, RunKind.NOMINAL_20M: 1200}
    if (
        receipt.run_kind not in required_duration
        or receipt.requested_duration_seconds != required_duration[receipt.run_kind]
        or (receipt.width, receipt.height, receipt.frames_per_second, receipt.warmup_seconds)
        != (1280, 720, 15, 5)
    ):
        return False
    if receipt.failure_code is D1FailureCode.PRIVACY_STOP:
        empty = Accounting(0, 0, 0, 0, 0, 0, ())
        not_attempted = EncoderDurabilityEvidence(
            StageState.NOT_ATTEMPTED,
            StageState.NOT_ATTEMPTED,
            StageState.NOT_ATTEMPTED,
            StageState.NOT_ATTEMPTED,
        )
        if (
            receipt.outcome is not ValidationOutcome.NO_GO
            or counts != ((D1FailureCode.PRIVACY_STOP.value, 1),)
            or receipt.privacy_checked_frames < 1
            or receipt.privacy_stop_count != 1
            or receipt.warmup_accounting != empty
            or receipt.accounting != empty
            or receipt.required_bytes != 0
            or receipt.free_bytes != 0
            or receipt.encoded_byte_count != 0
            or receipt.encoded_byte_rate != 0
            or receipt.throughput_sample_count != 0
            or receipt.throughput_digest != _digest([])
            or receipt.stages != not_attempted
            or receipt.input_digest != _privacy_stop_digest(receipt.privacy_checked_frames)
            or receipt.provenance_digest != _privacy_stop_digest(receipt.privacy_checked_frames)
            or receipt.reproduction_digest != _privacy_stop_digest(receipt.privacy_checked_frames)
            or receipt.evaluation_core_digest
            != _privacy_stop_digest(receipt.privacy_checked_frames)
        ):
            return False
        return receipt.result_digest == receipt.recompute_digest()
    expected_required = max(
        2 * 1024**3,
        int(2 * receipt.encoded_byte_rate * receipt.requested_duration_seconds),
    )
    if receipt.required_bytes != expected_required or receipt.free_bytes < receipt.required_bytes:
        return False
    if receipt.throughput_sample_count != 60 or not _is_digest(receipt.throughput_digest):
        return False
    if receipt.outcome is ValidationOutcome.BACKEND_CONTRACT_PASS:
        delivered = receipt.warmup_accounting.delivered_frames + receipt.accounting.delivered_frames
        if (
            receipt.failure_code is not None
            or counts
            or receipt.privacy_stop_count != 0
            or receipt.privacy_checked_frames != delivered
        ):
            return False
        if receipt.accounting.quality_insufficient != 0 or receipt.encoded_byte_count <= 0:
            return False
        if receipt.encoded_byte_rate <= 0 or not _stages_succeeded(receipt.stages):
            return False
        if not _metrics_are_semantic(receipt.metrics, receipt):
            return False
        if not math.isclose(
            receipt.encoded_byte_count / receipt.encoded_byte_rate,
            receipt.metrics.measured_total_seconds,
            abs_tol=0.001,
        ):
            return False
    elif receipt.outcome is ValidationOutcome.NO_GO:
        if receipt.failure_code is None or receipt.failure_code.value not in dict(counts):
            return False
    else:
        return False
    if receipt.privacy_checked_frames < 0 or receipt.privacy_stop_count < 0:
        return False
    if receipt.privacy_checked_frames < receipt.privacy_stop_count:
        return False
    return receipt.result_digest == receipt.recompute_digest()


def _evaluate_under_lease(request: ValidationInput, guard: PrivacyGuard) -> D1Receipt:
    checked = 0
    for observation in request.observations:
        checked += 1
        try:
            decision = guard.inspect(observation)
        except Exception:
            return _failure_receipt(
                request,
                D1FailureCode.PRIVACY_STOP,
                checked=checked,
                stops=1,
                counts=((D1FailureCode.PRIVACY_STOP.value, 1),),
            )
        if decision is not PrivacyDecision.CLEAR:
            return _failure_receipt(
                request,
                D1FailureCode.PRIVACY_STOP,
                checked=checked,
                stops=1,
                counts=((D1FailureCode.PRIVACY_STOP.value, 1),),
            )
    error = _validate_observations(request)
    if error is not None:
        return _failure_receipt(request, error, checked=checked)
    warmup, post = _split_warmup(request)
    warmup_accounting = _accounting(warmup)
    accounting = _accounting(post)
    counts = _failure_counts(request)
    if counts:
        return _failure_receipt(
            request, _first_count_code(counts), warmup, accounting, checked=checked, counts=counts
        )
    if accounting.delivered_frames == 0:
        return _failure_receipt(
            request, D1FailureCode.INPUT_UNAVAILABLE, warmup, accounting, checked=checked
        )
    if (
        accounting.processed + accounting.dropped_explicit + accounting.failed
        != accounting.delivered_frames
    ):
        return _failure_receipt(
            request, D1FailureCode.SCHEMA_INCOMPATIBLE, warmup, accounting, checked=checked
        )
    if accounting.quality_insufficient:
        return _failure_receipt(
            request, D1FailureCode.QUALITY_INSUFFICIENT, warmup, accounting, checked=checked
        )
    stage_code = _stage_failure(request.disk.stages)
    if stage_code is not None:
        return _failure_receipt(request, stage_code, warmup, accounting, checked=checked)
    metrics = _metrics(request, post)
    if metrics is None:
        return _failure_receipt(
            request, D1FailureCode.SCHEMA_INCOMPATIBLE, warmup, accounting, checked=checked
        )
    if request.disk.encoded_byte_count <= 0 or request.disk.encoded_byte_rate <= 0:
        return _failure_receipt(
            request, D1FailureCode.ENCODER_WRITE_FAILED, warmup, accounting, metrics, checked
        )
    if not math.isclose(
        request.disk.encoded_byte_count / request.disk.encoded_byte_rate,
        metrics.measured_total_seconds,
        abs_tol=0.001,
    ):
        return _failure_receipt(
            request, D1FailureCode.SCHEMA_INCOMPATIBLE, warmup, accounting, metrics, checked
        )
    threshold_failure = _threshold_failure(request, accounting, metrics)
    if threshold_failure is not None:
        return _failure_receipt(request, threshold_failure, warmup, accounting, metrics, checked)
    return _receipt(
        request,
        ValidationOutcome.BACKEND_CONTRACT_PASS,
        None,
        (),
        checked,
        0,
        warmup_accounting,
        accounting,
        metrics,
    )


def _validate_request(request: ValidationInput) -> None:
    if not isinstance(request, ValidationInput) or request.schema_version != 1:
        raise ValueError("input schema is not supported")
    if request.evidence_kind is not EvidenceKind.SIMULATED or not isinstance(
        request.input_kind, InputKind
    ):
        raise ValueError("input kind is not allowed")
    _validate_plan(request.plan)
    _validate_authority(request.authority)
    if not isinstance(request.observations, tuple) or not isinstance(request.disk, DiskEvidence):
        raise ValueError("input aggregate is malformed")
    if not isinstance(request.injected_failures, tuple) or any(
        not isinstance(value, D1FailureCode) for value in request.injected_failures
    ):
        raise ValueError("failure values are not allowlisted")
    _validate_disk_shape(request.disk)
    _validate_provenance(request)
    _validate_environment(request.environment)
    _validate_reproduction(request)


def _validate_plan(plan: RunPlan) -> None:
    required = {RunKind.PREFLIGHT_60S: 60, RunKind.NOMINAL_20M: 1200}
    if (
        not isinstance(plan, RunPlan)
        or plan.run_kind not in required
        or plan.requested_duration_seconds != required[plan.run_kind]
        or (plan.width, plan.height, plan.frames_per_second, plan.warmup_seconds)
        != (1280, 720, 15, 5)
        or not isinstance(plan.run_end_monotonic_ns, int)
        or plan.run_end_monotonic_ns < 0
    ):
        raise ValueError("plan must retain the exact D1 profile and durations")


def _validate_authority(value: AuthorityReceipt) -> None:
    if (
        not isinstance(value, AuthorityReceipt)
        or value.schema_version != 1
        or value.receipt_kind != "D1_C1_AUTHORITY"
        or value.decision_date != "2026-08-26"
        or value.decision_owner != "root"
        or value.proposal_sha256 != CANONICAL_PROPOSAL_SHA256
        or value.readiness_version != "0.4"
        or (value.p1_accepted, value.d1_authorized) != (True, True)
        or any(
            (
                value.physical_camera_access_authorized,
                value.participant_collection_authorized,
                value.model_evaluation_authorized,
                value.m1_recording_or_persistence_export_authorized,
            )
        )
    ):
        raise ValueError("input authority is not accepted")


def _validate_disk_shape(disk: DiskEvidence) -> None:
    if (
        not isinstance(disk.free_bytes, int)
        or disk.free_bytes < 0
        or not isinstance(disk.encoded_byte_count, int)
        or disk.encoded_byte_count < 0
        or not isinstance(disk.encoded_byte_rate, int | float)
        or not math.isfinite(disk.encoded_byte_rate)
        or disk.encoded_byte_rate < 0
        or not isinstance(disk.stages, EncoderDurabilityEvidence)
        or any(
            not isinstance(getattr(disk.stages, name), StageState)
            for name in ("encoder_open", "encoder_write", "encoder_finalize", "durability")
        )
        or len(disk.throughput_samples) != 60
    ):
        raise ValueError("disk aggregate is malformed")
    for index, sample in enumerate(disk.throughput_samples):
        if (
            not isinstance(sample, ThroughputSample)
            or sample.second_index != index
            or not isinstance(sample.bytes_per_second, int | float)
            or not math.isfinite(sample.bytes_per_second)
            or sample.bytes_per_second < 0
        ):
            raise ValueError("disk throughput samples are malformed")


def _validate_provenance(request: ValidationInput) -> None:
    value = request.provenance
    expected = _PROVENANCE_ALLOWLIST.get(request.input_kind)
    if (
        not isinstance(value, InputProvenanceReceipt)
        or value.schema_version != 1
        or value.source_kind is not request.input_kind
        or expected is None
        or (value.source_version, value.generator_id, value.baseline_id, value.mutant_ids)
        != expected
        or value.canonical_input_digest
        != canonical_input_digest(request.plan, request.observations, request.disk)
        or value.frame_count != len(request.observations)
        or value.simulated_no_human is not True
        or value.dataset_use_prohibited is not True
        or value.leakage_statement != "N/A"
        or value.deterministic_seed != "N/A"
    ):
        raise ValueError("input provenance is malformed")


def _validate_environment(value: EnvironmentReceipt) -> None:
    if (
        not isinstance(value, EnvironmentReceipt)
        or value.schema_version != 1
        or value.receipt_kind != "D1_C1_INJECTED_ENVIRONMENT"
        or not all(
            _is_digest(item)
            for item in (
                value.application_revision_digest,
                value.release_manifest_digest,
                value.pose_engine_digest,
                value.encoder_digest,
            )
        )
        or (value.operating_system, value.locale, value.timezone) != ("SIMULATED-N/A", "N/A", "N/A")
        or (
            value.offline,
            value.injected_only,
            value.camera_not_accessed,
            value.driver_unverified,
            value.audio_prohibited,
        )
        != (True, True, True, True, True)
    ):
        raise ValueError("input environment is malformed")


def _validate_reproduction(request: ValidationInput) -> None:
    value = request.reproduction
    if (
        not isinstance(value, ReproductionReceipt)
        or value.schema_version != 1
        or value.receipt_kind != "D1_C1_REPRODUCTION"
        or value.noninteractive_invocation != REPRODUCTION_INVOCATION
        or value.dependency_artifact != DEPENDENCY_ARTIFACT_NAME
        or value.lock_digest != DEPENDENCY_ARTIFACT_SHA256
        or value.source_digest != request.provenance.canonical_input_digest
        or value.deterministic_seed != "N/A"
        or value.threshold_version != "d1-thresholds-v1"
        or value.baseline_id != request.provenance.baseline_id
        or value.mutant_ids != request.provenance.mutant_ids
        or value.uncertainty_statement != "SIMULATED_EVALUATOR_ONLY"
        or value.input_digest != request.provenance.canonical_input_digest
        or value.expected_evaluation_digest != canonical_evaluation_digest(request)
    ):
        raise ValueError("input reproduction receipt is malformed")


def _validate_observations(request: ValidationInput) -> D1FailureCode | None:
    previous_capture: int | None = None
    previous_processed: int | None = None
    for item in request.observations:
        if not isinstance(item, Observation) or item.source_kind is not request.input_kind:
            return D1FailureCode.SCHEMA_INCOMPATIBLE
        if (
            not isinstance(item.captured_monotonic_ns, int)
            or item.captured_monotonic_ns < 0
            or item.captured_monotonic_ns > request.plan.run_end_monotonic_ns
        ):
            return D1FailureCode.SCHEMA_INCOMPATIBLE
        if previous_capture is not None:
            if item.captured_monotonic_ns == previous_capture:
                return D1FailureCode.FRAME_STALLED
            if item.captured_monotonic_ns < previous_capture:
                return D1FailureCode.CLOCK_REGRESSION
            if item.captured_monotonic_ns - previous_capture >= 1_000_000_000:
                return D1FailureCode.FRAME_STALLED
        previous_capture = item.captured_monotonic_ns
        if item.disposition is FrameDisposition.PROCESSED:
            if (
                not isinstance(item.processed_monotonic_ns, int)
                or item.processed_monotonic_ns < item.captured_monotonic_ns
                or item.processed_monotonic_ns > request.plan.run_end_monotonic_ns
                or item.failure_code is not None
                or item.drop_reason is not None
            ):
                return D1FailureCode.SCHEMA_INCOMPATIBLE
            if previous_processed is not None and item.processed_monotonic_ns <= previous_processed:
                return D1FailureCode.CLOCK_REGRESSION
            previous_processed = item.processed_monotonic_ns
        elif item.disposition is FrameDisposition.DROPPED_EXPLICIT:
            if (
                item.processed_monotonic_ns is not None
                or item.failure_code is not None
                or not isinstance(item.drop_reason, DropReason)
            ):
                return D1FailureCode.SCHEMA_INCOMPATIBLE
        elif item.disposition is FrameDisposition.FAILED:
            if (
                item.processed_monotonic_ns is not None
                or not isinstance(item.failure_code, D1FailureCode)
                or item.drop_reason is not None
            ):
                return D1FailureCode.SCHEMA_INCOMPATIBLE
        else:
            return D1FailureCode.SCHEMA_INCOMPATIBLE
        if not isinstance(item.quality_insufficient, bool) or (
            item.quality_insufficient and item.disposition is not FrameDisposition.PROCESSED
        ):
            return D1FailureCode.SCHEMA_INCOMPATIBLE
    return None


def _split_warmup(
    request: ValidationInput,
) -> tuple[tuple[Observation, ...], tuple[Observation, ...]]:
    if not request.observations:
        return (), ()
    boundary = (
        request.observations[0].captured_monotonic_ns + request.plan.warmup_seconds * 1_000_000_000
    )
    return (
        tuple(item for item in request.observations if item.captured_monotonic_ns < boundary),
        tuple(item for item in request.observations if item.captured_monotonic_ns >= boundary),
    )


def _accounting(items: tuple[Observation, ...]) -> Accounting:
    reasons: dict[str, int] = {}
    for item in items:
        if item.drop_reason is not None:
            reasons[item.drop_reason.value] = reasons.get(item.drop_reason.value, 0) + 1
    return Accounting(
        delivered_frames=len(items),
        inter_frame_gaps=max(len(items) - 1, 0),
        processed=sum(item.disposition is FrameDisposition.PROCESSED for item in items),
        dropped_explicit=sum(
            item.disposition is FrameDisposition.DROPPED_EXPLICIT for item in items
        ),
        failed=sum(item.disposition is FrameDisposition.FAILED for item in items),
        quality_insufficient=sum(item.quality_insufficient for item in items),
        drop_reasons=tuple(sorted(reasons.items())),
    )


def _failure_counts(
    request: ValidationInput, privacy_stop: bool = False
) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for item in request.observations:
        if item.failure_code is not None:
            counts[item.failure_code.value] = counts.get(item.failure_code.value, 0) + 1
        if item.quality_insufficient:
            counts[D1FailureCode.QUALITY_INSUFFICIENT.value] = (
                counts.get(D1FailureCode.QUALITY_INSUFFICIENT.value, 0) + 1
            )
    for code in request.injected_failures:
        counts[code.value] = counts.get(code.value, 0) + 1
    if privacy_stop:
        counts[D1FailureCode.PRIVACY_STOP.value] = (
            counts.get(D1FailureCode.PRIVACY_STOP.value, 0) + 1
        )
    return tuple(sorted(counts.items()))


def _first_count_code(counts: tuple[tuple[str, int], ...]) -> D1FailureCode:
    return D1FailureCode(counts[0][0])


def _metrics(request: ValidationInput, post: tuple[Observation, ...]) -> MetricSummary | None:
    if not request.observations or not post:
        return None
    first = request.observations[0].captured_monotonic_ns
    end = request.plan.run_end_monotonic_ns
    total = (end - first) / 1_000_000_000
    warmup_boundary = first + request.plan.warmup_seconds * 1_000_000_000
    post_seconds = (end - warmup_boundary) / 1_000_000_000
    if (
        total <= 0
        or post_seconds <= 0
        or not math.isfinite(total)
        or not math.isfinite(post_seconds)
    ):
        return None
    gaps = tuple(
        (right.captured_monotonic_ns - left.captured_monotonic_ns) / 1_000_000
        for left, right in zip(post, post[1:], strict=False)
    )
    processed = tuple(item for item in post if item.disposition is FrameDisposition.PROCESSED)
    latencies = tuple(
        (item.processed_monotonic_ns - item.captured_monotonic_ns) / 1_000_000
        for item in processed
        if item.processed_monotonic_ns is not None
    )
    latest_completed = max(
        processed, key=lambda item: item.processed_monotonic_ns or -1, default=None
    )
    backlog = (
        None
        if latest_completed is None
        else (post[-1].captured_monotonic_ns - latest_completed.captured_monotonic_ns) / 1_000_000
    )
    if backlog is not None and backlog < 0:
        return None
    rates = tuple(item.bytes_per_second for item in request.disk.throughput_samples)
    return MetricSummary(
        first_capture_monotonic_ns=first,
        run_end_monotonic_ns=end,
        measured_total_seconds=total,
        measured_post_warmup_seconds=post_seconds,
        delivered_frames_per_second=len(post) / post_seconds,
        p95_inter_frame_gap_ms=nearest_rank(gaps, 95) if gaps else None,
        p95_pose_latency_ms=nearest_rank(latencies, 95) if latencies else None,
        p99_pose_latency_ms=nearest_rank(latencies, 99) if latencies else None,
        p10_preflight_throughput_bytes_per_second=nearest_rank(rates, 10),
        backlog_ms=backlog,
    )


def _threshold_failure(
    request: ValidationInput, accounting: Accounting, metrics: MetricSummary
) -> D1FailureCode | None:
    if (
        metrics.measured_total_seconds < request.plan.requested_duration_seconds
        or metrics.measured_post_warmup_seconds < request.plan.requested_duration_seconds
    ):
        return D1FailureCode.QUALITY_INSUFFICIENT
    if metrics.delivered_frames_per_second < 13.5 or (
        metrics.p95_inter_frame_gap_ms is not None and metrics.p95_inter_frame_gap_ms > 200
    ):
        return D1FailureCode.QUALITY_INSUFFICIENT
    if (
        metrics.p95_pose_latency_ms is None
        or metrics.p99_pose_latency_ms is None
        or metrics.p95_pose_latency_ms > 200
        or metrics.p99_pose_latency_ms > 500
    ):
        return D1FailureCode.QUALITY_INSUFFICIENT
    if metrics.backlog_ms is None or metrics.backlog_ms > 2000:
        return D1FailureCode.QUALITY_INSUFFICIENT
    if (
        accounting.processed / accounting.delivered_frames < 0.99
        or (accounting.dropped_explicit + accounting.failed) / accounting.delivered_frames > 0.01
    ):
        return D1FailureCode.QUALITY_INSUFFICIENT
    required = max(
        2 * 1024**3,
        int(2 * request.disk.encoded_byte_rate * request.plan.requested_duration_seconds),
    )
    if request.disk.free_bytes < required:
        return D1FailureCode.DISK_SPACE_INSUFFICIENT
    if metrics.p10_preflight_throughput_bytes_per_second is None or (
        metrics.p10_preflight_throughput_bytes_per_second < 2 * request.disk.encoded_byte_rate
    ):
        return D1FailureCode.DISK_THROUGHPUT_INSUFFICIENT
    return None


def _stage_failure(stages: EncoderDurabilityEvidence) -> D1FailureCode | None:
    if stages.encoder_open is StageState.FAILED:
        return D1FailureCode.ENCODER_UNAVAILABLE
    if stages.encoder_write is StageState.FAILED:
        return D1FailureCode.ENCODER_WRITE_FAILED
    if stages.encoder_finalize is StageState.FAILED:
        return D1FailureCode.ENCODER_FINALIZE_FAILED
    if stages.durability is StageState.FAILED:
        return D1FailureCode.DISK_FSYNC_FAILED
    return None


def _failure_receipt(
    request: ValidationInput,
    code: D1FailureCode,
    warmup: tuple[Observation, ...] = (),
    accounting: Accounting | None = None,
    metrics: MetricSummary | None = None,
    checked: int = 0,
    stops: int = 0,
    counts: tuple[tuple[str, int], ...] | None = None,
) -> D1Receipt:
    all_counts = _failure_counts(request, privacy_stop=stops > 0) if counts is None else counts
    if code.value not in dict(all_counts):
        all_counts = tuple(sorted((*all_counts, (code.value, 1))))
    if code is D1FailureCode.PRIVACY_STOP:
        empty = Accounting(0, 0, 0, 0, 0, 0, ())
        return _receipt(
            request,
            ValidationOutcome.NO_GO,
            code,
            all_counts,
            checked,
            stops,
            empty,
            empty,
            _empty_metrics(request),
            scrubbed=True,
        )
    return _receipt(
        request,
        ValidationOutcome.NO_GO,
        code,
        all_counts,
        checked,
        stops,
        _accounting(warmup),
        accounting or Accounting(0, 0, 0, 0, 0, 0, ()),
        metrics or _empty_metrics(request),
    )


def _receipt(
    request: ValidationInput,
    outcome: ValidationOutcome,
    code: D1FailureCode | None,
    counts: tuple[tuple[str, int], ...],
    checked: int,
    stops: int,
    warmup: Accounting,
    accounting: Accounting,
    metrics: MetricSummary,
    scrubbed: bool = False,
) -> D1Receipt:
    required = 0 if scrubbed else max(
        2 * 1024**3,
        int(2 * request.disk.encoded_byte_rate * request.plan.requested_duration_seconds),
    )
    stages = (
        EncoderDurabilityEvidence(
            StageState.NOT_ATTEMPTED,
            StageState.NOT_ATTEMPTED,
            StageState.NOT_ATTEMPTED,
            StageState.NOT_ATTEMPTED,
        )
        if scrubbed
        else request.disk.stages
    )
    base = D1Receipt(
        schema_version=1,
        outcome=outcome,
        device_gate_decision=DeviceGateDecision.UNVERIFIED,
        evidence_kind=EvidenceKind.SIMULATED,
        failure_code=code,
        failure_counts=counts,
        run_kind=request.plan.run_kind,
        width=request.plan.width,
        height=request.plan.height,
        frames_per_second=request.plan.frames_per_second,
        requested_duration_seconds=request.plan.requested_duration_seconds,
        warmup_seconds=request.plan.warmup_seconds,
        privacy_checked_frames=checked,
        privacy_stop_count=stops,
        warmup_accounting=warmup,
        accounting=accounting,
        metrics=metrics,
        required_bytes=required,
        free_bytes=0 if scrubbed else request.disk.free_bytes,
        encoded_byte_count=0 if scrubbed else request.disk.encoded_byte_count,
        encoded_byte_rate=0.0 if scrubbed else request.disk.encoded_byte_rate,
        throughput_sample_count=0 if scrubbed else len(request.disk.throughput_samples),
        throughput_digest=(
            _digest([])
            if scrubbed
            else _digest(_throughput_payload(request.disk.throughput_samples))
        ),
        stages=stages,
        seal_attempted=False,
        export_attempted=False,
        authority_digest=_digest(_authority_payload(request.authority)),
        input_digest=(
            _privacy_stop_digest(checked)
            if scrubbed
            else canonical_input_digest(request.plan, request.observations, request.disk)
        ),
        provenance_digest=(
            _privacy_stop_digest(checked)
            if scrubbed
            else _digest(_provenance_payload(request.provenance))
        ),
        environment_digest=_digest(_environment_payload(request.environment)),
        reproduction_digest=(
            _privacy_stop_digest(checked)
            if scrubbed
            else _digest(_reproduction_payload(request.reproduction))
        ),
        evaluation_core_digest=(
            _privacy_stop_digest(checked)
            if scrubbed
            else canonical_evaluation_digest(request)
        ),
        result_digest="",
    )
    return replace(base, result_digest=base.recompute_digest())


def _empty_metrics(request: ValidationInput) -> MetricSummary:
    return MetricSummary(
        0, request.plan.run_end_monotonic_ns, 0.0, 0.0, 0.0, None, None, None, None, None
    )


def _privacy_stop_digest(checked: int) -> str:
    return _digest(
        {
            "receipt_scope": "PRIVACY_STOP_MINIMAL_V1",
            "privacy_checked_frames": checked,
            "privacy_stop_count": 1,
        }
    )


def _input_core_payload(
    plan: RunPlan, observations: tuple[Observation, ...], disk: DiskEvidence
) -> dict[str, object]:
    return {
        "plan": {
            "run_kind": plan.run_kind.value if isinstance(plan.run_kind, RunKind) else None,
            "width": plan.width,
            "height": plan.height,
            "frames_per_second": plan.frames_per_second,
            "requested_duration_seconds": plan.requested_duration_seconds,
            "warmup_seconds": plan.warmup_seconds,
            "run_end_monotonic_ns": plan.run_end_monotonic_ns,
        },
        "observations": [
            {
                "source_kind": item.source_kind.value
                if isinstance(item.source_kind, InputKind)
                else None,
                "captured_monotonic_ns": item.captured_monotonic_ns,
                "processed_monotonic_ns": item.processed_monotonic_ns,
                "disposition": item.disposition.value
                if isinstance(item.disposition, FrameDisposition)
                else None,
                "quality_insufficient": item.quality_insufficient,
                "failure_code": item.failure_code.value
                if isinstance(item.failure_code, D1FailureCode)
                else None,
                "drop_reason": item.drop_reason.value
                if isinstance(item.drop_reason, DropReason)
                else None,
            }
            for item in observations
        ],
        "disk": {
            "free_bytes": disk.free_bytes,
            "encoded_byte_count": disk.encoded_byte_count,
            "encoded_byte_rate": disk.encoded_byte_rate,
            "throughput_samples": _throughput_payload(disk.throughput_samples),
            "stages": _stage_payload(disk.stages),
        },
    }


def _accounting_payload(value: Accounting) -> dict[str, object]:
    return {
        "delivered_frames": value.delivered_frames,
        "inter_frame_gaps": value.inter_frame_gaps,
        "processed": value.processed,
        "dropped_explicit": value.dropped_explicit,
        "failed": value.failed,
        "quality_insufficient": value.quality_insufficient,
        "drop_reasons": [list(item) for item in value.drop_reasons],
    }


def _metrics_payload(value: MetricSummary) -> dict[str, float | int | None]:
    return {
        "first_capture_monotonic_ns": value.first_capture_monotonic_ns,
        "run_end_monotonic_ns": value.run_end_monotonic_ns,
        "measured_total_seconds": value.measured_total_seconds,
        "measured_post_warmup_seconds": value.measured_post_warmup_seconds,
        "delivered_frames_per_second": value.delivered_frames_per_second,
        "p95_inter_frame_gap_ms": value.p95_inter_frame_gap_ms,
        "p95_pose_latency_ms": value.p95_pose_latency_ms,
        "p99_pose_latency_ms": value.p99_pose_latency_ms,
        "p10_preflight_throughput_bytes_per_second": (
            value.p10_preflight_throughput_bytes_per_second
        ),
        "backlog_ms": value.backlog_ms,
    }


def _stage_payload(value: EncoderDurabilityEvidence) -> dict[str, str | None]:
    return {
        name: getattr(value, name).value if isinstance(getattr(value, name), StageState) else None
        for name in ("encoder_open", "encoder_write", "encoder_finalize", "durability")
    }


def _throughput_payload(values: tuple[ThroughputSample, ...]) -> list[list[float | int]]:
    return [[item.second_index, item.bytes_per_second] for item in values]


def _authority_payload(value: AuthorityReceipt) -> dict[str, object]:
    return {name: getattr(value, name) for name in AuthorityReceipt.__dataclass_fields__}


def _provenance_payload(value: InputProvenanceReceipt) -> dict[str, object]:
    return {
        name: (
            getattr(value, name).value
            if isinstance(getattr(value, name), InputKind)
            else list(getattr(value, name))
            if isinstance(getattr(value, name), tuple)
            else getattr(value, name)
        )
        for name in InputProvenanceReceipt.__dataclass_fields__
    }


def _environment_payload(value: EnvironmentReceipt) -> dict[str, object]:
    return {name: getattr(value, name) for name in EnvironmentReceipt.__dataclass_fields__}


def _reproduction_payload(value: ReproductionReceipt) -> dict[str, object]:
    return {
        name: list(getattr(value, name))
        if isinstance(getattr(value, name), tuple)
        else getattr(value, name)
        for name in ReproductionReceipt.__dataclass_fields__
    }


def _accounting_is_semantic(value: Accounting) -> bool:
    if not isinstance(value, Accounting):
        return False
    numeric = (
        value.delivered_frames,
        value.inter_frame_gaps,
        value.processed,
        value.dropped_explicit,
        value.failed,
        value.quality_insufficient,
    )
    return (
        all(isinstance(item, int) and item >= 0 for item in numeric)
        and value.inter_frame_gaps == max(value.delivered_frames - 1, 0)
        and value.processed + value.dropped_explicit + value.failed == value.delivered_frames
        and value.quality_insufficient <= value.processed
        and value.drop_reasons == tuple(sorted(value.drop_reasons))
        and all(
            isinstance(name, str)
            and name in {reason.value for reason in DropReason}
            and isinstance(count, int)
            and count > 0
            for name, count in value.drop_reasons
        )
        and sum(count for _, count in value.drop_reasons) == value.dropped_explicit
    )


def _count_is_valid(item: tuple[str, int]) -> bool:
    return (
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], str)
        and isinstance(item[1], int)
        and item[1] > 0
    )


def _failure_counts_are_semantic(values: tuple[tuple[str, int], ...]) -> bool:
    return (
        isinstance(values, tuple)
        and values == tuple(sorted(values))
        and len({name for name, _ in values}) == len(values)
        and all(
            _count_is_valid(item) and item[0] in {code.value for code in D1FailureCode}
            for item in values
        )
    )


def _metrics_are_semantic(metrics: MetricSummary, receipt: D1Receipt) -> bool:
    if not isinstance(metrics, MetricSummary):
        return False
    values = (
        metrics.measured_total_seconds,
        metrics.measured_post_warmup_seconds,
        metrics.delivered_frames_per_second,
        metrics.p95_inter_frame_gap_ms,
        metrics.p95_pose_latency_ms,
        metrics.p99_pose_latency_ms,
        metrics.p10_preflight_throughput_bytes_per_second,
        metrics.backlog_ms,
    )
    if any(value is None for value in values):
        return False
    if not all(
        isinstance(value, int | float) and math.isfinite(value) and value >= 0 for value in values
    ):
        return False
    assert metrics.p95_inter_frame_gap_ms is not None
    assert metrics.p95_pose_latency_ms is not None
    assert metrics.p99_pose_latency_ms is not None
    assert metrics.p10_preflight_throughput_bytes_per_second is not None
    assert metrics.backlog_ms is not None
    if (
        metrics.first_capture_monotonic_ns < 0
        or metrics.run_end_monotonic_ns < metrics.first_capture_monotonic_ns
    ):
        return False
    expected_total = (
        metrics.run_end_monotonic_ns - metrics.first_capture_monotonic_ns
    ) / 1_000_000_000
    if not math.isclose(metrics.measured_total_seconds, expected_total, abs_tol=0.001):
        return False
    if not math.isclose(
        metrics.measured_total_seconds - metrics.measured_post_warmup_seconds,
        receipt.warmup_seconds,
        abs_tol=0.001,
    ):
        return False
    if metrics.measured_total_seconds < receipt.requested_duration_seconds:
        return False
    if metrics.measured_post_warmup_seconds < receipt.requested_duration_seconds:
        return False
    expected_fps = receipt.accounting.delivered_frames / metrics.measured_post_warmup_seconds
    if not math.isclose(metrics.delivered_frames_per_second, expected_fps, abs_tol=0.000001):
        return False
    if metrics.delivered_frames_per_second < 13.5 or metrics.p95_inter_frame_gap_ms > 200:
        return False
    if metrics.p95_pose_latency_ms > 200 or metrics.p99_pose_latency_ms > 500:
        return False
    if metrics.backlog_ms > 2000:
        return False
    if metrics.p10_preflight_throughput_bytes_per_second < 2 * receipt.encoded_byte_rate:
        return False
    if receipt.accounting.delivered_frames == 0:
        return False
    if receipt.accounting.processed / receipt.accounting.delivered_frames < 0.99:
        return False
    return (
        receipt.accounting.dropped_explicit + receipt.accounting.failed
    ) / receipt.accounting.delivered_frames <= 0.01


def _stages_succeeded(value: EncoderDurabilityEvidence) -> bool:
    return isinstance(value, EncoderDurabilityEvidence) and all(
        getattr(value, name) is StageState.SUCCEEDED
        for name in ("encoder_open", "encoder_write", "encoder_finalize", "durability")
    )


def _tokens_are_valid(values: tuple[str, ...]) -> bool:
    return (
        isinstance(values, tuple)
        and bool(values)
        and len(set(values)) == len(values)
        and all(_is_token(value) for value in values)
    )


def _is_digest(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_token(value: str) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and value[0].isalnum()
        and all(character.isalnum() or character in "._-" for character in value)
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
