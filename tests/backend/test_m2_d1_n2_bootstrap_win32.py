from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest

from pdu_exam_observer.m2_d1_n2_a0 import BootstrapStatus
from pdu_exam_observer.m2_d1_n2_bootstrap import (
    BOOTSTRAP_EPOCH_DIGEST,
    ProvisioningReceiptV1,
    ProvisioningResult,
)
from pdu_exam_observer.m2_d1_n2_bootstrap_win32 import (
    BootstrapPaths,
    BootstrapState,
    CreateOpen,
    CreateOpenState,
    CtypesBootstrapHandleOps,
    CtypesBootstrapPublisher,
    FixedA0ApprovalSource,
    FixedBootstrapReader,
    InspectionOpen,
    InspectionOpenState,
    LazyFixedA0ApprovalSource,
    LazyWindowsProvisionedA0Bootstrap,
    WindowsProvisionedA0Bootstrap,
    identity_digest,
)
from pdu_exam_observer.m2_d1_n2_win32 import CtypesHandleOps, HandleInfo


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _bundle() -> bytes:
    public = struct.pack("<II", 0x31534345, 32) + bytes(range(1, 65))
    body = {
        "authority_revision": "d1-n2-authority-v1",
        "bootstrap_epoch_digest": BOOTSTRAP_EPOCH_DIGEST,
        "public_key_b64url": base64.urlsafe_b64encode(public)
        .rstrip(b"=")
        .decode("ascii"),
        "public_key_format": "BCRYPT_ECCPUBLIC_BLOB_P256",
    }
    return _canonical(
        {
            "body": body,
            "domain": "D1N2/A0_BOOTSTRAP/v1",
            "key_id": hashlib.sha256(public).hexdigest(),
            "schema_version": 1,
            "signature_algorithm": "ECDSA_P256_SHA256_IEEE_P1363",
            "signature_b64url": base64.urlsafe_b64encode(bytes(range(64)))
            .rstrip(b"=")
            .decode("ascii"),
        }
    )


@dataclass
class _Entry:
    payload: bytes
    identity: str
    reparse: bool = False


class _Ops:
    def __init__(
        self,
        entries: dict[str, _Entry],
        *,
        ambiguous: set[str] | None = None,
    ) -> None:
        self.entries = entries
        self.ambiguous = ambiguous or set()
        self.handles: dict[int, str] = {}
        self.positions: dict[int, int] = {}
        self.close_calls: list[int] = []
        self.next_handle = 1

    def open_inspection_tagged(self, path: str) -> InspectionOpen:
        if path in self.ambiguous:
            return InspectionOpen(InspectionOpenState.AMBIGUOUS)
        if path not in self.entries:
            return InspectionOpen(InspectionOpenState.ABSENT)
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = path
        self.positions[handle] = 0
        return InspectionOpen(InspectionOpenState.OPENED, handle)

    def info(self, handle: int) -> HandleInfo:
        path = self.handles[handle]
        entry = self.entries[path]
        return HandleInfo(
            disk=True,
            reparse=entry.reparse,
            directory=False,
            delete_pending=False,
            links=1,
            final_path=path,
            identity=entry.identity,
            size=len(entry.payload),
        )

    def read(self, handle: int, limit: int) -> bytes | None:
        path = self.handles[handle]
        payload = self.entries[path].payload
        start = self.positions[handle]
        result = payload[start : start + limit]
        self.positions[handle] += len(result)
        return result

    def seek_start(self, handle: int) -> bool:
        self.positions[handle] = 0
        return True

    def close(self, handle: int) -> bool:
        self.close_calls.append(handle)
        return True


class _Parent:
    identity = "parent-identity"

    def __init__(self) -> None:
        self.close_calls = 0
        self.close_error: BaseException | None = None

    def validate(self) -> bool:
        return True

    def durable(self) -> bool:
        return True

    def close(self) -> bool:
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        return True


def _installed_entries(paths: BootstrapPaths) -> dict[str, _Entry]:
    bundle = _bundle()
    key_id = json.loads(bundle)["key_id"]
    receipt = ProvisioningReceiptV1(
        result=ProvisioningResult.INSTALLED,
        installed_unix_ns=123,
        bootstrap_bundle_sha256=hashlib.sha256(bundle).hexdigest(),
        key_id=key_id,
        bootstrap_epoch_digest=BOOTSTRAP_EPOCH_DIGEST,
        create_new=True,
        no_reparse=True,
        share_zero=True,
        write_flushed=True,
        parent_durable=True,
        promoted_no_replace=True,
        readback_verified=True,
        leaf_identity_digest=identity_digest("receipt-identity"),
        parent_identity_digest=identity_digest(_Parent.identity),
        cleanup_clean=True,
    ).canonical_bytes()
    return {
        paths.bundle: _Entry(bundle, "bundle-identity"),
        paths.receipt: _Entry(receipt, "receipt-identity"),
    }


