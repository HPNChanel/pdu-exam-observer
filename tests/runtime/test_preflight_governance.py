"""Boundary tests for native preflight evaluation, frozen-rules binding, quarantine."""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pytest

from pdu_exam_observer.research_runtime.service import (
    ResearchRuntimeService,
    _camera_profile_ready,
    _evaluate_native_preflight,
)


def _frame() -> np.ndarray:
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def _pose33() -> list[dict[str, float]]:
    return [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9} for _ in range(33)]


def _authority(root: Path) -> dict[str, object]:
    return {
        "authority_reference": "unit-authority",
        "status": "APPROVED",
        "consent_policy_sha256": "a" * 64,
        "institutional_approval_sha256": "b" * 64,
        "retention_record_sha256": "c" * 64,
        "native_root_digest": ResearchRuntimeService.root_digest(root),
        "participant_pseudonym": "participant-01",
        "consent_status": "CONFIRMED",
        "retention_expires_at": time.time() + 3600,
        "protocol_version": "protocol-2026-v1",
        "consent_receipt_id": "receipt-2026-001",
        "consent_version": "consent-v1",
        "operator_pseudonym": "operator-7f2a",
        "device_gate_decision": "UNVERIFIED",
        "withdrawal_authority_sha256": "d" * 64,
        "withdrawal_decision": "DELETE_OWNED_RUNTIME_ARTIFACTS",
    }


def _frozen_rules(protocol_version: str) -> dict[str, object]:
    document: dict[str, object] = {
        "status": "FROZEN",
        "protocol_version": protocol_version,
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
    unsigned = json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    document["protocol_freeze_sha256"] = hashlib.sha256(unsigned.encode("utf-8")).hexdigest()
    return document


def _real_recording(
    service: ResearchRuntimeService, session_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service._connection:
        service._update_session_locked(
            session_id,
            state="RECORDING",
            source_kind="REAL",
            participant_pseudonym="participant-01",
            authority_reference="unit-authority",
            started_at=time.time(),
        )
    quality = {"state": "SUFFICIENT", "blur": 50.0, "exposure": 100.0}
    monkeypatch.setattr(
        service, "_analyze_frame", lambda _frame: (quality, [_pose33()], 1, None)
    )
    monkeypatch.setattr(service, "_write_frame_locked", lambda *_args: 0)


def _write_rules(root: Path, protocol_version: str) -> None:
    directory = root / ".pdu_exam_observer"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "frozen-rules.v1.json").write_text(
        json.dumps(_frozen_rules(protocol_version)), encoding="utf-8"
    )


def test_camera_profile_gate_boundaries() -> None:
    assert _camera_profile_ready(720, 1280, 15.0)
    assert _camera_profile_ready(720, 1280, 12.0)
    assert _camera_profile_ready(720, 1280, 18.0)
    assert not _camera_profile_ready(720, 1280, 11.99)
    assert not _camera_profile_ready(720, 1280, 18.01)
    assert not _camera_profile_ready(720, 1280, 0.0)
    assert not _camera_profile_ready(720, 1280, math.nan)
    assert not _camera_profile_ready(720, 1280, math.inf)
    assert not _camera_profile_ready(480, 640, 15.0)
    assert not _camera_profile_ready(1080, 1920, 15.0)


def test_native_preflight_evaluation_boundaries() -> None:
    ready = _evaluate_native_preflight(camera_ready=True, display_count=2, disk_ok=True)
    assert ready == {"camera": "READY", "display": "READY", "disk": "READY"}
    assert _evaluate_native_preflight(camera_ready=True, display_count=3, disk_ok=True)[
        "display"
    ] == "READY"
    for count in (0, 1):
        assert _evaluate_native_preflight(
            camera_ready=True, display_count=count, disk_ok=True
        )["display"] == "UNAVAILABLE"
    assert _evaluate_native_preflight(camera_ready=False, display_count=2, disk_ok=True)[
        "camera"
    ] == "UNAVAILABLE"
    assert _evaluate_native_preflight(camera_ready=True, display_count=2, disk_ok=False)[
        "disk"
    ] == "UNAVAILABLE"


def test_real_session_rejects_unfrozen_or_mismatched_protocol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _authority(tmp_path)
    service = ResearchRuntimeService(tmp_path, authority_resolver=lambda _ref: record)
    try:
        session_id = str(service.create_session()["session_id"])
        record["session_pseudonym"] = session_id
        service.preflight(session_id, diagnostic={"disk": "READY", "source": "test"})
        _real_recording(service, session_id, monkeypatch)

        _write_rules(tmp_path, "protocol-DIFFERENT")
        service.ingest_frame(session_id, _frame(), captured_at=time.perf_counter())
        kinds = [event["event_type"] for event in service.events_after(session_id)]
        insufficient = [
            event
            for event in service.events_after(session_id)
            if event["event_type"] == "TECHNICAL_STATE"
        ]
        assert "RULE_POLICY_BOUND" not in kinds
        assert any(
            event.get("reason") == "RULE_POLICY_NOT_FROZEN" for event in insufficient
        )

        # Positive control: matching protocol_version binds the frozen policy.
        # One RECORDING session per root — end the first before the control.
        service.stop(session_id)
        second = str(service.create_session()["session_id"])
        record["session_pseudonym"] = second
        service.preflight(second, diagnostic={"disk": "READY", "source": "test"})
        _real_recording(service, second, monkeypatch)
        _write_rules(tmp_path, "protocol-2026-v1")
        service.ingest_frame(second, _frame(), captured_at=time.perf_counter() + 1)
        kinds = [event["event_type"] for event in service.events_after(second)]
        assert "RULE_POLICY_BOUND" in kinds
    finally:
        service.close()


def test_withdrawal_quarantine_renames_owned_artifact_directory(tmp_path: Path) -> None:
    record = _authority(tmp_path)
    record["withdrawal_decision"] = "QUARANTINE_RUNTIME_ARTIFACTS"
    service = ResearchRuntimeService(tmp_path, authority_resolver=lambda _ref: record)
    try:
        session_id = str(service.create_session()["session_id"])
        service.preflight(session_id)
        service.start_synthetic_demo(session_id)
        service.stop(session_id)
        service.seal(session_id)
        with service._connection:
            service._update_session_locked(
                session_id,
                source_kind="REAL",
                participant_pseudonym="participant-01",
                authority_reference="unit-authority",
                operator_pseudonym="operator-7f2a",
            )
        record["session_pseudonym"] = session_id
        directory = Path(str(service.get_session(session_id)["artifact_directory"]))
        assert directory.is_dir()

        withdrawn = service.withdraw(session_id, "unit-authority")
        assert withdrawn["state"] == "WITHDRAWN"
        quarantine = directory.with_name(directory.name + ".withdrawn.quarantine")
        assert not directory.exists()
        assert quarantine.is_dir()
        receipt = service.events_after(session_id)[-1]
        assert receipt["event_type"] == "WITHDRAWAL_RECORDED"
        assert receipt["decision"] == "QUARANTINE_RUNTIME_ARTIFACTS"
        assert receipt["artifacts"]
    finally:
        service.close()
