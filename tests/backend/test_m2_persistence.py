# ruff: noqa: E501

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import pdu_exam_observer.m2_persistence as m2_persistence
from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m1 import M1Backend, M1Store, SchemaIntegrityError
from pdu_exam_observer.m2_persistence import (
    ArtifactIntent,
    M2PersistenceStore,
    PersistenceFailure,
    PlatformUnsupported,
    StaticArtifactSource,
)


def _research(root: Path, code: str = "m2") -> tuple[M1Backend, str]:
    backend = M1Backend(root, encryption_status="VERIFIED", acl_status="VERIFIED")
    study = backend.create_study(code, idempotency_key=f"study-{code}")
    participant = backend.create_participant(str(study["study_id"]), idempotency_key=f"person-{code}")
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key=f"session-{code}",
        retention_policy_reference="synthetic-test-policy",
    )
    return backend, str(session["session_id"])


def _intent(session_id: str, artifact_id: str = "fixture-a", parents: tuple[str, ...] = ()) -> ArtifactIntent:
    return ArtifactIntent(
        intent_id=f"intent-{artifact_id}",
        artifact_id=artifact_id,
        session_id=session_id,
        artifact_kind="TECHNICAL_FIXTURE",
        technical_input_kind="DETERMINISTIC_FIXTURE",
        capture_profile_version="fixture-profile-v1",
        monotonic_timing_origin="synthetic-monotonic-v1",
        processing_version="fixture-generator-v1",
        parent_ids=parents,
    )


def test_v1_remains_independently_valid_before_additive_v2_migration(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    M1Store(root).close()
    store = M2PersistenceStore(root)
    assert store.schema_version == 2
    store.close()


def test_migrates_v1_to_v2_and_reopens_exact_schema(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    store = M2PersistenceStore(root)
    assert store.ledger_versions() == (1, 2)
    store.close()
    reopened = M2PersistenceStore(root)
    assert reopened.ledger_versions() == (1, 2)
    reopened.close()


def test_migration_fault_rolls_back_additive_schema_and_ledger(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    with pytest.raises(PersistenceFailure, match="migration"):
        M2PersistenceStore(root, migration_fault=lambda: (_ for _ in ()).throw(OSError("inject")))
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]
    assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='artifact_manifests'").fetchone() is None
    connection.close()


def test_rejects_an_existing_empty_or_malformed_v1_database(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("DROP TABLE schema_migrations")
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError, match="ledger"):
        M2PersistenceStore(root)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE schema_migrations SET checksum='changed' WHERE version=1",
        "DELETE FROM schema_migrations WHERE version=1",
        "INSERT INTO schema_migrations(version,applied_at_utc,checksum) VALUES(99,'future','x')",
    ],
)
def test_rejects_bad_or_newer_migration_ledger(tmp_path: Path, sql: str) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(sql)
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError):
        M2PersistenceStore(root)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP INDEX idx_m2_manifests_session",
        "DROP TABLE artifact_manifests",
        "CREATE TABLE extra_m2_object(id TEXT)",
    ],
)
def test_rejects_v2_ddl_index_and_object_tamper(tmp_path: Path, sql: str) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    store = M2PersistenceStore(root)
    store.close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(sql)
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError):
        M2PersistenceStore(root)


def test_rejects_v2_column_and_foreign_key_tamper(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    store = M2PersistenceStore(root)
    store.close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("ALTER TABLE artifact_manifests ADD COLUMN tampered TEXT")
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError):
        M2PersistenceStore(root)


