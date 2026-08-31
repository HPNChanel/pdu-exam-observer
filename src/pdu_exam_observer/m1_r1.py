"""M1-R1 schema-v3 readiness and explicit source-only migration seam."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sqlite3
import unicodedata
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol, cast

from pdu_exam_observer.configuration import ConfigurationError, validate_storage_root
from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m1 import (
    _DDL as _V1_DDL,
)
from pdu_exam_observer.m1 import (
    _LEDGER_DDL,
    M1Backend,
    M1Store,
    SchemaIntegrityError,
    _acquire_migration_owner_lease,
    _canonical_schema_sql_objects,
    _release_migration_owner_lease,
    _schema_sql_objects,
)
from pdu_exam_observer.m2_persistence import (
    _M2_DDL,
    _V2_CHECKSUM,
    ArtifactBytes,
    ArtifactIntent,
    M2PersistenceStore,
    PersistenceFailure,
)
from pdu_exam_observer.storage_owner import SQLiteStoreOwner


class AuthorityNotIssued(PermissionError):
    """A destructive or irreversible operation has no scoped authority."""


class TargetRegistrationError(ValueError):
    """A target is not a closed, server-derived manifest binding."""


class MigrationAuthority(Protocol):
    """Non-persisted capability bound to one root and readiness receipt."""

    def permits_migration(
        self, *, root_identity_digest: str, readiness_digest: str
    ) -> bool: ...


R1_DDL = """
CREATE TABLE reconciliation_targets(
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifact_registry(id),
    target_kind TEXT NOT NULL CHECK(target_kind IN (
        'LOCAL_RESEARCH_FILE',
        'LOCAL_EXPORT_STAGING_FILE',
        'EXTERNAL_COPY'
    )),
    root_scope TEXT NOT NULL CHECK(root_scope IN (
        'RESEARCH_ROOT',
        'EXPORT_STAGING',
        'EXTERNAL_ATTESTATION'
    )),
    locator_digest TEXT NOT NULL UNIQUE CHECK(length(locator_digest)=64),
    relative_path TEXT,
    export_id TEXT,
    expected_byte_size INTEGER,
    expected_sha256 TEXT,
    manifest_schema_version INTEGER NOT NULL CHECK(manifest_schema_version>=1),
    manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
    registration_version INTEGER NOT NULL CHECK(registration_version=1),
    created_at REAL NOT NULL,
    UNIQUE(id,target_kind,root_scope),
    UNIQUE(id,artifact_id,target_kind,root_scope),
    CHECK(
        (
            target_kind IN ('LOCAL_RESEARCH_FILE','LOCAL_EXPORT_STAGING_FILE')
            AND root_scope IN ('RESEARCH_ROOT','EXPORT_STAGING')
            AND relative_path IS NOT NULL
            AND export_id IS NULL
            AND expected_byte_size IS NOT NULL
            AND expected_byte_size >= 0
            AND expected_sha256 IS NOT NULL
            AND length(expected_sha256)=64
        )
        OR
        (
            target_kind='EXTERNAL_COPY'
            AND root_scope='EXTERNAL_ATTESTATION'
            AND relative_path IS NULL
            AND export_id IS NOT NULL
            AND expected_byte_size IS NULL
            AND expected_sha256 IS NULL
        )
    )
);

CREATE UNIQUE INDEX uq_sessions_participant_binding
    ON sessions(id,participant_id);
CREATE UNIQUE INDEX uq_artifacts_session_binding
    ON artifact_registry(id,session_id);
CREATE UNIQUE INDEX uq_withdrawal_receipt_participant_binding
    ON withdrawal_receipts(id,participant_id);
CREATE UNIQUE INDEX uq_withdrawal_task_subject_artifact_binding
    ON withdrawal_tasks(id,withdrawal_subject_session_id,artifact_id);

CREATE TABLE withdrawal_task_targets(
    withdrawal_task_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    withdrawal_receipt_id TEXT NOT NULL,
    withdrawal_subject_session_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    artifact_session_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    root_scope TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN (
        'PENDING_CONFIRMATION',
        'IN_PROGRESS',
        'LOCAL_DELETION_VERIFIED',
        'EXTERNAL_DELETION_ATTESTED',
        'RECOVERY_REQUIRED',
        'BLOCKED'
    )),
    state_version INTEGER NOT NULL DEFAULT 0 CHECK(state_version>=0),
    blocker_code TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY(withdrawal_task_id,target_id),
    UNIQUE(target_id),
    UNIQUE(withdrawal_task_id,target_id,target_kind,root_scope),
    UNIQUE(
        withdrawal_task_id,target_id,target_kind,root_scope,
        participant_id,withdrawal_receipt_id
    ),
    FOREIGN KEY(
        withdrawal_task_id,withdrawal_subject_session_id,artifact_id
    ) REFERENCES withdrawal_tasks(
        id,withdrawal_subject_session_id,artifact_id
    ),
    FOREIGN KEY(withdrawal_receipt_id,participant_id)
        REFERENCES withdrawal_receipts(id,participant_id),
    FOREIGN KEY(withdrawal_subject_session_id,participant_id)
        REFERENCES sessions(id,participant_id),
    FOREIGN KEY(artifact_id,artifact_session_id)
        REFERENCES artifact_registry(id,session_id),
    FOREIGN KEY(artifact_session_id,participant_id)
        REFERENCES sessions(id,participant_id),
    FOREIGN KEY(target_id,artifact_id,target_kind,root_scope)
        REFERENCES reconciliation_targets(
            id,artifact_id,target_kind,root_scope
        ),
    CHECK(
        (
            target_kind IN ('LOCAL_RESEARCH_FILE','LOCAL_EXPORT_STAGING_FILE')
            AND root_scope IN ('RESEARCH_ROOT','EXPORT_STAGING')
            AND state <> 'EXTERNAL_DELETION_ATTESTED'
        )
        OR
        (
            target_kind='EXTERNAL_COPY'
            AND root_scope='EXTERNAL_ATTESTATION'
            AND state <> 'LOCAL_DELETION_VERIFIED'
        )
    )
);

