"""Isolated same-handle leaf primitive; no authority-store wiring."""

from __future__ import annotations

import ctypes
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

MAX_AUTHORITY_RECORD_BYTES = 32_768
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3

_FILE_TYPE_DISK = 1
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_WRITE_THROUGH = 0x80000000
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_FILE_READ_ATTRIBUTES = 0x00000080
_SYNCHRONIZE = 0x00100000
_CREATE_NEW = 1
_OPEN_EXISTING = 3
_FILE_BEGIN = 0
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_STANDARD_INFO_CLASS = 1
_FILE_ID_INFO_CLASS = 18


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


class LeafFailure(StrEnum):
    ABSENT = "ABSENT"
    OPEN_FAILED = "OPEN_FAILED"
    CREATE_CONFLICT = "CREATE_CONFLICT"
    HANDLE_VALIDATION_FAILED = "HANDLE_VALIDATION_FAILED"
    READ_FAILED = "READ_FAILED"
    CODEC_INVALID = "CODEC_INVALID"
    STALE_CAS = "STALE_CAS"
    WRITE_FAILED = "WRITE_FAILED"
    TRUNCATE_FAILED = "TRUNCATE_FAILED"
    FLUSH_FAILED = "FLUSH_FAILED"
    READBACK_FAILED = "READBACK_FAILED"
    IDENTITY_CHANGED = "IDENTITY_CHANGED"
    CLOSE_FAILED = "CLOSE_FAILED"


@dataclass(frozen=True, slots=True)
class HandleInfo:
    disk: bool
    reparse: bool
    directory: bool
    delete_pending: bool
    links: int
    final_path: str
    identity: str
    size: int = 0


@dataclass(frozen=True, slots=True)
class LeafResult:
    payload: bytes | None
    failure: LeafFailure | None


class HandleOps(Protocol):
    def create_new(self, path: str) -> int | None: ...
    def open_existing(self, path: str) -> int | None: ...
    def open_inspection(self, path: str) -> int | None: ...
    def info(self, handle: int) -> HandleInfo: ...
    def read(self, handle: int, limit: int) -> bytes | None: ...
    def seek_start(self, handle: int) -> bool: ...
    def write(self, handle: int, data: bytes) -> int: ...
    def truncate(self, handle: int) -> bool: ...
    def flush(self, handle: int) -> bool: ...
    def close(self, handle: int) -> bool: ...


