from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from pdu_exam_observer.m2_d1_contract import (
    CANONICAL_PROPOSAL_SHA256,
    DEPENDENCY_ARTIFACT_NAME,
    DEPENDENCY_ARTIFACT_SHA256,
    REPRODUCTION_INVOCATION,
    Accounting,
    AuthorityReceipt,
    D1FailureCode,
    DeviceGateDecision,
    DiskEvidence,
    DropReason,
    EncoderDurabilityEvidence,
    EnvironmentReceipt,
    EvidenceKind,
    FrameDisposition,
    InputKind,
    InputProvenanceReceipt,
    Observation,
    PrivacyDecision,
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
    nearest_rank,
    verify_receipt_semantics,
)


class Lease:
    def __init__(self, available: bool = True, broken_release: bool = False) -> None:
        self.available = available
        self.broken_release = broken_release
        self.acquired = 0
        self.released = 0

    def acquire(self) -> bool:
        self.acquired += 1
        return self.available

    def release(self) -> None:
        self.released += 1
        if self.broken_release:
            raise RuntimeError("release")


class Privacy:
    def __init__(self, decisions: tuple[PrivacyDecision, ...] = ()) -> None:
        self.decisions = decisions
        self.calls = 0

    def inspect(self, observation: Observation) -> PrivacyDecision:
        del observation
        result = (
            self.decisions[self.calls]
            if self.calls < len(self.decisions)
            else PrivacyDecision.CLEAR
        )
        self.calls += 1
        return result


ORIGIN_NS = 900_000_000_000
INTERVAL_NS = 1_000_000_000 // 15


def _observations() -> tuple[Observation, ...]:
    return tuple(
        Observation(
            source_kind=InputKind.TEST_CHART,
            captured_monotonic_ns=ORIGIN_NS + index * INTERVAL_NS,
            processed_monotonic_ns=ORIGIN_NS + index * INTERVAL_NS + 10_000_000,
            disposition=FrameDisposition.PROCESSED,
            quality_insufficient=False,
            failure_code=None,
            drop_reason=None,
        )
        for index in range(18_077)
    )


def _plan(observations: tuple[Observation, ...]) -> RunPlan:
    return RunPlan(
        run_kind=RunKind.NOMINAL_20M,
        width=1280,
        height=720,
        frames_per_second=15,
        requested_duration_seconds=1200,
        warmup_seconds=5,
        run_end_monotonic_ns=observations[-1].captured_monotonic_ns + 10_000_000,
    )


def _disk(plan: RunPlan) -> DiskEvidence:
    elapsed_ns = plan.run_end_monotonic_ns - ORIGIN_NS
    return DiskEvidence(
        free_bytes=3 * 1024**3,
        encoded_byte_count=int(elapsed_ns / 1_000),
        encoded_byte_rate=1_000_000.0,
        throughput_samples=tuple(ThroughputSample(index, 3_000_000.0) for index in range(60)),
        stages=EncoderDurabilityEvidence(
            encoder_open=StageState.SUCCEEDED,
            encoder_write=StageState.SUCCEEDED,
            encoder_finalize=StageState.SUCCEEDED,
            durability=StageState.SUCCEEDED,
        ),
    )


