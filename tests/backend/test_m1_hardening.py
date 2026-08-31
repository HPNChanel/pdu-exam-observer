# ruff: noqa: E501

import asyncio
import ctypes
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from threading import Barrier, Event, RLock
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pdu_exam_observer import configuration
from pdu_exam_observer.api.factories import AppConfig, create_monitor_app
from pdu_exam_observer.configuration import ConfigurationError, load_native_config
from pdu_exam_observer.contracts import ReadinessGateCode, SessionState
from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m1 import M1Backend, M1Store, SchemaIntegrityError


def _monitor(root: Path) -> tuple[TestClient, M1Backend, dict[str, str]]:
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    config = AppConfig(
        "123456",
        "http://exam.local",
        "http://monitor.local",
        ("exam.local", "monitor.local"),
        backend=backend,
    )
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    token = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": config.monitor_origin}
    ).json()["access_token"]
    return monitor, backend, {"Origin": config.monitor_origin, "Authorization": f"Bearer {token}"}


def _post(
    client: TestClient, path: str, payload: dict[str, object], headers: dict[str, str], key: str
) -> object:
    return client.post(path, json=payload, headers={**headers, "Idempotency-Key": key})


def _research(
    backend: M1Backend, code: str, retention: str | None = None
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    study = backend.create_study(code, idempotency_key=f"study-{code}")
    participant = backend.create_participant(
        str(study["study_id"]), idempotency_key=f"participant-{code}"
    )
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key=f"session-{code}",
        retention_policy_reference=retention,
    )
    return study, participant, session


def test_load_revalidates_tampered_relative_and_bundle_roots(tmp_path: Path) -> None:
    config = tmp_path / "config.v1.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "root": "relative",
                "encryption_status": "UNKNOWN",
                "acl_status": "UNKNOWN",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="absolute"):
        load_native_config(config_path=config)
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "root": str(Path(__file__).resolve().parents[2]),
                "encryption_status": "UNKNOWN",
                "acl_status": "UNKNOWN",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="outside"):
        load_native_config(config_path=config)


def test_windows_storage_root_rejects_unc_before_filesystem_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("UNC root reached filesystem resolution")
        ),
    )
    with pytest.raises(ConfigurationError, match="UNC"):
        configuration.validate_storage_root(Path(r"\\server\share\research"), create=False)


@pytest.mark.parametrize("failure", ["zero", "exception"])
def test_windows_ntfs_inspection_failures_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    class Kernel32:
        @staticmethod
        def GetVolumeInformationW(*args: object) -> int:
            if failure == "exception":
                raise OSError("inspection failed")
            return 0

    class Windll:
        kernel32 = Kernel32()

    monkeypatch.setattr(ctypes, "windll", Windll())
    with pytest.raises(ConfigurationError, match="inspect NTFS"):
        configuration._check_ntfs(tmp_path)


def test_windows_ntfs_inspection_rejects_missing_drive(tmp_path: Path) -> None:
    del tmp_path
    with pytest.raises(ConfigurationError, match="drive"):
        configuration._check_ntfs(Path("\\research"))


def test_storage_root_reparse_inspection_fails_closed_on_lstat_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    original_lstat = Path.lstat

    def failing_lstat(path: Path) -> os.stat_result:
        if path == root:
            raise OSError("reparse inspection unavailable")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", failing_lstat)
    with pytest.raises(ConfigurationError, match="reparse"):
        configuration.validate_storage_root(root, create=False, forbidden_roots=())


def test_m1_store_rejects_redirected_operational_directory_before_database_creation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    operational = root / "operational"
    try:
        operational.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink creation is unavailable: {exc}")

    with pytest.raises(SchemaIntegrityError, match="operational|reparse|unsafe"):
        M1Store(root)
    assert not (outside / "pdu-exam-observer.sqlite3").exists()


