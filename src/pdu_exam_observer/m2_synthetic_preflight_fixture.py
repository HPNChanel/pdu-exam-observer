"""Built-in zero-pose fixture series for the M2-S2A simulated smoke."""

from __future__ import annotations

from dataclasses import dataclass

from pdu_exam_observer.m2_synthetic import (
    FixtureDefinition,
    FixtureInput,
    PoseResult,
    ProcessingState,
    QualityState,
    SyntheticRunner,
    TechnicalInputKind,
    TechnicalObservation,
    fixture_input_digest,
)

FRAME_COUNT = 977
ORIGIN_NS = 900_000_000_000
INTERVAL_NS = 1_000_000_000 // 15
PROCESSING_LATENCY_NS = 10_000_000
BUILTIN_RUN_ID = "m2-s2a-preflight"
PREPROCESSING_ID = "synthetic-rgba-identity-v1"
TOPOLOGY_VERSION = "mediapipe-33-v1"


@dataclass(frozen=True, slots=True)
class BuiltinPreflightBundle:
    runner: SyntheticRunner
    fixtures: tuple[FixtureInput, ...]


class _IdentityInputProvider:
    def provide(self, fixture: FixtureInput) -> FixtureInput:
        return fixture


class _ZeroPoseProvider:
    def infer(self, _fixture: FixtureInput) -> PoseResult:
        return PoseResult(
            landmark_topology_version=TOPOLOGY_VERSION,
            landmarks=(),
            landmark_missing_mask=((True,) * 33, (True,) * 33),
            ordered_landmark_indices=(),
            quality_state=QualityState.VALID,
            reported_pose_count=0,
        )


class _SequenceClock:
    def __init__(self, values: tuple[int, ...]) -> None:
        self._values = iter(values)

    def now_ns(self) -> int:
        return next(self._values)


class _DiscardingSink:
    def observe(self, _observation: TechnicalObservation) -> None:
        return None


def build_builtin_preflight_bundle(pose_engine_task_hash: str) -> BuiltinPreflightBundle:
    fixtures = tuple(
        FixtureInput(
            fixture_id=f"preflight-frame-{index:04d}",
            fixture_version="v1",
            run_id=BUILTIN_RUN_ID,
            frame_seq=index,
            technical_input_kind=TechnicalInputKind.DETERMINISTIC_FIXTURE,
            preprocessing_id=PREPROCESSING_ID,
        )
        for index in range(FRAME_COUNT)
    )
    definitions: list[FixtureDefinition] = []
    clock_values: list[int] = []
    for fixture in fixtures:
        captured_ns = ORIGIN_NS + fixture.frame_seq * INTERVAL_NS
        processed_ns = captured_ns + PROCESSING_LATENCY_NS
        expected = TechnicalObservation(
            schema_version=1,
            technical_input_kind=fixture.technical_input_kind,
            fixture_id=fixture.fixture_id,
            fixture_version=fixture.fixture_version,
            run_id=fixture.run_id,
            frame_seq=fixture.frame_seq,
            captured_monotonic_ns=captured_ns,
            processed_monotonic_ns=processed_ns,
            pose_engine_task_hash=pose_engine_task_hash,
            preprocessing_id=fixture.preprocessing_id,
            landmark_topology_version=TOPOLOGY_VERSION,
            landmarks=(),
            landmark_missing_mask=((True,) * 33, (True,) * 33),
            pose_count=0,
            quality_state=QualityState.VALID,
            processing_state=ProcessingState.PROCESSED,
            failure_code=None,
            latency_ms=PROCESSING_LATENCY_NS // 1_000_000,
            fixture_input_hash=fixture_input_digest(fixture),
            golden_expected_output_digest="0" * 64,
            result_digest="",
        )
        golden = expected.recompute_result_digest()
        definitions.append(
            FixtureDefinition(
                fixture_id=fixture.fixture_id,
                fixture_version=fixture.fixture_version,
                technical_input_kind=fixture.technical_input_kind,
                preprocessing_id=fixture.preprocessing_id,
                fixture_input_hash=fixture_input_digest(fixture),
                golden_expected_output_digest=golden,
            )
        )
        clock_values.extend((captured_ns, processed_ns))
    runner = SyntheticRunner(
        input_provider=_IdentityInputProvider(),
        pose_result_provider=_ZeroPoseProvider(),
        monotonic_clock=_SequenceClock(tuple(clock_values)),
        sink=_DiscardingSink(),
        fixture_definitions=tuple(definitions),
        allowed_run_ids=(BUILTIN_RUN_ID,),
        pose_engine_task_hash=pose_engine_task_hash,
    )
    return BuiltinPreflightBundle(runner=runner, fixtures=fixtures)