def _request(
    *,
    observations: tuple[Observation, ...] | None = None,
    disk: DiskEvidence | None = None,
    faults: tuple[D1FailureCode, ...] = (),
    plan: RunPlan | None = None,
) -> ValidationInput:
    observations = _observations() if observations is None else observations
    plan = _plan(observations) if plan is None else plan
    disk = _disk(plan) if disk is None else disk
    provenance = InputProvenanceReceipt(
        schema_version=1,
        source_kind=InputKind.TEST_CHART,
        source_version="chart-v1",
        generator_id="d1-fixture-generator-v1",
        canonical_input_digest=canonical_input_digest(plan, observations, disk),
        frame_count=len(observations),
        simulated_no_human=True,
        dataset_use_prohibited=True,
        leakage_statement="N/A",
        deterministic_seed="N/A",
        baseline_id="d1-baseline-v1",
        mutant_ids=("mutant-ledger-v1",),
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
        application_revision_digest="a" * 64,
        release_manifest_digest="b" * 64,
        pose_engine_digest="c" * 64,
        encoder_digest="d" * 64,
        operating_system="SIMULATED-N/A",
        locale="N/A",
        timezone="N/A",
        offline=True,
        injected_only=True,
        camera_not_accessed=True,
        driver_unverified=True,
        audio_prohibited=True,
    )
    draft = ValidationInput(
        schema_version=1,
        evidence_kind=EvidenceKind.SIMULATED,
        input_kind=InputKind.TEST_CHART,
        plan=plan,
        observations=observations,
        disk=disk,
        injected_failures=faults,
        authority=authority,
        provenance=provenance,
        environment=environment,
        reproduction=ReproductionReceipt(
            schema_version=1,
            receipt_kind="D1_C1_REPRODUCTION",
            noninteractive_invocation=REPRODUCTION_INVOCATION,
            dependency_artifact=DEPENDENCY_ARTIFACT_NAME,
            lock_digest=DEPENDENCY_ARTIFACT_SHA256,
            source_digest=provenance.canonical_input_digest,
            deterministic_seed="N/A",
            threshold_version="d1-thresholds-v1",
            baseline_id="d1-baseline-v1",
            mutant_ids=("mutant-ledger-v1",),
            uncertainty_statement="SIMULATED_EVALUATOR_ONLY",
            input_digest=provenance.canonical_input_digest,
            expected_evaluation_digest="0" * 64,
        ),
    )
    return replace(
        draft,
        reproduction=replace(
            draft.reproduction, expected_evaluation_digest=canonical_evaluation_digest(draft)
        ),
    )


def test_simulated_pass_receipt_semantics_reject_relabel_and_recompute() -> None:
    receipt = evaluate(_request(), privacy_guard=Privacy(), owner_lease=Lease())
    assert receipt.outcome is ValidationOutcome.BACKEND_CONTRACT_PASS
    assert receipt.evidence_kind is EvidenceKind.SIMULATED
    assert receipt.device_gate_decision is DeviceGateDecision.UNVERIFIED
    assert receipt.seal_attempted is False and receipt.export_attempted is False
    assert verify_receipt_semantics(receipt)
    forged = replace(receipt, evidence_kind="FORGED")  # type: ignore[arg-type]
    assert not verify_receipt_semantics(replace(forged, result_digest=forged.recompute_digest()))


def test_exact_plan_nonzero_origin_zero_encoder_and_stage_failures() -> None:
    request = _request()
    receipt = evaluate(request, privacy_guard=Privacy(), owner_lease=Lease())
    assert receipt.metrics.first_capture_monotonic_ns == ORIGIN_NS
    assert receipt.metrics.measured_total_seconds >= 1200
    for plan in (
        replace(request.plan, requested_duration_seconds=1201),
        replace(request.plan, warmup_seconds=4),
        replace(request.plan, width=1279),
        replace(request.plan, height=721),
        replace(request.plan, frames_per_second=14),
    ):
        with pytest.raises(ValueError, match="plan"):
            evaluate(replace(request, plan=plan), privacy_guard=Privacy(), owner_lease=Lease())
    zero = replace(request.disk, encoded_byte_count=0, encoded_byte_rate=0.0)
    assert (
        evaluate(_request(disk=zero), privacy_guard=Privacy(), owner_lease=Lease()).failure_code
        is D1FailureCode.ENCODER_WRITE_FAILED
    )
    unfinished = replace(
        request.disk, stages=replace(request.disk.stages, durability=StageState.FAILED)
    )
    assert (
        evaluate(
            _request(disk=unfinished), privacy_guard=Privacy(), owner_lease=Lease()
        ).failure_code
        is D1FailureCode.DISK_FSYNC_FAILED
    )


