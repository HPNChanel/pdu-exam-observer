import ast
import hashlib
import inspect
import json
from dataclasses import replace

import pytest

from pdu_exam_observer import m2_synthetic
from pdu_exam_observer.m2_synthetic import (
    FixtureDefinition,
    FixtureInput,
    Landmark,
    PoseEngineUnavailable,
    PoseResult,
    ProcessingState,
    QualityState,
    ReservedNoHumanDeviceScene,
    SyntheticRunner,
    TechnicalFailureCode,
    TechnicalInputKind,
)

ENGINE_HASH = "a" * 64
PREPROCESSING_ID = "synthetic-rgba-identity-v1"
TOPOLOGY_VERSION = "mediapipe-33-v1"


class SequenceClock:
    def __init__(self, values: list[int]) -> None:
        self._values = iter(values)

    def now_ns(self) -> int:
        return next(self._values)


class DeterministicInputProvider:
    def __init__(
        self,
        replacement: FixtureInput | None = None,
        error: Exception | None = None,
        unavailable: bool = False,
    ) -> None:
        self._replacement = replacement
        self._error = error
        self._unavailable = unavailable

    def provide(self, fixture: FixtureInput) -> FixtureInput | None:
        if self._error is not None:
            raise self._error
        if self._unavailable:
            return None
        return self._replacement or fixture


