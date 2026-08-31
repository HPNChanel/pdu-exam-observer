from __future__ import annotations

import copy
import json

import pytest

from pdu_exam_observer.m2_d1_n2_evidence import (
    CAPTURE_POLICY_DIGEST,
    WATCHDOG_POLICY_DIGEST,
    FailureStage,
    RetainedLeaseCleanup,
    VerifiedTerminalEvidence,
    build_verified_terminal_evidence,
    verify_terminal_evidence,
)

DIGEST = "a" * 64


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _receipt() -> dict[str, object]:
    return {
        "audio_requested": False,
        "authority_digest": DIGEST,
        "backlog_ns": 0,
        "buffers_cleared": True,
        "capture_closed": True,
        "capture_policy_digest": CAPTURE_POLICY_DIGEST,
        "capture_starting": True,
        "challenge_digest": DIGEST,
        "d1_go": False,
        "delivered_frames": 900,
        "delivery_failure_frames": 0,
        "device_gate_decision": "UNVERIFIED",
        "dropped_explicit_frames": 0,
        "dropped_short_frames": 0,
        "duration_seconds": 60,
        "face_detections": 0,
        "failed_frames": 0,
        "failure_code": None,
        "ffmpeg_lease_closed": True,
        "first_frame": True,
        "grant_record_digest": DIGEST,
        "inference_failure_frames": 0,
        "job_drained": True,
        "job_name_digest": DIGEST,
        "max_stall_gap_ns": 100_000_000,
        "measured_post_warmup_ns": 55_000_000_000,
        "measured_total_ns": 60_000_000_000,
        "media_closed": True,
        "mutex_released": True,
        "network_authorized": False,
        "network_transport_constructed": False,
        "outbound_attempt_count": 0,
        "outcome": "D1_N2_PREFLIGHT_PASS",
        "p95_ingress_gap_us": 66_667,
        "p95_pose_latency_us": 100_000,
        "p99_pose_latency_us": 200_000,
        "pipe_closed": True,
        "pose_detections": 0,
        "pose_model_sha256": DIGEST,
        "post_attempted_frames": 825,
        "post_elapsed_ns": 55_000_000_000,
        "post_successful_frames": 825,
        "privacy_checked_frames": 900,
        "privacy_ready": True,
        "privacy_stop_count": 0,
        "privacy_terminal_frames": 0,
        "raw_retained": False,
        "receipt_received": True,
        "received_frames": 900,
        "retry": False,
        "runtime_digest": DIGEST,
        "schema_version": 1,
        "static_bindings_digest": DIGEST,
        "video_only": True,
        "watchdog_authorized": True,
        "watchdog_policy_digest": WATCHDOG_POLICY_DIGEST,
        "worker_lease_closed": True,
        "worker_supervised": True,
        "processed_frames": 900,
        "face_model_sha256": DIGEST,
    }


def _clean() -> RetainedLeaseCleanup:
    return RetainedLeaseCleanup(a0_clean=True, rp2_clean=True, preparation_clean=True)


def test_valid_pass_builds_reconstructively_verifiable_evidence() -> None:
    receipt_bytes = _canonical(_receipt())
    ledger_bytes = _canonical([])

    evidence = build_verified_terminal_evidence(receipt_bytes, ledger_bytes, _clean())

    assert type(evidence) is VerifiedTerminalEvidence
    assert evidence is not None
    assert verify_terminal_evidence(evidence)
    assert evidence.receipt_json.encode() == receipt_bytes
    assert evidence.failure_ledger_json.encode() == ledger_bytes
    persisted = _canonical(evidence.record_fields())
    assert b"Integrated Camera" not in persisted
    assert b"exception" not in persisted


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("received_frames", 901),
        ("failed_frames", 1),
        ("privacy_checked_frames", 899),
        ("measured_total_ns", 59_999_999_999),
        ("measured_post_warmup_ns", 54_999_999_999),
        ("post_successful_frames", 742),
        ("p95_ingress_gap_us", 200_001),
        ("p95_pose_latency_us", 200_001),
        ("p99_pose_latency_us", 500_001),
        ("backlog_ns", 2_000_000_001),
        ("max_stall_gap_ns", 1_000_000_000),
        ("delivery_failure_frames", 1),
        ("network_transport_constructed", True),
        ("outbound_attempt_count", 1),
        ("raw_retained", True),
        ("worker_lease_closed", False),
        ("d1_go", True),
        ("capture_policy_digest", DIGEST),
        ("watchdog_policy_digest", DIGEST),
    ],
)
def test_accounting_threshold_privacy_and_cleanup_mutants_are_rejected(
    field: str, value: object
) -> None:
    receipt = _receipt()
    receipt[field] = value
    assert build_verified_terminal_evidence(_canonical(receipt), _canonical([]), _clean()) is None


def test_no_go_requires_bounded_fixed_ledger_with_matching_first_code() -> None:
    receipt = _receipt()
    receipt.update(
        outcome="NO_GO",
        failure_code="FRAME_STALLED",
        max_stall_gap_ns=1_000_000_000,
    )
    ledger = [
        {
            "code": "FRAME_STALLED",
            "count": 1,
            "precedence": 0,
            "stage": FailureStage.WATCHDOG.value,
        }
    ]
    evidence = build_verified_terminal_evidence(
        _canonical(receipt), _canonical(ledger), _clean()
    )
    assert evidence is not None and verify_terminal_evidence(evidence)

    for mutant in (
        [],
        [{**ledger[0], "code": "UNKNOWN"}],
        [{**ledger[0], "count": 0}],
        [{**ledger[0], "precedence": 2}],
        [ledger[0], copy.deepcopy(ledger[0])],
    ):
        assert (
            build_verified_terminal_evidence(
                _canonical(receipt), _canonical(mutant), _clean()
            )
            is None
        )


def test_extra_float_noncanonical_or_unclean_retained_lease_is_rejected() -> None:
    receipt = _receipt()
    extra = {**receipt, "unexpected": 0}
    floating = {**receipt, "backlog_ns": 0.0}
    noncanonical = json.dumps(receipt).encode()
    assert build_verified_terminal_evidence(_canonical(extra), _canonical([]), _clean()) is None
    assert build_verified_terminal_evidence(_canonical(floating), _canonical([]), _clean()) is None
    assert build_verified_terminal_evidence(noncanonical, _canonical([]), _clean()) is None
    assert (
        build_verified_terminal_evidence(
            _canonical(receipt),
            _canonical([]),
            RetainedLeaseCleanup(True, False, True),
        )
        is None
    )


def test_post_build_receipt_or_digest_mutation_fails_restart_verification() -> None:
    evidence = build_verified_terminal_evidence(
        _canonical(_receipt()), _canonical([]), _clean()
    )
    assert evidence is not None
    mutated = VerifiedTerminalEvidence(
        receipt_json=evidence.receipt_json.replace(
            "\"received_frames\":900", "\"received_frames\":901"
        ),
        receipt_digest=evidence.receipt_digest,
        failure_ledger_json=evidence.failure_ledger_json,
        failure_ledger_digest=evidence.failure_ledger_digest,
        retained_cleanup=evidence.retained_cleanup,
    )
    assert not verify_terminal_evidence(mutated)