def test_time_quality_privacy_and_drop_mutants_fail_closed() -> None:
    request = _request()
    observations = list(request.observations)
    observations[100] = replace(
        observations[100], captured_monotonic_ns=observations[99].captured_monotonic_ns
    )
    assert (
        evaluate(
            _request(observations=tuple(observations)), privacy_guard=Privacy(), owner_lease=Lease()
        ).failure_code
        is D1FailureCode.FRAME_STALLED
    )
    observations = list(request.observations)
    observations[100] = replace(
        observations[100], captured_monotonic_ns=observations[99].captured_monotonic_ns - 1
    )
    assert (
        evaluate(
            _request(observations=tuple(observations)), privacy_guard=Privacy(), owner_lease=Lease()
        ).failure_code
        is D1FailureCode.CLOCK_REGRESSION
    )
    observations = list(request.observations)
    observations[99] = replace(
        observations[99],
        processed_monotonic_ns=observations[100].processed_monotonic_ns + 1,
    )
    assert (
        evaluate(
            _request(observations=tuple(observations)), privacy_guard=Privacy(), owner_lease=Lease()
        ).failure_code
        is D1FailureCode.CLOCK_REGRESSION
    )
    observations = list(request.observations)
    observations[-1] = replace(observations[-1], quality_insufficient=True)
    assert (
        evaluate(
            _request(observations=tuple(observations)), privacy_guard=Privacy(), owner_lease=Lease()
        ).failure_code
        is D1FailureCode.QUALITY_INSUFFICIENT
    )
    stopped = evaluate(
        request,
        privacy_guard=Privacy((PrivacyDecision.CLEAR, PrivacyDecision.UNKNOWN)),
        owner_lease=Lease(),
    )
    assert stopped.failure_code is D1FailureCode.PRIVACY_STOP
    assert stopped.privacy_checked_frames == 2 and stopped.privacy_stop_count == 1


def test_60_ordered_throughput_input_and_receipt_binding_are_required() -> None:
    request = _request()
    assert nearest_rank((90.0,) + (300.0,) * 9, 10) == 90.0
    short = replace(request.disk, throughput_samples=request.disk.throughput_samples[:-1])
    with pytest.raises(ValueError, match="disk"):
        evaluate(_request(disk=short), privacy_guard=Privacy(), owner_lease=Lease())
    low = replace(
        request.disk,
        throughput_samples=tuple(ThroughputSample(index, 1_999_999.0) for index in range(6))
        + request.disk.throughput_samples[6:],
    )
    assert (
        evaluate(_request(disk=low), privacy_guard=Privacy(), owner_lease=Lease()).failure_code
        is D1FailureCode.DISK_THROUGHPUT_INSUFFICIENT
    )
    for changed in (
        replace(request.authority, decision_date="2026-08-27"),
        replace(request.provenance, frame_count=1),
        replace(request.reproduction, input_digest="0" * 64),
        replace(request.reproduction, expected_evaluation_digest="0" * 64),
    ):
        field = (
            "authority"
            if isinstance(changed, AuthorityReceipt)
            else "provenance"
            if isinstance(changed, InputProvenanceReceipt)
            else "reproduction"
        )
        with pytest.raises(ValueError):
            evaluate(
                replace(request, **{field: changed}), privacy_guard=Privacy(), owner_lease=Lease()
            )


@pytest.mark.parametrize("fault", tuple(D1FailureCode))
def test_every_direct_failure_is_terminal_and_counted(fault: D1FailureCode) -> None:
    receipt = evaluate(
        _request(observations=_observations()[:2], faults=(fault,)),
        privacy_guard=Privacy(),
        owner_lease=Lease(),
    )
    assert receipt.outcome is ValidationOutcome.NO_GO
    assert receipt.failure_code is fault and receipt.failure_counts == ((fault.value, 1),)


