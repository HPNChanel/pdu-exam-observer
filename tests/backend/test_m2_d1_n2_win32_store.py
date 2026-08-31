import ctypes
from pathlib import Path

import pytest

import pdu_exam_observer.m2_d1_n2_win32_store as store_module
from pdu_exam_observer.m2_d1_n2_win32_store import (
    APPLICATION_DIRECTORY_LEAF,
    AUTHORITY_DIRECTORY_LEAF,
    AUTHORITY_MUTEX_NAME,
    FOLDERID_LOCAL_APP_DATA_GUID,
    CleanupFailure,
    CtypesDirectoryOps,
    CtypesMutexOps,
    DirectoryAcquireFailure,
    DirectoryCleanupStatus,
    DirectoryDurability,
    DirectoryInfo,
    DirectoryLease,
    DirectoryLeaseAcquisition,
    KnownFolderAuthorityPaths,
    MutexStatus,
    WindowsNamedMutex,
    resolve_known_folder_authority_root,
)


def test_h2_mutex_status_exists() -> None:
    assert MutexStatus.ABANDONED.value == "ABANDONED"


def test_h2_abandoned_mutex_never_permits_mutation_and_closes() -> None:
    class Ops:
        def __init__(self) -> None:
            self.closed = 0
            self.released = 0

        def acquire(self, _name: str) -> MutexStatus:
            return MutexStatus.ABANDONED

        def release(self) -> bool:
            self.released += 1
            return True

        def close(self) -> bool:
            self.closed += 1
            return True

    ops = Ops()
    mutex = WindowsNamedMutex(ops)
    assert mutex.acquire() is MutexStatus.ABANDONED
    assert mutex.mutation_permitted is False
    assert mutex.close() is True and mutex.close() is True
    assert ops.released == 1 and ops.closed == 1


def test_h2_red_repeated_acquire_preserves_owned_mutex_for_release() -> None:
    class Ops:
        def __init__(self) -> None:
            self.acquires = self.releases = self.closes = 0

        def acquire(self, _name: str) -> MutexStatus:
            self.acquires += 1
            return MutexStatus.ACQUIRED if self.acquires == 1 else MutexStatus.UNAVAILABLE

        def release(self) -> bool:
            self.releases += 1
            return True

        def close(self) -> bool:
            self.closes += 1
            return True

    ops = Ops()
    mutex = WindowsNamedMutex(ops)
    assert mutex.acquire() is MutexStatus.ACQUIRED
    assert mutex.acquire() is MutexStatus.ACQUIRED
    assert mutex.close() is True
    assert (ops.acquires, ops.releases, ops.closes) == (1, 1, 1)


def test_h2_red_known_folder_resolver_has_exact_guid_and_fixed_tiers() -> None:
    assert (
        FOLDERID_LOCAL_APP_DATA_GUID.Data1,
        FOLDERID_LOCAL_APP_DATA_GUID.Data2,
        FOLDERID_LOCAL_APP_DATA_GUID.Data3,
        tuple(FOLDERID_LOCAL_APP_DATA_GUID.Data4),
    ) == (0xF1B32785, 0x6FBA, 0x4FCF, (0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91))
    assert resolve_known_folder_authority_root


class _Fn:
    def __init__(self, callback: object) -> None:
        self.callback = callback
        self.calls: list[tuple[object, ...]] = []
        self.argtypes: object = None
        self.restype: object = None

    def __call__(self, *arguments: object) -> object:
        self.calls.append(arguments)
        if callable(self.callback):
            return self.callback(*arguments)
        return self.callback


