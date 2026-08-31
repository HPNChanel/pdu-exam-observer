import ctypes
import hashlib

import pytest

import pdu_exam_observer.m2_d1_n2_win32 as win32
from pdu_exam_observer.m2_d1_n2_win32 import (
    MAX_AUTHORITY_RECORD_BYTES,
    CtypesHandleOps,
    HandleInfo,
    LeafFailure,
    SameHandleLeaf,
)


def test_h1_ctypes_adapter_exists_for_injected_abi() -> None:
    assert CtypesHandleOps


def test_h1a_adapter_exposes_the_full_handle_protocol() -> None:
    required = (
        "create_new",
        "open_existing",
        "info",
        "read",
        "seek_start",
        "write",
        "truncate",
        "flush",
        "close",
    )
    assert all(hasattr(CtypesHandleOps, name) for name in required)


def test_h1b_red_ctypes_open_uses_exact_exclusive_create_and_open_flags() -> None:
    class Fn:
        def __init__(self, value: int = 1) -> None:
            self.value, self.calls = value, []

        def __call__(self, *args: object) -> int:
            self.calls.append(args)
            return self.value

    class Kernel:
        def __init__(self) -> None:
            for name in (
                "CreateFileW", "GetFileType", "GetFileInformationByHandleEx",
                "GetFinalPathNameByHandleW", "ReadFile", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn())

    kernel = Kernel()
    adapter = CtypesHandleOps(kernel)
    assert adapter.create_new(r"C:\leaf") == 1
    assert adapter.open_existing(r"C:\leaf") == 1
    create, existing = kernel.CreateFileW.calls
    expected_access = 0x80000000 | 0x40000000 | 0x80 | 0x00100000
    expected_flags = 0x80 | 0x00200000 | 0x80000000
    assert create[1:6] == (expected_access, 0, None, 1, expected_flags)
    assert existing[1:6] == (expected_access, 0, None, 3, expected_flags)


def test_h1b_red_ctypes_info_decodes_disk_metadata_identity_and_final_path() -> None:
    class Fn:
        def __init__(self, value: int = 1) -> None:
            self.value, self.calls = value, []

        def __call__(self, *args: object) -> int:
            self.calls.append(args)
            return self.value

    class Metadata:
        def __init__(self) -> None:
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
                    buffer, ctypes.POINTER(win32._FileAttributeTagInfo)
                ).contents
                value.file_attributes = 0x80
                value.reparse_tag = 0
            elif info_class == 1:
                value = ctypes.cast(
                    buffer, ctypes.POINTER(win32._FileStandardInfo)
                ).contents
                value.end_of_file = 3
                value.number_of_links = 1
                value.delete_pending = 0
                value.directory = 0
            elif info_class == 18:
                value = ctypes.cast(
                    buffer, ctypes.POINTER(win32._FileIdInfo)
                ).contents
                value.volume_serial_number = 7
                for index in range(16):
                    value.file_id[index] = index
            else:
                return 0
            return 1

    class FinalPath:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []
            self.argtypes: object = None
            self.restype: object = None

        def __call__(
            self, handle: int, buffer: object, size: int, flags: int
        ) -> int:
            self.calls.append((handle, buffer, size, flags))
            path = r"C:\leaf"
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_wchar * size)).contents.value = path
            return len(path)

    class Kernel:
        def __init__(self) -> None:
            for name in (
                "CreateFileW", "ReadFile", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn())
            self.GetFileType = Fn(1)
            self.GetFileInformationByHandleEx = Metadata()
            self.GetFinalPathNameByHandleW = FinalPath()

    kernel = Kernel()
    info = CtypesHandleOps(kernel).info(73)
    assert info.disk is True
    assert info.reparse is False
    assert info.directory is False
    assert info.delete_pending is False
    assert info.links == 1
    assert info.final_path == r"C:\leaf"
    assert info.identity == hashlib.sha256(
        (7).to_bytes(8, "little") + bytes(range(16))
    ).hexdigest()
    assert info.size == 3
    assert kernel.GetFileInformationByHandleEx.calls
    assert kernel.GetFinalPathNameByHandleW.calls


@pytest.mark.parametrize(
    ("mutant", "expected"),
    [
        ({"path": r"C:\wrong"}, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"directory": True}, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"delete": True}, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"links": 2}, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"read": b"o"}, LeafFailure.READ_FAILED),
        ({"read": b"different"}, LeafFailure.STALE_CAS),
    ],
)
def test_h1b_red_transition_validation_matrix(
    mutant: dict[str, object], expected: LeafFailure
) -> None:
    result = SameHandleLeaf(FakeOps(**mutant), r"C:\x").transition(
        b"old",
        b"new",
        lambda value: value in {b"old", b"different", b"new"},
    )
    assert result.payload is None and result.failure is expected