def test_clean_absence_is_unprovisioned_and_closes_parent() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    parent = _Parent()

    result = FixedBootstrapReader(paths, _Ops({}), parent, lambda *_: True).inspect()

    assert result.state is BootstrapState.ABSENT
    assert result.lease is None
    assert parent.close_calls == 1


def test_clean_absence_parent_close_base_exception_is_poisoned_without_retry() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    parent = _Parent()
    parent.close_error = KeyboardInterrupt()

    result = FixedBootstrapReader(paths, _Ops({}), parent, lambda *_: True).inspect()

    assert result.state is BootstrapState.POISONED
    assert result.lease is None
    assert parent.close_calls == 1


def test_partial_leaf_is_poisoned_and_never_treated_as_absence() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    parent = _Parent()
    ops = _Ops({paths.partial: _Entry(b"partial", "partial-identity")})

    result = FixedBootstrapReader(paths, ops, parent, lambda *_: True).inspect()

    assert result.state is BootstrapState.POISONED
    assert result.lease is None
    assert ops.close_calls == [1]
    assert parent.close_calls == 1


def test_ambiguous_open_is_poisoned_and_never_treated_as_absence() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    parent = _Parent()
    ops = _Ops({}, ambiguous={paths.partial})

    result = FixedBootstrapReader(paths, ops, parent, lambda *_: True).inspect()

    assert result.state is BootstrapState.POISONED
    assert result.lease is None
    assert ops.close_calls == []
    assert parent.close_calls == 1


def test_terminal_publisher_uses_only_fixed_no_replace_write_through_move() -> None:
    class Move:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []
            self.argtypes: object = None
            self.restype: object = None

        def __call__(self, *args: object) -> int:
            self.calls.append(args)
            return 1

    class Kernel:
        def __init__(self) -> None:
            self.MoveFileExW = Move()

    paths = BootstrapPaths.for_root(r"C:\authority")
    kernel = Kernel()
    publisher = CtypesBootstrapPublisher(paths, kernel)

    assert publisher.promote_bundle_no_replace_write_through(
        paths.partial, paths.bundle
    )
    assert publisher.publish_fixed_receipt_no_replace_write_through(
        paths.partial, paths.receipt
    )
    assert not publisher.publish_fixed_receipt_no_replace_write_through(
        r"C:\other\candidate", paths.receipt
    )
    assert kernel.MoveFileExW.calls == [
        (paths.partial, paths.bundle, 0x00000008),
        (paths.partial, paths.receipt, 0x00000008),
    ]
    assert kernel.MoveFileExW.argtypes == [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
    ]


def test_lazy_production_bootstrap_performs_no_io_until_inspection() -> None:
    calls = 0

    def reader_factory() -> FixedBootstrapReader | None:
        nonlocal calls
        calls += 1
        return None

    bootstrap = LazyWindowsProvisionedA0Bootstrap(reader_factory, lambda *_: True)

    assert calls == 0
    assert bootstrap.inspect() is BootstrapStatus.REJECTED
    assert calls == 1
    assert bootstrap.inspect() is BootstrapStatus.REJECTED
    assert calls == 1
    assert bootstrap.close()


def test_lazy_a0_source_fails_closed_when_fixed_source_cannot_be_acquired() -> None:
    source = LazyFixedA0ApprovalSource(lambda: None)

    try:
        source.open_fixed()
    except RuntimeError as error:
        assert str(error) == "fixed A0 source is unavailable"
    else:
        raise AssertionError("missing fixed A0 source must fail closed")


def test_ctypes_tagged_open_distinguishes_absent_opened_and_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = object.__new__(CtypesBootstrapHandleOps)

    monkeypatch.setattr(CtypesHandleOps, "open_inspection", lambda *_: None)
    assert adapter.open_inspection_tagged(r"C:\missing") == InspectionOpen(
        InspectionOpenState.ABSENT
    )

    monkeypatch.setattr(CtypesHandleOps, "open_inspection", lambda *_: 73)
    assert adapter.open_inspection_tagged(r"C:\present") == InspectionOpen(
        InspectionOpenState.OPENED, 73
    )

    def ambiguous(*_args: object) -> int:
        raise OSError(5, "access denied")

    monkeypatch.setattr(CtypesHandleOps, "open_inspection", ambiguous)
    assert adapter.open_inspection_tagged(r"C:\blocked") == InspectionOpen(
        InspectionOpenState.AMBIGUOUS
    )


def test_ctypes_tagged_create_distinguishes_conflict_from_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = object.__new__(CtypesBootstrapHandleOps)
    monkeypatch.setattr(CtypesHandleOps, "create_new", lambda *_: 81)
    assert adapter.create_new_tagged(r"C:\new") == CreateOpen(
        CreateOpenState.CREATED, 81
    )

    monkeypatch.setattr(CtypesHandleOps, "create_new", lambda *_: None)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 80)
    assert adapter.create_new_tagged(r"C:\existing") == CreateOpen(
        CreateOpenState.EXISTS
    )

    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5)
    assert adapter.create_new_tagged(r"C:\blocked") == CreateOpen(
        CreateOpenState.AMBIGUOUS
    )