def test_rejects_v2_foreign_key_tamper(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    store = M2PersistenceStore(root)
    store.close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("DROP INDEX idx_m2_intents_status")
    connection.execute("DROP TABLE m2_write_intents")
    connection.execute(
        "CREATE TABLE m2_write_intents(id TEXT PRIMARY KEY,session_id TEXT NOT NULL,artifact_id TEXT NOT NULL UNIQUE,partial_relative_path TEXT NOT NULL UNIQUE,final_relative_path TEXT NOT NULL UNIQUE,request_hash TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('PENDING','SEALED','FAILED','QUARANTINED')),created_at REAL NOT NULL,terminal_at REAL)"
    )
    connection.execute("CREATE INDEX idx_m2_intents_status ON m2_write_intents(status)")
    connection.commit()
    connection.close()
    with pytest.raises(SchemaIntegrityError):
        M2PersistenceStore(root)


def test_persists_valid_fixture_hash_and_reopens_manifest(tmp_path: Path) -> None:
    backend, session_id = _research(tmp_path / "root")
    root = tmp_path / "root"
    store = M2PersistenceStore(root)
    receipt = store.persist(_intent(session_id), StaticArtifactSource(b"fixture-bytes"))
    assert receipt["sha256"] == hashlib.sha256(b"fixture-bytes").hexdigest()
    assert set(receipt) == {"artifact_id", "artifact_kind", "technical_input_kind", "byte_size", "sha256", "manifest_schema_version", "validity_state", "sealed_at", "durability_state"}
    store.close()
    reopened = M2PersistenceStore(tmp_path / "root")
    assert reopened.manifest("fixture-a")["byte_size"] == len(b"fixture-bytes")
    reopened.close()
    backend.store.close()


def test_duplicate_intent_replays_only_the_same_canonical_request(tmp_path: Path) -> None:
    backend, session_id = _research(tmp_path / "root")
    store = M2PersistenceStore(tmp_path / "root")
    first = store.persist(_intent(session_id), StaticArtifactSource(b"fixture-bytes"))
    assert store.persist(_intent(session_id), StaticArtifactSource(b"fixture-bytes")) == first
    with pytest.raises(PersistenceFailure, match="idempotency"):
        store.persist(_intent(session_id), StaticArtifactSource(b"different"))
    store.close()
    backend.store.close()


@pytest.mark.parametrize(
    "changed",
    [
        {"artifact_id": "../escape"},
        {"artifact_kind": "REAL_CAPTURE"},
        {"technical_input_kind": "NO_HUMAN_DEVICE_SCENE"},
        {"capture_profile_version": "C:/private/path"},
    ],
)
def test_rejects_unsafe_ids_kinds_and_path_shaped_metadata(tmp_path: Path, changed: dict[str, str]) -> None:
    backend, session_id = _research(tmp_path / "root")
    store = M2PersistenceStore(tmp_path / "root")
    values = _intent(session_id).__dict__ | changed
    with pytest.raises(PersistenceFailure):
        store.persist(ArtifactIntent(**values), StaticArtifactSource(b"fixture"))
    store.close()
    backend.store.close()


def test_rejects_symlinked_artifact_directory(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    target = root / "outside"
    target.mkdir()
    artifacts = root / "artifacts"
    artifacts.mkdir()
    try:
        os.symlink(target, artifacts / "m2")
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(PersistenceFailure, match="symlink|reparse"):
        M2PersistenceStore(root)
    backend.store.close()


def test_rejects_missing_invalid_cross_session_and_cyclic_parents(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root, "one")
    _other, other_session = _research(root, "two")
    store = M2PersistenceStore(root)
    with pytest.raises(InvalidTransition, match="parent"):
        store.persist(_intent(session_id, "missing", ("none",)), StaticArtifactSource(b"x"))
    store.persist(_intent(session_id, "parent"), StaticArtifactSource(b"parent"))
    with pytest.raises(InvalidTransition, match="session"):
        store.persist(_intent(other_session, "other", ("parent",)), StaticArtifactSource(b"child"))
    with pytest.raises(InvalidTransition, match="cycle"):
        store.persist(_intent(session_id, "cycle", ("cycle",)), StaticArtifactSource(b"child"))
    backend.store.connection.execute("UPDATE artifact_registry SET status='INVALIDATED' WHERE id='parent'")
    with pytest.raises(InvalidTransition, match="parent"):
        store.persist(_intent(session_id, "invalid", ("parent",)), StaticArtifactSource(b"child"))
    store.close()
    backend.store.close()


class _FailingSource:
    def read_bytes(self) -> bytes:
        raise OSError("disk write injected")


def test_source_failure_never_reports_sealed_manifest(tmp_path: Path) -> None:
    backend, session_id = _research(tmp_path / "root")
    store = M2PersistenceStore(tmp_path / "root")
    with pytest.raises(PersistenceFailure, match="write"):
        store.persist(_intent(session_id), _FailingSource())
    assert store.manifest_or_none("fixture-a") is None
    with pytest.raises(KeyError):
        store.intent_status("intent-fixture-a")
    store.close()
    backend.store.close()


@pytest.mark.parametrize("stage", ["write", "fsync", "hash", "rename", "db_commit"])
def test_stage_faults_never_return_a_sealed_or_valid_manifest(tmp_path: Path, stage: str) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)

    def fail_at(current: str) -> None:
        if current == stage:
            raise OSError(f"injected {stage}")

    store = M2PersistenceStore(root, fault_hook=fail_at)
    with pytest.raises(PersistenceFailure):
        store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    assert store.manifest_or_none("fixture-a") is None
    expected = "FAILED" if stage == "write" else "QUARANTINED"
    assert store.intent_status("intent-fixture-a") == expected
    store.close()
    backend.store.close()


def test_failed_partial_is_quarantined_before_later_withdrawal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)

    def fail_at(stage: str) -> None:
        if stage == "fsync":
            raise OSError("injected fsync")

    store = M2PersistenceStore(root, fault_hook=fail_at)
    with pytest.raises(PersistenceFailure):
        store.persist(_intent(session_id), StaticArtifactSource(b"participant-like-bytes"))

    backend.withdraw(session_id, idempotency_key="withdraw-after-failed-partial")
    assert store.intent_status("intent-fixture-a") == "QUARANTINED"
    assert not (root / "staging" / "m2-partials" / "fixture-a.part").exists()
    assert not (root / "artifacts" / "m2" / "fixture-a.bin").exists()
    quarantined = tuple((root / "operational" / "quarantine").glob("*.quarantine"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"participant-like-bytes"
    store.close()
    backend.store.close()


def test_withdrawal_before_intent_and_before_commit_never_seals(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    backend.withdraw(session_id, idempotency_key="withdraw-first")
    store = M2PersistenceStore(root)
    with pytest.raises(InvalidTransition):
        store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    store.close()
    backend.store.close()


def test_withdrawal_injected_before_commit_preserves_withdrawn_state(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root, before_commit=lambda: backend.withdraw(session_id, idempotency_key="withdraw-race"))
    with pytest.raises(InvalidTransition):
        store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    assert backend.research_session(session_id)["state"] == "WITHDRAWN"
    assert store.manifest_or_none("fixture-a") is None
    store.close()
    backend.store.close()


def test_recovery_quarantines_pending_partial_and_renamed_orphan(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root)
    pending = _intent(session_id, "pending")
    store.create_pending_intent_for_test(pending)
    partial = root / "staging" / "m2-partials" / "pending.part"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(b"partial")
    orphan = root / "artifacts" / "m2" / "orphan.bin"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"orphan")
    result = store.recover()
    assert result["quarantined"] == 2
    assert store.intent_status("intent-pending") == "QUARANTINED"
    assert not partial.exists() and not orphan.exists()
    store.close()
    backend.store.close()


def test_withdrawal_invalidates_p1_artifact_through_canonical_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root)
    store.persist(_intent(session_id, "parent"), StaticArtifactSource(b"parent"))
    store.persist(_intent(session_id, "child", ("parent",)), StaticArtifactSource(b"child"))
    backend.withdraw(session_id, idempotency_key="withdraw-lineage")
    assert backend.artifact_status("parent") == "INVALIDATED"
    assert backend.artifact_status("child") == "INVALIDATED"
    store.close()
    backend.store.close()


def test_public_contract_has_no_routes_devices_audio_real_or_participant_creation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    store = M2PersistenceStore(root)
    assert not hasattr(store, "create_participant")
    assert not hasattr(store, "create_route")
    assert not hasattr(store, "enumerate_devices")
    assert not hasattr(store, "export")
    store.close()


def test_post_rename_substitution_fails_closed_before_manifest_commit(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)

    def substitute(path: Path) -> None:
        path.write_bytes(b"substituted")

    store = M2PersistenceStore(root, after_rename=substitute)
    with pytest.raises(PersistenceFailure, match="final"):
        store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    assert store.manifest_or_none("fixture-a") is None
    assert backend.store.connection.execute(
        "SELECT 1 FROM artifact_registry WHERE id='fixture-a'"
    ).fetchone() is None
    store.close()
    backend.store.close()


def test_reopen_recovery_ignores_tampered_db_path_and_fails_nonwithdrawn_session(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root)
    intent = _intent(session_id, "pending")
    store.create_pending_intent_for_test(intent)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    store.connection.execute(
        "UPDATE m2_write_intents SET final_relative_path='../outside.bin' WHERE id=?",
        (intent.intent_id,),
    )
    store.close()
    reopened = M2PersistenceStore(root)
    assert outside.read_bytes() == b"outside"
    assert reopened.intent_status(intent.intent_id) == "QUARANTINED"
    assert backend.research_session(session_id)["state"] == "FAILED"
    assert backend.research_session(session_id)["collection_blocked"] is True
    event = backend.store.connection.execute(
        "SELECT event_type,payload_json FROM session_events WHERE session_id=? ORDER BY event_seq DESC",
        (session_id,),
    ).fetchone()
    audit = backend.store.connection.execute(
        "SELECT event_type,payload_json FROM audit_events WHERE session_id=? ORDER BY created_at DESC",
        (session_id,),
    ).fetchone()
    assert event["event_type"] == "M2IntentQuarantined"
    assert audit["event_type"] == "M2_INTENT_QUARANTINED"
    assert "outside" not in event["payload_json"] + audit["payload_json"]
    reopened.close()
    backend.store.close()


def test_withdrawal_subordinates_manifest_and_idempotent_replay_to_registry(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root)
    first = store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    backend.withdraw(session_id, idempotency_key="withdraw-after-seal")
    assert store.manifest("fixture-a")["validity_state"] == "INVALIDATED"
    assert store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))["validity_state"] == "INVALIDATED"
    assert first["validity_state"] == "VALID"
    store.close()
    backend.store.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("capture_profile_version", "person@example.edu"),
        ("monotonic_timing_origin", "token=private"),
        ("processing_version", "arbitrary-build-77"),
    ],
)
def test_private_metadata_values_fail_explicit_allowlists(
    tmp_path: Path, field: str, value: str
) -> None:
    backend, session_id = _research(tmp_path / "root")
    store = M2PersistenceStore(tmp_path / "root")
    values = _intent(session_id).__dict__ | {field: value}
    with pytest.raises(PersistenceFailure, match="allowlisted"):
        store.persist(ArtifactIntent(**values), StaticArtifactSource(b"fixture"))
    store.close()
    backend.store.close()


