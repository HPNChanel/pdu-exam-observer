from __future__ import annotations

import numpy as np
import pytest

from pdu_exam_observer.showcase.temporal_rules import (
    RulePolicy,
    orientation_proxy_degrees,
)
from research.training.showcase.v3.dataset import RawRuleFrame
from research.training.showcase.v3.pipeline import Corpus, _rule_events_from_raw
from research.training.showcase.v3.splits import OuterFold


def _pose() -> list[dict[str, float]]:
    pose = [{"x": 0.0, "y": 0.0, "z": 0.0, "visibility": 1.0} for _ in range(33)]
    pose[0].update(x=0.5, y=0.6)
    pose[11].update(x=0.4, y=0.3)
    pose[12].update(x=0.6, y=0.3)
    pose[23].update(x=0.45, y=0.6)
    pose[24].update(x=0.55, y=0.6)
    return pose


def _protocol() -> dict[str, object]:
    return {
        "status": "FROZEN",
        "protocol_version": "test-v1",
        "policy_selection_source": "PILOT",
        "event_policy": {
            "head_down_start_degrees": 40.0,
            "head_down_end_degrees": 30.0,
            "side_look_start_degrees": 30.0,
            "side_look_end_degrees": 20.0,
            "persistence_ms": 100,
            "presence_persistence_ms": 100,
            "release_ms": 50,
            "merge_gap_ms": 50,
            "cooldown_ms": 50,
            "stride_ms": 100,
        },
    }


def test_orientation_proxy_uses_torso_scale_and_is_not_pitch_claim() -> None:
    down, side = orientation_proxy_degrees(_pose())

    assert down == pytest.approx(45.0)
    assert side == pytest.approx(0.0)


def test_protocol_mapping_has_no_implicit_temporal_defaults() -> None:
    policy = RulePolicy.from_protocol_freeze(_protocol())

    assert policy.motion_duration_ms == 100
    assert policy.presence_duration_ms == 100
    assert policy.release_ms == 50
    assert policy.selection_source == "PILOT"


def test_protocol_mapping_rejects_fractional_milliseconds() -> None:
    protocol = _protocol()
    protocol["event_policy"]["persistence_ms"] = 100.5

    with pytest.raises(ValueError, match="VALUE_INVALID"):
        RulePolicy.from_protocol_freeze(protocol)


def test_offline_rules_use_raw_frames_even_without_supervised_windows() -> None:
    frames = tuple(
        RawRuleFrame(
            "S1",
            "P03",
            "REAL",
            "CONFIRMATORY",
            timestamp,
            1,
            45.0,
            0.0,
            True,
        )
        for timestamp in (0, 100, 200)
    )
    corpus = Corpus(
        tensors=np.empty((0, 5, 90, 33), dtype=np.float32),
        labels=np.empty((0,), dtype=np.int64),
        context=np.empty((0, 6), dtype=np.float32),
        participants=(),
        source_kinds=(),
        sample_ids=(),
        dataset_manifest_sha256="0" * 64,
        protocol_version="test-v1",
        session_duration_ms={"S1": 201},
        session_participants={"S1": "P03"},
        raw_rule_frames=frames,
    )

    events = _rule_events_from_raw(corpus, OuterFold(0, (), (), ("P03",)), _protocol())

    assert len(events) == 1
    assert events[0].label == "PROLONGED_HEAD_DOWN"
    assert events[0].eligible_at_ms == 100
