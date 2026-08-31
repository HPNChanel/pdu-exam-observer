"""Fixed-leaf Windows bootstrap and A0 readers for D1-N2."""

from __future__ import annotations

import ctypes
import hashlib
import ntpath
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, cast

from pdu_exam_observer.m2_d1_n2_a0 import BootstrapStatus
from pdu_exam_observer.m2_d1_n2_bootstrap import (
    BOOTSTRAP_AUTHORITY_REVISION,
    BootstrapInstallAuthority,
    ParsedBootstrapBundle,
    ProvisioningReceiptV1,
    ProvisioningResult,
    parse_provisioning_receipt,
    verify_approved_bootstrap_bundle,
)
from pdu_exam_observer.m2_d1_n2_win32 import CtypesHandleOps, HandleInfo

BOOTSTRAP_LEAF = "a0-bootstrap.v1.json"
BOOTSTRAP_RECEIPT_LEAF = "a0-bootstrap-provisioning-receipt.v1.json"
BOOTSTRAP_PARTIAL_LEAF = "a0-bootstrap.v1.partial"
A0_APPROVAL_LEAF = "a0-approval.v1.json"
_MAX_BOOTSTRAP_BYTES = 16_384
_MAX_RECEIPT_BYTES = 16_384
_MAX_A0_APPROVAL_BYTES = 32_768
_IDENTITY_DOMAIN = b"D1N2/BOOTSTRAP_IDENTITY/v1\x00"
_MOVEFILE_WRITE_THROUGH = 0x00000008
_ERROR_FILE_EXISTS = 80
_ERROR_ALREADY_EXISTS = 183


class BootstrapState(StrEnum):
    ABSENT = "ABSENT"
    INSTALLED = "INSTALLED"
    POISONED = "POISONED"


class InspectionOpenState(StrEnum):
    OPENED = "OPENED"
    ABSENT = "ABSENT"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class InspectionOpen:
    state: InspectionOpenState
    handle: int | None = None


class CreateOpenState(StrEnum):
    CREATED = "CREATED"
    EXISTS = "EXISTS"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class CreateOpen:
    state: CreateOpenState
    handle: int | None = None


@dataclass(frozen=True, slots=True)
class BootstrapPaths:
    root: str
    bundle: str
    receipt: str
    partial: str
    approval: str

    @classmethod
    def for_root(cls, root: str) -> BootstrapPaths:
        return cls(
            root=root,
            bundle=ntpath.join(root, BOOTSTRAP_LEAF),
            receipt=ntpath.join(root, BOOTSTRAP_RECEIPT_LEAF),
            partial=ntpath.join(root, BOOTSTRAP_PARTIAL_LEAF),
            approval=ntpath.join(root, A0_APPROVAL_LEAF),
        )


class BootstrapHandleOps(Protocol):
    def open_inspection_tagged(self, path: str) -> InspectionOpen: ...

    def info(self, handle: int) -> HandleInfo: ...

    def read(self, handle: int, limit: int) -> bytes | None: ...

    def seek_start(self, handle: int) -> bool: ...

    def close(self, handle: int) -> bool: ...


class CtypesBootstrapHandleOps(CtypesHandleOps):
    """Production adapter that preserves absent versus ambiguous open state."""

    def open_inspection_tagged(self, path: str) -> InspectionOpen:
        try:
            handle = super().open_inspection(path)
        except BaseException:
            return InspectionOpen(InspectionOpenState.AMBIGUOUS)
        if handle is None:
            return InspectionOpen(InspectionOpenState.ABSENT)
        return InspectionOpen(InspectionOpenState.OPENED, handle)

    def create_new_tagged(self, path: str) -> CreateOpen:
        try:
            handle = super().create_new(path)
        except BaseException:
            return CreateOpen(CreateOpenState.AMBIGUOUS)
        if handle is not None:
            return CreateOpen(CreateOpenState.CREATED, handle)
        if ctypes.get_last_error() in {_ERROR_FILE_EXISTS, _ERROR_ALREADY_EXISTS}:
            return CreateOpen(CreateOpenState.EXISTS)
        return CreateOpen(CreateOpenState.AMBIGUOUS)