def test_owner_release_and_ast_boundary_are_strict() -> None:
    request = _request()
    assert (
        evaluate(request, privacy_guard=Privacy(), owner_lease=Lease(available=False)).failure_code
        is D1FailureCode.SCHEMA_INCOMPATIBLE
    )
    lease = Lease(broken_release=True)
    assert (
        evaluate(request, privacy_guard=Privacy(), owner_lease=lease).failure_code
        is D1FailureCode.SCHEMA_INCOMPATIBLE
    )
    assert lease.released == 1
    text = (
        Path(__file__).parents[2] / "src" / "pdu_exam_observer" / "m2_d1_contract.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(text)
    forbidden = {
        "cv2",
        "mediapipe",
        "audio",
        "sounddevice",
        "pyaudio",
        "os",
        "pathlib",
        "sqlite3",
        "fastapi",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "m1",
        "m2_persistence",
    }
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imports.isdisjoint(forbidden)
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "open",
        "importlib.import_module",
    }

    def call_names(candidate: ast.AST) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(candidate):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
            ):
                names.add(f"{node.func.value.id}.{node.func.attr}")
        return names

    assert call_names(tree).isdisjoint(forbidden_calls)
    mutant_calls = call_names(
        ast.parse("__import__('x'); importlib.import_module('x'); open('x'); exec('x')")
    )
    assert forbidden_calls.intersection(mutant_calls) == mutant_calls
    assert "NATIVE" not in text and "D1_GO" not in text and "REAL" not in text
    forbidden_fields = {
        "path",
        "url",
        "browser",
        "device_id",
        "participant_id",
        "session_id",
        "label",
        "confidence",
        "metadata",
        "alert",
    }
    for contract in (
        ValidationInput,
        Observation,
        InputProvenanceReceipt,
        EnvironmentReceipt,
        ReproductionReceipt,
    ):
        assert forbidden_fields.isdisjoint(contract.__dataclass_fields__)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda receipt: replace(receipt, privacy_checked_frames=0),
        lambda receipt: replace(
            receipt,
            metrics=replace(receipt.metrics, delivered_frames_per_second=13.4),
        ),
        lambda receipt: replace(
            receipt,
            metrics=replace(receipt.metrics, p99_pose_latency_ms=500.1),
        ),
        lambda receipt: replace(receipt, free_bytes=receipt.required_bytes - 1),
        lambda receipt: replace(
            receipt,
            accounting=replace(
                receipt.accounting,
                delivered_frames=0,
                processed=0,
                dropped_explicit=0,
                failed=0,
                inter_frame_gaps=0,
                quality_insufficient=-1,
            ),
        ),
        lambda receipt: replace(
            receipt,
            metrics=replace(
                receipt.metrics,
                measured_post_warmup_seconds=receipt.metrics.measured_total_seconds + 1,
            ),
        ),
    ),
)
def test_semantic_rehash_mutants_cannot_reclaim_contract_pass(mutate: object) -> None:
    receipt = evaluate(_request(), privacy_guard=Privacy(), owner_lease=Lease())
    forged = mutate(receipt)  # type: ignore[operator]
    assert not verify_receipt_semantics(replace(forged, result_digest=forged.recompute_digest()))


def test_privacy_stop_hides_later_evidence_and_uses_zero_processing_accounting() -> None:
    observations = list(_observations())
    observations[100] = replace(
        observations[100],
        disposition=FrameDisposition.FAILED,
        processed_monotonic_ns=None,
        failure_code=D1FailureCode.ENCODER_WRITE_FAILED,
    )
    receipt = evaluate(
        _request(observations=tuple(observations), faults=(D1FailureCode.DISK_FSYNC_FAILED,)),
        privacy_guard=Privacy((PrivacyDecision.CLEAR, PrivacyDecision.UNSAFE)),
        owner_lease=Lease(),
    )
    assert receipt.failure_code is D1FailureCode.PRIVACY_STOP
    assert receipt.failure_counts == ((D1FailureCode.PRIVACY_STOP.value, 1),)
    assert receipt.accounting == Accounting(0, 0, 0, 0, 0, 0, ())
    assert receipt.free_bytes == 0 and receipt.required_bytes == 0
    assert receipt.encoded_byte_count == 0 and receipt.encoded_byte_rate == 0
    assert receipt.throughput_sample_count == 0
    assert all(
        state is StageState.NOT_ATTEMPTED
        for state in (
            receipt.stages.encoder_open,
            receipt.stages.encoder_write,
            receipt.stages.encoder_finalize,
            receipt.stages.durability,
        )
    )
    assert verify_receipt_semantics(receipt)
    forged = replace(receipt, free_bytes=1)
    assert not verify_receipt_semantics(replace(forged, result_digest=forged.recompute_digest()))
    unmodified = evaluate(
        _request(),
        privacy_guard=Privacy((PrivacyDecision.CLEAR, PrivacyDecision.UNSAFE)),
        owner_lease=Lease(),
    )
    assert (
        receipt.input_digest,
        receipt.provenance_digest,
        receipt.reproduction_digest,
        receipt.evaluation_core_digest,
    ) == (
        unmodified.input_digest,
        unmodified.provenance_digest,
        unmodified.reproduction_digest,
        unmodified.evaluation_core_digest,
    )


