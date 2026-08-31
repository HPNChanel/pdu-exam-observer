import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app
from pdu_exam_observer.services.core import M0Backend


def _candidate_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": str(client.base_url).rstrip("/"),
        "X-CSRF-Token": client.cookies["pdu_exam_csrf"],
    }


def _reviewer_headers(client: TestClient, token: str) -> dict[str, str]:
    return {"Origin": str(client.base_url).rstrip("/"), "Authorization": f"Bearer {token}"}


def test_loopback_hosts_are_distinct_and_reviewer_bearer_cannot_cross_to_exam() -> None:
    config = AppConfig(
        "123456", "http://127.0.0.1:8765", "http://localhost:8766", ("127.0.0.1", "localhost")
    )
    exam = TestClient(create_exam_app(config), base_url=config.exam_origin)
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    login = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": config.monitor_origin}
    )
    token = login.json()["access_token"]

    assert "reviewer_session" not in monitor.cookies
    assert (
        exam.get(
            "/api/v1/events",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 404
    )
    assert monitor.get("/api/v1/health", headers={"Host": "127.0.0.1:8766"}).status_code == 403


def test_candidate_only_confirms_consent_and_preflight_while_reviewer_starts_and_stops() -> None:
    config = AppConfig(
        "123456", "http://127.0.0.1:8765", "http://localhost:8766", ("127.0.0.1", "localhost")
    )
    exam = TestClient(create_exam_app(config), base_url=config.exam_origin)
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    login = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": config.monitor_origin}
    )
    token = login.json()["access_token"]
    created = monitor.post("/api/v1/sessions", headers=_reviewer_headers(monitor, token)).json()
    exam.post(
        "/api/v1/candidate/pair",
        json={"pairing_code": created["pairing_code"]},
        headers={"Origin": config.exam_origin},
    )
    candidate_headers = _candidate_headers(exam)

    assert (
        exam.post(
            f"/api/v1/sessions/{created['session_id']}/start", headers=candidate_headers
        ).status_code
        == 404
    )
    assert (
        exam.post(
            f"/api/v1/sessions/{created['session_id']}/consent",
            json={"granted": True},
            headers=candidate_headers,
        ).status_code
        == 200
    )
    assert (
        exam.post(
            f"/api/v1/sessions/{created['session_id']}/preflight",
            json={"ready": True},
            headers=candidate_headers,
        ).status_code
        == 200
    )
    assert (
        monitor.post(
            f"/api/v1/sessions/{created['session_id']}/start",
            headers=_reviewer_headers(monitor, token),
        ).status_code
        == 200
    )
    assert (
        monitor.post(
            f"/api/v1/sessions/{created['session_id']}/stop",
            headers=_reviewer_headers(monitor, token),
        ).status_code
        == 200
    )


def test_service_stream_emits_snapshot_then_new_event_without_waiting_for_disconnect() -> None:
    async def scenario() -> None:
        backend = M0Backend()
        record, _ = backend.create_session()
        stream = backend.stream_events(record.session_id, 0, heartbeat_seconds=0.1)
        snapshot = await anext(stream)
        waiting = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        backend.append_demo_event(
            record.session_id,
            {
                "fixture_event_type": "technical_state",
                "confidence": None,
                "confidence_status": "INSUFFICIENT",
            },
        )
        event = await asyncio.wait_for(waiting, timeout=0.2)
        await stream.aclose()
        assert snapshot["type"] == "SessionSnapshot"
        assert event["event_seq"] == 1

    asyncio.run(scenario())


def test_replay_reads_the_canonical_demo_fixture(tmp_path: Path) -> None:
    fixture = tmp_path / "events.jsonl"
    fixture.write_text(
        '{"event_seq":1,"event_type":"technical_state","source_kind":"synthetic_demo","confidence":null,"confidence_status":"INSUFFICIENT","payload":{}}\n',
        encoding="utf-8",
    )
    backend = M0Backend(demo_fixture=fixture)
    record, _ = backend.create_session()
    assert (
        backend.replay_demo_alerts(record.session_id)[0]["fixture_event_type"] == "technical_state"
    )
