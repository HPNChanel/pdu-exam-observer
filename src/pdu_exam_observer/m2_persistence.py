"""Additive M2-P1 technical-artifact persistence over the immutable M1 schema."""
# ruff: noqa: E501

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sqlite3
import stat
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, RLock
from typing import Protocol, cast

from pdu_exam_observer.configuration import ConfigurationError, validate_storage_root
from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m1 import (
    _CHECKSUM as _V1_CHECKSUM,
)
from pdu_exam_observer.m1 import (
    _DDL as _V1_DDL,
)
from pdu_exam_observer.m1 import (
    _LEDGER_DDL,
    M1Store,
    SchemaIntegrityError,
    _canonical_schema_sql_objects,
    _schema_sql_objects,
)

_M2_DDL = """
CREATE TABLE artifact_manifests(
    artifact_id TEXT PRIMARY KEY REFERENCES artifact_registry(id),
    artifact_kind TEXT NOT NULL CHECK(artifact_kind='TECHNICAL_FIXTURE'),
    technical_input_kind TEXT NOT NULL CHECK(technical_input_kind IN ('DETERMINISTIC_FIXTURE','AI_RENDERED_FIXTURE')),
    manifest_schema_version INTEGER NOT NULL CHECK(manifest_schema_version=2),
    relative_path TEXT NOT NULL UNIQUE,
    byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    capture_profile_version TEXT NOT NULL,
    monotonic_timing_origin TEXT NOT NULL,
    processing_version TEXT NOT NULL,
    technical_failure_code TEXT,
    sealed_at REAL NOT NULL,
    validity_state TEXT NOT NULL CHECK(validity_state IN ('VALID','INVALIDATED'))
);
CREATE TABLE m2_write_intents(
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    artifact_id TEXT NOT NULL UNIQUE,
    partial_relative_path TEXT NOT NULL UNIQUE,
    final_relative_path TEXT NOT NULL UNIQUE,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING','SEALED','FAILED','QUARANTINED')),
    created_at REAL NOT NULL,
    terminal_at REAL
);
CREATE INDEX idx_m2_manifests_session ON artifact_registry(session_id);
CREATE INDEX idx_m2_intents_status ON m2_write_intents(status);
"""
_V2_CHECKSUM = hashlib.sha256((_LEDGER_DDL + _V1_DDL + _M2_DDL).encode("utf-8")).hexdigest()
_ALLOWED_INPUT_KINDS = frozenset(("DETERMINISTIC_FIXTURE", "AI_RENDERED_FIXTURE"))
_ALLOWED_FAILURES = frozenset(
    (
        "INPUT_UNAVAILABLE",
        "INPUT_MALFORMED",
        "ENCODER_WRITE_FAILED",
        "DISK_UNAVAILABLE",
        "DISK_FSYNC_FAILED",
        "ATOMIC_RENAME_FAILED",
        "MANIFEST_VALIDATION_FAILED",
        "SCHEMA_INCOMPATIBLE",
        "PRIVACY_STOP",
        "UNKNOWN_TECHNICAL_FAILURE",
    )
)
_CAPTURE_PROFILES = frozenset(("fixture-profile-v1", "ai-rendered-profile-v1"))
_TIMING_ORIGINS = frozenset(("synthetic-monotonic-v1", "ai-rendered-monotonic-v1"))
_PROCESSING_VERSIONS = frozenset(("fixture-generator-v1", "ai-renderer-v1"))


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.c_uint32),
        ("ftCreationTimeLow", ctypes.c_uint32),
        ("ftCreationTimeHigh", ctypes.c_uint32),
        ("ftLastAccessTimeLow", ctypes.c_uint32),
        ("ftLastAccessTimeHigh", ctypes.c_uint32),
        ("ftLastWriteTimeLow", ctypes.c_uint32),
        ("ftLastWriteTimeHigh", ctypes.c_uint32),
        ("dwVolumeSerialNumber", ctypes.c_uint32),
        ("nFileSizeHigh", ctypes.c_uint32),
        ("nFileSizeLow", ctypes.c_uint32),
        ("nNumberOfLinks", ctypes.c_uint32),
        ("nFileIndexHigh", ctypes.c_uint32),
        ("nFileIndexLow", ctypes.c_uint32),
    ]


class PersistenceFailure(RuntimeError):
    """A P1 artifact was not safely sealed and must not be treated as valid."""


class StoreOwnerUnavailable(PersistenceFailure):
    """The operating-system root lease is already held by another P1 store."""


class PlatformUnsupported(PersistenceFailure):
    """This platform may validate metadata but may not seal P1 artifacts."""


class ArtifactBytes(Protocol):
    """A deterministic or AI-rendered source; never a caller-provided filesystem path."""

    def read_bytes(self) -> bytes: ...


@dataclass(frozen=True)
class StaticArtifactSource:
    payload: bytes

    def read_bytes(self) -> bytes:
        return self.payload


@dataclass(frozen=True)
class ArtifactIntent:
    intent_id: str
    artifact_id: str
    session_id: str
    artifact_kind: str
    technical_input_kind: str
    capture_profile_version: str
    monotonic_timing_origin: str
    processing_version: str
    parent_ids: tuple[str, ...] = ()
    technical_failure_code: str | None = None


