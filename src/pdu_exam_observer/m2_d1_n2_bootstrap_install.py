"""One-shot, source-only D1-N2 bootstrap provisioning state machine."""

from __future__ import annotations

import hashlib
import ntpath
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from pdu_exam_observer.m2_d1_n2_bootstrap import (
    BOOTSTRAP_AUTHORITY_REVISION,
    BOOTSTRAP_EPOCH_DIGEST,
    BootstrapInstallAuthority,
    ParsedBootstrapBundle,
    ProvisioningReceiptV1,
    ProvisioningResult,
    verify_approved_bootstrap_bundle,
)
from pdu_exam_observer.m2_d1_n2_bootstrap_win32 import (
    BootstrapPaths,
    CreateOpen,
    CreateOpenState,
    CtypesBootstrapHandleOps,
    CtypesBootstrapPublisher,
    InspectionOpen,
    InspectionOpenState,
    identity_digest,
)
from pdu_exam_observer.m2_d1_n2_cng import verify_ecdsa_p256_sha256_p1363
from pdu_exam_observer.m2_d1_n2_win32 import HandleInfo
from pdu_exam_observer.m2_d1_n2_win32_store import (
    AUTHORITY_MUTEX_NAME,
    CtypesDirectoryOps,
    CtypesMutexOps,
    DirectoryCleanupStatus,
    DirectoryDurability,
    DirectoryLease,
    MutexOps,
    MutexStatus,
    resolve_known_folder_authority_root,
)

_MAX_BOOTSTRAP_BYTES = 16_384
_MAX_RECEIPT_BYTES = 16_384


class BootstrapInstallHandleOps(Protocol):
    def open_inspection_tagged(self, path: str) -> InspectionOpen: ...

    def create_new_tagged(self, path: str) -> CreateOpen: ...

    def info(self, handle: int) -> HandleInfo: ...

    def read(self, handle: int, limit: int) -> bytes | None: ...

    def seek_start(self, handle: int) -> bool: ...

    def write(self, handle: int, data: bytes) -> int: ...

    def flush(self, handle: int) -> bool: ...

    def close(self, handle: int) -> bool: ...


class BootstrapInstallParent(Protocol):
    identity: str

    def validate(self) -> bool: ...

    def durable(self) -> bool: ...

    def close(self) -> bool: ...


class BootstrapInstallMutex(Protocol):
    def acquire(self) -> bool: ...

    def release(self) -> bool: ...

    def close(self) -> bool: ...


class BootstrapPublisher(Protocol):
    def promote_bundle_no_replace_write_through(
        self, source: str, destination: str
    ) -> bool: ...

    def publish_fixed_receipt_no_replace_write_through(
        self, source: str, destination: str
    ) -> bool: ...


class _DirectoryLease(Protocol):
    identities: tuple[str, ...]

    def validate(self) -> bool: ...

    def durable(self) -> DirectoryDurability: ...

    def close(self) -> bool: ...


class FixedBootstrapInstallParent:
    def __init__(self, lease: _DirectoryLease) -> None:
        self._lease = lease
        self.identity = lease.identities[-1] if lease.identities else ""

    def validate(self) -> bool:
        return bool(self.identity and self._lease.validate())

    def durable(self) -> bool:
        return self._lease.durable() is DirectoryDurability.VERIFIED

    def close(self) -> bool:
        return self._lease.close()


class FixedBootstrapInstallMutex:
    def __init__(self, ops: MutexOps) -> None:
        self._ops = ops
        self._attempted = False
        self._owned = False
        self._closed = False

    def acquire(self) -> bool:
        if self._attempted or self._closed:
            return False
        self._attempted = True
        status = self._ops.acquire(AUTHORITY_MUTEX_NAME)
        self._owned = status in {MutexStatus.ACQUIRED, MutexStatus.ABANDONED}
        return status is MutexStatus.ACQUIRED

    def release(self) -> bool:
        if not self._owned:
            return False
        try:
            released = self._ops.release()
        except BaseException:
            released = False
        if released:
            self._owned = False
        return released

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        release_clean = True
        if self._owned:
            release_clean = self.release()
        try:
            close_clean = self._ops.close()
        except BaseException:
            close_clean = False
        return release_clean and close_clean