def test_m1_store_rejects_redirected_database_file_before_open(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    store = M1Store(root)
    database = store.database_path
    store.close()
    database.unlink()
    outside_database = tmp_path / "redirected.sqlite3"
    outside_database.touch()
    try:
        database.symlink_to(outside_database)
    except OSError as exc:
        pytest.skip(f"file symlink creation is unavailable: {exc}")

    with pytest.raises(SchemaIntegrityError, match="database|reparse|unsafe"):
        M1Store(root)
    assert outside_database.stat().st_size == 0


def test_schema_refuses_dropped_object_and_requires_wal_and_critical_tables(tmp_path: Path) -> None:
    root = tmp_path / "root"
    store = M1Store(root)
    assert store.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    database = store.database_path
    store.close()
    connection = sqlite3.connect(database)
    connection.execute("DROP TABLE artifact_dependencies")
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError, match="schema object"):
        M1Store(root)


def _replace_table(database: Path, table: str, ddl: str) -> None:
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute(f"ALTER TABLE {table} RENAME TO discarded_{table}")
    connection.execute(ddl)
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    names = ",".join(columns)
    connection.execute(
        f"INSERT INTO {table}({names}) SELECT {names} FROM discarded_{table}"
    )
    connection.execute(f"DROP TABLE discarded_{table}")
    connection.commit()
    connection.close()


def test_schema_rejects_migration_ledger_without_primary_key(tmp_path: Path) -> None:
    store = M1Store(tmp_path / "root")
    database = store.database_path
    store.close()
    _replace_table(
        database,
        "schema_migrations",
        "CREATE TABLE schema_migrations(version INTEGER, applied_at_utc TEXT NOT NULL, checksum TEXT NOT NULL)",
    )
    with pytest.raises(SchemaIntegrityError, match="schema"):
        M1Store(tmp_path / "root")


def test_schema_rejects_withdrawal_tasks_without_unique_subject_artifact_pair(
    tmp_path: Path,
) -> None:
    store = M1Store(tmp_path / "root")
    database = store.database_path
    store.close()
    _replace_table(
        database,
        "withdrawal_tasks",
        "CREATE TABLE withdrawal_tasks(id TEXT PRIMARY KEY, withdrawal_subject_session_id TEXT NOT NULL REFERENCES sessions(id), artifact_id TEXT NOT NULL REFERENCES artifact_registry(id), status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETED')), created_at REAL NOT NULL)",
    )
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE INDEX idx_tasks_subject ON withdrawal_tasks(withdrawal_subject_session_id)"
    )
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError, match="schema object"):
        M1Store(tmp_path / "root")


def test_schema_rejects_write_intents_without_declared_session_foreign_key(
    tmp_path: Path,
) -> None:
    store = M1Store(tmp_path / "root")
    database = store.database_path
    store.close()
    _replace_table(
        database,
        "write_intents",
        "CREATE TABLE write_intents(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, manifest_relative_path TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','QUARANTINED')), created_at REAL NOT NULL)",
    )
    with pytest.raises(SchemaIntegrityError, match="schema object"):
        M1Store(tmp_path / "root")


def test_schema_rejects_write_intents_with_weakened_nullability(tmp_path: Path) -> None:
    store = M1Store(tmp_path / "root")
    database = store.database_path
    store.close()
    _replace_table(
        database,
        "write_intents",
        "CREATE TABLE write_intents(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), manifest_relative_path TEXT NOT NULL, status TEXT CHECK(status IN ('PENDING','QUARANTINED')), created_at REAL NOT NULL)",
    )
    with pytest.raises(SchemaIntegrityError, match="schema object"):
        M1Store(tmp_path / "root")


def test_schema_rejects_exam_attempts_with_missing_submitted_default(tmp_path: Path) -> None:
    store = M1Store(tmp_path / "root")
    database = store.database_path
    store.close()
    _replace_table(
        database,
        "exam_attempts",
        "CREATE TABLE exam_attempts(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), submitted INTEGER NOT NULL CHECK(submitted IN (0,1)), created_at REAL NOT NULL)",
    )
    with pytest.raises(SchemaIntegrityError, match="schema object"):
        M1Store(tmp_path / "root")


def test_schema_rejects_sessions_without_state_enum_check(tmp_path: Path) -> None:
    store = M1Store(tmp_path / "root")
    database = store.database_path
    store.close()
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA writable_schema=ON")
    connection.execute(
        "UPDATE sqlite_master SET sql=replace(sql, ?, ?) WHERE type='table' AND name='sessions'",
        (
            "state TEXT NOT NULL CHECK(state IN ('DRAFT','CONSENT_CONFIRMED','PREFLIGHT_READY','RECORDING','SEALED','FAILED','WITHDRAWN'))",
            "state TEXT NOT NULL",
        ),
    )
    connection.execute("PRAGMA writable_schema=OFF")
    connection.execute("PRAGMA schema_version=2")
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError, match="schema object"):
        M1Store(tmp_path / "root")


