"""Closed reconstructive receipt and terminal-evidence verifier for D1-N2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn, cast

CAPTURE_POLICY_DIGEST = "553f25eb67f50d8fcb0285498a065ff77b5c0cedd7dcc8019ab3ac20a6b8042b"
WATCHDOG_POLICY_DIGEST = "b54e97e25f5428af7bc39cfc02fc7377bdd633f9b3834140cc13a22b844c2f78"


class FailureStage(StrEnum):
    AUTHORIZATION = "AUTHORIZATION"
    WORKER_IMAGE = "WORKER_IMAGE"
    JOB = "JOB"
    WATCHDOG = "WATCHDOG"
    CAPTURE = "CAPTURE"
    PRIVACY = "PRIVACY"
    ACCOUNTING = "ACCOUNTING"
    CLEANUP = "CLEANUP"


_FAILURE_CODES: dict[str, FailureStage] = {
    "AUTHORIZATION_FAILED": FailureStage.AUTHORIZATION,
    "WORKER_IMAGE_MISMATCH": FailureStage.WORKER_IMAGE,
    "JOB_BINDING_FAILED": FailureStage.JOB,
    "FRAME_STALLED": FailureStage.WATCHDOG,
    "WATCHDOG_FAILED": FailureStage.WATCHDOG,
    "CAPTURE_RUNTIME_FAILED": FailureStage.CAPTURE,
    "INFERENCE_FAILED": FailureStage.CAPTURE,
    "DELIVERY_FAILED": FailureStage.CAPTURE,
    "PRIVACY_STOP": FailureStage.PRIVACY,
    "ACCOUNTING_INVALID": FailureStage.ACCOUNTING,
    "QUALITY_INSUFFICIENT": FailureStage.ACCOUNTING,
    "CLEANUP_INCOMPLETE": FailureStage.CLEANUP,
}


@dataclass(frozen=True, slots=True)
class FailureLedgerEntry:
    stage: FailureStage
    code: str
    count: int
    precedence: int


@dataclass(frozen=True, slots=True)
class RedactedReceipt:
    canonical_bytes: bytes
    outcome: str
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class RetainedLeaseCleanup:
    a0_clean: bool
    rp2_clean: bool
    preparation_clean: bool

    def valid(self) -> bool:
        return (
            self.a0_clean is True
            and self.rp2_clean is True
            and self.preparation_clean is True
        )

    def record_fields(self) -> dict[str, bool]:
        return {
            "retained_a0_clean": self.a0_clean,
            "retained_preparation_clean": self.preparation_clean,
            "retained_rp2_clean": self.rp2_clean,
        }


@dataclass(frozen=True, slots=True)
class VerifiedTerminalEvidence:
    receipt_json: str
    receipt_digest: str
    failure_ledger_json: str
    failure_ledger_digest: str
    retained_cleanup: RetainedLeaseCleanup

    def record_fields(self) -> dict[str, object]:
        return {
            "failure_ledger_digest": self.failure_ledger_digest,
            "failure_ledger_json": self.failure_ledger_json,
            "receipt_digest": self.receipt_digest,
            "receipt_json": self.receipt_json,
            **self.retained_cleanup.record_fields(),
        }


_RECEIPT_KEYS = {
    "audio_requested",
    "authority_digest",
    "backlog_ns",
    "buffers_cleared",
    "capture_closed",
    "capture_policy_digest",
    "capture_starting",
    "challenge_digest",
    "d1_go",
    "delivered_frames",
    "delivery_failure_frames",
    "device_gate_decision",
    "dropped_explicit_frames",
    "dropped_short_frames",
    "duration_seconds",
    "face_detections",
    "face_model_sha256",
    "failed_frames",
    "failure_code",
    "ffmpeg_lease_closed",
    "first_frame",
    "grant_record_digest",
    "inference_failure_frames",
    "job_drained",
    "job_name_digest",
    "max_stall_gap_ns",
    "measured_post_warmup_ns",
    "measured_total_ns",
    "media_closed",
    "mutex_released",
    "network_authorized",
    "network_transport_constructed",
    "outbound_attempt_count",
    "outcome",
    "p95_ingress_gap_us",
    "p95_pose_latency_us",
    "p99_pose_latency_us",
    "pipe_closed",
    "pose_detections",
    "pose_model_sha256",
    "post_attempted_frames",
    "post_elapsed_ns",
    "post_successful_frames",
    "privacy_checked_frames",
    "privacy_ready",
    "privacy_stop_count",
    "privacy_terminal_frames",
    "processed_frames",
    "raw_retained",
    "receipt_received",
    "received_frames",
    "retry",
    "runtime_digest",
    "schema_version",
    "static_bindings_digest",
    "video_only",
    "watchdog_authorized",
    "watchdog_policy_digest",
    "worker_lease_closed",
    "worker_supervised",
}

_COUNT_FIELDS = {
    "received_frames",
    "delivered_frames",
    "processed_frames",
    "dropped_explicit_frames",
    "dropped_short_frames",
    "failed_frames",
    "inference_failure_frames",
    "privacy_terminal_frames",
    "delivery_failure_frames",
    "post_attempted_frames",
    "post_successful_frames",
    "privacy_checked_frames",
    "privacy_stop_count",
    "face_detections",
    "pose_detections",
    "outbound_attempt_count",
}
_TIMING_FIELDS = {
    "measured_total_ns",
    "measured_post_warmup_ns",
    "post_elapsed_ns",
    "p95_ingress_gap_us",
    "p95_pose_latency_us",
    "p99_pose_latency_us",
    "backlog_ns",
    "max_stall_gap_ns",
}
_BOOL_FIELDS = {
    "video_only",
    "retry",
    "audio_requested",
    "network_authorized",
    "network_transport_constructed",
    "raw_retained",
    "d1_go",
    "watchdog_authorized",
    "privacy_ready",
    "capture_starting",
    "first_frame",
    "capture_closed",
    "receipt_received",
    "worker_supervised",
    "job_drained",
    "worker_lease_closed",
    "pipe_closed",
    "media_closed",
    "ffmpeg_lease_closed",
    "mutex_released",
    "buffers_cleared",
}
_DIGEST_FIELDS = {
    "authority_digest",
    "grant_record_digest",
    "challenge_digest",
    "job_name_digest",
    "static_bindings_digest",
    "capture_policy_digest",
    "watchdog_policy_digest",
    "runtime_digest",
    "pose_model_sha256",
    "face_model_sha256",
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _decode_closed(payload: bytes) -> object | None:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_number(_value: str) -> NoReturn:
        raise ValueError("non-integer number")

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=reject_number,
            parse_constant=reject_number,
        )
    except (TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    if _canonical_bytes(value) != payload:
        return None
    return cast(object, value)


def _digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _ledger(payload: bytes, failure_code: object, outcome: object) -> bool:
    decoded = _decode_closed(payload)
    if type(decoded) is not list or len(decoded) > 8:
        return False
    if outcome == "D1_N2_PREFLIGHT_PASS":
        return failure_code is None and decoded == []
    if outcome != "NO_GO" or type(failure_code) is not str or not decoded:
        return False
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(decoded):
        if type(raw) is not dict or set(raw) != {"stage", "code", "count", "precedence"}:
            return False
        stage = raw.get("stage")
        code = raw.get("code")
        count = raw.get("count")
        precedence = raw.get("precedence")
        if (
            type(stage) is not str
            or type(code) is not str
            or type(count) is not int
            or count <= 0
            or type(precedence) is not int
            or precedence != index
            or _FAILURE_CODES.get(code) is None
            or _FAILURE_CODES[code].value != stage
            or (stage, code) in seen
        ):
            return False
        seen.add((stage, code))
    first = decoded[0]
    return isinstance(first, dict) and first.get("code") == failure_code


def _receipt(payload: bytes) -> RedactedReceipt | None:
    decoded = _decode_closed(payload)
    if type(decoded) is not dict or set(decoded) != _RECEIPT_KEYS:
        return None
    if (
        type(decoded.get("schema_version")) is not int
        or decoded.get("schema_version") != 1
        or type(decoded.get("duration_seconds")) is not int
        or decoded.get("duration_seconds") != 60
        or decoded.get("video_only") is not True
        or decoded.get("retry") is not False
        or decoded.get("audio_requested") is not False
        or decoded.get("network_authorized") is not False
        or decoded.get("network_transport_constructed") is not False
        or decoded.get("raw_retained") is not False
        or decoded.get("device_gate_decision") != "UNVERIFIED"
        or decoded.get("d1_go") is not False
        or not all(type(decoded.get(name)) is bool for name in _BOOL_FIELDS)
        or not all(
            type(decoded.get(name)) is int and int(decoded[name]) >= 0
            for name in _COUNT_FIELDS | _TIMING_FIELDS
        )
        or not all(_digest(decoded.get(name)) for name in _DIGEST_FIELDS)
        or decoded.get("capture_policy_digest") != CAPTURE_POLICY_DIGEST
        or decoded.get("watchdog_policy_digest") != WATCHDOG_POLICY_DIGEST
    ):
        return None
    if (
        decoded["outbound_attempt_count"] != 0
        or decoded["received_frames"] != decoded["delivered_frames"]
        or decoded["delivered_frames"]
        != decoded["processed_frames"]
        + decoded["dropped_explicit_frames"]
        + decoded["failed_frames"]
        or decoded["dropped_explicit_frames"] != decoded["dropped_short_frames"]
        or decoded["failed_frames"]
        != decoded["inference_failure_frames"]
        + decoded["privacy_terminal_frames"]
        + decoded["delivery_failure_frames"]
        or decoded["post_attempted_frames"]
        != decoded["post_successful_frames"]
        + decoded["dropped_short_frames"]
        + decoded["inference_failure_frames"]
        + decoded["privacy_terminal_frames"]
        + decoded["delivery_failure_frames"]
        or decoded["privacy_checked_frames"] != decoded["processed_frames"]
    ):
        return None
    cleanup = (
        "worker_supervised",
        "job_drained",
        "worker_lease_closed",
        "pipe_closed",
        "media_closed",
        "ffmpeg_lease_closed",
        "mutex_released",
        "buffers_cleared",
    )
    if not all(decoded[name] is True for name in cleanup):
        return None
    outcome = decoded.get("outcome")
    failure_code = decoded.get("failure_code")
    if outcome == "D1_N2_PREFLIGHT_PASS":
        attempted = int(decoded["post_attempted_frames"])
        successful = int(decoded["post_successful_frames"])
        elapsed = int(decoded["post_elapsed_ns"])
        dropped_or_failed = int(decoded["dropped_short_frames"]) + int(
            decoded["inference_failure_frames"]
        )
        if (
            failure_code is not None
            or int(decoded["measured_total_ns"]) < 60_000_000_000
            or int(decoded["measured_post_warmup_ns"]) < 55_000_000_000
            or elapsed <= 0
            or 2 * successful * 1_000_000_000 < 27 * elapsed
            or int(decoded["p95_ingress_gap_us"]) > 200_000
            or int(decoded["p95_pose_latency_us"]) > 200_000
            or int(decoded["p99_pose_latency_us"]) > 500_000
            or int(decoded["backlog_ns"]) > 2_000_000_000
            or int(decoded["max_stall_gap_ns"]) >= 1_000_000_000
            or attempted <= 0
            or 100 * dropped_or_failed > attempted
            or 100 * successful < 99 * attempted
            or int(decoded["delivery_failure_frames"]) != 0
            or int(decoded["privacy_stop_count"]) != 0
            or int(decoded["face_detections"]) != 0
            or int(decoded["pose_detections"]) != 0
            or not all(
                decoded[name] is True
                for name in (
                    "watchdog_authorized",
                    "privacy_ready",
                    "capture_starting",
                    "first_frame",
                    "capture_closed",
                    "receipt_received",
                )
            )
        ):
            return None
    elif outcome != "NO_GO" or type(failure_code) is not str:
        return None
    return RedactedReceipt(
        payload,
        str(outcome),
        failure_code if isinstance(failure_code, str) else None,
    )


def build_verified_terminal_evidence(
    receipt_bytes: bytes,
    failure_ledger_bytes: bytes,
    retained_cleanup: RetainedLeaseCleanup,
) -> VerifiedTerminalEvidence | None:
    if (
        type(receipt_bytes) is not bytes
        or type(failure_ledger_bytes) is not bytes
        or type(retained_cleanup) is not RetainedLeaseCleanup
        or not retained_cleanup.valid()
    ):
        return None
    receipt = _receipt(receipt_bytes)
    if receipt is None or not _ledger(
        failure_ledger_bytes, receipt.failure_code, receipt.outcome
    ):
        return None
    try:
        receipt_json = receipt_bytes.decode("utf-8")
        ledger_json = failure_ledger_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return VerifiedTerminalEvidence(
        receipt_json=receipt_json,
        receipt_digest=hashlib.sha256(receipt_bytes).hexdigest(),
        failure_ledger_json=ledger_json,
        failure_ledger_digest=hashlib.sha256(failure_ledger_bytes).hexdigest(),
        retained_cleanup=retained_cleanup,
    )


def verify_terminal_evidence(evidence: object) -> bool:
    if type(evidence) is not VerifiedTerminalEvidence:
        return False
    rebuilt = build_verified_terminal_evidence(
        evidence.receipt_json.encode("utf-8"),
        evidence.failure_ledger_json.encode("utf-8"),
        evidence.retained_cleanup,
    )
    return rebuilt == evidence


def verify_worker_candidate_envelope(value: object) -> bool:
    if (
        type(value) is not dict
        or set(value) != {"failure_ledger", "receipt"}
        or type(value.get("receipt")) is not dict
        or type(value.get("failure_ledger")) is not list
    ):
        return False
    receipt = value["receipt"]
    ledger = value["failure_ledger"]
    assert isinstance(receipt, dict)
    if set(receipt) != _RECEIPT_KEYS:
        return False
    if (
        receipt.get("schema_version") != 1
        or receipt.get("duration_seconds") != 60
        or receipt.get("video_only") is not True
        or receipt.get("retry") is not False
        or receipt.get("audio_requested") is not False
        or receipt.get("network_authorized") is not False
        or receipt.get("network_transport_constructed") is not False
        or receipt.get("outbound_attempt_count") != 0
        or receipt.get("raw_retained") is not False
        or receipt.get("device_gate_decision") != "UNVERIFIED"
        or receipt.get("d1_go") is not False
    ):
        return False

    def integer_only(item: object) -> bool:
        if type(item) is float:
            return False
        if type(item) is dict:
            return all(type(key) is str and integer_only(child) for key, child in item.items())
        if type(item) is list:
            return all(integer_only(child) for child in item)
        return type(item) in {str, int, bool, type(None)}

    return integer_only(value) and _ledger(
        _canonical_bytes(ledger), receipt.get("failure_code"), receipt.get("outcome")
    )


def build_sanitized_no_go_evidence(
    *,
    failure_code: str,
    authority_digest: str,
    grant_record_digest: str,
    challenge_digest: str,
    job_name_digest: str,
    static_bindings_digest: str,
    capture_policy_digest: str,
    watchdog_policy_digest: str,
    runtime_digest: str,
    pose_model_sha256: str,
    face_model_sha256: str,
    retained_cleanup: RetainedLeaseCleanup,
) -> VerifiedTerminalEvidence | None:
    stage = _FAILURE_CODES.get(failure_code)
    digests = (
        authority_digest,
        grant_record_digest,
        challenge_digest,
        job_name_digest,
        static_bindings_digest,
        capture_policy_digest,
        watchdog_policy_digest,
        runtime_digest,
        pose_model_sha256,
        face_model_sha256,
    )
    if stage is None or not all(_digest(value) for value in digests):
        return None
    receipt: dict[str, object] = {
        name: 0 for name in _COUNT_FIELDS | _TIMING_FIELDS
    }
    receipt.update(
        {
            name: False for name in _BOOL_FIELDS
        }
    )
    receipt.update(
        {
            "audio_requested": False,
            "authority_digest": authority_digest,
            "buffers_cleared": True,
            "capture_policy_digest": capture_policy_digest,
            "challenge_digest": challenge_digest,
            "d1_go": False,
            "device_gate_decision": "UNVERIFIED",
            "duration_seconds": 60,
            "face_model_sha256": face_model_sha256,
            "failure_code": failure_code,
            "ffmpeg_lease_closed": True,
            "grant_record_digest": grant_record_digest,
            "job_drained": True,
            "job_name_digest": job_name_digest,
            "media_closed": True,
            "mutex_released": True,
            "network_authorized": False,
            "network_transport_constructed": False,
            "outcome": "NO_GO",
            "pipe_closed": True,
            "pose_model_sha256": pose_model_sha256,
            "raw_retained": False,
            "retry": False,
            "runtime_digest": runtime_digest,
            "schema_version": 1,
            "static_bindings_digest": static_bindings_digest,
            "video_only": True,
            "watchdog_policy_digest": watchdog_policy_digest,
            "worker_lease_closed": True,
            "worker_supervised": True,
        }
    )
    ledger = [
        {
            "code": failure_code,
            "count": 1,
            "precedence": 0,
            "stage": stage.value,
        }
    ]
    return build_verified_terminal_evidence(
        _canonical_bytes(receipt), _canonical_bytes(ledger), retained_cleanup
    )


__all__ = [
    "FailureLedgerEntry",
    "FailureStage",
    "RedactedReceipt",
    "RetainedLeaseCleanup",
    "VerifiedTerminalEvidence",
    "build_verified_terminal_evidence",
    "build_sanitized_no_go_evidence",
    "verify_terminal_evidence",
    "verify_worker_candidate_envelope",
]