class M2PersistenceStore:
    """A v2 validator and technical artifact seam, intentionally separate from ``M1Backend``."""

    schema_version = 2
    _root_locks: dict[str, RLock] = {}
    _root_locks_guard = Lock()

    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], float] = time.time,
        migration_fault: Callable[[], None] | None = None,
        before_commit: Callable[[], None] | None = None,
        fault_hook: Callable[[str], None] | None = None,
        after_rename: Callable[[Path], None] | None = None,
        before_rename: Callable[[Path], None] | None = None,
        before_handle_open: Callable[[Path], None] | None = None,
    ) -> None:
        self.clock = clock
        self._migration_fault = migration_fault
        self._before_commit = before_commit
        self._fault_hook = fault_hook
        self._after_rename = after_rename
        self._before_rename = before_rename
        self._before_handle_open = before_handle_open
        self._durability_state = "PLATFORM_UNSUPPORTED" if os.name == "nt" else "CONFIRMED"
        self._lease: tuple[str, int] = ("unacquired", -1)
        self._lifetime_directory_handles: list[int] = []
        self._lifetime_database_handles: dict[Path, int] = {}
        self._sidecar_anchor: sqlite3.Connection | None = None
        self._cleanup_limitation: str | None = None
        try:
            self.root = validate_storage_root(root, create=False)
        except ConfigurationError as exc:
            raise SchemaIntegrityError("existing v1 storage root is required") from exc
        operational = self.root / "operational"
        try:
            M1Store._validated_child(
                self.root, operational, "operational directory", directory=True
            )
        except (ConfigurationError, SchemaIntegrityError) as exc:
            raise SchemaIntegrityError("existing v1 operational database is required") from exc

        self.connection: sqlite3.Connection
        try:
            if os.name == "nt":
                self._lifetime_directory_handles.append(
                    self._windows_open_checked(self.root, directory=True, share=3)
                )
                self._lifetime_directory_handles.append(
                    self._windows_open_checked(operational, directory=True, share=3)
                )
            database = operational / "pdu-exam-observer.sqlite3"
            try:
                M1Store._validated_child(
                    operational, database, "operational database", directory=False
                )
            except SchemaIntegrityError as exc:
                raise SchemaIntegrityError(
                    "existing v1 operational database is required"
                ) from exc
            self.database_path = database
            if os.name == "nt":
                self._guard_sqlite_leaf(database, "operational database")
            self._lease = self._acquire_root_lease(operational)
            if os.name == "nt":
                self._reserve_sqlite_sidecars()
            with self._root_locks_guard:
                self._root_lock = self._root_locks.setdefault(str(self.root), RLock())
            self._lock = RLock()
            self.connection = sqlite3.connect(
                self.database_path, isolation_level=None, check_same_thread=False
            )
            self.connection.row_factory = sqlite3.Row
            journal = str(self.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if journal != "wal":
                raise SchemaIntegrityError("SQLite WAL could not be enabled")
            self.connection.execute("PRAGMA foreign_keys=ON")
            self._migrate_and_validate()
            self.recover()
        except Exception:
            try:
                self._cleanup_live_connection()
            finally:
                try:
                    self._release_sqlite_sidecar_handles()
                finally:
                    try:
                        self._close_sidecar_anchor()
                    finally:
                        try:
                            self._release_lifetime_database_handles()
                        finally:
                            try:
                                self._release_root_lease()
                            finally:
                                self._release_lifetime_directory_handles()
            raise

    def close(self) -> None:
        try:
            with self._lock:
                self._cleanup_live_connection()
        finally:
            try:
                self._release_sqlite_sidecar_handles()
            finally:
                try:
                    self._close_sidecar_anchor()
                finally:
                    try:
                        self._release_lifetime_database_handles()
                    finally:
                        try:
                            self._release_root_lease()
                        finally:
                            self._release_lifetime_directory_handles()

    @staticmethod
    def _acquire_root_lease(operational: Path) -> tuple[str, int]:
        lease_path = operational / "p1-store.lock"
        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            create_file = kernel32.CreateFileW
            create_file.restype = ctypes.c_void_p
            handle = create_file(
                str(lease_path),
                0x80000000 | 0x40000000,
                0,
                None,
                4,
                0x80 | 0x200000,
                None,
            )
            if handle in (None, ctypes.c_void_p(-1).value):
                raise StoreOwnerUnavailable("STORE_OWNER_UNAVAILABLE")
            information = _ByHandleFileInformation()
            if not ctypes.windll.kernel32.GetFileInformationByHandle(
                handle, ctypes.byref(information)
            ) or information.dwFileAttributes & (0x400 | 0x10):
                ctypes.windll.kernel32.CloseHandle(handle)
                raise PersistenceFailure("lease handle is not a normal file")
            return ("windows", int(handle))
        descriptor = os.open(lease_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl = __import__("fcntl")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(descriptor)
            raise StoreOwnerUnavailable("STORE_OWNER_UNAVAILABLE") from exc
        return ("posix", descriptor)

    def _release_root_lease(self) -> None:
        kind, handle = self._lease
        if handle < 0:
            return
        self._lease = (kind, -1)
        if kind == "windows":
            ctypes.windll.kernel32.CloseHandle(handle)
            return
        fcntl = __import__("fcntl")
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            os.close(handle)

    def _release_lifetime_directory_handles(self) -> None:
        handles = self._lifetime_directory_handles
        self._lifetime_directory_handles = []
        if os.name != "nt":
            return
        for handle in reversed(handles):
            ctypes.windll.kernel32.CloseHandle(handle)

    def _release_lifetime_database_handles(self) -> None:
        handles = self._lifetime_database_handles
        self._lifetime_database_handles = {}
        if os.name != "nt":
            return
        for handle in reversed(tuple(handles.values())):
            ctypes.windll.kernel32.CloseHandle(handle)

    def _cleanup_live_connection(self) -> None:
        if not hasattr(self, "connection"):
            return
        connection = self.connection
        safe_to_release_sidecars = False
        try:
            if connection.in_transaction:
                connection.rollback()
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("PRAGMA query_only=ON")
            safe_to_release_sidecars = True
        except sqlite3.Error:
            self._cleanup_limitation = "SQLITE_CLEANUP_GUARDED_CLOSE"
        try:
            if safe_to_release_sidecars:
                self._release_sqlite_sidecar_handles()
            connection.close()
        finally:
            self._release_sqlite_sidecar_handles()

    def _release_sqlite_sidecar_handles(self) -> None:
        for path, handle in tuple(self._lifetime_database_handles.items()):
            if path == self.database_path:
                continue
            del self._lifetime_database_handles[path]
            if os.name == "nt":
                ctypes.windll.kernel32.CloseHandle(handle)

    def _close_sidecar_anchor(self) -> None:
        if self._sidecar_anchor is None:
            return
        anchor = self._sidecar_anchor
        self._sidecar_anchor = None
        anchor.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._root_lock, self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
            except Exception:
                self.connection.execute("ROLLBACK")
                raise
            else:
                self.connection.execute("COMMIT")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Expose the sole guarded transaction seam to the injected M1 backend."""

        with self._transaction() as connection:
            yield connection

    @contextmanager
    def read_transaction(self) -> Iterator[sqlite3.Connection]:
        """Hold one stable read snapshot without acquiring a write transaction."""

        with self._root_lock, self._lock:
            self.connection.execute("BEGIN")
            try:
                yield self.connection
            except Exception:
                self.connection.execute("ROLLBACK")
                raise
            else:
                self.connection.execute("COMMIT")

    @staticmethod
    def require_valid_parents(
        connection: sqlite3.Connection, parents: tuple[str, ...]
    ) -> None:
        """Apply the accepted M1 parent invariant on the shared connection."""

        M1Store.require_valid_parents(connection, parents)

    @staticmethod
    def _ledger_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT version,applied_at_utc,checksum FROM schema_migrations ORDER BY version"
        ).fetchall()

    def _migrate_and_validate(self) -> None:
        ledger = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if ledger is None:
            raise SchemaIntegrityError("schema migration ledger is malformed")
        rows = self._ledger_rows(self.connection)
        if len(rows) == 1:
            self._validate_v1_ledger(rows)
            try:
                with self._transaction() as connection:
                    for statement in _M2_DDL.split(";"):
                        if statement.strip():
                            connection.execute(statement)
                    if self._migration_fault is not None:
                        self._migration_fault()
                    connection.execute(
                        "INSERT INTO schema_migrations(version,applied_at_utc,checksum) VALUES(?,?,?)",
                        (2, datetime.now(UTC).isoformat(), _V2_CHECKSUM),
                    )
            except Exception as exc:
                if isinstance(exc, SchemaIntegrityError | PersistenceFailure):
                    raise
                raise PersistenceFailure("v1-to-v2 migration rolled back") from exc
        self._validate_v2()

    @staticmethod
    def _validate_v1_ledger(rows: list[sqlite3.Row]) -> None:
        row = rows[0]
        if (
            int(row["version"]) != 1
            or not str(row["applied_at_utc"])
            or str(row["checksum"]) != _V1_CHECKSUM
        ):
            raise SchemaIntegrityError("schema migration checksum is invalid or newer than this runtime")

    def _validate_v2(self) -> None:
        rows = self._ledger_rows(self.connection)
        if len(rows) != 2:
            raise SchemaIntegrityError("schema migration ledger is malformed or newer than this runtime")
        self._validate_v1_ledger(rows[:1])
        v2 = rows[1]
        if (
            int(v2["version"]) != 2
            or not str(v2["applied_at_utc"])
            or str(v2["checksum"]) != _V2_CHECKSUM
        ):
            raise SchemaIntegrityError("schema migration checksum is invalid or newer than this runtime")
        trusted = sqlite3.connect(":memory:")
        try:
            trusted.executescript(_LEDGER_DDL + _V1_DDL + _M2_DDL)
            expected = _schema_sql_objects(trusted)
        finally:
            trusted.close()
        if expected != _canonical_schema_sql_objects() | {
            key: value
            for key, value in expected.items()
            if key[1] in {"artifact_manifests", "m2_write_intents", "idx_m2_manifests_session", "idx_m2_intents_status"}
        }:
            raise SchemaIntegrityError("canonical v1 schema construction is inconsistent")
        try:
            if _schema_sql_objects(self.connection) != expected:
                raise SchemaIntegrityError("schema object is missing or malformed")
            if self.connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise SchemaIntegrityError("foreign key check failed")
        except sqlite3.DatabaseError as exc:
            raise SchemaIntegrityError("schema object is missing or malformed") from exc

    def ledger_versions(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(int(row["version"]) for row in self._ledger_rows(self.connection))

    @staticmethod
    def _opaque(value: str, label: str) -> None:
        if not 1 <= len(value) <= 128 or not all(ch.isascii() and (ch.isalnum() or ch in "-_") for ch in value):
            raise PersistenceFailure(f"invalid opaque {label}")

    @classmethod
    def _validate_intent(cls, intent: ArtifactIntent) -> None:
        for label, value in (
            ("intent id", intent.intent_id),
            ("artifact id", intent.artifact_id),
            ("session id", intent.session_id),
        ):
            cls._opaque(value, label)
        if intent.artifact_kind != "TECHNICAL_FIXTURE":
            raise PersistenceFailure("artifact kind is not authorized for P1")
        if intent.technical_input_kind not in _ALLOWED_INPUT_KINDS:
            raise PersistenceFailure("technical input kind is not authorized for P1")
        allowed_metadata = (
            ("capture profile version", intent.capture_profile_version, _CAPTURE_PROFILES),
            ("monotonic timing origin", intent.monotonic_timing_origin, _TIMING_ORIGINS),
            ("processing version", intent.processing_version, _PROCESSING_VERSIONS),
        )
        for label, value, allowed in allowed_metadata:
            if value not in allowed:
                raise PersistenceFailure(f"{label} is not allowlisted for P1")
        if intent.technical_failure_code not in _ALLOWED_FAILURES | {None}:
            raise PersistenceFailure("technical failure code is not allowlisted")
        if intent.artifact_id in intent.parent_ids:
            raise InvalidTransition("artifact parent cycle is not allowed")
        if len(set(intent.parent_ids)) != len(intent.parent_ids):
            raise PersistenceFailure("duplicate artifact parent")
        for parent in intent.parent_ids:
            cls._opaque(parent, "parent id")

    def _require_mutable_retained(self, connection: sqlite3.Connection, session_id: str) -> None:
        row = connection.execute(
            "SELECT s.state,s.collection_blocked,p.withdrawn_at,"
            "EXISTS(SELECT 1 FROM retention_records r WHERE r.session_id=s.id) retention_recorded "
            "FROM sessions s JOIN participants p ON p.id=s.participant_id "
            "WHERE s.id=? AND s.session_kind='RESEARCH'",
            (session_id,),
        ).fetchone()
        if row is None:
            raise InvalidTransition("research session is missing")
        if row["withdrawn_at"] is not None or row["state"] == "WITHDRAWN" or row["collection_blocked"]:
            raise InvalidTransition("Withdrawn or blocked research records cannot be mutated")
        if not row["retention_recorded"]:
            raise InvalidTransition("retention decision is required")

    def _require_valid_parents(
        self, connection: sqlite3.Connection, session_id: str, parents: tuple[str, ...]
    ) -> None:
        for parent in parents:
            row = connection.execute(
                "SELECT a.status,a.session_id,s.state,p.withdrawn_at FROM artifact_registry a "
                "JOIN sessions s ON s.id=a.session_id JOIN participants p ON p.id=s.participant_id "
                "WHERE a.id=?",
                (parent,),
            ).fetchone()
            if row is None or row["status"] != "VALID" or row["state"] == "WITHDRAWN" or row["withdrawn_at"] is not None:
                raise InvalidTransition("artifact parent is missing or invalidated")
            if row["session_id"] != session_id:
                raise InvalidTransition("artifact parent belongs to another session")

    @staticmethod
    def _request_hash(intent: ArtifactIntent, payload: bytes) -> str:
        document = {
            "intent": {
                "intent_id": intent.intent_id,
                "artifact_id": intent.artifact_id,
                "session_id": intent.session_id,
                "artifact_kind": intent.artifact_kind,
                "technical_input_kind": intent.technical_input_kind,
                "capture_profile_version": intent.capture_profile_version,
                "monotonic_timing_origin": intent.monotonic_timing_origin,
                "processing_version": intent.processing_version,
                "parent_ids": intent.parent_ids,
                "technical_failure_code": intent.technical_failure_code,
            },
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _safe_directory(parent: Path, name: str, label: str) -> Path:
        child = parent / name
        try:
            child.mkdir(exist_ok=True)
            before = parent.resolve(strict=True)
            metadata = child.lstat()
            after = parent.resolve(strict=True)
            resolved = child.resolve(strict=True)
        except OSError as exc:
            raise PersistenceFailure(f"{label} is unavailable") from exc
        if before != after or stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
            raise PersistenceFailure(f"{label} may not be a symlink or reparse point")
        if not stat.S_ISDIR(metadata.st_mode):
            raise PersistenceFailure(f"{label} is not a directory")
        try:
            resolved.relative_to(after)
        except ValueError as exc:
            raise PersistenceFailure(f"{label} escapes storage root") from exc
        return resolved

    def _paths(self, artifact_id: str) -> tuple[Path, Path, str, str]:
        staging = self._safe_directory(self.root, "staging", "staging directory")
        partials = self._safe_directory(staging, "m2-partials", "partial directory")
        artifacts = self._safe_directory(self.root, "artifacts", "artifact directory")
        final_dir = self._safe_directory(artifacts, "m2", "M2 artifact directory")
        partial = partials / f"{artifact_id}.part"
        final = final_dir / f"{artifact_id}.bin"
        return partial, final, str(partial.relative_to(self.root)), str(final.relative_to(self.root))

    def _windows_open_checked(
        self, path: Path, *, directory: bool, share: int, invoke_hook: bool = True
    ) -> int:
        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attributes == 0xFFFFFFFF or attributes & 0x400:
            raise PersistenceFailure("reparse-safe handle acquisition failed")
        if invoke_hook and self._before_handle_open is not None:
            self._before_handle_open(path)
        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.restype = ctypes.c_void_p
        flags = 0x200000 | (0x02000000 if directory else 0)
        handle = create_file(str(path), 0x80000000, share, None, 3, flags, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise PersistenceFailure("exclusive handle acquisition failed")
        information = _ByHandleFileInformation()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(
            handle, ctypes.byref(information)
        ) or information.dwFileAttributes & 0x400:
            ctypes.windll.kernel32.CloseHandle(handle)
            raise PersistenceFailure("actual handle is a reparse point")
        buffer = ctypes.create_unicode_buffer(32768)
        size = ctypes.windll.kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        resolved = buffer.value.removeprefix("\\\\?\\")
        try:
            Path(resolved).relative_to(self.root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            ctypes.windll.kernel32.CloseHandle(handle)
            raise PersistenceFailure("handle path escapes approved root") from exc
        if size == 0:
            ctypes.windll.kernel32.CloseHandle(handle)
            raise PersistenceFailure("handle path verification failed")
        return cast(int, handle)

    def _guard_sqlite_leaf(self, path: Path, label: str, *, invoke_hook: bool = True) -> None:
        if path in self._lifetime_database_handles:
            return
        handle = self._windows_open_checked(
            path, directory=False, share=3, invoke_hook=invoke_hook
        )
        try:
            self._validate_sqlite_leaf_handle(handle, path, label)
        except Exception:
            ctypes.windll.kernel32.CloseHandle(handle)
            raise
        self._lifetime_database_handles[path] = handle

    def _validate_sqlite_leaf_handle(self, handle: int, path: Path, label: str) -> None:
        information = _ByHandleFileInformation()
        if not ctypes.windll.kernel32.GetFileInformationByHandle(
            handle, ctypes.byref(information)
        ) or information.dwFileAttributes & (0x400 | 0x10):
            raise PersistenceFailure(f"{label} handle is not a regular file")
        buffer = ctypes.create_unicode_buffer(32768)
        size = ctypes.windll.kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if size == 0:
            raise PersistenceFailure(f"{label} handle path verification failed")
        actual = os.path.normcase(os.path.normpath(buffer.value.removeprefix("\\\\?\\")))
        expected = os.path.normcase(os.path.normpath(str(path.resolve(strict=True))))
        if actual != expected:
            raise PersistenceFailure(f"{label} handle does not match the derived path")

    def _reserve_sqlite_sidecars(self) -> None:
        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.restype = ctypes.c_void_p
        for suffix in ("-wal", "-shm"):
            sidecar = self.database_path.with_name(f"{self.database_path.name}{suffix}")
            ctypes.windll.kernel32.GetFileAttributesW(str(sidecar))
            if self._before_handle_open is not None:
                self._before_handle_open(sidecar)
            for attempt in range(2):
                handle = create_file(
                    str(sidecar),
                    0x80000000 | 0x40000000,
                    3,
                    None,
                    1,
                    0x80 | 0x200000,
                    None,
                )
                if handle not in (None, ctypes.c_void_p(-1).value):
                    try:
                        self._validate_sqlite_leaf_handle(
                            cast(int, handle), sidecar, "SQLite sidecar"
                        )
                    except Exception:
                        ctypes.windll.kernel32.CloseHandle(handle)
                        raise
                    self._lifetime_database_handles[sidecar] = cast(int, handle)
                    break
                if ctypes.windll.kernel32.GetLastError() not in {80, 183}:
                    raise PersistenceFailure("SQLite sidecar reservation failed")
                self._on_existing_sqlite_sidecar(sidecar)
                try:
                    self._guard_sqlite_leaf(sidecar, "SQLite sidecar", invoke_hook=False)
                    break
                except PersistenceFailure:
                    if attempt or os.path.lexists(sidecar):
                        raise PersistenceFailure("SQLite sidecar is unsafe") from None
            else:
                raise PersistenceFailure("SQLite sidecar reservation failed")

    def _on_existing_sqlite_sidecar(self, _sidecar: Path) -> None:
        """Allow stricter owners to reject a raced-existing SQLite sidecar."""

    def _guard_existing_sqlite_sidecars(self, operational: Path, *, require_all: bool) -> None:
        for suffix in ("-wal", "-shm"):
            sidecar = self.database_path.with_name(f"{self.database_path.name}{suffix}")
            if not os.path.lexists(sidecar):
                if require_all:
                    raise PersistenceFailure("SQLite sidecar guard is unavailable")
                continue
            try:
                M1Store._validated_child(
                    operational, sidecar, "SQLite sidecar", directory=False
                )
            except SchemaIntegrityError as exc:
                raise PersistenceFailure("SQLite sidecar is unsafe") from exc
            self._guard_sqlite_leaf(sidecar, "SQLite sidecar")

    @contextmanager
    def _directory_guards(self) -> Iterator[None]:
        if os.name != "nt":
            yield
            return
        staging = self._safe_directory(self.root, "staging", "staging directory")
        partials = self._safe_directory(staging, "m2-partials", "partial directory")
        artifacts = self._safe_directory(self.root, "artifacts", "artifact directory")
        artifact_m2 = self._safe_directory(artifacts, "m2", "M2 artifact directory")
        operational = self._safe_directory(self.root, "operational", "operational directory")
        quarantine = self._safe_directory(operational, "quarantine", "quarantine directory")
        directories = (self.root, staging, partials, artifacts, artifact_m2, quarantine)
        handles: list[int] = []
        try:
            for directory in directories:
                handles.append(self._windows_open_checked(directory, directory=True, share=3))
            yield
        finally:
            for handle in reversed(handles):
                ctypes.windll.kernel32.CloseHandle(handle)

    def _write_durable(self, path: Path, payload: bytes) -> None:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            directory_descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        except OSError as exc:
            if os.name == "nt":
                self._durability_state = "PLATFORM_UNSUPPORTED"
                return
            raise PersistenceFailure("DISK_FSYNC_FAILED") from exc
        try:
            try:
                os.fsync(directory_descriptor)
            except OSError as exc:
                if os.name == "nt":
                    self._durability_state = "PLATFORM_UNSUPPORTED"
                else:
                    raise PersistenceFailure("DISK_FSYNC_FAILED") from exc
        finally:
            os.close(directory_descriptor)

    def _open_final_guard(self, path: Path, expected_size: int, expected_digest: str) -> int:
        descriptor: int
        try:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
                raise PersistenceFailure("final object is a symlink or reparse point")
            if os.name == "nt":
                raw_handle = self._windows_open_checked(path, directory=False, share=0)
                descriptor = __import__("msvcrt").open_osfhandle(
                    raw_handle, os.O_RDONLY | getattr(os, "O_BINARY", 0)
                )
            else:
                flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(path, flags)
        except OSError as exc:
            raise PersistenceFailure("final object could not be guarded") from exc
        try:
            self._verify_final_guard(path, descriptor, expected_size, expected_digest)
        except Exception:
            os.close(descriptor)
            raise
        return descriptor

    @staticmethod
    def _verify_final_guard(
        path: Path, descriptor: int, expected_size: int, expected_digest: str
    ) -> None:
        try:
            handle_stat = os.fstat(descriptor)
            path_stat = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(handle_stat.st_mode) or handle_stat.st_size != expected_size:
                raise PersistenceFailure("final object verification failed")
            if (handle_stat.st_dev, handle_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
                raise PersistenceFailure("final object identity changed")
            digest = hashlib.sha256()
            os.lseek(descriptor, 0, os.SEEK_SET)
            while block := os.read(descriptor, 65536):
                digest.update(block)
            if digest.hexdigest() != expected_digest:
                raise PersistenceFailure("final object hash verification failed")
        except OSError as exc:
            raise PersistenceFailure("final object verification failed") from exc

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        count = 0
        with path.open("rb") as handle:
            while block := handle.read(65536):
                count += len(block)
                digest.update(block)
        return count, digest.hexdigest()

    def _create_intent(
        self, intent: ArtifactIntent, request_hash: str, partial_relative: str, final_relative: str
    ) -> dict[str, object] | None:
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT request_hash,status,artifact_id FROM m2_write_intents WHERE id=?", (intent.intent_id,)
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise PersistenceFailure("idempotency key was reused with a different request")
                if existing["status"] == "SEALED":
                    return self._receipt(connection, str(existing["artifact_id"]))
                raise PersistenceFailure("intent is already terminal or pending")
            self._require_mutable_retained(connection, intent.session_id)
            self._require_valid_parents(connection, intent.session_id, intent.parent_ids)
            if connection.execute("SELECT 1 FROM artifact_registry WHERE id=?", (intent.artifact_id,)).fetchone():
                raise PersistenceFailure("artifact id already exists")
            connection.execute(
                "INSERT INTO m2_write_intents(id,session_id,artifact_id,partial_relative_path,final_relative_path,request_hash,status,created_at) "
                "VALUES(?,?,?,?,?,?, 'PENDING',?)",
                (intent.intent_id, intent.session_id, intent.artifact_id, partial_relative, final_relative, request_hash, self.clock()),
            )
        return None

    def _mark_failed(self, intent_id: str, partial: Path, final: Path) -> None:
        quarantined = False
        try:
            quarantined = self._quarantine(partial, intent_id)
            quarantined = self._quarantine(final, intent_id) or quarantined
        except OSError:
            quarantined = False
        with self._transaction() as connection:
            connection.execute(
                "UPDATE m2_write_intents SET status=?,terminal_at=? "
                "WHERE id=? AND status='PENDING'",
                ("QUARANTINED" if quarantined else "FAILED", self.clock(), intent_id),
            )

    def _fault(self, stage: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(stage)

    def persist(self, intent: ArtifactIntent, source: ArtifactBytes) -> dict[str, object]:
        if os.name != "nt":
            raise PlatformUnsupported("PLATFORM_UNSUPPORTED: artifact sealing is Windows-only")
        with self._root_lock:
            with self._directory_guards():
                return self._persist_locked(intent, source)

    def _persist_locked(self, intent: ArtifactIntent, source: ArtifactBytes) -> dict[str, object]:
        self._validate_intent(intent)
        try:
            payload = source.read_bytes()
        except Exception as exc:
            raise PersistenceFailure("artifact write source failed") from exc
        if not isinstance(payload, bytes) or not payload:
            raise PersistenceFailure("artifact bytes are missing or malformed")
        request_hash = self._request_hash(intent, payload)
        partial, final, partial_relative, final_relative = self._paths(intent.artifact_id)
        replay = self._create_intent(intent, request_hash, partial_relative, final_relative)
        if replay is not None:
            return replay
        try:
            self._fault("write")
            self._write_durable(partial, payload)
            self._fault("fsync")
            self._fault("hash")
            size, digest = self._hash_file(partial)
            if size != len(payload) or digest != hashlib.sha256(payload).hexdigest():
                raise PersistenceFailure("artifact hash verification failed")
            self._fault("rename")
            if self._before_rename is not None:
                self._before_rename(final)
            os.replace(partial, final)
            guard = self._open_final_guard(final, size, digest)
            try:
                if self._after_rename is not None:
                    try:
                        self._after_rename(final)
                    except Exception as exc:
                        raise PersistenceFailure("final guard rejected post-rename mutation") from exc
                self._verify_final_guard(final, guard, size, digest)
                if self._before_commit is not None:
                    self._before_commit()
                with self._transaction() as connection:
                    self._require_mutable_retained(connection, intent.session_id)
                    self._require_valid_parents(connection, intent.session_id, intent.parent_ids)
                    self._verify_final_guard(final, guard, size, digest)
                    connection.execute(
                    "INSERT INTO artifact_registry(id,session_id,status,created_at) VALUES(?,?, 'VALID',?)",
                    (intent.artifact_id, intent.session_id, self.clock()),
                )
                    connection.execute(
                    "INSERT INTO artifact_manifests(artifact_id,artifact_kind,technical_input_kind,manifest_schema_version,relative_path,byte_size,sha256,capture_profile_version,monotonic_timing_origin,processing_version,technical_failure_code,sealed_at,validity_state) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'VALID')",
                    (intent.artifact_id, intent.artifact_kind, intent.technical_input_kind, 2, final_relative, size, digest, intent.capture_profile_version, intent.monotonic_timing_origin, intent.processing_version, intent.technical_failure_code, self.clock()),
                )
                    self._after_manifest_insert(
                        connection,
                        intent=intent,
                        relative_path=final_relative,
                        byte_size=size,
                        sha256=digest,
                    )
                    for parent in intent.parent_ids:
                        connection.execute(
                        "INSERT INTO artifact_dependencies(parent_artifact_id,child_artifact_id) VALUES(?,?)",
                        (parent, intent.artifact_id),
                    )
                    sequence = int(connection.execute("SELECT event_seq FROM sessions WHERE id=?", (intent.session_id,)).fetchone()[0]) + 1
                    connection.execute("UPDATE sessions SET event_seq=? WHERE id=?", (sequence, intent.session_id))
                    payload_json = json.dumps({"artifact_id": intent.artifact_id, "schema_version": 2}, separators=(",", ":"))
                    connection.execute(
                    "INSERT INTO session_events(session_id,event_seq,event_type,payload_json,created_at) VALUES(?,?, 'M2ArtifactSealed',?,?)",
                    (intent.session_id, sequence, payload_json, self.clock()),
                )
                    connection.execute(
                    "INSERT INTO audit_events(id,event_type,session_id,payload_json,created_at) VALUES(?,?,?, ?,?)",
                    (f"m2-audit-{intent.intent_id}", "M2_ARTIFACT_SEALED", intent.session_id, payload_json, self.clock()),
                )
                    connection.execute(
                    "UPDATE m2_write_intents SET status='SEALED',terminal_at=? WHERE id=?",
                    (self.clock(), intent.intent_id),
                )
                    self._fault("db_commit")
                    return self._receipt(connection, intent.artifact_id)
            finally:
                os.close(guard)
        except (InvalidTransition, PersistenceFailure):
            self._mark_failed(intent.intent_id, partial, final)
            raise
        except Exception as exc:
            self._mark_failed(intent.intent_id, partial, final)
            raise PersistenceFailure("artifact write, fsync, rename, or commit failed") from exc

    def _after_manifest_insert(
        self,
        connection: sqlite3.Connection,
        *,
        intent: ArtifactIntent,
        relative_path: str,
        byte_size: int,
        sha256: str,
    ) -> None:
        """Schema-specific atomic registration hook; v2 intentionally does nothing."""

        del connection, intent, relative_path, byte_size, sha256

    def _receipt(self, connection: sqlite3.Connection, artifact_id: str) -> dict[str, object]:
        row = connection.execute(
            "SELECT m.artifact_id,m.artifact_kind,m.technical_input_kind,m.byte_size,m.sha256,"
            "m.manifest_schema_version,a.status validity_state,m.sealed_at "
            "FROM artifact_manifests m JOIN artifact_registry a ON a.id=m.artifact_id "
            "WHERE m.artifact_id=?",
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise SchemaIntegrityError("sealed intent is missing its manifest")
        result = {str(key): row[key] for key in row.keys()}
        result["durability_state"] = self._durability_state
        return result

    def manifest(self, artifact_id: str) -> dict[str, object]:
        self._opaque(artifact_id, "artifact id")
        with self._lock:
            row = self.connection.execute(
                "SELECT m.artifact_id,m.artifact_kind,m.technical_input_kind,"
                "m.manifest_schema_version,m.relative_path,m.byte_size,m.sha256,"
                "m.capture_profile_version,m.monotonic_timing_origin,m.processing_version,"
                "m.technical_failure_code,m.sealed_at,a.status validity_state "
                "FROM artifact_manifests m JOIN artifact_registry a ON a.id=m.artifact_id "
                "WHERE m.artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        result = {str(key): row[key] for key in row.keys()}
        result["durability_state"] = self._durability_state
        return result

    def manifest_or_none(self, artifact_id: str) -> dict[str, object] | None:
        try:
            return self.manifest(artifact_id)
        except KeyError:
            return None

    def intent_status(self, intent_id: str) -> str:
        self._opaque(intent_id, "intent id")
        with self._lock:
            row = self.connection.execute("SELECT status FROM m2_write_intents WHERE id=?", (intent_id,)).fetchone()
        if row is None:
            raise KeyError(intent_id)
        return str(row["status"])

    def create_pending_intent_for_test(self, intent: ArtifactIntent) -> None:
        """Test-only seeding hook; production callers must use ``persist``."""
        self._validate_intent(intent)
        partial, final, partial_relative, final_relative = self._paths(intent.artifact_id)
        del partial, final
        self._create_intent(intent, self._request_hash(intent, b"test-pending"), partial_relative, final_relative)

    def _quarantine(self, path: Path, label: str) -> bool:
        if not path.exists():
            return False
        operational = self._safe_directory(self.root, "operational", "operational directory")
        quarantine = self._safe_directory(operational, "quarantine", "quarantine directory")
        target = quarantine / f"m2-{label}-{hashlib.sha256(str(path).encode()).hexdigest()[:12]}.quarantine"
        os.replace(path, target)
        return True

    def recover(self) -> dict[str, int]:
        with self._root_lock:
            with self._directory_guards():
                return self._recover_guarded()

    def _recover_guarded(self) -> dict[str, int]:
        quarantined = 0
        with self._root_lock, self._lock:
            rows = self.connection.execute(
                "SELECT id,session_id,artifact_id,partial_relative_path,final_relative_path "
                "FROM m2_write_intents WHERE status IN ('PENDING','FAILED')"
            ).fetchall()
        for row in rows:
            partial, final, expected_partial, expected_final = self._paths(str(row["artifact_id"]))
            stored_paths_match = (
                str(row["partial_relative_path"]) == expected_partial
                and str(row["final_relative_path"]) == expected_final
            )
            moved = False
            if stored_paths_match:
                moved = self._quarantine(partial, str(row["id"]))
                moved = self._quarantine(final, str(row["id"])) or moved
            if moved:
                quarantined += 1
            self._terminalize_recovery(str(row["id"]), str(row["session_id"]))
        final_dir = self._safe_directory(
            self._safe_directory(self.root, "artifacts", "artifact directory"),
            "m2",
            "M2 artifact directory",
        )
        for orphan in final_dir.glob("*.bin"):
            artifact_id = orphan.stem
            with self._root_lock, self._lock:
                known = self.connection.execute(
                    "SELECT 1 FROM artifact_manifests WHERE artifact_id=?", (artifact_id,)
                ).fetchone()
            if known is None and self._quarantine(orphan, "orphan"):
                quarantined += 1
        return {"quarantined": quarantined}

    def _terminalize_recovery(self, intent_id: str, session_id: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE m2_write_intents SET status='QUARANTINED',terminal_at=? "
                "WHERE id=? AND status IN ('PENDING','FAILED')",
                (self.clock(), intent_id),
            )
            state = connection.execute(
                "SELECT state,event_seq FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if state is None or state["state"] == "WITHDRAWN":
                return
            sequence = int(state["event_seq"]) + 1
            connection.execute(
                "UPDATE sessions SET state='FAILED',collection_blocked=1,event_seq=? WHERE id=?",
                (sequence, session_id),
            )
            payload = json.dumps({"intent_id": intent_id}, separators=(",", ":"))
            connection.execute(
                "INSERT INTO session_events(session_id,event_seq,event_type,payload_json,created_at) "
                "VALUES(?,?, 'M2IntentQuarantined',?,?)",
                (session_id, sequence, payload, self.clock()),
            )
            connection.execute(
                "INSERT INTO audit_events(id,event_type,session_id,payload_json,created_at) VALUES(?,?,?,?,?)",
                (f"m2-recovery-{intent_id}", "M2_INTENT_QUARANTINED", session_id, payload, self.clock()),
            )