def test_schema_rejects_constraint_text_hidden_in_a_comment(tmp_path: Path) -> None:
    root = tmp_path / "root"
    store = M1Store(root)
    database = store.database_path
    store.close()
    active_constraint = "state TEXT NOT NULL CHECK(state IN ('DRAFT','CONSENT_CONFIRMED','PREFLIGHT_READY','RECORDING','SEALED','FAILED','WITHDRAWN'))"
    commented_constraint = "state TEXT NOT NULL /* CHECK(state IN ('DRAFT','CONSENT_CONFIRMED','PREFLIGHT_READY','RECORDING','SEALED','FAILED','WITHDRAWN')) */"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA writable_schema=ON")
    connection.execute(
        "UPDATE sqlite_master SET sql=replace(sql, ?, ?) WHERE type='table' AND name='sessions'",
        (active_constraint, commented_constraint),
    )
    connection.execute("PRAGMA writable_schema=OFF")
    connection.execute("PRAGMA schema_version=2")
    connection.commit()
    connection.close()

    with pytest.raises(SchemaIntegrityError, match="schema object"):
        M1Store(root)


def test_canonical_schema_accepts_fresh_and_reopened_database(tmp_path: Path) -> None:
    root = tmp_path / "root"
    store = M1Store(root)
    store.close()
    reopened = M1Store(root)
    assert reopened.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    reopened.close()


def test_m1_monitor_demo_replay_uses_durable_sqlite_events(tmp_path: Path) -> None:
    monitor, backend, headers = _monitor(tmp_path / "root")
    created = monitor.post("/api/v1/sessions", headers=headers).json()
    replay = _post(
        monitor, "/api/v1/demo/replay", {"session_id": created["session_id"]}, headers, "demo-1"
    )
    assert replay.status_code == 200
    assert replay.json()["events"] == backend.events_after(created["session_id"], 0)


def test_research_posts_require_keys_use_frozen_payloads_and_preserve_canonical_retries(
    tmp_path: Path,
) -> None:
    monitor, _backend, headers = _monitor(tmp_path / "root")
    missing = monitor.post("/api/v1/research/studies", json={"study_code": "s"}, headers=headers)
    extra = _post(
        monitor,
        "/api/v1/research/studies",
        {"study_code": "s", "path": "C:/secret"},
        headers,
        "study-1",
    )
    first = _post(monitor, "/api/v1/research/studies", {"study_code": "s"}, headers, "study-1")
    retry = _post(monitor, "/api/v1/research/studies", {"study_code": "s"}, headers, "study-1")
    conflict = _post(
        monitor, "/api/v1/research/studies", {"study_code": "other"}, headers, "study-1"
    )
    assert missing.status_code == 422
    assert extra.status_code == 422
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_concurrent_study_and_answer_retries_are_singleton_and_rollback_never_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: backend.create_study("parallel", idempotency_key="same"), range(2)
            )
        )
    assert results[0] == results[1]
    assert backend.store.connection.execute("SELECT COUNT(*) FROM studies").fetchone()[0] == 1

    session, _ = backend.create_session()
    for action in ("consent", "preflight", "start"):
        backend.apply_session_action(session.session_id, action)
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    backend._subscribers[session.session_id] = [queue]
    original = backend._event
    monkeypatch.setattr(
        backend, "_event", lambda *args: (_ for _ in ()).throw(RuntimeError("rollback"))
    )
    with pytest.raises(RuntimeError, match="rollback"):
        backend.record_answer(
            session.session_id, "answer", {"answer_id": "a", "question_id": "q", "value": "A"}
        )
    monkeypatch.setattr(backend, "_event", original)
    assert backend.events_after(session.session_id, 0)[-1]["type"] == "SessionStateChanged"
    assert queue.empty()