@dataclass(frozen=True, slots=True)
class BootstrapInstallOutcome:
    result: ProvisioningResult
    receipt: ProvisioningReceiptV1 | None = None


@dataclass(frozen=True, slots=True)
class _ClosedReceiptCandidate:
    source: str
    destination: str
    receipt: ProvisioningReceiptV1


def parse_operator_authority(
    *,
    authority_revision: str,
    bootstrap_bundle_sha256: str,
    key_id: str,
    bootstrap_epoch_digest: str,
    one_shot: str,
    overwrite: str,
) -> BootstrapInstallAuthority | None:
    if (
        one_shot != "true"
        or overwrite != "false"
        or bootstrap_epoch_digest != BOOTSTRAP_EPOCH_DIGEST
    ):
        return None
    authority = BootstrapInstallAuthority(
        authority_revision=authority_revision,
        bootstrap_bundle_sha256=bootstrap_bundle_sha256,
        key_id=key_id,
        bootstrap_epoch_digest=bootstrap_epoch_digest,
        one_shot=True,
        overwrite=False,
    )
    if authority.authority_revision != BOOTSTRAP_AUTHORITY_REVISION:
        return None
    return authority


def create_production_bootstrap_installer() -> OneShotBootstrapInstaller | None:
    """Compose fixed Windows dependencies; caller still needs B0.4 authority."""

    try:
        known_paths = resolve_known_folder_authority_root()
        if known_paths is None:
            return None
        paths = BootstrapPaths.for_root(known_paths.authority)
        ops = CtypesBootstrapHandleOps()
        publisher = CtypesBootstrapPublisher(paths)

        def parent_factory() -> FixedBootstrapInstallParent:
            acquisition = DirectoryLease.acquire(CtypesDirectoryOps(), known_paths)
            if (
                acquisition.lease is None
                or acquisition.failure is not None
                or acquisition.cleanup_status is not DirectoryCleanupStatus.CLEAN
            ):
                raise RuntimeError("fixed authority directory unavailable")
            return FixedBootstrapInstallParent(acquisition.lease)

        return OneShotBootstrapInstaller(
            paths,
            ops,
            parent_factory,
            lambda: FixedBootstrapInstallMutex(CtypesMutexOps()),
            publisher,
            verify_ecdsa_p256_sha256_p1363,
            time.time_ns,
        )
    except BaseException:
        return None


def _normalize(path: str) -> str:
    return ntpath.normcase(ntpath.normpath(path.removeprefix("\\\\?\\")))


def _valid_info(
    info: HandleInfo,
    path: str,
    *,
    maximum: int,
    expected_size: int | None = None,
) -> bool:
    size_valid = (
        0 <= info.size <= maximum
        if expected_size is None
        else info.size == expected_size
    )
    return (
        info.disk
        and not info.reparse
        and not info.directory
        and not info.delete_pending
        and info.links == 1
        and bool(info.identity)
        and size_valid
        and _normalize(info.final_path) == _normalize(path)
    )