class CtypesHandleOps:
    """ABI-declared production adapter; tests inject a fake and never invoke Win32."""

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
            "ReadFile": (
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.c_void_p,
                ],
                ctypes.c_int32,
            ),
            "SetFilePointerEx": (
                [
                    ctypes.c_void_p,
                    ctypes.c_longlong,
                    ctypes.POINTER(ctypes.c_longlong),
                    ctypes.c_uint32,
                ],
                ctypes.c_int32,
            ),
            "WriteFile": (
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.c_void_p,
                ],
                ctypes.c_int32,
            ),
            "SetEndOfFile": ([ctypes.c_void_p], ctypes.c_int32),
            "FlushFileBuffers": ([ctypes.c_void_p], ctypes.c_int32),
            "CloseHandle": ([ctypes.c_void_p], ctypes.c_int32),
        }
        for name, (args, result) in specs.items():
            function = getattr(self._api, name)
            function.argtypes, function.restype = args, result

    def create_new(self, path: str) -> int | None:
        return self._open(
            path,
            _CREATE_NEW,
            missing_is_absent=False,
            access=self._write_access,
            flags=self._write_flags,
        )

    def open_existing(self, path: str) -> int | None:
        return self._open(
            path,
            _OPEN_EXISTING,
            missing_is_absent=True,
            access=self._write_access,
            flags=self._write_flags,
        )

    def open_inspection(self, path: str) -> int | None:
        return self._open(
            path,
            _OPEN_EXISTING,
            missing_is_absent=True,
            access=_GENERIC_READ | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
            flags=_FILE_ATTRIBUTE_NORMAL | _FILE_FLAG_OPEN_REPARSE_POINT,
        )

    @property
    def _write_access(self) -> int:
        return _GENERIC_READ | _GENERIC_WRITE | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE

    @property
    def _write_flags(self) -> int:
        return (
            _FILE_ATTRIBUTE_NORMAL
            | _FILE_FLAG_OPEN_REPARSE_POINT
            | _FILE_FLAG_WRITE_THROUGH
        )

    def _open(
        self,
        path: str,
        disposition: int,
        *,
        missing_is_absent: bool,
        access: int,
        flags: int,
    ) -> int | None:
        handle = self._api.CreateFileW(path, access, 0, None, disposition, flags, None)
        value = handle.value if isinstance(handle, ctypes.c_void_p) else handle
        if not isinstance(value, int) or value == ctypes.c_void_p(-1).value:
            if missing_is_absent:
                error = ctypes.get_last_error()
                if error not in {_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND}:
                    raise OSError(error, "authority leaf open failed")
            return None
        return value

    def info(self, handle: int) -> HandleInfo:
        invalid = HandleInfo(False, True, True, True, 0, "", "", -1)
        try:
            if self._api.GetFileType(handle) != _FILE_TYPE_DISK:
                return invalid
            attributes = _FileAttributeTagInfo()
            standard = _FileStandardInfo()
            identity = _FileIdInfo()
            metadata = (
                (
                    _FILE_ATTRIBUTE_TAG_INFO_CLASS,
                    attributes,
                ),
                (
                    _FILE_STANDARD_INFO_CLASS,
                    standard,
                ),
                (
                    _FILE_ID_INFO_CLASS,
                    identity,
                ),
            )
            for info_class, value in metadata:
                if not self._api.GetFileInformationByHandleEx(
                    handle,
                    info_class,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                ):
                    return invalid
            path_buffer = ctypes.create_unicode_buffer(32_768)
            path_size = self._api.GetFinalPathNameByHandleW(
                handle, path_buffer, len(path_buffer), 0
            )
            if path_size == 0 or path_size >= len(path_buffer):
                return invalid
            identity_bytes = (
                int(identity.volume_serial_number).to_bytes(8, "little")
                + bytes(identity.file_id)
            )
            return HandleInfo(
                disk=True,
                reparse=bool(
                    attributes.file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT
                ),
                directory=bool(standard.directory),
                delete_pending=bool(standard.delete_pending),
                links=int(standard.number_of_links),
                final_path=path_buffer.value,
                identity=hashlib.sha256(identity_bytes).hexdigest(),
                size=int(standard.end_of_file),
            )
        except Exception:
            return invalid

    def read(self, handle: int, limit: int) -> bytes | None:
        if limit <= 0:
            return None
        result = bytearray()
        try:
            while len(result) < limit:
                requested = min(4096, limit - len(result))
                buffer = (ctypes.c_ubyte * requested)()
                count = ctypes.c_uint32()
                if not self._api.ReadFile(
                    handle, buffer, requested, ctypes.byref(count), None
                ):
                    return None
                if count.value > requested:
                    return None
                if count.value == 0:
                    break
                result.extend(buffer[: count.value])
            return bytes(result)
        except Exception:
            return None

    def seek_start(self, handle: int) -> bool:
        return bool(self._api.SetFilePointerEx(handle, 0, None, 0))

    def write(self, handle: int, data: bytes) -> int:
        if not data:
            return 0
        count = ctypes.c_uint32()
        buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        if not self._api.WriteFile(
            handle, buffer, len(data), ctypes.byref(count), None
        ):
            return 0
        return int(count.value)

    def truncate(self, handle: int) -> bool:
        return bool(self._api.SetEndOfFile(handle))

    def flush(self, handle: int) -> bool:
        return bool(self._api.FlushFileBuffers(handle))

    def close(self, handle: int) -> bool:
        try:
            return bool(self._api.CloseHandle(handle))
        except Exception:
            return False