def test_simultaneous_duplicate_start_serializes_before_state_read(tmp_path: Path) -> None:
    root = tmp_path / "root"
    first = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    session, _ = first.create_session()
    first.apply_session_action(session.session_id, "consent")
    first.apply_session_action(session.session_id, "preflight")
    second = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    blocker = sqlite3.connect(first.store.database_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    launch = Barrier(3)
    began_transactions = (Event(), Event())

    def trace_begin(index: int) -> Any:
        def trace(statement: str) -> None:
            if statement.strip().upper() == "BEGIN IMMEDIATE":
                began_transactions[index].set()

        return trace

    first.store.connection.set_trace_callback(trace_begin(0))
    second.store.connection.set_trace_callback(trace_begin(1))

    def start(backend: M1Backend) -> object:
        launch.wait(timeout=5)
        try:
            return backend.apply_session_action(session.session_id, "start")
        except Exception as exc:  # asserted below so OperationalError cannot hide in a Future
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (executor.submit(start, first), executor.submit(start, second))
            launch.wait(timeout=5)
            both_waiting = all(event.wait(timeout=5) for event in began_transactions)
            blocker.execute("COMMIT")
            outcomes = tuple(future.result(timeout=5) for future in futures)
    finally:
        if blocker.in_transaction:
            blocker.execute("ROLLBACK")
        blocker.close()
        first.store.connection.set_trace_callback(None)
        second.store.connection.set_trace_callback(None)

    assert both_waiting
    assert not any(isinstance(outcome, sqlite3.OperationalError) for outcome in outcomes)
    assert all(
        (outcome is not None and getattr(outcome, "state", None) is SessionState.RECORDING)
        or isinstance(outcome, InvalidTransition | SchemaIntegrityError)
        for outcome in outcomes
    )
    recording_events = [
        event
        for event in first.events_after(session.session_id, 0)
        if event["type"] == "SessionStateChanged" and event["state"] == SessionState.RECORDING
    ]
    assert len(recording_events) == 1
    first.store.close()
    second.store.close()


class _LockCheckingConnection:
    def __init__(self, connection: sqlite3.Connection, lock: RLock) -> None:
        self._connection = connection
        self._lock = lock

    def execute(self, *args: Any, **kwargs: Any) -> sqlite3.Cursor:
        assert self._lock._is_owned(), "shared SQLite access occurred outside M1Store RLock"
        return self._connection.execute(*args, **kwargs)


def test_shared_connection_reads_and_writes_hold_store_lock(tmp_path: Path) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, research = _research(backend, "locking", retention="policy-2026")
    research_id = str(research["session_id"])
    backend.register_artifact("locking-artifact", research_id)
    raw_connection = backend.store.connection
    backend.store.connection = _LockCheckingConnection(  # type: ignore[assignment]
        raw_connection, backend.store._lock
    )

    def read_research() -> None:
        backend.research_session(research_id)
        backend.readiness(research_id)
        backend.withdrawal_status(research_id)
        backend.artifact_status("locking-artifact")

    def write_and_read_demo() -> None:
        demo, _ = backend.create_session()
        backend.snapshot(demo.session_id)
        backend.events_after(demo.session_id, 0)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(read_research), executor.submit(write_and_read_demo)]
        for future in futures:
            future.result()


def test_withdrawal_is_participant_wide_blocks_mutation_and_scopes_shared_artifact_tasks(
    tmp_path: Path,
) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    study1, participant1, session1 = _research(backend, "p1")
    session1b = backend.create_research_session(
        str(study1["study_id"]), str(participant1["participant_id"]), idempotency_key="p1-second"
    )
    _study2, participant2, session2 = _research(backend, "p2")
    backend.register_artifact("p1-raw", str(session1["session_id"]))
    backend.register_artifact("shared-derived", str(session1["session_id"]), parents=("p1-raw",))
    backend.register_artifact("p2-root", str(session2["session_id"]))
    backend.store.add_dependency("p2-root", "shared-derived")
    first = backend.withdraw(str(session1["session_id"]), idempotency_key="withdraw-p1")
    retry = backend.withdraw(str(session1["session_id"]), idempotency_key="withdraw-p1")
    assert first == retry
    assert backend.research_session(str(session1b["session_id"]))["state"] == SessionState.WITHDRAWN
    with pytest.raises(InvalidTransition):
        backend.confirm_operator_consent(
            str(session1b["session_id"]), "receipt", "v1", idempotency_key="consent"
        )
    with pytest.raises(InvalidTransition):
        backend.create_research_session(
            str(study1["study_id"]), str(participant1["participant_id"]), idempotency_key="blocked"
        )
    with pytest.raises(InvalidTransition):
        backend.register_artifact("late", str(session1b["session_id"]))
    second = backend.withdraw(str(session2["session_id"]), idempotency_key="withdraw-p2")
    assert first["task_count"] == 2
    assert second["task_count"] == 2


