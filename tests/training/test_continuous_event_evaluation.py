from __future__ import annotations

import pytest

from research.training.showcase.v3.evaluation import (
    Event,
    Session,
    evaluate_configurations,
    match_events,
)


def test_matching_is_class_aware_one_to_one_and_uses_tiou_sweep() -> None:
    truth = (Event("S1", "P03", "PROLONGED_HEAD_DOWN", 10_000, 20_000, 11_500),)
    predictions = (
        Event("S1", "P03", "PROLONGED_HEAD_DOWN", 10_000, 20_000),
        Event("S1", "P03", "PROLONGED_HEAD_DOWN", 10_500, 19_500),
        Event("S1", "P03", "PROLONGED_SIDE_LOOK", 10_000, 20_000),
    )

    result = match_events(truth, predictions, tiou_threshold=0.5)

    assert len(result.matches) == 1
    assert result.matches[0].truth_index == 0
    assert result.unmatched_prediction_indices == (1, 2)


def test_matching_maximizes_cardinality_before_tiou_tie_break() -> None:
    truth = (
        Event("S1", "P03", "PROLONGED_HEAD_DOWN", 0, 2),
        Event("S1", "P03", "PROLONGED_HEAD_DOWN", 2, 4),
    )
    predictions = (
        Event("S1", "P03", "PROLONGED_HEAD_DOWN", 0, 4),
        Event("S1", "P03", "PROLONGED_HEAD_DOWN", 0, 1),
    )

    result = match_events(truth, predictions, tiou_threshold=0.5)

    assert {(match.truth_index, match.prediction_index) for match in result.matches} == {
        (0, 1),
        (1, 0),
    }


def test_false_alert_rate_uses_full_continuous_session_hours_and_latency() -> None:
    sessions = (
        Session("S1", "P03", duration_ms=120_000, source_kind="REAL"),
        Session("S2", "P04", duration_ms=60_000, source_kind="REAL"),
    )
    truth = (Event("S1", "P03", "PROLONGED_HEAD_DOWN", 10_000, 20_000, 11_500),)
    configurations = {
        "rules": (
            Event("S1", "P03", "PROLONGED_HEAD_DOWN", 12_000, 20_000),
            Event("S2", "P04", "PROLONGED_SIDE_LOOK", 20_000, 25_000),
        ),
        "camera_only": (),
        "context_plus_abstention": (Event("S1", "P03", "PROLONGED_HEAD_DOWN", 11_500, 20_000),),
    }

    report = evaluate_configurations(sessions, truth, configurations, seed=7)

    assert report["tiou_thresholds"] == pytest.approx(
        [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    )
    assert report["actual_session_hours"] == pytest.approx(0.05)
    assert set(report["configurations"]) == {
        "rules",
        "camera_only",
        "context_plus_abstention",
    }
    primary = report["configurations"]["rules"]["by_tiou"]["0.50"]
    assert primary["false_alert_count"] == 1
    assert primary["false_alerts_per_session_hour"] == pytest.approx(20.0)
    assert primary["eligible_onset_to_alert_latency_ms"]["mean"] == pytest.approx(500.0)
    assert report["participant_uncertainty"]["method"] == "participant_cluster_bootstrap"


def test_pilot_or_non_real_session_cannot_enter_confirmatory_report() -> None:
    with pytest.raises(ValueError, match="confirmatory REAL"):
        evaluate_configurations(
            (Session("pilot", "P01", 60_000, source_kind="REAL", cohort="PILOT"),),
            (),
            {"rules": (), "camera_only": (), "context_plus_abstention": ()},
        )