def test_h2_known_folder_abi_exact_path_and_free() -> None:
    buffer = ctypes.create_unicode_buffer(r"C:\Local")

    def get_path(
        guid: object,
        flags: int,
        token: object,
        output: object,
    ) -> int:
        value = ctypes.cast(
            guid, ctypes.POINTER(store_module._Guid)
        ).contents
        assert (value.Data1, value.Data2, value.Data3, tuple(value.Data4)) == (
            0xF1B32785,
            0x6FBA,
            0x4FCF,
            (0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
        )
        assert flags == 0 and token is None
        pointer = ctypes.cast(output, ctypes.POINTER(ctypes.c_wchar_p))
        pointer[0] = ctypes.cast(buffer, ctypes.c_wchar_p)
        return 0

    shell = type("Shell", (), {})()
    shell.SHGetKnownFolderPath = _Fn(get_path)
    allocator = type("Allocator", (), {})()
    allocator.CoTaskMemFree = _Fn(None)

    resolved = resolve_known_folder_authority_root(shell, allocator)
    assert resolved == KnownFolderAuthorityPaths(
        r"C:\Local",
        str(Path(r"C:\Local") / APPLICATION_DIRECTORY_LEAF),
        str(
            Path(r"C:\Local")
            / APPLICATION_DIRECTORY_LEAF
            / AUTHORITY_DIRECTORY_LEAF
        ),
    )
    assert shell.SHGetKnownFolderPath.restype is ctypes.c_int32
    assert shell.SHGetKnownFolderPath.argtypes[0] == ctypes.POINTER(store_module._Guid)
    assert allocator.CoTaskMemFree.calls


@pytest.mark.parametrize(
    ("wait", "status"),
    [
        (0, MutexStatus.ACQUIRED),
        (0x80, MutexStatus.ABANDONED),
        (0x102, MutexStatus.UNAVAILABLE),
        (0xFFFFFFFF, MutexStatus.UNAVAILABLE),
    ],
)
def test_h2_ctypes_mutex_wait_status_and_high_handle(
    wait: int, status: MutexStatus
) -> None:
    high_handle = 0x1_0000_0099
    kernel = type("Kernel", (), {})()
    kernel.CreateMutexW = _Fn(high_handle)
    kernel.WaitForSingleObject = _Fn(wait)
    kernel.ReleaseMutex = _Fn(1)
    kernel.CloseHandle = _Fn(1)
    ops = CtypesMutexOps(kernel)
    mutex = WindowsNamedMutex(ops)

    assert mutex.acquire() is status
    assert mutex.mutation_permitted is (status is MutexStatus.ACQUIRED)
    assert kernel.CreateMutexW.calls[0][2] == AUTHORITY_MUTEX_NAME
    assert mutex.close() is True
    assert kernel.CloseHandle.calls == [(high_handle,)]
    expected_release = status in {MutexStatus.ACQUIRED, MutexStatus.ABANDONED}
    assert bool(kernel.ReleaseMutex.calls) is expected_release
    assert kernel.CreateMutexW.restype is ctypes.c_void_p
    assert kernel.ReleaseMutex.restype is ctypes.c_int32
    assert kernel.CloseHandle.restype is ctypes.c_int32


def test_h2_mutex_release_failure_still_closes_and_reports_failure() -> None:
    kernel = type("Kernel", (), {})()
    kernel.CreateMutexW = _Fn(41)
    kernel.WaitForSingleObject = _Fn(0)
    kernel.ReleaseMutex = _Fn(0)
    kernel.CloseHandle = _Fn(1)
    mutex = WindowsNamedMutex(CtypesMutexOps(kernel))
    assert mutex.acquire() is MutexStatus.ACQUIRED
    assert mutex.close() is False
    assert kernel.CloseHandle.calls == [(41,)]


def test_h2_red_directory_lease_exposes_typed_durability() -> None:
    assert DirectoryDurability.VERIFIED.value == "VERIFIED"
    assert DirectoryDurability.UNVERIFIED.value == "UNVERIFIED"


def test_h2_review_red_directory_acquisition_reports_cleanup_failure() -> None:
    assert DirectoryLeaseAcquisition


def test_h2_review_red_cleanup_failure_surface_preserves_body_exception() -> None:
    assert CleanupFailure


def test_h2_review_red_directory_abi_cleanup_status_surface() -> None:
    assert DirectoryCleanupStatus.CLEANUP_FAILED.value == "CLEANUP_FAILED"


def test_h2_review_red_known_folder_paths_are_three_distinct_tiers() -> None:
    paths = KnownFolderAuthorityPaths(
        r"C:\Local",
        r"C:\Local\PDUExamObserver",
        r"C:\Local\PDUExamObserver\d1-n2-authority-v1",
    )
    assert paths.base != paths.application != paths.authority


class _DirectoryOps:
    def __init__(self, **mutants: object) -> None:
        self.mutants = mutants
        self.created: set[str] = set()
        self.opened: list[str] = []
        self.create_calls: list[tuple[object, str]] = []
        self.closed: list[object] = []
        self.flush_calls: list[object] = []
        self.info_counts: dict[object, int] = {}
        self.paths: dict[object, str] = {}

    def open_existing(self, path: str) -> object | None:
        self.opened.append(path)
        name = Path(path).name
        if (
            name in {APPLICATION_DIRECTORY_LEAF, AUTHORITY_DIRECTORY_LEAF}
            and name not in self.created
        ):
            return None
        handle = f"h:{name or 'root'}"
        self.paths[handle] = path
        return handle

    def create_child(self, parent: object, name: str) -> bool:
        self.create_calls.append((parent, name))
        if self.mutants.get("create_failure") == name:
            return False
        self.created.add(name)
        return True

    def info(self, handle: object) -> DirectoryInfo:
        if self.mutants.get("raise_info") == handle:
            raise RuntimeError("injected")
        count = self.info_counts.get(handle, 0) + 1
        self.info_counts[handle] = count
        identity = f"id:{handle}"
        if self.mutants.get("identity_swap") == handle and count > 1:
            identity = "changed"
        path = self.paths[handle]
        if self.mutants.get("wrong_path") == handle:
            path += "-wrong"
        return DirectoryInfo(
            disk=True,
            reparse=self.mutants.get("reparse") == handle,
            directory=True,
            final_path=path,
            identity=identity,
        )

    def flush_directory(self, handle: object) -> bool:
        self.flush_calls.append(handle)
        return not self.mutants.get("flush_failure")

    def close(self, handle: object) -> bool:
        self.closed.append(handle)
        return self.mutants.get("close_failure") != handle


def _paths() -> KnownFolderAuthorityPaths:
    base = str(Path(r"C:\Local"))
    application = str(Path(base) / APPLICATION_DIRECTORY_LEAF)
    authority = str(Path(application) / AUTHORITY_DIRECTORY_LEAF)
    return KnownFolderAuthorityPaths(base, application, authority)


def test_h2_directory_lease_exact_tiers_durability_and_reverse_close() -> None:
    ops = _DirectoryOps()
    acquisition = DirectoryLease.acquire(ops, _paths())
    lease = acquisition.lease
    assert lease is not None
    assert acquisition.failure is None
    assert acquisition.cleanup_status is DirectoryCleanupStatus.CLEAN
    expected = (_paths().base, _paths().application, _paths().authority)
    assert lease.paths == expected
    assert [name for _, name in ops.create_calls] == [
        APPLICATION_DIRECTORY_LEAF,
        AUTHORITY_DIRECTORY_LEAF,
    ]
    assert lease.durable() is DirectoryDurability.VERIFIED
    assert ops.flush_calls == [lease.handles[-1]]
    assert lease.close() is True and lease.close() is True
    assert ops.closed == list(reversed(lease.handles))


@pytest.mark.parametrize(
    "mutants",
    [
        {"create_failure": APPLICATION_DIRECTORY_LEAF},
        {"wrong_path": "h:PDUExamObserver"},
        {"reparse": "h:d1-n2-authority-v1"},
    ],
)
def test_h2_directory_acquire_mutants_fail_and_close(
    mutants: dict[str, object]
) -> None:
    ops = _DirectoryOps(**mutants)
    acquisition = DirectoryLease.acquire(ops, _paths())
    assert acquisition.lease is None
    assert acquisition.failure is not None
    assert len(ops.closed) == len(set(ops.closed))


def test_h2_directory_identity_or_flush_failure_is_unverified() -> None:
    ops = _DirectoryOps(identity_swap="h:d1-n2-authority-v1")
    lease = DirectoryLease.acquire(ops, _paths()).lease
    assert lease is not None
    assert lease.durable() is DirectoryDurability.UNVERIFIED
    lease.close()

    flush_ops = _DirectoryOps(flush_failure=True)
    flush_lease = DirectoryLease.acquire(flush_ops, _paths()).lease
    assert flush_lease is not None
    assert flush_lease.durable() is DirectoryDurability.UNVERIFIED
    flush_lease.close()


def test_h2_directory_close_attempts_every_handle_after_failure() -> None:
    ops = _DirectoryOps(close_failure="h:d1-n2-authority-v1")
    lease = DirectoryLease.acquire(ops, _paths()).lease
    assert lease is not None
    assert lease.close() is False
    assert ops.closed == list(reversed(lease.handles))


def test_h2_acquisition_preserves_primary_and_cleanup_failure() -> None:
    ops = _DirectoryOps(
        create_failure=APPLICATION_DIRECTORY_LEAF,
        close_failure="h:Local",
    )
    acquisition = DirectoryLease.acquire(ops, _paths())
    assert acquisition == DirectoryLeaseAcquisition(
        lease=None,
        failure=DirectoryAcquireFailure.CREATE_FAILED,
        cleanup_status=DirectoryCleanupStatus.CLEANUP_FAILED,
    )


def test_h2_acquisition_exception_closes_prior_tiers() -> None:
    ops = _DirectoryOps(raise_info="h:PDUExamObserver")
    acquisition = DirectoryLease.acquire(ops, _paths())
    assert acquisition.lease is None
    assert acquisition.failure is DirectoryAcquireFailure.OPERATION_FAILED
    assert ops.closed == ["h:PDUExamObserver", "h:Local"]


def test_h2_mutex_context_dual_failure_preserves_body_and_cleanup() -> None:
    class Stop(BaseException):
        pass

    class Ops:
        def __init__(self) -> None:
            self.closed = 0

        def acquire(self, _name: str) -> MutexStatus:
            return MutexStatus.ACQUIRED

        def release(self) -> bool:
            raise Stop("release")

        def close(self) -> bool:
            self.closed += 1
            return True

    ops = Ops()
    with pytest.raises(BaseExceptionGroup) as raised:
        with WindowsNamedMutex(ops) as mutex:
            assert mutex.acquire() is MutexStatus.ACQUIRED
            raise Stop("body")
    assert len(raised.value.exceptions) == 2
    assert ops.closed == 1


def test_h2_directory_context_cleanup_failure_is_explicit() -> None:
    ops = _DirectoryOps(close_failure="h:d1-n2-authority-v1")
    lease = DirectoryLease.acquire(ops, _paths()).lease
    assert lease is not None
    with pytest.raises(CleanupFailure):
        with lease:
            pass


class _Metadata:
    def __init__(self, identity_by_handle: dict[int, int]) -> None:
        self.identity_by_handle = identity_by_handle
        self.calls: list[tuple[object, ...]] = []
        self.argtypes: object = None
        self.restype: object = None

    def __call__(
        self,
        handle: int,
        info_class: int,
        buffer: object,
        _size: int,
    ) -> int:
        self.calls.append((handle, info_class, buffer, _size))
        if info_class == 9:
            value = ctypes.cast(
                buffer, ctypes.POINTER(store_module._FileAttributeTagInfo)
            ).contents
            value.file_attributes = 0x10
        elif info_class == 1:
            value = ctypes.cast(
                buffer, ctypes.POINTER(store_module._FileStandardInfo)
            ).contents
            value.number_of_links = 1
            value.directory = 1
            value.delete_pending = 0
        elif info_class == 18:
            value = ctypes.cast(
                buffer, ctypes.POINTER(store_module._FileIdInfo)
            ).contents
            value.volume_serial_number = self.identity_by_handle[handle]
            for index in range(16):
                value.file_id[index] = index
        else:
            return 0
        return 1


class _FinalPath:
    def __init__(self, paths: dict[int, str]) -> None:
        self.paths = paths
        self.argtypes: object = None
        self.restype: object = None

    def __call__(
        self, handle: int, buffer: object, size: int, _flags: int
    ) -> int:
        path = self.paths[handle]
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_wchar * size)).contents.value = path
        return len(path)


