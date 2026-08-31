"""Offline schema-v3 D1-N2 authority records. Native execution is absent."""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import os
import secrets
import stat
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, TypeVar, runtime_checkable

from . import m2_d1_n2_canonical as _canonical

SCHEMA_VERSION = 3
AUTHORITY_REVISION = "d1-n2-authority-v1"
DIRECTORY_LEAF = "d1-n2-authority-v1"
PREPARED_RECORD_NAME = "prepared.v3.json"
TERMINAL_RECORD_NAME = "terminal.v3.json"
WORKER_GRANT_RECORD_NAME = "worker-grant.v2.json"
AUTHORITY_MUTEX_NAME = r"Local\PDUExamObserver.D1N2.AuthorityV1"
VIDEO_MUTEX_NAME = r"Local\PDUExamObserver.D1N2.VideoOnly"
JOB_NAME_PREFIX = r"Local\PDUExamObserver.D1N2.Capture."
WORKER_GRANT_TTL_NS = 300_000_000_000


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


_FOLDERID_LOCAL_APP_DATA = _Guid(
    0xF1B32785,
    0x6FBA,
    0x4FCF,
    (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
)


@runtime_checkable
class _KnownFolderApi(Protocol):
    def known_folder_path(self, guid: _Guid) -> str: ...

    def free(self) -> None: ...


class _WindowsKnownFolderApi:
    """Typed SHGetKnownFolderPath wrapper with a single owned allocation."""

    def __init__(self) -> None:
        self._shell32: Any = ctypes.WinDLL("shell32", use_last_error=True)
        self._ole32: Any = ctypes.WinDLL("ole32", use_last_error=True)
        self._shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_Guid),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        self._shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        self._ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        self._ole32.CoTaskMemFree.restype = None
        self._allocated: ctypes.c_wchar_p | None = None

    def known_folder_path(self, guid: _Guid) -> str:
        if self._allocated is not None:
            raise OSError("known-folder allocation already active")
        output = ctypes.c_wchar_p()
        result = self._shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(output)
        )
        if result != 0 or not output.value:
            raise OSError("SHGetKnownFolderPath failed")
        self._allocated = output
        return output.value

    def free(self) -> None:
        if self._allocated is not None:
            self._ole32.CoTaskMemFree(ctypes.cast(self._allocated, ctypes.c_void_p))
            self._allocated = None


def _resolve_production_root(api: _KnownFolderApi) -> Path:
    try:
        local_app_data = Path(api.known_folder_path(_FOLDERID_LOCAL_APP_DATA))
        return local_app_data / "PDUExamObserver" / DIRECTORY_LEAF
    finally:
        api.free()


class D1N2State(StrEnum):
    ABSENT = "ABSENT"
    PENDING = "PENDING"
    PREPARED = "PREPARED"
    CONSUMED = "CONSUMED"
    TERMINAL = "TERMINAL"


class WorkerGrantState(StrEnum):
    ISSUED = "ISSUED"
    REVOKED = "REVOKED"


class TerminalCode(StrEnum):
    NONLAUNCHING_NO_GO = "NONLAUNCHING_NO_GO"


class D1N2PrepareStatus(StrEnum):
    PREPARED_NONLAUNCHING = "PREPARED_NONLAUNCHING"
    PENDING_NONLAUNCHABLE = "PENDING_NONLAUNCHABLE"
    STATE_CLOSED = "STATE_CLOSED"


class D1N2PlatformUnsupported(RuntimeError):
    """Production storage is intentionally Windows-only."""


@dataclass(frozen=True, slots=True)
class StaticBindingAttestation:
    static_bindings_digest: str
    binding_schema_digest: str

    def valid(self) -> bool:
        return _is_digest(self.static_bindings_digest) and _is_digest(self.binding_schema_digest)


