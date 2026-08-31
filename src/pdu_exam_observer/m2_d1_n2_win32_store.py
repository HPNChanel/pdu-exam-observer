"""Fixed Win32 directory and mutex primitives; no authority-state wiring."""

from __future__ import annotations

import ctypes
import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Never, Protocol

AUTHORITY_MUTEX_NAME = r"Local\PDUExamObserver.D1N2.AuthorityV1"
APPLICATION_DIRECTORY_LEAF = "PDUExamObserver"
AUTHORITY_DIRECTORY_LEAF = "d1-n2-authority-v1"

_WAIT_OBJECT_0 = 0
_WAIT_ABANDONED_0 = 0x80
_WAIT_TIMEOUT = 0x102
_FILE_TYPE_DISK = 1
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_GENERIC_WRITE = 0x40000000
_FILE_READ_ATTRIBUTES = 0x00000080
_SYNCHRONIZE = 0x00100000
_FILE_SHARE_READ = 0x1
_FILE_SHARE_WRITE = 0x2
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_STANDARD_INFO_CLASS = 1
_FILE_ID_INFO_CLASS = 18


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


FOLDERID_LOCAL_APP_DATA_GUID = _Guid(
    0xF1B32785,
    0x6FBA,
    0x4FCF,
    (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
)


class _FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [
        ("file_attributes", ctypes.c_uint32),
        ("reparse_tag", ctypes.c_uint32),
    ]


class _FileStandardInfo(ctypes.Structure):
    _fields_ = [
        ("allocation_size", ctypes.c_longlong),
        ("end_of_file", ctypes.c_longlong),
        ("number_of_links", ctypes.c_uint32),
        ("delete_pending", ctypes.c_ubyte),
        ("directory", ctypes.c_ubyte),
    ]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [
        ("volume_serial_number", ctypes.c_ulonglong),
        ("file_id", ctypes.c_ubyte * 16),
    ]


class MutexStatus(StrEnum):
    ACQUIRED = "ACQUIRED"
    ABANDONED = "ABANDONED"
    UNAVAILABLE = "UNAVAILABLE"


class DirectoryDurability(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class DirectoryCleanupStatus(StrEnum):
    CLEAN = "CLEAN"
    CLEANUP_FAILED = "CLEANUP_FAILED"


class DirectoryAcquireFailure(StrEnum):
    OPEN_FAILED = "OPEN_FAILED"
    CREATE_FAILED = "CREATE_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    OPERATION_FAILED = "OPERATION_FAILED"


class CleanupFailure(RuntimeError):
    """Sanitized ownership-cleanup failure."""


@dataclass(frozen=True, slots=True)
class KnownFolderAuthorityPaths:
    base: str
    application: str
    authority: str


class MutexOps(Protocol):
    def acquire(self, name: str) -> MutexStatus: ...
    def release(self) -> bool: ...
    def close(self) -> bool: ...


class CtypesMutexOps:
    """Pointer-safe named-mutex adapter. Construction does not create a mutex."""

    def __init__(self, kernel32: object | None = None, timeout_ms: int = 10_000) -> None:
        self._api: Any = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        self._timeout_ms = timeout_ms
        self._handle: int | None = None
        self._owned = False
        specs = {
            "CreateMutexW": (
                [ctypes.c_void_p, ctypes.c_int32, ctypes.c_wchar_p],
                ctypes.c_void_p,
            ),
            "WaitForSingleObject": (
                [ctypes.c_void_p, ctypes.c_uint32],
                ctypes.c_uint32,
            ),
            "ReleaseMutex": ([ctypes.c_void_p], ctypes.c_int32),
            "CloseHandle": ([ctypes.c_void_p], ctypes.c_int32),
        }
        for name, (arguments, result) in specs.items():
            function = getattr(self._api, name)
            function.argtypes = arguments
            function.restype = result

    def acquire(self, name: str) -> MutexStatus:
        if self._handle is not None:
            return MutexStatus.UNAVAILABLE
        try:
            raw = self._api.CreateMutexW(None, 0, name)
            value = raw.value if isinstance(raw, ctypes.c_void_p) else raw
            if not isinstance(value, int) or value == 0:
                return MutexStatus.UNAVAILABLE
            self._handle = value
            wait = int(self._api.WaitForSingleObject(value, self._timeout_ms))
            if wait == _WAIT_OBJECT_0:
                self._owned = True
                return MutexStatus.ACQUIRED
            if wait == _WAIT_ABANDONED_0:
                self._owned = True
                return MutexStatus.ABANDONED
            return MutexStatus.UNAVAILABLE
        except Exception:
            return MutexStatus.UNAVAILABLE

    def release(self) -> bool:
        if self._handle is None or not self._owned:
            return False
        try:
            released = bool(self._api.ReleaseMutex(self._handle))
        except Exception:
            released = False
        if released:
            self._owned = False
        return released

    def close(self) -> bool:
        if self._handle is None:
            return True
        handle, self._handle = self._handle, None
        self._owned = False
        try:
            return bool(self._api.CloseHandle(handle))
        except Exception:
            return False


class WindowsNamedMutex:
    def __init__(self, ops: MutexOps, name: str = AUTHORITY_MUTEX_NAME) -> None:
        self._ops, self._name, self._closed = ops, name, False
        self.status = MutexStatus.UNAVAILABLE
        self._attempted = False
        self._owned = False

    def acquire(self) -> MutexStatus:
        if self._closed:
            return MutexStatus.UNAVAILABLE
        if self._attempted:
            return self.status
        self._attempted = True
        self.status = self._ops.acquire(self._name)
        self._owned = self.status in {MutexStatus.ACQUIRED, MutexStatus.ABANDONED}
        return self.status

    @property
    def mutation_permitted(self) -> bool:
        return self.status is MutexStatus.ACQUIRED

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        release_ok = True
        if self._owned:
            try:
                release_ok = self._ops.release()
            except BaseException:
                release_ok = False
        try:
            close_ok = self._ops.close()
        except BaseException:
            close_ok = False
        self._owned = False
        return release_ok and close_ok

    def __enter__(self) -> WindowsNamedMutex:
        return self

    def __exit__(
        self,
        _error_type: type[BaseException] | None,
        error: BaseException | None,
        _traceback: object,
    ) -> Literal[False]:
        if self.close():
            return False
        _raise_cleanup(error)


class DirectoryOps(Protocol):
    def open_existing(self, path: str) -> object | None: ...
    def create_child(self, parent: object, name: str) -> bool: ...
    def info(self, handle: object) -> DirectoryInfo: ...
    def flush_directory(self, handle: object) -> bool: ...
    def close(self, handle: object) -> bool: ...


@dataclass(frozen=True, slots=True)
class DirectoryInfo:
    disk: bool
    reparse: bool
    directory: bool
    final_path: str
    identity: str


@dataclass(frozen=True, slots=True)
class DirectoryLeaseAcquisition:
    lease: DirectoryLease | None
    failure: DirectoryAcquireFailure | None
    cleanup_status: DirectoryCleanupStatus


@dataclass(slots=True)
class DirectoryLease:
    ops: DirectoryOps
    handles: tuple[object, ...]
    paths: tuple[str, ...]
    identities: tuple[str, ...]
    _closed: bool = field(default=False, init=False)

    @classmethod
    def acquire(
        cls, ops: DirectoryOps, paths: KnownFolderAuthorityPaths
    ) -> DirectoryLeaseAcquisition:
        expected_paths = (paths.base, paths.application, paths.authority)
        handles: list[object] = []
        identities: list[str] = []
        primary: DirectoryAcquireFailure | None = None
        escaped: BaseException | None = None
        try:
            for index, path in enumerate(expected_paths):
                handle = ops.open_existing(path)
                if handle is None and index > 0:
                    if not ops.create_child(handles[index - 1], Path(path).name):
                        primary = DirectoryAcquireFailure.CREATE_FAILED
                        break
                    handle = ops.open_existing(path)
                if handle is None:
                    primary = DirectoryAcquireFailure.OPEN_FAILED
                    break
                handles.append(handle)
                info = ops.info(handle)
                if not cls._valid(info, path):
                    primary = DirectoryAcquireFailure.VALIDATION_FAILED
                    break
                identities.append(info.identity)
        except Exception:
            primary = DirectoryAcquireFailure.OPERATION_FAILED
        except BaseException as error:
            escaped = error
        if primary is None and escaped is None and len(handles) == len(expected_paths):
            return DirectoryLeaseAcquisition(
                cls(
                    ops,
                    tuple(handles),
                    expected_paths,
                    tuple(identities),
                ),
                None,
                DirectoryCleanupStatus.CLEAN,
            )
        cleanup_ok = cls._close_all(ops, handles)
        if escaped is not None:
            if not cleanup_ok:
                _raise_cleanup(escaped)
            raise escaped
        return DirectoryLeaseAcquisition(
            None,
            primary or DirectoryAcquireFailure.OPERATION_FAILED,
            (
                DirectoryCleanupStatus.CLEAN
                if cleanup_ok
                else DirectoryCleanupStatus.CLEANUP_FAILED
            ),
        )

    @staticmethod
    def _valid(info: DirectoryInfo, path: str) -> bool:
        return (
            info.disk
            and not info.reparse
            and info.directory
            and bool(info.identity)
            and _normalize(info.final_path) == _normalize(path)
        )

    @staticmethod
    def _close_all(ops: DirectoryOps, handles: list[object]) -> bool:
        result = True
        for handle in reversed(handles):
            try:
                result = ops.close(handle) and result
            except BaseException:
                result = False
        return result

    def validate(self) -> bool:
        if self._closed:
            return False
        try:
            for handle, path, identity in zip(
                self.handles, self.paths, self.identities, strict=True
            ):
                info = self.ops.info(handle)
                if not self._valid(info, path) or info.identity != identity:
                    return False
            return True
        except Exception:
            return False

    def durable(self) -> DirectoryDurability:
        if not self.validate():
            return DirectoryDurability.UNVERIFIED
        try:
            flushed = self.ops.flush_directory(self.handles[-1])
        except Exception:
            flushed = False
        if not flushed or not self.validate():
            return DirectoryDurability.UNVERIFIED
        return DirectoryDurability.VERIFIED

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        return self._close_all(self.ops, list(self.handles))

    def __enter__(self) -> DirectoryLease:
        return self

    def __exit__(
        self,
        _error_type: type[BaseException] | None,
        error: BaseException | None,
        _traceback: object,
    ) -> Literal[False]:
        if self.close():
            return False
        _raise_cleanup(error)


class CtypesDirectoryOps:
    """Win32 directory adapter; callers provide only fixed, precomputed tiers."""

    def __init__(self, kernel32: object | None = None) -> None:
        self._api: Any = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        specs = {
            "CreateFileW": (
                [
                    ctypes.c_wchar_p,
                    ctypes.c_uint32,
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                ],
                ctypes.c_void_p,
            ),
            "CreateDirectoryW": (
                [ctypes.c_wchar_p, ctypes.c_void_p],
                ctypes.c_int32,
            ),
            "GetFileType": ([ctypes.c_void_p], ctypes.c_uint32),
            "GetFileInformationByHandleEx": (
                [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32],
                ctypes.c_int32,
            ),
            "GetFinalPathNameByHandleW": (
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_wchar),
                    ctypes.c_uint32,
                    ctypes.c_uint32,
                ],
                ctypes.c_uint32,
            ),
            "FlushFileBuffers": ([ctypes.c_void_p], ctypes.c_int32),
            "CloseHandle": ([ctypes.c_void_p], ctypes.c_int32),
        }
        for name, (arguments, result) in specs.items():
            function = getattr(self._api, name)
            function.argtypes = arguments
            function.restype = result

    def open_existing(self, path: str) -> object | None:
        access = _FILE_READ_ATTRIBUTES | _SYNCHRONIZE
        share = _FILE_SHARE_READ | _FILE_SHARE_WRITE
        flags = _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT
        raw = self._api.CreateFileW(
            path, access, share, None, _OPEN_EXISTING, flags, None
        )
        value = raw.value if isinstance(raw, ctypes.c_void_p) else raw
        if not isinstance(value, int) or value == ctypes.c_void_p(-1).value:
            return None
        return value

    def create_child(self, parent: object, name: str) -> bool:
        if not isinstance(parent, int) or not _safe_leaf(name):
            return False
        parent_info = self.info(parent)
        if (
            not parent_info.disk
            or not parent_info.directory
            or parent_info.reparse
            or not parent_info.identity
        ):
            return False
        child = str(Path(parent_info.final_path) / name)
        try:
            return bool(self._api.CreateDirectoryW(child, None))
        except Exception:
            return False

    def info(self, handle: object) -> DirectoryInfo:
        invalid = DirectoryInfo(False, True, False, "", "")
        if not isinstance(handle, int):
            return invalid
        try:
            if self._api.GetFileType(handle) != _FILE_TYPE_DISK:
                return invalid
            attributes = _FileAttributeTagInfo()
            standard = _FileStandardInfo()
            identity = _FileIdInfo()
            for info_class, value in (
                (_FILE_ATTRIBUTE_TAG_INFO_CLASS, attributes),
                (_FILE_STANDARD_INFO_CLASS, standard),
                (_FILE_ID_INFO_CLASS, identity),
            ):
                if not self._api.GetFileInformationByHandleEx(
                    handle, info_class, ctypes.byref(value), ctypes.sizeof(value)
                ):
                    return invalid
            buffer = ctypes.create_unicode_buffer(32_768)
            size = self._api.GetFinalPathNameByHandleW(
                handle, buffer, len(buffer), 0
            )
            if size == 0 or size >= len(buffer):
                return invalid
            raw_identity = (
                int(identity.volume_serial_number).to_bytes(8, "little")
                + bytes(identity.file_id)
            )
            return DirectoryInfo(
                disk=True,
                reparse=bool(
                    attributes.file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT
                ),
                directory=bool(standard.directory),
                final_path=buffer.value,
                identity=hashlib.sha256(raw_identity).hexdigest(),
            )
        except Exception:
            return invalid

    def flush_directory(self, handle: object) -> bool:
        if not isinstance(handle, int):
            return False
        source = self.info(handle)
        if not source.disk or source.reparse or not source.directory:
            return False
        access = _GENERIC_WRITE | _SYNCHRONIZE
        share = _FILE_SHARE_READ | _FILE_SHARE_WRITE
        flags = _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT
        durability_handle: int | None = None
        result = False
        close_ok = True
        try:
            raw = self._api.CreateFileW(
                source.final_path,
                access,
                share,
                None,
                _OPEN_EXISTING,
                flags,
                None,
            )
            value = raw.value if isinstance(raw, ctypes.c_void_p) else raw
            if not isinstance(value, int) or value == ctypes.c_void_p(-1).value:
                return False
            durability_handle = value
            durable_info = self.info(value)
            result = (
                durable_info.disk
                and not durable_info.reparse
                and durable_info.directory
                and bool(durable_info.identity)
                and durable_info.identity == source.identity
                and _normalize(durable_info.final_path)
                == _normalize(source.final_path)
                and bool(self._api.FlushFileBuffers(value))
            )
        except Exception:
            result = False
        finally:
            if durability_handle is not None:
                try:
                    close_ok = bool(self._api.CloseHandle(durability_handle))
                except BaseException:
                    close_ok = False
        return result and close_ok

    def close(self, handle: object) -> bool:
        if not isinstance(handle, int):
            return False
        try:
            return bool(self._api.CloseHandle(handle))
        except Exception:
            return False