def test_receipt_reports_explicit_parent_directory_durability_state(tmp_path: Path) -> None:
    backend, session_id = _research(tmp_path / "root")
    store = M2PersistenceStore(tmp_path / "root")
    receipt = store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    assert receipt["durability_state"] in {"CONFIRMED", "PLATFORM_UNSUPPORTED"}
    store.close()
    backend.store.close()


def test_same_intent_concurrent_retries_replay_and_competing_artifact_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    first = M2PersistenceStore(root)
    intent = _intent(session_id)
    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(
            executor.map(
                lambda store: store.persist(intent, StaticArtifactSource(b"fixture")),
                (first, first),
            )
        )
    assert receipts[0] == receipts[1]
    competing = ArtifactIntent(
        **(_intent(session_id, "fixture-a").__dict__ | {"intent_id": "other-intent"})
    )
    with pytest.raises(PersistenceFailure, match="artifact"):
        first.persist(competing, StaticArtifactSource(b"different"))
    first.close()
    backend.store.close()


def test_lifetime_root_lease_rejects_subprocess_without_recovery_or_mutation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    owner = M2PersistenceStore(root)
    owner.create_pending_intent_for_test(_intent(session_id, "pending"))
    code = (
        "from pathlib import Path\n"
        "from pdu_exam_observer.m2_persistence import M2PersistenceStore, StoreOwnerUnavailable\n"
        "try:\n"
        f" M2PersistenceStore(Path(r'{root}'))\n"
        "except StoreOwnerUnavailable:\n"
        " print('STORE_OWNER_UNAVAILABLE')\n"
        "else:\n"
        " raise SystemExit(9)\n"
    )
    environment = os.environ | {"PYTHONPATH": "src"}
    contender = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert contender.returncode == 0
    assert contender.stdout.strip() == "STORE_OWNER_UNAVAILABLE"
    assert owner.intent_status("intent-pending") == "PENDING"
    assert backend.research_session(session_id)["state"] == "DRAFT"
    owner.close()
    backend.store.close()


