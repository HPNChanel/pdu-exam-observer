from pathlib import Path

from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app


class FakeWorkspace:
    def summary(self) -> dict[str, object]:
        return {"schema_version": 1, "sessions": [], "model": {"status": "MODEL_UNAVAILABLE"}}

    def create(self, source_kind: str, key: str) -> dict[str, object]:
        return {"session_id": "runtime-one", "source_kind": source_kind}


def test_workspace_requires_reviewer_and_is_absent_from_exam(tmp_path: Path) -> None:
    config = AppConfig(
        reviewer_pin="123456",
        exam_origin="http://127.0.0.1:8765",
        monitor_origin="http://localhost:8766",
        allowed_hosts=("localhost", "127.0.0.1"),
        workspace=FakeWorkspace(),
    )
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    exam = TestClient(create_exam_app(config), base_url=config.exam_origin)
    assert monitor.get("/api/v1/workspace").status_code == 401
    assert "media-src 'self' blob:" in monitor.get("/monitor").headers["content-security-policy"]
    assert "blob:" not in exam.get("/exam").headers["content-security-policy"]
    login = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": config.monitor_origin}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Origin": config.monitor_origin}
    assert monitor.get("/api/v1/workspace", headers=headers).status_code == 200
    assert exam.get("/api/v1/workspace", headers=headers).status_code in (403, 404)
    assert (
        monitor.post(
            "/api/v1/workspace/sessions",
            headers=headers,
            json={"source_kind": "AI_RENDERED", "path": "C:/private"},
        ).status_code
        == 422
    )
    assert (
        monitor.post(
            "/api/v1/workspace/sessions", headers=headers, json={"source_kind": "AI_RENDERED"}
        ).status_code
        == 422
    )
    monitor.post("/api/v1/reviewer/logout", headers=headers)
    assert monitor.get("/api/v1/workspace", headers=headers).status_code == 401