@pytest.mark.parametrize(
    "disposition",
    (
        FrameDisposition.PROCESSED,
        FrameDisposition.DROPPED_EXPLICIT,
        FrameDisposition.FAILED,
    ),
)
def test_all_observation_kinds_reject_capture_after_declared_run_end(
    disposition: FrameDisposition,
) -> None:
    request = _request()
    observations = list(request.observations)
    observations[-1] = replace(
        observations[-1],
        captured_monotonic_ns=request.plan.run_end_monotonic_ns + 1,
        disposition=disposition,
        processed_monotonic_ns=request.plan.run_end_monotonic_ns + 2
        if disposition is FrameDisposition.PROCESSED
        else None,
        failure_code=D1FailureCode.INPUT_MALFORMED
        if disposition is FrameDisposition.FAILED
        else None,
        drop_reason=None,
    )
    assert (
        evaluate(
            _request(observations=tuple(observations), plan=request.plan),
            privacy_guard=Privacy(),
            owner_lease=Lease(),
        ).failure_code
        is D1FailureCode.SCHEMA_INCOMPATIBLE
    )


def test_receipt_identifiers_are_revision_scoped_allowlists() -> None:
    request = _request()
    mutations = (
        replace(request.provenance, source_version="chart-v999"),
        replace(request.provenance, generator_id="d1-fixture-generator-v999"),
        replace(request.provenance, baseline_id="d1-baseline-v999"),
        replace(request.provenance, mutant_ids=("mutant-ledger-v999",)),
        replace(request.reproduction, lock_digest="1" * 64),
        replace(request.reproduction, source_digest="2" * 64),
    )
    for changed in mutations:
        field = "provenance" if isinstance(changed, InputProvenanceReceipt) else "reproduction"
        with pytest.raises(ValueError):
            evaluate(
                replace(request, **{field: changed}), privacy_guard=Privacy(), owner_lease=Lease()
            )


def test_preflight_run_kind_has_its_own_exact_duration_contract() -> None:
    observations = _observations()[:977]
    plan = RunPlan(
        run_kind=RunKind.PREFLIGHT_60S,
        width=1280,
        height=720,
        frames_per_second=15,
        requested_duration_seconds=60,
        warmup_seconds=5,
        run_end_monotonic_ns=observations[-1].captured_monotonic_ns + 10_000_000,
    )
    receipt = evaluate(
        _request(observations=observations, plan=plan), privacy_guard=Privacy(), owner_lease=Lease()
    )
    assert receipt.outcome is ValidationOutcome.BACKEND_CONTRACT_PASS
    with pytest.raises(ValueError, match="plan"):
        evaluate(
            _request(
                observations=observations, plan=replace(plan, requested_duration_seconds=1200)
            ),
            privacy_guard=Privacy(),
            owner_lease=Lease(),
        )


def test_quality_failures_are_counted_without_a_synthetic_extra() -> None:
    observations = list(_observations())
    for index in (100, 200, 300):
        observations[index] = replace(observations[index], quality_insufficient=True)
    receipt = evaluate(
        _request(observations=tuple(observations)), privacy_guard=Privacy(), owner_lease=Lease()
    )
    assert receipt.failure_code is D1FailureCode.QUALITY_INSUFFICIENT
    assert receipt.accounting.quality_insufficient == 3
    assert receipt.failure_counts == ((D1FailureCode.QUALITY_INSUFFICIENT.value, 3),)


def test_reproduction_requires_artifact_hash_and_provenance_alignment() -> None:
    request = _request()
    for changed in (
        replace(request.reproduction, dependency_artifact="pyproject.toml"),
        replace(request.reproduction, lock_digest="1" * 64),
        replace(request.reproduction, source_digest="2" * 64),
        replace(request.reproduction, baseline_id="d1-baseline-v999"),
        replace(request.reproduction, mutant_ids=("mutant-ledger-v999",)),
    ):
        with pytest.raises(ValueError):
            evaluate(
                replace(request, reproduction=changed), privacy_guard=Privacy(), owner_lease=Lease()
            )