def _directory_kernel(
    *,
    durability_identity: int = 7,
    close_result: int = 1,
    lifetime_handle: int = 101,
    durability_handle: int = 202,
) -> object:
    handles = iter((lifetime_handle, durability_handle))
    kernel = type("Kernel", (), {})()
    kernel.CreateFileW = _Fn(lambda *_args: next(handles))
    kernel.CreateDirectoryW = _Fn(1)
    kernel.GetFileType = _Fn(1)
    kernel.GetFileInformationByHandleEx = _Metadata(
        {lifetime_handle: 7, durability_handle: durability_identity}
    )
    kernel.GetFinalPathNameByHandleW = _FinalPath(
        {lifetime_handle: r"C:\tier", durability_handle: r"C:\tier"}
    )
    kernel.FlushFileBuffers = _Fn(1)
    kernel.CloseHandle = _Fn(close_result)
    return kernel


def test_h2_ctypes_directory_exact_flags_metadata_and_durability() -> None:
    kernel = _directory_kernel()
    ops = CtypesDirectoryOps(kernel)
    handle = ops.open_existing(r"C:\tier")
    assert handle == 101
    info = ops.info(handle)
    assert info.disk and info.directory and not info.reparse
    assert info.final_path == r"C:\tier" and info.identity
    assert ops.flush_directory(handle) is True

    lifetime, durability = kernel.CreateFileW.calls
    expected_flags = 0x02000000 | 0x00200000
    assert lifetime[1:6] == (0x80 | 0x00100000, 0x3, None, 3, expected_flags)
    assert durability[0] == r"C:\tier"
    assert durability[1:6] == (
        0x40000000 | 0x00100000,
        0x3,
        None,
        3,
        expected_flags,
    )
    assert kernel.CloseHandle.calls == [(202,)]
    assert kernel.CreateFileW.restype is ctypes.c_void_p
    assert kernel.FlushFileBuffers.restype is ctypes.c_int32