def test_h1_review_red_bool_abi_is_win32_bool_and_handles_are_pointer_width() -> None:
    class Fn:
        def __call__(self, *_args: object) -> int:
            return 1

    class Kernel:
        def __init__(self) -> None:
            for name in (
                "CreateFileW", "GetFileType", "GetFileInformationByHandleEx",
                "GetFinalPathNameByHandleW", "ReadFile", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn())

    kernel = Kernel()
    CtypesHandleOps(kernel)
    for name in (
        "GetFileInformationByHandleEx", "ReadFile", "SetFilePointerEx", "WriteFile",
        "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
    ):
        assert getattr(kernel, name).restype is ctypes.c_int32
    assert kernel.CreateFileW.restype is ctypes.c_void_p
    assert kernel.ReadFile.argtypes[0] is ctypes.c_void_p


def test_h1_review_red_close_failure_overrides_invalid_metadata_once() -> None:
    class InvalidAndCloseFails(FakeOps):
        def __init__(self) -> None:
            super().__init__(reparse=True)
            self.close_calls = 0

        def close(self, handle: int) -> bool:
            assert handle == 1
            self.close_calls += 1
            return False

    ops = InvalidAndCloseFails()
    result = SameHandleLeaf(ops, r"C:\x").create(b"new", lambda value: bool(value))
    assert result.payload is None
    assert result.failure is LeafFailure.CLOSE_FAILED
    assert ops.close_calls == 1


def test_h1_review_red_ctypes_read_accumulates_scripted_chunks_on_one_handle() -> None:
    class Fn:
        def __call__(self, *_args: object) -> int:
            return 1

    class ReadFile:
        def __init__(self) -> None:
            self.chunks = [b"ab", b"c", b""]
            self.handles: list[int] = []

        def __call__(
            self,
            handle: int,
            buffer: object,
            _requested: int,
            count: object,
            _ov: object,
        ) -> int:
            self.handles.append(handle)
            chunk = self.chunks.pop(0)
            for index, value in enumerate(chunk):
                buffer[index] = value  # type: ignore[index]
            ctypes.cast(count, ctypes.POINTER(ctypes.c_uint32)).contents.value = len(chunk)
            return 1

    class Kernel:
        def __init__(self) -> None:
            for name in (
                "CreateFileW", "GetFileType", "GetFileInformationByHandleEx",
                "GetFinalPathNameByHandleW", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn())
            self.ReadFile = ReadFile()

    kernel = Kernel()
    assert CtypesHandleOps(kernel).read(91, 3) == b"abc"
    assert kernel.ReadFile.handles == [91, 91]


def test_h1_max_record_bound_exists() -> None:
    assert MAX_AUTHORITY_RECORD_BYTES > 0


class FakeOps:
    def __init__(self, **mutant: object) -> None:
        self.mutant = mutant
        self.data = bytearray(b"old")
        self.position = 0
        self.read_count = 0
        self.info_count = 0
        self.handles: list[int] = []
        self.close_count = 0

    def create_new(self, _path: str) -> int | None:
        return None if self.mutant.get("conflict") else 1

    def open_existing(self, _path: str) -> int | None:
        return 1

    def info(self, _handle: int) -> HandleInfo:
        self.handles.append(_handle)
        self.info_count += 1
        identity = "b" if self.mutant.get("identity_swap") and self.info_count > 1 else "a"
        return HandleInfo(
            True,
            bool(self.mutant.get("reparse")),
            bool(self.mutant.get("directory")),
            bool(self.mutant.get("delete")),
            int(self.mutant.get("links", 1)),
            str(self.mutant.get("path", "C:\\x")),
            str(self.mutant.get("identity", identity)),
            len(self.data),
        )

    def read(self, _handle: int, _limit: int) -> bytes | None:
        self.handles.append(_handle)
        self.read_count += 1
        if self.read_count > 1 and "readback" in self.mutant:
            return self.mutant["readback"]  # type: ignore[return-value]
        if "read" in self.mutant:
            return self.mutant["read"]  # type: ignore[return-value]
        value = bytes(self.data[self.position : _limit])
        self.position += len(value)
        return value

    def seek_start(self, _handle: int) -> bool:
        self.handles.append(_handle)
        self.position = 0
        return True

    def write(self, _handle: int, data: bytes) -> int:
        self.handles.append(_handle)
        if self.mutant.get("zero"):
            return 0
        count = min(len(data), int(self.mutant.get("short_write", len(data))))
        end = self.position + count
        if end > len(self.data):
            self.data.extend(b"\x00" * (end - len(self.data)))
        self.data[self.position : end] = data[:count]
        self.position = end
        return count

    def truncate(self, _handle: int) -> bool:
        self.handles.append(_handle)
        if not self.mutant.get("truncate"):
            del self.data[self.position :]
        return not self.mutant.get("truncate")

    def flush(self, _handle: int) -> bool:
        self.handles.append(_handle)
        return not self.mutant.get("flush")

    def close(self, _handle: int) -> bool:
        self.handles.append(_handle)
        self.close_count += 1
        return not self.mutant.get("close")


