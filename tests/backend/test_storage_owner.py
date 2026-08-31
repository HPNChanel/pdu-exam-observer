from pathlib import Path

import pytest

from pdu_exam_observer.m1 import M1Backend, M1Store, SchemaIntegrityError
from pdu_exam_observer.m2_persistence import M2PersistenceStore
from pdu_exam_observer.storage_owner import SQLiteStoreOwner


def _build_v1_root(root: Path) -> None:
    store = M1Store(root)
    store.close()


def test_guarded_v2_owner_is_the_only_store_used_by_injected_m1_backend(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    _build_v1_root(root)
    owner: SQLiteStoreOwner = M2PersistenceStore(root)

    try:
        backend = M1Backend(
            root,
            encryption_status="VERIFIED",
            acl_status="VERIFIED",
            store=owner,
        )

        assert backend.store is owner
        assert backend.store.connection is owner.connection
        assert backend.store.schema_version == 2
        row = owner.connection.execute(
            "SELECT encryption_status,acl_status FROM storage_roots WHERE id='active'"
        ).fetchone()
        assert row is not None
        assert tuple(row) == ("VERIFIED", "VERIFIED")

        session, _ = backend.create_session()
        assert owner.connection.execute(
            "SELECT id FROM sessions WHERE id=?", (session.session_id,)
        ).fetchone() is not None
    finally:
        owner.close()


def test_injected_owner_root_mismatch_is_rejected_before_storage_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    _build_v1_root(root)
    owner = M2PersistenceStore(root)

    try:
        before = owner.connection.total_changes
        with pytest.raises(SchemaIntegrityError, match="injected store root"):
            M1Backend(
                tmp_path / "different-root",
                encryption_status="VERIFIED",
                acl_status="VERIFIED",
                store=owner,
            )
        assert owner.connection.total_changes == before
    finally:
        owner.close()


def test_legacy_m1_backend_still_constructs_its_v1_store(tmp_path: Path) -> None:
    backend = M1Backend(
        tmp_path / "root",
        encryption_status="VERIFIED",
        acl_status="VERIFIED",
    )
    try:
        assert isinstance(backend.store, M1Store)
        assert backend.store.schema_version == 1
    finally:
        backend.store.close()
