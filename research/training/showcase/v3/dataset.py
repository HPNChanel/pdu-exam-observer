"""Strict loader for the runtime's allowlisted frame export.

`UNCERTAIN`, presence states, and unusable quality remain in audit counts but
never become ST-GCN supervised targets.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pdu_exam_observer.showcase.export_contract import validate_research_export
from pdu_exam_observer.showcase.model_runtime import CONTEXT_ORDER, aggregate_context_rows
from pdu_exam_observer.showcase.preprocessing import resample_pose_window
from pdu_exam_observer.showcase.temporal_rules import orientation_proxy_degrees

CLASS_ORDER = (
    "NORMAL",
    "BENIGN_CONFOUNDER",
    "PROLONGED_HEAD_DOWN",
    "PROLONGED_SIDE_LOOK",
)
ALL_LABELS = frozenset((*CLASS_ORDER, "NO_PERSON", "MULTIPLE_PEOPLE", "UNCERTAIN"))
RECORD_FIELDS = frozenset(
    {
        "export_id",
        "manifest_sha256",
        "schema_version",
        "record_count",
        "sample_id",
        "participant_pseudonym",
        "session_pseudonym",
        "source_kind",
        "parent_provenance_id",
        "pose",
        "label",
        "quality",
        "focus",
        "timing",
    }
)
EXPORT_FILES = frozenset({"manifest.json", "records.jsonl"})


@dataclass(frozen=True, slots=True)
class LoadedRuntimeExport:
    tensors: NDArray[np.float32]
    labels: NDArray[np.int64]
    context: NDArray[np.float32]
    participants: tuple[str, ...]
    sessions: tuple[str, ...]
    source_kinds: tuple[str, ...]
    phases: tuple[str, ...]
    sample_ids: tuple[str, ...]
    window_start_ms: tuple[int, ...]
    window_end_ms: tuple[int, ...]
    parent_provenance_ids: tuple[tuple[str, ...], ...]
    source_record_ids: tuple[tuple[str, ...], ...]
    manifest_sha256: str
    audit_label_counts: dict[str, int]
    session_duration_ms: dict[str, int]
    session_participants: dict[str, str]
    session_source_kinds: dict[str, str]
    session_phases: dict[str, str]
    record_provenance: dict[str, tuple[str, str, str]]
    raw_rule_frames: tuple[RawRuleFrame, ...]
    reviewed_events: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class RawRuleFrame:
    session_id: str
    participant_id: str
    source_kind: str
    phase: str
    timestamp_ms: int
    pose_count: int
    down_score: float
    side_score: float
    quality_ok: bool


def _read_export(source: bytes | Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    validated = validate_research_export(source)
    return validated.manifest, validated.records


def _pose_rows(record: dict[str, Any]) -> tuple[tuple[dict[str, Any], ...], ...]:
    pose = record.get("pose")
    if (
        not isinstance(pose, dict)
        or pose.get("topology") not in {"mediapipe-33", "mediapipe-33-v1"}
        or not isinstance(pose.get("pose_count"), int)
        or not 0 <= pose["pose_count"] <= 2
        or not isinstance(pose.get("landmarks"), list)
        or len(pose["landmarks"]) != pose["pose_count"]
    ):
        raise ValueError("MediaPipe-33 pose collection is invalid")
    poses: list[tuple[dict[str, Any], ...]] = []
    for candidate in pose["landmarks"]:
        if not isinstance(candidate, list) or len(candidate) != 33:
            raise ValueError("MediaPipe-33 pose collection is invalid")
        normalized: list[dict[str, Any]] = []
        for landmark in candidate:
            if not isinstance(landmark, dict) or set(landmark) != {
                "x",
                "y",
                "z",
                "visibility",
            }:
                raise ValueError("landmark record is incompatible")
            row = np.asarray(
                [landmark["x"], landmark["y"], landmark["z"], landmark["visibility"]],
                dtype=np.float32,
            )
            if not np.isfinite(row).all() or not 0 <= row[3] <= 1:
                raise ValueError("landmark value is invalid")
            normalized.append(landmark)
        poses.append(tuple(normalized))
    return tuple(poses)


def _landmarks(record: dict[str, Any]) -> tuple[NDArray[np.float32], NDArray[np.bool_]]:
    poses = _pose_rows(record)
    if len(poses) != 1:
        raise ValueError("single-pose MediaPipe-33 landmarks are required")
    values: NDArray[np.float32] = np.empty((33, 4), dtype=np.float32)
    present: NDArray[np.bool_] = np.ones(33, dtype=bool)
    for index, landmark in enumerate(poses[0]):
        row = np.asarray(
            [landmark["x"], landmark["y"], landmark["z"], landmark["visibility"]],
            dtype=np.float32,
        )
        if not np.isfinite(row).all() or not 0 <= row[3] <= 1:
            raise ValueError("landmark value is invalid")
        values[index] = row
        present[index] = bool(row[3] > 0)
    return values, present


def _context(records: tuple[dict[str, Any], ...]) -> NDArray[np.float32]:
    rows: list[dict[str, float]] = []
    for record in records:
        quality = record.get("quality")
        focus = record.get("focus")
        if (
            not isinstance(quality, dict)
            or not isinstance(focus, dict)
            or any(
                key not in quality
                for key in ("blur", "exposure", "visibility_mean", "frame_gap_ratio")
            )
            or "signal_age_ms" not in focus
            or focus.get("state") not in {"EXAM_FOCUSED", "EXAM_NOT_FOCUSED", "FOCUS_UNKNOWN"}
            or focus.get("contaminated_by_operator") not in {True, False}
        ):
            raise ValueError("quality/focus context is incomplete")
        if focus["contaminated_by_operator"]:
            raise ValueError("operator-contaminated focus cannot enter model context")
        row = {
            "visibility_mean": float(quality["visibility_mean"]),
            "blur_score": float(quality["blur"]),
            "exposure_score": float(quality["exposure"]),
            "frame_gap_ratio": float(quality["frame_gap_ratio"]),
            "focus_fraction": 1.0 if focus["state"] == "EXAM_FOCUSED" else 0.0,
            "scaled_focus_signal_age": min(float(focus["signal_age_ms"]) / 6_000.0, 1.0),
        }
        if not np.isfinite(list(row.values())).all() or row["scaled_focus_signal_age"] < 0:
            raise ValueError("quality/focus context is non-finite")
        rows.append(row)
    aggregate = aggregate_context_rows(rows)
    return np.asarray(
        [aggregate[name] for name in CONTEXT_ORDER],
        dtype=np.float32,
    )


def _validate_record(record: dict[str, Any], manifest: dict[str, Any]) -> None:
    if set(record) != RECORD_FIELDS:
        raise ValueError("record must use the exact research export envelope")
    if (
        record.get("schema_version") != 1
        or record.get("export_id") != manifest.get("export_id")
        or record.get("manifest_sha256") != manifest.get("manifest_sha256")
        or record.get("record_count") != manifest.get("record_count")
        or record.get("label") not in ALL_LABELS
        or record.get("source_kind") not in {"REAL", "AI_RENDERED", "AUGMENTED"}
    ):
        raise ValueError("record envelope is incompatible")
    for key in ("sample_id", "participant_pseudonym", "session_pseudonym"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError("record pseudonymous identifier is invalid")
    if record["source_kind"] == "AUGMENTED" and not record.get("parent_provenance_id"):
        raise ValueError("augmented record requires parent provenance")


def load_runtime_export(source: bytes | Path) -> LoadedRuntimeExport:
    manifest, records = _read_export(source)
    for record in records:
        _validate_record(record, manifest)
    sample_ids = [str(record["sample_id"]) for record in records]
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("record sample IDs must be unique")
    audit_counts = Counter(str(record["label"]) for record in records)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["session_pseudonym"])].append(record)
    tensors: list[NDArray[np.float32]] = []
    labels: list[int] = []
    contexts: list[NDArray[np.float32]] = []
    participants: list[str] = []
    sessions: list[str] = []
    sources: list[str] = []
    window_ids: list[str] = []
    parent_ids: list[tuple[str, ...]] = []
    source_record_ids: list[tuple[str, ...]] = []
    phases: list[str] = []
    window_starts: list[int] = []
    window_ends: list[int] = []
    session_durations: dict[str, int] = {}
    session_participants: dict[str, str] = {}
    session_sources: dict[str, str] = {}
    session_phases: dict[str, str] = {}
    record_provenance: dict[str, tuple[str, str, str]] = {}
    raw_rule_frames: list[RawRuleFrame] = []
    reviewed_events: list[dict[str, object]] = []
    for session_id, session_records in grouped.items():
        session_records.sort(key=lambda record: int(record["timing"].get("captured_ns", -1)))
        participant_set = {str(record["participant_pseudonym"]) for record in session_records}
        source_set = {str(record["source_kind"]) for record in session_records}
        phase_set = {str(record["timing"].get("phase")) for record in session_records}
        if (
            len(participant_set) != 1
            or len(source_set) != 1
            or len(phase_set) != 1
            or not phase_set <= {"PILOT", "CONFIRMATORY"}
        ):
            raise ValueError("session participant/source/phase provenance changed")
        participant = next(iter(participant_set))
        session_source = next(iter(source_set))
        phase = next(iter(phase_set))
        session_participants[session_id] = participant
        session_sources[session_id] = session_source
        session_phases[session_id] = phase
        offsets = [record["timing"].get("offset_ms") for record in session_records]
        if any(not isinstance(value, int) or value < 0 for value in offsets):
            raise ValueError("session timing is invalid")
        if any(right <= left for left, right in zip(offsets, offsets[1:], strict=False)):
            raise ValueError("session offsets must increase strictly")
        session_durations[session_id] = max(int(value) for value in offsets) + 1
        for record in session_records:
            sample_id = str(record["sample_id"])
            record_provenance[sample_id] = (participant, session_source, phase)
            poses = _pose_rows(record)
            down_score = 0.0
            side_score = 0.0
            quality = record.get("quality")
            quality_ok = isinstance(quality, dict) and quality.get("state") == "SUFFICIENT"
            if len(poses) == 1:
                try:
                    down_score, side_score = orientation_proxy_degrees(poses[0])
                except ValueError:
                    quality_ok = False
            raw_rule_frames.append(
                RawRuleFrame(
                    session_id=session_id,
                    participant_id=participant,
                    source_kind=session_source,
                    phase=phase,
                    timestamp_ms=int(record["timing"]["offset_ms"]),
                    pose_count=len(poses),
                    down_score=down_score,
                    side_score=side_score,
                    quality_ok=quality_ok,
                )
            )
        event_run_start = 0
        while event_run_start < len(session_records):
            event_label = str(session_records[event_run_start]["label"])
            event_run_end = event_run_start + 1
            while (
                event_run_end < len(session_records)
                and session_records[event_run_end]["label"] == event_label
            ):
                event_run_end += 1
            if event_label in {"PROLONGED_HEAD_DOWN", "PROLONGED_SIDE_LOOK"}:
                event_offsets = [
                    int(record["timing"]["offset_ms"])
                    for record in session_records[event_run_start:event_run_end]
                ]
                reviewed_events.append(
                    {
                        "session_id": session_id,
                        "participant_id": next(iter(participant_set)),
                        "label": event_label,
                        "start_ms": event_offsets[0],
                        "end_ms": event_offsets[-1] + 67,
                    }
                )
            event_run_start = event_run_end
        run_start = 0
        while run_start < len(session_records):
            label = session_records[run_start]["label"]
            run_end = run_start + 1
            while run_end < len(session_records) and session_records[run_end]["label"] == label:
                run_end += 1
            if label in CLASS_ORDER:
                run = tuple(session_records[run_start:run_end])
                start = 0
                while start + 89 < len(run):
                    candidate = run[start:]
                    landmark_rows: list[NDArray[np.float32]] = []
                    mask_rows: list[NDArray[np.bool_]] = []
                    timestamps: list[int] = []
                    for record in candidate:
                        landmark, mask = _landmarks(record)
                        landmark_rows.append(landmark)
                        mask_rows.append(mask)
                        timing = record["timing"]
                        captured_ns = timing.get("captured_ns")
                        if not isinstance(captured_ns, int):
                            raise ValueError("captured_ns is required")
                        timestamps.append(captured_ns)
                    try:
                        prepared = resample_pose_window(
                            np.asarray(timestamps, dtype=np.int64),
                            np.asarray(landmark_rows, dtype=np.float32),
                            np.asarray(mask_rows, dtype=bool),
                        )
                    except ValueError:
                        break
                    selected_records = candidate[:90]
                    tensors.append(prepared.tensor[0])
                    labels.append(CLASS_ORDER.index(str(label)))
                    contexts.append(_context(selected_records))
                    participants.append(next(iter(participant_set)))
                    sessions.append(session_id)
                    sources.append(next(iter(source_set)))
                    phase_set = {str(record["timing"].get("phase")) for record in selected_records}
                    if len(phase_set) != 1:
                        raise ValueError("window phase changed within one supervised sample")
                    phases.append(next(iter(phase_set)))
                    window_starts.append(int(selected_records[0]["timing"]["offset_ms"]))
                    window_ends.append(window_starts[-1] + 6_000)
                    window_ids.append(
                        hashlib.sha256(f"{session_id}:{timestamps[0]}:{label}".encode()).hexdigest()
                    )
                    parent_ids.append(
                        tuple(
                            str(record["parent_provenance_id"])
                            for record in selected_records
                            if record["parent_provenance_id"] is not None
                        )
                    )
                    source_record_ids.append(
                        tuple(str(record["sample_id"]) for record in selected_records)
                    )
                    start += 15
            run_start = run_end
    tensor_array = (
        np.asarray(tensors, dtype=np.float32)
        if tensors
        else np.empty((0, 5, 90, 33), dtype=np.float32)
    )
    context_array = (
        np.asarray(contexts, dtype=np.float32)
        if contexts
        else np.empty((0, 6), dtype=np.float32)
    )
    return LoadedRuntimeExport(
        tensors=tensor_array,
        labels=np.asarray(labels, dtype=np.int64),
        context=context_array,
        participants=tuple(participants),
        sessions=tuple(sessions),
        source_kinds=tuple(sources),
        phases=tuple(phases),
        sample_ids=tuple(window_ids),
        window_start_ms=tuple(window_starts),
        window_end_ms=tuple(window_ends),
        parent_provenance_ids=tuple(parent_ids),
        source_record_ids=tuple(source_record_ids),
        manifest_sha256=str(manifest["manifest_sha256"]),
        audit_label_counts=dict(audit_counts),
        session_duration_ms=session_durations,
        session_participants=session_participants,
        session_source_kinds=session_sources,
        session_phases=session_phases,
        record_provenance=record_provenance,
        raw_rule_frames=tuple(raw_rule_frames),
        reviewed_events=tuple(reviewed_events),
    )