class OneShotBootstrapInstaller:
    """Installs only approved public bootstrap bytes into fixed leaves."""

    def __init__(
        self,
        paths: BootstrapPaths,
        ops: BootstrapInstallHandleOps,
        parent_factory: Callable[[], BootstrapInstallParent],
        mutex_factory: Callable[[], BootstrapInstallMutex],
        publisher: BootstrapPublisher,
        verify_signature: Callable[[bytes, bytes, bytes], bool],
        unix_clock_ns: Callable[[], int],
    ) -> None:
        self._paths = paths
        self._ops = ops
        self._parent_factory = parent_factory
        self._mutex_factory = mutex_factory
        self._publisher = publisher
        self._verify_signature = verify_signature
        self._unix_clock_ns = unix_clock_ns

    def install(
        self, payload: bytes, authority: BootstrapInstallAuthority
    ) -> BootstrapInstallOutcome:
        bundle = verify_approved_bootstrap_bundle(
            payload, authority, self._verify_signature
        )
        if bundle is None:
            return BootstrapInstallOutcome(ProvisioningResult.INVALID_INPUT)

        try:
            mutex = self._mutex_factory()
        except BaseException:
            return BootstrapInstallOutcome(ProvisioningResult.CLEANUP_FAILED)
        if not self._safe_bool(mutex.acquire):
            result = (
                ProvisioningResult.WRITE_FAILED
                if self._safe_bool(mutex.close)
                else ProvisioningResult.CLEANUP_FAILED
            )
            return BootstrapInstallOutcome(result)

        try:
            parent = self._parent_factory()
        except BaseException:
            clean = self._cleanup_mutex(mutex)
            return BootstrapInstallOutcome(
                ProvisioningResult.WRITE_FAILED
                if clean
                else ProvisioningResult.CLEANUP_FAILED
            )

        handles: list[int] = []
        if not self._safe_bool(parent.validate):
            return self._failure(
                ProvisioningResult.DURABILITY_FAILED, handles, parent, mutex
            )

        preflight = self._preflight_absence(handles)
        if preflight is not None:
            return self._failure(preflight, handles, parent, mutex)

        partial_create = self._safe_create(self._paths.partial)
        if (
            partial_create.state is not CreateOpenState.CREATED
            or partial_create.handle is None
        ):
            return self._failure(
                (
                    ProvisioningResult.ALREADY_EXISTS
                    if partial_create.state is CreateOpenState.EXISTS
                    else ProvisioningResult.WRITE_FAILED
                ),
                handles,
                parent,
                mutex,
            )
        partial_handle = partial_create.handle
        handles.append(partial_handle)
        write_result = self._write_exact(
            partial_handle,
            self._paths.partial,
            payload,
            maximum=_MAX_BOOTSTRAP_BYTES,
        )
        if write_result is not None:
            return self._failure(write_result, handles, parent, mutex)
        if not self._close_owned(handles, partial_handle):
            return self._failure(
                ProvisioningResult.CLEANUP_FAILED, handles, parent, mutex
            )
        if not self._safe_publish_bundle():
            return self._failure(
                ProvisioningResult.WRITE_FAILED, handles, parent, mutex
            )
        if not self._safe_bool(parent.durable):
            return self._failure(
                ProvisioningResult.DURABILITY_FAILED, handles, parent, mutex
            )

        final_open = self._safe_open(self._paths.bundle)
        if (
            final_open.state is not InspectionOpenState.OPENED
            or final_open.handle is None
        ):
            return self._failure(
                ProvisioningResult.READBACK_FAILED, handles, parent, mutex
            )
        final_bundle_handle = final_open.handle
        handles.append(final_bundle_handle)
        if not self._verify_final_bundle(final_bundle_handle, payload, authority):
            return self._failure(
                ProvisioningResult.READBACK_FAILED, handles, parent, mutex
            )

        receipt_create = self._safe_create(self._paths.partial)
        if (
            receipt_create.state is not CreateOpenState.CREATED
            or receipt_create.handle is None
        ):
            return self._failure(
                (
                    ProvisioningResult.ALREADY_EXISTS
                    if receipt_create.state is CreateOpenState.EXISTS
                    else ProvisioningResult.WRITE_FAILED
                ),
                handles,
                parent,
                mutex,
            )
        receipt_handle = receipt_create.handle
        handles.append(receipt_handle)
        try:
            receipt_info = self._ops.info(receipt_handle)
        except BaseException:
            return self._failure(
                ProvisioningResult.WRITE_FAILED, handles, parent, mutex
            )
        if not _valid_info(
            receipt_info,
            self._paths.partial,
            maximum=_MAX_RECEIPT_BYTES,
            expected_size=0,
        ):
            return self._failure(
                ProvisioningResult.WRITE_FAILED, handles, parent, mutex
            )
        try:
            installed_unix_ns = self._unix_clock_ns()
        except BaseException:
            return self._failure(
                ProvisioningResult.WRITE_FAILED, handles, parent, mutex
            )
        if type(installed_unix_ns) is not int or not 0 <= installed_unix_ns < 2**63:
            return self._failure(
                ProvisioningResult.WRITE_FAILED, handles, parent, mutex
            )
        try:
            receipt = self._installed_receipt(
                bundle,
                receipt_info.identity,
                parent.identity,
                installed_unix_ns,
            )
            receipt_bytes = receipt.canonical_bytes()
        except BaseException:
            return self._failure(
                ProvisioningResult.WRITE_FAILED, handles, parent, mutex
            )
        write_result = self._write_exact(
            receipt_handle,
            self._paths.partial,
            receipt_bytes,
            maximum=_MAX_RECEIPT_BYTES,
        )
        if write_result is not None:
            return self._failure(write_result, handles, parent, mutex)
        if not self._safe_bool(parent.durable):
            return self._failure(
                ProvisioningResult.DURABILITY_FAILED, handles, parent, mutex
            )

        if not self._close_all(handles):
            return self._failure(
                ProvisioningResult.CLEANUP_FAILED, handles, parent, mutex
            )
        if not self._safe_bool(parent.close):
            return self._failure_after_parent(
                ProvisioningResult.CLEANUP_FAILED, mutex
            )
        if not self._cleanup_mutex(mutex):
            return BootstrapInstallOutcome(ProvisioningResult.CLEANUP_FAILED)

        closed_candidate = _ClosedReceiptCandidate(
            self._paths.partial,
            self._paths.receipt,
            receipt,
        )
        if not self._safe_publish_receipt(closed_candidate):
            return BootstrapInstallOutcome(ProvisioningResult.WRITE_FAILED)
        return BootstrapInstallOutcome(
            ProvisioningResult.INSTALLED, closed_candidate.receipt
        )

    def _preflight_absence(self, handles: list[int]) -> ProvisioningResult | None:
        ambiguous = False
        existing = False
        for path in (
            self._paths.bundle,
            self._paths.receipt,
            self._paths.partial,
        ):
            opened = self._safe_open(path)
            if opened.state is InspectionOpenState.AMBIGUOUS:
                ambiguous = True
            elif opened.state is InspectionOpenState.OPENED:
                if opened.handle is None:
                    ambiguous = True
                else:
                    handles.append(opened.handle)
                    existing = True
        if ambiguous:
            return ProvisioningResult.WRITE_FAILED
        if existing:
            return ProvisioningResult.ALREADY_EXISTS
        return None

    def _write_exact(
        self,
        handle: int,
        path: str,
        payload: bytes,
        *,
        maximum: int,
    ) -> ProvisioningResult | None:
        try:
            initial = self._ops.info(handle)
            if not _valid_info(initial, path, maximum=maximum, expected_size=0):
                return ProvisioningResult.WRITE_FAILED
            offset = 0
            while offset < len(payload):
                written = self._ops.write(handle, payload[offset:])
                if written <= 0 or written > len(payload) - offset:
                    return ProvisioningResult.WRITE_FAILED
                offset += written
            if not self._ops.flush(handle):
                return ProvisioningResult.DURABILITY_FAILED
            if not self._ops.seek_start(handle):
                return ProvisioningResult.READBACK_FAILED
            if self._ops.read(handle, maximum + 1) != payload:
                return ProvisioningResult.READBACK_FAILED
            final = self._ops.info(handle)
            if (
                not _valid_info(
                    final, path, maximum=maximum, expected_size=len(payload)
                )
                or final.identity != initial.identity
            ):
                return ProvisioningResult.READBACK_FAILED
        except BaseException:
            return ProvisioningResult.WRITE_FAILED
        return None

    def _verify_final_bundle(
        self,
        handle: int,
        expected: bytes,
        authority: BootstrapInstallAuthority,
    ) -> bool:
        try:
            info = self._ops.info(handle)
            if not _valid_info(
                info,
                self._paths.bundle,
                maximum=_MAX_BOOTSTRAP_BYTES,
                expected_size=len(expected),
            ):
                return False
            payload = self._ops.read(handle, _MAX_BOOTSTRAP_BYTES + 1)
            return (
                payload == expected
                and verify_approved_bootstrap_bundle(
                    payload, authority, self._verify_signature
                )
                is not None
            )
        except BaseException:
            return False

    def _installed_receipt(
        self,
        bundle: ParsedBootstrapBundle,
        receipt_identity: str,
        parent_identity: str,
        installed_unix_ns: int,
    ) -> ProvisioningReceiptV1:
        return ProvisioningReceiptV1(
            result=ProvisioningResult.INSTALLED,
            installed_unix_ns=installed_unix_ns,
            bootstrap_bundle_sha256=hashlib.sha256(bundle.canonical_bytes).hexdigest(),
            key_id=bundle.key_id,
            bootstrap_epoch_digest=bundle.bootstrap_epoch_digest,
            create_new=True,
            no_reparse=True,
            share_zero=True,
            write_flushed=True,
            parent_durable=True,
            promoted_no_replace=True,
            readback_verified=True,
            leaf_identity_digest=identity_digest(receipt_identity),
            parent_identity_digest=identity_digest(parent_identity),
            cleanup_clean=True,
        )

    def _failure(
        self,
        primary: ProvisioningResult,
        handles: list[int],
        parent: BootstrapInstallParent,
        mutex: BootstrapInstallMutex,
    ) -> BootstrapInstallOutcome:
        clean = self._close_all(handles)
        clean = self._safe_bool(parent.close) and clean
        clean = self._cleanup_mutex(mutex) and clean
        return BootstrapInstallOutcome(
            primary if clean else ProvisioningResult.CLEANUP_FAILED
        )

    def _failure_after_parent(
        self, primary: ProvisioningResult, mutex: BootstrapInstallMutex
    ) -> BootstrapInstallOutcome:
        clean = self._cleanup_mutex(mutex)
        return BootstrapInstallOutcome(
            primary if clean else ProvisioningResult.CLEANUP_FAILED
        )

    def _close_owned(self, handles: list[int], handle: int) -> bool:
        try:
            clean = self._ops.close(handle)
        except BaseException:
            clean = False
        handles.remove(handle)
        return clean

    def _close_all(self, handles: list[int]) -> bool:
        clean = True
        while handles:
            handle = handles.pop()
            try:
                clean = self._ops.close(handle) and clean
            except BaseException:
                clean = False
        return clean

    def _cleanup_mutex(self, mutex: BootstrapInstallMutex) -> bool:
        clean = self._safe_bool(mutex.release)
        return self._safe_bool(mutex.close) and clean

    def _safe_open(self, path: str) -> InspectionOpen:
        try:
            return self._ops.open_inspection_tagged(path)
        except BaseException:
            return InspectionOpen(InspectionOpenState.AMBIGUOUS)

    def _safe_create(self, path: str) -> CreateOpen:
        try:
            return self._ops.create_new_tagged(path)
        except BaseException:
            return CreateOpen(CreateOpenState.AMBIGUOUS)

    def _safe_publish_bundle(self) -> bool:
        try:
            return self._publisher.promote_bundle_no_replace_write_through(
                self._paths.partial, self._paths.bundle
            )
        except BaseException:
            return False

    def _safe_publish_receipt(self, candidate: _ClosedReceiptCandidate) -> bool:
        try:
            return self._publisher.publish_fixed_receipt_no_replace_write_through(
                candidate.source, candidate.destination
            )
        except BaseException:
            return False

    @staticmethod
    def _safe_bool(operation: Callable[[], bool]) -> bool:
        try:
            return operation() is True
        except BaseException:
            return False


__all__ = [
    "BootstrapInstallOutcome",
    "FixedBootstrapInstallMutex",
    "FixedBootstrapInstallParent",
    "OneShotBootstrapInstaller",
    "create_production_bootstrap_installer",
    "parse_operator_authority",
]