class CtypesBootstrapPublisher:
    """Fixed no-replace MoveFileExW publisher with no owned cleanup state."""

    def __init__(self, paths: BootstrapPaths, kernel32: object | None = None) -> None:
        self._paths = paths
        api = cast(Any, kernel32 or ctypes.WinDLL("kernel32", use_last_error=True))
        api.MoveFileExW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
        ]
        api.MoveFileExW.restype = ctypes.c_int32
        self._api = api

    def promote_bundle_no_replace_write_through(
        self, source: str, destination: str
    ) -> bool:
        return self._move_fixed(source, destination, self._paths.bundle)

    def publish_fixed_receipt_no_replace_write_through(
        self, source: str, destination: str
    ) -> bool:
        return self._move_fixed(source, destination, self._paths.receipt)

    def _move_fixed(self, source: str, destination: str, expected: str) -> bool:
        if (
            _normalize(source) != _normalize(self._paths.partial)
            or _normalize(destination) != _normalize(expected)
            or _normalize(ntpath.dirname(source))
            != _normalize(ntpath.dirname(destination))
        ):
            return False
        try:
            return bool(
                self._api.MoveFileExW(source, destination, _MOVEFILE_WRITE_THROUGH)
            )
        except BaseException:
            return False


class BootstrapParentLease(Protocol):
    identity: str

    def validate(self) -> bool: ...

    def durable(self) -> bool: ...

    def close(self) -> bool: ...


def identity_digest(identity: str) -> str:
    return hashlib.sha256(_IDENTITY_DOMAIN + identity.encode("utf-8")).hexdigest()


def _normalize(path: str) -> str:
    return ntpath.normcase(ntpath.normpath(path.removeprefix("\\\\?\\")))


def _valid_info(info: HandleInfo, expected_path: str, limit: int) -> bool:
    return (
        info.disk
        and not info.reparse
        and not info.directory
        and not info.delete_pending
        and info.links == 1
        and bool(info.identity)
        and 0 < info.size <= limit
        and _normalize(info.final_path) == _normalize(expected_path)
    )


@dataclass(slots=True)
class FixedBootstrapLease:
    ops: BootstrapHandleOps
    parent: BootstrapParentLease
    handles: tuple[int, int]
    paths: tuple[str, str]
    infos: tuple[HandleInfo, HandleInfo]
    payloads: tuple[bytes, bytes]
    _closed: bool = field(default=False, init=False)

    def validate(self) -> bool:
        if self._closed or not self.parent.validate() or not self.parent.durable():
            return False
        try:
            for handle, path, expected, payload in zip(
                self.handles,
                self.paths,
                self.infos,
                self.payloads,
                strict=True,
            ):
                info = self.ops.info(handle)
                if (
                    not _valid_info(info, path, max(len(payload), 1))
                    or info.identity != expected.identity
                    or info.size != len(payload)
                    or not self.ops.seek_start(handle)
                    or self.ops.read(handle, len(payload) + 1) != payload
                ):
                    return False
            return True
        except BaseException:
            return False

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        clean = True
        for handle in reversed(self.handles):
            try:
                clean = self.ops.close(handle) and clean
            except BaseException:
                clean = False
        try:
            clean = self.parent.close() and clean
        except BaseException:
            clean = False
        return clean


@dataclass(frozen=True, slots=True)
class BootstrapInspection:
    state: BootstrapState
    bundle: ParsedBootstrapBundle | None = None
    receipt: ProvisioningReceiptV1 | None = None
    lease: FixedBootstrapLease | None = None