@dataclass(frozen=True, slots=True)
class InertPrepareAttestation:
    supervisor_sha256: str
    supervisor_size_bytes: int
    supervisor_identity_digest: str
    worker_sha256: str
    worker_size_bytes: int
    worker_identity_digest: str
    ffmpeg_sha256: str
    ffmpeg_size_bytes: int
    ffmpeg_identity_digest: str
    ffmpeg_version_digest: str
    executable_lease_verified: bool

    def valid(self) -> bool:
        digests = (
            self.supervisor_sha256,
            self.supervisor_identity_digest,
            self.worker_sha256,
            self.worker_identity_digest,
            self.ffmpeg_sha256,
            self.ffmpeg_identity_digest,
            self.ffmpeg_version_digest,
        )
        return (
            all(_is_digest(value) for value in digests)
            and all(
                type(value) is int and value > 0
                for value in (
                    self.supervisor_size_bytes,
                    self.worker_size_bytes,
                    self.ffmpeg_size_bytes,
                )
            )
            and self.supervisor_sha256 == self.worker_sha256
            and self.supervisor_size_bytes == self.worker_size_bytes
            and self.supervisor_identity_digest == self.worker_identity_digest
            and self.executable_lease_verified is True
        )

    def binding_digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class AuthorityRecord:
    schema_version: int
    authority_revision: str
    state: D1N2State
    static_bindings_digest: str | None
    binding_schema_digest: str | None
    prepared_binding_digest: str | None
    consumed_binding_digest: str | None
    record_digest: str

    def body(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema_version": self.schema_version,
            "authority_revision": self.authority_revision,
            "state": self.state.value,
        }
        if self.state in (D1N2State.PREPARED, D1N2State.CONSUMED):
            body.update(
                {
                    "static_bindings_digest": self.static_bindings_digest,
                    "binding_schema_digest": self.binding_schema_digest,
                    "prepared_binding_digest": self.prepared_binding_digest,
                }
            )
        if self.state is D1N2State.CONSUMED:
            body["consumed_binding_digest"] = self.consumed_binding_digest
        return body

    def serialized(self) -> dict[str, object]:
        return {**self.body(), "record_digest": self.record_digest}


@dataclass(frozen=True, slots=True)
class WorkerGrantRecord:
    schema_version: int
    state: WorkerGrantState
    consumed_record_digest: str
    challenge_digest: str
    capability_digest: str
    issued_monotonic_ns: int
    expires_monotonic_ns: int
    record_digest: str

    def body(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "state": self.state.value,
            "consumed_record_digest": self.consumed_record_digest,
            "challenge_digest": self.challenge_digest,
            "capability_digest": self.capability_digest,
            "issued_monotonic_ns": self.issued_monotonic_ns,
            "expires_monotonic_ns": self.expires_monotonic_ns,
        }

    def serialized(self) -> dict[str, object]:
        return {**self.body(), "record_digest": self.record_digest}


@dataclass(frozen=True, slots=True)
class TerminalRecord:
    schema_version: int
    authority_revision: str
    state: D1N2State
    consumed_record_digest: str
    revoked_grant_digest: str
    terminal_code: TerminalCode
    record_digest: str

    def body(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "authority_revision": self.authority_revision,
            "state": self.state.value,
            "consumed_record_digest": self.consumed_record_digest,
            "revoked_grant_digest": self.revoked_grant_digest,
            "terminal_code": self.terminal_code.value,
        }

    def serialized(self) -> dict[str, object]:
        return {**self.body(), "record_digest": self.record_digest}


@dataclass(frozen=True, slots=True)
class D1N2Inspection:
    state: D1N2State | None
    record: AuthorityRecord | TerminalRecord | None
    invalid: bool = False
    parent_directory_durability: str = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class D1N2PrepareResult:
    status: D1N2PrepareStatus
    record: AuthorityRecord | None
    native_side_effects: bool = False


@dataclass(frozen=True, slots=True)
class _FaultPlan:
    stages: frozenset[str] = frozenset()

    def check(self, stage: str) -> None:
        if stage in self.stages:
            raise OSError("injected authority fault")


class _NamedMutex(Protocol):
    def acquire(self) -> bool: ...
    def release(self) -> bool: ...


_TEST_MUTEXES: dict[str, threading.Lock] = {}
_TEST_MUTEXES_GUARD = threading.Lock()


class _TestNamedMutex:
    """Private injected mutex. A unique name is required in every test."""

    def __init__(self, name: str) -> None:
        with _TEST_MUTEXES_GUARD:
            self._lock = _TEST_MUTEXES.setdefault(name, threading.Lock())

    def acquire(self) -> bool:
        return self._lock.acquire(timeout=1.0)

    def release(self) -> bool:
        self._lock.release()
        return True