class StaticPoseProvider:
    def __init__(self, result: PoseResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    def infer(self, fixture: FixtureInput) -> PoseResult | None:
        if self._error is not None:
            raise self._error
        return self._result


class RecordingSink:
    def __init__(self) -> None:
        self.observations: list[object] = []

    def observe(self, observation: object) -> None:
        self.observations.append(observation)


def _landmarks() -> tuple[Landmark, ...]:
    return tuple(
        Landmark(float(index), float(index + 1), float(index + 2), 0.99) for index in range(33)
    )


def _mask(pose_count: int) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    return tuple(tuple(index >= pose_count for _landmark in range(33)) for index in range(2))  # type: ignore[return-value]


def _pose_result(pose_count: int = 1, quality: QualityState = QualityState.VALID) -> PoseResult:
    poses = tuple(_landmarks() for _pose in range(pose_count))
    return PoseResult(
        landmark_topology_version=TOPOLOGY_VERSION,
        landmarks=poses,
        landmark_missing_mask=_mask(pose_count),
        ordered_landmark_indices=tuple(tuple(range(33)) for _pose in range(pose_count)),
        quality_state=quality,
    )


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _input_hash(fixture: FixtureInput) -> str:
    return _canonical_digest(
        {
            "fixture_id": fixture.fixture_id,
            "fixture_version": fixture.fixture_version,
            "frame_seq": fixture.frame_seq,
            "preprocessing_id": fixture.preprocessing_id,
            "run_id": fixture.run_id,
            "technical_input_kind": fixture.technical_input_kind.value,
        }
    )


def _golden_for_valid_fixture(
    fixture: FixtureInput, pose_count: int, captured_ns: int, processed_ns: int
) -> str:
    poses = [
        [
            {"visibility": 0.99, "x": float(index), "y": float(index + 1), "z": float(index + 2)}
            for index in range(33)
        ]
        for _pose in range(pose_count)
    ]
    return _canonical_digest(
        {
            "captured_monotonic_ns": captured_ns,
            "failure_code": None,
            "fixture_id": fixture.fixture_id,
            "fixture_input_hash": _input_hash(fixture),
            "fixture_version": fixture.fixture_version,
            "frame_seq": fixture.frame_seq,
            "landmark_missing_mask": [list(row) for row in _mask(pose_count)],
            "landmark_topology_version": TOPOLOGY_VERSION,
            "landmarks": poses,
            "latency_ms": (processed_ns - captured_ns) // 1_000_000,
            "pose_count": pose_count,
            "pose_engine_task_hash": ENGINE_HASH,
            "preprocessing_id": PREPROCESSING_ID,
            "processed_monotonic_ns": processed_ns,
            "processing_state": "PROCESSED",
            "quality_state": "VALID",
            "run_id": fixture.run_id,
            "schema_version": 1,
            "technical_input_kind": fixture.technical_input_kind.value,
        }
    )


def _fixture(
    frame_seq: int = 0, kind: TechnicalInputKind = TechnicalInputKind.DETERMINISTIC_FIXTURE
) -> FixtureInput:
    return FixtureInput(
        fixture_id="fixture-alpha",
        fixture_version="v1",
        run_id="run-alpha",
        frame_seq=frame_seq,
        technical_input_kind=kind,
        preprocessing_id=PREPROCESSING_ID,
    )


def _definition(
    fixture: FixtureInput,
    pose_count: int = 1,
    captured_ns: int = 1_000_000_000,
    processed_ns: int = 1_010_000_000,
) -> FixtureDefinition:
    return FixtureDefinition(
        fixture_id=fixture.fixture_id,
        fixture_version=fixture.fixture_version,
        technical_input_kind=fixture.technical_input_kind,
        preprocessing_id=fixture.preprocessing_id,
        fixture_input_hash=_input_hash(fixture),
        golden_expected_output_digest=_golden_for_valid_fixture(
            fixture, pose_count, captured_ns, processed_ns
        ),
    )


def _runner(
    fixture: FixtureInput,
    pose: PoseResult | None = None,
    *,
    input_provider: DeterministicInputProvider | None = None,
    pose_provider: StaticPoseProvider | None = None,
    clock: SequenceClock | None = None,
    sink: RecordingSink | None = None,
) -> SyntheticRunner:
    selected_pose = pose or _pose_result()
    return SyntheticRunner(
        input_provider=input_provider or DeterministicInputProvider(),
        pose_result_provider=pose_provider or StaticPoseProvider(selected_pose),
        monotonic_clock=clock or SequenceClock([1_000_000_000, 1_010_000_000]),
        sink=sink or RecordingSink(),
        fixture_definitions=(_definition(fixture, pose_count=len(selected_pose.landmarks)),),
        allowed_run_ids=(fixture.run_id,),
        pose_engine_task_hash=ENGINE_HASH,
    )


def test_successful_fixture_has_exact_contract_digest_and_nonwriting_sink() -> None:
    fixture = _fixture()
    sink = RecordingSink()
    observation = _runner(fixture, sink=sink).process(fixture)

    assert observation.schema_version == 1
    assert observation.pose_count == 1
    assert observation.quality_state is QualityState.VALID
    assert observation.processing_state is ProcessingState.PROCESSED
    assert observation.failure_code is None
    assert observation.fixture_input_hash == _input_hash(fixture)
    assert observation.result_digest == observation.golden_expected_output_digest
    assert observation.result_digest == _golden_for_valid_fixture(
        fixture, 1, 1_000_000_000, 1_010_000_000
    )
    assert sink.observations == [observation]


@pytest.mark.parametrize("pose_count", [0, 1, 2])
def test_complete_zero_one_and_two_pose_shapes_reconcile_count(pose_count: int) -> None:
    fixture = _fixture()
    observation = _runner(
        fixture,
        pose=_pose_result(pose_count),
    ).process(fixture)

    assert observation.pose_count == pose_count
    assert len(observation.landmarks) == pose_count
    assert len(observation.landmark_missing_mask) == 2
    assert all(len(row) == 33 for row in observation.landmark_missing_mask)
    assert observation.failure_code is None


def test_tampered_result_digest_is_detectable_against_the_golden_fixture_vector() -> None:
    fixture = _fixture()
    observation = _runner(fixture).process(fixture)
    tampered = observation.with_result_digest("0" * 64)

    assert observation.result_digest == observation.golden_expected_output_digest
    assert tampered.result_digest != tampered.recompute_result_digest()
    assert tampered.result_digest != observation.golden_expected_output_digest


def test_mismatched_golden_digest_fails_closed_without_a_successful_sink_observation() -> None:
    fixture = _fixture()
    definition = replace(_definition(fixture), golden_expected_output_digest="0" * 64)
    sink = RecordingSink()
    runner = SyntheticRunner(
        input_provider=DeterministicInputProvider(),
        pose_result_provider=StaticPoseProvider(_pose_result()),
        monotonic_clock=SequenceClock([1_000_000_000, 1_010_000_000]),
        sink=sink,
        fixture_definitions=(definition,),
        allowed_run_ids=(fixture.run_id,),
        pose_engine_task_hash=ENGINE_HASH,
    )

    observation = runner.process(fixture)

    assert observation.failure_code is TechnicalFailureCode.MANIFEST_VALIDATION_FAILED
    assert observation.quality_state is QualityState.FAILED
    assert observation.processing_state is ProcessingState.FAILED
    assert observation.pose_count is None
    assert observation.result_digest == observation.recompute_result_digest()
    assert observation.result_digest != observation.golden_expected_output_digest
    assert sink.observations == [observation]


def test_rejects_nonincreasing_frame_sequence_and_clock_regression() -> None:
    first = _fixture(0)
    second = _fixture(0)
    runner = SyntheticRunner(
        input_provider=DeterministicInputProvider(),
        pose_result_provider=StaticPoseProvider(_pose_result()),
        monotonic_clock=SequenceClock([1_000_000_000, 1_010_000_000, 999_000_000, 1_011_000_000]),
        sink=RecordingSink(),
        fixture_definitions=(_definition(first),),
        allowed_run_ids=(first.run_id,),
        pose_engine_task_hash=ENGINE_HASH,
    )

    assert runner.process(first).failure_code is None
    sequence_failure = runner.process(second)
    assert sequence_failure.failure_code is TechnicalFailureCode.INPUT_MALFORMED

    clock_failure = _runner(
        _fixture(), clock=SequenceClock([1_010_000_000, 1_000_000_000])
    ).process(_fixture())
    assert clock_failure.failure_code is TechnicalFailureCode.CLOCK_REGRESSION
    assert clock_failure.latency_ms is None


@pytest.mark.parametrize(
    "result",
    [
        PoseResult(TOPOLOGY_VERSION, (_landmarks(),), _mask(1), ((0,) * 33,), QualityState.VALID),
        PoseResult(
            TOPOLOGY_VERSION,
            (_landmarks(),),
            ((False,) * 32, (True,) * 33),
            (tuple(range(33)),),
            QualityState.VALID,
        ),
        PoseResult(
            TOPOLOGY_VERSION, (_landmarks(),), _mask(0), (tuple(range(33)),), QualityState.VALID
        ),
        PoseResult(
            TOPOLOGY_VERSION,
            (_landmarks()[:-1],),
            _mask(1),
            (tuple(range(32)),),
            QualityState.VALID,
        ),
        PoseResult(
            TOPOLOGY_VERSION,
            (_landmarks(),),
            _mask(1),
            (tuple(reversed(range(33))),),
            QualityState.VALID,
        ),
        PoseResult(
            TOPOLOGY_VERSION,
            (_landmarks(), _landmarks(), _landmarks()),
            _mask(2),
            (tuple(range(33)),) * 3,
            QualityState.VALID,
        ),
    ],
)
def test_malformed_topology_mask_count_or_landmarks_fails_closed(result: PoseResult) -> None:
    fixture = _fixture()
    observation = _runner(fixture, pose=result).process(fixture)

    assert observation.failure_code is TechnicalFailureCode.POSE_OUTPUT_INVALID
    assert observation.processing_state is ProcessingState.FAILED
    assert observation.pose_count is None


def test_provider_unavailability_and_exceptions_do_not_become_zero_pose_success() -> None:
    fixture = _fixture()
    unavailable = _runner(
        fixture, input_provider=DeterministicInputProvider(unavailable=True)
    ).process(fixture)
    input_exception = _runner(
        fixture, input_provider=DeterministicInputProvider(error=RuntimeError("unavailable"))
    ).process(fixture)
    pose_unavailable = _runner(
        fixture, pose_provider=StaticPoseProvider(error=PoseEngineUnavailable("missing"))
    ).process(fixture)
    pose_exception = _runner(
        fixture, pose_provider=StaticPoseProvider(error=RuntimeError("boom"))
    ).process(fixture)

    assert unavailable.failure_code is TechnicalFailureCode.INPUT_UNAVAILABLE
    assert input_exception.failure_code is TechnicalFailureCode.INPUT_UNAVAILABLE
    assert pose_unavailable.failure_code is TechnicalFailureCode.POSE_ENGINE_UNAVAILABLE
    assert pose_exception.failure_code is TechnicalFailureCode.POSE_ENGINE_EXCEPTION
    assert all(
        item.pose_count is None
        for item in (unavailable, input_exception, pose_unavailable, pose_exception)
    )


def test_quality_insufficient_is_processed_and_never_silently_excluded() -> None:
    fixture = _fixture()
    observation = _runner(fixture, pose=_pose_result(1, QualityState.INSUFFICIENT)).process(fixture)

    assert observation.quality_state is QualityState.INSUFFICIENT
    assert observation.processing_state is ProcessingState.PROCESSED
    assert observation.failure_code is TechnicalFailureCode.QUALITY_INSUFFICIENT
    assert observation.pose_count == 1


def test_unknown_provider_failure_is_schema_incompatible_not_an_accepted_failure() -> None:
    fixture = _fixture()
    result = _pose_result()
    result = PoseResult(
        result.landmark_topology_version,
        result.landmarks,
        result.landmark_missing_mask,
        result.ordered_landmark_indices,
        result.quality_state,
        reported_failure_code="NOT_A_FAILURE_CODE",
    )

    observation = _runner(fixture, pose=result).process(fixture)
    assert observation.failure_code is TechnicalFailureCode.SCHEMA_INCOMPATIBLE
    assert observation.processing_state is ProcessingState.FAILED


def test_no_human_device_scene_is_reserved_for_d1() -> None:
    fixture = _fixture(kind=TechnicalInputKind.NO_HUMAN_DEVICE_SCENE)
    with pytest.raises(ReservedNoHumanDeviceScene):
        _runner(fixture).process(fixture)


def test_pure_seam_exposes_no_forbidden_research_or_io_interface() -> None:
    source = inspect.getsource(m2_synthetic)
    imports = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    forbidden_imports = {
        "sqlite3",
        "fastapi",
        "os",
        "pathlib",
        "subprocess",
        "cv2",
        "mediapipe",
        "pdu_exam_observer.api",
        "pdu_exam_observer.m1",
    }
    forbidden_fields = {"participant_id", "session_id", "source_kind", "label", "confidence"}

    assert imports.isdisjoint(forbidden_imports)
    assert forbidden_fields.isdisjoint(m2_synthetic.TechnicalObservation.__dataclass_fields__)
    assert not hasattr(m2_synthetic, "SampleProvenance")
    assert not hasattr(m2_synthetic, "AlertEvent")
    assert "RESEARCH_COLLECTION_NOT_IMPLEMENTED" not in source
    assert "write_text" not in source and "sqlite" not in source.lower()
