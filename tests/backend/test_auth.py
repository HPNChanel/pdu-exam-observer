# ruff: noqa: E501

import pytest
from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app
from pdu_exam_observer.services.core import M0Backend, ReviewerClockInvalid


class Clock:
    def __init__(self, value: float = 1_700_000_000.0) -> None:
        self.value = value
        self.monotonic_value = 1_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds

    def monotonic(self) -> float:
        return self.monotonic_value

    def advance_monotonic(self, seconds: float) -> None:
        self.monotonic_value += seconds


def _apps(backend: M0Backend | None = None) -> tuple[TestClient, TestClient]:
    config = AppConfig(
        reviewer_pin="123456",
        exam_origin="http://exam.local",
        monitor_origin="http://monitor.local",
        allowed_hosts=("exam.local", "monitor.local", "testserver"),
        backend=backend or M0Backend(),
    )
    return (
        TestClient(create_exam_app(config), base_url="http://exam.local"),
        TestClient(create_monitor_app(config), base_url="http://monitor.local"),
    )


def _candidate_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": str(client.base_url).rstrip("/"),
        "X-CSRF-Token": client.cookies["pdu_exam_csrf"],
    }


def _reviewer_headers(client: TestClient, token: str) -> dict[str, str]:
    return {
        "Origin": str(client.base_url).rstrip("/"),
        "Authorization": f"Bearer {token}",
    }


def _login(monitor: TestClient) -> dict[str, object]:
    response = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": "http://monitor.local"}
    )
    assert response.status_code == 200
    return response.json()


def test_reviewer_login_returns_a_tab_bearer_without_reviewer_cookies_and_supports_session_logout() -> (
    None
):
    _, monitor = _apps()

    rejected = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "bad"}, headers={"Origin": "http://monitor.local"}
    )
    accepted = _login(monitor)

    assert rejected.status_code == 401
    assert accepted["schema_version"] == 1
    assert accepted["token_type"] == "Bearer"
    assert isinstance(accepted["access_token"], str)
    assert len(accepted["access_token"]) >= 43
    assert isinstance(accepted["expires_at_utc"], str)
    assert accepted["reviewer"] == "Nghi\u00ean c\u1ee9u vi\u00ean"
    assert "reviewer_session" not in monitor.cookies
    assert "pdu_monitor_csrf" not in monitor.cookies

    token = str(accepted["access_token"])
    session = monitor.get("/api/v1/reviewer/session", headers={"Authorization": f"Bearer {token}"})
    logged_out = monitor.post("/api/v1/reviewer/logout", headers=_reviewer_headers(monitor, token))
    rejected_after_logout = monitor.get(
        "/api/v1/reviewer/session", headers={"Authorization": f"Bearer {token}"}
    )

    assert session.status_code == 200
    assert session.json()["reviewer"] == "Nghi\u00ean c\u1ee9u vi\u00ean"
    assert logged_out.status_code == 204
    assert rejected_after_logout.status_code == 401
    assert rejected_after_logout.headers["www-authenticate"] == "Bearer"


def test_pairing_code_can_be_used_once_and_candidate_isolated_from_monitor() -> None:
    exam, monitor = _apps()
    token = str(_login(monitor)["access_token"])
    created = monitor.post("/api/v1/sessions", headers=_reviewer_headers(monitor, token))

    assert created.status_code == 201
    pairing_code = created.json()["pairing_code"]
    paired = exam.post(
        "/api/v1/candidate/pair",
        json={"pairing_code": pairing_code},
        headers={"Origin": "http://exam.local"},
    )
    reused = exam.post(
        "/api/v1/candidate/pair",
        json={"pairing_code": pairing_code},
        headers={"Origin": "http://exam.local"},
    )

    assert paired.status_code == 200
    assert "candidate_session" in paired.headers["set-cookie"]
    assert reused.status_code == 409
    forbidden = monitor.get("/api/v1/events", headers={"Cookie": "reviewer_session=legacy"})
    assert forbidden.status_code == 401
    assert forbidden.headers["www-authenticate"] == "Bearer"
    assert 'reviewer_session=""' in forbidden.headers["set-cookie"]


def test_state_changes_reject_bad_origin_or_missing_csrf() -> None:
    _, monitor = _apps()
    token = str(_login(monitor)["access_token"])

    missing_bearer = monitor.post("/api/v1/sessions", headers={"Origin": "http://monitor.local"})
    bad_origin = monitor.post(
        "/api/v1/sessions",
        headers={
            "Origin": "http://evil.invalid",
            "Authorization": f"Bearer {token}",
        },
    )

    assert missing_bearer.status_code == 401
    assert missing_bearer.headers["www-authenticate"] == "Bearer"
    assert bad_origin.status_code == 403