class _WindowsNamedMutex:
    """The production cross-process mutex uses the exact fixed mutex name."""

    def __init__(self, name: str, kernel32: object | None = None) -> None:
        api: Any = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        create = api.CreateMutexW
        if type(api).__module__ == "ctypes":
            create.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            create.restype = ctypes.c_void_p
            api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            api.WaitForSingleObject.restype = ctypes.c_uint32
            api.ReleaseMutex.argtypes = [ctypes.c_void_p]
            api.ReleaseMutex.restype = ctypes.c_bool
            api.CloseHandle.argtypes = [ctypes.c_void_p]
            api.CloseHandle.restype = ctypes.c_bool
        self._kernel32: Any = api
        self._handle = create(None, False, name)
        if not self._handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW failed")

    def acquire(self) -> bool:
        return self._kernel32.WaitForSingleObject(self._handle, 10_000) in (0, 0x80)

    def release(self) -> bool:
        return bool(self._kernel32.ReleaseMutex(self._handle))

    def close(self) -> None:
        if self._handle is not None:
            handle, self._handle = self._handle, None
            if not self._kernel32.CloseHandle(handle):
                raise OSError(ctypes.get_last_error(), "CloseHandle mutex failed")

    def __enter__(self) -> _WindowsNamedMutex:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


class _WindowsLeafGuard:
    """Rejects reparse/nonregular leaves and parent swaps before each operation."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_api()
        self._root_handle = self._open_directory(root)
        self._root_final_path = self._final_path(self._root_handle)
        self._root_identity = self._file_identity(self._root_handle)
        self._leaf_handle: int | None = None

    def close(self) -> None:
        """Close held directory guards; a close error is never treated as success."""
        handles = (self._leaf_handle, self._root_handle)
        self._leaf_handle = None
        for handle in handles:
            if handle is not None and not self._kernel32.CloseHandle(handle):
                raise OSError(ctypes.get_last_error(), "CloseHandle failed")

    def __enter__(self) -> _WindowsLeafGuard:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def _configure_api(self) -> None:
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.CloseHandle.restype = ctypes.c_bool
        self._kernel32.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        self._kernel32.CreateFileW.restype = ctypes.c_void_p
        self._kernel32.GetFileInformationByHandleEx.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self._kernel32.GetFileInformationByHandleEx.restype = ctypes.c_bool
        self._kernel32.GetFinalPathNameByHandleW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        self._kernel32.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
        self._kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
        self._kernel32.FlushFileBuffers.restype = ctypes.c_bool

    def validate(self, directory: Path, leaves: tuple[Path, ...]) -> bool:
        try:
            if (
                self._final_path(self._root_handle) != self._root_final_path
                or self._file_identity(self._root_handle) != self._root_identity
            ):
                return False
            if directory.exists() and not _is_regular_directory(directory):
                return False
            if directory.exists() and self._leaf_handle is None:
                self._leaf_handle = self._open_directory(directory)
            if self._leaf_handle is not None and not self._is_directory(self._leaf_handle):
                return False
            for leaf in leaves:
                if leaf.exists() and not self._validate_leaf(leaf):
                    return False
            return True
        except OSError:
            return False

    def _open_directory(self, path: Path) -> int:
        handle = self._open(path, 0x02000000 | 0x00200000)
        if not self._is_directory(handle):
            self._kernel32.CloseHandle(handle)
            raise OSError("authority directory is nonregular")
        return handle

    def _validate_leaf(self, path: Path) -> bool:
        handle = self._open(path, 0x00200000)
        try:
            return not self._is_directory(handle)
        finally:
            if not self._kernel32.CloseHandle(handle):
                raise OSError(ctypes.get_last_error(), "CloseHandle failed")

    def _open(self, path: Path, flags: int) -> int:
        # FILE_SHARE_READ deliberately excludes FILE_SHARE_WRITE and FILE_SHARE_DELETE.
        handle = self._kernel32.CreateFileW(
            str(path),
            0x80 | 0x00100000,
            0x00000001,
            None,
            3,
            flags,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle in (None, invalid):
            raise OSError(ctypes.get_last_error(), "CreateFileW authority guard failed")
        return int(handle)

    def _is_directory(self, handle: int) -> bool:
        attributes = (ctypes.c_uint32 * 2)()
        if not self._kernel32.GetFileInformationByHandleEx(
            handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)
        ):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandleEx failed")
        if attributes[0] & 0x400:
            raise OSError("authority reparse point is rejected")
        return bool(attributes[0] & 0x10)

    def _file_identity(self, handle: int) -> str:
        buffer = (ctypes.c_ubyte * 24)()
        if not self._kernel32.GetFileInformationByHandleEx(
            handle, 18, ctypes.byref(buffer), ctypes.sizeof(buffer)
        ):
            raise OSError(ctypes.get_last_error(), "FileIdInfo unavailable")
        return hashlib.sha256(bytes(buffer)).hexdigest()

    def _final_path(self, handle: int) -> str:
        buffer = ctypes.create_unicode_buffer(32_768)
        size = self._kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if size == 0 or size >= len(buffer):
            raise OSError(ctypes.get_last_error(), "GetFinalPathNameByHandleW failed")
        return buffer.value

    def flush_parent_directory(self) -> bool:
        return bool(self._kernel32.FlushFileBuffers(self._leaf_handle or self._root_handle))


class _LegacyTestOnlyProductionAuthorityStore:
    """Deprecated pathname adapter retained only for isolated legacy tests."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise D1N2PlatformUnsupported("Windows known-folder storage required")
        mutex: _WindowsNamedMutex | None = None
        guard: _WindowsLeafGuard | None = None
        try:
            root = _resolve_production_root(_WindowsKnownFolderApi())
            mutex = _WindowsNamedMutex(AUTHORITY_MUTEX_NAME)
            guard = _WindowsLeafGuard(root.parent)
            self._mutex = mutex
            self._guard = guard
            self._core = _D1N2AuthorityStore(
                root.parent,
                mutex,
                leaf_guard=guard,
                parent_durability=guard.flush_parent_directory,
            )
        except Exception:
            if guard is not None:
                with contextlib.suppress(Exception):
                    guard.close()
            if mutex is not None:
                with contextlib.suppress(Exception):
                    mutex.close()
            raise

    def inspect(self) -> D1N2Inspection:
        return self._core.inspect()

    def reserve_pending(self) -> AuthorityRecord | None:
        return self._core.reserve_pending()

    def close(self) -> None:
        errors: list[Exception] = []
        for resource in (self._guard, self._mutex):
            try:
                resource.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise errors[0]

    def __enter__(self) -> _LegacyTestOnlyProductionAuthorityStore:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


