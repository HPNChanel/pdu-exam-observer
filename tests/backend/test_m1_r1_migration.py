from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

import pdu_exam_observer.m1_r1 as m1_r1_module
from pdu_exam_observer.m1 import M1Backend, M1Store, SchemaIntegrityError
from pdu_exam_observer.m1_r1 import (
    R1_CHECKSUM,
    R1_DDL,
    AuthorityNotIssued,
    MigrationAuthority,
    ResearchStoreV3,
    check_migration_readiness,
    migrate_to_v3,
)
from pdu_exam_observer.m2_persistence import (
    _M2_DDL,
    _V2_CHECKSUM,
    M2PersistenceStore,
    PersistenceFailure,
)


def _v1_root(root: Path) -> None:
    store = M1Store(root)
    store.close()


def _database(root: Path) -> Path:
    return root / "operational" / "pdu-exam-observer.sqlite3"


def _ledger(root: Path) -> list[tuple[int, str]]:
    connection = sqlite3.connect(_database(root))
    try:
        return [
            (int(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT version,checksum FROM schema_migrations ORDER BY version"
            )
        ]
    finally:
        connection.close()


@dataclass(frozen=True)
class _BoundTestAuthority:
    root_identity_digest: str
    readiness_digest: str

    def permits_migration(self, *, root_identity_digest: str, readiness_digest: str) -> bool:
        return (
            root_identity_digest == self.root_identity_digest
            and readiness_digest == self.readiness_digest
        )


def test_r1_ddl_is_exactly_the_reviewed_migration_design_and_drift_changes_checksum() -> None:
    design = Path(
        "docs/superpowers/specs/2026-08-30-m1-r1-production-withdrawal-reconciler-migration-design.md"
    ).read_text(encoding="utf-8")
    reviewed = design.split("```sql\n", 1)[1].split("\n```", 1)[0].strip()

    assert R1_DDL.strip() == reviewed
    assert len(R1_CHECKSUM) == 64
    drifted = R1_DDL.replace("reconciliation_targets", "reconciliation_targetz", 1)
    assert hashlib.sha256(drifted.encode("utf-8")).hexdigest() != hashlib.sha256(
        R1_DDL.encode("utf-8")
    ).hexdigest()


def test_readiness_check_is_canonical_and_does_not_mutate_v1_database(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    database = _database(root)
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    before_children = sorted(path.name for path in database.parent.iterdir())

    first = check_migration_readiness(root)
    second = check_migration_readiness(root)

    assert first == second
    assert first.eligible is True
    assert first.source_ledger_version == 1
    assert first.target_ledger_version == 3
    assert first.blocking_codes == ()
    assert set(first.body()) == {
        "receipt_schema_version",
        "operational_ledger_version",
        "source_ledger_versions",
        "source_schema_sha256",
        "target_ledger_versions",
        "target_schema_sha256",
        "eligibility_counts",
        "proposal_sha256",
        "source_binding_sha256",
        "root_identity_bound",
        "precollection_empty",
        "migration_authorized",
        "real_data_present",
        "research_ready",
        "collection_authorized",
    }
    assert first.body()["proposal_sha256"] == (
        "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5"
    )
    assert first.body()["migration_authorized"] is False
    assert first.body()["research_ready"] is False
    assert first.body()["collection_authorized"] is False
    assert len(first.root_identity_digest) == 64
    assert len(first.readiness_digest) == 64
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_hash
    assert sorted(path.name for path in database.parent.iterdir()) == before_children
    assert _ledger(root) == [(1, _ledger(root)[0][1])]


def test_readiness_check_never_uses_the_storage_write_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    original_write_text = Path.write_text

    def reject_probe(path: Path, *args: object, **kwargs: object) -> int:
        if path.name == ".pdu-write-probe":
            raise AssertionError("readiness check attempted a storage write probe")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", reject_probe)
    assert check_migration_readiness(root).eligible is True


def test_normal_migration_apply_is_denied_before_mutation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    before = _ledger(root)

    with pytest.raises(AuthorityNotIssued, match="AUTHORITY_NOT_ISSUED"):
        migrate_to_v3(
            root,
            expected_readiness_digest=readiness.readiness_digest,
            authority=None,
        )

    assert _ledger(root) == before


def test_apply_rejects_a_legacy_owner_opened_after_readiness(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )
    active_legacy = M1Store(root)
    try:
        with pytest.raises(
            (SchemaIntegrityError, PersistenceFailure),
            match="MIGRATION_ROOT_NOT_QUIESCENT|STORE_OWNER_UNAVAILABLE|unsafe",
        ):
            migrate_to_v3(
                root,
                expected_readiness_digest=readiness.readiness_digest,
                authority=authority,
            )
        assert _ledger(root) == [(1, _ledger(root)[0][1])]
    finally:
        active_legacy.close()


def test_apply_revalidates_quiescence_after_internal_readiness_before_owner_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )
    original_check = m1_r1_module.check_migration_readiness
    active: list[M1Store] = []

    def race(candidate: Path):
        receipt = original_check(candidate)
        active.append(M1Store(candidate))
        return receipt

    monkeypatch.setattr(m1_r1_module, "check_migration_readiness", race)
    try:
        with pytest.raises(
            (SchemaIntegrityError, PersistenceFailure),
            match="MIGRATION_ROOT_NOT_QUIESCENT|STORE_OWNER_UNAVAILABLE|unsafe",
        ):
            migrate_to_v3(
                root,
                expected_readiness_digest=readiness.readiness_digest,
                authority=authority,
            )
        assert _ledger(root) == [(1, _ledger(root)[0][1])]
    finally:
        for store in active:
            store.close()


def test_apply_excludes_legacy_owner_started_after_sidecar_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )
    original_reserve = M2PersistenceStore._reserve_sqlite_sidecars
    active: list[M1Store] = []

    def open_legacy_after_reservation(owner: M2PersistenceStore) -> None:
        original_reserve(owner)
        active.append(M1Store(owner.root))

    monkeypatch.setattr(
        M2PersistenceStore, "_reserve_sqlite_sidecars", open_legacy_after_reservation
    )
    try:
        with pytest.raises(
            (SchemaIntegrityError, PersistenceFailure),
            match="MIGRATION_ROOT_NOT_QUIESCENT|STORE_OWNER_UNAVAILABLE|owner|lease",
        ):
            migrate_to_v3(
                root,
                expected_readiness_digest=readiness.readiness_digest,
                authority=authority,
            )
        assert _ledger(root) == [(1, _ledger(root)[0][1])]
    finally:
        for store in active:
            store.close()


