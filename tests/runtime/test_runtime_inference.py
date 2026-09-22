from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pdu_exam_observer.research_runtime import ResearchRuntimeService


def test_runtime_buffers_pose_sequence_and_stale_focus_abstains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1000.0]
    packets: list[dict[str, Any]] = []
    quality_values: list[float] = []
    expected_blurs: list[float] = []

    def provider(packet):
        packets.append(dict(packet))
        expected_blurs.append(float(np.mean(quality_values[-91:])))
        return {"label": "NORMAL", "confidence": 0.95, "model_version": "synthetic-test"}

    runtime = ResearchRuntimeService(tmp_path, model_provider=provider, clock=lambda: now[0])
    session_id = str(runtime.create_session()["session_id"])
    runtime.preflight(session_id)
    with runtime._connection:
        runtime._update_session_locked(session_id, state="RECORDING", started_at=1000.0)
    pose = [{"x": 0.5, "y": 0.3, "z": 0.0, "visibility": 1.0} for _ in range(33)]
    pose[11]["x"], pose[12]["x"] = 0.4, 0.6
    pose[23]["y"], pose[24]["y"] = 0.6, 0.6

    def analyze(_frame):
        blur = 20.0 + len(quality_values)
        quality_values.append(blur)
        return ({"state": "SUFFICIENT", "blur": blur, "exposure": 100.0}, [pose], 1, None)

    monkeypatch.setattr(
        runtime,
        "_analyze_frame",
        analyze,
    )
    monkeypatch.setattr(runtime, "_write_frame_locked", lambda *_args: 0)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    try:
        for index in range(100):
            now[0] = 1000 + index / 15
            if index % 30 == 0:
                runtime.record_focus_context(session_id, "EXAM_FOCUSED")
            result = runtime.ingest_frame(session_id, frame, index / 15)
            assert result["state"] == "RECORDING"
            if index < 89:
                assert not packets
        assert packets
        packet = packets[-1]
        assert packet["pose_tensor"].shape == (1, 5, 90, 33)
        assert packet["source_kind"] == "AI_RENDERED"
        assert packet["context"]["blur_score"] == pytest.approx(expected_blurs[-1])
        assert packet["context"]["blur_score"] != quality_values[-1]
        assert packet["context"]["exposure_score"] == pytest.approx(100.0)
        before = len(packets)
        now[0] += 7
        for index in range(100, 110):
            runtime.ingest_frame(session_id, frame, index / 15)
        assert len(packets) == before
        states = [
            event
            for event in runtime.events_after(session_id)
            if event["event_type"] == "MODEL_STATE"
        ]
        assert states[-1]["state"] == "TECHNICAL_INSUFFICIENT"
    finally:
        runtime.close()


def test_invalid_timestamp_fails_recording_closed(tmp_path: Path) -> None:
    runtime = ResearchRuntimeService(tmp_path)
    sid = str(runtime.create_session()["session_id"])
    runtime.preflight(sid)
    with runtime._connection:
        runtime._update_session_locked(sid, state="RECORDING")
    try:
        result = runtime.ingest_frame(sid, np.zeros((720, 1280, 3), dtype=np.uint8), float("nan"))
        assert result["state"] == "FAILED"
        assert result["failure_reason"] == "CAPTURE_TIMESTAMP_INVALID"
    finally:
        runtime.close()