CREATE TABLE approved_procedure_authorities(
    id TEXT PRIMARY KEY,
    authority_reference TEXT NOT NULL UNIQUE CHECK(
        length(authority_reference) BETWEEN 1 AND 128
        AND authority_reference NOT GLOB '*[^A-Za-z0-9._-]*'
    ),
    procedure_kind TEXT NOT NULL CHECK(
        procedure_kind='EXTERNAL_DELETION'
    ),
    source_document_sha256 TEXT NOT NULL CHECK(
        length(source_document_sha256)=64
    ),
    status TEXT NOT NULL CHECK(status IN ('APPROVED','REVOKED')),
    approved_at REAL NOT NULL,
    expires_at REAL,
    revoked_at REAL,
    CHECK(expires_at IS NULL OR expires_at>approved_at),
    CHECK(
        (status='APPROVED' AND revoked_at IS NULL)
        OR (status='REVOKED' AND revoked_at IS NOT NULL)
    )
);

CREATE TABLE reconciliation_holds(
    id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(id),
    authority_reference TEXT NOT NULL CHECK(
        length(authority_reference) BETWEEN 1 AND 128
    ),
    status TEXT NOT NULL CHECK(status IN ('ACTIVE','RELEASED')),
    recorded_at REAL NOT NULL,
    released_at REAL,
    CHECK(
        (status='ACTIVE' AND released_at IS NULL)
        OR (status='RELEASED' AND released_at IS NOT NULL)
    )
);

CREATE TABLE reviewer_step_up_authentications(
    id TEXT PRIMARY KEY,
    reviewer_session_digest TEXT NOT NULL CHECK(length(reviewer_session_digest)=64),
    authentication_epoch INTEGER NOT NULL CHECK(authentication_epoch>=0),
    verified_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    consumed_at REAL,
    CHECK(expires_at>verified_at),
    CHECK(expires_at<=verified_at+120.0),
    CHECK(consumed_at IS NULL OR consumed_at<=expires_at),
    UNIQUE(id,reviewer_session_digest,verified_at,expires_at)
);