def test_readiness_rejects_an_active_or_uncheckpointed_sqlite_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    active = M1Store(root)
    try:
        with pytest.raises(SchemaIntegrityError, match="MIGRATION_ROOT_NOT_QUIESCENT"):
            check_migration_readiness(root)
    finally:
        active.close()


def test_v3_migration_fault_rolls_back_v2_v3_and_ledger_together(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )

    def fail() -> None:
        raise RuntimeError("injected migration failure")

    with pytest.raises(PersistenceFailure, match="migration rolled back"):
        ResearchStoreV3(
            root,
            expected_readiness_digest=readiness.readiness_digest,
            authority=authority,
            migration_fault=fail,
        )

    assert len(_ledger(root)) == 1
    connection = sqlite3.connect(_database(root))
    try:
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reconciliation_targets'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artifact_manifests'"
        ).fetchone() is None
    finally:
        connection.close()


def test_bound_synthetic_authority_migrates_v1_to_exact_v3_and_reopens(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )

    store = migrate_to_v3(
        root,
        expected_readiness_digest=readiness.readiness_digest,
        authority=authority,
    )
    try:
        assert isinstance(store, ResearchStoreV3)
        assert store.schema_version == 3
        assert store.ledger_versions() == (1, 2, 3)
        assert store.connection.execute("PRAGMA foreign_key_check").fetchone() is None
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_targets"
        ).fetchone()[0] == 0
        assert store.migration_receipt is not None
        assert store.migration_receipt.body()["readiness_body_sha256"] == (
            readiness.readiness_digest
        )
        assert store.migration_receipt.body()["migration_committed"] is True
        assert store.migration_receipt.body()["post_reopen_validated"] is True
        assert store.migration_receipt.body()["legacy_runtime_compatible"] is False
        assert store.migration_receipt.body()["research_ready"] is False
        assert store.migration_receipt.body()["collection_authorized"] is False
    finally:
        store.close()

    assert _ledger(root)[1] == (2, _V2_CHECKSUM)
    assert _ledger(root)[2] == (3, R1_CHECKSUM)
    reopened = ResearchStoreV3(root)
    try:
        assert reopened.ledger_versions() == (1, 2, 3)
    finally:
        reopened.close()

    with pytest.raises(SchemaIntegrityError, match="newer than this runtime"):
        M1Store(root)


