from __future__ import annotations

import base64
import hashlib
import json
import struct
from dataclasses import dataclass

import pytest

from pdu_exam_observer.m2_d1_n2_bootstrap import (
    BOOTSTRAP_AUTHORITY_REVISION,
    BOOTSTRAP_EPOCH_DIGEST,
    BootstrapInstallAuthority,
    ProvisioningReceiptV1,
    ProvisioningResult,
    parse_provisioning_receipt,
)
from pdu_exam_observer.m2_d1_n2_bootstrap_install import (
    FixedBootstrapInstallMutex,
    FixedBootstrapInstallParent,
    OneShotBootstrapInstaller,
    parse_operator_authority,
)
from pdu_exam_observer.m2_d1_n2_bootstrap_win32 import (
    BootstrapPaths,
    CreateOpen,
    CreateOpenState,
    InspectionOpen,
    InspectionOpenState,
    identity_digest,
)
from pdu_exam_observer.m2_d1_n2_win32 import HandleInfo
from pdu_exam_observer.m2_d1_n2_win32_store import (
    DirectoryDurability,
    MutexStatus,
)


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
        "authority_revision": BOOTSTRAP_AUTHORITY_REVISION,
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


def _authority(bundle: bytes) -> BootstrapInstallAuthority:
    decoded = json.loads(bundle)
    return BootstrapInstallAuthority(
        authority_revision=BOOTSTRAP_AUTHORITY_REVISION,
        bootstrap_bundle_sha256=hashlib.sha256(bundle).hexdigest(),
        key_id=decoded["key_id"],
        bootstrap_epoch_digest=decoded["body"]["bootstrap_epoch_digest"],
        one_shot=True,
        overwrite=False,
    )


@dataclass
class _Entry:
    payload: bytearray
    identity: str


class _Ops:
    def __init__(self, paths: BootstrapPaths) -> None:
        self.paths = paths
        self.entries: dict[str, _Entry] = {}
        self.handles: dict[int, str] = {}
        self.positions: dict[int, int] = {}
        self.next_handle = 1
        self.next_identity = 1
        self.ambiguous: set[str] = set()
        self.create_ambiguous: set[str] = set()
        self.close_failure_paths: set[str] = set()
        self.close_failure_identities: set[str] = set()
        self.close_failure_occurrences: set[tuple[str, int]] = set()
        self.close_counts: dict[str, int] = {}
        self.write_failure_identities: set[str] = set()
        self.flush_failure_identities: set[str] = set()
        self.readback_failure_identities: set[str] = set()
        self.events: list[str] = []

    def open_inspection_tagged(self, path: str) -> InspectionOpen:
        self.events.append(f"open:{path}")
        if path in self.ambiguous:
            return InspectionOpen(InspectionOpenState.AMBIGUOUS)
        if path not in self.entries:
            return InspectionOpen(InspectionOpenState.ABSENT)
        return InspectionOpen(InspectionOpenState.OPENED, self._new_handle(path))

    def create_new_tagged(self, path: str) -> CreateOpen:
        self.events.append(f"create:{path}")
        if path in self.create_ambiguous:
            return CreateOpen(CreateOpenState.AMBIGUOUS)
        if path in self.entries:
            return CreateOpen(CreateOpenState.EXISTS)
        identity = f"leaf-{self.next_identity}"
        self.next_identity += 1
        self.entries[path] = _Entry(bytearray(), identity)
        return CreateOpen(CreateOpenState.CREATED, self._new_handle(path))

    def _new_handle(self, path: str) -> int:
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = path
        self.positions[handle] = 0
        return handle

    def info(self, handle: int) -> HandleInfo:
        path = self.handles[handle]
        entry = self.entries[path]
        return HandleInfo(
            disk=True,
            reparse=False,
            directory=False,
            delete_pending=False,
            links=1,
            final_path=path,
            identity=entry.identity,
            size=len(entry.payload),
        )

    def read(self, handle: int, limit: int) -> bytes | None:
        entry = self.entries[self.handles[handle]]
        start = self.positions[handle]
        result = bytes(entry.payload[start : start + limit])
        self.positions[handle] += len(result)
        if entry.identity in self.readback_failure_identities and result:
            return bytes([result[0] ^ 1]) + result[1:]
        return result

    def seek_start(self, handle: int) -> bool:
        self.positions[handle] = 0
        return True

    def write(self, handle: int, data: bytes) -> int:
        entry = self.entries[self.handles[handle]]
        if entry.identity in self.write_failure_identities:
            return 0
        start = self.positions[handle]
        end = start + len(data)
        entry.payload[start:end] = data
        self.positions[handle] = end
        return len(data)

    def flush(self, handle: int) -> bool:
        path = self.handles[handle]
        self.events.append(f"flush:{path}")
        return self.entries[path].identity not in self.flush_failure_identities

    def close(self, handle: int) -> bool:
        path = self.handles.pop(handle)
        identity = self.entries[path].identity
        occurrence = self.close_counts.get(identity, 0) + 1
        self.close_counts[identity] = occurrence
        self.positions.pop(handle)
        self.events.append(f"close:{path}")
        return (
            path not in self.close_failure_paths
            and identity not in self.close_failure_identities
            and (identity, occurrence) not in self.close_failure_occurrences
        )