def resolve_known_folder_authority_root(
    shell32: object | None = None,
    ole32: object | None = None,
) -> KnownFolderAuthorityPaths | None:
    """Resolve the exact production root without environment or CWD input."""

    shell: Any = shell32 or ctypes.WinDLL("shell32", use_last_error=True)
    allocator: Any = ole32 or ctypes.WinDLL("ole32", use_last_error=True)
    get_path = shell.SHGetKnownFolderPath
    free = allocator.CoTaskMemFree
    get_path.argtypes = [
        ctypes.POINTER(_Guid),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    get_path.restype = ctypes.c_int32
    free.argtypes = [ctypes.c_void_p]
    free.restype = None
    value = ctypes.c_wchar_p()
    try:
        result = get_path(
            ctypes.byref(FOLDERID_LOCAL_APP_DATA_GUID),
            0,
            None,
            ctypes.byref(value),
        )
        if result != 0 or not value.value:
            return None
        base = Path(value.value)
        application = base / APPLICATION_DIRECTORY_LEAF
        authority = application / AUTHORITY_DIRECTORY_LEAF
        return KnownFolderAuthorityPaths(
            str(base),
            str(application),
            str(authority),
        )
    except Exception:
        return None
    finally:
        if value:
            free(ctypes.cast(value, ctypes.c_void_p))


def _safe_leaf(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and all(
        character not in value for character in ("/", "\\", "\x00")
    )


def _normalize(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\").casefold().removeprefix("\\\\?\\")


def _raise_cleanup(error: BaseException | None) -> Never:
    cleanup = CleanupFailure(DirectoryCleanupStatus.CLEANUP_FAILED.value)
    if error is None:
        raise cleanup
    raise BaseExceptionGroup(
        "authority ownership and cleanup failed",
        [error, cleanup],
    )