_Result = TypeVar("_Result")


class _D1N2AuthorityStore:
    """Private root-taking core for temporary-directory tests only."""

    def __init__(
        self,
        root: Path,
        mutex: _NamedMutex,
        faults: _FaultPlan | None = None,
        leaf_guard: _WindowsLeafGuard | None = None,
        parent_durability: Callable[[], bool] | None = None,
        clock_ns: Callable[[], int] | None = None,
    ) -> None:
        self.directory = root / DIRECTORY_LEAF
        self.prepared_path = self.directory / PREPARED_RECORD_NAME
        self.terminal_path = self.directory / TERMINAL_RECORD_NAME
        self.worker_grant_path = self.directory / WORKER_GRANT_RECORD_NAME
        self._root = root
        self._mutex = mutex
        self._faults = faults or _FaultPlan()
        self._leaf_guard = leaf_guard
        self._root_identity: tuple[int, int] | None = None
        self._parent_durability = parent_durability or (lambda: True)
        self._clock_ns = clock_ns or _monotonic_ns

    def inspect(self) -> D1N2Inspection:
        return self._under_mutex(self._inspect_locked, _invalid())

    def reserve_pending(self) -> AuthorityRecord | None:
        def action() -> AuthorityRecord | None:
            if self._inspect_locked().state is not D1N2State.ABSENT:
                return None
            record = _new_authority_record(D1N2State.PENDING, None, None, None)
            self._create(self.prepared_path, record.serialized(), "pending_create")
            return record

        return self._under_mutex(action, None)

    def finalize_prepared(
        self, expected: str, static: StaticBindingAttestation, inert: InertPrepareAttestation
    ) -> AuthorityRecord | None:
        if not (_is_digest(expected) and static.valid() and inert.valid()):
            return None

        def action() -> AuthorityRecord | None:
            current = self._inspect_locked()
            if not _matches(current, D1N2State.PENDING, expected):
                return None
            record = _new_authority_record(D1N2State.PREPARED, static, inert.binding_digest(), None)
            self._transition(
                self.prepared_path,
                expected,
                record.serialized(),
                "prepared_transition",
                _parse_authority_record,
            )
            return record

        return self._under_mutex(action, None)

    def consume(self, expected: str, consumed_binding_digest: str) -> AuthorityRecord | None:
        if not (_is_digest(expected) and _is_digest(consumed_binding_digest)):
            return None

        def action() -> AuthorityRecord | None:
            current = self._inspect_locked()
            if not _matches(current, D1N2State.PREPARED, expected):
                return None
            assert isinstance(current.record, AuthorityRecord)
            record = _new_authority_record(
                D1N2State.CONSUMED,
                StaticBindingAttestation(
                    current.record.static_bindings_digest or "",
                    current.record.binding_schema_digest or "",
                ),
                current.record.prepared_binding_digest,
                consumed_binding_digest,
            )
            self._transition(
                self.prepared_path,
                expected,
                record.serialized(),
                "consumed_transition",
                _parse_authority_record,
            )
            return record

        return self._under_mutex(action, None)

    def issue_worker_grant(
        self, expected_consumed: str, challenge: str, capability: str, issued_ns: int | None = None
    ) -> WorkerGrantRecord | None:
        if not all(_is_digest(value) for value in (expected_consumed, challenge, capability)):
            return None
        issued = self._clock_ns() if issued_ns is None else issued_ns
        if type(issued) is not int or issued <= 0:
            return None

        def action() -> WorkerGrantRecord | None:
            if not _matches(self._inspect_locked(), D1N2State.CONSUMED, expected_consumed):
                return None
            record = _new_grant(
                WorkerGrantState.ISSUED,
                expected_consumed,
                challenge,
                capability,
                issued,
                issued + WORKER_GRANT_TTL_NS,
            )
            self._create(self.worker_grant_path, record.serialized(), "grant_issue")
            return record

        return self._under_mutex(action, None)

    def revoke_worker_grant(self, expected: str) -> WorkerGrantRecord | None:
        if not _is_digest(expected):
            return None

        def action() -> WorkerGrantRecord | None:
            grant = self._grant_locked()
            if (
                grant is None
                or grant.state is not WorkerGrantState.ISSUED
                or grant.record_digest != expected
                or not _grant_unexpired(grant, self._clock_ns())
            ):
                return None
            record = _new_grant(
                WorkerGrantState.REVOKED,
                grant.consumed_record_digest,
                grant.challenge_digest,
                grant.capability_digest,
                grant.issued_monotonic_ns,
                grant.expires_monotonic_ns,
            )
            self._transition(
                self.worker_grant_path, expected, record.serialized(), "grant_revoke", _parse_grant
            )
            return record

        return self._under_mutex(action, None)

    def finalize_terminal(
        self, expected_consumed: str, terminal_code: TerminalCode, expected_revoked_grant: str
    ) -> TerminalRecord | None:
        if not (
            isinstance(terminal_code, TerminalCode)
            and _is_digest(expected_consumed)
            and _is_digest(expected_revoked_grant)
        ):
            return None

        def action() -> TerminalRecord | None:
            if not _matches(self._inspect_locked(), D1N2State.CONSUMED, expected_consumed):
                return None
            grant = self._grant_locked()
            if (
                grant is None
                or grant.state is not WorkerGrantState.REVOKED
                or grant.record_digest != expected_revoked_grant
                or grant.consumed_record_digest != expected_consumed
                or not _grant_unexpired(grant, self._clock_ns())
            ):
                return None
            record = _new_terminal(expected_consumed, expected_revoked_grant, terminal_code)
            self._create(self.terminal_path, record.serialized(), "terminal_create")
            return record

        return self._under_mutex(action, None)

    def _under_mutex(self, action: Callable[[], _Result], fallback: _Result) -> _Result:
        try:
            self._faults.check("mutex_acquire")
            if not self._mutex.acquire():
                return fallback
        except Exception:
            return fallback
        try:
            result = action()
        except (OSError, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            result = fallback
        try:
            try:
                self._faults.check("mutex_release")
                if not self._mutex.release():
                    return fallback
            except Exception:
                return fallback
        finally:
            # No caller receives an authority result if mutual exclusion is uncertain.
            pass
        return result

    def _valid_filesystem_locked(self) -> bool:
        try:
            if self._root.exists():
                identity = _directory_identity(self._root)
                if self._root_identity is None:
                    self._root_identity = identity
                elif identity != self._root_identity:
                    return False
            if self.directory.exists() and not _is_regular_directory(self.directory):
                return False
            leaves = (self.prepared_path, self.terminal_path, self.worker_grant_path)
            if any(leaf.exists() and not _is_regular_file(leaf) for leaf in leaves):
                return False
            return self._leaf_guard is None or self._leaf_guard.validate(self.directory, leaves)
        except OSError:
            return False

    def _inspect_locked(self) -> D1N2Inspection:
        if not self._valid_filesystem_locked():
            return _invalid()
        prepared_exists = self.prepared_path.exists()
        terminal_exists = self.terminal_path.exists()
        grant_exists = self.worker_grant_path.exists()
        if not prepared_exists and not terminal_exists and not grant_exists:
            return D1N2Inspection(D1N2State.ABSENT, None)
        try:
            if not prepared_exists:
                raise ValueError("companion without authority")
            prepared = _parse_authority_record(_read_json(self.prepared_path))
            grant = self._grant_locked() if grant_exists else None
            if terminal_exists:
                terminal = _parse_terminal(_read_json(self.terminal_path))
                if (
                    prepared.state is not D1N2State.CONSUMED
                    or grant is None
                    or grant.state is not WorkerGrantState.REVOKED
                    or terminal.consumed_record_digest != prepared.record_digest
                    or terminal.revoked_grant_digest != grant.record_digest
                    or grant.consumed_record_digest != prepared.record_digest
                ):
                    raise ValueError("terminal binding invalid")
                return D1N2Inspection(D1N2State.TERMINAL, terminal)
            if grant is not None and prepared.state is not D1N2State.CONSUMED:
                raise ValueError("grant binding invalid")
            return D1N2Inspection(prepared.state, prepared)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return _invalid()

    def _grant_locked(self) -> WorkerGrantRecord | None:
        if not self.worker_grant_path.exists():
            return None
        return _parse_grant(_read_json(self.worker_grant_path))

    def _ensure_directory(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        if not _is_regular_directory(self._root):
            raise OSError("unsafe root")
        self.directory.mkdir(exist_ok=True)
        if not self._valid_filesystem_locked():
            raise OSError("unsafe leaf")

    def _create(self, path: Path, value: dict[str, object], stage: str) -> None:
        self._faults.check(stage)
        self._ensure_directory()
        encoded = _canonical_bytes(value)
        with path.open("xb") as handle:
            handle.write(encoded)
            self._faults.check(f"{stage}_flush")
            handle.flush()
            os.fsync(handle.fileno())
        if not self._parent_durability():
            raise OSError("parent directory durability is unavailable")
        if path.read_bytes() != encoded:
            raise OSError("create readback failed")

    def _transition(
        self,
        path: Path,
        expected: str,
        value: dict[str, object],
        stage: str,
        parser: Callable[[object], object],
    ) -> None:
        current = parser(_read_json(path))
        if not hasattr(current, "record_digest") or current.record_digest != expected:
            raise ValueError("stale transition")
        self._faults.check(stage)
        self._ensure_directory()
        encoded = _canonical_bytes(value)
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(16)}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(encoded)
                self._faults.check(f"{stage}_flush")
                handle.flush()
                os.fsync(handle.fileno())
            if not self._valid_filesystem_locked():
                raise OSError("unsafe transition")
            os.replace(temporary, path)
            if not self._parent_durability():
                raise OSError("parent directory durability is unavailable")
            if path.read_bytes() != encoded or not self._valid_filesystem_locked():
                raise OSError("transition readback failed")
        finally:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)