def test_directory_swap_before_rename_cannot_escape_or_seal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    outside = tmp_path / "outside"
    outside.mkdir()

    def swap_artifact_directory(path: Path) -> None:
        directory = path.parent
        directory.rmdir()
        os.symlink(outside, directory)

    store = M2PersistenceStore(root, before_rename=swap_artifact_directory)
    with pytest.raises(PersistenceFailure):
        store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    assert not (outside / "fixture-a.bin").exists()
    assert store.manifest_or_none("fixture-a") is None
    store.close()
    backend.store.close()


def test_guard_and_lease_handles_close_after_post_rename_failure(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root, after_rename=lambda _path: (_ for _ in ()).throw(OSError("fault")))
    with pytest.raises(PersistenceFailure):
        store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    store.close()
    backend.store.close()
    shutil.rmtree(root)
    assert not root.exists()


def test_constructor_releases_lease_after_reparse_database_rejection(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"not-a-database")
    database.unlink()
    try:
        os.symlink(outside, database)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(SchemaIntegrityError):
        M2PersistenceStore(root)
    database.unlink()
    M1Store(root).close()
    M2PersistenceStore(root).close()


def test_actual_windows_handle_check_rejects_acquisition_window_swap(tmp_path: Path) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    outside = tmp_path / "outside"
    outside.mkdir()

    def swap(path: Path) -> None:
        if path.name != "m2":
            return
        path.rmdir()
        os.symlink(outside, path)

    with pytest.raises(PersistenceFailure, match="reparse|handle"):
        M2PersistenceStore(root, before_handle_open=swap)
    assert not (outside / "m2").exists()