def test_every_reviewer_rest_and_stream_route_requires_a_well_formed_bearer() -> None:
    _, monitor = _apps()
    requests = (
        lambda: monitor.get("/api/v1/reviewer/session"),
        lambda: monitor.post("/api/v1/reviewer/logout", headers={"Origin": "http://monitor.local"}),
        lambda: monitor.post("/api/v1/sessions", headers={"Origin": "http://monitor.local"}),
        lambda: monitor.get("/api/v1/events?session_id=missing"),
        lambda: monitor.post(
            "/api/v1/events/stream",
            json={"session_id": "missing", "after_event_seq": 0},
            headers={"Origin": "http://monitor.local"},
        ),
        lambda: monitor.post(
            "/api/v1/demo/replay",
            json={"session_id": "missing"},
            headers={"Origin": "http://monitor.local"},
        ),
        lambda: monitor.get("/api/v1/sessions/missing/snapshot"),
        lambda: monitor.post(
            "/api/v1/sessions/missing/start", headers={"Origin": "http://monitor.local"}
        ),
        lambda: monitor.post(
            "/api/v1/sessions/missing/stop", headers={"Origin": "http://monitor.local"}
        ),
    )

    for request in requests:
        response = request()
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    malformed = monitor.get(
        "/api/v1/reviewer/session", headers={"Authorization": "Bearer token extra"}
    )
    assert malformed.status_code == 401
    assert malformed.headers["www-authenticate"] == "Bearer"


def test_reviewer_bearer_replacement_and_two_hour_absolute_expiry_revoke_access() -> None:
    clock = Clock()
    _, monitor = _apps(M0Backend(clock=clock))
    first = str(_login(monitor)["access_token"])
    second = str(_login(monitor)["access_token"])

    assert first != second
    first_session = monitor.get(
        "/api/v1/reviewer/session", headers={"Authorization": f"Bearer {first}"}
    )
    second_session = monitor.get(
        "/api/v1/reviewer/session", headers={"Authorization": f"Bearer {second}"}
    )
    assert first_session.status_code == 401
    assert second_session.status_code == 200

    clock.advance(7_199)
    valid_before_expiry = monitor.get(
        "/api/v1/reviewer/session", headers={"Authorization": f"Bearer {second}"}
    )
    assert valid_before_expiry.status_code == 200
    clock.advance(1)
    expired = monitor.get("/api/v1/reviewer/session", headers={"Authorization": f"Bearer {second}"})
    assert expired.status_code == 401
    assert expired.headers["www-authenticate"] == "Bearer"


def test_reviewer_bearer_uses_elapsed_time_when_wall_clock_is_rolled_back() -> None:
    clock = Clock()
    _, monitor = _apps(M0Backend(clock=clock, monotonic_clock=clock.monotonic))
    token = str(_login(monitor)["access_token"])

    clock.advance(30)
    clock.advance_monotonic(7_200)
    expired = monitor.get(
        "/api/v1/reviewer/session", headers={"Authorization": f"Bearer {token}"}
    )

    assert expired.status_code == 401
    assert expired.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("invalid_time", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("invalid_source", ["wall", "monotonic"])
def test_reviewer_bearer_rejects_nonfinite_time_at_issuance(
    invalid_time: float, invalid_source: str
) -> None:
    clock = Clock()
    if invalid_source == "wall":
        clock.value = invalid_time
    else:
        clock.monotonic_value = invalid_time
    backend = M0Backend(clock=clock, monotonic_clock=clock.monotonic)

    with pytest.raises(ReviewerClockInvalid, match="CLOCK_INVALID"):
        backend.issue_reviewer_token()


def test_reviewer_login_reports_clock_failure_as_technical_insufficient() -> None:
    clock = Clock(float("nan"))
    _, monitor = _apps(M0Backend(clock=clock, monotonic_clock=clock.monotonic))

    response = monitor.post(
        "/api/v1/reviewer/login",
        json={"pin": "123456"},
        headers={"Origin": "http://monitor.local"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "TECHNICAL_INSUFFICIENT"}}


@pytest.mark.parametrize("invalid_time", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("invalid_source", ["wall", "monotonic"])
def test_reviewer_bearer_rejects_nonfinite_time_during_validation(
    invalid_time: float, invalid_source: str
) -> None:
    clock = Clock()
    backend = M0Backend(clock=clock, monotonic_clock=clock.monotonic)
    token = backend.issue_reviewer_token()
    if invalid_source == "wall":
        clock.value = invalid_time
    else:
        clock.monotonic_value = invalid_time

    assert backend.is_reviewer(token) is False