def test_explicit_drop_reason_is_accounted_and_over_budget_fails_quality() -> None:
    request = _request()
    observations = list(request.observations)
    observations[-1] = replace(
        observations[-1],
        processed_monotonic_ns=None,
        disposition=FrameDisposition.DROPPED_EXPLICIT,
        drop_reason=DropReason.BACKPRESSURE,
    )
    passed = evaluate(
        _request(observations=tuple(observations)), privacy_guard=Privacy(), owner_lease=Lease()
    )
    assert passed.outcome is ValidationOutcome.BACKEND_CONTRACT_PASS
    assert passed.accounting.drop_reasons == ((DropReason.BACKPRESSURE.value, 1),)
    malformed = list(observations)
    malformed[-1] = replace(malformed[-1], drop_reason=None)
    assert (
        evaluate(
            _request(observations=tuple(malformed)), privacy_guard=Privacy(), owner_lease=Lease()
        ).failure_code
        is D1FailureCode.SCHEMA_INCOMPATIBLE
    )
    over_budget = list(request.observations)
    for index in range(1000, 1181):
        over_budget[index] = replace(
            over_budget[index],
            processed_monotonic_ns=None,
            disposition=FrameDisposition.DROPPED_EXPLICIT,
            drop_reason=DropReason.BACKPRESSURE,
        )
    assert (
        evaluate(
            _request(observations=tuple(over_budget)), privacy_guard=Privacy(), owner_lease=Lease()
        ).failure_code
        is D1FailureCode.QUALITY_INSUFFICIENT
    )


def test_privacy_variants_and_owner_acquire_exception_fail_closed() -> None:
    request = _request()
    for decision in (PrivacyDecision.UNSAFE, PrivacyDecision.UNKNOWN):
        assert (
            evaluate(
                request, privacy_guard=Privacy((decision,)), owner_lease=Lease()
            ).failure_code
            is D1FailureCode.PRIVACY_STOP
        )

    class BrokenPrivacy:
        def inspect(self, observation: Observation) -> PrivacyDecision:
            del observation
            raise RuntimeError("privacy")

    class BrokenAcquire:
        def acquire(self) -> bool:
            raise RuntimeError("owner")

        def release(self) -> None:
            return None

    assert (
        evaluate(request, privacy_guard=BrokenPrivacy(), owner_lease=Lease()).failure_code
        is D1FailureCode.PRIVACY_STOP
    )
    assert (
        evaluate(request, privacy_guard=Privacy(), owner_lease=BrokenAcquire()).failure_code
        is D1FailureCode.SCHEMA_INCOMPATIBLE
    )


@pytest.mark.parametrize(
    ("stage", "code"),
    (
        ("encoder_open", D1FailureCode.ENCODER_UNAVAILABLE),
        ("encoder_write", D1FailureCode.ENCODER_WRITE_FAILED),
        ("encoder_finalize", D1FailureCode.ENCODER_FINALIZE_FAILED),
        ("durability", D1FailureCode.DISK_FSYNC_FAILED),
    ),
)
def test_actual_stage_failures_map_to_their_failure_ledger_codes(
    stage: str, code: D1FailureCode
) -> None:
    request = _request()
    disk = replace(request.disk, stages=replace(request.disk.stages, **{stage: StageState.FAILED}))
    assert (
        evaluate(_request(disk=disk), privacy_guard=Privacy(), owner_lease=Lease()).failure_code
        is code
    )


def test_warmup_failure_quality_and_drop_evidence_are_retained_terminally() -> None:
    request = _request()
    failed = list(request.observations)
    failed[1] = replace(
        failed[1],
        processed_monotonic_ns=None,
        disposition=FrameDisposition.FAILED,
        failure_code=D1FailureCode.POSE_OUTPUT_INVALID,
    )
    failed_receipt = evaluate(
        _request(observations=tuple(failed)), privacy_guard=Privacy(), owner_lease=Lease()
    )
    assert failed_receipt.failure_code is D1FailureCode.POSE_OUTPUT_INVALID
    assert failed_receipt.warmup_accounting.failed == 1
    quality = list(request.observations)
    quality[1] = replace(quality[1], quality_insufficient=True)
    quality_receipt = evaluate(
        _request(observations=tuple(quality)), privacy_guard=Privacy(), owner_lease=Lease()
    )
    assert quality_receipt.failure_code is D1FailureCode.QUALITY_INSUFFICIENT
    assert quality_receipt.warmup_accounting.quality_insufficient == 1
    dropped = list(request.observations)
    dropped[1] = replace(
        dropped[1],
        processed_monotonic_ns=None,
        disposition=FrameDisposition.DROPPED_EXPLICIT,
        drop_reason=DropReason.BACKPRESSURE,
    )
    dropped_receipt = evaluate(
        _request(
            observations=tuple(dropped), faults=(D1FailureCode.UNKNOWN_TECHNICAL_FAILURE,)
        ),
        privacy_guard=Privacy(),
        owner_lease=Lease(),
    )
    assert dropped_receipt.failure_code is D1FailureCode.UNKNOWN_TECHNICAL_FAILURE
    assert dropped_receipt.warmup_accounting.drop_reasons == ((DropReason.BACKPRESSURE.value, 1),)


