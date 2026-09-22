"""Continuous-session, participant-aware event evaluation.

The denominator is complete recorded session time. It is never reconstructed
from selected six-second training windows.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

ALERT_LABELS = frozenset({"PROLONGED_HEAD_DOWN", "PROLONGED_SIDE_LOOK"})
CONFIGURATION_NAMES = (
    "rules",
    "camera_only",
    "context_plus_abstention",
)
TIOU_THRESHOLDS = tuple(round(value / 100, 2) for value in range(50, 100, 5))


@dataclass(frozen=True, slots=True)
class Session:
    session_id: str
    participant_id: str
    duration_ms: int
    source_kind: str
    cohort: str = "CONFIRMATORY"

    def __post_init__(self) -> None:
        if not self.session_id or not self.participant_id or self.duration_ms <= 0:
            raise ValueError("session identifiers and positive duration are required")


@dataclass(frozen=True, slots=True)
class Event:
    session_id: str
    participant_id: str
    label: str
    start_ms: int
    end_ms: int
    eligible_at_ms: int | None = None

    def __post_init__(self) -> None:
        if (
            not self.session_id
            or not self.participant_id
            or self.start_ms < 0
            or self.end_ms <= self.start_ms
            or (self.eligible_at_ms is not None and self.eligible_at_ms < self.start_ms)
        ):
            raise ValueError("event interval is invalid")


@dataclass(frozen=True, slots=True)
class EventMatch:
    truth_index: int
    prediction_index: int
    tiou: float


@dataclass(frozen=True, slots=True)
class MatchResult:
    matches: tuple[EventMatch, ...]
    unmatched_truth_indices: tuple[int, ...]
    unmatched_prediction_indices: tuple[int, ...]


@dataclass(slots=True)
class _FlowEdge:
    destination: int
    reverse_index: int
    capacity: int
    cost: float


def _add_flow_edge(
    graph: list[list[_FlowEdge]], source: int, destination: int, cost: float
) -> int:
    forward_index = len(graph[source])
    reverse_index = len(graph[destination])
    graph[source].append(_FlowEdge(destination, reverse_index, 1, cost))
    graph[destination].append(_FlowEdge(source, forward_index, 0, -cost))
    return forward_index


def temporal_iou(left: Event, right: Event) -> float:
    if left.session_id != right.session_id:
        return 0.0
    overlap = max(0, min(left.end_ms, right.end_ms) - max(left.start_ms, right.start_ms))
    union = max(left.end_ms, right.end_ms) - min(left.start_ms, right.start_ms)
    return overlap / union


def match_events(
    truth: Sequence[Event], predictions: Sequence[Event], *, tiou_threshold: float
) -> MatchResult:
    """Find maximum cardinality first, then maximize total tIoU."""

    if not 0.0 < tiou_threshold <= 1.0:
        raise ValueError("tIoU threshold must be within (0, 1]")
    candidates: list[tuple[float, int, int]] = []
    for truth_index, expected in enumerate(truth):
        for prediction_index, predicted in enumerate(predictions):
            if (
                expected.label != predicted.label
                or expected.participant_id != predicted.participant_id
            ):
                continue
            score = temporal_iou(expected, predicted)
            if score >= tiou_threshold:
                candidates.append((score, truth_index, prediction_index))
    source = 0
    truth_offset = 1
    prediction_offset = truth_offset + len(truth)
    sink = prediction_offset + len(predictions)
    graph: list[list[_FlowEdge]] = [[] for _ in range(sink + 1)]
    for truth_index in range(len(truth)):
        _add_flow_edge(graph, source, truth_offset + truth_index, 0.0)
    for prediction_index in range(len(predictions)):
        _add_flow_edge(graph, prediction_offset + prediction_index, sink, 0.0)
    candidate_edges: list[tuple[float, int, int, int]] = []
    for score, truth_index, prediction_index in sorted(
        candidates, key=lambda value: (value[1], value[2])
    ):
        node = truth_offset + truth_index
        edge_index = _add_flow_edge(
            graph,
            node,
            prediction_offset + prediction_index,
            -score,
        )
        candidate_edges.append((score, truth_index, prediction_index, edge_index))
    while True:
        distances = [float("inf")] * len(graph)
        previous: list[tuple[int, int] | None] = [None] * len(graph)
        distances[source] = 0.0
        for _ in range(len(graph) - 1):
            changed = False
            for node, edges in enumerate(graph):
                if not math.isfinite(distances[node]):
                    continue
                for edge_index, edge in enumerate(edges):
                    if edge.capacity == 0:
                        continue
                    candidate_distance = distances[node] + edge.cost
                    if candidate_distance < distances[edge.destination] - 1e-15:
                        distances[edge.destination] = candidate_distance
                        previous[edge.destination] = (node, edge_index)
                        changed = True
            if not changed:
                break
        if previous[sink] is None:
            break
        node = sink
        while node != source:
            parent = previous[node]
            if parent is None:
                raise AssertionError("augmenting path is incomplete")
            parent_node, edge_index = parent
            edge = graph[parent_node][edge_index]
            edge.capacity = 0
            graph[node][edge.reverse_index].capacity = 1
            node = parent_node
    matches = [
        EventMatch(truth_index, prediction_index, score)
        for score, truth_index, prediction_index, edge_index in candidate_edges
        if graph[truth_offset + truth_index][edge_index].capacity == 0
    ]
    matches.sort(key=lambda value: (value.truth_index, value.prediction_index))
    used_truth = {match.truth_index for match in matches}
    used_predictions = {match.prediction_index for match in matches}
    return MatchResult(
        matches=tuple(matches),
        unmatched_truth_indices=tuple(
            index for index in range(len(truth)) if index not in used_truth
        ),
        unmatched_prediction_indices=tuple(
            index for index in range(len(predictions)) if index not in used_predictions
        ),
    )


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _event_metrics(
    sessions: Sequence[Session],
    truth: Sequence[Event],
    predictions: Sequence[Event],
    threshold: float,
) -> dict[str, object]:
    result = match_events(truth, predictions, tiou_threshold=threshold)
    total_hours = sum(session.duration_ms for session in sessions) / 3_600_000
    false_alert_indices = tuple(
        index
        for index in result.unmatched_prediction_indices
        if predictions[index].label in ALERT_LABELS
    )
    latencies: list[int] = []
    for match in result.matches:
        truth_event = truth[match.truth_index]
        if truth_event.label not in ALERT_LABELS:
            continue
        eligible_at_ms = truth_event.eligible_at_ms
        if eligible_at_ms is None:
            eligible_at_ms = truth_event.start_ms
        latencies.append(predictions[match.prediction_index].start_ms - eligible_at_ms)
    labels = sorted({event.label for event in truth} | {event.label for event in predictions})
    per_class: dict[str, dict[str, float | int | None]] = {}
    for label in labels:
        true_count = sum(event.label == label for event in truth)
        predicted_count = sum(event.label == label for event in predictions)
        matched_count = sum(truth[match.truth_index].label == label for match in result.matches)
        precision = _safe_ratio(matched_count, predicted_count)
        recall = _safe_ratio(matched_count, true_count)
        f1 = (
            None
            if precision is None or recall is None or precision + recall == 0
            else 2 * precision * recall / (precision + recall)
        )
        per_class[label] = {
            "true_events": true_count,
            "predicted_events": predicted_count,
            "matched_events": matched_count,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "matched_event_count": len(result.matches),
        "false_negative_count": len(result.unmatched_truth_indices),
        "false_alert_count": len(false_alert_indices),
        "false_alerts_per_session_hour": len(false_alert_indices) / total_hours,
        "per_class": per_class,
        "eligible_onset_to_alert_latency_ms": {
            "count": len(latencies),
            "mean": None if not latencies else float(np.mean(latencies)),
            "median": None if not latencies else float(np.median(latencies)),
        },
    }


def _participant_bootstrap(
    sessions: Sequence[Session],
    truth: Sequence[Event],
    configurations: Mapping[str, Sequence[Event]],
    *,
    seed: int,
    tiou_threshold: float,
    draws: int = 1_000,
) -> dict[str, object]:
    participants = tuple(sorted({session.participant_id for session in sessions}))
    rng = np.random.default_rng(seed)
    estimates: dict[str, list[float]] = {name: [] for name in CONFIGURATION_NAMES}
    for _ in range(draws):
        selected = tuple(rng.choice(participants, size=len(participants), replace=True))
        sampled_hours = (
            sum(
                sum(
                    session.duration_ms
                    for session in sessions
                    if session.participant_id == participant
                )
                for participant in selected
            )
            / 3_600_000
        )
        for name in CONFIGURATION_NAMES:
            false_alerts = 0
            for participant in selected:
                participant_truth = tuple(
                    event for event in truth if event.participant_id == participant
                )
                participant_predictions = tuple(
                    event for event in configurations[name] if event.participant_id == participant
                )
                matches = match_events(
                    participant_truth,
                    participant_predictions,
                    tiou_threshold=tiou_threshold,
                )
                false_alerts += sum(
                    participant_predictions[index].label in ALERT_LABELS
                    for index in matches.unmatched_prediction_indices
                )
            estimates[name].append(false_alerts / sampled_hours)
    return {
        "method": "participant_cluster_bootstrap",
        "seed": seed,
        "draws": draws,
        "unit": "participant",
        "false_alerts_per_session_hour_95_interval": {
            name: [
                float(np.quantile(values, 0.025)),
                float(np.quantile(values, 0.975)),
            ]
            for name, values in estimates.items()
        },
    }


def evaluate_configurations(
    sessions: Sequence[Session],
    truth: Sequence[Event],
    configurations: Mapping[str, Sequence[Event]],
    *,
    seed: int = 20260908,
    primary_tiou: float | None = None,
) -> dict[str, object]:
    """Report the fixed three configurations over the pre-freeze tIoU sweep."""

    if not sessions or any(
        session.cohort != "CONFIRMATORY" or session.source_kind != "REAL" for session in sessions
    ):
        raise ValueError("evaluation requires confirmatory REAL continuous sessions")
    if set(configurations) != set(CONFIGURATION_NAMES):
        raise ValueError("the three protocol configurations are required exactly")
    if primary_tiou is not None and primary_tiou not in TIOU_THRESHOLDS:
        raise ValueError("primary_tiou must come from the declared sweep")
    session_lookup = {session.session_id: session for session in sessions}
    if len(session_lookup) != len(sessions):
        raise ValueError("session IDs must be unique")
    for event in (*truth, *(item for values in configurations.values() for item in values)):
        session = session_lookup.get(event.session_id)
        if (
            session is None
            or event.participant_id != session.participant_id
            or event.end_ms > session.duration_ms
        ):
            raise ValueError("event is outside its continuous session")
    return {
        "schema_version": 1,
        "claim_status": "UNVERIFIED_RESEARCH_RESULT",
        "tiou_thresholds": list(TIOU_THRESHOLDS),
        "primary_tiou": primary_tiou,
        "actual_session_hours": sum(session.duration_ms for session in sessions) / 3_600_000,
        "configurations": {
            name: {
                "by_tiou": {
                    f"{threshold:.2f}": _event_metrics(
                        sessions, truth, configurations[name], threshold
                    )
                    for threshold in TIOU_THRESHOLDS
                }
            }
            for name in CONFIGURATION_NAMES
        },
        "participant_uncertainty": _participant_bootstrap(
            sessions,
            truth,
            configurations,
            seed=seed,
            tiou_threshold=primary_tiou if primary_tiou is not None else 0.5,
        ),
    }