def test_non_windows_capability_refuses_before_artifact_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, session_id = _research(tmp_path / "root")
    store = M2PersistenceStore(tmp_path / "root")
    monkeypatch.setattr(m2_persistence.os, "name", "posix")
    with pytest.raises(PlatformUnsupported, match="PLATFORM_UNSUPPORTED"):
        store.persist(_intent(session_id), StaticArtifactSource(b"fixture"))
    assert store.manifest_or_none("fixture-a") is None
    store.close()
    backend.store.close()


def test_p1_rejects_missing_v1_root_without_creating_any_storage(tmp_path: Path) -> None:
    root = tmp_path / "missing-root"
    with pytest.raises(SchemaIntegrityError, match="existing v1"):
        M2PersistenceStore(root)
    assert not root.exists()


@pytest.mark.parametrize("missing", ("operational", "database"))
def test_p1_rejects_missing_v1_components_without_bootstrapping(
    tmp_path: Path, missing: str
) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    operational = root / "operational"
    database = operational / "pdu-exam-observer.sqlite3"
    if missing == "operational":
        for child in operational.iterdir():
            child.unlink()
        operational.rmdir()
    else:
        database.unlink()
    before = {path.relative_to(root) for path in root.rglob("*")}

    with pytest.raises(SchemaIntegrityError, match="existing v1"):
        M2PersistenceStore(root)

    assert {path.relative_to(root) for path in root.rglob("*")} == before


