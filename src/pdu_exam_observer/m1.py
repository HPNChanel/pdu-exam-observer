"""M1 durable metadata, with volatile M0 authentication inherited deliberately."""
# ruff: noqa: E501

import ctypes
import hashlib
import json
import os
import sqlite3
import stat
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock

from pdu_exam_observer.configuration import ConfigurationError, validate_storage_root
from pdu_exam_observer.contracts import (
    ArtifactStatus,
    ReadinessGateCode,
    SessionKind,
    SessionSnapshot,
    SessionState,
)
from pdu_exam_observer.domain.state import InvalidTransition, transition
from pdu_exam_observer.repositories.in_memory import SessionRecord
from pdu_exam_observer.services.core import IdempotencyConflict, M0Backend
from pdu_exam_observer.storage_owner import SQLiteStoreOwner


class SchemaIntegrityError(RuntimeError):
    """A persisted database is outside this runtime's safe schema boundary."""


def _acquire_migration_owner_lease(
    operational: Path, *, create: bool, exclusive: bool = True
) -> tuple[str, int]:
    """Exclude legacy M1 while a migration readiness/apply owner is active."""

    lease_path = operational / "m1-migration-owner.lock"
    if os.name == "nt":
        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.restype = ctypes.c_void_p
        handle = create_file(
            str(lease_path),
            (0x80000000 | 0x40000000) if exclusive else 0x80000000,
            0 if exclusive else 1,
            None,
            4 if create else 3,
            0x80 | 0x200000,
            None,
        )
        if handle in (None, ctypes.c_void_p(-1).value):
            raise SchemaIntegrityError("MIGRATION_ROOT_NOT_QUIESCENT")
        return ("windows", int(handle))
    flags = os.O_RDWR | (os.O_CREAT if create else 0)
    try:
        descriptor = os.open(lease_path, flags, 0o600)
    except OSError as exc:
        raise SchemaIntegrityError("MIGRATION_ROOT_NOT_QUIESCENT") from exc
    try:
        fcntl = __import__("fcntl")
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(descriptor, mode | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(descriptor)
        raise SchemaIntegrityError("MIGRATION_ROOT_NOT_QUIESCENT") from exc
    return ("posix", descriptor)


def _release_migration_owner_lease(lease: tuple[str, int]) -> None:
    kind, handle = lease
    if handle < 0:
        return
    if kind == "windows":
        ctypes.windll.kernel32.CloseHandle(handle)
        return
    fcntl = __import__("fcntl")
    try:
        fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


_LEDGER_DDL = "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at_utc TEXT NOT NULL, checksum TEXT NOT NULL);"
_DDL = """
CREATE TABLE storage_roots(id TEXT PRIMARY KEY, encryption_status TEXT NOT NULL, acl_status TEXT NOT NULL, configured_at REAL NOT NULL);
CREATE TABLE studies(id TEXT PRIMARY KEY, study_code TEXT NOT NULL UNIQUE, status TEXT NOT NULL CHECK(status='APPROVAL_PENDING'), created_at REAL NOT NULL);
CREATE TABLE participants(id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), pseudonym TEXT NOT NULL UNIQUE, withdrawn_at REAL, created_at REAL NOT NULL);
CREATE TABLE sessions(id TEXT PRIMARY KEY, study_id TEXT REFERENCES studies(id), participant_id TEXT REFERENCES participants(id), session_kind TEXT NOT NULL CHECK(session_kind IN ('DEMO','RESEARCH')), state TEXT NOT NULL CHECK(state IN ('DRAFT','CONSENT_CONFIRMED','PREFLIGHT_READY','RECORDING','SEALED','FAILED','WITHDRAWN')), event_seq INTEGER NOT NULL DEFAULT 0 CHECK(event_seq >= 0), submitted INTEGER NOT NULL DEFAULT 0 CHECK(submitted IN (0,1)), duration_seconds INTEGER NOT NULL, started_at REAL, collection_blocked INTEGER NOT NULL DEFAULT 0 CHECK(collection_blocked IN (0,1)), created_at REAL NOT NULL, withdrawn_at REAL);
CREATE TABLE consent_receipts(id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id), consent_version TEXT NOT NULL, confirmed_at REAL NOT NULL);
CREATE TABLE retention_records(id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id), decision TEXT NOT NULL, recorded_at REAL NOT NULL);
CREATE TABLE exam_attempts(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), submitted INTEGER NOT NULL DEFAULT 0 CHECK(submitted IN (0,1)), created_at REAL NOT NULL);
CREATE TABLE answer_versions(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), answer_id TEXT NOT NULL, question_id TEXT NOT NULL, value_json TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE session_events(session_id TEXT NOT NULL REFERENCES sessions(id), event_seq INTEGER NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(session_id,event_seq));
CREATE TABLE idempotency_records(scope TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL, response_json TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(scope,idempotency_key));
CREATE TABLE artifact_registry(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), status TEXT NOT NULL CHECK(status IN ('VALID','INVALIDATED')), created_at REAL NOT NULL);
CREATE TABLE artifact_dependencies(parent_artifact_id TEXT NOT NULL REFERENCES artifact_registry(id), child_artifact_id TEXT NOT NULL REFERENCES artifact_registry(id), PRIMARY KEY(parent_artifact_id,child_artifact_id));
CREATE TABLE withdrawal_receipts(id TEXT PRIMARY KEY, participant_id TEXT NOT NULL UNIQUE REFERENCES participants(id), subject_session_id TEXT NOT NULL REFERENCES sessions(id), response_json TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE withdrawal_tasks(id TEXT PRIMARY KEY, withdrawal_subject_session_id TEXT NOT NULL REFERENCES sessions(id), artifact_id TEXT NOT NULL REFERENCES artifact_registry(id), status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETED')), created_at REAL NOT NULL, UNIQUE(withdrawal_subject_session_id,artifact_id));
CREATE TABLE write_intents(id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), manifest_relative_path TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','QUARANTINED')), created_at REAL NOT NULL);
CREATE TABLE audit_events(id TEXT PRIMARY KEY, event_type TEXT NOT NULL, session_id TEXT REFERENCES sessions(id), payload_json TEXT NOT NULL, created_at REAL NOT NULL);
CREATE INDEX idx_sessions_participant ON sessions(participant_id);
CREATE INDEX idx_events_session_seq ON session_events(session_id,event_seq);
CREATE INDEX idx_artifacts_session ON artifact_registry(session_id);
CREATE INDEX idx_tasks_subject ON withdrawal_tasks(withdrawal_subject_session_id);
"""
_CHECKSUM = hashlib.sha256((_LEDGER_DDL + _DDL).encode("utf-8")).hexdigest()


def _normalize_schema_sql(sql: str) -> str:
    return " ".join(sql.strip().removesuffix(";").split()).casefold()


def _schema_sql_objects(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    return {
        (str(row[0]), str(row[1])): _normalize_schema_sql(str(row[2]))
        for row in connection.execute(
            "SELECT type,name,sql FROM sqlite_master "
            "WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
        )
    }


def _canonical_schema_sql_objects() -> dict[tuple[str, str], str]:
    trusted = sqlite3.connect(":memory:")
    try:
        trusted.executescript(_LEDGER_DDL + _DDL)
        return _schema_sql_objects(trusted)
    finally:
        trusted.close()


_REQUIRED_TABLES = {
    "schema_migrations",
    "storage_roots",
    "studies",
    "participants",
    "consent_receipts",
    "retention_records",
    "sessions",
    "exam_attempts",
    "answer_versions",
    "session_events",
    "idempotency_records",
    "artifact_registry",
    "artifact_dependencies",
    "withdrawal_receipts",
    "withdrawal_tasks",
    "write_intents",
    "audit_events",
}
_ColumnShape = tuple[str, str, int, str | None, int]
_REQUIRED_COLUMNS: dict[str, tuple[_ColumnShape, ...]] = {
    "schema_migrations": (
        ("version", "INTEGER", 0, None, 1),
        ("applied_at_utc", "TEXT", 1, None, 0),
        ("checksum", "TEXT", 1, None, 0),
    ),
    "storage_roots": (
        ("id", "TEXT", 0, None, 1),
        ("encryption_status", "TEXT", 1, None, 0),
        ("acl_status", "TEXT", 1, None, 0),
        ("configured_at", "REAL", 1, None, 0),
    ),
    "studies": (
        ("id", "TEXT", 0, None, 1),
        ("study_code", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "participants": (
        ("id", "TEXT", 0, None, 1),
        ("study_id", "TEXT", 1, None, 0),
        ("pseudonym", "TEXT", 1, None, 0),
        ("withdrawn_at", "REAL", 0, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "sessions": (
        ("id", "TEXT", 0, None, 1),
        ("study_id", "TEXT", 0, None, 0),
        ("participant_id", "TEXT", 0, None, 0),
        ("session_kind", "TEXT", 1, None, 0),
        ("state", "TEXT", 1, None, 0),
        ("event_seq", "INTEGER", 1, "0", 0),
        ("submitted", "INTEGER", 1, "0", 0),
        ("duration_seconds", "INTEGER", 1, None, 0),
        ("started_at", "REAL", 0, None, 0),
        ("collection_blocked", "INTEGER", 1, "0", 0),
        ("created_at", "REAL", 1, None, 0),
        ("withdrawn_at", "REAL", 0, None, 0),
    ),
    "consent_receipts": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("consent_version", "TEXT", 1, None, 0),
        ("confirmed_at", "REAL", 1, None, 0),
    ),
    "retention_records": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("decision", "TEXT", 1, None, 0),
        ("recorded_at", "REAL", 1, None, 0),
    ),
    "exam_attempts": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("submitted", "INTEGER", 1, "0", 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "answer_versions": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("answer_id", "TEXT", 1, None, 0),
        ("question_id", "TEXT", 1, None, 0),
        ("value_json", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "session_events": (
        ("session_id", "TEXT", 1, None, 1),
        ("event_seq", "INTEGER", 1, None, 2),
        ("event_type", "TEXT", 1, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "idempotency_records": (
        ("scope", "TEXT", 1, None, 1),
        ("idempotency_key", "TEXT", 1, None, 2),
        ("request_hash", "TEXT", 1, None, 0),
        ("response_json", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "artifact_registry": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "artifact_dependencies": (
        ("parent_artifact_id", "TEXT", 1, None, 1),
        ("child_artifact_id", "TEXT", 1, None, 2),
    ),
    "withdrawal_receipts": (
        ("id", "TEXT", 0, None, 1),
        ("participant_id", "TEXT", 1, None, 0),
        ("subject_session_id", "TEXT", 1, None, 0),
        ("response_json", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "withdrawal_tasks": (
        ("id", "TEXT", 0, None, 1),
        ("withdrawal_subject_session_id", "TEXT", 1, None, 0),
        ("artifact_id", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "write_intents": (
        ("id", "TEXT", 0, None, 1),
        ("session_id", "TEXT", 1, None, 0),
        ("manifest_relative_path", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
    "audit_events": (
        ("id", "TEXT", 0, None, 1),
        ("event_type", "TEXT", 1, None, 0),
        ("session_id", "TEXT", 0, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "REAL", 1, None, 0),
    ),
}
_REQUIRED_INDEXES: dict[str, tuple[str, tuple[str, ...], int, int]] = {
    "idx_sessions_participant": ("sessions", ("participant_id",), 0, 0),
    "idx_events_session_seq": ("session_events", ("session_id", "event_seq"), 0, 0),
    "idx_artifacts_session": ("artifact_registry", ("session_id",), 0, 0),
    "idx_tasks_subject": ("withdrawal_tasks", ("withdrawal_subject_session_id",), 0, 0),
}
_REQUIRED_UNIQUES: dict[str, set[tuple[str, ...]]] = {
    "studies": {("study_code",)},
    "participants": {("pseudonym",)},
    "consent_receipts": {("session_id",)},
    "retention_records": {("session_id",)},
    "withdrawal_receipts": {("participant_id",)},
    "withdrawal_tasks": {("withdrawal_subject_session_id", "artifact_id")},
}
_REQUIRED_FOREIGN_KEYS: dict[str, set[tuple[str, str, str, str, str, str]]] = {
    table: set() for table in _REQUIRED_TABLES
}
_REQUIRED_FOREIGN_KEYS.update(
    {
        "participants": {("study_id", "studies", "id", "NO ACTION", "NO ACTION", "NONE")},
        "sessions": {
            ("study_id", "studies", "id", "NO ACTION", "NO ACTION", "NONE"),
            ("participant_id", "participants", "id", "NO ACTION", "NO ACTION", "NONE"),
        },
        "consent_receipts": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
        "retention_records": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
        "exam_attempts": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
        "answer_versions": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
        "session_events": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
        "artifact_registry": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
        "artifact_dependencies": {
            (
                "parent_artifact_id",
                "artifact_registry",
                "id",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
            (
                "child_artifact_id",
                "artifact_registry",
                "id",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
        },
        "withdrawal_receipts": {
            ("participant_id", "participants", "id", "NO ACTION", "NO ACTION", "NONE"),
            ("subject_session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE"),
        },
        "withdrawal_tasks": {
            (
                "withdrawal_subject_session_id",
                "sessions",
                "id",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
            ("artifact_id", "artifact_registry", "id", "NO ACTION", "NO ACTION", "NONE"),
        },
        "write_intents": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
        "audit_events": {
            ("session_id", "sessions", "id", "NO ACTION", "NO ACTION", "NONE")
        },
    }
)
class M1Store:
    schema_version = 1

    def __init__(self, root: Path) -> None:
        self._migration_owner_lease: tuple[str, int] = ("unacquired", -1)
        try:
            self.root = validate_storage_root(root, create=True)
        except ConfigurationError as exc:
            raise SchemaIntegrityError("storage root is unsafe") from exc
        operational = self._secure_directory_child(
            self.root, "operational", "operational directory"
        )
        self._migration_owner_lease = _acquire_migration_owner_lease(
            operational, create=True, exclusive=False
        )
        self.database_path = self._secure_file_child(
            operational, "pdu-exam-observer.sqlite3", "operational database"
        )
        self._lock = RLock()
        try:
            self.connection = sqlite3.connect(
                self.database_path, isolation_level=None, check_same_thread=False
            )
            with self._lock:
                self.connection.row_factory = sqlite3.Row
                journal = str(
                    self.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                ).lower()
                if journal != "wal":
                    raise SchemaIntegrityError("SQLite WAL could not be enabled")
                self.connection.execute("PRAGMA foreign_keys=ON")
                self._migrate_and_validate()
        except Exception:
            if hasattr(self, "connection"):
                self.connection.close()
            _release_migration_owner_lease(self._migration_owner_lease)
            self._migration_owner_lease = ("unacquired", -1)
            raise

    @staticmethod
    def _validated_child(parent: Path, child: Path, label: str, *, directory: bool) -> Path:
        try:
            parent_before = parent.resolve(strict=True)
            metadata = child.lstat()
            parent_after = parent.resolve(strict=True)
            resolved = child.resolve(strict=True)
        except OSError as exc:
            raise SchemaIntegrityError(f"{label} is unavailable") from exc
        if parent_before != parent_after:
            raise SchemaIntegrityError(f"{label} parent changed during validation")
        if stat.S_ISLNK(metadata.st_mode) or bool(
            getattr(metadata, "st_file_attributes", 0) & 0x400
        ):
            raise SchemaIntegrityError(f"{label} may not be a symlink or reparse point")
        expected_type = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
        if not expected_type:
            raise SchemaIntegrityError(f"{label} has an unsafe filesystem type")
        try:
            resolved.relative_to(parent_after)
        except ValueError as exc:
            raise SchemaIntegrityError(f"{label} is outside its storage parent") from exc
        return resolved

    @classmethod
    def _secure_directory_child(cls, parent: Path, name: str, label: str) -> Path:
        child = parent / name
        try:
            child.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise SchemaIntegrityError(f"{label} could not be created") from exc
        return cls._validated_child(parent, child, label, directory=True)

    @classmethod
    def _secure_file_child(cls, parent: Path, name: str, label: str) -> Path:
        child = parent / name
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(child, flags, 0o600)
        except FileExistsError:
            pass
        except OSError as exc:
            raise SchemaIntegrityError(f"{label} could not be created") from exc
        else:
            os.close(descriptor)
        return cls._validated_child(parent, child, label, directory=False)

    def close(self) -> None:
        try:
            with self._lock:
                self.connection.close()
        finally:
            _release_migration_owner_lease(self._migration_owner_lease)
            self._migration_owner_lease = ("unacquired", -1)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
            except Exception:
                self.connection.execute("ROLLBACK")
                raise
            else:
                self.connection.execute("COMMIT")

    def _migrate_and_validate(self) -> None:
        ledger = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if ledger is None:
            self.connection.executescript(
                "BEGIN IMMEDIATE;"
                + _LEDGER_DDL
                + _DDL
                + f"INSERT INTO schema_migrations(version,applied_at_utc,checksum) VALUES(1,'{datetime.now(UTC).isoformat()}','{_CHECKSUM}');COMMIT;"
            )
        columns = tuple(
            (
                str(row[1]),
                str(row[2]).upper(),
                int(row[3]),
                None if row[4] is None else str(row[4]),
                int(row[5]),
            )
            for row in self.connection.execute("PRAGMA table_info(schema_migrations)")
        )
        if columns != _REQUIRED_COLUMNS["schema_migrations"]:
            raise SchemaIntegrityError("schema migration ledger is malformed")
        rows = self.connection.execute(
            "SELECT version,applied_at_utc,checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        if (
            len(rows) != 1
            or int(rows[0]["version"]) != 1
            or not rows[0]["applied_at_utc"]
            or rows[0]["checksum"] != _CHECKSUM
        ):
            raise SchemaIntegrityError(
                "schema migration checksum is invalid or newer than this runtime"
            )
        self._validate_schema()

    def _validate_schema(self) -> None:
        try:
            actual_schema = _schema_sql_objects(self.connection)
            if actual_schema != _canonical_schema_sql_objects():
                raise SchemaIntegrityError("schema object is missing or malformed")
            objects = {
                name: sql for (object_type, name), sql in actual_schema.items() if object_type == "table"
            }
            if not _REQUIRED_TABLES.issubset(objects):
                raise SchemaIntegrityError("schema object is missing or malformed")
            for table, expected_shape in _REQUIRED_COLUMNS.items():
                actual_shape = tuple(
                    (
                        str(row[1]),
                        str(row[2]).upper(),
                        int(row[3]),
                        None if row[4] is None else str(row[4]),
                        int(row[5]),
                    )
                    for row in self.connection.execute(f"PRAGMA table_info({table})")
                )
                if actual_shape != expected_shape:
                    raise SchemaIntegrityError("schema object is missing or malformed")
            for table, expected_foreign_keys in _REQUIRED_FOREIGN_KEYS.items():
                actual_foreign_keys = {
                    (
                        str(row[3]),
                        str(row[2]),
                        str(row[4]),
                        str(row[5]),
                        str(row[6]),
                        str(row[7]),
                    )
                    for row in self.connection.execute(f"PRAGMA foreign_key_list({table})")
                }
                if actual_foreign_keys != expected_foreign_keys:
                    raise SchemaIntegrityError("schema object is missing or malformed")
            index_objects = {
                str(row["name"]): str(row["tbl_name"])
                for row in self.connection.execute(
                    "SELECT name,tbl_name FROM sqlite_master WHERE type='index'"
                )
            }
            for name, (table, expected_columns, unique, partial) in _REQUIRED_INDEXES.items():
                if index_objects.get(name) != table:
                    raise SchemaIntegrityError("schema object is missing or malformed")
                flags = {
                    str(row[1]): (int(row[2]), int(row[4]))
                    for row in self.connection.execute(f"PRAGMA index_list({table})")
                }
                columns = tuple(
                    str(row[2])
                    for row in self.connection.execute(f"PRAGMA index_info({name})")
                )
                if flags.get(name) != (unique, partial) or columns != expected_columns:
                    raise SchemaIntegrityError("schema object is missing or malformed")
            for table, expected_uniques in _REQUIRED_UNIQUES.items():
                actual_uniques = {
                    tuple(
                        str(column[2])
                        for column in self.connection.execute(
                            f"PRAGMA index_info({str(index[1])})"
                        )
                    )
                    for index in self.connection.execute(f"PRAGMA index_list({table})")
                    if int(index[2]) == 1 and int(index[4]) == 0
                }
                if not expected_uniques.issubset(actual_uniques):
                    raise SchemaIntegrityError("schema object is missing or malformed")
            if self.connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise SchemaIntegrityError("foreign key check failed")
            invalid = self.connection.execute(
                "SELECT 1 FROM sessions WHERE session_kind='RESEARCH' AND state='RECORDING'"
            ).fetchone()
            if invalid is not None:
                raise SchemaIntegrityError("persisted research session is recording")
        except sqlite3.DatabaseError as exc:
            raise SchemaIntegrityError("schema object is missing or malformed") from exc

    def add_dependency(self, parent: str, child: str) -> None:
        with self.transaction() as connection:
            self.require_valid_parents(connection, (parent,))
            if connection.execute(
                "SELECT 1 FROM artifact_registry WHERE id=?", (child,)
            ).fetchone() is None:
                raise InvalidTransition("Artifact dependency child is missing")
            connection.execute(
                "INSERT INTO artifact_dependencies(parent_artifact_id,child_artifact_id) VALUES(?,?)",
                (parent, child),
            )

    @staticmethod
    def require_valid_parents(
        connection: sqlite3.Connection, parents: tuple[str, ...]
    ) -> None:
        for parent in parents:
            row = connection.execute(
                "SELECT a.status,s.state,p.withdrawn_at "
                "FROM artifact_registry a "
                "JOIN sessions s ON s.id=a.session_id "
                "LEFT JOIN participants p ON p.id=s.participant_id "
                "WHERE a.id=?",
                (parent,),
            ).fetchone()
            if (
                row is None
                or row["status"] != ArtifactStatus.VALID
                or row["state"] == SessionState.WITHDRAWN
                or row["withdrawn_at"] is not None
            ):
                raise InvalidTransition(
                    "Artifact parent is missing, invalidated, or belongs to a withdrawn record"
                )


class M1Backend(M0Backend):
    def __init__(
        self,
        root: Path,
        *,
        encryption_status: str,
        acl_status: str,
        clock: Callable[[], float] = time.time,
        duration_seconds: int = 2700,
        store: SQLiteStoreOwner | None = None,
    ) -> None:
        super().__init__(clock=clock, duration_seconds=duration_seconds)
        if store is not None and Path(root).resolve() != store.root:
            raise SchemaIntegrityError("injected store root does not match requested root")
        self.store: M1Store | SQLiteStoreOwner = M1Store(root) if store is None else store
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO storage_roots(id,encryption_status,acl_status,configured_at) VALUES('active',?,?,?)",
                (encryption_status, acl_status, self.clock()),
            )
        self._recover_pending_intents()

    def _record(self, session_id: str) -> SessionRecord | None:
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT id,state,event_seq,submitted,duration_seconds,started_at FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
        return (
            None
            if row is None
            else SessionRecord(
                str(row["id"]),
                SessionState(str(row["state"])),
                int(row["event_seq"]),
                bool(row["submitted"]),
                int(row["duration_seconds"]),
                row["started_at"],
            )
        )

    def _event(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        row = connection.execute(
            "SELECT event_seq FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        sequence = int(row["event_seq"]) + 1
        connection.execute("UPDATE sessions SET event_seq=? WHERE id=?", (sequence, session_id))
        connection.execute(
            "INSERT INTO session_events(session_id,event_seq,event_type,payload_json,created_at) VALUES(?,?,?,?,?)",
            (
                session_id,
                sequence,
                event_type,
                json.dumps(payload, separators=(",", ":")),
                self.clock(),
            ),
        )
        return {"event_seq": sequence, "type": event_type, **payload}

    def _publish(self, session_id: str, event: dict[str, object]) -> None:
        self._fanout(session_id, event)

    def _key(self, key: str | None, fallback: str) -> str:
        value = key or fallback
        if not 1 <= len(value) <= 128 or any(ch in value for ch in "\\/:"):
            raise InvalidTransition("Invalid idempotency key")
        return value

    def _mutate(
        self,
        scope: str,
        key: str,
        payload: dict[str, object],
        operation: Callable[[sqlite3.Connection], dict[str, object]],
    ) -> dict[str, object]:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT request_hash,response_json FROM idempotency_records WHERE scope=? AND idempotency_key=?",
                (scope, key),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != digest:
                    raise IdempotencyConflict(
                        "Idempotency key was reused with a different request payload"
                    )
                replayed = json.loads(row["response_json"])
                if not isinstance(replayed, dict):
                    raise SchemaIntegrityError("idempotency response is malformed")
                return {str(name): value for name, value in replayed.items()}
            response = operation(connection)
            connection.execute(
                "INSERT INTO idempotency_records(scope,idempotency_key,request_hash,response_json,created_at) VALUES(?,?,?,?,?)",
                (scope, key, digest, json.dumps(response, separators=(",", ":")), self.clock()),
            )
            return response

    def _kind(self, session_id: str) -> SessionKind:
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT session_kind FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return SessionKind(str(row["session_kind"]))

    def _mutable_research(self, session_id: str) -> None:
        with self.store._lock:
            self._require_mutable_research(self.store.connection, session_id)

    @staticmethod
    def _require_mutable_research(
        connection: sqlite3.Connection, session_id: str
    ) -> None:
        row = connection.execute(
            "SELECT s.state,s.collection_blocked,p.withdrawn_at FROM sessions s JOIN participants p ON p.id=s.participant_id WHERE s.id=? AND s.session_kind='RESEARCH'",
            (session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        if (
            row["withdrawn_at"] is not None
            or row["state"] == SessionState.WITHDRAWN
            or bool(row["collection_blocked"])
        ):
            raise InvalidTransition("Withdrawn or blocked research records cannot be mutated")

    def append_event(
        self, session_id: str, event_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        with self.store.transaction() as connection:
            event = self._event(connection, session_id, event_type, payload)
        self._publish(session_id, event)
        return event

    def create_session(self) -> tuple[SessionRecord, str]:
        session_id, pairing = token_urlsafe(18), token_urlsafe(12)
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO sessions(id,session_kind,state,duration_seconds,created_at) VALUES(?,?,?,?,?)",
                (
                    session_id,
                    SessionKind.DEMO,
                    SessionState.DRAFT,
                    self.duration_seconds,
                    self.clock(),
                ),
            )
        self.pairing_codes[pairing] = session_id
        record = self._record(session_id)
        assert record is not None
        return record, pairing

    def snapshot(self, session_id: str) -> SessionSnapshot | None:
        record = self._record(session_id)
        if record is None:
            return None
        return self._snapshot_for_record(record)

    def _snapshot_for_record(self, record: SessionRecord) -> SessionSnapshot:
        remaining, started = None, None
        if record.started_at is not None:
            remaining = max(
                0, record.duration_seconds - max(0, int(self.clock() - record.started_at))
            )
            started = (
                datetime.fromtimestamp(record.started_at, UTC).isoformat().replace("+00:00", "Z")
            )
        return SessionSnapshot(
            session_id=record.session_id,
            state=record.state,
            event_seq=record.event_seq,
            submitted=record.submitted,
            duration_seconds=record.duration_seconds,
            remaining_seconds=remaining,
            started_at_utc=started,
        )

    def apply_session_action(self, session_id: str, action: str) -> SessionSnapshot | None:
        event: dict[str, object] | None = None
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT id,session_kind,state,event_seq,submitted,duration_seconds,started_at FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            if SessionKind(str(row["session_kind"])) is SessionKind.RESEARCH:
                raise InvalidTransition("Research sessions cannot enter the M0 lifecycle in M1")
            current_state = SessionState(str(row["state"]))
            next_state = transition(current_state, action)
            started_at = self.clock() if action == "start" and next_state != current_state else row["started_at"]
            if next_state != current_state:
                updated = connection.execute(
                    "UPDATE sessions SET state=?,started_at=? WHERE id=? AND state=?",
                    (next_state, started_at, session_id, current_state),
                )
                if updated.rowcount != 1:
                    raise SchemaIntegrityError("session lifecycle compare-and-set failed")
                event = self._event(
                    connection, session_id, "SessionStateChanged", {"state": next_state}
                )
            persisted = connection.execute(
                "SELECT event_seq,submitted FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            assert persisted is not None
            record = SessionRecord(
                session_id,
                next_state,
                int(persisted["event_seq"]),
                bool(persisted["submitted"]),
                int(row["duration_seconds"]),
                started_at,
            )
        if event is not None:
            self._publish(session_id, event)
        return self._snapshot_for_record(record)

    def events_after(self, session_id: str, event_seq: int) -> list[dict[str, object]]:
        with self.store._lock:
            rows = self.store.connection.execute(
                "SELECT event_seq,event_type,payload_json FROM session_events WHERE session_id=? AND event_seq>? ORDER BY event_seq",
                (session_id, event_seq),
            ).fetchall()
        return [
            {
                "event_seq": int(row["event_seq"]),
                "type": row["event_type"],
                **json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def record_answer(
        self, session_id: str, idempotency_key: str, payload: dict[str, object]
    ) -> dict[str, object]:
        key = self._key(idempotency_key, str(payload["answer_id"]))
        event: dict[str, object] | None = None

        def operation(connection: sqlite3.Connection) -> dict[str, object]:
            nonlocal event
            row = connection.execute(
                "SELECT state,submitted FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            if row["state"] != SessionState.RECORDING or row["submitted"]:
                raise InvalidTransition("Answers are accepted only while the session is recording")
            result: dict[str, object] = {"schema_version": 1, "accepted": True}
            connection.execute(
                "INSERT INTO answer_versions(id,session_id,answer_id,question_id,value_json,created_at) VALUES(?,?,?,?,?,?)",
                (
                    token_urlsafe(12),
                    session_id,
                    payload["answer_id"],
                    payload["question_id"],
                    json.dumps(payload.get("value")),
                    self.clock(),
                ),
            )
            event = self._event(
                connection, session_id, "AnswerRecorded", {"answer_id": payload["answer_id"]}
            )
            return result

        result = self._mutate(f"answer:{session_id}", key, payload, operation)
        if event is not None:
            self._publish(session_id, event)
        return result

    def submit_exam(self, session_id: str, idempotency_key: str) -> dict[str, object]:
        key, event = self._key(idempotency_key, "submit"), None

        def operation(connection: sqlite3.Connection) -> dict[str, object]:
            nonlocal event
            row = connection.execute(
                "SELECT state,submitted FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            if row["state"] != SessionState.RECORDING:
                raise InvalidTransition("Exam can be submitted only while the session is recording")
            if row["submitted"]:
                raise IdempotencyConflict(
                    "Exam was already submitted with a different idempotency key"
                )
            result: dict[str, object] = {"schema_version": 1, "submitted": True}
            connection.execute("UPDATE sessions SET submitted=1 WHERE id=?", (session_id,))
            connection.execute(
                "INSERT INTO exam_attempts(id,session_id,submitted,created_at) VALUES(?,?,1,?)",
                (token_urlsafe(12), session_id, self.clock()),
            )
            event = self._event(connection, session_id, "ExamSubmitted", {})
            return result

        result = self._mutate(f"submit:{session_id}", key, {"submit": True}, operation)
        if event is not None:
            self._publish(session_id, event)
        return result

    def replay_demo_alerts(self, session_id: str) -> list[dict[str, object]]:
        if self._record(session_id) is None:
            raise KeyError(session_id)
        fixtures = self._fixture_events()
        for fixture in fixtures:
            self.append_demo_event(
                session_id,
                {
                    "fixture_event_type": fixture["event_type"],
                    "confidence": fixture["confidence"],
                    "confidence_status": fixture["confidence_status"],
                    "source_kind": fixture["source_kind"],
                    "payload": fixture["payload"],
                },
            )
        return self.events_after(session_id, 0)[-len(fixtures) :]

    def create_study(
        self, study_code: str, *, idempotency_key: str | None = None
    ) -> dict[str, object]:
        key = self._key(idempotency_key, f"study-{study_code}")

        def operation(connection: sqlite3.Connection) -> dict[str, object]:
            study_id = f"study-{token_urlsafe(9)}"
            connection.execute(
                "INSERT INTO studies(id,study_code,status,created_at) VALUES(?,?,'APPROVAL_PENDING',?)",
                (study_id, study_code, self.clock()),
            )
            return {"schema_version": 1, "study_id": study_id, "status": "APPROVAL_PENDING"}

        return self._mutate("research-study", key, {"study_code": study_code}, operation)

    def create_participant(
        self, study_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, object]:
        key = self._key(idempotency_key, f"participant-{study_id}")

        def operation(connection: sqlite3.Connection) -> dict[str, object]:
            if (
                connection.execute("SELECT 1 FROM studies WHERE id=?", (study_id,)).fetchone()
                is None
            ):
                raise KeyError(study_id)
            participant_id, pseudonym = f"participant-{token_urlsafe(9)}", f"p-{token_urlsafe(8)}"
            connection.execute(
                "INSERT INTO participants(id,study_id,pseudonym,created_at) VALUES(?,?,?,?)",
                (participant_id, study_id, pseudonym, self.clock()),
            )
            return {
                "schema_version": 1,
                "participant_id": participant_id,
                "participant_pseudonym": pseudonym,
            }

        return self._mutate("research-participant", key, {"study_id": study_id}, operation)

    def create_research_session(
        self,
        study_id: str,
        participant_id: str,
        *,
        idempotency_key: str | None = None,
        retention_policy_reference: str | None = None,
        retention_end_date: str | None = None,
    ) -> dict[str, object]:
        if retention_policy_reference is not None and retention_end_date is not None:
            raise InvalidTransition("Only one retention value may be supplied")
        if retention_end_date is not None:
            try:
                parsed_retention_end = date.fromisoformat(retention_end_date)
            except ValueError as exc:
                raise InvalidTransition("Retention end date must be a valid ISO date") from exc
            if parsed_retention_end < date.fromtimestamp(self.clock()):
                raise InvalidTransition("Retention end date may not be in the past")
        key = self._key(idempotency_key, f"session-{participant_id}")
        payload: dict[str, object] = {
            "study_id": study_id,
            "participant_id": participant_id,
            "retention_policy_reference": retention_policy_reference,
            "retention_end_date": retention_end_date,
        }

        def operation(connection: sqlite3.Connection) -> dict[str, object]:
            participant = connection.execute(
                "SELECT pseudonym,withdrawn_at FROM participants WHERE id=? AND study_id=?",
                (participant_id, study_id),
            ).fetchone()
            if participant is None:
                raise KeyError(participant_id)
            if participant["withdrawn_at"] is not None:
                raise InvalidTransition("Withdrawn participant cannot receive a session")
            session_id = f"research-{token_urlsafe(12)}"
            connection.execute(
                "INSERT INTO sessions(id,study_id,participant_id,session_kind,state,duration_seconds,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    session_id,
                    study_id,
                    participant_id,
                    SessionKind.RESEARCH,
                    SessionState.DRAFT,
                    self.duration_seconds,
                    self.clock(),
                ),
            )
            decision = retention_policy_reference or retention_end_date or "PENDING"
            connection.execute(
                "INSERT INTO retention_records(id,session_id,decision,recorded_at) VALUES(?,?,?,?)",
                (f"retention-{token_urlsafe(8)}", session_id, decision, self.clock()),
            )
            return {
                "schema_version": 1,
                "session_id": session_id,
                "session_kind": SessionKind.RESEARCH,
                "state": SessionState.DRAFT,
                "participant_pseudonym": participant["pseudonym"],
            }

        return self._mutate("research-session", key, payload, operation)

    def confirm_operator_consent(
        self, session_id: str, receipt_id: str, version: str, *, idempotency_key: str | None = None
    ) -> dict[str, object]:
        self._mutable_research(session_id)
        key = self._key(idempotency_key, f"consent-{session_id}")
        event: dict[str, object] | None = None

        def operation(connection: sqlite3.Connection) -> dict[str, object]:
            nonlocal event
            self._require_mutable_research(connection, session_id)
            connection.execute(
                "INSERT OR REPLACE INTO consent_receipts(id,session_id,consent_version,confirmed_at) VALUES(?,?,?,?)",
                (receipt_id, session_id, version, self.clock()),
            )
            connection.execute(
                "UPDATE sessions SET state=? WHERE id=? AND state=?",
                (SessionState.CONSENT_CONFIRMED, session_id, SessionState.DRAFT),
            )
            event = self._event(
                connection, session_id, "OperatorConsentConfirmed", {"consent_version": version}
            )
            return {"schema_version": 1, "session_id": session_id, "consent_confirmed": True}

        result = self._mutate(
            f"research-consent:{session_id}",
            key,
            {"receipt_id": receipt_id, "version": version},
            operation,
        )
        if event is not None:
            self._publish(session_id, event)
        return result

    def research_session(self, session_id: str) -> dict[str, object]:
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT s.id,s.state,s.session_kind,s.collection_blocked,p.pseudonym,p.withdrawn_at FROM sessions s JOIN participants p ON p.id=s.participant_id WHERE s.id=?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return {
            "schema_version": 1,
            "session_id": row["id"],
            "session_kind": row["session_kind"],
            "state": row["state"],
            "participant_pseudonym": row["pseudonym"],
            "collection_blocked": bool(row["collection_blocked"]),
            "participant_withdrawn": row["withdrawn_at"] is not None,
        }

    def readiness(self, session_id: str) -> dict[str, object]:
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT st.status,r.decision,c.id consent_id,sr.encryption_status,sr.acl_status FROM sessions s JOIN studies st ON st.id=s.study_id JOIN retention_records r ON r.session_id=s.id LEFT JOIN consent_receipts c ON c.session_id=s.id JOIN storage_roots sr ON sr.id='active' WHERE s.id=?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        gates: list[ReadinessGateCode] = [ReadinessGateCode.RESEARCH_COLLECTION_NOT_IMPLEMENTED]
        if row["status"] != "APPROVED":
            gates.append(ReadinessGateCode.INSTITUTIONAL_APPROVAL_REQUIRED)
        if row["consent_id"] is None:
            gates.append(ReadinessGateCode.OPERATOR_CONSENT_REQUIRED)
        if row["decision"] == "PENDING":
            gates.append(ReadinessGateCode.RETENTION_DECISION_REQUIRED)
        gates.append(ReadinessGateCode.RETENTION_AUTHORITY_UNVERIFIED)
        if row["encryption_status"] != "VERIFIED":
            gates.append(ReadinessGateCode.STORAGE_ENCRYPTION_UNVERIFIED)
        if row["acl_status"] != "VERIFIED":
            gates.append(ReadinessGateCode.STORAGE_ACL_UNVERIFIED)
        return {
            "schema_version": 1,
            "session_id": session_id,
            "ready": False,
            "blocking_gates": [str(item) for item in gates],
        }

    def start_research_session(self, session_id: str) -> bool:
        self.research_session(session_id)
        return False

    def register_artifact(
        self, artifact_id: str, session_id: str, parents: tuple[str, ...] = ()
    ) -> None:
        self._mutable_research(session_id)
        with self.store.transaction() as connection:
            self._require_mutable_research(connection, session_id)
            self.store.require_valid_parents(connection, parents)
            connection.execute(
                "INSERT INTO artifact_registry(id,session_id,status,created_at) VALUES(?,?,?,?)",
                (artifact_id, session_id, ArtifactStatus.VALID, self.clock()),
            )
            for parent in parents:
                connection.execute(
                    "INSERT INTO artifact_dependencies(parent_artifact_id,child_artifact_id) VALUES(?,?)",
                    (parent, artifact_id),
                )

    def withdraw(self, session_id: str, *, idempotency_key: str | None = None) -> dict[str, object]:
        record = self.research_session(session_id)
        with self.store._lock:
            participant = self.store.connection.execute(
                "SELECT participant_id FROM sessions WHERE id=? AND session_kind='RESEARCH'",
                (session_id,),
            ).fetchone()
        if participant is None:
            raise KeyError(session_id)
        participant_id = str(participant["participant_id"])
        key, event = self._key(idempotency_key, f"withdraw-{participant_id}"), None

        def operation(connection: sqlite3.Connection) -> dict[str, object]:
            nonlocal event
            current = connection.execute(
                "SELECT participant_id FROM sessions WHERE id=? AND session_kind='RESEARCH'",
                (session_id,),
            ).fetchone()
            if current is None or str(current["participant_id"]) != participant_id:
                raise KeyError(session_id)
            receipt = connection.execute(
                "SELECT response_json FROM withdrawal_receipts WHERE participant_id=?",
                (participant_id,),
            ).fetchone()
            if receipt is not None:
                canonical_response: object = json.loads(receipt["response_json"])
                if not isinstance(canonical_response, dict):
                    raise SchemaIntegrityError("withdrawal canonical response is malformed")
                return {str(name): value for name, value in canonical_response.items()}
            connection.execute(
                "UPDATE participants SET withdrawn_at=COALESCE(withdrawn_at,?) WHERE id=?",
                (self.clock(), participant_id),
            )
            connection.execute(
                "UPDATE sessions SET state=?,collection_blocked=1,withdrawn_at=COALESCE(withdrawn_at,?) WHERE participant_id=?",
                (SessionState.WITHDRAWN, self.clock(), participant_id),
            )
            artifacts = connection.execute(
                "WITH RECURSIVE lineage(id) AS (SELECT id FROM artifact_registry WHERE session_id IN (SELECT id FROM sessions WHERE participant_id=?) UNION SELECT d.child_artifact_id FROM artifact_dependencies d JOIN lineage l ON d.parent_artifact_id=l.id) SELECT DISTINCT id FROM lineage",
                (participant_id,),
            ).fetchall()
            for row in artifacts:
                artifact_id = str(row["id"])
                connection.execute(
                    "UPDATE artifact_registry SET status=? WHERE id=?",
                    (ArtifactStatus.INVALIDATED, artifact_id),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO withdrawal_tasks(id,withdrawal_subject_session_id,artifact_id,status,created_at) VALUES(?,?,?,?,?)",
                    (
                        f"withdrawal-{token_urlsafe(8)}",
                        session_id,
                        artifact_id,
                        "PENDING",
                        self.clock(),
                    ),
                )
            event = self._event(connection, session_id, "WithdrawalRequested", {})
            count = connection.execute(
                "SELECT COUNT(*) FROM withdrawal_tasks WHERE withdrawal_subject_session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
                (participant_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO audit_events(id,event_type,session_id,payload_json,created_at) VALUES(?,?,?,?,?)",
                (
                    f"audit-{token_urlsafe(8)}",
                    "ParticipantWithdrawn",
                    session_id,
                    "{}",
                    self.clock(),
                ),
            )
            receipt_id = f"withdrawal-receipt-{token_urlsafe(8)}"
            response: dict[str, object] = {
                "schema_version": 1,
                "withdrawal_receipt_id": receipt_id,
                "participant_pseudonym": record["participant_pseudonym"],
                "terminal": True,
                "task_count": int(count),
            }
            connection.execute(
                "INSERT INTO withdrawal_receipts(id,participant_id,subject_session_id,response_json,created_at) VALUES(?,?,?,?,?)",
                (
                    receipt_id,
                    participant_id,
                    session_id,
                    json.dumps(response, separators=(",", ":")),
                    self.clock(),
                ),
            )
            self._after_withdrawal_receipt(
                connection,
                participant_id=participant_id,
                withdrawal_receipt_id=receipt_id,
            )
            return response

        result = self._mutate(
            f"research-withdraw:{participant_id}",
            key,
            {
                "participant_id": participant_id,
                "participant_pseudonym": record["participant_pseudonym"],
            },
            operation,
        )
        if event is not None:
            self._publish(session_id, event)
        return result

    def _after_withdrawal_receipt(
        self,
        connection: sqlite3.Connection,
        *,
        participant_id: str,
        withdrawal_receipt_id: str,
    ) -> None:
        """Schema-specific mapping hook; legacy M1 intentionally has no targets."""

        del connection, participant_id, withdrawal_receipt_id

    def withdrawal_status(self, session_id: str) -> dict[str, object]:
        record = self.research_session(session_id)
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT p.id participant_id,wr.response_json FROM sessions s JOIN participants p ON p.id=s.participant_id LEFT JOIN withdrawal_receipts wr ON wr.participant_id=p.id WHERE s.id=? AND s.session_kind='RESEARCH'",
                (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            if row["response_json"] is not None:
                response = json.loads(row["response_json"])
                if not isinstance(response, dict):
                    raise SchemaIntegrityError("withdrawal canonical response is malformed")
                return {str(name): value for name, value in response.items()}
            count = self.store.connection.execute(
                "SELECT COUNT(*) FROM withdrawal_tasks WHERE withdrawal_subject_session_id IN (SELECT id FROM sessions WHERE participant_id=?)",
                (row["participant_id"],),
            ).fetchone()[0]
        return {
            "schema_version": 1,
            "withdrawal_receipt_id": None,
            "participant_pseudonym": record["participant_pseudonym"],
            "terminal": False,
            "task_count": int(count),
        }

    def artifact_status(self, artifact_id: str) -> str:
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT status FROM artifact_registry WHERE id=?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return str(row["status"])

    def _partial_file(self, value: str) -> Path:
        path = Path(value)
        segments = value.replace("\\", "/").split("/")
        if (
            path.is_absolute()
            or len(segments) < 3
            or segments[:2] != ["staging", "partials"]
            or any(segment in {"", ".", ".."} for segment in segments)
        ):
            raise InvalidTransition(
                "Write intent must name a file within staging/partials"
            )
        source = self.store.root.joinpath(*segments)
        current = self.store.root
        try:
            for segment in segments:
                current /= segment
                metadata = current.lstat()
                if current.is_symlink() or bool(
                    getattr(metadata, "st_file_attributes", 0) & 0x400
                ):
                    raise InvalidTransition(
                        "Write intent may not reference a symlink or reparse point"
                    )
            resolved_namespace = (self.store.root / "staging" / "partials").resolve(
                strict=True
            )
            resolved = source.resolve(strict=True)
        except InvalidTransition:
            raise
        except OSError as exc:
            raise InvalidTransition("Write intent partial file is unavailable") from exc
        try:
            resolved.relative_to(resolved_namespace)
        except ValueError as exc:
            raise InvalidTransition("Write intent partial file escapes staging/partials") from exc
        try:
            if not stat.S_ISREG(source.lstat().st_mode):
                raise InvalidTransition("Write intent must reference a regular partial file")
        except OSError as exc:
            raise InvalidTransition("Write intent partial file is unavailable") from exc
        return resolved

    def _quarantine_directory(self) -> Path:
        operational = self.store.root / "operational"
        quarantine = operational / "quarantine"
        quarantine.mkdir(exist_ok=True)
        for path in (operational, quarantine):
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise SchemaIntegrityError("quarantine directory is unavailable") from exc
            if path.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                raise SchemaIntegrityError("quarantine directory traverses a reparse point")
        try:
            quarantine.resolve(strict=True).relative_to(operational.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise SchemaIntegrityError("quarantine directory is outside operational storage") from exc
        return quarantine.resolve(strict=True)

    def create_write_intent(self, session_id: str, manifest_relative_path: str) -> None:
        self._mutable_research(session_id)
        source = self._partial_file(manifest_relative_path)
        safe = source.relative_to(self.store.root)
        with self.store.transaction() as connection:
            self._require_mutable_research(connection, session_id)
            connection.execute(
                "INSERT INTO write_intents(id,session_id,manifest_relative_path,status,created_at) VALUES(?,?,?,'PENDING',?)",
                (f"intent-{token_urlsafe(8)}", session_id, str(safe), self.clock()),
            )

    def _recover_pending_intents(self) -> None:
        with self.store._lock:
            rows = self.store.connection.execute(
                "SELECT id,session_id,manifest_relative_path FROM write_intents WHERE status='PENDING'"
            ).fetchall()
        for row in rows:
            try:
                quarantine = self._quarantine_directory()
                source = self._partial_file(str(row["manifest_relative_path"]))
                for _ in range(8):
                    destination = quarantine / (
                        f"{row['id']}-{token_urlsafe(8)}-{source.name}"
                    )
                    if destination.exists():
                        continue
                    try:
                        source.rename(destination)
                    except FileExistsError:
                        continue
                    break
                else:
                    raise SchemaIntegrityError("unable to allocate a quarantine destination")
            except InvalidTransition:
                pass
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE write_intents SET status='QUARANTINED' WHERE id=?", (row["id"],)
                )
                session = connection.execute(
                    "SELECT s.state,p.withdrawn_at FROM sessions s "
                    "LEFT JOIN participants p ON p.id=s.participant_id WHERE s.id=?",
                    (row["session_id"],),
                ).fetchone()
                if session is None:
                    raise SchemaIntegrityError("pending write intent session is missing")
                recovered_state = (
                    SessionState.WITHDRAWN
                    if session["state"] == SessionState.WITHDRAWN
                    or session["withdrawn_at"] is not None
                    else SessionState.FAILED
                )
                connection.execute(
                    "UPDATE sessions SET state=?,collection_blocked=1 WHERE id=?",
                    (recovered_state, row["session_id"]),
                )

    def recovery(self, session_id: str) -> dict[str, object]:
        record = self.research_session(session_id)
        return {
            "schema_version": 1,
            "session_id": session_id,
            "state": record["state"],
            "collection_blocked": record["collection_blocked"],
            "reauthentication_required": True,
        }