class FixedBootstrapReader:
    def __init__(
        self,
        paths: BootstrapPaths,
        ops: BootstrapHandleOps,
        parent: BootstrapParentLease,
        verify_signature: Callable[[bytes, bytes, bytes], bool],
    ) -> None:
        self._paths = paths
        self._ops = ops
        self._parent = parent
        self._verify_signature = verify_signature

    def _close_parent_once(self) -> bool:
        try:
            return self._parent.close()
        except BaseException:
            return False

    def _close_failure(self, handles: list[int]) -> BootstrapInspection:
        for handle in reversed(handles):
            try:
                self._ops.close(handle)
            except BaseException:
                pass
        self._close_parent_once()
        return BootstrapInspection(BootstrapState.POISONED)

    def inspect(self) -> BootstrapInspection:
        handles: list[int] = []
        try:
            if not self._parent.validate() or not self._parent.durable():
                return self._close_failure(handles)
            partial = self._ops.open_inspection_tagged(self._paths.partial)
            if partial.state is not InspectionOpenState.ABSENT:
                if (
                    partial.state is InspectionOpenState.OPENED
                    and partial.handle is not None
                ):
                    handles.append(partial.handle)
                return self._close_failure(handles)
            bundle_open = self._ops.open_inspection_tagged(self._paths.bundle)
            receipt_open = self._ops.open_inspection_tagged(self._paths.receipt)
            for result in (bundle_open, receipt_open):
                if (
                    result.state is InspectionOpenState.OPENED
                    and result.handle is not None
                ):
                    handles.append(result.handle)
            if (
                bundle_open.state is InspectionOpenState.AMBIGUOUS
                or receipt_open.state is InspectionOpenState.AMBIGUOUS
            ):
                return self._close_failure(handles)
            if (
                bundle_open.state is InspectionOpenState.ABSENT
                and receipt_open.state is InspectionOpenState.ABSENT
            ):
                clean = self._close_parent_once()
                return BootstrapInspection(
                    BootstrapState.ABSENT if clean else BootstrapState.POISONED
                )
            if (
                bundle_open.state is not InspectionOpenState.OPENED
                or receipt_open.state is not InspectionOpenState.OPENED
                or bundle_open.handle is None
                or receipt_open.handle is None
            ):
                return self._close_failure(handles)
            bundle_handle = bundle_open.handle
            receipt_handle = receipt_open.handle
            bundle_info = self._ops.info(bundle_handle)
            receipt_info = self._ops.info(receipt_handle)
            if not _valid_info(
                bundle_info, self._paths.bundle, _MAX_BOOTSTRAP_BYTES
            ) or not _valid_info(
                receipt_info, self._paths.receipt, _MAX_RECEIPT_BYTES
            ):
                return self._close_failure(handles)
            bundle_bytes = self._ops.read(bundle_handle, _MAX_BOOTSTRAP_BYTES + 1)
            receipt_bytes = self._ops.read(receipt_handle, _MAX_RECEIPT_BYTES + 1)
            if (
                bundle_bytes is None
                or receipt_bytes is None
                or len(bundle_bytes) != bundle_info.size
                or len(receipt_bytes) != receipt_info.size
            ):
                return self._close_failure(handles)
            receipt = parse_provisioning_receipt(receipt_bytes)
            if (
                receipt is None
                or receipt.result is not ProvisioningResult.INSTALLED
                or receipt.leaf_identity_digest
                != identity_digest(receipt_info.identity)
                or receipt.parent_identity_digest
                != identity_digest(self._parent.identity)
            ):
                return self._close_failure(handles)
            authority = BootstrapInstallAuthority(
                authority_revision=BOOTSTRAP_AUTHORITY_REVISION,
                bootstrap_bundle_sha256=receipt.bootstrap_bundle_sha256,
                key_id=receipt.key_id,
                bootstrap_epoch_digest=receipt.bootstrap_epoch_digest,
                one_shot=True,
                overwrite=False,
            )
            bundle = verify_approved_bootstrap_bundle(
                bundle_bytes, authority, self._verify_signature
            )
            if bundle is None:
                return self._close_failure(handles)
            lease = FixedBootstrapLease(
                self._ops,
                self._parent,
                (bundle_handle, receipt_handle),
                (self._paths.bundle, self._paths.receipt),
                (bundle_info, receipt_info),
                (bundle_bytes, receipt_bytes),
            )
            handles.clear()
            return BootstrapInspection(BootstrapState.INSTALLED, bundle, receipt, lease)
        except BaseException:
            return self._close_failure(handles)