class _Parent:
    identity = "parent-identity"

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.durable_results: list[bool] = []
        self.close_ok = True

    def validate(self) -> bool:
        return True

    def durable(self) -> bool:
        self.events.append("parent:durable")
        return self.durable_results.pop(0) if self.durable_results else True

    def close(self) -> bool:
        self.events.append("parent:close")
        return self.close_ok


class _Mutex:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.release_ok = True
        self.close_ok = True

    def acquire(self) -> bool:
        self.events.append("mutex:acquire")
        return True

    def release(self) -> bool:
        self.events.append("mutex:release")
        return self.release_ok

    def close(self) -> bool:
        self.events.append("mutex:close")
        return self.close_ok


class _Publisher:
    def __init__(self, ops: _Ops) -> None:
        self.ops = ops
        self.bundle_calls = 0
        self.receipt_calls = 0
        self.bundle_ok = True
        self.receipt_ok = True

    def promote_bundle_no_replace_write_through(
        self, source: str, destination: str
    ) -> bool:
        self.bundle_calls += 1
        return self.bundle_ok and self._move(source, destination)

    def publish_fixed_receipt_no_replace_write_through(
        self, source: str, destination: str
    ) -> bool:
        self.receipt_calls += 1
        self.ops.events.append("receipt:publish")
        return self.receipt_ok and self._move(source, destination)

    def _move(self, source: str, destination: str) -> bool:
        if source not in self.ops.entries or destination in self.ops.entries:
            return False
        self.ops.entries[destination] = self.ops.entries.pop(source)
        return True


def _installer(
    paths: BootstrapPaths,
    ops: _Ops,
    parent: _Parent,
    mutex: _Mutex,
    publisher: _Publisher,
) -> OneShotBootstrapInstaller:
    return OneShotBootstrapInstaller(
        paths,
        ops,
        lambda: parent,
        lambda: mutex,
        publisher,
        lambda *_: True,
        lambda: 123,
    )


def test_invalid_external_tuple_performs_no_authority_io() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    bundle = _bundle()
    invalid = _authority(bundle)
    invalid = BootstrapInstallAuthority(
        invalid.authority_revision,
        "00" * 32,
        invalid.key_id,
        invalid.bootstrap_epoch_digest,
        True,
        False,
    )

    result = _installer(paths, ops, parent, mutex, publisher).install(bundle, invalid)

    assert result.result is ProvisioningResult.INVALID_INPUT
    assert result.receipt is None
    assert ops.events == []
    assert publisher.bundle_calls == publisher.receipt_calls == 0


def test_success_publishes_receipt_only_after_all_cleanup() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    bundle = _bundle()

    result = _installer(paths, ops, parent, mutex, publisher).install(
        bundle, _authority(bundle)
    )

    assert result.result is ProvisioningResult.INSTALLED
    assert result.receipt is not None
    assert bytes(ops.entries[paths.bundle].payload) == bundle
    assert paths.partial not in ops.entries
    receipt_bytes = bytes(ops.entries[paths.receipt].payload)
    receipt = parse_provisioning_receipt(receipt_bytes)
    assert receipt == result.receipt
    assert receipt is not None
    assert receipt.leaf_identity_digest == identity_digest(
        ops.entries[paths.receipt].identity
    )
    assert publisher.bundle_calls == publisher.receipt_calls == 1
    assert ops.events.index("parent:close") < ops.events.index("mutex:release")
    assert ops.events.index("mutex:close") < ops.events.index("receipt:publish")


def test_receipt_writer_close_failure_never_calls_terminal_publisher() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    ops.close_failure_identities.add("leaf-2")
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    bundle = _bundle()

    result = _installer(paths, ops, parent, mutex, publisher).install(
        bundle, _authority(bundle)
    )

    assert result.result is ProvisioningResult.CLEANUP_FAILED
    assert result.receipt is None
    assert publisher.bundle_calls == 1
    assert publisher.receipt_calls == 0
    assert paths.receipt not in ops.entries
    assert paths.partial in ops.entries


