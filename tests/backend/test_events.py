import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app


def _candidate_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": str(client.base_url).rstrip("/"),
        "X-CSRF-Token": client.cookies["pdu_exam_csrf"],
    }


def _reviewer_headers(client: TestClient, token: str) -> dict[str, str]:
    return {"Origin": str(client.base_url).rstrip("/"), "Authorization": f"Bearer {token}"}


def _recording_session() -> tuple[TestClient, TestClient, str, str]:
    config = AppConfig(
        "123456", "http://exam.local", "http://monitor.local", ("exam.local", "monitor.local")
    )
    exam = TestClient(create_exam_app(config), base_url="http://exam.local")
    monitor = TestClient(create_monitor_app(config), base_url="http://monitor.local")
    login = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": "http://monitor.local"}
    )
    token = login.json()["access_token"]
    created = monitor.post("/api/v1/sessions", headers=_reviewer_headers(monitor, token)).json()
    exam.post(
        "/api/v1/candidate/pair",
        json={"pairing_code": created["pairing_code"]},
        headers={"Origin": "http://exam.local"},
    )
    for action in ("consent", "preflight", "start"):
        exam.post(
            f"/api/v1/sessions/{created['session_id']}/{action}",
            headers=_candidate_headers(exam),
        )
    return exam, monitor, created["session_id"], token


def test_reviewer_replays_the_canonical_safe_fixture_and_lists_monotonic_events() -> None:
    _, monitor, session_id, token = _recording_session()

    replayed = monitor.post(
        "/api/v1/demo/replay",
        json={"session_id": session_id},
        headers=_reviewer_headers(monitor, token),
    )
    listed = monitor.get(
        f"/api/v1/events?session_id={session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert replayed.status_code == 200
    events = listed.json()["events"]
    assert [event["event_seq"] for event in events] == list(range(1, len(events) + 1))
    replayed_events = [event for event in events if event["type"] == "DemoEvent"]
    assert [event["fixture_event_type"] for event in replayed_events] == [
        "session_started",
        "answer_recorded",
        "technical_state",
        "session_stopped",
    ]
    assert all(event["source_kind"] == "synthetic_demo" for event in replayed_events)
    assert all(
        "media" not in json.dumps(event).lower() and "candidate" not in json.dumps(event).lower()
        for event in replayed_events
    )


def test_reviewer_stream_rechecks_its_bearer_before_a_heartbeat() -> None:
    async def scenario() -> None:
        from pdu_exam_observer.services.core import M0Backend

        backend = M0Backend()
        record, _ = backend.create_session()
        token = backend.issue_reviewer_token()
        stream = backend.stream_reviewer_events(record.session_id, 0, token, heartbeat_seconds=0.01)

        snapshot = await anext(stream)
        backend.revoke_reviewer_token(token)
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), timeout=0.1)

        assert snapshot["type"] == "SessionSnapshot"

    asyncio.run(scenario())


def test_open_stream_before_replay_yields_monotonic_demo_events_live() -> None:
    async def scenario() -> None:
        from pdu_exam_observer.services.core import M0Backend

        backend = M0Backend()
        record, _ = backend.create_session()
        token = backend.issue_reviewer_token()
        stream = backend.stream_reviewer_events(record.session_id, 0, token, heartbeat_seconds=0.1)
        try:
            snapshot = await anext(stream)
            backend.replay_demo_alerts(record.session_id)
            live_events = [await asyncio.wait_for(anext(stream), timeout=0.1) for _ in range(4)]
        finally:
            await stream.aclose()

        assert snapshot["type"] == "SessionSnapshot"
        assert [event["event_seq"] for event in live_events] == [1, 2, 3, 4]
        assert [event["type"] for event in live_events] == ["DemoEvent"] * 4
        assert all(event["confidence"] is None for event in live_events)
        assert all(event["source_kind"] == "synthetic_demo" for event in live_events)

    asyncio.run(scenario())