@dataclass(slots=True)
class FixedA0ApprovalLease:
    ops: BootstrapHandleOps
    parent: BootstrapParentLease
    handle: int
    path: str
    info: HandleInfo
    payload: bytes
    _closed: bool = field(default=False, init=False)

    def read_exact(self) -> bytes:
        if self._closed:
            raise RuntimeError("A0 approval lease is closed")
        return self.payload

    def validate(self) -> bool:
        if self._closed or not self.parent.validate():
            return False
        try:
            current = self.ops.info(self.handle)
            return (
                _valid_info(current, self.path, _MAX_A0_APPROVAL_BYTES)
                and current.identity == self.info.identity
                and current.size == len(self.payload)
                and self.ops.seek_start(self.handle)
                and self.ops.read(self.handle, len(self.payload) + 1) == self.payload
            )
        except BaseException:
            return False

    def parent_durable(self) -> bool:
        try:
            return self.validate() and self.parent.durable() and self.validate()
        except BaseException:
            return False

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        try:
            leaf_clean = self.ops.close(self.handle)
        except BaseException:
            leaf_clean = False
        try:
            parent_clean = self.parent.close()
        except BaseException:
            parent_clean = False
        return leaf_clean and parent_clean


class FixedA0ApprovalSource:
    def __init__(
        self,
        paths: BootstrapPaths,
        ops: BootstrapHandleOps,
        parent_factory: Callable[[], BootstrapParentLease],
    ) -> None:
        self._paths = paths
        self._ops = ops
        self._parent_factory = parent_factory

    def open_fixed(self) -> FixedA0ApprovalLease:
        parent = self._parent_factory()
        handle: int | None = None
        try:
            if not parent.validate() or not parent.durable():
                raise RuntimeError("A0 approval parent is unavailable")
            opened = self._ops.open_inspection_tagged(self._paths.approval)
            if (
                opened.state is not InspectionOpenState.OPENED
                or opened.handle is None
            ):
                raise RuntimeError("A0 approval is unavailable")
            handle = opened.handle
            info = self._ops.info(handle)
            if not _valid_info(info, self._paths.approval, _MAX_A0_APPROVAL_BYTES):
                raise RuntimeError("A0 approval is invalid")
            payload = self._ops.read(handle, _MAX_A0_APPROVAL_BYTES + 1)
            if payload is None or len(payload) != info.size:
                raise RuntimeError("A0 approval read failed")
            return FixedA0ApprovalLease(
                self._ops,
                parent,
                handle,
                self._paths.approval,
                info,
                payload,
            )
        except BaseException as primary:
            clean = True
            if handle is not None:
                try:
                    clean = self._ops.close(handle) and clean
                except BaseException:
                    clean = False
            try:
                clean = parent.close() and clean
            except BaseException:
                clean = False
            if not clean:
                raise BaseExceptionGroup(
                    "A0 approval open failed with cleanup ambiguity",
                    [primary, RuntimeError("A0 approval cleanup failed")],
                ) from primary
            raise


class LazyFixedA0ApprovalSource:
    def __init__(
        self, factory: Callable[[], FixedA0ApprovalSource | None]
    ) -> None:
        self._factory = factory

    def open_fixed(self) -> FixedA0ApprovalLease:
        try:
            source = self._factory()
        except BaseException as error:
            raise RuntimeError("fixed A0 source is unavailable") from error
        if source is None:
            raise RuntimeError("fixed A0 source is unavailable")
        return source.open_fixed()