@pytest.mark.parametrize(
    ("identity", "close_result"),
    [(8, 1), (7, 0)],
)
def test_h2_ctypes_directory_durability_identity_or_close_failure_rejects(
    identity: int, close_result: int
) -> None:
    kernel = _directory_kernel(
        durability_identity=identity,
        close_result=close_result,
    )
    ops = CtypesDirectoryOps(kernel)
    handle = ops.open_existing(r"C:\tier")
    assert handle == 101
    assert ops.flush_directory(handle) is False


def test_h2_ctypes_directory_high_handle_round_trips_and_invalid_rejects() -> None:
    high = 0x1_0000_0065
    kernel = _directory_kernel(lifetime_handle=high, durability_handle=high + 1)
    ops = CtypesDirectoryOps(kernel)
    assert ops.open_existing(r"C:\tier") == high
    invalid = _directory_kernel(lifetime_handle=ctypes.c_void_p(-1).value or -1)
    assert CtypesDirectoryOps(invalid).open_existing(r"C:\tier") is None


def test_h2_ctypes_create_child_uses_validated_parent_final_path_only() -> None:
    kernel = _directory_kernel()
    ops = CtypesDirectoryOps(kernel)
    parent = ops.open_existing(r"C:\tier")
    assert parent == 101
    assert ops.create_child(parent, "child") is True
    assert kernel.CreateDirectoryW.calls == [(r"C:\tier\child", None)]
    assert ops.create_child(parent, "..\\unsafe") is False
    assert len(kernel.CreateDirectoryW.calls) == 1