class SameHandleLeaf:
    def __init__(self, ops: HandleOps, path: str) -> None:
        self._ops, self._path = ops, path

    def create(self, payload: bytes, codec: Callable[[bytes], bool]) -> LeafResult:
        handle = self._ops.create_new(self._path)
        if handle is None:
            return LeafResult(None, LeafFailure.CREATE_CONFLICT)
        return self._commit(handle, None, payload, codec)

    def transition(
        self, expected: bytes, payload: bytes, codec: Callable[[bytes], bool]
    ) -> LeafResult:
        try:
            handle = self._ops.open_existing(self._path)
        except Exception:
            return LeafResult(None, LeafFailure.OPEN_FAILED)
        if handle is None:
            return LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        return self._commit(handle, expected, payload, codec)

    def inspect(self, codec: Callable[[bytes], bool]) -> LeafResult:
        """Read and validate an existing leaf without mutating its handle."""
        try:
            handle = self._ops.open_inspection(self._path)
        except Exception:
            return LeafResult(None, LeafFailure.OPEN_FAILED)
        if handle is None:
            return LeafResult(None, LeafFailure.ABSENT)
        return self._inspect_commit(handle, codec)

    def _inspect_commit(
        self, handle: int, codec: Callable[[bytes], bool]
    ) -> LeafResult:
        escaped: BaseException | None = None
        close_error: BaseException | None = None
        closed = False
        result = LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        try:
            try:
                result = self._inspect_open(handle, codec)
            except Exception:
                result = LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
            except BaseException as error:
                escaped = error
        finally:
            try:
                closed = self._ops.close(handle)
            except BaseException as error:
                close_error = error
                closed = False
        if escaped is not None:
            if not closed:
                cleanup = close_error or RuntimeError(LeafFailure.CLOSE_FAILED.value)
                raise BaseExceptionGroup(
                    "authority inspection and handle cleanup failed",
                    [escaped, cleanup],
                )
            raise escaped
        if not closed:
            return LeafResult(None, LeafFailure.CLOSE_FAILED)
        return result

    def _inspect_open(
        self, handle: int, codec: Callable[[bytes], bool]
    ) -> LeafResult:
        try:
            initial = self._ops.info(handle)
        except Exception:
            return LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        if not self._valid(initial):
            return LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        try:
            at_start = self._ops.seek_start(handle)
        except Exception:
            at_start = False
        if not at_start:
            return LeafResult(None, LeafFailure.READ_FAILED)
        try:
            payload = self._ops.read(handle, MAX_AUTHORITY_RECORD_BYTES + 1)
        except Exception:
            return LeafResult(None, LeafFailure.READ_FAILED)
        if payload is None or not 0 < len(payload) <= MAX_AUTHORITY_RECORD_BYTES:
            return LeafResult(None, LeafFailure.READ_FAILED)
        try:
            codec_valid = codec(payload)
        except Exception:
            codec_valid = False
        if not codec_valid:
            return LeafResult(None, LeafFailure.CODEC_INVALID)
        try:
            final = self._ops.info(handle)
        except Exception:
            return LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        if not self._valid(final):
            return LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        if final.identity != initial.identity:
            return LeafResult(None, LeafFailure.IDENTITY_CHANGED)
        return LeafResult(payload, None)

    def _commit(
        self, handle: int, expected: bytes | None, payload: bytes, codec: Callable[[bytes], bool]
    ) -> LeafResult:
        escaped: BaseException | None = None
        close_error: BaseException | None = None
        closed = False
        result = LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        try:
            try:
                result = self._commit_open(handle, expected, payload, codec)
            except Exception:
                result = LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
            except BaseException as error:
                escaped = error
        finally:
            try:
                closed = self._ops.close(handle)
            except BaseException as error:
                close_error = error
                closed = False
        if escaped is not None:
            if not closed:
                cleanup = close_error or RuntimeError(LeafFailure.CLOSE_FAILED.value)
                raise BaseExceptionGroup(
                    "authority operation and handle cleanup failed",
                    [escaped, cleanup],
                )
            raise escaped
        if not closed:
            return LeafResult(None, LeafFailure.CLOSE_FAILED)
        return result

    def _commit_open(
        self,
        handle: int,
        expected: bytes | None,
        payload: bytes,
        codec: Callable[[bytes], bool],
    ) -> LeafResult:
        invalid = LeafResult(None, LeafFailure.HANDLE_VALIDATION_FAILED)
        initial = self._ops.info(handle)
        if not self._valid(initial) or not self._valid_payload(payload, codec):
            return invalid
        if expected is not None:
            current = self._ops.read(handle, MAX_AUTHORITY_RECORD_BYTES + 1)
            if current is None or not self._valid_payload(current, codec):
                return LeafResult(None, LeafFailure.READ_FAILED)
            if current != expected:
                return LeafResult(None, LeafFailure.STALE_CAS)
        if not self._ops.seek_start(handle):
            return LeafResult(None, LeafFailure.WRITE_FAILED)
        offset = 0
        while offset < len(payload):
            written = self._ops.write(handle, payload[offset:])
            if written <= 0 or written > len(payload) - offset:
                return LeafResult(None, LeafFailure.WRITE_FAILED)
            offset += written
        if not self._ops.truncate(handle):
            return LeafResult(None, LeafFailure.TRUNCATE_FAILED)
        if not self._ops.flush(handle):
            return LeafResult(None, LeafFailure.FLUSH_FAILED)
        if not self._ops.seek_start(handle):
            return LeafResult(None, LeafFailure.READBACK_FAILED)
        readback = self._ops.read(handle, MAX_AUTHORITY_RECORD_BYTES + 1)
        if readback != payload:
            return LeafResult(None, LeafFailure.READBACK_FAILED)
        final = self._ops.info(handle)
        if not self._valid(final):
            return invalid
        if final.identity != initial.identity:
            return LeafResult(None, LeafFailure.IDENTITY_CHANGED)
        return LeafResult(payload, None)

    def _valid(self, info: HandleInfo) -> bool:
        return (
            info.disk
            and not info.reparse
            and not info.directory
            and not info.delete_pending
            and info.links == 1
            and _normalize(info.final_path) == _normalize(self._path)
        )

    def _valid_payload(self, payload: bytes, codec: Callable[[bytes], bool]) -> bool:
        return 0 < len(payload) <= MAX_AUTHORITY_RECORD_BYTES and codec(payload)


def _normalize(path: str) -> str:
    return path.replace("/", "\\").lower().removeprefix("\\\\?\\")
