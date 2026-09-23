from collections.abc import Callable

from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app
from pdu_exam_observer.services.core import M0Backend


class Clock:
    def __init__(self, value: float = 1_700_000_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _apps(clock: Callable[[], float]) -> tuple[TestClient, TestClient, M0Backend]:
    backend = M0Backend(clock=clock, monotonic_clock=clock)
    config = AppConfig(
        "123456",
        "http://exam.local",
        "http://monitor.local",
        ("exam.local", "monitor.local"),
        backend=backend,
    )
    return (
        TestClient(create_exam_app(config), base_url=config.exam_origin),
        TestClient(create_monitor_app(config), base_url=config.monitor_origin),
        backend,
    )


def _login(monitor: TestClient) -> str:
    response = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": "http://monitor.local"}
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _candidate_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": str(client.base_url).rstrip("/"),
        "X-CSRF-Token": client.cookies["pdu_exam_csrf"],
    }


def _reviewer_headers(client: TestClient, token: str) -> dict[str, str]:
    return {"Origin": str(client.base_url).rstrip("/"), "Authorization": f"Bearer {token}"}


def _recording_session(exam: TestClient, monitor: TestClient) -> tuple[str, str]:
    token = _login(monitor)
    created = monitor.post("/api/v1/sessions", headers=_reviewer_headers(monitor, token)).json()
    paired = exam.post(
        "/api/v1/candidate/pair",
        json={"pairing_code": created["pairing_code"]},
        headers={"Origin": "http://exam.local"},
    )
    assert paired.status_code == 200
    session_id = created["session_id"]
    candidate_headers = _candidate_headers(exam)
    assert (
        exam.post(f"/api/v1/sessions/{session_id}/consent", headers=candidate_headers).status_code
        == 200
    )
    assert (
        exam.post(f"/api/v1/sessions/{session_id}/preflight", headers=candidate_headers).status_code
        == 200
    )
    assert (
        monitor.post(
            f"/api/v1/sessions/{session_id}/start", headers=_reviewer_headers(monitor, token)
        ).status_code
        == 200
    )
    return session_id, token


def test_reviewer_login_hashes_secret_throttles_and_revokes_with_clock() -> None:
    clock = Clock()
    _, monitor, backend = _apps(clock)
    assert not hasattr(backend, "reviewer_pin")
    assert not hasattr(monitor.app.state, "reviewer_pin")

    for _ in range(4):
        rejected = monitor.post(
            "/api/v1/reviewer/login",
            json={"pin": "wrong"},
            headers={"Origin": "http://monitor.local"},
        )
        assert rejected.status_code == 401
    blocked = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "wrong"}, headers={"Origin": "http://monitor.local"}
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0

    clock.advance(61)
    first_token = _login(monitor)
    replacement_token = _login(monitor)
    assert (
        monitor.get(
            "/api/v1/reviewer/session", headers={"Authorization": f"Bearer {first_token}"}
        ).status_code
        == 401
    )
    reviewer_headers = _reviewer_headers(monitor, replacement_token)
    logged_out = monitor.post("/api/v1/reviewer/logout", headers=reviewer_headers)
    assert logged_out.status_code == 204
    assert monitor.post("/api/v1/sessions", headers=reviewer_headers).status_code == 401


def test_answer_and_submit_retries_preserve_success_without_duplicate_events() -> None:
    clock = Clock()
    exam, monitor, _ = _apps(clock)
    session_id, token = _recording_session(exam, monitor)
    answer = {"answer_id": "answer-1", "question_id": "q-1", "value": "A"}
    headers = {**_candidate_headers(exam), "Idempotency-Key": "answer-retry-1"}

    first = exam.post("/api/v1/exam/answers", json=answer, headers=headers)
    retry = exam.post("/api/v1/exam/answers", json=answer, headers=headers)
    conflict = exam.post(
        "/api/v1/exam/answers",
        json={**answer, "value": "B"},
        headers=headers,
    )
    submit_headers = {**_candidate_headers(exam), "Idempotency-Key": "submit-retry-1"}
    submitted = exam.post("/api/v1/exam/submit", headers=submit_headers)
    submit_retry = exam.post("/api/v1/exam/submit", headers=submit_headers)
    events = monitor.get(
        f"/api/v1/events?session_id={session_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["events"]

    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json() == {"schema_version": 1, "accepted": True}
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert submitted.status_code == submit_retry.status_code == 200
    assert submitted.json() == submit_retry.json() == {"schema_version": 1, "submitted": True}
    assert [event["type"] for event in events].count("AnswerRecorded") == 1
    assert [event["type"] for event in events].count("ExamSubmitted") == 1


def test_reviewer_owned_lifecycle_and_candidate_timing_status_are_server_derived() -> None:
    clock = Clock()
    exam, monitor, _ = _apps(clock)
    token = _login(monitor)
    created = monitor.post("/api/v1/sessions", headers=_reviewer_headers(monitor, token)).json()
    session_id = created["session_id"]
    exam.post(
        "/api/v1/candidate/pair",
        json={"pairing_code": created["pairing_code"]},
        headers={"Origin": "http://exam.local"},
    )
    candidate_headers = _candidate_headers(exam)
    assert (
        exam.post(f"/api/v1/sessions/{session_id}/start", headers=candidate_headers).status_code
        == 404
    )
    assert (
        exam.post(f"/api/v1/sessions/{session_id}/consent", headers=candidate_headers).status_code
        == 200
    )
    assert (
        exam.post(f"/api/v1/sessions/{session_id}/preflight", headers=candidate_headers).status_code
        == 200
    )
    started = monitor.post(
        f"/api/v1/sessions/{session_id}/start", headers=_reviewer_headers(monitor, token)
    )
    clock.advance(17)
    status = exam.get("/api/v1/exam/status")

    assert started.json()["state"] == "RECORDING"
    assert status.json() == {
        "schema_version": 1,
        "session_id": session_id,
        "state": "RECORDING",
        "submitted": False,
        "duration_seconds": 2700,
        "remaining_seconds": 2683,
        "started_at_utc": "2023-11-14T22:13:20Z",
    }