def _prepare_once(
    store: _D1N2AuthorityStore,
    static_attestor: Callable[[], StaticBindingAttestation],
    inert_attestor: Callable[[], InertPrepareAttestation],
) -> D1N2PrepareResult:
    """Private, inert seam. Any failure after PENDING is permanently closed."""
    if store.inspect().state is not D1N2State.ABSENT:
        return D1N2PrepareResult(D1N2PrepareStatus.STATE_CLOSED, None)
    pending = store.reserve_pending()
    if pending is None:
        return D1N2PrepareResult(D1N2PrepareStatus.STATE_CLOSED, None)
    try:
        prepared = store.finalize_prepared(
            pending.record_digest, static_attestor(), inert_attestor()
        )
    except Exception:
        prepared = None
    if prepared is None:
        return D1N2PrepareResult(D1N2PrepareStatus.PENDING_NONLAUNCHABLE, None)
    return D1N2PrepareResult(D1N2PrepareStatus.PREPARED_NONLAUNCHING, prepared)


def _matches(inspection: D1N2Inspection, state: D1N2State, expected: str) -> bool:
    return (
        inspection.state is state
        and isinstance(inspection.record, AuthorityRecord)
        and inspection.record.record_digest == expected
    )


def _new_authority_record(
    state: D1N2State,
    static: StaticBindingAttestation | None,
    prepared: str | None,
    consumed: str | None,
) -> AuthorityRecord:
    record = AuthorityRecord(
        SCHEMA_VERSION,
        AUTHORITY_REVISION,
        state,
        static.static_bindings_digest if static else None,
        static.binding_schema_digest if static else None,
        prepared,
        consumed,
        "",
    )
    return AuthorityRecord(
        record.schema_version,
        record.authority_revision,
        record.state,
        record.static_bindings_digest,
        record.binding_schema_digest,
        record.prepared_binding_digest,
        record.consumed_binding_digest,
        _digest(record.body()),
    )


