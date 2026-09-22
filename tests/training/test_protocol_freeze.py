from __future__ import annotations

import hashlib
import json

import pytest

from research.training.showcase.v3.protocol import validate_protocol_freeze


def _freeze() -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 1,
        "status": "FROZEN",
        "protocol_version": "pdu-confirmatory-v1",
        "frozen_before_outer_test": True,
        "pilot_participants": ["P01", "P02"],
        "confirmatory_participants": [f"P{i:02d}" for i in range(3, 13)],
        "primary_tiou": 0.5,
        "policy_selection_source": "PILOT",
        "event_policy": {
            "head_down_start_degrees": 25.0,
            "head_down_end_degrees": 18.0,
            "side_look_start_degrees": 28.0,
            "side_look_end_degrees": 20.0,
            "persistence_ms": 1500,
            "presence_persistence_ms": 1500,
            "release_ms": 400,
            "cooldown_ms": 750,
            "merge_gap_ms": 500,
            "stride_ms": 1000,
        },
    }
    value["protocol_freeze_sha256"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def test_protocol_freeze_is_self_hashed_and_complete_before_research() -> None:
    freeze = _freeze()

    validated = validate_protocol_freeze(json.dumps(freeze).encode())

    assert validated["primary_tiou"] == 0.5
    assert validated["protocol_freeze_sha256"] == freeze["protocol_freeze_sha256"]


def test_unset_or_post_test_protocol_is_rejected() -> None:
    for update in (
        {"primary_tiou": None},
        {"frozen_before_outer_test": False},
        {"status": "DRAFT"},
    ):
        freeze = _freeze() | update
        unsigned = dict(freeze)
        unsigned.pop("protocol_freeze_sha256", None)
        freeze["protocol_freeze_sha256"] = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with pytest.raises(ValueError):
            validate_protocol_freeze(json.dumps(freeze).encode())
