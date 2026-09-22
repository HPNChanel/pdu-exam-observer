"""Task-06 runtime hardening gates: bounded resources, fail-closed inputs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import pdu_exam_observer.launcher as launcher
from pdu_exam_observer.contracts import AnswerRequest, SessionState
from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.repositories.in_memory import (
    MAX_ANSWERS_PER_SESSION,
    MAX_EVENTS_PER_SESSION,
    EventLogLimitExceeded,
    EventRecord,
)
from pdu_exam_observer.services.core import M0Backend, ReviewerAuthenticator


def _make_monitor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PDU_REVIEWER_PIN", "test-only-pin")
    monkeypatch.setenv("PDU_RUNTIME_MODE", "m2research")
    monkeypatch.setenv("PDU_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PDU_COLLECTION_AUTHORITY_REF", "")
    _, monitor = launcher.build_apps_from_environment()
    return TestClient(monitor, base_url="http://localhost:8766")


ORIGIN = {"Origin": "http://localhost:8766"}


def _reviewer_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/reviewer/login", json={"pin": "test-only-pin"}, headers=ORIGIN
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_answer_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AnswerRequest(
            answer_id="a1",
            question_id="q1",
            value="x",
            unexpected="field",  # type: ignore[call-arg]
        )


def test_answer_request_still_accepts_declared_fields() -> None:
    request = AnswerRequest(answer_id="a1", question_id="q1", value="x")
    assert request.answer_id == "a1"


def test_pin_throttle_ignores_wall_clock() -> None:
    auth = ReviewerAuthenticator("correct-pin", max_failures=2, cooldown_seconds=60)
    base = time.monotonic()
    assert auth.authenticate("wrong", "client", base).accepted is False
    blocked = auth.authenticate("wrong", "client", base + 1)
    assert blocked.accepted is False
    assert blocked.retry_after == 60
    # The throttle only observes the monotonic value it is handed; a
    # wall-clock jump cannot reset the cooldown.
    still_blocked = auth.authenticate("correct-pin", "client", base + 30)
    assert still_blocked.accepted is False
    assert still_blocked.retry_after is not None


def test_event_log_cap_fails_closed() -> None:
    backend = M0Backend()
    record, _ = backend.create_session()
    record.events.extend(
        EventRecord(index, "FILLER", {}) for index in range(MAX_EVENTS_PER_SESSION)
    )
    with pytest.raises(EventLogLimitExceeded):
        backend.append_event(record.session_id, "OVERFLOW", {})


def test_answer_cap_fails_closed() -> None:
    backend = M0Backend()
    record, _ = backend.create_session()
    record.state = SessionState.RECORDING
    for index in range(MAX_ANSWERS_PER_SESSION):
        record.answers[f"k{index}"] = {"answer_id": f"a{index}"}
    with pytest.raises(InvalidTransition, match="ANSWER_LIMIT_REACHED"):
        backend.record_answer(record.session_id, "new-key", {"answer_id": "a-new"})


def test_sse_subscriber_cap_returns_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _make_monitor(tmp_path, monkeypatch)
    token = _reviewer_token(client)
    backend = client.app.state.backend  # type: ignore[attr-defined]
    created = client.post(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {token}", **ORIGIN},
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    for _ in range(backend.max_subscribers_per_session):
        backend._subscribers.setdefault(session_id, []).append(asyncio.Queue())
    response = client.post(
        "/api/v1/events/stream",
        json={"session_id": session_id, "after_event_seq": 0},
        headers={"Authorization": f"Bearer {token}", **ORIGIN},
    )
    assert response.status_code == 429


def test_sse_queue_overflow_marks_subscriber_stale() -> None:
    backend = M0Backend(subscriber_queue_size=1)
    record, _ = backend.create_session()
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)
    backend._subscribers[record.session_id] = [queue]
    backend.append_event(record.session_id, "E1", {})
    backend.append_event(record.session_id, "E2", {})
    assert queue in backend._stale_subscribers
    assert queue.qsize() == 1


def test_sse_stream_terminates_for_stalled_consumer() -> None:
    """A consumer slower than the producer must be disconnected, not buffered forever."""

    async def scenario() -> tuple[int, int]:
        backend = M0Backend(subscriber_queue_size=4)
        record, _ = backend.create_session()
        session_id = record.session_id
        stream = backend.stream_events(session_id, 0, heartbeat_seconds=0.02)
        snapshot = await anext(stream)
        assert snapshot["type"] == "SessionSnapshot"
        delivered = 0

        async def consume() -> None:
            nonlocal delivered
            async for event in stream:
                if event is not None:
                    delivered += 1
                await asyncio.sleep(0.05)  # stalled relative to the producer

        async def produce() -> None:
            for index in range(16):
                backend.append_event(session_id, "Flood", {"index": index})
                await asyncio.sleep(0)

        await asyncio.gather(consume(), produce())
        return delivered, len(backend._subscribers.get(session_id, ()))

    delivered, remaining_subscribers = asyncio.run(scenario())
    # One event is handed directly to the pending getter, four fill the bounded
    # queue, and the rest are dropped — never 16 buffered events.
    assert delivered == 5
    assert remaining_subscribers == 0  # finally block detached the subscriber


def test_authority_template_dispatches(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    session_id = "12345678-1234-1234-1234-123456789abc"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdu_exam_observer",
            "authority-template",
            "--root",
            str(root),
            "--session-id",
            session_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["status"] == "DRAFT"
    assert record["session_pseudonym"] == session_id
    assert record["authority_reference"].startswith("REPLACE_WITH")


def test_ffmpeg_path_requires_env_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pdu_exam_observer.research_runtime.service import ResearchRuntimeService

    monkeypatch.delenv("PDU_FFMPEG_PATH", raising=False)
    monkeypatch.delenv("PDU_FFMPEG_SHA256", raising=False)
    assert ResearchRuntimeService._ffmpeg_path() is None

    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"fake-ffmpeg")
    monkeypatch.setenv("PDU_FFMPEG_PATH", str(binary))
    assert ResearchRuntimeService._ffmpeg_path() is None
    monkeypatch.setenv("PDU_FFMPEG_SHA256", "0" * 64)
    assert ResearchRuntimeService._ffmpeg_path() is None
    monkeypatch.setenv(
        "PDU_FFMPEG_SHA256", hashlib.sha256(b"fake-ffmpeg").hexdigest()
    )
    assert ResearchRuntimeService._ffmpeg_path() == binary.resolve()


def test_session_column_allowlist(tmp_path: Path) -> None:
    from pdu_exam_observer.research_runtime.service import (
        ResearchRuntimeService,
        RuntimeErrorBase,
    )

    service = ResearchRuntimeService(tmp_path)
    try:
        session = service.create_session()
        session_id = str(session["session_id"])
        with pytest.raises(RuntimeErrorBase):
            service._update_session_locked(
                session_id, **{"state=1; DROP TABLE runtime_sessions;--": "x"}
            )
        service._update_session_locked(session_id, state="SEALED")
        assert service.get_session(session_id)["state"] == "SEALED"
    finally:
        service.close()


def test_degenerate_frame_fails_closed_without_nan(tmp_path: Path) -> None:
    import numpy as np

    from pdu_exam_observer.research_runtime.service import ResearchRuntimeService

    service = ResearchRuntimeService(tmp_path)
    try:
        quality, landmarks, pose_count, failure = service._analyze_frame(
            np.zeros((0, 1280, 3), dtype=np.uint8)
        )
        assert failure == "POSE_SCHEMA_FAILED"
        assert landmarks == [] and pose_count == 0
        serialized = json.dumps(quality)
        assert "NaN" not in serialized
    finally:
        service.close()


def test_preview_stop_refuses_unowned_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import start_workspace_preview as preview

    unowned = tmp_path / "not-a-preview"
    unowned.mkdir()
    state = tmp_path / "preview-server.json"
    state.write_text(
        json.dumps({"pid": 0, "root": str(unowned)}), encoding="utf-8"
    )
    monkeypatch.setattr(preview, "STATE", state)
    monkeypatch.setattr(
        preview.subprocess,
        "run",
        lambda *a, **k: None,
    )
    assert preview._stop() == 0
    assert unowned.is_dir()  # containment/marker check refused deletion
