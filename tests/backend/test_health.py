from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app


def test_each_origin_exposes_no_store_health() -> None:
    config = AppConfig(
        reviewer_pin="123456",
        exam_origin="http://exam.local",
        monitor_origin="http://monitor.local",
        allowed_hosts=("exam.local", "monitor.local", "testserver"),
    )

    for factory in (create_exam_app, create_monitor_app):
        base_url = "http://exam.local" if factory is create_exam_app else "http://monitor.local"
        response = TestClient(factory(config), base_url=base_url).get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"schema_version": 1, "status": "ok"}
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-security-policy"] == (
            "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        assert response.headers["x-content-type-options"] == "nosniff"


def test_security_headers_apply_to_rejected_state_change() -> None:
    config = AppConfig(
        reviewer_pin="123456",
        exam_origin="http://exam.local",
        monitor_origin="http://monitor.local",
        allowed_hosts=("exam.local", "monitor.local"),
    )
    response = TestClient(create_monitor_app(config), base_url="http://monitor.local").post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": "http://evil.invalid"}
    )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-security-policy"] == (
        "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
