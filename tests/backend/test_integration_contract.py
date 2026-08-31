from pathlib import Path

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
    candidate_headers = {
        "Origin": "http://exam.local",
        "X-CSRF-Token": exam.cookies["pdu_exam_csrf"],
    }
    for action in ("consent", "preflight", "start"):
        exam.post(f"/api/v1/sessions/{created['session_id']}/{action}", headers=candidate_headers)
    return exam, monitor, created["session_id"], token


def test_replay_uses_canonical_null_confidence_without_alert_labels() -> None:
    _, monitor, session_id, token = _recording_session()

    replayed = monitor.post(
        "/api/v1/demo/replay",
        json={"session_id": session_id},
        headers=_reviewer_headers(monitor, token),
    )
    events = replayed.json()["events"]
    assert replayed.status_code == 200
    assert all(event["confidence"] is None for event in events)
    assert [event["confidence_status"] for event in events] == [
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "INSUFFICIENT",
        "NOT_APPLICABLE",
    ]
    event_sequences = [event["event_seq"] for event in events]
    assert event_sequences == sorted(event_sequences)
    assert all("label" not in event for event in events)


def test_static_shells_are_origin_scoped_and_api_routes_remain_reachable(tmp_path: Path) -> None:
    static_dir = tmp_path / "web"
    assets = static_dir / "assets"
    assets.mkdir(parents=True)
    (static_dir / "index.html").write_text(
        '<script src="./assets/app.js"></script>', encoding="utf-8"
    )
    (assets / "app.js").write_text("window.pdu = true;", encoding="utf-8")
    config = AppConfig(
        "123456",
        "http://exam.local",
        "http://monitor.local",
        ("exam.local", "monitor.local"),
        static_dir=static_dir,
    )

    exam = TestClient(create_exam_app(config), base_url="http://exam.local")
    monitor = TestClient(create_monitor_app(config), base_url="http://monitor.local")

    assert exam.get("/exam").status_code == 200
    assert monitor.get("/monitor").status_code == 200
    assert exam.get("/monitor").status_code == 404
    assert monitor.get("/exam").status_code == 404
    assert exam.get("/assets/app.js").text == "window.pdu = true;"
    assert monitor.get("/api/v1/health").json() == {"schema_version": 1, "status": "ok"}


def test_required_browser_security_headers_apply_to_normal_and_rejected_responses() -> None:
    config = AppConfig(
        "123456", "http://exam.local", "http://monitor.local", ("exam.local", "monitor.local")
    )
    app = TestClient(create_monitor_app(config), base_url="http://monitor.local")

    for response in (
        app.get("/api/v1/health"),
        app.post(
            "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": "http://bad"}
        ),
    ):
        assert response.headers["content-security-policy"] == (
            "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["permissions-policy"] == (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )


def test_each_origin_serves_explicit_favicons_without_shadowing_api(tmp_path: Path) -> None:
    static_dir = tmp_path / "web"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text("<main>test</main>", encoding="utf-8")
    (static_dir / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (static_dir / "favicon.ico").write_bytes(b"icon")
    config = AppConfig(
        "123456",
        "http://exam.local",
        "http://monitor.local",
        ("exam.local", "monitor.local"),
        static_dir=static_dir,
    )

    for factory, origin in (
        (create_exam_app, config.exam_origin),
        (create_monitor_app, config.monitor_origin),
    ):
        client = TestClient(factory(config), base_url=origin)
        svg = client.get("/favicon.svg")
        icon = client.get("/favicon.ico")

        assert svg.status_code == 200
        assert svg.headers["content-type"].startswith("image/svg+xml")
        assert svg.headers["cache-control"] == "no-store"
        assert icon.status_code == 200
        assert icon.headers["content-type"].startswith("image/x-icon")
        assert icon.headers["cache-control"] == "no-store"
        assert client.get("/api/v1/health").json() == {"schema_version": 1, "status": "ok"}
