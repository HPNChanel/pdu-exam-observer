from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.m2_d1_contract import (
    D1FailureCode,
    PrivacyDecision,
    RunKind,
    ValidationOutcome,
)
from pdu_exam_observer.m2_persistence import M2PersistenceStore
from pdu_exam_observer.m2_synthetic import (
    FixtureDefinition,
    FixtureInput,
    PoseResult,
    ProcessingState,
    QualityState,
    SyntheticRunner,
    TechnicalFailureCode,
    TechnicalInputKind,
    TechnicalObservation,
    fixture_input_digest,
)
from pdu_exam_observer.m2_synthetic_integration import (
    IntegrationFailureCode,
    IntegrationStatus,
    M2SyntheticNominalCore,
    M2SyntheticPreflightCore,
    SyntheticEnvironmentBindings,
    SyntheticNominalRequest,
    SyntheticPreflightRequest,
)
from pdu_exam_observer.m2_synthetic_nominal_fixture import (
    BUILTIN_RUN_ID,
    FRAME_COUNT,
    INTERVAL_NS,
    ORIGIN_NS,
    PROCESSING_LATENCY_NS,
    build_builtin_nominal_bundle,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import (
    BUILTIN_RUN_ID as PREFLIGHT_RUN_ID,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import (
    build_builtin_preflight_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
ENGINE_HASH = "c" * 64


class Lease:
    def acquire(self) -> bool:
        return True

    def release(self) -> None:
        return None


class Privacy:
    def __init__(self, decision: PrivacyDecision = PrivacyDecision.CLEAR) -> None:
        self.decision = decision

    def inspect(self, _observation: object) -> PrivacyDecision:
        return self.decision


class IdentityProvider:
    def provide(self, fixture: FixtureInput) -> FixtureInput:
        return fixture


class ZeroPoseProvider:
    def infer(self, _fixture: FixtureInput) -> PoseResult:
        return PoseResult(
            landmark_topology_version="mediapipe-33-v1",
            landmarks=(),
            landmark_missing_mask=((True,) * 33, (True,) * 33),
            ordered_landmark_indices=(),
            quality_state=QualityState.VALID,
            reported_pose_count=0,
        )


class SequenceClock:
    def __init__(self, values: tuple[int, ...]) -> None:
        self.values = iter(values)

    def now_ns(self) -> int:
        return next(self.values)


class Sink:
    def observe(self, _observation: TechnicalObservation) -> None:
        return None


class FixedObservationRunner:
    def __init__(self, failure: TechnicalFailureCode) -> None:
        self.failure = failure

    def process(self, fixture: FixtureInput) -> TechnicalObservation:
        quality_failure = self.failure is TechnicalFailureCode.QUALITY_INSUFFICIENT
        value = TechnicalObservation(
            schema_version=1,
            technical_input_kind=fixture.technical_input_kind,
            fixture_id=fixture.fixture_id,
            fixture_version=fixture.fixture_version,
            run_id=fixture.run_id,
            frame_seq=fixture.frame_seq,
            captured_monotonic_ns=ORIGIN_NS,
            processed_monotonic_ns=(
                ORIGIN_NS + PROCESSING_LATENCY_NS if quality_failure else None
            ),
            pose_engine_task_hash=ENGINE_HASH,
            preprocessing_id=fixture.preprocessing_id,
            landmark_topology_version="mediapipe-33-v1",
            landmarks=(),
            landmark_missing_mask=((True,) * 33, (True,) * 33),
            pose_count=0 if quality_failure else None,
            quality_state=(QualityState.INSUFFICIENT if quality_failure else QualityState.FAILED),
            processing_state=(
                ProcessingState.PROCESSED if quality_failure else ProcessingState.FAILED
            ),
            failure_code=self.failure,
            latency_ms=10 if quality_failure else None,
            fixture_input_hash=fixture_input_digest(fixture),
            golden_expected_output_digest="0" * 64,
            result_digest="",
        )
        return value.with_result_digest(value.recompute_result_digest())

    def expected_output_digest(self, _fixture: FixtureInput) -> str:
        return "0" * 64


class MutatingNominalRunner:
    def __init__(self, mode: str) -> None:
        bundle = build_builtin_nominal_bundle(ENGINE_HASH)
        self.runner = bundle.runner
        self.fixtures = bundle.fixtures
        self.mode = mode
        self.expected: dict[tuple[str, str], str] = {}

    def process(self, fixture: FixtureInput) -> TechnicalObservation:
        original = self.runner.process(fixture)
        value = original
        if self.mode == "coverage" and 76 <= fixture.frame_seq < 276:
            value = replace(
                original,
                processed_monotonic_ns=None,
                pose_count=None,
                quality_state=QualityState.VALID,
                processing_state=ProcessingState.DROPPED_EXPLICIT,
                failure_code=None,
                latency_ms=None,
            )
        elif self.mode == "gap":
            captured = ORIGIN_NS + fixture.frame_seq * 250_000_000
            value = replace(
                original,
                captured_monotonic_ns=captured,
                processed_monotonic_ns=captured + PROCESSING_LATENCY_NS,
            )
        elif self.mode == "latency":
            value = replace(
                original,
                processed_monotonic_ns=original.captured_monotonic_ns + 600_000_000,
                latency_ms=600,
            )
        elif self.mode == "backlog" and fixture.frame_seq >= FRAME_COUNT - 46:
            value = replace(
                original,
                processed_monotonic_ns=None,
                pose_count=None,
                quality_state=QualityState.VALID,
                processing_state=ProcessingState.DROPPED_EXPLICIT,
                failure_code=None,
                latency_ms=None,
            )
        value = replace(value, golden_expected_output_digest="", result_digest="")
        digest = value.recompute_result_digest()
        value = replace(value, golden_expected_output_digest=digest, result_digest=digest)
        self.expected[(fixture.fixture_id, fixture.fixture_version)] = digest
        return value

    def expected_output_digest(self, fixture: FixtureInput) -> str:
        return self.expected[(fixture.fixture_id, fixture.fixture_version)]


def _bindings(
    failures: tuple[D1FailureCode, ...] = (),
    *,
    application_digest: str = "a" * 64,
) -> SyntheticEnvironmentBindings:
    return SyntheticEnvironmentBindings(
        application_revision_digest=application_digest,
        release_manifest_digest="b" * 64,
        pose_engine_digest=ENGINE_HASH,
        encoder_policy_digest="d" * 64,
        injected_failure_codes=failures,
    )


def _research(
    root: Path,
    *,
    code: str,
    withdraw: bool = False,
    fault_hook: object | None = None,
) -> tuple[str, M2PersistenceStore]:
    backend = M1Backend(root, encryption_status="UNVERIFIED", acl_status="UNVERIFIED")
    study = backend.create_study(code, idempotency_key=f"study-{code}")
    participant = backend.create_participant(
        str(study["study_id"]), idempotency_key=f"person-{code}"
    )
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key=f"session-{code}",
        retention_policy_reference="synthetic-test-policy",
    )
    session_id = str(session["session_id"])
    if withdraw:
        backend.withdraw(session_id, idempotency_key=f"withdraw-{code}")
    backend.store.close()
    kwargs = {} if fault_hook is None else {"fault_hook": fault_hook}
    return session_id, M2PersistenceStore(root, **kwargs)  # type: ignore[arg-type]


def _request(
    session_id: str,
    fixtures: tuple[FixtureInput, ...],
    *,
    suffix: str = "nominal",
) -> SyntheticNominalRequest:
    return SyntheticNominalRequest(
        session_id=session_id,
        intent_id=f"intent-m2-s2b-{suffix}",
        artifact_id=f"artifact-m2-s2b-{suffix}",
        run_id=BUILTIN_RUN_ID,
        fixtures=fixtures,
    )


def _nominal_core(
    store: M2PersistenceStore,
    *,
    privacy: Privacy | None = None,
    bindings: SyntheticEnvironmentBindings | None = None,
) -> tuple[M2SyntheticNominalCore, tuple[FixtureInput, ...]]:
    bundle = build_builtin_nominal_bundle(ENGINE_HASH)
    return (
        M2SyntheticNominalCore(
            runner=bundle.runner,
            privacy_guard=privacy or Privacy(),
            owner_lease=Lease(),
            persistence_store=store,
            environment_bindings=bindings or _bindings(),
        ),
        bundle.fixtures,
    )


def _single_bundle() -> tuple[SyntheticRunner, tuple[FixtureInput, ...]]:
    fixture = FixtureInput(
        fixture_id="nominal-frame-single",
        fixture_version="v1",
        run_id=BUILTIN_RUN_ID,
        frame_seq=0,
        technical_input_kind=TechnicalInputKind.DETERMINISTIC_FIXTURE,
        preprocessing_id="synthetic-rgba-identity-v1",
    )
    expected = TechnicalObservation(
        schema_version=1,
        technical_input_kind=fixture.technical_input_kind,
        fixture_id=fixture.fixture_id,
        fixture_version=fixture.fixture_version,
        run_id=fixture.run_id,
        frame_seq=0,
        captured_monotonic_ns=ORIGIN_NS,
        processed_monotonic_ns=ORIGIN_NS + PROCESSING_LATENCY_NS,
        pose_engine_task_hash=ENGINE_HASH,
        preprocessing_id=fixture.preprocessing_id,
        landmark_topology_version="mediapipe-33-v1",
        landmarks=(),
        landmark_missing_mask=((True,) * 33, (True,) * 33),
        pose_count=0,
        quality_state=QualityState.VALID,
        processing_state=ProcessingState.PROCESSED,
        failure_code=None,
        latency_ms=10,
        fixture_input_hash=fixture_input_digest(fixture),
        golden_expected_output_digest="0" * 64,
        result_digest="",
    )
    definition = FixtureDefinition(
        fixture_id=fixture.fixture_id,
        fixture_version=fixture.fixture_version,
        technical_input_kind=fixture.technical_input_kind,
        preprocessing_id=fixture.preprocessing_id,
        fixture_input_hash=fixture_input_digest(fixture),
        golden_expected_output_digest=expected.recompute_result_digest(),
    )
    return (
        SyntheticRunner(
            input_provider=IdentityProvider(),
            pose_result_provider=ZeroPoseProvider(),
            monotonic_clock=SequenceClock(
                (ORIGIN_NS, ORIGIN_NS + PROCESSING_LATENCY_NS)
            ),
            sink=Sink(),
            fixture_definitions=(definition,),
            allowed_run_ids=(BUILTIN_RUN_ID,),
            pose_engine_task_hash=ENGINE_HASH,
        ),
        (fixture,),
    )


def _single_core(
    store: M2PersistenceStore,
    *,
    bindings: SyntheticEnvironmentBindings,
    privacy: Privacy | None = None,
) -> tuple[M2SyntheticNominalCore, tuple[FixtureInput, ...]]:
    runner, fixtures = _single_bundle()
    return (
        M2SyntheticNominalCore(
            runner=runner,
            privacy_guard=privacy or Privacy(),
            owner_lease=Lease(),
            persistence_store=store,
            environment_bindings=bindings,
        ),
        fixtures,
    )


def _artifact_document(
    root: Path, store: M2PersistenceStore, artifact_id: str
) -> dict[str, object]:
    manifest = store.manifest(artifact_id)
    return json.loads((root / str(manifest["relative_path"])).read_bytes())


def test_nominal_fixture_has_exact_shape_timestamps_and_golden_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = build_builtin_nominal_bundle(ENGINE_HASH)
    assert len(bundle.fixtures) == FRAME_COUNT == 18_077
    assert bundle.fixtures[0].fixture_id == "nominal-frame-00000"
    assert bundle.fixtures[-1].fixture_id == "nominal-frame-18076"
    observations = tuple(bundle.runner.process(item) for item in bundle.fixtures)
    assert observations[0].captured_monotonic_ns == ORIGIN_NS
    assert observations[-1].captured_monotonic_ns == ORIGIN_NS + 18_076 * INTERVAL_NS
    assert observations[-1].processed_monotonic_ns == (
        ORIGIN_NS + 18_076 * INTERVAL_NS + PROCESSING_LATENCY_NS
    )
    assert all(item.result_digest == item.golden_expected_output_digest for item in observations)
    assert observations[0].golden_expected_output_digest == (
        "7fb94743b22368793e0581060c52df5a1f0c0b062f78e55fabe69a5cd8a52f60"
    )
    assert observations[-1].golden_expected_output_digest == (
        "326c0e9cbd370199cb8382d17de0b459d6cbdb4c5017bc5ee16bc3c6d4176156"
    )

    monkeypatch.setattr(
        TechnicalObservation,
        "recompute_result_digest",
        lambda _self: "0" * 64,
    )
    mutant = build_builtin_nominal_bundle(ENGINE_HASH)
    mutated = mutant.runner.process(mutant.fixtures[0])
    assert mutated.failure_code is TechnicalFailureCode.MANIFEST_VALIDATION_FAILED


def test_shared_engine_preserves_preflight_and_locks_nominal_run_kind(tmp_path: Path) -> None:
    session_id, store = _research(tmp_path / "preflight", code="preflight-regression")
    preflight = build_builtin_preflight_bundle(ENGINE_HASH)
    receipt = M2SyntheticPreflightCore(
        runner=preflight.runner,
        privacy_guard=Privacy(),
        owner_lease=Lease(),
        persistence_store=store,
        environment_bindings=_bindings(),
    ).execute(
        SyntheticPreflightRequest(
            session_id=session_id,
            intent_id="intent-preflight-regression",
            artifact_id="artifact-preflight-regression",
            run_id=PREFLIGHT_RUN_ID,
            fixtures=preflight.fixtures,
        )
    )
    assert receipt.run_kind is RunKind.PREFLIGHT_60S
    assert receipt.d1_outcome is ValidationOutcome.BACKEND_CONTRACT_PASS
    store.close()

    session_id, store = _research(tmp_path / "nominal", code="nominal-lock")
    core, fixtures = _single_core(
        store, bindings=_bindings((D1FailureCode.QUALITY_INSUFFICIENT,))
    )
    nominal = core.execute(_request(session_id, fixtures))
    assert nominal.run_kind is RunKind.NOMINAL_20M
    assert nominal.d1_outcome is ValidationOutcome.NO_GO
    store.close()


def test_nominal_20m_pass_persists_exact_d1_metrics_and_receipt(tmp_path: Path) -> None:
    root = tmp_path / "root"
    session_id, store = _research(root, code="nominal-pass")
    core, fixtures = _nominal_core(store)
    receipt = core.execute(_request(session_id, fixtures))
    assert receipt.integration_failure_code is None, receipt.integration_failure_code
    assert receipt.integration_status is IntegrationStatus.PERSISTED, receipt.as_dict()
    document = _artifact_document(root, store, receipt.artifact_id or "")
    d1 = document["d1_receipt"]
    assert receipt.integration_status is IntegrationStatus.PERSISTED
    assert receipt.d1_outcome is ValidationOutcome.BACKEND_CONTRACT_PASS
    assert receipt.run_kind is RunKind.NOMINAL_20M
    assert isinstance(d1, dict)
    assert d1["run_kind"] == "NOMINAL_20M"
    assert d1["requested_duration_seconds"] == 1200
    assert d1["warmup_seconds"] == 5
    assert d1["frames_per_second"] == 15
    store.close()


def test_warmup_and_post_warmup_accounting_use_exact_denominators(tmp_path: Path) -> None:
    root = tmp_path / "root"
    session_id, store = _research(root, code="accounting")
    core, fixtures = _nominal_core(store)
    receipt = core.execute(_request(session_id, fixtures))
    document = _artifact_document(root, store, receipt.artifact_id or "")
    d1 = document["d1_receipt"]
    assert isinstance(d1, dict)
    assert d1["warmup_accounting"] == {
        "delivered_frames": 76,
        "drop_reasons": [],
        "dropped_explicit": 0,
        "failed": 0,
        "inter_frame_gaps": 75,
        "processed": 76,
        "quality_insufficient": 0,
    }
    assert d1["accounting"] == {
        "delivered_frames": 18_001,
        "drop_reasons": [],
        "dropped_explicit": 0,
        "failed": 0,
        "inter_frame_gaps": 18_000,
        "processed": 18_001,
        "quality_insufficient": 0,
    }
    store.close()


def test_stall_clock_regression_and_nonmonotonic_sequence_fail_closed(tmp_path: Path) -> None:
    for index, failure in enumerate(
        (TechnicalFailureCode.FRAME_STALLED, TechnicalFailureCode.CLOCK_REGRESSION)
    ):
        session_id, store = _research(tmp_path / failure.value, code=f"timing-{index}")
        _, fixtures = _single_bundle()
        core = M2SyntheticNominalCore(
            runner=FixedObservationRunner(failure),  # type: ignore[arg-type]
            privacy_guard=Privacy(),
            owner_lease=Lease(),
            persistence_store=store,
            environment_bindings=_bindings(),
        )
        receipt = core.execute(_request(session_id, fixtures, suffix=f"timing-{index}"))
        assert receipt.integration_status is IntegrationStatus.PERSISTED
        assert receipt.d1_outcome is ValidationOutcome.NO_GO
        assert receipt.d1_failure_code is D1FailureCode(failure.value)
        store.close()

    session_id, store = _research(tmp_path / "sequence", code="sequence")
    _, fixtures = _single_bundle()
    duplicate = replace(fixtures[0], fixture_id="nominal-frame-second")
    core = M2SyntheticNominalCore(
        runner=FixedObservationRunner(TechnicalFailureCode.INPUT_MALFORMED),  # type: ignore[arg-type]
        privacy_guard=Privacy(),
        owner_lease=Lease(),
        persistence_store=store,
        environment_bindings=_bindings(),
    )
    receipt = core.execute(_request(session_id, (fixtures[0], duplicate), suffix="sequence"))
    assert receipt.integration_status is IntegrationStatus.NOT_PERSISTED
    assert receipt.integration_failure_code is IntegrationFailureCode.REQUEST_INVALID
    store.close()


def test_nominal_metrics_enforce_coverage_gap_latency_and_backlog_thresholds(
    tmp_path: Path,
) -> None:
    for index, mode in enumerate(("coverage", "gap", "latency", "backlog")):
        root = tmp_path / mode
        session_id, store = _research(root, code=f"threshold-{index}")
        runner = MutatingNominalRunner(mode)
        core = M2SyntheticNominalCore(
            runner=runner,  # type: ignore[arg-type]
            privacy_guard=Privacy(),
            owner_lease=Lease(),
            persistence_store=store,
            environment_bindings=_bindings(),
        )
        receipt = core.execute(_request(session_id, runner.fixtures, suffix=mode))
        document = _artifact_document(root, store, receipt.artifact_id or "")
        d1 = document["d1_receipt"]
        assert receipt.integration_status is IntegrationStatus.PERSISTED
        assert receipt.d1_failure_code is D1FailureCode.QUALITY_INSUFFICIENT
        assert isinstance(d1, dict)
        metrics = d1["metrics"]
        accounting = d1["accounting"]
        assert isinstance(metrics, dict) and isinstance(accounting, dict)
        if mode == "coverage":
            assert accounting["processed"] / accounting["delivered_frames"] < 0.99
        elif mode == "gap":
            assert metrics["delivered_frames_per_second"] < 13.5
            assert metrics["p95_inter_frame_gap_ms"] > 200
        elif mode == "latency":
            assert metrics["p95_pose_latency_ms"] > 200
            assert metrics["p99_pose_latency_ms"] > 500
        else:
            assert metrics["backlog_ms"] > 2000
        store.close()


def test_input_pose_quality_and_manifest_failures_persist_exact_no_go(tmp_path: Path) -> None:
    failures = (
        D1FailureCode.INPUT_UNAVAILABLE,
        D1FailureCode.INPUT_MALFORMED,
        D1FailureCode.POSE_ENGINE_UNAVAILABLE,
        D1FailureCode.POSE_ENGINE_EXCEPTION,
        D1FailureCode.POSE_OUTPUT_INVALID,
        D1FailureCode.QUALITY_INSUFFICIENT,
        D1FailureCode.MANIFEST_VALIDATION_FAILED,
    )
    for index, failure in enumerate(failures):
        session_id, store = _research(tmp_path / failure.value, code=f"technical-{index}")
        _, fixtures = _single_bundle()
        core = M2SyntheticNominalCore(
            runner=FixedObservationRunner(TechnicalFailureCode(failure.value)),  # type: ignore[arg-type]
            privacy_guard=Privacy(),
            owner_lease=Lease(),
            persistence_store=store,
            environment_bindings=_bindings(),
        )
        receipt = core.execute(_request(session_id, fixtures, suffix=f"technical-{index}"))
        manifest = store.manifest(receipt.artifact_id or "")
        assert receipt.integration_status is IntegrationStatus.PERSISTED
        assert receipt.d1_failure_code is failure
        assert manifest["technical_failure_code"] == failure.value
        store.close()


def test_encoder_disk_durability_and_schema_failures_persist_exact_no_go(
    tmp_path: Path,
) -> None:
    failures = (
        D1FailureCode.ENCODER_UNAVAILABLE,
        D1FailureCode.ENCODER_WRITE_FAILED,
        D1FailureCode.ENCODER_FINALIZE_FAILED,
        D1FailureCode.DISK_UNAVAILABLE,
        D1FailureCode.DISK_SPACE_INSUFFICIENT,
        D1FailureCode.DISK_THROUGHPUT_INSUFFICIENT,
        D1FailureCode.DISK_FSYNC_FAILED,
        D1FailureCode.ATOMIC_RENAME_FAILED,
        D1FailureCode.SCHEMA_INCOMPATIBLE,
        D1FailureCode.UNKNOWN_TECHNICAL_FAILURE,
    )
    for index, failure in enumerate(failures):
        session_id, store = _research(tmp_path / failure.value, code=f"stage-{index}")
        core, fixtures = _single_core(store, bindings=_bindings((failure,)))
        receipt = core.execute(_request(session_id, fixtures, suffix=f"stage-{index}"))
        assert receipt.integration_status is IntegrationStatus.PERSISTED
        assert receipt.d1_outcome is ValidationOutcome.NO_GO
        assert receipt.d1_failure_code is failure
        assert store.manifest(receipt.artifact_id or "")["validity_state"] == "VALID"
        store.close()


def test_privacy_no_go_persists_but_forged_d1_receipt_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, store = _research(tmp_path / "privacy", code="privacy")
    core, fixtures = _single_core(
        store, bindings=_bindings(), privacy=Privacy(PrivacyDecision.UNSAFE)
    )
    privacy = core.execute(_request(session_id, fixtures, suffix="privacy"))
    assert privacy.integration_status is IntegrationStatus.PERSISTED
    assert privacy.d1_failure_code is D1FailureCode.PRIVACY_STOP
    store.close()

    session_id, store = _research(tmp_path / "forged", code="forged")
    core, fixtures = _single_core(
        store, bindings=_bindings((D1FailureCode.QUALITY_INSUFFICIENT,))
    )
    monkeypatch.setattr(
        "pdu_exam_observer.m2_synthetic_integration.verify_receipt_semantics",
        lambda _receipt: False,
    )
    forged = core.execute(_request(session_id, fixtures, suffix="forged"))
    assert forged.integration_status is IntegrationStatus.NOT_PERSISTED
    assert forged.integration_failure_code is IntegrationFailureCode.D1_RECEIPT_INVALID
    assert forged.artifact_id is None and forged.artifact_sha256 is None
    store.close()


def test_replay_collision_persistence_fault_and_withdrawal_race_fail_closed(
    tmp_path: Path,
) -> None:
    bindings = _bindings((D1FailureCode.QUALITY_INSUFFICIENT,))
    session_id, store = _research(tmp_path / "replay", code="replay")
    core, fixtures = _single_core(store, bindings=bindings)
    first = core.execute(_request(session_id, fixtures, suffix="replay"))
    replay_core, replay_fixtures = _single_core(store, bindings=bindings)
    replay = replay_core.execute(_request(session_id, replay_fixtures, suffix="replay"))
    changed_core, changed_fixtures = _single_core(
        store,
        bindings=_bindings(
            (D1FailureCode.QUALITY_INSUFFICIENT,), application_digest="e" * 64
        ),
    )
    changed = changed_core.execute(_request(session_id, changed_fixtures, suffix="replay"))
    assert first.artifact_sha256 == replay.artifact_sha256
    assert changed.integration_status is IntegrationStatus.NOT_PERSISTED
    assert changed.artifact_id is None and changed.artifact_sha256 is None
    store.close()

    def fail_write(stage: str) -> None:
        if stage == "write":
            raise OSError("injected")

    session_id, store = _research(
        tmp_path / "fault", code="fault", fault_hook=fail_write
    )
    core, fixtures = _single_core(store, bindings=bindings)
    failed = core.execute(_request(session_id, fixtures, suffix="fault"))
    assert failed.integration_status is IntegrationStatus.NOT_PERSISTED
    assert failed.artifact_id is None and failed.artifact_sha256 is None
    store.close()

    session_id, store = _research(
        tmp_path / "withdrawn", code="withdrawn", withdraw=True
    )
    core, fixtures = _single_core(store, bindings=bindings)
    withdrawn = core.execute(_request(session_id, fixtures, suffix="withdrawn"))
    assert withdrawn.integration_status is IntegrationStatus.NOT_PERSISTED
    assert withdrawn.artifact_id is None and withdrawn.artifact_sha256 is None
    store.close()


def test_nominal_artifact_is_canonical_minimized_and_hash_bound(tmp_path: Path) -> None:
    root = tmp_path / "root"
    session_id, store = _research(root, code="artifact")
    core, fixtures = _nominal_core(store)
    receipt = core.execute(_request(session_id, fixtures, suffix="artifact"))
    manifest = store.manifest(receipt.artifact_id or "")
    payload = (root / str(manifest["relative_path"])).read_bytes()
    document = json.loads(payload)
    assert payload == (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    assert hashlib.sha256(payload).hexdigest() == receipt.artifact_sha256
    assert document["artifact_kind"] == "M2_SYNTHETIC_NOMINAL_RECEIPT"
    assert len(document["observation_result_digests"]) == FRAME_COUNT
    forbidden = {
        "landmarks",
        "fixture_bytes",
        "frame",
        "session_id",
        "participant_id",
        "local_path",
        "device_id",
        "username",
        "exception",
    }
    assert forbidden.isdisjoint(document)
    assert forbidden.isdisjoint(document["d1_receipt"])
    store.close()


def test_nominal_cli_is_no_argument_deterministic_sanitized_and_cleans_temp_root() -> None:
    command = [sys.executable, str(ROOT / "scripts" / "run_m2_s2b_synthetic_nominal.py")]
    first = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    second = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr == b""
    document = json.loads(first.stdout)
    assert document["run_kind"] == "NOMINAL_20M"
    assert document["d1_outcome"] == "BACKEND_CONTRACT_PASS"
    assert document["device_gate_decision"] == "UNVERIFIED"
    assert document["d1_go"] is False
    assert document["temp_root_removed"] is True
    assert document["package_contains_integration"] is False
    assert {"path", "session_id", "participant_id", "device_id"}.isdisjoint(document)
    rejected = subprocess.run([*command, "--path", "x"], cwd=ROOT, capture_output=True)
    assert rejected.returncode == 2
    assert rejected.stderr == b""
    assert json.loads(rejected.stdout)["integration_failure_code"] == "REQUEST_INVALID"

    paths = (
        ROOT / "src" / "pdu_exam_observer" / "m2_synthetic_integration.py",
        ROOT / "src" / "pdu_exam_observer" / "m2_synthetic_nominal_fixture.py",
        ROOT / "scripts" / "run_m2_s2b_synthetic_nominal.py",
    )
    for path in paths:
        imports = {
            alias.name
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        }
        assert imports.isdisjoint({"cv2", "mediapipe", "fastapi", "subprocess"})