def test_artifact_parent_validation_rejects_missing_and_invalidated_parents(
    tmp_path: Path,
) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, session = _research(backend, "parent-validation")
    session_id = str(session["session_id"])
    with pytest.raises(InvalidTransition, match="parent"):
        backend.register_artifact("missing-child", session_id, parents=("missing",))
    backend.register_artifact("invalid-parent", session_id)
    backend.register_artifact("existing-child", session_id)
    backend.store.connection.execute(
        "UPDATE artifact_registry SET status='INVALIDATED' WHERE id='invalid-parent'"
    )
    with pytest.raises(InvalidTransition, match="parent"):
        backend.register_artifact("invalid-child", session_id, parents=("invalid-parent",))
    with pytest.raises(InvalidTransition, match="parent"):
        backend.store.add_dependency("invalid-parent", "existing-child")
    children = backend.store.connection.execute(
        "SELECT id FROM artifact_registry WHERE id IN ('missing-child','invalid-child')"
    ).fetchall()
    assert children == []


def test_withdrawn_cross_session_parent_cannot_gain_a_valid_descendant(
    tmp_path: Path,
) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    _study1, _participant1, withdrawn_session = _research(backend, "withdrawn-parent")
    _study2, _participant2, active_session = _research(backend, "active-child")
    withdrawn_session_id = str(withdrawn_session["session_id"])
    backend.register_artifact("withdrawn-parent", withdrawn_session_id)
    backend.withdraw(withdrawn_session_id, idempotency_key="withdraw-parent")
    backend.store.connection.execute(
        "UPDATE artifact_registry SET status='VALID' WHERE id='withdrawn-parent'"
    )

    with pytest.raises(InvalidTransition, match="parent"):
        backend.register_artifact(
            "post-withdraw-descendant",
            str(active_session["session_id"]),
            parents=("withdrawn-parent",),
        )
    assert backend.store.connection.execute(
        "SELECT 1 FROM artifact_registry WHERE id='post-withdraw-descendant'"
    ).fetchone() is None


def test_withdrawal_business_state_is_idempotent_across_distinct_request_keys(
    tmp_path: Path,
) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, session = _research(backend, "idempotent-withdrawal")
    session_id = str(session["session_id"])
    backend.register_artifact("artifact", session_id)
    first = backend.withdraw(session_id, idempotency_key="withdraw-first")
    before = {
        "events": backend.store.connection.execute(
            "SELECT COUNT(*) FROM session_events WHERE session_id=?", (session_id,)
        ).fetchone()[0],
        "audits": backend.store.connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE session_id=?", (session_id,)
        ).fetchone()[0],
        "tasks": backend.store.connection.execute(
            "SELECT COUNT(*) FROM withdrawal_tasks WHERE withdrawal_subject_session_id=?",
            (session_id,),
        ).fetchone()[0],
    }
    repeated = backend.withdraw(session_id, idempotency_key="withdraw-second")
    after = {
        "events": backend.store.connection.execute(
            "SELECT COUNT(*) FROM session_events WHERE session_id=?", (session_id,)
        ).fetchone()[0],
        "audits": backend.store.connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE session_id=?", (session_id,)
        ).fetchone()[0],
        "tasks": backend.store.connection.execute(
            "SELECT COUNT(*) FROM withdrawal_tasks WHERE withdrawal_subject_session_id=?",
            (session_id,),
        ).fetchone()[0],
    }
    assert repeated == first
    assert after == before