def _new_grant(
    state: WorkerGrantState,
    consumed: str,
    challenge: str,
    capability: str,
    issued_ns: int,
    expires_ns: int,
) -> WorkerGrantRecord:
    record = WorkerGrantRecord(2, state, consumed, challenge, capability, issued_ns, expires_ns, "")
    return WorkerGrantRecord(
        record.schema_version,
        record.state,
        record.consumed_record_digest,
        record.challenge_digest,
        record.capability_digest,
        record.issued_monotonic_ns,
        record.expires_monotonic_ns,
        _digest(record.body()),
    )


def _new_terminal(consumed: str, revoked: str, code: TerminalCode) -> TerminalRecord:
    record = TerminalRecord(
        SCHEMA_VERSION, AUTHORITY_REVISION, D1N2State.TERMINAL, consumed, revoked, code, ""
    )
    return TerminalRecord(
        record.schema_version,
        record.authority_revision,
        record.state,
        record.consumed_record_digest,
        record.revoked_grant_digest,
        record.terminal_code,
        _digest(record.body()),
    )


def _parse_authority_record(raw: object) -> AuthorityRecord:
    if not isinstance(raw, dict) or not isinstance(raw.get("state"), str):
        raise ValueError("authority malformed")
    state = D1N2State(raw["state"])
    keys = {"schema_version", "authority_revision", "state", "record_digest"}
    if state in (D1N2State.PREPARED, D1N2State.CONSUMED):
        keys |= {"static_bindings_digest", "binding_schema_digest", "prepared_binding_digest"}
    if state is D1N2State.CONSUMED:
        keys.add("consumed_binding_digest")
    if set(raw) != keys:
        raise ValueError("authority keys")
    record = AuthorityRecord(
        raw["schema_version"],
        raw["authority_revision"],
        state,
        raw.get("static_bindings_digest"),
        raw.get("binding_schema_digest"),
        raw.get("prepared_binding_digest"),
        raw.get("consumed_binding_digest"),
        raw["record_digest"],
    )
    values = (
        record.record_digest,
        record.static_bindings_digest,
        record.binding_schema_digest,
        record.prepared_binding_digest,
        record.consumed_binding_digest,
    )
    if (
        type(record.schema_version) is not int
        or record.schema_version != SCHEMA_VERSION
        or record.authority_revision != AUTHORITY_REVISION
        or any(value is not None and not _is_digest(value) for value in values)
        or record.record_digest != _digest(record.body())
        or state is D1N2State.TERMINAL
        or (state is D1N2State.PENDING and any(value is not None for value in values[1:]))
        or (
            state is D1N2State.PREPARED
            and (
                not all(_is_digest(value) for value in values[1:4])
                or record.consumed_binding_digest is not None
            )
        )
        or (state is D1N2State.CONSUMED and not all(_is_digest(value) for value in values[1:]))
    ):
        raise ValueError("authority invalid")
    return record