def test_h1_short_writes_complete_on_one_handle_and_close_once() -> None:
    ops = FakeOps(short_write=1)
    result = SameHandleLeaf(ops, r"C:\x").transition(
        b"old", b"new-value", lambda value: bool(value)
    )
    assert result.payload == b"new-value" and result.failure is None
    assert set(ops.handles) == {1}
    assert ops.close_count == 1


@pytest.mark.parametrize(
    ("mutant", "failure"),
    [
        ({"read": b""}, LeafFailure.READ_FAILED),
        ({"read": b"x" * (MAX_AUTHORITY_RECORD_BYTES + 1)}, LeafFailure.READ_FAILED),
        ({"readback": b"corrupt"}, LeafFailure.READBACK_FAILED),
        ({"identity_swap": True}, LeafFailure.IDENTITY_CHANGED),
    ],
)
def test_h1_read_and_identity_mutants_fail_closed(
    mutant: dict[str, object], failure: LeafFailure
) -> None:
    ops = FakeOps(**mutant)
    result = SameHandleLeaf(ops, r"C:\x").transition(
        b"old", b"new", lambda value: bool(value)
    )
    assert result.payload is None and result.failure is failure
    assert ops.close_count == 1


@pytest.mark.parametrize(
    "mutant,code",
    [
        ({"conflict": True}, LeafFailure.CREATE_CONFLICT),
        ({"reparse": True}, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"zero": True}, LeafFailure.WRITE_FAILED),
        ({"truncate": True}, LeafFailure.TRUNCATE_FAILED),
        ({"flush": True}, LeafFailure.FLUSH_FAILED),
        ({"close": True}, LeafFailure.CLOSE_FAILED),
    ],
)
def test_h1_fake_failures_suppress_payload(mutant: dict[str, object], code: LeafFailure) -> None:
    result = SameHandleLeaf(FakeOps(**mutant), "C:\\x").create(b"new", lambda value: bool(value))
    assert result.payload is None and result.failure is code


def test_h1_final_red_high_bit_handle_round_trips_and_invalid_handle_rejects() -> None:
    class Fn:
        def __init__(self, value: int) -> None:
            self.value = value

        def __call__(self, *_args: object) -> int:
            return self.value

    class Kernel:
        def __init__(self, value: int) -> None:
            for name in (
                "CreateFileW", "GetFileType", "GetFileInformationByHandleEx",
                "GetFinalPathNameByHandleW", "ReadFile", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn(value))

    high = 0x1_0000_0042
    assert CtypesHandleOps(Kernel(high)).create_new(r"C:\leaf") == high
    assert CtypesHandleOps(Kernel(high)).open_existing(r"C:\leaf") == high
    assert CtypesHandleOps(Kernel(ctypes.c_void_p(-1).value)).create_new(r"C:\leaf") is None


def test_h1_final_red_baseexception_close_failure_is_explicit_not_silent() -> None:
    class Stop(BaseException):
        pass

    class InterruptingOps(FakeOps):
        def __init__(self) -> None:
            super().__init__()
            self.close_count = 0

        def info(self, _handle: int) -> HandleInfo:
            raise Stop("stop")

        def close(self, _handle: int) -> bool:
            self.close_count += 1
            return False

    ops = InterruptingOps()
    with pytest.raises(BaseExceptionGroup) as raised:
        SameHandleLeaf(ops, "C:\\x").create(b"new", lambda value: bool(value))
    assert any(isinstance(error, Stop) for error in raised.value.exceptions)
    assert ops.close_count == 1