def test_withdrawal_receipt_and_status_are_canonical_across_participant_sessions(
    tmp_path: Path,
) -> None:
    backend = M1Backend(tmp_path / "root", encryption_status="VERIFIED", acl_status="VERIFIED")
    study, participant, session_a = _research(backend, "participant-receipt")
    session_b = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key="participant-receipt-b",
    )
    session_a_id = str(session_a["session_id"])
    session_b_id = str(session_b["session_id"])
    backend.register_artifact("participant-a", session_a_id)
    backend.register_artifact("participant-b", session_b_id)
    first = backend.withdraw(session_a_id, idempotency_key="withdraw-via-a")
    participant_id = str(participant["participant_id"])
    before = {
        "events": backend.store.connection.execute(
            "SELECT COUNT(*) FROM session_events WHERE session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
            (participant_id,),
        ).fetchone()[0],
        "audits": backend.store.connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
            (participant_id,),
        ).fetchone()[0],
        "tasks": backend.store.connection.execute(
            "SELECT COUNT(*) FROM withdrawal_tasks WHERE withdrawal_subject_session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
            (participant_id,),
        ).fetchone()[0],
    }
    repeated = backend.withdraw(session_b_id, idempotency_key="withdraw-via-b")
    status = backend.withdrawal_status(session_b_id)
    assert set(first) == {
        "schema_version",
        "withdrawal_receipt_id",
        "participant_pseudonym",
        "terminal",
        "task_count",
    }
    after = {
        "events": backend.store.connection.execute(
            "SELECT COUNT(*) FROM session_events WHERE session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
            (participant_id,),
        ).fetchone()[0],
        "audits": backend.store.connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
            (participant_id,),
        ).fetchone()[0],
        "tasks": backend.store.connection.execute(
            "SELECT COUNT(*) FROM withdrawal_tasks WHERE withdrawal_subject_session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
            (participant_id,),
        ).fetchone()[0],
    }
    assert first["task_count"] == 2
    assert repeated == status == first
    assert after == before