def _parse_grant(raw: object) -> WorkerGrantRecord:
    keys = {
        "schema_version",
        "state",
        "consumed_record_digest",
        "challenge_digest",
        "capability_digest",
        "issued_monotonic_ns",
        "expires_monotonic_ns",
        "record_digest",
    }
    if not isinstance(raw, dict) or set(raw) != keys or not isinstance(raw.get("state"), str):
        raise ValueError("grant malformed")
    record = WorkerGrantRecord(
        raw["schema_version"],
        WorkerGrantState(raw["state"]),
        raw["consumed_record_digest"],
        raw["challenge_digest"],
        raw["capability_digest"],
        raw["issued_monotonic_ns"],
        raw["expires_monotonic_ns"],
        raw["record_digest"],
    )
    if (
        type(record.schema_version) is not int
        or record.schema_version != 2
        or type(record.issued_monotonic_ns) is not int
        or type(record.expires_monotonic_ns) is not int
        or record.issued_monotonic_ns <= 0
        or record.expires_monotonic_ns != record.issued_monotonic_ns + WORKER_GRANT_TTL_NS
        or not all(
            _is_digest(value)
            for value in (
                record.consumed_record_digest,
                record.challenge_digest,
                record.capability_digest,
                record.record_digest,
            )
        )
        or record.record_digest != _digest(record.body())
    ):
        raise ValueError("grant invalid")
    return record


