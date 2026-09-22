import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pdu_exam_observer.launcher import _close_synthetic_review_service, build_apps_from_environment


def test_workspace_exam_review_export_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PDU_RUNTIME_MODE", "m2research")
    monkeypatch.setenv("PDU_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PDU_REVIEWER_PIN", "integration-only-pin")
    exam_app, monitor_app = build_apps_from_environment()
    monitor = TestClient(monitor_app, base_url="http://localhost:8766")
    exam = TestClient(exam_app, base_url="http://127.0.0.1:8765")
    try:
        response = monitor.post(
            "/api/v1/reviewer/login",
            json={"pin": "integration-only-pin"},
            headers={"Origin": "http://localhost:8766"},
        )
        headers = {
            "Origin": "http://localhost:8766",
            "Authorization": f"Bearer {response.json()['access_token']}",
        }
        count = 0

        def post(path: str, payload: object = None):
            nonlocal count
            count += 1
            return monitor.post(
                "/api/v1/workspace" + path,
                json=payload,
                headers={**headers, "Idempotency-Key": f"integration-{count}"},
            )

        created = post("/sessions", {"source_kind": "AI_RENDERED"})
        assert created.status_code == 201, created.text
        row = created.json()
        sid, exam_id = row["session_id"], row["exam_session_id"]
        assert "artifact_directory" not in created.text
        paired = exam.post(
            "/api/v1/candidate/pair",
            json={"pairing_code": row["pairing_code"]},
            headers={"Origin": "http://127.0.0.1:8765"},
        )
        assert paired.status_code == 200
        candidate_headers = {
            "Origin": "http://127.0.0.1:8765",
            "X-CSRF-Token": exam.cookies["pdu_exam_csrf"],
        }
        for action in ("consent", "preflight"):
            assert (
                exam.post(
                    f"/api/v1/sessions/{exam_id}/{action}", headers=candidate_headers
                ).status_code
                == 200
            )
        assert post(f"/sessions/{sid}/preflight").status_code == 200
        start = post(f"/sessions/{sid}/start")
        assert start.status_code == 200, start.text
        assert exam.get("/api/v1/exam/status").json()["state"] == "RECORDING"
        assert (
            exam.post(
                "/api/v1/exam/focus", json={"focused": True}, headers=candidate_headers
            ).status_code
            == 204
        )
        assert (
            exam.post(
                "/api/v1/exam/focus",
                json={"focused": True, "window_title": "private"},
                headers=candidate_headers,
            ).status_code
            == 422
        )
        answer = exam.post(
            "/api/v1/exam/answers",
            json={"answer_id": "q1-B", "question_id": "q1", "value": "B"},
            headers={**candidate_headers, "Idempotency-Key": "answer-one"},
        )
        assert answer.status_code == 200, answer.text
        assert post(f"/sessions/{sid}/stop").status_code == 200
        assert post(f"/sessions/{sid}/seal").status_code == 200
        assert post(f"/sessions/{sid}/lock").status_code == 409
        detail = monitor.get(f"/api/v1/workspace/sessions/{sid}", headers=headers).json()
        assert detail["events"]
        for event in detail["events"]:
            current = monitor.get(f"/api/v1/workspace/sessions/{sid}", headers=headers).json()
            payload = {
                "event_id": event["event_id"],
                "label": event["research_label"],
                "review_status": "CONFIRMED",
                "start_ms": event["start_ms"],
                "end_ms": event["end_ms"],
                "reason": "Synthetic integration fixture",
                "expected_revision": current["revision"],
            }
            decision = monitor.put(
                f"/api/v1/workspace/sessions/{sid}/decision",
                json=payload,
                headers={**headers, "Idempotency-Key": f"review-{event['event_id']}"},
            )
            assert decision.status_code == 200, decision.text
        preview = monitor.get(f"/api/v1/workspace/sessions/{sid}/preview", headers=headers)
        assert preview.status_code == 200, preview.text[:100]
        assert "video/" in preview.headers["content-type"]
        assert post(f"/sessions/{sid}/lock").status_code == 200
        exported = monitor.get(f"/api/v1/workspace/sessions/{sid}/export", headers=headers)
        assert exported.status_code == 200, exported.text[:100]
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            assert all(not name.endswith((".mp4", ".avi", ".db")) for name in archive.namelist())
        assert exam.get(f"/api/v1/workspace/sessions/{sid}/export").status_code == 404
        assert post(f"/sessions/{sid}/withdraw-test").status_code == 200
        assert (
            monitor.get(f"/api/v1/workspace/sessions/{sid}/export", headers=headers).status_code
            == 409
        )
    finally:
        _close_synthetic_review_service(monitor_app)