def test_retention_reference_clears_only_retention_gate_and_pending_write_intent_is_bounded(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, draft = _research(backend, "draft")
    _study2, _participant2, retained = _research(backend, "retained", retention="policy-2026")
    assert (
        ReadinessGateCode.RETENTION_DECISION_REQUIRED
        in backend.readiness(str(draft["session_id"]))["blocking_gates"]
    )
    assert (
        ReadinessGateCode.RETENTION_DECISION_REQUIRED
        not in backend.readiness(str(retained["session_id"]))["blocking_gates"]
    )
    partial = root / "staging" / "partials" / "capture.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"partial-capture")
    backend.create_write_intent(str(retained["session_id"]), "staging/partials/capture.part")
    backend.store.close()
    reopened = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    assert reopened.recovery(str(retained["session_id"]))["collection_blocked"] is True
    assert reopened.recovery(str(retained["session_id"]))["state"] == SessionState.FAILED
    quarantined = list((root / "operational" / "quarantine").iterdir())
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"partial-capture"
    assert not partial.exists()
    with pytest.raises(InvalidTransition):
        reopened.create_write_intent(str(retained["session_id"]), "../escape.bin")


def test_create_write_intent_rechecks_mutability_inside_insert_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, session = _research(backend, "intent-race", retention="policy")
    session_id = str(session["session_id"])
    partial = root / "staging" / "partials" / "race.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"race")
    original_partial_file = backend._partial_file

    def withdraw_before_insert(value: str) -> Path:
        resolved = original_partial_file(value)
        backend.withdraw(session_id, idempotency_key="withdraw-during-intent")
        return resolved

    monkeypatch.setattr(backend, "_partial_file", withdraw_before_insert)
    with pytest.raises(InvalidTransition, match="Withdrawn|blocked"):
        backend.create_write_intent(session_id, "staging/partials/race.part")
    assert backend.store.connection.execute(
        "SELECT 1 FROM write_intents WHERE session_id=?", (session_id,)
    ).fetchone() is None
    assert backend.research_session(session_id)["state"] == SessionState.WITHDRAWN


def test_recovery_quarantines_withdrawn_pending_intent_without_losing_terminal_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, session = _research(backend, "withdrawn-recovery", retention="policy")
    session_id = str(session["session_id"])
    partial = root / "staging" / "partials" / "withdrawn.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"withdrawn-partial")
    backend.create_write_intent(session_id, "staging/partials/withdrawn.part")
    backend.withdraw(session_id, idempotency_key="withdraw-before-restart")
    backend.store.close()

    reopened = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    recovery = reopened.recovery(session_id)
    intent_status = reopened.store.connection.execute(
        "SELECT status FROM write_intents WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    quarantined = list((root / "operational" / "quarantine").iterdir())
    assert recovery["state"] == SessionState.WITHDRAWN
    assert recovery["collection_blocked"] is True
    assert intent_status == "QUARANTINED"
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"withdrawn-partial"
    assert not partial.exists()


def test_past_retention_end_date_is_rejected_by_backend_and_http(tmp_path: Path) -> None:
    past = (date.today() - timedelta(days=1)).isoformat()
    backend = M1Backend(
        tmp_path / "backend-root", encryption_status="VERIFIED", acl_status="VERIFIED"
    )
    study = backend.create_study("past-backend")
    participant = backend.create_participant(str(study["study_id"]))
    with pytest.raises(InvalidTransition, match="past"):
        backend.create_research_session(
            str(study["study_id"]),
            str(participant["participant_id"]),
            retention_end_date=past,
        )

    monitor, _monitor_backend, headers = _monitor(tmp_path / "http-root")
    http_study = _post(
        monitor, "/api/v1/research/studies", {"study_code": "past-http"}, headers, "past-study"
    ).json()
    http_participant = _post(
        monitor,
        "/api/v1/research/participants",
        {"study_id": http_study["study_id"]},
        headers,
        "past-participant",
    ).json()
    response = _post(
        monitor,
        "/api/v1/research/sessions",
        {
            "study_id": http_study["study_id"],
            "participant_id": http_participant["participant_id"],
            "retention_end_date": past,
        },
        headers,
        "past-session",
    )
    assert response.status_code == 422


def test_browser_retention_decision_cannot_clear_authority_gates(tmp_path: Path) -> None:
    monitor, _backend, headers = _monitor(tmp_path / "root")
    study = _post(
        monitor,
        "/api/v1/research/studies",
        {"study_code": "authority-gates"},
        headers,
        "authority-study",
    ).json()
    participant = _post(
        monitor,
        "/api/v1/research/participants",
        {"study_id": study["study_id"]},
        headers,
        "authority-participant",
    ).json()
    forged = _post(
        monitor,
        "/api/v1/research/sessions",
        {
            "study_id": study["study_id"],
            "participant_id": participant["participant_id"],
            "retention_policy_reference": "policy-2026",
            "retention_authority_approved": True,
        },
        headers,
        "authority-forged",
    )
    assert forged.status_code == 422
    created = _post(
        monitor,
        "/api/v1/research/sessions",
        {
            "study_id": study["study_id"],
            "participant_id": participant["participant_id"],
            "retention_policy_reference": "policy-2026",
        },
        headers,
        "authority-valid",
    ).json()
    readiness = monitor.get(
        f"/api/v1/research/sessions/{created['session_id']}/readiness", headers=headers
    ).json()
    assert readiness["ready"] is False
    assert "RETENTION_DECISION_REQUIRED" not in readiness["blocking_gates"]
    assert "RETENTION_AUTHORITY_UNVERIFIED" in readiness["blocking_gates"]
    assert "INSTITUTIONAL_APPROVAL_REQUIRED" in readiness["blocking_gates"]


def test_write_intents_reject_root_directory_operational_and_partial_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, session = _research(backend, "invalid-intents", retention="policy")
    partials = root / "staging" / "partials"
    partials.mkdir(parents=True)
    for invalid in (
        ".",
        "operational/pdu-exam-observer.sqlite3",
        "staging/partials",
    ):
        with pytest.raises(InvalidTransition, match="partial"):
            backend.create_write_intent(str(session["session_id"]), invalid)


def test_write_intents_reject_symlink_or_windows_reparse_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    _study, _participant, session = _research(backend, "symlink-intent", retention="policy")
    partials = root / "staging" / "partials"
    partials.mkdir(parents=True)
    target = root / "outside.part"
    target.write_bytes(b"outside")
    link = partials / "linked.part"
    try:
        os.symlink(target, link)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")
    with pytest.raises(InvalidTransition, match="reparse|symlink"):
        backend.create_write_intent(str(session["session_id"]), "staging/partials/linked.part")