CREATE TABLE reconciliation_challenges(
    id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(id),
    withdrawal_receipt_id TEXT NOT NULL REFERENCES withdrawal_receipts(id),
    reviewer_session_digest TEXT NOT NULL CHECK(length(reviewer_session_digest)=64),
    token_digest TEXT NOT NULL UNIQUE CHECK(length(token_digest)=64),
    plan_sha256 TEXT NOT NULL CHECK(length(plan_sha256)=64),
    target_state_version INTEGER NOT NULL CHECK(target_state_version>=0),
    step_up_authentication_id TEXT NOT NULL UNIQUE,
    step_up_verified_at REAL NOT NULL,
    step_up_expires_at REAL NOT NULL,
    target_id TEXT,
    target_kind TEXT,
    root_scope TEXT,
    action TEXT NOT NULL CHECK(action IN (
        'EXECUTE_LOCAL_RECONCILIATION',
        'ATTEST_EXTERNAL_DELETION'
    )),
    status TEXT NOT NULL CHECK(status IN (
        'ISSUED','CONSUMED','EXPIRED','REVOKED'
    )),
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    consumed_at REAL,
    CHECK(expires_at>issued_at),
    CHECK(issued_at>=step_up_verified_at),
    CHECK(expires_at<=step_up_expires_at),
    CHECK(
        (
            action='EXECUTE_LOCAL_RECONCILIATION'
            AND target_id IS NULL
            AND target_kind IS NULL
            AND root_scope IS NULL
        )
        OR
        (
            action='ATTEST_EXTERNAL_DELETION'
            AND target_id IS NOT NULL
            AND target_kind='EXTERNAL_COPY'
            AND root_scope='EXTERNAL_ATTESTATION'
        )
    ),
    FOREIGN KEY(target_id,target_kind,root_scope)
        REFERENCES reconciliation_targets(id,target_kind,root_scope),
    FOREIGN KEY(
        step_up_authentication_id,reviewer_session_digest,
        step_up_verified_at,step_up_expires_at
    ) REFERENCES reviewer_step_up_authentications(
        id,reviewer_session_digest,verified_at,expires_at
    ),
    CHECK(
        (status IN ('ISSUED','EXPIRED','REVOKED') AND consumed_at IS NULL)
        OR (status='CONSUMED' AND consumed_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX idx_reconciliation_challenge_binding
    ON reconciliation_challenges(
        id,participant_id,withdrawal_receipt_id,plan_sha256,
        action,target_id,target_kind,root_scope
    );

CREATE TABLE reconciliation_executions(
    id TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES reconciliation_challenges(id),
    execution_kind TEXT NOT NULL CHECK(execution_kind IN (
        'LOCAL_RUN','EXTERNAL_ATTESTATION'
    )),
    created_at REAL NOT NULL,
    UNIQUE(id,challenge_id,execution_kind)
);

CREATE TABLE reconciliation_runs(
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    execution_kind TEXT NOT NULL DEFAULT 'LOCAL_RUN'
        CHECK(execution_kind='LOCAL_RUN'),
    participant_id TEXT NOT NULL REFERENCES participants(id),
    challenge_id TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL CHECK(length(plan_sha256)=64),
    state TEXT NOT NULL CHECK(state IN (
        'QUEUED','RUNNING','COMPLETED','BLOCKED',
        'RECOVERY_REQUIRED','FAILED_TECHNICAL'
    )),
    failure_code TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    terminal_at REAL,
    FOREIGN KEY(execution_id,challenge_id,execution_kind)
        REFERENCES reconciliation_executions(id,challenge_id,execution_kind)
);

CREATE TABLE reconciliation_attempts(
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES reconciliation_runs(id),
    withdrawal_task_id TEXT NOT NULL REFERENCES withdrawal_tasks(id),
    target_id TEXT NOT NULL REFERENCES reconciliation_targets(id),
    attempt_number INTEGER NOT NULL CHECK(attempt_number>=1),
    stage TEXT NOT NULL CHECK(stage IN (
        'PREDELETE_PENDING',
        'PREDELETE_VERIFIED',
        'DELETE_MARKED',
        'ABSENCE_VERIFIED',
        'RECOVERY_REQUIRED',
        'BLOCKED'
    )),
    observed_byte_size INTEGER,
    observed_sha256 TEXT,
    volume_identity_digest TEXT,
    file_identity_digest TEXT,
    failure_code TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(run_id,target_id),
    UNIQUE(withdrawal_task_id,target_id,attempt_number)
);

CREATE TABLE external_deletion_attestations(
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    execution_kind TEXT NOT NULL DEFAULT 'EXTERNAL_ATTESTATION'
        CHECK(execution_kind='EXTERNAL_ATTESTATION'),
    participant_id TEXT NOT NULL REFERENCES participants(id),
    withdrawal_receipt_id TEXT NOT NULL REFERENCES withdrawal_receipts(id),
    plan_sha256 TEXT NOT NULL CHECK(length(plan_sha256)=64),
    withdrawal_task_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_kind TEXT NOT NULL DEFAULT 'EXTERNAL_COPY'
        CHECK(target_kind='EXTERNAL_COPY'),
    root_scope TEXT NOT NULL DEFAULT 'EXTERNAL_ATTESTATION'
        CHECK(root_scope='EXTERNAL_ATTESTATION'),
    challenge_action TEXT NOT NULL DEFAULT 'ATTEST_EXTERNAL_DELETION'
        CHECK(challenge_action='ATTEST_EXTERNAL_DELETION'),
    challenge_id TEXT NOT NULL,
    procedure_authority_id TEXT NOT NULL
        REFERENCES approved_procedure_authorities(id),
    reviewer_session_digest TEXT NOT NULL CHECK(length(reviewer_session_digest)=64),
    attested_at REAL NOT NULL,
    UNIQUE(withdrawal_task_id,target_id),
    FOREIGN KEY(execution_id,challenge_id,execution_kind)
        REFERENCES reconciliation_executions(id,challenge_id,execution_kind),
    FOREIGN KEY(
        withdrawal_task_id,target_id,target_kind,root_scope,
        participant_id,withdrawal_receipt_id
    )
        REFERENCES withdrawal_task_targets(
            withdrawal_task_id,target_id,target_kind,root_scope,
            participant_id,withdrawal_receipt_id
        ),
    FOREIGN KEY(
        challenge_id,participant_id,withdrawal_receipt_id,plan_sha256,
        challenge_action,target_id,target_kind,root_scope
    ) REFERENCES reconciliation_challenges(
        id,participant_id,withdrawal_receipt_id,plan_sha256,
        action,target_id,target_kind,root_scope
    )
);

CREATE TABLE reconciliation_receipts(
    id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL UNIQUE REFERENCES participants(id),
    withdrawal_receipt_id TEXT NOT NULL UNIQUE REFERENCES withdrawal_receipts(id),
    body_json TEXT NOT NULL,
    body_sha256 TEXT NOT NULL CHECK(length(body_sha256)=64),
    created_at REAL NOT NULL
);

CREATE INDEX idx_reconciliation_targets_artifact
    ON reconciliation_targets(artifact_id);
CREATE INDEX idx_reconciliation_holds_participant
    ON reconciliation_holds(participant_id,status);
CREATE INDEX idx_withdrawal_task_targets_state
    ON withdrawal_task_targets(state);
CREATE INDEX idx_reconciliation_challenges_participant
    ON reconciliation_challenges(participant_id,status);
CREATE INDEX idx_reconciliation_runs_participant
    ON reconciliation_runs(participant_id,state);
CREATE INDEX idx_reconciliation_attempts_target
    ON reconciliation_attempts(target_id,attempt_number);
""".strip()


R1_CHECKSUM = hashlib.sha256(
    (_LEDGER_DDL + _V1_DDL + _M2_DDL + R1_DDL).encode("utf-8")
).hexdigest()

_PROPOSAL_SHA256 = "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5"


_ELIGIBILITY_TABLES = (
    "participants",
    "consent_records",
    "retention_records",
    "withdrawal_receipts",
    "withdrawal_tasks",
    "artifact_registry",
    "artifact_dependencies",
    "write_intents",
    "artifact_manifests",
    "m2_write_intents",
)


@dataclass(frozen=True)
class MigrationReadinessReceipt:
    receipt_schema_version: int
    operational_ledger_version: int
    source_ledger_versions: tuple[int, ...]
    source_schema_sha256: str
    target_ledger_versions: tuple[int, ...]
    target_schema_sha256: str
    eligibility_counts: tuple[tuple[str, int], ...]
    proposal_sha256: str
    source_binding_sha256: str
    root_identity_bound: bool
    precollection_empty: bool
    migration_authorized: bool
    real_data_present: bool
    research_ready: bool
    collection_authorized: bool
    root_identity_digest: str
    blocking_codes: tuple[str, ...]
    readiness_digest: str

    @property
    def eligible(self) -> bool:
        return self.precollection_empty

    @property
    def source_ledger_version(self) -> int:
        return self.source_ledger_versions[-1]

    @property
    def target_ledger_version(self) -> int:
        return self.operational_ledger_version

    def body(self) -> dict[str, object]:
        return {
            "collection_authorized": self.collection_authorized,
            "eligibility_counts": {key: value for key, value in self.eligibility_counts},
            "migration_authorized": self.migration_authorized,
            "operational_ledger_version": self.operational_ledger_version,
            "precollection_empty": self.precollection_empty,
            "proposal_sha256": self.proposal_sha256,
            "real_data_present": self.real_data_present,
            "receipt_schema_version": self.receipt_schema_version,
            "research_ready": self.research_ready,
            "root_identity_bound": self.root_identity_bound,
            "source_binding_sha256": self.source_binding_sha256,
            "source_ledger_versions": list(self.source_ledger_versions),
            "source_schema_sha256": self.source_schema_sha256,
            "target_ledger_versions": list(self.target_ledger_versions),
            "target_schema_sha256": self.target_schema_sha256,
        }


@dataclass(frozen=True)
class MigrationReceipt:
    readiness: MigrationReadinessReceipt
    readiness_body_sha256: str
    migration_committed: bool
    post_reopen_validated: bool
    foreign_keys_valid: bool
    integrity_valid: bool
    legacy_runtime_compatible: bool

    def body(self) -> dict[str, object]:
        body = self.readiness.body()
        body["migration_authorized"] = True
        body.update(
            {
                "foreign_keys_valid": self.foreign_keys_valid,
                "integrity_valid": self.integrity_valid,
                "legacy_runtime_compatible": self.legacy_runtime_compatible,
                "migration_committed": self.migration_committed,
                "post_reopen_validated": self.post_reopen_validated,
                "readiness_body_sha256": self.readiness_body_sha256,
            }
        )
        return body


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _root_identity_digest(root: Path) -> str:
    metadata = root.stat()
    body = {
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "normalized_root": str(root).replace("\\", "/").casefold(),
    }
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def _ledger_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT version,applied_at_utc,checksum FROM schema_migrations ORDER BY version"
    ).fetchall()


def _validate_source_schema(connection: sqlite3.Connection) -> tuple[int, str]:
    rows = _ledger_rows(connection)
    if len(rows) == 1:
        M2PersistenceStore._validate_v1_ledger(rows)
        expected = _canonical_schema_sql_objects()
        checksum = str(rows[0]["checksum"])
        version = 1
    elif len(rows) == 2:
        M2PersistenceStore._validate_v1_ledger(rows[:1])
        if int(rows[1]["version"]) != 2 or str(rows[1]["checksum"]) != _V2_CHECKSUM:
            raise SchemaIntegrityError("schema migration checksum is invalid or newer")
        trusted = sqlite3.connect(":memory:")
        try:
            trusted.executescript(_LEDGER_DDL + _V1_DDL + _M2_DDL)
            expected = _schema_sql_objects(trusted)
        finally:
            trusted.close()
        checksum = str(rows[1]["checksum"])
        version = 2
    else:
        raise SchemaIntegrityError("migration source must be exact v1 or v2")
    if _schema_sql_objects(connection) != expected:
        raise SchemaIntegrityError("schema object is missing or malformed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise SchemaIntegrityError("foreign key check failed")
    integrity = connection.execute("PRAGMA integrity_check").fetchall()
    if [str(row[0]) for row in integrity] != ["ok"]:
        raise SchemaIntegrityError("integrity check failed")
    return version, checksum


def _readiness_from_connection(
    root: Path, connection: sqlite3.Connection
) -> MigrationReadinessReceipt:
    source_version, source_checksum = _validate_source_schema(connection)
    available = {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    counts: list[tuple[str, int]] = []
    for table in _ELIGIBILITY_TABLES:
        if table in available:
            count = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            counts.append((table, count))
    research_sessions = int(
        connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_kind='RESEARCH'"
        ).fetchone()[0]
    )
    counts.append(("research_sessions", research_sessions))
    counts_tuple = tuple(sorted(counts))
    eligible = all(value == 0 for _, value in counts_tuple)
    blockers = () if eligible else ("MIGRATION_REQUIRES_EMPTY_PRECOLLECTION_ROOT",)
    root_digest = _root_identity_digest(root)
    source_versions = tuple(range(1, source_version + 1))
    source_binding_body = {
        "eligibility_counts": {key: value for key, value in counts_tuple},
        "root_identity_digest": root_digest,
        "source_ledger_versions": list(source_versions),
        "source_schema_sha256": source_checksum,
    }
    source_binding_sha256 = hashlib.sha256(
        _canonical_json(source_binding_body).encode("utf-8")
    ).hexdigest()
    body = {
        "collection_authorized": False,
        "eligibility_counts": {key: value for key, value in counts_tuple},
        "migration_authorized": False,
        "operational_ledger_version": 3,
        "precollection_empty": eligible,
        "proposal_sha256": _PROPOSAL_SHA256,
        "real_data_present": not eligible,
        "receipt_schema_version": 1,
        "research_ready": False,
        "root_identity_bound": True,
        "source_binding_sha256": source_binding_sha256,
        "source_ledger_versions": list(source_versions),
        "source_schema_sha256": source_checksum,
        "target_ledger_versions": [1, 2, 3],
        "target_schema_sha256": R1_CHECKSUM,
    }
    digest = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    return MigrationReadinessReceipt(
        receipt_schema_version=1,
        operational_ledger_version=3,
        source_ledger_versions=source_versions,
        source_schema_sha256=source_checksum,
        target_ledger_versions=(1, 2, 3),
        target_schema_sha256=R1_CHECKSUM,
        eligibility_counts=counts_tuple,
        proposal_sha256=_PROPOSAL_SHA256,
        source_binding_sha256=source_binding_sha256,
        root_identity_bound=True,
        precollection_empty=eligible,
        migration_authorized=False,
        real_data_present=not eligible,
        research_ready=False,
        collection_authorized=False,
        root_identity_digest=root_digest,
        blocking_codes=blockers,
        readiness_digest=digest,
    )


def _existing_database(root: Path) -> tuple[Path, Path]:
    try:
        validated_root = validate_storage_root(root, create=False, require_writable=False)
    except ConfigurationError as exc:
        raise SchemaIntegrityError("existing v1 or v2 storage root is required") from exc
    operational = M1Store._validated_child(
        validated_root,
        validated_root / "operational",
        "operational directory",
        directory=True,
    )
    database = M1Store._validated_child(
        operational,
        operational / "pdu-exam-observer.sqlite3",
        "operational database",
        directory=False,
    )
    return validated_root, database


@contextmanager
def _migration_readiness_guard(root: Path, database: Path) -> Iterator[None]:
    """Retain no-follow identities and any existing P1 owner lease without writes."""

    handles: list[int] = []
    lease_owner = object.__new__(M2PersistenceStore)
    lease_owner._lease = ("unacquired", -1)
    migration_lease: tuple[str, int] = ("unacquired", -1)
    try:
        if os.name == "nt":
            handle_owner = object.__new__(M2PersistenceStore)
            handle_owner.root = root
            handle_owner._before_handle_open = None
            handles.extend(
                (
                    handle_owner._windows_open_checked(root, directory=True, share=3),
                    handle_owner._windows_open_checked(
                        database.parent, directory=True, share=3
                    ),
                    handle_owner._windows_open_checked(
                        database, directory=False, share=3
                    ),
                )
            )
        migration_lease = _acquire_migration_owner_lease(
            database.parent, create=False
        )
        lease_path = database.parent / "p1-store.lock"
        if os.path.lexists(lease_path):
            lease_owner._lease = M2PersistenceStore._acquire_root_lease(database.parent)
        yield
    finally:
        lease_owner._release_root_lease()
        _release_migration_owner_lease(migration_lease)
        if os.name == "nt":
            for handle in reversed(handles):
                ctypes.windll.kernel32.CloseHandle(handle)


def check_migration_readiness(root: Path) -> MigrationReadinessReceipt:
    """Inspect exact v1/v2 through a SQLite read-only connection."""

    validated_root, database = _existing_database(root)
    sidecars = tuple(database.with_name(database.name + suffix) for suffix in ("-wal", "-shm"))
    with _migration_readiness_guard(validated_root, database):
        if any(os.path.lexists(sidecar) for sidecar in sidecars):
            raise SchemaIntegrityError("MIGRATION_ROOT_NOT_QUIESCENT")
        connection = sqlite3.connect(
            database.as_uri() + "?mode=ro&immutable=1", uri=True, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only=ON")
            readiness = _readiness_from_connection(validated_root, connection)
            if any(os.path.lexists(sidecar) for sidecar in sidecars):
                raise SchemaIntegrityError("MIGRATION_ROOT_NOT_QUIESCENT")
            return readiness
        finally:
            connection.close()


class ResearchStoreV3(M2PersistenceStore):
    """The sole guarded v3 owner; migration is explicit and authority-bound."""

    schema_version = 3

    def __init__(
        self,
        root: Path,
        *,
        expected_readiness_digest: str | None = None,
        authority: MigrationAuthority | None = None,
        migration_fault: object | None = None,
    ) -> None:
        self.migration_receipt: MigrationReceipt | None = None
        self._r1_expected_readiness_digest = expected_readiness_digest
        self._r1_authority = authority
        self._r1_migration_sidecar_observed = False
        migration_lease: tuple[str, int] = ("unacquired", -1)
        try:
            if expected_readiness_digest is not None or authority is not None:
                _validated_root, database = _existing_database(root)
                migration_lease = _acquire_migration_owner_lease(
                    database.parent, create=False
                )
                sidecars = tuple(
                    database.with_name(database.name + suffix)
                    for suffix in ("-wal", "-shm")
                )
                if any(os.path.lexists(sidecar) for sidecar in sidecars):
                    raise SchemaIntegrityError("MIGRATION_ROOT_NOT_QUIESCENT")
            fault = migration_fault if callable(migration_fault) else None
            super().__init__(root, migration_fault=fault)
        finally:
            _release_migration_owner_lease(migration_lease)

    def _on_existing_sqlite_sidecar(self, sidecar: Path) -> None:
        if self._r1_expected_readiness_digest is not None or self._r1_authority is not None:
            self._r1_migration_sidecar_observed = True
            raise PersistenceFailure("MIGRATION_ROOT_NOT_QUIESCENT")
        super()._on_existing_sqlite_sidecar(sidecar)

    def _migrate_and_validate(self) -> None:
        rows = self._ledger_rows(self.connection)
        if len(rows) == 3:
            self._validate_v3()
            return
        if self._r1_authority is None or self._r1_expected_readiness_digest is None:
            raise AuthorityNotIssued("AUTHORITY_NOT_ISSUED")
        readiness = _readiness_from_connection(self.root, self.connection)
        if readiness.readiness_digest != self._r1_expected_readiness_digest:
            raise SchemaIntegrityError("MIGRATION_READINESS_DIGEST_CHANGED")
        if not readiness.eligible:
            raise ValueError("MIGRATION_REQUIRES_EMPTY_PRECOLLECTION_ROOT")
        if not self._r1_authority.permits_migration(
            root_identity_digest=readiness.root_identity_digest,
            readiness_digest=readiness.readiness_digest,
        ):
            raise AuthorityNotIssued("AUTHORITY_NOT_ISSUED")
        try:
            with self._transaction() as connection:
                if readiness.source_ledger_version == 1:
                    for statement in _M2_DDL.split(";"):
                        if statement.strip():
                            connection.execute(statement)
                    connection.execute(
                        "INSERT INTO schema_migrations"
                        "(version,applied_at_utc,checksum) VALUES(?,?,?)",
                        (2, datetime.now(UTC).isoformat(), _V2_CHECKSUM),
                    )
                for statement in R1_DDL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                if self._migration_fault is not None:
                    self._migration_fault()
                connection.execute(
                    "INSERT INTO schema_migrations(version,applied_at_utc,checksum) VALUES(?,?,?)",
                    (3, datetime.now(UTC).isoformat(), R1_CHECKSUM),
                )
        except (AuthorityNotIssued, SchemaIntegrityError, ValueError):
            raise
        except Exception as exc:
            raise PersistenceFailure("v1-or-v2-to-v3 migration rolled back") from exc
        self._validate_v3()

    def _validate_v3(self) -> None:
        rows = self._ledger_rows(self.connection)
        if len(rows) != 3:
            raise SchemaIntegrityError("schema migration ledger is malformed or newer")
        self._validate_v1_ledger(rows[:1])
        if int(rows[1]["version"]) != 2 or str(rows[1]["checksum"]) != _V2_CHECKSUM:
            raise SchemaIntegrityError("schema migration checksum is invalid or newer")
        if int(rows[2]["version"]) != 3 or str(rows[2]["checksum"]) != R1_CHECKSUM:
            raise SchemaIntegrityError("schema migration checksum is invalid or newer")
        if self._integrity_check_rows() != ("ok",):
            raise SchemaIntegrityError("SQLite integrity check failed")
        trusted = sqlite3.connect(":memory:")
        try:
            trusted.executescript(_LEDGER_DDL + _V1_DDL + _M2_DDL + R1_DDL)
            expected = _schema_sql_objects(trusted)
        finally:
            trusted.close()
        if _schema_sql_objects(self.connection) != expected:
            raise SchemaIntegrityError("schema object is missing or malformed")
        if self.connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise SchemaIntegrityError("foreign key check failed")

    def _integrity_check_rows(self) -> tuple[str, ...]:
        return tuple(str(row[0]) for row in self.connection.execute("PRAGMA integrity_check"))

    def recover(self) -> dict[str, int]:
        """Recover M2 intents, then mark interrupted reconciliation without deleting."""

        result = super().recover()
        available = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reconciliation_runs'"
        ).fetchone()
        if available is None:
            return result
        with self.transaction() as connection:
            interrupted = int(
                connection.execute(
                    "SELECT COUNT(*) FROM reconciliation_runs "
                    "WHERE state IN ('QUEUED','RUNNING')"
                ).fetchone()[0]
            )
            connection.execute(
                "UPDATE reconciliation_runs SET state='RECOVERY_REQUIRED',"
                "failure_code='PROCESS_INTERRUPTED',terminal_at=? "
                "WHERE state IN ('QUEUED','RUNNING')",
                (self.clock(),),
            )
            connection.execute(
                "UPDATE withdrawal_task_targets SET state='RECOVERY_REQUIRED',"
                "state_version=state_version+1,blocker_code='PROCESS_INTERRUPTED',updated_at=? "
                "WHERE state='IN_PROGRESS'",
                (self.clock(),),
            )
            connection.execute(
                "UPDATE reconciliation_attempts SET stage='RECOVERY_REQUIRED',"
                "failure_code='PROCESS_INTERRUPTED',updated_at=? "
                "WHERE stage IN ('PREDELETE_PENDING','PREDELETE_VERIFIED','DELETE_MARKED')",
                (self.clock(),),
            )
        return result | {"reconciliation_runs_recovery_required": interrupted}

    @staticmethod
    def _normalized_relative_path(value: str) -> str:
        path = value.replace("\\", "/")
        if path != unicodedata.normalize("NFC", path):
            raise TargetRegistrationError("relative path is not NFC")
        if not path or path.startswith("/") or "\\" in path or ":" in path:
            raise TargetRegistrationError("invalid server-derived relative path")
        parts = PurePosixPath(path).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise TargetRegistrationError("invalid server-derived relative path")
        reserved = {
            "aux",
            "clock$",
            "com1",
            "com2",
            "com3",
            "com4",
            "com5",
            "com6",
            "com7",
            "com8",
            "com9",
            "con",
            "lpt1",
            "lpt2",
            "lpt3",
            "lpt4",
            "lpt5",
            "lpt6",
            "lpt7",
            "lpt8",
            "lpt9",
            "nul",
            "prn",
        }
        for part in parts:
            if part.endswith((" ", ".")) or part.split(".", 1)[0].casefold() in reserved:
                raise TargetRegistrationError("invalid server-derived relative path")
        return "/".join(parts)

    @staticmethod
    def _opaque_external_id(value: str) -> str:
        if not 1 <= len(value) <= 128 or not all(
            character.isascii() and (character.isalnum() or character in "._-")
            for character in value
        ):
            raise TargetRegistrationError("invalid export id")
        return value

    @staticmethod
    def _manifest_body(row: sqlite3.Row) -> dict[str, object]:
        return {
            "artifact_id": str(row["artifact_id"]),
            "artifact_kind": str(row["artifact_kind"]),
            "byte_size": int(row["byte_size"]),
            "capture_profile_version": str(row["capture_profile_version"]),
            "manifest_schema_version": int(row["manifest_schema_version"]),
            "monotonic_timing_origin": str(row["monotonic_timing_origin"]),
            "processing_version": str(row["processing_version"]),
            "relative_path": ResearchStoreV3._normalized_relative_path(
                str(row["relative_path"])
            ),
            "sha256": str(row["sha256"]),
            "technical_failure_code": row["technical_failure_code"],
            "technical_input_kind": str(row["technical_input_kind"]),
        }

    @classmethod
    def _manifest_binding_from_row(cls, row: sqlite3.Row) -> str:
        return hashlib.sha256(
            _canonical_json(cls._manifest_body(row)).encode("utf-8")
        ).hexdigest()

    def manifest_binding_sha256(self, artifact_id: str) -> str:
        self._opaque(artifact_id, "artifact id")
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM artifact_manifests WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return self._manifest_binding_from_row(row)

    @staticmethod
    def _target_identity(locator: Mapping[str, object]) -> tuple[str, str]:
        locator_digest = hashlib.sha256(
            _canonical_json(locator).encode("utf-8")
        ).hexdigest()
        target_id = "target-" + hashlib.sha256(
            (str(locator["artifact_id"]) + ":" + locator_digest).encode("utf-8")
        ).hexdigest()[:24]
        return target_id, locator_digest

    def persist(self, intent: ArtifactIntent, source: ArtifactBytes) -> dict[str, object]:
        """Reject Windows-equivalent target names before any final-file replacement."""

        self._validate_intent(intent)
        with self._root_lock:
            _partial, _final, _partial_relative, final_relative = self._paths(
                intent.artifact_id
            )
            normalized = self._normalized_relative_path(final_relative)
            with self._lock:
                rows = self.connection.execute(
                    "SELECT artifact_id,relative_path FROM reconciliation_targets "
                    "WHERE relative_path IS NOT NULL"
                ).fetchall()
            for row in rows:
                if (
                    str(row["relative_path"]).casefold() == normalized.casefold()
                    and str(row["artifact_id"]) != intent.artifact_id
                ):
                    raise TargetRegistrationError("local target case-fold collision")
            return super().persist(intent, source)

    def _after_manifest_insert(
        self,
        connection: sqlite3.Connection,
        *,
        intent: ArtifactIntent,
        relative_path: str,
        byte_size: int,
        sha256: str,
    ) -> None:
        row = connection.execute(
            "SELECT * FROM artifact_manifests WHERE artifact_id=?",
            (intent.artifact_id,),
        ).fetchone()
        if row is None:
            raise SchemaIntegrityError("sealed artifact manifest is missing")
        normalized = self._normalized_relative_path(relative_path)
        manifest_sha256 = self._manifest_binding_from_row(row)
        locator = {
            "artifact_id": intent.artifact_id,
            "relative_path": normalized,
            "root_scope": "RESEARCH_ROOT",
            "target_kind": "LOCAL_RESEARCH_FILE",
        }
        target_id, locator_digest = self._target_identity(locator)
        connection.execute(
            "INSERT INTO reconciliation_targets("
            "id,artifact_id,target_kind,root_scope,locator_digest,relative_path,export_id,"
            "expected_byte_size,expected_sha256,manifest_schema_version,manifest_sha256,"
            "registration_version,created_at) VALUES(?,?,?,?,?,?,NULL,?,?,?,?,1,?)",
            (
                target_id,
                intent.artifact_id,
                "LOCAL_RESEARCH_FILE",
                "RESEARCH_ROOT",
                locator_digest,
                normalized,
                byte_size,
                sha256,
                int(row["manifest_schema_version"]),
                manifest_sha256,
                self.clock(),
            ),
        )

    def register_external_target(
        self,
        artifact_id: str,
        *,
        export_id: str,
        manifest_sha256: str,
    ) -> str:
        self._opaque(artifact_id, "artifact id")
        export_id = self._opaque_external_id(export_id)
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT m.*,a.status FROM artifact_manifests m "
                "JOIN artifact_registry a ON a.id=m.artifact_id WHERE m.artifact_id=?",
                (artifact_id,),
            ).fetchone()
            if row is None or str(row["status"]) != "VALID":
                raise TargetRegistrationError("artifact manifest is not valid")
            actual_manifest_sha256 = self._manifest_binding_from_row(row)
            if manifest_sha256 != actual_manifest_sha256:
                raise TargetRegistrationError("manifest binding does not match")
            locator = {
                "artifact_id": artifact_id,
                "export_id": export_id,
                "root_scope": "EXTERNAL_ATTESTATION",
                "target_kind": "EXTERNAL_COPY",
            }
            target_id, locator_digest = self._target_identity(locator)
            connection.execute(
                "INSERT OR IGNORE INTO reconciliation_targets("
                "id,artifact_id,target_kind,root_scope,locator_digest,relative_path,export_id,"
                "expected_byte_size,expected_sha256,manifest_schema_version,manifest_sha256,"
                "registration_version,created_at) VALUES(?,?,?,?,?,NULL,?,NULL,NULL,?,?,1,?)",
                (
                    target_id,
                    artifact_id,
                    "EXTERNAL_COPY",
                    "EXTERNAL_ATTESTATION",
                    locator_digest,
                    export_id,
                    int(row["manifest_schema_version"]),
                    actual_manifest_sha256,
                    self.clock(),
                ),
            )
            persisted = connection.execute(
                "SELECT artifact_id,target_kind,root_scope,locator_digest,export_id,"
                "manifest_sha256 FROM reconciliation_targets WHERE id=?",
                (target_id,),
            ).fetchone()
            expected = (
                artifact_id,
                "EXTERNAL_COPY",
                "EXTERNAL_ATTESTATION",
                locator_digest,
                export_id,
                actual_manifest_sha256,
            )
            if persisted is None or tuple(persisted) != expected:
                raise TargetRegistrationError("external target idempotency conflict")
            return target_id


class M1R1Backend(M1Backend):
    """M1 governance composed with the sole v3 guarded store."""

    def __init__(
        self,
        root: Path,
        *,
        encryption_status: str,
        acl_status: str,
        store: ResearchStoreV3 | None = None,
    ) -> None:
        owner = ResearchStoreV3(root) if store is None else store
        if owner.schema_version != 3:
            raise SchemaIntegrityError("m1r1 requires operational ledger v3")
        super().__init__(
            root,
            encryption_status=encryption_status,
            acl_status=acl_status,
            store=cast("SQLiteStoreOwner", owner),
        )

    def register_artifact(
        self, artifact_id: str, session_id: str, parents: tuple[str, ...] = ()
    ) -> None:
        del artifact_id, session_id, parents
        raise InvalidTransition("TARGET_REGISTRATION_REQUIRED")

    def _after_withdrawal_receipt(
        self,
        connection: sqlite3.Connection,
        *,
        participant_id: str,
        withdrawal_receipt_id: str,
    ) -> None:
        rows = connection.execute(
            "SELECT wt.id withdrawal_task_id,wt.withdrawal_subject_session_id,"
            "wt.artifact_id,a.session_id artifact_session_id,t.id target_id,"
            "t.target_kind,t.root_scope FROM withdrawal_tasks wt "
            "JOIN sessions subject ON subject.id=wt.withdrawal_subject_session_id "
            "JOIN artifact_registry a ON a.id=wt.artifact_id "
            "JOIN reconciliation_targets t ON t.artifact_id=wt.artifact_id "
            "WHERE subject.participant_id=?",
            (participant_id,),
        ).fetchall()
        for row in rows:
            connection.execute(
                "INSERT OR IGNORE INTO withdrawal_task_targets("
                "withdrawal_task_id,participant_id,withdrawal_receipt_id,"
                "withdrawal_subject_session_id,artifact_id,artifact_session_id,target_id,"
                "target_kind,root_scope,state,state_version,blocker_code,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,'PENDING_CONFIRMATION',0,NULL,?)",
                (
                    row["withdrawal_task_id"],
                    participant_id,
                    withdrawal_receipt_id,
                    row["withdrawal_subject_session_id"],
                    row["artifact_id"],
                    row["artifact_session_id"],
                    row["target_id"],
                    row["target_kind"],
                    row["root_scope"],
                    self.clock(),
                ),
            )


def migrate_to_v3(
    root: Path,
    *,
    expected_readiness_digest: str,
    authority: MigrationAuthority | None,
) -> ResearchStoreV3:
    """Apply one exact migration only when a bound in-memory authority permits it."""

    if authority is None:
        raise AuthorityNotIssued("AUTHORITY_NOT_ISSUED")
    readiness = check_migration_readiness(root)
    if readiness.readiness_digest != expected_readiness_digest:
        raise SchemaIntegrityError("MIGRATION_READINESS_DIGEST_CHANGED")
    if not readiness.eligible:
        raise ValueError("MIGRATION_REQUIRES_EMPTY_PRECOLLECTION_ROOT")
    if not authority.permits_migration(
        root_identity_digest=readiness.root_identity_digest,
        readiness_digest=readiness.readiness_digest,
    ):
        raise AuthorityNotIssued("AUTHORITY_NOT_ISSUED")
    migrated = ResearchStoreV3(
        root,
        expected_readiness_digest=expected_readiness_digest,
        authority=authority,
    )
    migrated.close()
    reopened = ResearchStoreV3(root)
    foreign_keys_valid = reopened.connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchone() is None
    integrity_rows = reopened.connection.execute("PRAGMA integrity_check").fetchall()
    integrity_valid = [str(row[0]) for row in integrity_rows] == ["ok"]
    if not foreign_keys_valid or not integrity_valid:
        reopened.close()
        raise SchemaIntegrityError("post-reopen v3 validation failed")
    reopened.migration_receipt = MigrationReceipt(
        readiness=readiness,
        readiness_body_sha256=readiness.readiness_digest,
        migration_committed=True,
        post_reopen_validated=True,
        foreign_keys_valid=True,
        integrity_valid=True,
        legacy_runtime_compatible=False,
    )
    return reopened