class _InspectOps:
    def __init__(self, **mutant: object) -> None:
        self.mutant = mutant
        self.handle = 0x1_0000_0042
        self.calls: list[tuple[str, int]] = []
        self.write_calls = 0
        self.truncate_calls = 0
        self.flush_calls = 0
        self.close_calls = 0
        self.info_calls = 0

    def create_new(self, _path: str) -> int | None:
        raise AssertionError("inspect must not create")

    def open_existing(self, path: str) -> int | None:
        raise AssertionError("inspect must not use the write-capable opener")

    def open_inspection(self, path: str) -> int | None:
        assert path == r"C:\\inspect"
        if self.mutant.get("open_error"):
            raise RuntimeError("open")
        return None if self.mutant.get("absent") else self.handle

    def info(self, handle: int) -> HandleInfo:
        self.calls.append(("info", handle))
        self.info_calls += 1
        if self.mutant.get("primary_baseexception"):
            raise _InspectStop()
        identity = (
            "changed"
            if self.mutant.get("identity_drift") and self.info_calls > 1
            else "stable"
        )
        return HandleInfo(
            disk=not bool(self.mutant.get("non_disk")),
            reparse=bool(self.mutant.get("reparse")),
            directory=False,
            delete_pending=bool(self.mutant.get("delete_pending")),
            links=int(self.mutant.get("links", 1)),
            final_path=str(self.mutant.get("path", r"C:\\inspect")),
            identity=identity,
            size=9,
        )

    def read(self, handle: int, limit: int) -> bytes | None:
        self.calls.append(("read", handle))
        assert limit == MAX_AUTHORITY_RECORD_BYTES + 1
        return self.mutant.get("read", b"canonical")  # type: ignore[return-value]

    def seek_start(self, handle: int) -> bool:
        self.calls.append(("seek", handle))
        return True

    def write(self, _handle: int, _data: bytes) -> int:
        self.write_calls += 1
        raise AssertionError("inspect must not write")

    def truncate(self, _handle: int) -> bool:
        self.truncate_calls += 1
        raise AssertionError("inspect must not truncate")

    def flush(self, _handle: int) -> bool:
        self.flush_calls += 1
        raise AssertionError("inspect must not flush")

    def close(self, handle: int) -> bool:
        self.calls.append(("close", handle))
        self.close_calls += 1
        return not bool(self.mutant.get("close"))


class _InspectStop(BaseException):
    pass


def test_h1i_inspect_returns_exact_payload_on_one_handle_without_mutation() -> None:
    ops = _InspectOps()
    result = SameHandleLeaf(ops, r"C:\\inspect").inspect(lambda value: value == b"canonical")
    assert result.payload == b"canonical"
    assert result.failure is None
    assert {handle for _, handle in ops.calls} == {ops.handle}
    assert ops.close_calls == 1
    assert ops.write_calls == ops.truncate_calls == ops.flush_calls == 0


@pytest.mark.parametrize(
    ("mutant", "codec", "failure"),
    [
        ({"absent": True}, lambda _value: True, LeafFailure.ABSENT),
        ({"open_error": True}, lambda _value: True, LeafFailure.OPEN_FAILED),
        ({"reparse": True}, lambda _value: True, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"non_disk": True}, lambda _value: True, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"delete_pending": True}, lambda _value: True, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"links": 2}, lambda _value: True, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"path": r"C:\\wrong"}, lambda _value: True, LeafFailure.HANDLE_VALIDATION_FAILED),
        ({"read": None}, lambda _value: True, LeafFailure.READ_FAILED),
        ({"read": b""}, lambda _value: True, LeafFailure.READ_FAILED),
        (
            {"read": b"x" * (MAX_AUTHORITY_RECORD_BYTES + 1)},
            lambda _value: True,
            LeafFailure.READ_FAILED,
        ),
        ({}, lambda _value: False, LeafFailure.CODEC_INVALID),
        ({"identity_drift": True}, lambda _value: True, LeafFailure.IDENTITY_CHANGED),
        ({"close": True}, lambda _value: True, LeafFailure.CLOSE_FAILED),
    ],
)
def test_h1i_inspect_failure_matrix_is_typed_and_never_mutates(
    mutant: dict[str, object],
    codec: object,
    failure: LeafFailure,
) -> None:
    ops = _InspectOps(**mutant)
    result = SameHandleLeaf(ops, r"C:\\inspect").inspect(codec)  # type: ignore[arg-type]
    assert result.payload is None
    assert result.failure is failure
    assert ops.write_calls == ops.truncate_calls == ops.flush_calls == 0
    assert ops.close_calls == (0 if mutant.get("absent") or mutant.get("open_error") else 1)


