"""Fail-closed protocol-freeze record used before any research-mode fitting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .evaluation import TIOU_THRESHOLDS

EVENT_POLICY_FIELDS = frozenset(
    {
        "head_down_start_degrees",
        "head_down_end_degrees",
        "side_look_start_degrees",
        "side_look_end_degrees",
        "persistence_ms",
        "presence_persistence_ms",
        "release_ms",
        "cooldown_ms",
        "merge_gap_ms",
        "stride_ms",
    }
)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def validate_protocol_freeze(source: bytes | Path) -> dict[str, Any]:
    if isinstance(source, Path):
        if not source.is_file() or source.is_symlink():
            raise ValueError("protocol freeze must be a trusted regular file")
        payload = source.read_bytes()
    elif isinstance(source, bytes):
        payload = source
    else:
        raise TypeError("protocol freeze must be bytes or Path")
    try:
        value = json.loads(payload.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("protocol freeze JSON is invalid") from error
    if not isinstance(value, dict):
        raise ValueError("protocol freeze must be an object")
    recorded = value.get("protocol_freeze_sha256")
    unsigned = dict(value)
    unsigned.pop("protocol_freeze_sha256", None)
    digest = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    if not isinstance(recorded, str) or recorded != digest:
        raise ValueError("protocol freeze self-hash mismatch")
    if (
        value.get("schema_version") != 1
        or value.get("status") != "FROZEN"
        or value.get("frozen_before_outer_test") is not True
        or value.get("pilot_participants") != ["P01", "P02"]
        or value.get("confirmatory_participants") != [f"P{i:02d}" for i in range(3, 13)]
        or value.get("primary_tiou") not in TIOU_THRESHOLDS
        or value.get("policy_selection_source") not in {"PILOT", "CALIBRATION"}
    ):
        raise ValueError("protocol freeze identity/split/tIoU contract is incomplete")
    protocol_version = value.get("protocol_version")
    if not isinstance(protocol_version, str) or not protocol_version or len(protocol_version) > 128:
        raise ValueError("protocol version is invalid")
    policy = value.get("event_policy")
    if not isinstance(policy, dict) or set(policy) != EVENT_POLICY_FIELDS:
        raise ValueError("frozen event policy is incomplete")
    for field, item in policy.items():
        if isinstance(item, bool) or not isinstance(item, int | float) or float(item) < 0:
            raise ValueError(f"event policy {field} is invalid")
        if field.endswith("_ms") and not isinstance(item, int):
            raise ValueError(f"event policy {field} must be integer milliseconds")
    if (
        float(policy["head_down_end_degrees"]) >= float(policy["head_down_start_degrees"])
        or float(policy["side_look_end_degrees"]) >= float(policy["side_look_start_degrees"])
        or int(policy["persistence_ms"]) <= 0
        or int(policy["presence_persistence_ms"]) <= 0
        or int(policy["stride_ms"]) <= 0
    ):
        raise ValueError("event policy hysteresis/duration is invalid")
    return value