@pytest.mark.skipif(os.name != "nt", reason="requires real Windows MoveFileExW")
def test_real_windows_terminal_move_preserves_identity_and_never_replaces(
    tmp_path: Path,
) -> None:
    paths = BootstrapPaths.for_root(str(tmp_path))
    Path(paths.partial).write_bytes(b"receipt-candidate")
    ops = CtypesBootstrapHandleOps()
    before_open = ops.open_inspection_tagged(paths.partial)
    assert before_open.state is InspectionOpenState.OPENED
    assert before_open.handle is not None
    before = ops.info(before_open.handle)
    assert ops.close(before_open.handle)

    publisher = CtypesBootstrapPublisher(paths)
    assert publisher.publish_fixed_receipt_no_replace_write_through(
        paths.partial, paths.receipt
    )

    after_open = ops.open_inspection_tagged(paths.receipt)
    assert after_open.state is InspectionOpenState.OPENED
    assert after_open.handle is not None
    after = ops.info(after_open.handle)
    assert ops.close(after_open.handle)
    assert before.identity == after.identity
    assert Path(paths.receipt).read_bytes() == b"receipt-candidate"
    assert not Path(paths.partial).exists()

    Path(paths.partial).write_bytes(b"second-attempt")
    assert not publisher.publish_fixed_receipt_no_replace_write_through(
        paths.partial, paths.receipt
    )
    assert Path(paths.partial).read_bytes() == b"second-attempt"
    assert Path(paths.receipt).read_bytes() == b"receipt-candidate"


def test_valid_pair_is_installed_and_retained_until_idempotent_close() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    parent = _Parent()
    ops = _Ops(_installed_entries(paths))

    result = FixedBootstrapReader(paths, ops, parent, lambda *_: True).inspect()

    assert result.state is BootstrapState.INSTALLED
    assert result.bundle is not None
    assert result.receipt is not None
    assert result.lease is not None
    assert result.lease.validate()
    assert ops.close_calls == []
    assert result.lease.close()
    assert result.lease.close()
    assert ops.close_calls == [2, 1]
    assert parent.close_calls == 1


def test_asymmetric_or_reparse_pair_is_poisoned_and_closes_every_owner() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    entries = _installed_entries(paths)
    entries.pop(paths.receipt)
    parent = _Parent()
    ops = _Ops(entries)

    asymmetric = FixedBootstrapReader(paths, ops, parent, lambda *_: True).inspect()

    assert asymmetric.state is BootstrapState.POISONED
    assert ops.close_calls == [1]
    assert parent.close_calls == 1

    entries = _installed_entries(paths)
    entries[paths.bundle].reparse = True
    parent = _Parent()
    ops = _Ops(entries)

    reparse = FixedBootstrapReader(paths, ops, parent, lambda *_: True).inspect()

    assert reparse.state is BootstrapState.POISONED
    assert ops.close_calls == [2, 1]
    assert parent.close_calls == 1


def test_retained_bootstrap_lease_rejects_identity_drift() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    entries = _installed_entries(paths)
    result = FixedBootstrapReader(
        paths, _Ops(entries), _Parent(), lambda *_: True
    ).inspect()
    assert result.lease is not None

    entries[paths.bundle].identity = "replacement"

    assert not result.lease.validate()
    assert result.lease.close()


def test_fixed_a0_source_returns_retained_exact_read_only_lease() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    parent = _Parent()
    ops = _Ops({paths.approval: _Entry(b"approval", "approval-identity")})
    source = FixedA0ApprovalSource(paths, ops, lambda: parent)

    lease = source.open_fixed()

    assert lease.read_exact() == b"approval"
    assert lease.validate()
    assert lease.parent_durable()
    assert lease.close()
    assert lease.close()
    assert ops.close_calls == [1]
    assert parent.close_calls == 1


def test_provisioned_bootstrap_reuses_retained_key_only_for_exact_a0_key_id() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    calls: list[tuple[bytes, bytes, bytes]] = []

    def verify(public_blob: bytes, message: bytes, signature: bytes) -> bool:
        calls.append((public_blob, message, signature))
        return True

    bootstrap = WindowsProvisionedA0Bootstrap(
        FixedBootstrapReader(paths, _Ops(_installed_entries(paths)), _Parent(), verify),
        verify,
    )

    assert bootstrap.inspect() is BootstrapStatus.VERIFIED
    assert bootstrap.validate()
    assert bootstrap.verify(b"a0-body", json.loads(_bundle())["key_id"], b"s" * 64) is (
        BootstrapStatus.VERIFIED
    )
    assert bootstrap.verify(b"a0-body", "ff" * 32, b"s" * 64) is (
        BootstrapStatus.REJECTED
    )
    assert calls[-1][1:] == (b"a0-body", b"s" * 64)
    assert bootstrap.close()
    assert bootstrap.close()