def test_v3_reopen_fails_closed_when_sqlite_integrity_check_is_not_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )
    migrated = migrate_to_v3(
        root,
        expected_readiness_digest=readiness.readiness_digest,
        authority=authority,
    )
    migrated.close()

    monkeypatch.setattr(
        ResearchStoreV3,
        "_integrity_check_rows",
        lambda _self: ("database disk image is malformed",),
        raising=False,
    )
    with pytest.raises(SchemaIntegrityError, match="integrity check failed"):
        ResearchStoreV3(root)


def test_bound_synthetic_authority_migrates_exact_empty_v2_to_v3(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    v2 = M2PersistenceStore(root)
    v2.close()
    readiness = check_migration_readiness(root)
    assert readiness.source_ledger_versions == (1, 2)
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )

    store = migrate_to_v3(
        root,
        expected_readiness_digest=readiness.readiness_digest,
        authority=authority,
    )
    try:
        assert store.ledger_versions() == (1, 2, 3)
        assert store.migration_receipt is not None
    finally:
        store.close()


def test_changed_digest_or_wrong_root_authority_cannot_apply(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _v1_root(root)
    readiness = check_migration_readiness(root)
    wrong = _BoundTestAuthority("0" * 64, readiness.readiness_digest)

    with pytest.raises(SchemaIntegrityError, match="MIGRATION_READINESS_DIGEST_CHANGED"):
        migrate_to_v3(
            root,
            expected_readiness_digest="0" * 64,
            authority=wrong,
        )
    with pytest.raises(AuthorityNotIssued, match="AUTHORITY_NOT_ISSUED"):
        migrate_to_v3(
            root,
            expected_readiness_digest=readiness.readiness_digest,
            authority=wrong,
        )
    assert len(_ledger(root)) == 1


def test_nonempty_research_root_is_ineligible_even_with_bound_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    study = backend.create_study("study", idempotency_key="study")
    backend.create_participant(str(study["study_id"]), idempotency_key="participant")
    backend.store.close()

    readiness = check_migration_readiness(root)
    assert readiness.eligible is False
    assert "MIGRATION_REQUIRES_EMPTY_PRECOLLECTION_ROOT" in readiness.blocking_codes
    authority: MigrationAuthority = _BoundTestAuthority(
        readiness.root_identity_digest, readiness.readiness_digest
    )

    with pytest.raises(ValueError, match="MIGRATION_REQUIRES_EMPTY_PRECOLLECTION_ROOT"):
        migrate_to_v3(
            root,
            expected_readiness_digest=readiness.readiness_digest,
            authority=authority,
        )

    assert len(_ledger(root)) == 1


def test_r1_ddl_applies_after_exact_v1_and_v2_in_memory() -> None:
    from pdu_exam_observer.m1 import _DDL, _LEDGER_DDL

    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(_LEDGER_DDL + _DDL + _M2_DDL + R1_DDL)
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
    finally:
        connection.close()