def _parse_terminal(raw: object) -> TerminalRecord:
    keys = {
        "schema_version",
        "authority_revision",
        "state",
        "consumed_record_digest",
        "revoked_grant_digest",
        "terminal_code",
        "record_digest",
    }
    if not isinstance(raw, dict) or set(raw) != keys:
        raise ValueError("terminal malformed")
    record = TerminalRecord(
        raw["schema_version"],
        raw["authority_revision"],
        D1N2State(raw["state"]),
        raw["consumed_record_digest"],
        raw["revoked_grant_digest"],
        TerminalCode(raw["terminal_code"]),
        raw["record_digest"],
    )
    if (
        type(record.schema_version) is not int
        or record.schema_version != SCHEMA_VERSION
        or record.authority_revision != AUTHORITY_REVISION
        or record.state is not D1N2State.TERMINAL
        or not all(
            _is_digest(value)
            for value in (
                record.consumed_record_digest,
                record.revoked_grant_digest,
                record.record_digest,
            )
        )
        or record.record_digest != _digest(record.body())
    ):
        raise ValueError("terminal invalid")
    return record


def _read_json(path: Path) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_float=lambda _: (_ for _ in ()).throw(ValueError("floats forbidden")),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constants forbidden")),
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _invalid() -> D1N2Inspection:
    return D1N2Inspection(None, None, invalid=True)


def _directory_identity(path: Path) -> tuple[int, int]:
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
        raise OSError("unsafe directory")
    return info.st_dev, info.st_ino


def _is_regular_directory(path: Path) -> bool:
    info = path.stat(follow_symlinks=False)
    return stat.S_ISDIR(info.st_mode) and not path.is_symlink()


def _is_regular_file(path: Path) -> bool:
    info = path.stat(follow_symlinks=False)
    return stat.S_ISREG(info.st_mode) and not path.is_symlink()


def _grant_unexpired(grant: WorkerGrantRecord, now_ns: int) -> bool:
    return type(now_ns) is int and grant.issued_monotonic_ns <= now_ns <= grant.expires_monotonic_ns


def _monotonic_ns() -> int:
    return time.monotonic_ns()


AuthorityLeaf = _canonical.AuthorityLeaf
BeginResult = _canonical.BeginResult
CanonicalAuthorityPersistence = _canonical.CanonicalAuthorityPersistence
CanonicalCleanupFailure = _canonical.CanonicalCleanupFailure
CanonicalGrantInspection = _canonical.CanonicalGrantInspection
CanonicalInjectableAuthorityLifecycle = _canonical.CanonicalInjectableAuthorityLifecycle
CanonicalInspection = _canonical.CanonicalInspection
CanonicalLifecycleState = _canonical.CanonicalLifecycleState
classify_canonical_leaf_record = _canonical.classify_canonical_leaf_record
CleanupReport = _canonical.CleanupReport
DurabilityStatus = _canonical.DurabilityStatus
GrantDisposition = _canonical.GrantDisposition
InjectableAuthorityLifecycle = _canonical.InjectableAuthorityLifecycle
InjectableAuthorityState = _canonical.InjectableAuthorityState
InjectableWorkerGrant = _canonical.InjectableWorkerGrant
MutationGuardFactory = _canonical.MutationGuardFactory
MutationSession = _canonical.MutationSession
OperationKind = _canonical.OperationKind
OwnerStatus = _canonical.OwnerStatus
PersistenceOutcome = _canonical.PersistenceOutcome
ProcessEpoch = _canonical.ProcessEpoch
ProcessEpochV2 = _canonical.ProcessEpochV2
StepStatus = _canonical.StepStatus
ValidationStatus = _canonical.ValidationStatus
WriteDisposition = _canonical.WriteDisposition
WriteResult = _canonical.WriteResult
