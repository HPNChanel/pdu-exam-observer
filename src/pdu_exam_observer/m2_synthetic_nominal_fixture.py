"""Built-in zero-pose fixture series for the M2-S2B simulated nominal run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pdu_exam_observer.m2_synthetic import (
    FixtureDefinition,
    FixtureInput,
    PoseResult,
    QualityState,
    SyntheticRunner,
    TechnicalInputKind,
    TechnicalObservation,
    fixture_input_digest,
)

FRAME_COUNT = 18_077
ORIGIN_NS = 1_800_000_000_000
INTERVAL_NS = 1_000_000_000 // 15
PROCESSING_LATENCY_NS = 10_000_000
BUILTIN_RUN_ID = "m2-s2b-nominal-20m"
PREPROCESSING_ID = "synthetic-rgba-identity-v1"
TOPOLOGY_VERSION = "mediapipe-33-v1"


@dataclass(frozen=True, slots=True)
class BuiltinNominalBundle:
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


def _independent_zero_pose_digest(
    fixture: FixtureInput,
    *,
    captured_ns: int,
    processed_ns: int,
    pose_engine_task_hash: str,
) -> str:
    payload = {
        "captured_monotonic_ns": captured_ns,
        "failure_code": None,
        "fixture_id": fixture.fixture_id,
        "fixture_input_hash": fixture_input_digest(fixture),
        "fixture_version": fixture.fixture_version,
        "frame_seq": fixture.frame_seq,
        "landmark_missing_mask": [[True] * 33, [True] * 33],
        "landmark_topology_version": TOPOLOGY_VERSION,
        "landmarks": [],
        "latency_ms": PROCESSING_LATENCY_NS // 1_000_000,
        "pose_count": 0,
        "pose_engine_task_hash": pose_engine_task_hash,
        "preprocessing_id": fixture.preprocessing_id,
        "processed_monotonic_ns": processed_ns,
        "processing_state": "PROCESSED",
        "quality_state": "VALID",
        "run_id": fixture.run_id,
        "schema_version": 1,
        "technical_input_kind": fixture.technical_input_kind.value,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_builtin_nominal_bundle(pose_engine_task_hash: str) -> BuiltinNominalBundle:
    fixtures = tuple(
        FixtureInput(
            fixture_id=f"nominal-frame-{index:05d}",
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
        definitions.append(
            FixtureDefinition(
                fixture_id=fixture.fixture_id,
                fixture_version=fixture.fixture_version,
                technical_input_kind=fixture.technical_input_kind,
                preprocessing_id=fixture.preprocessing_id,
                fixture_input_hash=fixture_input_digest(fixture),
                golden_expected_output_digest=_independent_zero_pose_digest(
                    fixture,
                    captured_ns=captured_ns,
                    processed_ns=processed_ns,
                    pose_engine_task_hash=pose_engine_task_hash,
                ),
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
    return BuiltinNominalBundle(runner=runner, fixtures=fixtures)
