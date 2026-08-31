"""Pure, deterministic M2-S1 technical-fixture seam.

This module is deliberately in-memory only.  It does not represent a study
record, a device interface, or a research collection workflow.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

SCHEMA_VERSION = 1
LANDMARK_TOPOLOGY_VERSION = "mediapipe-33-v1"
_ACCEPTED_INPUT_KINDS: frozenset[TechnicalInputKind]  # declared after the enum


class TechnicalInputKind(StrEnum):
    DETERMINISTIC_FIXTURE = "DETERMINISTIC_FIXTURE"
    AI_RENDERED_FIXTURE = "AI_RENDERED_FIXTURE"
    NO_HUMAN_DEVICE_SCENE = "NO_HUMAN_DEVICE_SCENE"


_ACCEPTED_INPUT_KINDS = frozenset(
    {TechnicalInputKind.DETERMINISTIC_FIXTURE, TechnicalInputKind.AI_RENDERED_FIXTURE}
)
_DEFINED_INPUT_KINDS = frozenset(
    {
        TechnicalInputKind.DETERMINISTIC_FIXTURE,
        TechnicalInputKind.AI_RENDERED_FIXTURE,
        TechnicalInputKind.NO_HUMAN_DEVICE_SCENE,
    }
)


class TechnicalFailureCode(StrEnum):
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


class QualityState(StrEnum):
    VALID = "VALID"
    INSUFFICIENT = "INSUFFICIENT"
    FAILED = "FAILED"


class ProcessingState(StrEnum):
    PROCESSED = "PROCESSED"
    DROPPED_EXPLICIT = "DROPPED_EXPLICIT"
    FAILED = "FAILED"


class ReservedNoHumanDeviceScene(ValueError):
    """Raised because NO_HUMAN_DEVICE_SCENE belongs to the unopened D1 rung."""


class PoseEngineUnavailable(RuntimeError):
    """The injected pose provider explicitly reports that no engine is available."""


@dataclass(frozen=True, slots=True)
class Landmark:
    x: float
    y: float
    z: float
    visibility: float


@dataclass(frozen=True, slots=True)
class FixtureInput:
    fixture_id: str
    fixture_version: str
    run_id: str
    frame_seq: int
    technical_input_kind: TechnicalInputKind
    preprocessing_id: str


@dataclass(frozen=True, slots=True)
class FixtureDefinition:
    fixture_id: str
    fixture_version: str
    technical_input_kind: TechnicalInputKind
    preprocessing_id: str
    fixture_input_hash: str
    golden_expected_output_digest: str


@dataclass(frozen=True, slots=True)
class PoseResult:
    landmark_topology_version: str
    landmarks: tuple[tuple[Landmark, ...], ...]
    landmark_missing_mask: tuple[tuple[bool, ...], tuple[bool, ...]]
    ordered_landmark_indices: tuple[tuple[int, ...], ...]
    quality_state: QualityState
    reported_failure_code: str | None = None
    reported_pose_count: int | None = None


@dataclass(frozen=True, slots=True)
class TechnicalObservation:
    schema_version: int
    technical_input_kind: TechnicalInputKind
    fixture_id: str
    fixture_version: str
    run_id: str
    frame_seq: int
    captured_monotonic_ns: int
    processed_monotonic_ns: int | None
    pose_engine_task_hash: str
    preprocessing_id: str
    landmark_topology_version: str
    landmarks: tuple[tuple[Landmark, ...], ...]
    landmark_missing_mask: tuple[tuple[bool, ...], tuple[bool, ...]]
    pose_count: int | None
    quality_state: QualityState
    processing_state: ProcessingState
    failure_code: TechnicalFailureCode | None
    latency_ms: int | None
    fixture_input_hash: str
    golden_expected_output_digest: str
    result_digest: str

    def digest_payload(self) -> dict[str, object]:
        """Return the digest basis, excluding both derived digest fields.

        ``golden_expected_output_digest`` is also excluded: otherwise making it
        equal the observed digest would create a circular hash definition.
        """

        return {
            "captured_monotonic_ns": self.captured_monotonic_ns,
            "failure_code": self.failure_code.value if self.failure_code is not None else None,
            "fixture_id": self.fixture_id,
            "fixture_input_hash": self.fixture_input_hash,
            "fixture_version": self.fixture_version,
            "frame_seq": self.frame_seq,
            "landmark_missing_mask": [list(row) for row in self.landmark_missing_mask],
            "landmark_topology_version": self.landmark_topology_version,
            "landmarks": [
                [
                    {
                        "visibility": landmark.visibility,
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z,
                    }
                    for landmark in pose
                ]
                for pose in self.landmarks
            ],
            "latency_ms": self.latency_ms,
            "pose_count": self.pose_count,
            "pose_engine_task_hash": self.pose_engine_task_hash,
            "preprocessing_id": self.preprocessing_id,
            "processed_monotonic_ns": self.processed_monotonic_ns,
            "processing_state": self.processing_state.value,
            "quality_state": self.quality_state.value,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "technical_input_kind": self.technical_input_kind.value,
        }

    def recompute_result_digest(self) -> str:
        return _canonical_digest(self.digest_payload())

    def with_result_digest(self, result_digest: str) -> TechnicalObservation:
        return replace(self, result_digest=result_digest)


class DeterministicInputProvider(Protocol):
    def provide(self, fixture: FixtureInput) -> FixtureInput | None: ...


class PoseResultProvider(Protocol):
    def infer(self, fixture: FixtureInput) -> PoseResult | None: ...


class MonotonicClock(Protocol):
    def now_ns(self) -> int: ...


class TechnicalObservationSink(Protocol):
    def observe(self, observation: TechnicalObservation) -> None: ...


class SyntheticRunner:
    """Validate one allowlisted fixture at a time through injected pure providers."""

    def __init__(
        self,
        *,
        input_provider: DeterministicInputProvider,
        pose_result_provider: PoseResultProvider,
        monotonic_clock: MonotonicClock,
        sink: TechnicalObservationSink,
        fixture_definitions: tuple[FixtureDefinition, ...],
        allowed_run_ids: tuple[str, ...],
        pose_engine_task_hash: str,
    ) -> None:
        if not _is_sha256(pose_engine_task_hash):
            raise ValueError("pose_engine_task_hash must be a SHA-256")
        if not allowed_run_ids or not all(
            _is_opaque_identifier(value) for value in allowed_run_ids
        ):
            raise ValueError("allowed_run_ids must be opaque nonempty identifiers")
        definitions: dict[tuple[str, str], FixtureDefinition] = {}
        for definition in fixture_definitions:
            key = (definition.fixture_id, definition.fixture_version)
            if key in definitions or not _definition_is_valid(definition):
                raise ValueError("fixture definitions must be unique and valid")
            definitions[key] = definition
        if not definitions:
            raise ValueError("at least one fixture definition is required")
        self._input_provider = input_provider
        self._pose_result_provider = pose_result_provider
        self._clock = monotonic_clock
        self._sink = sink
        self._definitions = definitions
        self._allowed_run_ids = frozenset(allowed_run_ids)
        self._pose_engine_task_hash = pose_engine_task_hash
        self._last_frame_seq: dict[str, int] = {}
        self._last_captured_ns: dict[str, int] = {}
        self._last_processed_ns: dict[str, int] = {}

    def process(self, fixture: FixtureInput) -> TechnicalObservation:
        definition = self._definition_for(fixture)
        self._validate_input_identity(fixture, definition)
        if fixture.technical_input_kind is TechnicalInputKind.NO_HUMAN_DEVICE_SCENE:
            raise ReservedNoHumanDeviceScene("NO_HUMAN_DEVICE_SCENE is reserved for D1")
        if fixture.frame_seq < 0 or self._frame_seq_not_increasing(fixture):
            return self._emit(
                self._failure(fixture, definition, TechnicalFailureCode.INPUT_MALFORMED)
            )

        captured_ns = self._clock.now_ns()
        timing_failure = self._capture_timing_failure(fixture, captured_ns)
        if timing_failure is not None:
            return self._emit(
                self._failure(fixture, definition, timing_failure, captured_ns=captured_ns)
            )

        self._last_frame_seq[fixture.run_id] = fixture.frame_seq
        self._last_captured_ns[fixture.run_id] = captured_ns
        try:
            provided = self._input_provider.provide(fixture)
        except Exception:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    TechnicalFailureCode.INPUT_UNAVAILABLE,
                    captured_ns=captured_ns,
                )
            )
        if provided is None:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    TechnicalFailureCode.INPUT_UNAVAILABLE,
                    captured_ns=captured_ns,
                )
            )
        if provided != fixture:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    TechnicalFailureCode.INPUT_MALFORMED,
                    captured_ns=captured_ns,
                )
            )

        try:
            pose = self._pose_result_provider.infer(provided)
        except PoseEngineUnavailable:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    TechnicalFailureCode.POSE_ENGINE_UNAVAILABLE,
                    captured_ns=captured_ns,
                )
            )
        except Exception:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    TechnicalFailureCode.POSE_ENGINE_EXCEPTION,
                    captured_ns=captured_ns,
                )
            )
        if pose is None:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    TechnicalFailureCode.POSE_ENGINE_UNAVAILABLE,
                    captured_ns=captured_ns,
                )
            )

        processed_ns = self._clock.now_ns()
        processing_timing_failure = self._processing_timing_failure(
            fixture, captured_ns, processed_ns
        )
        if processing_timing_failure is not None:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    processing_timing_failure,
                    captured_ns=captured_ns,
                    processed_ns=processed_ns,
                )
            )
        self._last_processed_ns[fixture.run_id] = processed_ns

        validation_failure = _validate_pose_result(pose)
        if validation_failure is not None:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    validation_failure,
                    captured_ns=captured_ns,
                    processed_ns=processed_ns,
                )
            )
        if pose.reported_failure_code is not None:
            try:
                reported_failure = TechnicalFailureCode(pose.reported_failure_code)
            except ValueError:
                reported_failure = TechnicalFailureCode.SCHEMA_INCOMPATIBLE
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    reported_failure,
                    captured_ns=captured_ns,
                    processed_ns=processed_ns,
                )
            )

        pose_count = len(pose.landmarks)
        if pose.quality_state is QualityState.INSUFFICIENT:
            observation = self._observation(
                fixture,
                definition,
                captured_ns=captured_ns,
                processed_ns=processed_ns,
                landmarks=pose.landmarks,
                mask=pose.landmark_missing_mask,
                pose_count=pose_count,
                quality_state=QualityState.INSUFFICIENT,
                processing_state=ProcessingState.PROCESSED,
                failure_code=TechnicalFailureCode.QUALITY_INSUFFICIENT,
            )
            return self._emit(observation)

        observation = self._observation(
            fixture,
            definition,
            captured_ns=captured_ns,
            processed_ns=processed_ns,
            landmarks=pose.landmarks,
            mask=pose.landmark_missing_mask,
            pose_count=pose_count,
            quality_state=QualityState.VALID,
            processing_state=ProcessingState.PROCESSED,
            failure_code=None,
        )
        if observation.result_digest != observation.golden_expected_output_digest:
            return self._emit(
                self._failure(
                    fixture,
                    definition,
                    TechnicalFailureCode.MANIFEST_VALIDATION_FAILED,
                    captured_ns=captured_ns,
                    processed_ns=processed_ns,
                )
            )
        return self._emit(observation)

    def _definition_for(self, fixture: FixtureInput) -> FixtureDefinition:
        if not isinstance(fixture, FixtureInput):
            raise ValueError("fixture must be a FixtureInput")
        definition = self._definitions.get((fixture.fixture_id, fixture.fixture_version))
        if definition is None:
            raise ValueError("fixture is not allowlisted")
        return definition

    def _validate_input_identity(
        self, fixture: FixtureInput, definition: FixtureDefinition
    ) -> None:
        if not isinstance(fixture.technical_input_kind, TechnicalInputKind):
            raise ValueError("technical input kind is schema-incompatible")
        if fixture.technical_input_kind is TechnicalInputKind.NO_HUMAN_DEVICE_SCENE:
            return
        if fixture.technical_input_kind not in _ACCEPTED_INPUT_KINDS:
            raise ValueError("technical input kind is not allowed in S1")
        if fixture.run_id not in self._allowed_run_ids or not _is_opaque_identifier(fixture.run_id):
            raise ValueError("run_id is not allowlisted")
        if (
            fixture.technical_input_kind is not definition.technical_input_kind
            or fixture.preprocessing_id != definition.preprocessing_id
            or _input_hash(fixture) != definition.fixture_input_hash
        ):
            raise ValueError("fixture identity is schema-incompatible")

    def _frame_seq_not_increasing(self, fixture: FixtureInput) -> bool:
        previous = self._last_frame_seq.get(fixture.run_id)
        return previous is not None and fixture.frame_seq <= previous

    def _capture_timing_failure(
        self, fixture: FixtureInput, captured_ns: int
    ) -> TechnicalFailureCode | None:
        if captured_ns < 0:
            return TechnicalFailureCode.SCHEMA_INCOMPATIBLE
        previous = self._last_captured_ns.get(fixture.run_id)
        if previous is None:
            return None
        if captured_ns < previous:
            return TechnicalFailureCode.CLOCK_REGRESSION
        if captured_ns == previous:
            return TechnicalFailureCode.FRAME_STALLED
        return None

    def _processing_timing_failure(
        self, fixture: FixtureInput, captured_ns: int, processed_ns: int
    ) -> TechnicalFailureCode | None:
        if processed_ns < 0 or processed_ns < captured_ns:
            return TechnicalFailureCode.CLOCK_REGRESSION
        previous = self._last_processed_ns.get(fixture.run_id)
        if previous is not None and processed_ns < previous:
            return TechnicalFailureCode.CLOCK_REGRESSION
        return None

    def _failure(
        self,
        fixture: FixtureInput,
        definition: FixtureDefinition,
        failure_code: TechnicalFailureCode,
        *,
        captured_ns: int = 0,
        processed_ns: int | None = None,
    ) -> TechnicalObservation:
        return self._observation(
            fixture,
            definition,
            captured_ns=captured_ns,
            processed_ns=processed_ns,
            landmarks=(),
            mask=((True,) * 33, (True,) * 33),
            pose_count=None,
            quality_state=QualityState.FAILED,
            processing_state=ProcessingState.FAILED,
            failure_code=failure_code,
        )

    def _observation(
        self,
        fixture: FixtureInput,
        definition: FixtureDefinition,
        *,
        captured_ns: int,
        processed_ns: int | None,
        landmarks: tuple[tuple[Landmark, ...], ...],
        mask: tuple[tuple[bool, ...], tuple[bool, ...]],
        pose_count: int | None,
        quality_state: QualityState,
        processing_state: ProcessingState,
        failure_code: TechnicalFailureCode | None,
    ) -> TechnicalObservation:
        latency_ms = (
            None
            if processed_ns is None or processed_ns < captured_ns
            else (processed_ns - captured_ns) // 1_000_000
        )
        provisional = TechnicalObservation(
            schema_version=SCHEMA_VERSION,
            technical_input_kind=fixture.technical_input_kind,
            fixture_id=fixture.fixture_id,
            fixture_version=fixture.fixture_version,
            run_id=fixture.run_id,
            frame_seq=fixture.frame_seq,
            captured_monotonic_ns=captured_ns,
            processed_monotonic_ns=processed_ns,
            pose_engine_task_hash=self._pose_engine_task_hash,
            preprocessing_id=fixture.preprocessing_id,
            landmark_topology_version=LANDMARK_TOPOLOGY_VERSION,
            landmarks=landmarks,
            landmark_missing_mask=mask,
            pose_count=pose_count,
            quality_state=quality_state,
            processing_state=processing_state,
            failure_code=failure_code,
            latency_ms=latency_ms,
            fixture_input_hash=definition.fixture_input_hash,
            golden_expected_output_digest=definition.golden_expected_output_digest,
            result_digest="",
        )
        return provisional.with_result_digest(provisional.recompute_result_digest())

    def _emit(self, observation: TechnicalObservation) -> TechnicalObservation:
        self._sink.observe(observation)
        return observation


def _validate_pose_result(pose: PoseResult) -> TechnicalFailureCode | None:
    if pose.landmark_topology_version != LANDMARK_TOPOLOGY_VERSION:
        return TechnicalFailureCode.POSE_OUTPUT_INVALID
    if not isinstance(pose.quality_state, QualityState):
        return TechnicalFailureCode.SCHEMA_INCOMPATIBLE
    if len(pose.landmarks) > 2 or len(pose.ordered_landmark_indices) != len(pose.landmarks):
        return TechnicalFailureCode.POSE_OUTPUT_INVALID
    if len(pose.landmark_missing_mask) != 2 or any(
        len(row) != 33 for row in pose.landmark_missing_mask
    ):
        return TechnicalFailureCode.POSE_OUTPUT_INVALID
    if any(type(value) is not bool for row in pose.landmark_missing_mask for value in row):
        return TechnicalFailureCode.POSE_OUTPUT_INVALID
    if pose.reported_pose_count is not None and pose.reported_pose_count != len(pose.landmarks):
        return TechnicalFailureCode.POSE_OUTPUT_INVALID
    for pose_index, landmarks in enumerate(pose.landmarks):
        if len(landmarks) != 33 or pose.ordered_landmark_indices[pose_index] != tuple(range(33)):
            return TechnicalFailureCode.POSE_OUTPUT_INVALID
        if any(pose.landmark_missing_mask[pose_index]):
            return TechnicalFailureCode.POSE_OUTPUT_INVALID
        if not all(_landmark_is_valid(landmark) for landmark in landmarks):
            return TechnicalFailureCode.POSE_OUTPUT_INVALID
    for missing_row in pose.landmark_missing_mask[len(pose.landmarks) :]:
        if not all(missing_row):
            return TechnicalFailureCode.POSE_OUTPUT_INVALID
    return None


def _landmark_is_valid(landmark: Landmark) -> bool:
    return (
        isinstance(landmark, Landmark)
        and all(
            math.isfinite(value)
            for value in (landmark.x, landmark.y, landmark.z, landmark.visibility)
        )
        and 0.0 <= landmark.visibility <= 1.0
    )


def _definition_is_valid(definition: FixtureDefinition) -> bool:
    return (
        _is_opaque_identifier(definition.fixture_id)
        and _is_opaque_identifier(definition.fixture_version)
        and definition.technical_input_kind in _DEFINED_INPUT_KINDS
        and _is_opaque_identifier(definition.preprocessing_id)
        and _is_sha256(definition.fixture_input_hash)
        and _is_sha256(definition.golden_expected_output_digest)
    )


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


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_opaque_identifier(value: str) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and value[0].isalnum()
        and all(character.isalnum() or character in "._-" for character in value)
    )
