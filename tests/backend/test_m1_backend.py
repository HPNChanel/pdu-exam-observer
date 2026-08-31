# ruff: noqa: E501

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_monitor_app
from pdu_exam_observer.configuration import (
    ConfigurationError,
    configure_storage_root,
    load_native_config,
)
from pdu_exam_observer.contracts import SessionKind, SessionState
from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m1 import M1Backend, M1Store, SchemaIntegrityError


def _headers(client: TestClient, token: str) -> dict[str, str]:
    return {"Origin": str(client.base_url).rstrip("/"), "Authorization": f"Bearer {token}"}


def _monitor(root: Path) -> tuple[TestClient, M1Backend, str]:
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    config = AppConfig(
        "123456",
        "http://exam.local",
        "http://monitor.local",
        ("exam.local", "monitor.local"),
        backend=backend,
    )
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    login = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": config.monitor_origin}
    )
    return monitor, backend, str(login.json()["access_token"])


def test_native_config_requires_an_absolute_writable_non_bundle_root(tmp_path: Path) -> None:
    config_path = tmp_path / "native" / "config.v1.json"
    root = tmp_path / "research-root"
    configured = configure_storage_root(
        root, config_path=config_path, encryption_status="UNKNOWN", acl_status="UNKNOWN"
    )
    loaded = load_native_config(config_path=config_path)
    assert configured.root == root.resolve()
    assert loaded.encryption_status == "UNKNOWN"
    with pytest.raises(ConfigurationError, match="absolute"):
        configure_storage_root(Path("relative-root"), config_path=config_path)
    with pytest.raises(ConfigurationError, match="outside"):
        configure_storage_root(
            tmp_path / "bundle", config_path=config_path, forbidden_roots=(tmp_path / "bundle",)
        )


def test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger(tmp_path: Path) -> None:
    root = tmp_path / "research-root"
    store = M1Store(root)
    assert (root / "operational" / "pdu-exam-observer.sqlite3").is_file()
    store.close()
    M1Store(root).close()

    database = root / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO schema_migrations(version, applied_at_utc, checksum) VALUES(99, 'future', 'future')"
    )
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError, match="newer"):
        M1Store(root)

    root2 = tmp_path / "tampered-root"
    M1Store(root2).close()
    database2 = root2 / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database2)
    connection.execute("UPDATE schema_migrations SET checksum = 'tampered' WHERE version = 1")
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError, match="checksum"):
        M1Store(root2)


def test_m1_research_routes_persist_without_auth_or_path_leakage(tmp_path: Path) -> None:
    monitor, backend, token = _monitor(tmp_path / "root")
    headers = _headers(monitor, token)
    assert (
        monitor.post(
            "/api/v1/research/studies",
            json={"study_code": "pilot-01"},
            headers={"Origin": str(monitor.base_url).rstrip("/")},
        ).status_code
        == 401
    )
    study = monitor.post(
        "/api/v1/research/studies",
        json={"study_code": "pilot-01"},
        headers={**headers, "Idempotency-Key": "study-1"},
    )
    participant = monitor.post(
        "/api/v1/research/participants",
        json={"study_id": study.json()["study_id"]},
        headers={**headers, "Idempotency-Key": "participant-1"},
    )
    session = monitor.post(
        "/api/v1/research/sessions",
        json={
            "study_id": study.json()["study_id"],
            "participant_id": participant.json()["participant_id"],
        },
        headers={**headers, "Idempotency-Key": "session-1"},
    )
    body = f"{study.text}{participant.text}{session.text}".lower()
    assert participant.json()["participant_pseudonym"].startswith("p-")
    assert "path" not in body
    assert str(tmp_path).lower() not in body
    assert "pin" not in body and "bearer" not in body
    assert session.json()["session_kind"] == SessionKind.RESEARCH

    session_id = session.json()["session_id"]
    readiness = monitor.get(f"/api/v1/research/sessions/{session_id}/readiness", headers=headers)
    assert readiness.json()["ready"] is False
    assert "INSTITUTIONAL_APPROVAL_REQUIRED" in readiness.json()["blocking_gates"]
    assert backend.start_research_session(session_id) is False

    restored = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    assert (
        restored.research_session(session_id)["participant_pseudonym"]
        == participant.json()["participant_pseudonym"]
    )
    assert restored.candidate_session("old-memory-token") is None


def test_m1_restart_replays_durable_events_and_idempotency_without_candidate_auth(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    record, _pairing = backend.create_session()
    backend.apply_session_action(record.session_id, "consent")
    backend.apply_session_action(record.session_id, "preflight")
    backend.apply_session_action(record.session_id, "start")
    payload = {"answer_id": "a-1", "question_id": "q-1", "value": "A"}
    assert backend.record_answer(record.session_id, "answer-1", payload)["accepted"] is True
    backend.store.close()

    restored = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    assert restored.snapshot(record.session_id).state is SessionState.RECORDING  # type: ignore[union-attr]
    assert restored.record_answer(record.session_id, "answer-1", payload)["accepted"] is True
    assert [event["type"] for event in restored.events_after(record.session_id, 0)].count(
        "AnswerRecorded"
    ) == 1
    assert restored.candidate_session("pre-restart-candidate-token") is None


def test_m1_research_session_rejects_every_generic_lifecycle_action(tmp_path: Path) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    study = backend.create_study("pilot-03")
    participant = backend.create_participant(str(study["study_id"]))
    research = backend.create_research_session(
        str(study["study_id"]), str(participant["participant_id"])
    )
    session_id = str(research["session_id"])

    for action in ("consent", "preflight", "start", "stop"):
        with pytest.raises(InvalidTransition):
            backend.apply_session_action(session_id, action)
        assert backend.snapshot(session_id).state is SessionState.DRAFT  # type: ignore[union-attr]


def test_m1_withdrawal_is_terminal_idempotent_and_invalidates_transitive_lineage(
    tmp_path: Path,
) -> None:
    monitor, backend, token = _monitor(tmp_path / "root")
    headers = _headers(monitor, token)
    study = monitor.post(
        "/api/v1/research/studies",
        json={"study_code": "pilot-02"},
        headers={**headers, "Idempotency-Key": "study-2"},
    ).json()
    participant = monitor.post(
        "/api/v1/research/participants",
        json={"study_id": study["study_id"]},
        headers={**headers, "Idempotency-Key": "participant-2"},
    ).json()
    session = monitor.post(
        "/api/v1/research/sessions",
        json={"study_id": study["study_id"], "participant_id": participant["participant_id"]},
        headers={**headers, "Idempotency-Key": "session-2"},
    ).json()
    backend.register_artifact("raw-a", session["session_id"])
    backend.register_artifact("derived-b", session["session_id"], parents=("raw-a",))
    first = monitor.post(
        f"/api/v1/research/sessions/{session['session_id']}/withdrawal",
        headers={**headers, "Idempotency-Key": "withdraw-2"},
    )
    second = monitor.post(
        f"/api/v1/research/sessions/{session['session_id']}/withdrawal",
        headers={**headers, "Idempotency-Key": "withdraw-2"},
    )
    status = monitor.get(
        f"/api/v1/research/sessions/{session['session_id']}/withdrawal-status", headers=headers
    )
    assert first.json() == second.json()
    assert status.json()["terminal"] is True
    assert status.json()["task_count"] == 2
    assert backend.artifact_status("raw-a") == "INVALIDATED"
    assert backend.artifact_status("derived-b") == "INVALIDATED"
    assert backend.recovery(session["session_id"])["collection_blocked"] is True