def test_metric_and_capacity_limits_are_evaluated_from_observations() -> None:
    request = _request()
    slower = tuple(
        replace(
            item,
            captured_monotonic_ns=ORIGIN_NS + index * 75_000_000,
            processed_monotonic_ns=ORIGIN_NS + index * 75_000_000 + 10_000_000,
        )
        for index, item in enumerate(request.observations)
    )
    slower_plan = _plan(slower)
    fps_receipt = evaluate(
        _request(observations=slower, plan=slower_plan),
        privacy_guard=Privacy(),
        owner_lease=Lease(),
    )
    assert fps_receipt.metrics.delivered_frames_per_second < 13.5
    assert fps_receipt.failure_code is D1FailureCode.QUALITY_INSUFFICIENT
    gapped = tuple(
        replace(
            item,
            captured_monotonic_ns=ORIGIN_NS + index * 201_000_000,
            processed_monotonic_ns=ORIGIN_NS + index * 201_000_000 + 10_000_000,
        )
        for index, item in enumerate(request.observations)
    )
    gapped_receipt = evaluate(
        _request(observations=gapped, plan=_plan(gapped)),
        privacy_guard=Privacy(),
        owner_lease=Lease(),
    )
    assert gapped_receipt.metrics.p95_inter_frame_gap_ms == 201.0
    assert gapped_receipt.failure_code is D1FailureCode.QUALITY_INSUFFICIENT
    stalled = list(request.observations)
    stalled[100] = replace(
        stalled[100], captured_monotonic_ns=stalled[99].captured_monotonic_ns + 1_000_000_000
    )
    assert (
        evaluate(
            _request(observations=tuple(stalled)),
            privacy_guard=Privacy(),
            owner_lease=Lease(),
        ).failure_code
        is D1FailureCode.FRAME_STALLED
    )
    delayed = tuple(
        replace(item, processed_monotonic_ns=item.captured_monotonic_ns + 501_000_000)
        for item in request.observations
    )
    delayed_plan = replace(
        _plan(delayed),
        run_end_monotonic_ns=delayed[-1].captured_monotonic_ns + 600_000_000,
    )
    delayed_receipt = evaluate(
        _request(observations=delayed, plan=delayed_plan),
        privacy_guard=Privacy(),
        owner_lease=Lease(),
    )
    assert delayed_receipt.metrics.p99_pose_latency_ms == 501.0
    assert delayed_receipt.failure_code is D1FailureCode.QUALITY_INSUFFICIENT
    backlogged = list(request.observations)
    for index in range(len(backlogged) - 31, len(backlogged)):
        backlogged[index] = replace(
            backlogged[index],
            processed_monotonic_ns=None,
            disposition=FrameDisposition.DROPPED_EXPLICIT,
            drop_reason=DropReason.BACKPRESSURE,
        )
    backlog_receipt = evaluate(
        _request(observations=tuple(backlogged)), privacy_guard=Privacy(), owner_lease=Lease()
    )
    assert backlog_receipt.metrics.backlog_ms > 2000
    assert backlog_receipt.failure_code is D1FailureCode.QUALITY_INSUFFICIENT
    assert (
        evaluate(
            _request(disk=replace(request.disk, free_bytes=0)),
            privacy_guard=Privacy(),
            owner_lease=Lease(),
        ).failure_code
        is D1FailureCode.DISK_SPACE_INSUFFICIENT
    )
    assert (
        evaluate(
            _request(
                disk=replace(
                    request.disk,
                    throughput_samples=tuple(
                        ThroughputSample(index, 1_999_999.0) for index in range(60)
                    ),
                )
            ),
            privacy_guard=Privacy(),
            owner_lease=Lease(),
        ).failure_code
        is D1FailureCode.DISK_THROUGHPUT_INSUFFICIENT
    )
