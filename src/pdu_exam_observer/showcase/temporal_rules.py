"""Shared observable temporal rules for runtime and offline evaluation.

The orientation values are image-plane proxies expressed in degrees. They are
not anatomical pitch or yaw estimates. Keeping the geometry and temporal state
machine here makes the independent-rules baseline executable in both places.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

PROTOCOL_EVENT_POLICY_FIELDS = frozenset(
    {
        "head_down_start_degrees",
        "head_down_end_degrees",
        "side_look_start_degrees",
        "side_look_end_degrees",
        "persistence_ms",
        "presence_persistence_ms",
        "release_ms",
        "merge_gap_ms",
        "cooldown_ms",
        "stride_ms",
    }
)


def _xyz(landmark: Mapping[str, float] | Sequence[float]) -> tuple[float, float, float]:
    try:
        if isinstance(landmark, Mapping):
            values = (float(landmark["x"]), float(landmark["y"]), float(landmark["z"]))
        else:
            values = (float(landmark[0]), float(landmark[1]), float(landmark[2]))
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError("POSE_LANDMARK_INVALID") from error
    if not all(math.isfinite(value) for value in values):
        raise ValueError("POSE_LANDMARK_INVALID")
    return values


def orientation_proxy_degrees(
    pose: Sequence[Mapping[str, float] | Sequence[float]],
) -> tuple[float, float]:
    """Return down and absolute-side image-plane orientation proxies.

    Let ``s`` be the midpoint of shoulders 11/12, ``h`` the midpoint of hips
    23/24, and ``r = ||s-h||_xyz``. The returned values are
    ``degrees(atan2(nose_y-s_y, r))`` and
    ``degrees(atan2(abs(nose_x-s_x), r))``. Image coordinates have positive y
    downward. A degenerate torso is rejected instead of producing a score.
    """

    if len(pose) != 33:
        raise ValueError("POSE_TOPOLOGY_INVALID")
    nose = _xyz(pose[0])
    left_shoulder = _xyz(pose[11])
    right_shoulder = _xyz(pose[12])
    left_hip = _xyz(pose[23])
    right_hip = _xyz(pose[24])
    shoulder = tuple(
        (left + right) / 2.0
        for left, right in zip(left_shoulder, right_shoulder, strict=True)
    )
    hip = tuple(
        (left + right) / 2.0 for left, right in zip(left_hip, right_hip, strict=True)
    )
    torso_scale = math.sqrt(
        sum((left - right) ** 2 for left, right in zip(shoulder, hip, strict=True))
    )
    if not math.isfinite(torso_scale) or torso_scale <= 1e-6:
        raise ValueError("POSE_TORSO_SCALE_INVALID")
    down = math.degrees(math.atan2(nose[1] - shoulder[1], torso_scale))
    side = math.degrees(math.atan2(abs(nose[0] - shoulder[0]), torso_scale))
    return down, side


@dataclass(frozen=True)
class RulePolicy:
    policy_version: str
    status: str
    selection_source: str
    head_down_on: float
    head_down_off: float
    side_look_on: float
    side_look_off: float
    motion_duration_ms: int
    presence_duration_ms: int
    release_ms: int
    merge_gap_ms: int
    cooldown_ms: int

    @classmethod
    def demo(cls) -> RulePolicy:
        # Illustration parameters, never admitted as a frozen research policy.
        return cls(
            "rules-demo-v2",
            "DEMO_ONLY",
            "SYNTHETIC",
            15.0,
            8.0,
            25.0,
            15.0,
            2000,
            1500,
            400,
            700,
            1000,
        )

    def to_document(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_document(cls, document: dict[str, Any], *, research: bool) -> RulePolicy:
        if set(document) != set(cls.__dataclass_fields__):
            raise ValueError("POLICY_SCHEMA_INVALID")
        if research and (
            document["status"] != "FROZEN"
            or document["selection_source"] not in {"PILOT", "CALIBRATION"}
        ):
            raise ValueError("POLICY_NOT_FROZEN")
        for field in ("head_down_on", "head_down_off", "side_look_on", "side_look_off"):
            if type(document[field]) not in {float, int} or not math.isfinite(document[field]):
                raise ValueError("POLICY_THRESHOLD_INVALID")
        for field in (
            "motion_duration_ms",
            "presence_duration_ms",
            "release_ms",
            "merge_gap_ms",
            "cooldown_ms",
        ):
            if type(document[field]) is not int or not 0 <= document[field] <= 60000:
                raise ValueError("POLICY_DURATION_INVALID")
        if (
            not 0 <= document["head_down_off"] < document["head_down_on"]
            or not 0 <= document["side_look_off"] < document["side_look_on"]
            or document["motion_duration_ms"] <= 0
            or document["presence_duration_ms"] <= 0
        ):
            raise ValueError("POLICY_HYSTERESIS_INVALID")
        if not all(
            isinstance(document[key], str) and document[key]
            for key in ("policy_version", "status", "selection_source")
        ):
            raise ValueError("POLICY_VERSION_INVALID")
        return cls(**document)

    @classmethod
    def from_protocol_freeze(cls, document: Mapping[str, Any]) -> RulePolicy:
        """Map the frozen research protocol's event policy without defaults."""

        policy = document.get("event_policy")
        protocol_version = document.get("protocol_version")
        selection_source = document.get("policy_selection_source")
        if (
            document.get("status") != "FROZEN"
            or not isinstance(protocol_version, str)
            or not protocol_version
            or selection_source not in {"PILOT", "CALIBRATION"}
            or not isinstance(policy, Mapping)
            or set(policy) != PROTOCOL_EVENT_POLICY_FIELDS
        ):
            raise ValueError("PROTOCOL_POLICY_NOT_FROZEN")
        threshold_fields = (
            "head_down_start_degrees",
            "head_down_end_degrees",
            "side_look_start_degrees",
            "side_look_end_degrees",
        )
        duration_fields = PROTOCOL_EVENT_POLICY_FIELDS - set(threshold_fields)
        if any(
            isinstance(policy[name], bool)
            or not isinstance(policy[name], int | float)
            or not math.isfinite(float(policy[name]))
            for name in threshold_fields
        ) or any(
            not isinstance(policy[name], int)
            or isinstance(policy[name], bool)
            or not 0 <= policy[name] <= 60000
            for name in duration_fields
        ):
            raise ValueError("PROTOCOL_POLICY_VALUE_INVALID")
        try:
            mapped = cls(
                policy_version=f"{protocol_version}-policy",
                status="FROZEN",
                selection_source=str(selection_source),
                head_down_on=float(policy["head_down_start_degrees"]),
                head_down_off=float(policy["head_down_end_degrees"]),
                side_look_on=float(policy["side_look_start_degrees"]),
                side_look_off=float(policy["side_look_end_degrees"]),
                motion_duration_ms=int(policy["persistence_ms"]),
                presence_duration_ms=int(policy["presence_persistence_ms"]),
                release_ms=int(policy["release_ms"]),
                merge_gap_ms=int(policy["merge_gap_ms"]),
                cooldown_ms=int(policy["cooldown_ms"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("PROTOCOL_POLICY_SCHEMA_INVALID") from error
        return cls.from_document(mapped.to_document(), research=True)


@dataclass(frozen=True)
class RuleEvent:
    logical_id: str
    kind: str
    label: str
    start_ms: int
    end_ms: int
    eligible_onset_ms: int


class TemporalRuleEngine:
    def __init__(self, policy: RulePolicy) -> None:
        self.policy = policy
        self.operator_outcome = "TECHNICAL_INSUFFICIENT"
        self._last_ms = -1
        self._pending: str | None = None
        self._pending_start = 0
        self._active: RuleEvent | None = None
        self._last_support = 0
        self._last_emission = 0
        self._cooldown_until = 0

    def advance(
        self,
        timestamp_ms: int,
        pose_count: int,
        down_score: float,
        side_score: float,
        *,
        quality_ok: bool,
        prediction_label: str | None = None,
    ) -> list[RuleEvent]:
        if timestamp_ms <= self._last_ms or timestamp_ms < 0:
            raise ValueError("TIMESTAMP_NOT_MONOTONIC")
        self._last_ms = timestamp_ms
        if not quality_ok or not math.isfinite(down_score) or not math.isfinite(side_score):
            self.operator_outcome = "TECHNICAL_INSUFFICIENT"
            self._pending = None
            return self.close(timestamp_ms)
        active_label = self._active.label if self._active else None
        observed = None
        if pose_count == 0:
            observed = "NO_PERSON"
        elif pose_count > 1:
            observed = "MULTIPLE_PEOPLE"
        elif prediction_label in {"PROLONGED_HEAD_DOWN", "PROLONGED_SIDE_LOOK"}:
            observed = prediction_label
        elif prediction_label is None:
            down_limit = (
                self.policy.head_down_off
                if active_label == "PROLONGED_HEAD_DOWN"
                else self.policy.head_down_on
            )
            side_limit = (
                self.policy.side_look_off
                if active_label == "PROLONGED_SIDE_LOOK"
                else self.policy.side_look_on
            )
            if down_score >= down_limit:
                observed = "PROLONGED_HEAD_DOWN"
            elif side_score >= side_limit:
                observed = "PROLONGED_SIDE_LOOK"
        self.operator_outcome = "REVIEW_REQUIRED" if self._active else "NORMAL"
        if self._active:
            if observed == active_label:
                self._last_support = timestamp_ms + 1
                if timestamp_ms - self._last_emission >= 1000:
                    self._last_emission = timestamp_ms
                    return [self._event("UPDATE", self._last_support)]
                return []
            if timestamp_ms - self._last_support > max(
                self.policy.release_ms, self.policy.merge_gap_ms
            ):
                return self.close(timestamp_ms)
            return []
        if observed is None or timestamp_ms < self._cooldown_until:
            self._pending = None
            return []
        if observed != self._pending:
            self._pending, self._pending_start = observed, timestamp_ms
        duration = (
            self.policy.presence_duration_ms if pose_count != 1 else self.policy.motion_duration_ms
        )
        if timestamp_ms - self._pending_start < duration:
            return []
        self._active = RuleEvent(
            uuid.uuid4().hex,
            "START",
            observed,
            self._pending_start,
            timestamp_ms + 1,
            self._pending_start + duration,
        )
        self._last_support = timestamp_ms + 1
        self._last_emission = timestamp_ms
        self._pending = None
        self.operator_outcome = "REVIEW_REQUIRED"
        return [self._active]

    def _event(self, kind: str, end_ms: int) -> RuleEvent:
        assert self._active is not None
        return RuleEvent(
            self._active.logical_id,
            kind,
            self._active.label,
            self._active.start_ms,
            max(self._active.start_ms + 1, end_ms),
            self._active.eligible_onset_ms,
        )

    def close(self, timestamp_ms: int) -> list[RuleEvent]:
        if self._active is None:
            return []
        event = self._event("END", self._last_support)
        self._active = None
        self._pending = None
        self._cooldown_until = timestamp_ms + self.policy.cooldown_ms
        return [event]