def test_operational_swap_before_lifetime_handle_creates_no_outside_lease_or_database(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    outside = tmp_path / "outside"
    outside.mkdir()
    operational = root / "operational"
    moved = root / "moved-operational"

    def swap(path: Path) -> None:
        if path != operational:
            return
        os.replace(operational, moved)
        os.symlink(outside, operational)

    with pytest.raises(PersistenceFailure, match="reparse|handle"):
        M2PersistenceStore(root, before_handle_open=swap)
    assert not (outside / "p1-store.lock").exists()
    assert not (outside / "pdu-exam-observer.sqlite3").exists()


def test_database_leaf_swap_before_guard_never_migrates_outside_v1_database(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    outside_root = tmp_path / "outside"
    M1Store(outside_root).close()
    outside_database = outside_root / "operational" / "pdu-exam-observer.sqlite3"
    moved = root / "operational" / "moved.sqlite3"

    def swap(path: Path) -> None:
        if path != database:
            return
        os.replace(database, moved)
        os.symlink(outside_database, database)

    with pytest.raises(PersistenceFailure, match="reparse|handle"):
        M2PersistenceStore(root, before_handle_open=swap)

    connection = sqlite3.connect(outside_database)
    assert connection.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'artifact_manifests'"
    ).fetchone() is None
    connection.close()
    assert not outside_database.with_name(f"{outside_database.name}-wal").exists()
    assert not outside_database.with_name(f"{outside_database.name}-shm").exists()


def test_existing_sqlite_sidecar_reparse_is_rejected_before_migration(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    sidecar = database.with_name(f"{database.name}-wal")
    outside = tmp_path / "outside-wal"
    outside.write_bytes(b"outside")
    try:
        os.symlink(outside, sidecar)
    except OSError as exc:
        pytest.skip(f"sidecar symlink creation unavailable: {exc}")

    with pytest.raises(PersistenceFailure, match="sidecar"):
        M2PersistenceStore(root)

    connection = sqlite3.connect(database)
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'artifact_manifests'"
    ).fetchone() is None
    connection.close()


def test_absent_wal_reservation_race_rejects_outside_symlink_before_sqlite(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    M1Store(root).close()
    database = root / "operational" / "pdu-exam-observer.sqlite3"
    wal = database.with_name(f"{database.name}-wal")
    outside = tmp_path / "outside-wal"
    outside.write_bytes(b"outside-wal-bytes")

    def plant(path: Path) -> None:
        if path != wal or os.path.lexists(wal):
            return
        os.symlink(outside, wal)

    with pytest.raises(PersistenceFailure, match="reparse|sidecar|handle"):
        M2PersistenceStore(root, before_handle_open=plant)

    assert outside.read_bytes() == b"outside-wal-bytes"
    assert not outside.with_name(f"{outside.name}-shm").exists()


def test_sqlite_sidecar_guards_close_and_reopen_without_local_stall(tmp_path: Path) -> None:
    from time import perf_counter

    root = tmp_path / "root"
    M1Store(root).close()
    durations: list[float] = []
    for _ in range(2):
        store = M2PersistenceStore(root)
        started = perf_counter()
        store.close()
        durations.append(perf_counter() - started)

    connection = sqlite3.connect(root / "operational" / "pdu-exam-observer.sqlite3")
    assert connection.execute("SELECT version FROM schema_migrations").fetchall() == [(1,), (2,)]
    connection.close()
    assert max(durations) < 0.75, durations


def test_migration_fault_cleanup_is_bounded_and_allows_immediate_exact_retry(
    tmp_path: Path,
) -> None:
    from shutil import rmtree
    from time import perf_counter

    root = tmp_path / "root"
    M1Store(root).close()

    def fail() -> None:
        raise RuntimeError("migration fault")

    started = perf_counter()
    with pytest.raises(PersistenceFailure, match="migration rolled back"):
        M2PersistenceStore(root, migration_fault=fail)
    duration = perf_counter() - started

    store = M2PersistenceStore(root)
    store.close()
    connection = sqlite3.connect(root / "operational" / "pdu-exam-observer.sqlite3")
    assert connection.execute("SELECT version FROM schema_migrations").fetchall() == [(1,), (2,)]
    connection.close()
    rmtree(root)
    assert duration < 0.75, duration


def test_verified_artifact_read_returns_exact_bytes_and_enforces_bound(tmp_path: Path) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root)
    payload = b'{"artifact_kind":"M2_SYNTHETIC_PREFLIGHT_RECEIPT"}\n'
    store.persist(_intent(session_id), StaticArtifactSource(payload))
    assert store.read_verified_artifact("fixture-a", maximum_bytes=len(payload)) == payload
    with pytest.raises(PersistenceFailure, match="size|limit|maximum"):
        store.read_verified_artifact("fixture-a", maximum_bytes=len(payload) - 1)
    store.close()
    backend.store.close()


def test_verified_artifact_read_rejects_manifest_path_and_final_byte_tamper(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    backend, session_id = _research(root)
    store = M2PersistenceStore(root)
    payload = b"verified-artifact"
    store.persist(_intent(session_id), StaticArtifactSource(payload))
    original_relative = str(store.manifest("fixture-a")["relative_path"])
    store.connection.execute(
        "UPDATE artifact_manifests SET relative_path='artifacts/m2/other.bin' "
        "WHERE artifact_id='fixture-a'"
    )
    with pytest.raises(PersistenceFailure, match="path|manifest"):
        store.read_verified_artifact("fixture-a", maximum_bytes=1024)
    store.connection.execute(
        "UPDATE artifact_manifests SET relative_path=? WHERE artifact_id='fixture-a'",
        (original_relative,),
    )
    (root / "artifacts" / "m2" / "fixture-a.bin").write_bytes(b"tampered-artifact")
    with pytest.raises(PersistenceFailure, match="verification|hash|size"):
        store.read_verified_artifact("fixture-a", maximum_bytes=1024)
    store.close()
    backend.store.close()