class WindowsProvisionedA0Bootstrap:
    """Retained fixed bootstrap pair; it has verification powers only."""

    def __init__(
        self,
        reader: FixedBootstrapReader,
        verify_signature: Callable[[bytes, bytes, bytes], bool],
    ) -> None:
        self._reader = reader
        self._verify_signature = verify_signature
        self._inspection: BootstrapInspection | None = None
        self._closed = False

    def inspect(self) -> BootstrapStatus:
        if self._closed:
            return BootstrapStatus.REJECTED
        if self._inspection is None:
            self._inspection = self._reader.inspect()
        if self._inspection.state is BootstrapState.ABSENT:
            return BootstrapStatus.UNPROVISIONED
        if (
            self._inspection.state is BootstrapState.INSTALLED
            and self._inspection.bundle is not None
            and self._inspection.receipt is not None
            and self._inspection.lease is not None
            and self._inspection.lease.validate()
        ):
            return BootstrapStatus.VERIFIED
        return BootstrapStatus.REJECTED

    def verify(
        self,
        canonical_body: bytes,
        key_id: str,
        signature: bytes,
    ) -> BootstrapStatus:
        inspection = self._inspection
        if (
            self.inspect() is not BootstrapStatus.VERIFIED
            or inspection is None
            or inspection.bundle is None
            or inspection.lease is None
            or key_id != inspection.bundle.key_id
            or not inspection.lease.validate()
        ):
            return BootstrapStatus.REJECTED
        try:
            verified = self._verify_signature(
                inspection.bundle.public_key_blob,
                canonical_body,
                signature,
            )
        except BaseException:
            verified = False
        return (
            BootstrapStatus.VERIFIED
            if verified is True and inspection.lease.validate()
            else BootstrapStatus.REJECTED
        )

    def validate(self) -> bool:
        inspection = self._inspection
        return (
            not self._closed
            and inspection is not None
            and inspection.state is BootstrapState.INSTALLED
            and inspection.lease is not None
            and inspection.lease.validate()
        )

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        inspection = self._inspection
        if inspection is None or inspection.lease is None:
            return True
        return inspection.lease.close()


class LazyWindowsProvisionedA0Bootstrap:
    """Constructor-inert production bootstrap that attempts composition once."""

    def __init__(
        self,
        reader_factory: Callable[[], FixedBootstrapReader | None],
        verify_signature: Callable[[bytes, bytes, bytes], bool],
    ) -> None:
        self._reader_factory = reader_factory
        self._verify_signature = verify_signature
        self._attempted = False
        self._delegate: WindowsProvisionedA0Bootstrap | None = None
        self._closed = False

    def inspect(self) -> BootstrapStatus:
        if self._closed:
            return BootstrapStatus.REJECTED
        if not self._attempted:
            self._attempted = True
            try:
                reader = self._reader_factory()
            except BaseException:
                reader = None
            if reader is not None:
                self._delegate = WindowsProvisionedA0Bootstrap(
                    reader, self._verify_signature
                )
        return (
            self._delegate.inspect()
            if self._delegate is not None
            else BootstrapStatus.REJECTED
        )

    def verify(
        self,
        canonical_body: bytes,
        key_id: str,
        signature: bytes,
    ) -> BootstrapStatus:
        if self.inspect() is not BootstrapStatus.VERIFIED or self._delegate is None:
            return BootstrapStatus.REJECTED
        return self._delegate.verify(canonical_body, key_id, signature)

    def validate(self) -> bool:
        return (
            not self._closed
            and self._delegate is not None
            and self._delegate.validate()
        )

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        return self._delegate.close() if self._delegate is not None else True


__all__ = [
    "A0_APPROVAL_LEAF",
    "BOOTSTRAP_LEAF",
    "BOOTSTRAP_PARTIAL_LEAF",
    "BOOTSTRAP_RECEIPT_LEAF",
    "BootstrapInspection",
    "BootstrapPaths",
    "BootstrapState",
    "CtypesBootstrapHandleOps",
    "CtypesBootstrapPublisher",
    "CreateOpen",
    "CreateOpenState",
    "FixedBootstrapLease",
    "FixedBootstrapReader",
    "InspectionOpen",
    "InspectionOpenState",
    "LazyFixedA0ApprovalSource",
    "LazyWindowsProvisionedA0Bootstrap",
    "FixedA0ApprovalLease",
    "FixedA0ApprovalSource",
    "WindowsProvisionedA0Bootstrap",
    "identity_digest",
]