def test_h1i_inspect_preserves_primary_baseexception_and_close_failure() -> None:
    ops = _InspectOps(primary_baseexception=True, close=True)
    with pytest.raises(BaseExceptionGroup) as raised:
        SameHandleLeaf(ops, r"C:\\inspect").inspect(lambda _value: True)
    assert any(isinstance(error, _InspectStop) for error in raised.value.exceptions)
    assert ops.close_calls == 1


@pytest.mark.parametrize("last_error", [2, 3])
def test_h1i_ctypes_open_existing_maps_only_confirmed_missing_errors_to_absent(
    monkeypatch: pytest.MonkeyPatch, last_error: int
) -> None:
    class Fn:
        def __call__(self, *_args: object) -> int:
            return ctypes.c_void_p(-1).value  # type: ignore[return-value]

    class Kernel:
        def __init__(self) -> None:
            for name in (
                "CreateFileW", "GetFileType", "GetFileInformationByHandleEx",
                "GetFinalPathNameByHandleW", "ReadFile", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn())

    calls = 0

    def last_error_value() -> int:
        nonlocal calls
        calls += 1
        return last_error

    monkeypatch.setattr(win32.ctypes, "get_last_error", last_error_value)
    assert CtypesHandleOps(Kernel()).open_existing(r"C:\\missing") is None
    assert calls == 1


def test_h1i_ctypes_open_existing_raises_for_nonmissing_error_and_preserves_high_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Fn:
        def __init__(self, value: int) -> None:
            self.value = value

        def __call__(self, *_args: object) -> int:
            return self.value

    class Kernel:
        def __init__(self, value: int) -> None:
            for name in (
                "CreateFileW", "GetFileType", "GetFileInformationByHandleEx",
                "GetFinalPathNameByHandleW", "ReadFile", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn(value))

    monkeypatch.setattr(win32.ctypes, "get_last_error", lambda: 5)
    with pytest.raises(OSError) as raised:
        CtypesHandleOps(Kernel(ctypes.c_void_p(-1).value)).open_existing(r"C:\\denied")
    assert raised.value.errno == 5

    high = 0x1_0000_0042
    monkeypatch.setattr(
        win32.ctypes,
        "get_last_error",
        lambda: pytest.fail("high handle must not read last error"),
    )
    assert CtypesHandleOps(Kernel(high)).open_existing(r"C:\\leaf") == high


def test_h1i_ctypes_open_inspection_uses_read_only_open_abi() -> None:
    class Fn:
        def __init__(self, value: int = 73) -> None:
            self.value = value
            self.calls: list[tuple[object, ...]] = []

        def __call__(self, *args: object) -> int:
            self.calls.append(args)
            return self.value

    class Kernel:
        def __init__(self) -> None:
            for name in (
                "CreateFileW", "GetFileType", "GetFileInformationByHandleEx",
                "GetFinalPathNameByHandleW", "ReadFile", "SetFilePointerEx", "WriteFile",
                "SetEndOfFile", "FlushFileBuffers", "CloseHandle",
            ):
                setattr(self, name, Fn())

    kernel = Kernel()
    assert CtypesHandleOps(kernel).open_inspection(r"C:\\leaf") == 73
    create = kernel.CreateFileW.calls[-1]
    expected_access = 0x80000000 | 0x80 | 0x00100000
    expected_flags = 0x80 | 0x00200000
    assert create[1:6] == (expected_access, 0, None, 3, expected_flags)
    assert create[1] & 0x40000000 == 0


def test_h1i_inspection_and_transition_use_distinct_openers() -> None:
    class SplitOpenOps(FakeOps):
        def __init__(self) -> None:
            super().__init__()
            self.write_opens = 0
            self.read_opens = 0

        def open_existing(self, path: str) -> int | None:
            self.write_opens += 1
            return super().open_existing(path)

        def open_inspection(self, path: str) -> int | None:
            self.read_opens += 1
            return super().open_existing(path)

    ops = SplitOpenOps()
    assert SameHandleLeaf(ops, "C:\\x").transition(
        b"old", b"new", lambda value: bool(value)
    ).failure is None
    assert ops.write_opens == 1
    assert ops.read_opens == 0

    inspected = SameHandleLeaf(ops, "C:\\x").inspect(lambda value: value == b"new")
    assert inspected.payload == b"new"
    assert ops.write_opens == 1
    assert ops.read_opens == 1
