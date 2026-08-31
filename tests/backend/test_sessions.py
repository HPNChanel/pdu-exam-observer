from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app


def _candidate_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": str(client.base_url).rstrip("/"),
        "X-CSRF-Token": client.cookies["pdu_exam_csrf"],
    }


def _reviewer_headers(client: TestClient, token: str) -> dict[str, str]:
    return {"Origin": str(client.base_url).rstrip("/"), "Authorization": f"Bearer {token}"}


def _paired_clients() -> tuple[TestClient, TestClient, str, str]:
    config = AppConfig(
        "123456", "http://exam.local", "http://monitor.local", ("exam.local", "monitor.local")
    )
    exam = TestClient(create_exam_app(config), base_url="http://exam.local")
    monitor = TestClient(create_monitor_app(config), base_url="http://monitor.local")
    login = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": "http://monitor.local"}
    )
    token = login.json()["access_token"]
    created = monitor.post("/api/v1/sessions", headers=_reviewer_headers(monitor, token))
    session_id = created.json()["session_id"]
    exam.post(
        "/api/v1/candidate/pair",
        json={"pairing_code": created.json()["pairing_code"]},
        headers={"Origin": "http://exam.local"},
    )
    return exam, monitor, session_id, token


def test_session_cannot_start_until_consent_and_preflight_then_start_stop_are_idempotent() -> None:
    exam, monitor, session_id, token = _paired_clients()
    base = f"/api/v1/sessions/{session_id}"

    blocked = monitor.post(f"{base}/start", headers=_reviewer_headers(monitor, token))
    consent = exam.post(f"{base}/consent", headers=_candidate_headers(exam))
    preflight = exam.post(f"{base}/preflight", headers=_candidate_headers(exam))
    started = monitor.post(f"{base}/start", headers=_reviewer_headers(monitor, token))
    repeated_start = monitor.post(f"{base}/start", headers=_reviewer_headers(monitor, token))
    stopped = monitor.post(f"{base}/stop", headers=_reviewer_headers(monitor, token))
    repeated_stop = monitor.post(f"{base}/stop", headers=_reviewer_headers(monitor, token))
    snapshot = monitor.get(f"{base}/snapshot", headers={"Authorization": f"Bearer {token}"})

    assert blocked.status_code == 409
    assert consent.json()["state"] == "CONSENT_CONFIRMED"
    assert preflight.json()["state"] == "PREFLIGHT_READY"
    assert started.json()["state"] == "RECORDING"
    assert repeated_start.json() == started.json()
    assert stopped.json()["state"] == "SEALED"
    assert repeated_stop.json() == stopped.json()
    assert snapshot.json()["state"] == "SEALED"
    assert "path" not in snapshot.text.lower()


def test_exam_answers_and_submit_are_idempotent_for_the_paired_candidate() -> None:
    exam, monitor, session_id, token = _paired_clients()
    base = f"/api/v1/sessions/{session_id}"
    exam.post(f"{base}/consent", headers=_candidate_headers(exam))
    exam.post(f"{base}/preflight", headers=_candidate_headers(exam))
    monitor.post(f"{base}/start", headers=_reviewer_headers(monitor, token))
    answer = {"answer_id": "a-1", "question_id": "q-1", "value": "42"}

    first_answer = exam.post("/api/v1/exam/answers", json=answer, headers=_candidate_headers(exam))
    replayed_answer = exam.post(
        "/api/v1/exam/answers", json=answer, headers=_candidate_headers(exam)
    )
    first_submit = exam.post("/api/v1/exam/submit", headers=_candidate_headers(exam))
    replayed_submit = exam.post("/api/v1/exam/submit", headers=_candidate_headers(exam))

    assert first_answer.status_code == 200
    assert first_answer.json()["accepted"] is True
    assert replayed_answer.json()["accepted"] is True
    assert first_submit.json()["submitted"] is True
    assert replayed_submit.json()["submitted"] is True