def test_h2_ctypes_create_child_api_failure_and_false_flush_reject() -> None:
    kernel = _directory_kernel()
    kernel.CreateDirectoryW = _Fn(0)
    kernel.FlushFileBuffers = _Fn(0)
    ops = CtypesDirectoryOps(kernel)
    parent = ops.open_existing(r"C:\tier")
    assert parent == 101
    assert ops.create_child(parent, "child") is False
    assert ops.flush_directory(parent) is False


@pytest.mark.parametrize(
    "invalid",
    [
        DirectoryInfo(False, False, True, r"C:\tier", "identity"),
        DirectoryInfo(True, True, True, r"C:\tier", "identity"),
        DirectoryInfo(True, False, False, r"C:\tier", "identity"),
        DirectoryInfo(True, False, True, r"C:\tier", ""),
    ],
)
def test_h2_ctypes_create_child_invalid_parent_metadata_never_calls_api(
    invalid: DirectoryInfo,
) -> None:
    kernel = _directory_kernel()
    ops = CtypesDirectoryOps(kernel)
    parent = ops.open_existing(r"C:\tier")
    assert parent == 101
    ops.info = lambda _handle: invalid  # type: ignore[method-assign]
    assert ops.create_child(parent, "child") is False
    assert kernel.CreateDirectoryW.calls == []


@pytest.mark.parametrize("reparse,directory", [(True, True), (False, False)])
def test_h2_ctypes_directory_durability_reopened_metadata_rejects(
    reparse: bool, directory: bool
) -> None:
    kernel = _directory_kernel()
    ops = CtypesDirectoryOps(kernel)
    handle = ops.open_existing(r"C:\tier")
    assert handle == 101
    source_info = ops.info(handle)
    reopened = DirectoryInfo(
        disk=True,
        reparse=reparse,
        directory=directory,
        final_path=r"C:\tier",
        identity=source_info.identity,
    )
    original_info = ops.info
    ops.info = lambda candidate: reopened if candidate == 202 else original_info(candidate)  # type: ignore[method-assign]
    assert ops.flush_directory(handle) is False