@pytest.mark.parametrize("clock_error", [RuntimeError("clock"), KeyboardInterrupt()])
def test_clock_failure_cleans_every_owner_without_terminal_publication(
    clock_error: BaseException,
) -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    bundle = _bundle()

    def fail_clock() -> int:
        raise clock_error

    installer = OneShotBootstrapInstaller(
        paths,
        ops,
        lambda: parent,
        lambda: mutex,
        publisher,
        lambda *_: True,
        fail_clock,
    )

    result = installer.install(bundle, _authority(bundle))

    assert result.result is ProvisioningResult.WRITE_FAILED
    assert result.receipt is None
    assert publisher.bundle_calls == 1
    assert publisher.receipt_calls == 0
    assert paths.receipt not in ops.entries
    assert paths.partial in ops.entries
    assert ops.handles == {}
    assert ops.events.count("parent:close") == 1
    assert ops.events.count("mutex:release") == 1
    assert ops.events.count("mutex:close") == 1


@pytest.mark.parametrize(
    "canonical_error", [RuntimeError("canonical"), KeyboardInterrupt()]
)
def test_receipt_canonicalization_failure_cleans_every_owner_without_publication(
    monkeypatch: pytest.MonkeyPatch,
    canonical_error: BaseException,
) -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    bundle = _bundle()

    def fail_canonical(_receipt: ProvisioningReceiptV1) -> bytes:
        raise canonical_error

    monkeypatch.setattr(ProvisioningReceiptV1, "canonical_bytes", fail_canonical)

    result = _installer(paths, ops, parent, mutex, publisher).install(
        bundle, _authority(bundle)
    )

    assert result.result is ProvisioningResult.WRITE_FAILED
    assert result.receipt is None
    assert publisher.bundle_calls == 1
    assert publisher.receipt_calls == 0
    assert paths.receipt not in ops.entries
    assert paths.partial in ops.entries
    assert ops.handles == {}
    assert ops.events.count("parent:close") == 1
    assert ops.events.count("mutex:release") == 1
    assert ops.events.count("mutex:close") == 1


def test_ambiguous_preflight_open_never_creates_or_publishes() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    ops.ambiguous.add(paths.receipt)
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    bundle = _bundle()

    result = _installer(paths, ops, parent, mutex, publisher).install(
        bundle, _authority(bundle)
    )

    assert result.result is ProvisioningResult.WRITE_FAILED
    assert all(not event.startswith("create:") for event in ops.events)
    assert publisher.bundle_calls == publisher.receipt_calls == 0


def test_ambiguous_create_is_write_failure_not_existing_artifact() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    ops.create_ambiguous.add(paths.partial)
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    bundle = _bundle()

    result = _installer(paths, ops, parent, mutex, publisher).install(
        bundle, _authority(bundle)
    )

    assert result.result is ProvisioningResult.WRITE_FAILED
    assert publisher.bundle_calls == publisher.receipt_calls == 0


def test_existing_identical_bundle_is_not_a_second_install() -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    bundle = _bundle()
    ops.entries[paths.bundle] = _Entry(bytearray(bundle), "existing")
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)

    result = _installer(paths, ops, parent, mutex, publisher).install(
        bundle, _authority(bundle)
    )

    assert result.result is ProvisioningResult.ALREADY_EXISTS
    assert bytes(ops.entries[paths.bundle].payload) == bundle
    assert publisher.bundle_calls == publisher.receipt_calls == 0


def test_abandoned_production_mutex_is_not_mutation_authority_but_closes_cleanly() -> None:
    class Ops:
        def __init__(self) -> None:
            self.release_calls = 0
            self.close_calls = 0

        def acquire(self, name: str) -> MutexStatus:
            assert name == r"Local\PDUExamObserver.D1N2.AuthorityV1"
            return MutexStatus.ABANDONED

        def release(self) -> bool:
            self.release_calls += 1
            return True

        def close(self) -> bool:
            self.close_calls += 1
            return True

    ops = Ops()
    mutex = FixedBootstrapInstallMutex(ops)

    assert not mutex.acquire()
    assert mutex.close()
    assert ops.release_calls == 1
    assert ops.close_calls == 1


def test_production_parent_requires_exact_verified_directory_durability() -> None:
    class Lease:
        identities = ("base", "application", "authority")

        def validate(self) -> bool:
            return True

        def durable(self) -> DirectoryDurability:
            return DirectoryDurability.UNVERIFIED

        def close(self) -> bool:
            return True

    parent = FixedBootstrapInstallParent(Lease())

    assert parent.identity == "authority"
    assert parent.validate()
    assert not parent.durable()
    assert parent.close()


