import pytest
from fastapi.testclient import TestClient

import pdu_exam_observer.launcher as launcher
from pdu_exam_observer.launcher import build_apps_from_environment, should_open_browser


def test_launcher_requires_external_pin_and_builds_two_loopback_apps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PDU_REVIEWER_PIN", raising=False)
    with pytest.raises(RuntimeError, match="PDU_REVIEWER_PIN"):
        build_apps_from_environment()

    monkeypatch.setenv("PDU_REVIEWER_PIN", "test-only-pin")
    exam, monitor = build_apps_from_environment()

    assert (
        TestClient(exam, base_url="http://127.0.0.1:8765").get("/api/v1/health").status_code == 200
    )
    assert (
        TestClient(monitor, base_url="http://localhost:8766").get("/api/v1/health").status_code
        == 200
    )


def test_launcher_allows_headless_mode_without_opening_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PDU_OPEN_BROWSER", "0")
    assert should_open_browser() is False
    monkeypatch.setenv("PDU_OPEN_BROWSER", "1")
    assert should_open_browser() is True


def test_launcher_binds_both_servers_to_literal_ipv4_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configs = []

    class RecordingServer:
        def __init__(self, config: object) -> None:
            self.config = config
            self.started = False
            self.should_exit = False
            configs.append(config)

        def run(self) -> None:
            self.started = True

    class SynchronousThread:
        def __init__(self, *, target: object, name: str, daemon: bool) -> None:
            self._target = target

        def start(self) -> None:
            self._target()  # type: ignore[operator]

        def is_alive(self) -> bool:
            return False

        def join(self, timeout: float | None = None) -> None:
            return None

    monkeypatch.setenv("PDU_REVIEWER_PIN", "test-only-pin")
    monkeypatch.setenv("PDU_OPEN_BROWSER", "0")
    monkeypatch.setattr(launcher.uvicorn, "Server", RecordingServer)
    monkeypatch.setattr(launcher, "Thread", SynchronousThread)

    launcher.main()

    assert [config.host for config in configs] == ["127.0.0.1", "127.0.0.1"]


def test_launcher_m2synthetic_injects_monitor_only_service_and_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []

    class Service:
        @classmethod
        def create_owned(cls) -> "Service":
            instance = cls()
            instance.closed = False
            created.append(instance)
            return instance

        def close(self) -> None:
            self.closed = True

    monkeypatch.setenv("PDU_REVIEWER_PIN", "test-only-pin")
    monkeypatch.setenv("PDU_RUNTIME_MODE", "m2synthetic")
    monkeypatch.setattr(launcher, "SyntheticReviewService", Service)

    exam, monitor = launcher.build_apps_from_environment()
    assert exam.state.synthetic_review_service is None
    assert monitor.state.synthetic_review_service is created[0]
    launcher._close_synthetic_review_service(monitor)
    assert created[0].closed is True  # type: ignore[attr-defined]