def test_operator_authority_requires_explicit_exact_one_shot_no_overwrite_tuple() -> None:
    bundle = _bundle()
    authority = _authority(bundle)

    parsed = parse_operator_authority(
        authority_revision=authority.authority_revision,
        bootstrap_bundle_sha256=authority.bootstrap_bundle_sha256,
        key_id=authority.key_id,
        bootstrap_epoch_digest=authority.bootstrap_epoch_digest,
        one_shot="true",
        overwrite="false",
    )

    assert parsed == authority
    assert (
        parse_operator_authority(
            authority_revision=authority.authority_revision,
            bootstrap_bundle_sha256=authority.bootstrap_bundle_sha256,
            key_id=authority.key_id,
            bootstrap_epoch_digest=authority.bootstrap_epoch_digest,
            one_shot="True",
            overwrite="false",
        )
        is None
    )


def test_operator_authority_rejects_well_formed_alternate_epoch_digest() -> None:
    bundle = _bundle()
    authority = _authority(bundle)

    assert (
        parse_operator_authority(
            authority_revision=authority.authority_revision,
            bootstrap_bundle_sha256=authority.bootstrap_bundle_sha256,
            key_id=authority.key_id,
            bootstrap_epoch_digest="cd" * 32,
            one_shot="true",
            overwrite="false",
        )
        is None
    )


@pytest.mark.parametrize(
    ("fault", "expected"),
    [
        ("bundle_write", ProvisioningResult.WRITE_FAILED),
        ("bundle_flush", ProvisioningResult.DURABILITY_FAILED),
        ("bundle_readback", ProvisioningResult.READBACK_FAILED),
        ("bundle_promotion", ProvisioningResult.WRITE_FAILED),
        ("bundle_parent_durability", ProvisioningResult.DURABILITY_FAILED),
        ("receipt_write", ProvisioningResult.WRITE_FAILED),
        ("receipt_flush", ProvisioningResult.DURABILITY_FAILED),
        ("receipt_readback", ProvisioningResult.READBACK_FAILED),
        ("receipt_parent_durability", ProvisioningResult.DURABILITY_FAILED),
        ("final_bundle_close", ProvisioningResult.CLEANUP_FAILED),
        ("parent_close", ProvisioningResult.CLEANUP_FAILED),
        ("mutex_release", ProvisioningResult.CLEANUP_FAILED),
        ("mutex_close", ProvisioningResult.CLEANUP_FAILED),
        ("receipt_publish", ProvisioningResult.WRITE_FAILED),
    ],
)
def test_fault_matrix_never_exposes_a_final_receipt(
    fault: str, expected: ProvisioningResult
) -> None:
    paths = BootstrapPaths.for_root(r"C:\authority")
    ops = _Ops(paths)
    parent = _Parent(ops.events)
    mutex = _Mutex(ops.events)
    publisher = _Publisher(ops)
    if fault == "bundle_write":
        ops.write_failure_identities.add("leaf-1")
    elif fault == "bundle_flush":
        ops.flush_failure_identities.add("leaf-1")
    elif fault == "bundle_readback":
        ops.readback_failure_identities.add("leaf-1")
    elif fault == "bundle_promotion":
        publisher.bundle_ok = False
    elif fault == "bundle_parent_durability":
        parent.durable_results = [False]
    elif fault == "receipt_write":
        ops.write_failure_identities.add("leaf-2")
    elif fault == "receipt_flush":
        ops.flush_failure_identities.add("leaf-2")
    elif fault == "receipt_readback":
        ops.readback_failure_identities.add("leaf-2")
    elif fault == "receipt_parent_durability":
        parent.durable_results = [True, False]
    elif fault == "final_bundle_close":
        ops.close_failure_occurrences.add(("leaf-1", 2))
    elif fault == "parent_close":
        parent.close_ok = False
    elif fault == "mutex_release":
        mutex.release_ok = False
    elif fault == "mutex_close":
        mutex.close_ok = False
    elif fault == "receipt_publish":
        publisher.receipt_ok = False

    bundle = _bundle()
    result = _installer(paths, ops, parent, mutex, publisher).install(
        bundle, _authority(bundle)
    )

    assert result.result is expected
    assert result.receipt is None
    assert paths.receipt not in ops.entries
    assert publisher.receipt_calls == (1 if fault == "receipt_publish" else 0)
