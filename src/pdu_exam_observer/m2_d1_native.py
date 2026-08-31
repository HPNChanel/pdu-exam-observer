"""D1-N1's fixed, video-only native preflight adapter.

This module deliberately has no route, browser, caller-supplied capture input, persistence, or
export surface. The public actions are parameter-free and are intended for one no-human preflight.
"""

from __future__ import annotations

import ctypes
import hashlib
import importlib.abc
import json
import math
import os
import queue
import re
import secrets
import socket
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from importlib import metadata, resources
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, cast

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 15
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 3
PREFLIGHT_SECONDS = 60
WARMUP_SECONDS = 5
WORKER_AUTHORIZATION_TIMEOUT_SECONDS = 10.0
WORKER_PRIVACY_READY_TIMEOUT_SECONDS = 30.0
WORKER_DEVICE_SETUP_TIMEOUT_SECONDS = 25.0
WORKER_FIRST_FRAME_TIMEOUT_SECONDS = 10.0
WORKER_CAPTURE_TIMEOUT_SECONDS = float(PREFLIGHT_SECONDS)
WORKER_GRANT_VALIDITY_SECONDS = 30
WORKER_CAPABILITY_BYTES = 32
WORKER_JOB_PREFIX = "Local\\PDUExamObserver.D1N1.Capture."
JOB_OBJECT_QUERY = 0x0004


def _windows_system_directory() -> str:
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        return str(Path(r"C:\Windows\System32"))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    kernel32.GetSystemDirectoryW.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32_768)
    length = kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if length == 0 or length >= len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    return str(Path(buffer.value).resolve(strict=True))


def _windows_local_app_data_directory() -> str:
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        return str(Path(os.environ.get("LOCALAPPDATA", ".")).resolve())
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.SHGetFolderPathW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_wchar_p,
    ]
    shell32.SHGetFolderPathW.restype = ctypes.c_long
    buffer = ctypes.create_unicode_buffer(32_768)
    result = shell32.SHGetFolderPathW(None, 0x001C, None, 0, buffer)
    if result != 0:
        raise OSError(f"SHGetFolderPathW failed with HRESULT 0x{result & 0xFFFFFFFF:08x}")
    return str(Path(buffer.value).resolve(strict=True))


WINDOWS_SYSTEM_DIRECTORY = _windows_system_directory()
LOCAL_APP_DATA_DIRECTORY = _windows_local_app_data_directory()
POWERSHELL_CANONICAL_PATH = str(
    (
        Path(WINDOWS_SYSTEM_DIRECTORY)
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    ).resolve(strict=os.name == "nt")
)
POWERSHELL_WORKING_DIRECTORY = WINDOWS_SYSTEM_DIRECTORY
WORKER_REPORT_TIMEOUT_SECONDS = 5.0
WORKER_MESSAGE_MAX_BYTES = 65_536
MEDIA_CLOSE_TIMEOUT_SECONDS = 2.0
LOCAL_DIRECTORY_NAME = "PDUExamObserver"
AUTHORITY_REVISION = "d1-n1-authority-v2"
DEPENDENCY_PIN = "mediapipe==1.0.1"
POSE_MODEL_SHA256 = "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a"
FACE_MODEL_SHA256 = "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f"
POSE_MODEL_BYTES = 5_777_746
FACE_MODEL_BYTES = 229_746
MUTEX_NAME = "Local\\PDUExamObserver.D1N1.VideoOnly"
AUTHORITY_MUTEX_NAME = "Local\\PDUExamObserver.D1N1.AuthorityV2"
FFMPEG_CANONICAL_PATH = (
    r"C:\\ProgramData\\chocolatey\\lib\\ffmpeg\\tools\\ffmpeg\\bin\\ffmpeg.exe"
)
WORKER_PROJECT_ROOT = Path(__file__).parents[2]
WORKER_SOURCE_ROOT = str(WORKER_PROJECT_ROOT / "src")
WORKER_SITE_PACKAGES = str(WORKER_PROJECT_ROOT / ".venv" / "Lib" / "site-packages")
WORKER_CANONICAL_PATH = str(
    Path(cast(str, getattr(sys, "_base_executable", sys.executable))).resolve()
)
WORKER_ARGUMENT = "--d1-n1-capture-worker-v1"
WORKER_CHALLENGE_ENV = "PDU_D1_N1_WORKER_CHALLENGE"
WORKER_BOOTSTRAP = (
    "import runpy,sys;"
    f"sys.path[:0]=[{WORKER_SOURCE_ROOT!r},{WORKER_SITE_PACKAGES!r}];"
    f"sys.argv=['pdu_exam_observer.m2_d1_native',{WORKER_ARGUMENT!r}];"
    "runpy.run_module('pdu_exam_observer.m2_d1_native',run_name='__main__')"
)
_AUDIO_ROOTS = frozenset({"sounddevice", "_sounddevice", "pyaudio", "soundcard", "portaudio"})
_ORIGINAL_SOCKET = socket.socket
_NETWORK_GUARD_ACTIVE = False
_OUTBOUND_NETWORK_ATTEMPTS = 0


class _AudioImportDenyFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self, fullname: str, path: Sequence[str] | None, target: ModuleType | None = None
    ) -> ModuleSpec | None:
        del path, target
        if fullname.split(".", 1)[0] in _AUDIO_ROOTS:
            raise ImportError("D1-N1 forbids audio-capable imports")
        return None


class _DisabledMediaPipeAudio(ModuleType):
    _allowed = frozenset({"__name__", "__package__", "__loader__", "__spec__", "DISABLED"})

    def __getattribute__(self, name: str) -> object:
        if name in _DisabledMediaPipeAudio._allowed:
            return super().__getattribute__(name)
        raise RuntimeError("MediaPipe audio namespace is disabled for D1-N1")

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"__name__", "__package__", "__loader__", "__spec__", "DISABLED"}:
            super().__setattr__(name, value)
            return
        raise RuntimeError("MediaPipe audio namespace is sealed for D1-N1")


def _install_audio_import_seal() -> bool:
    if any(name.split(".", 1)[0] in _AUDIO_ROOTS for name in sys.modules):
        return False
    name = "mediapipe.tasks.python.audio"
    disabled = sys.modules.get(name)
    if disabled is None:
        disabled = _DisabledMediaPipeAudio(name)
        disabled.__package__ = "mediapipe.tasks.python"
        disabled.DISABLED = True
        sys.modules[name] = disabled
    if not isinstance(disabled, _DisabledMediaPipeAudio) or disabled.DISABLED is not True:
        return False
    if not any(isinstance(finder, _AudioImportDenyFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _AudioImportDenyFinder())
    return not any(name.split(".", 1)[0] in _AUDIO_ROOTS for name in sys.modules)


def _is_loopback(address: object) -> bool:
    host = address[0] if isinstance(address, tuple) and address else None
    return host in {"127.0.0.1", "::1", "localhost"}


class _OutboundDenySocket(_ORIGINAL_SOCKET):
    def connect(self, address: object) -> None:
        global _OUTBOUND_NETWORK_ATTEMPTS
        if not _is_loopback(address):
            _OUTBOUND_NETWORK_ATTEMPTS += 1
            raise OSError("D1-N1 runtime denies outbound Python network connections")
        super().connect(cast(Any, address))

    def connect_ex(self, address: object) -> int:
        self.connect(address)
        return 0


def _install_network_guard() -> bool:
    global _NETWORK_GUARD_ACTIVE
    if socket.socket is not _OutboundDenySocket:
        socket.socket = _OutboundDenySocket  # type: ignore[misc]
    _NETWORK_GUARD_ACTIVE = socket.socket is _OutboundDenySocket
    return _NETWORK_GUARD_ACTIVE


def _runtime_prerequisites() -> tuple[bytes, bytes] | None:
    if not _install_audio_import_seal() or not _install_network_guard():
        return None
    if _OUTBOUND_NETWORK_ATTEMPTS != 0:
        return None
    try:
        package = resources.files("pdu_exam_observer")
        face = package.joinpath("assets/models/blaze_face_short_range.tflite").read_bytes()
        pose = package.joinpath("assets/models/pose_landmarker_lite.task").read_bytes()
        installed = metadata.version("mediapipe")
    except Exception:
        return None
    if (
        len(pose) != POSE_MODEL_BYTES
        or hashlib.sha256(pose).hexdigest() != POSE_MODEL_SHA256
        or len(face) != FACE_MODEL_BYTES
        or hashlib.sha256(face).hexdigest() != FACE_MODEL_SHA256
        or installed != "1.0.1"
    ):
        return None
    return face, pose


def _observed_runtime_binding() -> tuple[str, str, int, int, str | None]:
    try:
        package = resources.files("pdu_exam_observer")
        face = package.joinpath("assets/models/blaze_face_short_range.tflite").read_bytes()
        pose = package.joinpath("assets/models/pose_landmarker_lite.task").read_bytes()
        version = metadata.version("mediapipe")
    except Exception:
        return "", "", 0, 0, None
    return (
        hashlib.sha256(pose).hexdigest(),
        hashlib.sha256(face).hexdigest(),
        len(pose),
        len(face),
        version,
    )
FFMPEG_PREFIX = (
    "-hide_banner",
    "-nostdin",
    "-loglevel",
    "warning",
    "-f",
    "dshow",
    "-video_size",
    "1280x720",
    "-framerate",
    "15",
)


class NativeOutcome(StrEnum):
    PREPARED = "PREPARED"
    D1_N1_PREFLIGHT_PASS = "D1_N1_PREFLIGHT_PASS"
    NO_GO = "NO_GO"


class NativeFailure(StrEnum):
    INPUT_UNAVAILABLE = "INPUT_UNAVAILABLE"
    INPUT_MALFORMED = "INPUT_MALFORMED"
    FRAME_STALLED = "FRAME_STALLED"
    CLOCK_REGRESSION = "CLOCK_REGRESSION"
    POSE_ENGINE_UNAVAILABLE = "POSE_ENGINE_UNAVAILABLE"
    POSE_ENGINE_EXCEPTION = "POSE_ENGINE_EXCEPTION"
    POSE_OUTPUT_INVALID = "POSE_OUTPUT_INVALID"
    QUALITY_INSUFFICIENT = "QUALITY_INSUFFICIENT"
    PRIVACY_STOP = "PRIVACY_STOP"
    PRIVACY_GUARD_TIMEOUT = "PRIVACY_GUARD_TIMEOUT"
    REAUTHORIZATION_REQUIRED = "REAUTHORIZATION_REQUIRED"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"
    AUTHORITY_FINALIZATION_FAILED = "AUTHORITY_FINALIZATION_FAILED"
    EXECUTABLE_IDENTITY_UNAVAILABLE = "EXECUTABLE_IDENTITY_UNAVAILABLE"
    EXECUTABLE_LEASE_INCOMPATIBLE = "EXECUTABLE_LEASE_INCOMPATIBLE"
    FRAME_READER_EXCEPTION = "FRAME_READER_EXCEPTION"
    CAPTURE_RUNTIME_EXCEPTION = "CAPTURE_RUNTIME_EXCEPTION"
    CAPTURE_STARTUP_TIMEOUT = "CAPTURE_STARTUP_TIMEOUT"
    CLEANUP_INCOMPLETE = "CLEANUP_INCOMPLETE"
    WORKER_PROTOCOL_FAILURE = "WORKER_PROTOCOL_FAILURE"
    UNKNOWN_TECHNICAL_FAILURE = "UNKNOWN_TECHNICAL_FAILURE"


class DeviceGateDecision(StrEnum):
    UNVERIFIED = "UNVERIFIED"


class StageState(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class _ReaderDisposition(StrEnum):
    FRAME = "FRAME"
    EOF = "EOF"
    READ_EXCEPTION = "READ_EXCEPTION"
    INGRESS_CLOCK_EXCEPTION = "INGRESS_CLOCK_EXCEPTION"


class AuthorizationState(StrEnum):
    PENDING = "PENDING"
    PREPARED = "PREPARED"
    CONSUMED = "CONSUMED"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True, slots=True)
class CameraCandidate:
    friendly_name: str
    present: bool
    status_ok: bool


@dataclass(frozen=True, slots=True)
class PreparedAuthority:
    schema_version: int
    opaque_device_token: str
    authority_revision: str
    state: AuthorizationState
    ffmpeg_sha256: str
    ffmpeg_version: str
    ffmpeg_size_bytes: int
    ffmpeg_identity_digest: str
    authorization_nonce: str


@dataclass(frozen=True, slots=True)
class TerminalAuthority:
    schema_version: int
    authority_revision: str
    prepared_config_digest: str
    run_nonce: str
    receipt_core_digest: str
    outcome: str
    failure_code: str
    record_digest: str


@dataclass(frozen=True, slots=True)
class NativeReceipt:
    schema_version: int
    outcome: NativeOutcome
    failure_code: NativeFailure | None
    device_gate_decision: DeviceGateDecision
    d1_go: bool
    opaque_device_token: str | None
    ffmpeg_sha256: str | None
    ffmpeg_version: str | None
    prepared_ffmpeg_sha256: str | None
    prepared_ffmpeg_version: str | None
    prepared_ffmpeg_size_bytes: int | None
    prepared_ffmpeg_identity_digest: str | None
    ffmpeg_size_bytes: int | None
    ffmpeg_identity_digest: str | None
    ffmpeg_lease_verified: bool
    ffmpeg_lease_closed: bool
    fixed_argv_digest: str | None
    frame_bytes: int
    requested_duration_seconds: int
    warmup_seconds: int
    delivered_frames: int
    processed_frames: int
    dropped_explicit_frames: int
    failed_frames: int
    privacy_checked_frames: int
    privacy_stop_count: int
    face_detections: int
    pose_detections: int
    measured_total_seconds: float
    measured_post_warmup_seconds: float
    delivered_frames_per_second: float | None
    p95_ingress_gap_ms: float | None
    p95_pose_latency_ms: float | None
    p99_pose_latency_ms: float | None
    backlog_ms: float | None
    raw_retained: bool
    audio_requested: bool
    stages: tuple[StageState, StageState, StageState, StageState]
    mutex_released: bool
    child_terminated: bool
    pipe_closed: bool
    reader_stopped: bool
    worker_cleanup_complete: bool
    media_closed: bool
    capture_worker_supervised: bool
    capture_deadline_enforced: bool
    capture_job_drained: bool
    capture_worker_executable_sha256: str | None
    capture_worker_identity_digest: str | None
    capture_worker_lease_closed: bool
    source_sha256: str
    lock_sha256: str
    pose_model_sha256: str
    face_model_sha256: str
    pose_model_bytes: int
    face_model_bytes: int
    runtime_dependency_version: str | None
    prepared_config_digest: str | None
    dependency_pin: str
    offline: bool
    video_only: bool
    audio_seal_active: bool
    network_guard_active: bool
    outbound_network_attempts: int
    authority_consumed: bool
    received_frames: int
    warmup_frames: int
    post_attempted_frames: int
    post_successful_frames: int
    dropped_short_frames: int
    inference_failure_frames: int
    privacy_terminal_frames: int
    delivery_failure_frames: int
    post_elapsed_ns: int
    max_stall_gap_ns: int
    backlog_ns: int
    run_nonce: str | None
    terminal_receipt_digest: str | None
    terminal_state_digest: str | None
    result_digest: str

    def recompute_core_digest(self) -> str:
        return _digest(
            {
                name: getattr(self, name).value
                if isinstance(getattr(self, name), StrEnum)
                else [item.value for item in getattr(self, name)]
                if name == "stages"
                else getattr(self, name)
                for name in NativeReceipt.__dataclass_fields__
                if name
                not in {
                    "terminal_receipt_digest",
                    "terminal_state_digest",
                    "result_digest",
                }
            }
        )

    def recompute_digest(self) -> str:
        return _digest(
            {
                name: getattr(self, name).value
                if isinstance(getattr(self, name), StrEnum)
                else [item.value for item in getattr(self, name)]
                if name == "stages"
                else getattr(self, name)
                for name in NativeReceipt.__dataclass_fields__
                if name != "result_digest"
            }
        )


@dataclass(frozen=True, slots=True)
class WorkerGrant:
    schema_version: int
    state: str
    grant_id: str
    challenge_digest: str
    capability_digest: str
    consumed_authority_digest: str
    supervisor_executable_sha256: str
    worker_executable_sha256: str
    worker_identity_digest: str
    worker_argv_digest: str
    source_sha256: str
    lock_sha256: str
    pose_model_sha256: str
    face_model_sha256: str
    ffmpeg_sha256: str
    ffmpeg_version: str
    ffmpeg_size_bytes: int
    ffmpeg_identity_digest: str
    job_policy_digest: str
    issued_unix_ns: int
    expires_unix_ns: int
    record_digest: str

    def recompute_digest(self) -> str:
        return _digest(
            {
                name: getattr(self, name)
                for name in WorkerGrant.__dataclass_fields__
                if name != "record_digest"
            }
        )


class AuthorityStore(Protocol):
    def load(self) -> PreparedAuthority | None: ...

    def save(self, value: PreparedAuthority) -> None: ...

    def finalize(self, value: PreparedAuthority) -> bool: ...

    def consume(self, value: PreparedAuthority) -> bool: ...

    def issue_worker_grant(self, value: PreparedAuthority, grant: WorkerGrant) -> bool: ...

    def load_worker_grant(self) -> WorkerGrant | None: ...

    def revoke_worker_grant(self, grant: WorkerGrant) -> bool: ...

    def finalize_terminal(
        self,
        value: PreparedAuthority,
        *,
        run_nonce: str,
        receipt_core_digest: str,
        outcome: NativeOutcome,
        failure: NativeFailure | None,
    ) -> TerminalAuthority | None: ...

    def load_terminal(self) -> TerminalAuthority | None: ...


class NamedMutex(Protocol):
    def acquire(self) -> bool: ...

    def release(self) -> bool | None: ...


class RawPipe(Protocol):
    def readinto(self, buffer: bytearray) -> int: ...

    def close(self) -> None: ...


class _FrameReader:
    def __init__(
        self,
        pipe: RawPipe,
        buffers: tuple[bytearray, bytearray],
        monotonic_ns: Callable[[], int],
    ) -> None:
        self._pipe = pipe
        self._buffers = buffers
        self._monotonic_ns = monotonic_ns
        self._free: queue.Queue[int] = queue.Queue(maxsize=2)
        self._ready: queue.Queue[
            tuple[_ReaderDisposition, int, int | None, int | None]
        ] = queue.Queue(maxsize=2)
        self._free.put(0)
        self._free.put(1)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def next(self) -> tuple[_ReaderDisposition, int, int | None, int | None] | None:
        try:
            return self._ready.get(timeout=1.0)
        except queue.Empty:
            return None

    def release(self, index: int) -> None:
        self._free.put(index)

    def alive(self) -> bool:
        return self._thread.is_alive()

    def stop(self) -> bool:
        try:
            self._free.put_nowait(-1)
        except queue.Full:
            pass
        self._thread.join(timeout=1.0)
        return not self._thread.is_alive()

    def _run(self) -> None:
        while True:
            index = self._free.get()
            if index < 0:
                return
            try:
                count = self._pipe.readinto(self._buffers[index])
            except Exception:
                self._ready.put((_ReaderDisposition.READ_EXCEPTION, index, None, None))
                return
            if count == 0:
                self._ready.put((_ReaderDisposition.EOF, index, count, None))
                return
            ingress: int | None = None
            if count == FRAME_BYTES:
                try:
                    ingress = self._monotonic_ns()
                except Exception:
                    self._ready.put(
                        (_ReaderDisposition.INGRESS_CLOCK_EXCEPTION, index, count, None)
                    )
                    return
            self._ready.put((_ReaderDisposition.FRAME, index, count, ingress))


class VideoChild(Protocol):
    stdout: RawPipe

    def terminate(self) -> None: ...

    def wait(self, timeout: float) -> None: ...


class NativePlatform(Protocol):
    def camera_class_devices(self) -> tuple[CameraCandidate, ...]: ...

    def ffmpeg_authority(self) -> tuple[str, str, str]: ...

    def sha256_of_executable(self, executable: str) -> str: ...

    def named_mutex(self) -> NamedMutex: ...

    def launch_video_only(self, argv: tuple[str, ...]) -> VideoChild: ...

    def monotonic_ns(self) -> int: ...


class MediaRuntime(Protocol):
    def liveness(self) -> bool: ...

    def inspect_face(self, frame: memoryview, timestamp_ms: int) -> bool: ...

    def inspect_pose(self, frame: memoryview, timestamp_ms: int) -> bool: ...

    def close(self) -> None: ...


class FixedLocalAuthorityStore:
    """Fixed local single-use authority plus a durable terminal receipt commitment."""

    def __init__(self, root: Path | None = None) -> None:
        local = root if root is not None else Path(LOCAL_APP_DATA_DIRECTORY)
        self._root = local / LOCAL_DIRECTORY_NAME
        self._legacy_prepared_path = self._root / "d1-n1-prepared.v1.json"
        self._prepared_path = self._root / "d1-n1-prepared.v2.json"
        self._terminal_path = self._root / "d1-n1-terminal.v2.json"
        self._worker_grant_path = self._root / "d1-n1-worker-grant.v1.json"

    def load(self) -> PreparedAuthority | None:
        if self._legacy_prepared_path.exists():
            raise ValueError("legacy authority is present and cannot be migrated")
        if not self._prepared_path.is_file():
            return None
        try:
            raw = _strict_json_object(self._prepared_path)
            if not isinstance(raw, dict) or set(raw) != set(PreparedAuthority.__dataclass_fields__):
                raise ValueError("prepared authority fields are malformed")
            typed_raw = cast(dict[str, Any], dict(raw))
            typed_raw["state"] = AuthorizationState(cast(str, typed_raw["state"]))
            value = PreparedAuthority(**typed_raw)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("prepared authority is present but invalid") from None
        if not _prepared_is_valid(value):
            raise ValueError("prepared authority is present but invalid")
        return value

    def save(self, value: PreparedAuthority) -> None:
        with _authority_write_guard():
            if not _prepared_is_valid(value):
                raise ValueError("prepared authority is malformed")
            current = self.load()
            if current is not None:
                raise ValueError("authorization state is not absent")
            if os.path.lexists(self._terminal_path) or os.path.lexists(
                self._worker_grant_path
            ):
                raise ValueError("terminal or worker-grant authority already exists")
            self._root.mkdir(parents=True, exist_ok=True)
            _atomic_json_write(self._prepared_path, asdict(value))

    def finalize(self, value: PreparedAuthority) -> bool:
        with _authority_write_guard():
            current = self.load()
            if (
                current != value
                or value.state is not AuthorizationState.PENDING
                or os.path.lexists(self._terminal_path)
            ):
                return False
            prepared = replace(value, state=AuthorizationState.PREPARED)
            _atomic_json_write(self._prepared_path, asdict(prepared))
            return True

    def consume(self, value: PreparedAuthority) -> bool:
        with _authority_write_guard():
            current = self.load()
            if (
                current != value
                or value.state is not AuthorizationState.PREPARED
                or os.path.lexists(self._terminal_path)
            ):
                return False
            consumed = replace(value, state=AuthorizationState.CONSUMED)
            _atomic_json_write(self._prepared_path, asdict(consumed))
            return True

    def issue_worker_grant(self, value: PreparedAuthority, grant: WorkerGrant) -> bool:
        with _authority_write_guard():
            current = self.load()
            if (
                current != replace(value, state=AuthorizationState.CONSUMED)
                or os.path.lexists(self._terminal_path)
                or os.path.lexists(self._worker_grant_path)
                or not _worker_grant_is_valid(grant, allow_revoked=False)
                or grant.consumed_authority_digest != _digest(asdict(current))
            ):
                return False
            try:
                _atomic_json_write(
                    self._worker_grant_path, asdict(grant), create_only=True
                )
            except Exception:
                return False
            return self.load_worker_grant() == grant

    def load_worker_grant(self) -> WorkerGrant | None:
        if not os.path.lexists(self._worker_grant_path):
            return None
        try:
            if not stat.S_ISREG(self._worker_grant_path.lstat().st_mode):
                raise ValueError("worker grant is not a regular file")
            raw = _strict_json_object(self._worker_grant_path)
            if set(raw) != set(WorkerGrant.__dataclass_fields__):
                raise ValueError("worker grant fields are malformed")
            grant = WorkerGrant(**cast(dict[str, Any], raw))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("worker grant is present but invalid") from None
        if not _worker_grant_is_valid(grant, allow_revoked=True):
            raise ValueError("worker grant is present but invalid")
        return grant

    def revoke_worker_grant(self, grant: WorkerGrant) -> bool:
        with _authority_write_guard():
            observed = self.load_worker_grant()
            if observed is None:
                return False
            if observed.state == "REVOKED":
                return observed.grant_id == grant.grant_id
            if observed != grant:
                return False
            revoked = replace(grant, state="REVOKED", record_digest="")
            revoked = replace(revoked, record_digest=revoked.recompute_digest())
            try:
                _atomic_json_write(self._worker_grant_path, asdict(revoked))
            except Exception:
                return False
            return self.load_worker_grant() == revoked

    def finalize_terminal(
        self,
        value: PreparedAuthority,
        *,
        run_nonce: str,
        receipt_core_digest: str,
        outcome: NativeOutcome,
        failure: NativeFailure | None,
    ) -> TerminalAuthority | None:
        with _authority_write_guard():
            current = self.load()
            expected = replace(value, state=AuthorizationState.CONSUMED)
            if current != expected or os.path.lexists(self._terminal_path):
                return None
            if (
                not _is_nonce(run_nonce)
                or not _is_digest(receipt_core_digest)
                or outcome is NativeOutcome.PREPARED
                or (outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS and failure is not None)
                or (outcome is NativeOutcome.NO_GO and failure is None)
            ):
                return None
            core: dict[str, Any] = {
                "schema_version": 2,
                "authority_revision": AUTHORITY_REVISION,
                "prepared_config_digest": _digest(asdict(value)),
                "run_nonce": run_nonce,
                "receipt_core_digest": receipt_core_digest,
                "outcome": outcome.value,
                "failure_code": failure.value if failure is not None else "NONE",
            }
            terminal = TerminalAuthority(**core, record_digest=_digest(core))
            try:
                _atomic_json_write(self._terminal_path, asdict(terminal), create_only=True)
            except Exception:
                observed = self.load_terminal()
                return terminal if observed == terminal else None
            return terminal

    def load_terminal(self) -> TerminalAuthority | None:
        if not os.path.lexists(self._terminal_path):
            return None
        try:
            if not stat.S_ISREG(self._terminal_path.lstat().st_mode):
                raise ValueError("terminal authority is not a regular file")
            raw = _strict_json_object(self._terminal_path)
            if set(raw) != set(TerminalAuthority.__dataclass_fields__):
                raise ValueError("terminal authority fields are malformed")
            terminal = TerminalAuthority(**cast(dict[str, Any], raw))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("terminal authority is present but invalid") from None
        core = {
            name: getattr(terminal, name)
            for name in TerminalAuthority.__dataclass_fields__
            if name != "record_digest"
        }
        if (
            terminal.schema_version != 2
            or terminal.authority_revision != AUTHORITY_REVISION
            or not _is_digest(terminal.prepared_config_digest)
            or not _is_nonce(terminal.run_nonce)
            or not _is_digest(terminal.receipt_core_digest)
            or terminal.outcome
            not in {NativeOutcome.D1_N1_PREFLIGHT_PASS.value, NativeOutcome.NO_GO.value}
            or (
                terminal.outcome == NativeOutcome.D1_N1_PREFLIGHT_PASS.value
                and terminal.failure_code != "NONE"
            )
            or (
                terminal.outcome == NativeOutcome.NO_GO.value
                and terminal.failure_code not in {item.value for item in NativeFailure}
            )
            or terminal.record_digest != _digest(core)
        ):
            raise ValueError("terminal authority is present but invalid")
        return terminal


class FixedWorkerGrantReader:
    """Read-only view of the nonsensitive durable worker-issuance record."""

    def __init__(self, root: Path | None = None) -> None:
        local = root if root is not None else Path(LOCAL_APP_DATA_DIRECTORY)
        self._path = local / LOCAL_DIRECTORY_NAME / "d1-n1-worker-grant.v1.json"

    def load(self) -> WorkerGrant | None:
        if not os.path.lexists(self._path):
            return None
        try:
            if not stat.S_ISREG(self._path.lstat().st_mode):
                raise ValueError("worker grant is not a regular file")
            raw = _strict_json_object(self._path)
            if set(raw) != set(WorkerGrant.__dataclass_fields__):
                raise ValueError("worker grant fields are malformed")
            grant = WorkerGrant(**cast(dict[str, Any], raw))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("worker grant is present but invalid") from None
        if not _worker_grant_is_valid(grant, allow_revoked=False):
            raise ValueError("worker grant is not launchable")
        return grant


class WindowsNamedMutex:
    def __init__(self, name: str = MUTEX_NAME) -> None:
        self._handle: int | None = None
        self._name = name
        self._kernel32: Any | None = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return False
        if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle_type = ctypes.c_void_p
        dword = ctypes.c_ulong
        bool_type = ctypes.c_int
        kernel32.CreateMutexW.argtypes = [handle_type, bool_type, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = handle_type
        kernel32.WaitForSingleObject.argtypes = [handle_type, dword]
        kernel32.WaitForSingleObject.restype = dword
        kernel32.ReleaseMutex.argtypes = [handle_type]
        kernel32.ReleaseMutex.restype = bool_type
        kernel32.CloseHandle.argtypes = [handle_type]
        kernel32.CloseHandle.restype = bool_type
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            return False
        wait = kernel32.WaitForSingleObject(handle, 0)
        if wait not in {0, 0x80}:
            if handle:
                kernel32.CloseHandle(handle)
            return False
        self._handle = int(handle)
        self._kernel32 = kernel32
        return True

    def release(self) -> bool:
        if self._handle is None or self._kernel32 is None:
            return False
        kernel32 = self._kernel32
        released = bool(kernel32.ReleaseMutex(self._handle))
        closed = bool(kernel32.CloseHandle(self._handle))
        self._handle = None
        self._kernel32 = None
        if not released or not closed:
            raise OSError("video-owner mutex cleanup failed")
        return True


@dataclass(frozen=True, slots=True)
class FfmpegBinding:
    sha256: str
    size_bytes: int
    identity_digest: str
    version_output_sha256: str


class WindowsExecutableLease:
    """Deny-write/delete lease held across binding, suspended launch, and child cleanup."""

    _GENERIC_READ = 0x80000000
    _FILE_READ_ATTRIBUTES = 0x80
    _SYNCHRONIZE = 0x00100000
    _FILE_SHARE_READ = 0x1
    _OPEN_EXISTING = 3
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _CREATE_SUSPENDED = 0x00000004
    _CREATE_NO_WINDOW = 0x08000000
    _TH32CS_SNAPTHREAD = 0x00000004
    _THREAD_SUSPEND_RESUME = 0x0002
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _canonical_path = FFMPEG_CANONICAL_PATH
    _identity_namespace = "ffmpeg-file-id-v1"
    _display_name = "FFmpeg"

    class _FileIdInfo(ctypes.Structure):
        _fields_ = [
            ("volume_serial", ctypes.c_ulonglong),
            ("file_id", ctypes.c_ubyte * 16),
        ]

    class _FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [("file_attributes", ctypes.c_ulong), ("reparse_tag", ctypes.c_ulong)]

    class _FileStandardInfo(ctypes.Structure):
        _fields_ = [
            ("allocation_size", ctypes.c_longlong),
            ("end_of_file", ctypes.c_longlong),
            ("number_of_links", ctypes.c_ulong),
            ("delete_pending", ctypes.c_ubyte),
            ("directory", ctypes.c_ubyte),
        ]

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("cntUsage", ctypes.c_ulong),
            ("th32ThreadID", ctypes.c_ulong),
            ("th32OwnerProcessID", ctypes.c_ulong),
            ("tpBasePri", ctypes.c_long),
            ("tpDeltaPri", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong),
        ]

    def __init__(self) -> None:
        if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
            raise OSError("Windows executable identity is unavailable")
        path = self._canonical_path
        self._path = str(Path(path).resolve(strict=True))
        if os.path.normcase(self._path) != os.path.normcase(str(Path(path))):
            raise OSError(f"{self._display_name} canonical path is indirect")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_api()
        self._ancestor_handles: list[int] = []
        self._handle: int | None = None
        self._image_verified = False
        try:
            self._open_ancestors()
            self._handle = self._open_handle(
                self._path,
                self._GENERIC_READ | self._FILE_READ_ATTRIBUTES | self._SYNCHRONIZE,
                self._FILE_FLAG_OPEN_REPARSE_POINT | self._FILE_FLAG_SEQUENTIAL_SCAN,
            )
            size = self._validate_handle(self._handle, expect_directory=False)
            final_path = self._final_path(self._handle)
            if os.path.normcase(final_path) != os.path.normcase(self._path):
                raise OSError(f"{self._display_name} final path mismatch")
            identity = self._identity(self._handle)
            digest = self._hash_handle(self._handle)
            identity_digest = _digest(
                [self._identity_namespace, identity[0], identity[1].hex(), size]
            )
            self._binding = FfmpegBinding(digest, size, identity_digest, "")
            self._initial_identity = identity
        except Exception:
            self.close()
            raise

    @property
    def binding(self) -> FfmpegBinding:
        return self._binding

    @property
    def image_verified(self) -> bool:
        return self._image_verified

    @property
    def executable(self) -> str:
        return self._path

    def probe_version(self) -> FfmpegBinding:
        argv = (self._path, "-hide_banner", "-nostdin", "-version")
        child = self._launch_suspended(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            output, _ = child.communicate(timeout=10.0)
        except Exception:
            child.kill()
            child.wait(timeout=2.0)
            raise
        if (
            child.returncode != 0
            or not isinstance(output, bytes)
            or not output.startswith(b"ffmpeg version ")
            or len(output) > 65_536
        ):
            raise OSError("FFmpeg version evidence is invalid")
        self._recheck()
        self._binding = replace(
            self._binding, version_output_sha256=hashlib.sha256(output).hexdigest()
        )
        return self._binding

    def launch_video_only(self, argv: tuple[str, ...]) -> VideoChild:
        if not argv or os.path.normcase(argv[0]) != os.path.normcase(self._path):
            raise OSError("FFmpeg launch path is not leased")
        child = self._launch_suspended(
            argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        if child.stdout is None:
            child.kill()
            child.wait(timeout=2.0)
            raise OSError("video pipe was not created")
        self._recheck()
        return cast(VideoChild, child)

    def close(self) -> bool:
        success = True
        if getattr(self, "_handle", None) is not None:
            success = bool(self._kernel32.CloseHandle(self._handle)) and success
            self._handle = None
        for handle in reversed(getattr(self, "_ancestor_handles", [])):
            success = bool(self._kernel32.CloseHandle(handle)) and success
        self._ancestor_handles = []
        return success

    def _configure_api(self) -> None:
        handle = ctypes.c_void_p
        dword = ctypes.c_ulong
        self._kernel32.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            dword,
            dword,
            handle,
            dword,
            dword,
            handle,
        ]
        self._kernel32.CreateFileW.restype = ctypes.c_void_p
        self._kernel32.CloseHandle.argtypes = [handle]
        self._kernel32.CloseHandle.restype = ctypes.c_int
        self._kernel32.GetCurrentProcess.restype = handle
        self._kernel32.DuplicateHandle.argtypes = [
            handle,
            handle,
            handle,
            ctypes.POINTER(handle),
            dword,
            ctypes.c_bool,
            dword,
        ]
        self._kernel32.SetFilePointerEx.argtypes = [
            handle,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            dword,
        ]
        self._kernel32.GetFinalPathNameByHandleW.argtypes = [
            handle,
            ctypes.c_wchar_p,
            dword,
            dword,
        ]
        self._kernel32.GetFinalPathNameByHandleW.restype = dword
        self._kernel32.GetFileInformationByHandleEx.argtypes = [
            handle,
            ctypes.c_int,
            handle,
            dword,
        ]
        self._kernel32.GetFileInformationByHandleEx.restype = ctypes.c_int
        self._kernel32.QueryFullProcessImageNameW.argtypes = [
            handle,
            dword,
            ctypes.c_wchar_p,
            ctypes.POINTER(dword),
        ]
        self._kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
        self._kernel32.CreateToolhelp32Snapshot.argtypes = [dword, dword]
        self._kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        self._kernel32.Thread32First.argtypes = [handle, ctypes.POINTER(self._ThreadEntry)]
        self._kernel32.Thread32First.restype = ctypes.c_int
        self._kernel32.Thread32Next.argtypes = [handle, ctypes.POINTER(self._ThreadEntry)]
        self._kernel32.Thread32Next.restype = ctypes.c_int
        self._kernel32.OpenThread.argtypes = [dword, ctypes.c_int, dword]
        self._kernel32.OpenThread.restype = ctypes.c_void_p
        self._kernel32.ResumeThread.argtypes = [handle]
        self._kernel32.ResumeThread.restype = dword

    def _open_ancestors(self) -> None:
        target = Path(self._path)
        parents = [parent for parent in reversed(target.parents) if str(parent) != target.anchor]
        for parent in parents:
            handle = self._open_handle(
                str(parent),
                self._FILE_READ_ATTRIBUTES | self._SYNCHRONIZE,
                self._FILE_FLAG_BACKUP_SEMANTICS | self._FILE_FLAG_OPEN_REPARSE_POINT,
            )
            self._ancestor_handles.append(handle)
            self._validate_handle(handle, expect_directory=True)

    def _open_handle(self, path: str, access: int, flags: int) -> int:
        handle = self._kernel32.CreateFileW(
            path,
            access,
            self._FILE_SHARE_READ,
            None,
            self._OPEN_EXISTING,
            flags,
            None,
        )
        value = int(handle) if handle else 0
        if not value or value == self._INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    def _final_path(self, handle: int) -> str:
        size = self._kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not size:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(size + 1)
        if not self._kernel32.GetFinalPathNameByHandleW(handle, buffer, size + 1, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        value = buffer.value
        return value[4:] if value.startswith("\\\\?\\") else value

    def _identity(self, handle: int) -> tuple[int, bytes]:
        info = self._FileIdInfo()
        if not self._kernel32.GetFileInformationByHandleEx(
            handle, 18, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(info.volume_serial), bytes(info.file_id)

    def _validate_handle(self, handle: int, *, expect_directory: bool) -> int:
        attributes = self._FileAttributeTagInfo()
        if not self._kernel32.GetFileInformationByHandleEx(
            handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if attributes.file_attributes & 0x400:
            raise OSError("leased FFmpeg topology contains a reparse point")
        standard = self._FileStandardInfo()
        if not self._kernel32.GetFileInformationByHandleEx(
            handle, 1, ctypes.byref(standard), ctypes.sizeof(standard)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if bool(standard.directory) is not expect_directory or standard.delete_pending:
            raise OSError("leased FFmpeg object type is invalid")
        return int(standard.end_of_file)

    def _hash_handle(self, handle: int) -> str:
        import msvcrt

        if not self._kernel32.SetFilePointerEx(handle, 0, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        current = self._kernel32.GetCurrentProcess()
        duplicate = ctypes.c_void_p()
        if not self._kernel32.DuplicateHandle(
            current, handle, current, ctypes.byref(duplicate), 0, False, 2
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        duplicate_value = duplicate.value
        if duplicate_value is None:
            raise OSError("FFmpeg lease duplication returned no handle")
        fd = msvcrt.open_osfhandle(duplicate_value, os.O_RDONLY)
        with os.fdopen(fd, "rb", closefd=True) as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def _query_process_path(self, child: subprocess.Popen[bytes]) -> str:
        size = ctypes.c_ulong(32_768)
        buffer = ctypes.create_unicode_buffer(size.value)
        handle = int(child._handle)  # type: ignore[attr-defined]
        if not self._kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.value

    def _verify_process_image(self, child: subprocess.Popen[bytes]) -> None:
        reported = self._query_process_path(child)
        if os.path.normcase(reported) != os.path.normcase(self._path):
            raise OSError("suspended process image mismatch")
        image_handle = self._open_handle(
            reported,
            self._GENERIC_READ | self._FILE_READ_ATTRIBUTES | self._SYNCHRONIZE,
            self._FILE_FLAG_OPEN_REPARSE_POINT | self._FILE_FLAG_SEQUENTIAL_SCAN,
        )
        try:
            self._validate_handle(image_handle, expect_directory=False)
            if self._identity(image_handle) != self._initial_identity:
                raise OSError("suspended process file identity mismatch")
        finally:
            if not self._kernel32.CloseHandle(image_handle):
                raise OSError("suspended process image handle cleanup failed")

    def _resume(self, pid: int) -> None:
        snapshot = self._kernel32.CreateToolhelp32Snapshot(self._TH32CS_SNAPTHREAD, 0)
        value = int(snapshot) if snapshot else 0
        if not value or value == self._INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        resumed = 0
        cleanup_failed = False
        try:
            entry = self._ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            ok = self._kernel32.Thread32First(value, ctypes.byref(entry))
            while ok:
                if entry.th32OwnerProcessID == pid:
                    thread = self._kernel32.OpenThread(
                        self._THREAD_SUSPEND_RESUME, False, entry.th32ThreadID
                    )
                    if thread:
                        try:
                            if self._kernel32.ResumeThread(thread) != 0xFFFFFFFF:
                                resumed += 1
                        finally:
                            thread_close_failed = not bool(
                                self._kernel32.CloseHandle(thread)
                            )
                            cleanup_failed = thread_close_failed or cleanup_failed
                ok = self._kernel32.Thread32Next(value, ctypes.byref(entry))
        finally:
            cleanup_failed = not bool(self._kernel32.CloseHandle(value)) or cleanup_failed
        if resumed != 1 or cleanup_failed:
            raise OSError("suspended FFmpeg thread identity is unavailable")

    def _launch_suspended(
        self,
        argv: tuple[str, ...],
        *,
        stdin: int = subprocess.DEVNULL,
        stdout: int,
        stderr: int,
        before_resume: Callable[[subprocess.Popen[bytes]], None] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> subprocess.Popen[bytes]:
        child = subprocess.Popen(
            argv,
            executable=self._path,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            shell=False,
            close_fds=True,
            creationflags=self._CREATE_SUSPENDED | self._CREATE_NO_WINDOW,
            bufsize=0,
            env=env,
            cwd=cwd,
        )
        try:
            self._verify_process_image(child)
            self._recheck()
            if before_resume is not None:
                before_resume(child)
            self._resume(child.pid)
            self._image_verified = True
            return child
        except Exception:
            child.kill()
            child.wait(timeout=2.0)
            raise

    def _recheck(self) -> None:
        if self._handle is None:
            raise OSError("FFmpeg lease is closed")
        if self._identity(self._handle) != self._initial_identity:
            raise OSError("FFmpeg file identity changed")
        if self._hash_handle(self._handle) != self._binding.sha256:
            raise OSError("FFmpeg bytes changed")


class _WindowsWorkerExecutableLease(WindowsExecutableLease):
    """Fixed worker-image lease; it has no caller-selected executable surface."""

    _canonical_path = WORKER_CANONICAL_PATH
    _identity_namespace = "d1-n1-worker-file-id-v1"
    _display_name = "D1-N1 worker"


class _WindowsPowerShellExecutableLease(WindowsExecutableLease):
    """System-directory PowerShell lease with process-image verification."""

    _canonical_path = POWERSHELL_CANONICAL_PATH
    _identity_namespace = "d1-n1-powershell-file-id-v1"
    _display_name = "Windows PowerShell"


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("per_process_user_time_limit", ctypes.c_longlong),
        ("per_job_user_time_limit", ctypes.c_longlong),
        ("limit_flags", ctypes.c_ulong),
        ("minimum_working_set_size", ctypes.c_size_t),
        ("maximum_working_set_size", ctypes.c_size_t),
        ("active_process_limit", ctypes.c_ulong),
        ("affinity", ctypes.c_size_t),
        ("priority_class", ctypes.c_ulong),
        ("scheduling_class", ctypes.c_ulong),
    ]


class _JobIoCounters(ctypes.Structure):
    _fields_ = [
        ("read_operation_count", ctypes.c_ulonglong),
        ("write_operation_count", ctypes.c_ulonglong),
        ("other_operation_count", ctypes.c_ulonglong),
        ("read_transfer_count", ctypes.c_ulonglong),
        ("write_transfer_count", ctypes.c_ulonglong),
        ("other_transfer_count", ctypes.c_ulonglong),
    ]


class _JobExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("basic_limit_information", _JobBasicLimitInformation),
        ("io_info", _JobIoCounters),
        ("process_memory_limit", ctypes.c_size_t),
        ("job_memory_limit", ctypes.c_size_t),
        ("peak_process_memory_used", ctypes.c_size_t),
        ("peak_job_memory_used", ctypes.c_size_t),
    ]


class _JobBasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("total_user_time", ctypes.c_longlong),
        ("total_kernel_time", ctypes.c_longlong),
        ("this_period_total_user_time", ctypes.c_longlong),
        ("this_period_total_kernel_time", ctypes.c_longlong),
        ("total_page_fault_count", ctypes.c_ulong),
        ("total_processes", ctypes.c_ulong),
        ("active_processes", ctypes.c_ulong),
        ("total_terminated_processes", ctypes.c_ulong),
    ]


def _worker_job_name(challenge: str) -> str:
    if not _is_nonce(challenge):
        raise ValueError("worker challenge is malformed")
    return WORKER_JOB_PREFIX + challenge


def _current_process_in_expected_worker_job(challenge: str) -> bool:
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenJobObjectW.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.OpenJobObjectW.restype = ctypes.c_void_p
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.IsProcessInJob.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    kernel32.IsProcessInJob.restype = ctypes.c_int
    kernel32.QueryInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    kernel32.QueryInformationJobObject.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    try:
        handle = kernel32.OpenJobObjectW(JOB_OBJECT_QUERY, False, _worker_job_name(challenge))
    except (OSError, ValueError):
        return False
    if not handle:
        return False
    try:
        in_job = ctypes.c_int(0)
        if not kernel32.IsProcessInJob(
            kernel32.GetCurrentProcess(), handle, ctypes.byref(in_job)
        ):
            return False
        limits = _JobExtendedLimitInformation()
        if not kernel32.QueryInformationJobObject(
            handle,
            9,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
            None,
        ):
            return False
        required = 0x00000008 | 0x00002000
        return (
            in_job.value == 1
            and limits.basic_limit_information.limit_flags & required == required
            and limits.basic_limit_information.active_process_limit == 2
        )
    finally:
        kernel32.CloseHandle(handle)


class _WindowsCaptureJob:
    """A two-process job: one capture worker and at most one native descendant."""

    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _SYNCHRONIZE = 0x00100000
    _JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1

    def __init__(self, name: str | None = None) -> None:
        if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
            raise OSError("Windows Job Object support is unavailable")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_api()
        ctypes.set_last_error(0)
        handle = self._kernel32.CreateJobObjectW(None, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if name is not None and ctypes.get_last_error() == 183:
            self._kernel32.CloseHandle(handle)
            raise OSError("capture job name already exists")
        self._handle: int | None = int(handle)
        self._process_handle: int | None = None
        self.assigned = False
        limits = _JobExtendedLimitInformation()
        limits.basic_limit_information.limit_flags = (
            self._JOB_OBJECT_LIMIT_ACTIVE_PROCESS | self._JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        limits.basic_limit_information.active_process_limit = 2
        if not self._kernel32.SetInformationJobObject(
            self._handle,
            self._JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def _configure_api(self) -> None:
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self._kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        self._kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self._kernel32.SetInformationJobObject.restype = ctypes.c_int
        self._kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        self._kernel32.IsProcessInJob.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._kernel32.IsProcessInJob.restype = ctypes.c_int
        self._kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self._kernel32.TerminateJobObject.restype = ctypes.c_int
        self._kernel32.QueryInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        self._kernel32.QueryInformationJobObject.restype = ctypes.c_int
        self._kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        self._kernel32.OpenProcess.restype = ctypes.c_void_p
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.CloseHandle.restype = ctypes.c_int

    def assign(self, child: subprocess.Popen[bytes]) -> None:
        if self._handle is None or self._process_handle is not None:
            raise OSError("capture job assignment state is invalid")
        access = (
            self._PROCESS_TERMINATE
            | self._PROCESS_SET_QUOTA
            | self._PROCESS_QUERY_LIMITED_INFORMATION
            | self._SYNCHRONIZE
        )
        process = self._kernel32.OpenProcess(access, False, child.pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        value = int(process)
        try:
            if not self._kernel32.AssignProcessToJobObject(self._handle, value):
                raise ctypes.WinError(ctypes.get_last_error())
            in_job = ctypes.c_int(0)
            if not self._kernel32.IsProcessInJob(value, self._handle, ctypes.byref(in_job)):
                raise ctypes.WinError(ctypes.get_last_error())
            if in_job.value != 1:
                raise OSError("capture worker is outside the watchdog job")
        except Exception:
            self._kernel32.CloseHandle(value)
            raise
        self._process_handle = value
        self.assigned = True

    def active_processes(self) -> int:
        if self._handle is None:
            raise OSError("capture job is closed")
        accounting = _JobBasicAccountingInformation()
        if not self._kernel32.QueryInformationJobObject(
            self._handle,
            self._JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(accounting.active_processes)

    def wait_drained(self, child: subprocess.Popen[bytes], timeout: float) -> bool:
        try:
            deadline = time.perf_counter() + max(timeout, 0.0)
            child.wait(timeout=timeout)
            while self.active_processes() != 0:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return False
                time.sleep(min(0.01, remaining))
            return True
        except Exception:
            return False

    def terminate_and_drain(self, child: subprocess.Popen[bytes]) -> bool:
        if self._handle is None:
            return False
        try:
            if not self._kernel32.TerminateJobObject(self._handle, 0xD1):
                return False
            child.wait(timeout=5.0)
            return self.active_processes() == 0
        except Exception:
            return False

    def close(self) -> bool:
        closed = True
        if self._process_handle is not None:
            closed = bool(self._kernel32.CloseHandle(self._process_handle)) and closed
            self._process_handle = None
        if self._handle is not None:
            closed = bool(self._kernel32.CloseHandle(self._handle)) and closed
            self._handle = None
        return closed


class WindowsNativePlatform:
    def __init__(self, store: FixedLocalAuthorityStore) -> None:
        self._store = store
        self._ffmpeg_lease: WindowsExecutableLease | None = None
        self._last_ffmpeg_verified = False

    def camera_class_devices(self) -> tuple[CameraCandidate, ...]:
        lease = _WindowsPowerShellExecutableLease()
        command = (
            lease.executable,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-PnpDevice -Class Camera -PresentOnly | Select-Object FriendlyName,Status,Present "
            "| ConvertTo-Json -Compress",
        )
        system32 = WINDOWS_SYSTEM_DIRECTORY
        powershell = str(Path(POWERSHELL_CANONICAL_PATH).parent)
        environment = {
            "SystemRoot": str(Path(system32).parent),
            "WINDIR": str(Path(system32).parent),
            "PATH": os.pathsep.join((powershell, system32)),
        }
        child: subprocess.Popen[bytes] | None = None
        output = b""
        try:
            child = lease._launch_suspended(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                cwd=POWERSHELL_WORKING_DIRECTORY,
            )
            output, _ = child.communicate(timeout=10.0)
            if child.returncode != 0 or not lease.image_verified:
                raise OSError("PowerShell camera enumeration failed")
            if len(output) > 32_768:
                raise ValueError("camera enumeration output is oversized")
        finally:
            if child is not None and child.poll() is None:
                child.kill()
                child.wait(timeout=2.0)
            if not lease.close():
                raise OSError("PowerShell executable lease cleanup failed")
        raw = json.loads(output.decode("utf-8", errors="strict"))
        rows = raw if isinstance(raw, list) else [raw]
        return tuple(
            CameraCandidate(
                friendly_name=row["FriendlyName"],
                present=row.get("Present") is True,
                status_ok=row.get("Status") == "OK",
            )
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("FriendlyName"), str)
        )

    def ffmpeg_authority(self) -> tuple[str, str, str]:
        if self._ffmpeg_lease is not None:
            raise OSError("FFmpeg lease is already active")
        self._ffmpeg_lease = WindowsExecutableLease()
        self._last_ffmpeg_verified = False
        binding = self._ffmpeg_lease.probe_version()
        return self._ffmpeg_lease.executable, binding.sha256, binding.version_output_sha256

    def sha256_of_executable(self, executable: str) -> str:
        if self._ffmpeg_lease is None or executable != self._ffmpeg_lease.executable:
            raise OSError("executable is not protected by the active lease")
        return self._ffmpeg_lease.binding.sha256

    def ffmpeg_identity(self) -> tuple[int, str, bool]:
        if self._ffmpeg_lease is None:
            raise OSError("FFmpeg lease is unavailable")
        binding = self._ffmpeg_lease.binding
        return binding.size_bytes, binding.identity_digest, self._ffmpeg_lease.image_verified

    def ffmpeg_lease_verified(self) -> bool:
        return self._last_ffmpeg_verified

    def close_ffmpeg_lease(self) -> bool:
        if self._ffmpeg_lease is None:
            return True
        lease, self._ffmpeg_lease = self._ffmpeg_lease, None
        return lease.close()

    def named_mutex(self) -> NamedMutex:
        return WindowsNamedMutex()

    def launch_video_only(self, argv: tuple[str, ...]) -> VideoChild:
        if self._ffmpeg_lease is None:
            raise OSError("FFmpeg launch has no active executable lease")
        child = self._ffmpeg_lease.launch_video_only(argv)
        self._last_ffmpeg_verified = self._ffmpeg_lease.image_verified
        return child

    def monotonic_ns(self) -> int:
        return time.perf_counter_ns()


class MediaPipeTasksRuntime:
    """Loads only package resources and uses synchronous VIDEO tasks."""

    def __init__(self) -> None:
        self._face: Any | None = None
        self._pose: Any | None = None

    def liveness(self) -> bool:
        try:
            assets = _runtime_prerequisites()
            if assets is None:
                return False
            self._ensure_tasks(*assets)
            self._probe()
        except Exception:
            return False
        return (
            self._face is not None
            and self._pose is not None
            and not any(name.split(".", 1)[0] in _AUDIO_ROOTS for name in sys.modules)
        )

    def inspect_face(self, frame: memoryview, timestamp_ms: int) -> bool:
        face, _ = self._tasks()
        result = face.detect_for_video(self._image(frame), timestamp_ms)
        return bool(result.detections)

    def inspect_pose(self, frame: memoryview, timestamp_ms: int) -> bool:
        _, pose = self._tasks()
        result = pose.detect_for_video(self._image(frame), timestamp_ms)
        return bool(result.pose_landmarks)

    def close(self) -> None:
        tasks = tuple(task for task in (self._face, self._pose) if task is not None)
        self._face = None
        self._pose = None
        failures: queue.Queue[BaseException | None] = queue.Queue(maxsize=len(tasks) or 1)

        def close_task(task: object) -> None:
            close = getattr(task, "close", None)
            if not callable(close):
                failures.put(None)
                return
            try:
                close()
            except BaseException as error:
                failures.put(error)
            else:
                failures.put(None)

        threads = [
            threading.Thread(target=close_task, args=(task,), daemon=True) for task in tasks
        ]
        for thread in threads:
            thread.start()
        deadline = time.perf_counter() + MEDIA_CLOSE_TIMEOUT_SECONDS
        for thread in threads:
            thread.join(timeout=max(deadline - time.perf_counter(), 0.0))
        if any(thread.is_alive() for thread in threads):
            raise TimeoutError("MediaPipe task cleanup exceeded its process boundary")
        failure: BaseException | None = None
        while not failures.empty():
            failure = failures.get_nowait() or failure
        if failure is not None:
            raise failure

    def _ensure_tasks(self, face_bytes: bytes, pose_bytes: bytes) -> None:
        if self._face is not None and self._pose is not None:
            return
        import mediapipe as mp  # type: ignore[import-untyped]
        from mediapipe.tasks import python  # type: ignore[import-untyped]
        from mediapipe.tasks.python import vision  # type: ignore[import-untyped]

        face_options = vision.FaceDetectorOptions(
            base_options=python.BaseOptions(model_asset_buffer=face_bytes),
            running_mode=vision.RunningMode.VIDEO,
        )
        pose_options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_buffer=pose_bytes),
            running_mode=vision.RunningMode.VIDEO,
        )
        self._face = vision.FaceDetector.create_from_options(face_options)
        self._pose = vision.PoseLandmarker.create_from_options(pose_options)
        del mp

    def _tasks(self) -> tuple[Any, Any]:
        if self._face is None or self._pose is None:
            raise RuntimeError("media tasks are unavailable")
        return self._face, self._pose

    def _probe(self) -> None:
        face, pose = self._tasks()
        image = self._image(memoryview(bytearray(FRAME_BYTES)))
        face.detect_for_video(image, 0)
        pose.detect_for_video(image, 0)

    def _image(self, frame: memoryview) -> object:
        import mediapipe as mp
        import numpy as np

        array = np.frombuffer(frame, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=array)


class NativePreflightService:
    def __init__(
        self,
        *,
        platform: NativePlatform,
        media: MediaRuntime,
        store: AuthorityStore,
        supervised: bool = False,
        defer_terminalization: bool = False,
        event_sink: Callable[[str, int], None] | None = None,
    ) -> None:
        self._platform = platform
        self._media = media
        self._store = store
        self._supervised = supervised
        self._defer_terminalization = defer_terminalization
        self._event_sink = event_sink

    @classmethod
    def fixed(cls) -> NativePreflightService:
        store = FixedLocalAuthorityStore()
        return cls(
            platform=WindowsNativePlatform(store),
            media=MediaPipeTasksRuntime(),
            store=store,
            supervised=True,
        )

    def prepare(self) -> NativeReceipt:
        mutex: NamedMutex | None = None
        prepared: PreparedAuthority | None = None
        outcome = NativeOutcome.NO_GO
        failure: NativeFailure | None = NativeFailure.UNKNOWN_TECHNICAL_FAILURE
        media_used = False
        media_closed = True
        ffmpeg_lease_opened = False
        ffmpeg_lease_closed = True
        mutex_released = False
        try:
            mutex = self._platform.named_mutex()
            if not mutex.acquire():
                failure = NativeFailure.SCHEMA_INCOMPATIBLE
            else:
                existing = self._store.load()
                if existing is not None:
                    if (
                        _prepared_is_valid(existing)
                        and existing.state is AuthorizationState.PREPARED
                    ):
                        prepared = existing
                        outcome = NativeOutcome.PREPARED
                        failure = None
                    else:
                        failure = NativeFailure.REAUTHORIZATION_REQUIRED
                elif _runtime_prerequisites() is None:
                    failure = NativeFailure.POSE_ENGINE_UNAVAILABLE
                else:
                    cameras = self._platform.camera_class_devices()
                    if (
                        len(cameras) != 1
                        or not cameras[0].present
                        or not cameras[0].status_ok
                        or not _safe_directshow_name(cameras[0].friendly_name)
                    ):
                        failure = NativeFailure.SCHEMA_INCOMPATIBLE
                    else:
                        executable, digest, _version = self._platform.ffmpeg_authority()
                        ffmpeg_lease_opened = True
                        ffmpeg_size, ffmpeg_identity, _ = _platform_ffmpeg_identity(
                            self._platform, digest, _version
                        )
                        if (
                            not _is_digest(digest)
                            or self._platform.sha256_of_executable(executable) != digest
                        ):
                            failure = NativeFailure.SCHEMA_INCOMPATIBLE
                        else:
                            prepared = PreparedAuthority(
                                schema_version=2,
                                opaque_device_token=secrets.token_hex(32),
                                authority_revision=AUTHORITY_REVISION,
                                state=AuthorizationState.PENDING,
                                ffmpeg_sha256=digest,
                                ffmpeg_version=_version,
                                ffmpeg_size_bytes=ffmpeg_size,
                                ffmpeg_identity_digest=ffmpeg_identity,
                                authorization_nonce=secrets.token_hex(32),
                            )
                            self._store.save(prepared)
                            media_used = True
                            if self._media.liveness():
                                failure = None
                            else:
                                failure = NativeFailure.POSE_ENGINE_UNAVAILABLE
        except ValueError:
            outcome = NativeOutcome.NO_GO
            failure = NativeFailure.SCHEMA_INCOMPATIBLE
        except Exception:
            outcome = NativeOutcome.NO_GO
            failure = NativeFailure.UNKNOWN_TECHNICAL_FAILURE
        finally:
            if media_used:
                media_closed = _close_media(self._media)
            if ffmpeg_lease_opened:
                ffmpeg_lease_closed = _close_platform_ffmpeg_lease(self._platform)
            mutex_released = mutex is not None and _release_mutex(mutex)
        if (
            failure is None
            and prepared is not None
            and prepared.state is AuthorizationState.PENDING
        ):
            if not media_closed or not ffmpeg_lease_closed or not mutex_released:
                failure = NativeFailure.CLEANUP_INCOMPLETE
            else:
                try:
                    if self._store.finalize(prepared):
                        prepared = replace(prepared, state=AuthorizationState.PREPARED)
                        outcome = NativeOutcome.PREPARED
                    else:
                        failure = NativeFailure.REAUTHORIZATION_REQUIRED
                except Exception:
                    failure = NativeFailure.UNKNOWN_TECHNICAL_FAILURE
        if outcome is NativeOutcome.PREPARED and (
            not media_closed or not ffmpeg_lease_closed or not mutex_released
        ):
            outcome = NativeOutcome.NO_GO
            failure = NativeFailure.CLEANUP_INCOMPLETE
        return _receipt(
            outcome,
            failure,
            prepared=prepared,
            media_closed=media_closed,
            mutex_released=mutex_released,
            ffmpeg_lease_closed=ffmpeg_lease_closed,
        )

    def preflight(self) -> NativeReceipt:
        if self._supervised:
            return self._supervised_preflight()
        return self._local_preflight()

    def _take_prepared_authority(self) -> tuple[PreparedAuthority | None, NativeReceipt | None]:
        try:
            prepared = self._store.load()
        except Exception:
            return None, _receipt(NativeOutcome.NO_GO, NativeFailure.SCHEMA_INCOMPATIBLE)
        if not _prepared_is_valid(prepared):
            return None, _receipt(NativeOutcome.NO_GO, NativeFailure.SCHEMA_INCOMPATIBLE)
        assert isinstance(prepared, PreparedAuthority)
        if prepared.state is not AuthorizationState.PREPARED:
            return None, _receipt(NativeOutcome.NO_GO, NativeFailure.REAUTHORIZATION_REQUIRED)
        try:
            if self._store.load_terminal() is not None:
                return None, _receipt(
                    NativeOutcome.NO_GO, NativeFailure.REAUTHORIZATION_REQUIRED
                )
        except Exception:
            return None, _receipt(NativeOutcome.NO_GO, NativeFailure.SCHEMA_INCOMPATIBLE)
        try:
            if not self._store.consume(prepared):
                return None, _receipt(
                    NativeOutcome.NO_GO, NativeFailure.REAUTHORIZATION_REQUIRED
                )
        except Exception:
            return None, _receipt(NativeOutcome.NO_GO, NativeFailure.SCHEMA_INCOMPATIBLE)
        return prepared, None

    def _local_preflight(self) -> NativeReceipt:
        prepared, failure_receipt = self._take_prepared_authority()
        if failure_receipt is not None:
            return failure_receipt
        assert prepared is not None
        return self._run_consumed(prepared)

    def _supervised_preflight(self) -> NativeReceipt:
        challenge = secrets.token_hex(32)
        capability = secrets.token_bytes(WORKER_CAPABILITY_BYTES)
        prepared, failure_receipt = self._take_prepared_authority()
        if failure_receipt is not None:
            return failure_receipt
        assert prepared is not None
        grant: WorkerGrant | None = None
        grant_issued = False
        try:
            probe = _WindowsWorkerExecutableLease()
            try:
                worker_binding = probe.binding
            finally:
                probe_closed = probe.close()
            if not probe_closed:
                raise OSError("worker grant probe lease cleanup failed")
            grant = _new_worker_grant(
                prepared, challenge, capability, worker_binding
            )
            grant_issued = self._store.issue_worker_grant(prepared, grant)
            if not grant_issued:
                raise OSError("worker launch grant could not be persisted")
            candidate = _run_windows_capture_worker(
                prepared, challenge, grant, capability
            )
        except Exception:
            candidate = _receipt(
                NativeOutcome.NO_GO,
                NativeFailure.UNKNOWN_TECHNICAL_FAILURE,
                prepared=prepared,
                authority_consumed=True,
            )
        finally:
            capability = b""
        pass_supervision_invalid = (
            candidate.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
            and not (
                candidate.capture_worker_supervised
                and candidate.capture_deadline_enforced
                and candidate.capture_job_drained
                and candidate.capture_worker_lease_closed
            )
        )
        if pass_supervision_invalid or not _candidate_semantics_are_valid(candidate):
            candidate = _receipt(
                NativeOutcome.NO_GO,
                NativeFailure.WORKER_PROTOCOL_FAILURE,
                prepared=prepared,
                authority_consumed=True,
            )
        if grant_issued and grant is not None:
            try:
                grant_revoked = self._store.revoke_worker_grant(grant)
            except Exception:
                grant_revoked = False
            if not grant_revoked:
                candidate = _receipt(
                    NativeOutcome.NO_GO,
                    NativeFailure.UNKNOWN_TECHNICAL_FAILURE,
                    prepared=prepared,
                    authority_consumed=True,
                )
        return self._terminalize(prepared, candidate)

    def _run_consumed(self, prepared: PreparedAuthority) -> NativeReceipt:
        ffmpeg_lease_opened = False
        if _runtime_prerequisites() is None:
            return self._terminalize(
                prepared,
                _receipt(
                    NativeOutcome.NO_GO,
                    NativeFailure.POSE_ENGINE_UNAVAILABLE,
                    prepared=prepared,
                    authority_consumed=True,
                ),
            )
        try:
            runtime_live = self._media.liveness()
        except Exception:
            runtime_live = False
        if not runtime_live:
            return self._terminalize(
                prepared,
                _receipt(
                    NativeOutcome.NO_GO,
                    NativeFailure.POSE_ENGINE_UNAVAILABLE,
                    prepared=prepared,
                    media_closed=_close_media(self._media),
                    authority_consumed=True,
                ),
            )
        if self._event_sink is not None:
            try:
                self._event_sink("PRIVACY_READY", self._platform.monotonic_ns())
            except Exception:
                return self._terminalize(
                    prepared,
                    _receipt(
                        NativeOutcome.NO_GO,
                        NativeFailure.CAPTURE_RUNTIME_EXCEPTION,
                        prepared=prepared,
                        media_closed=_close_media(self._media),
                        authority_consumed=True,
                    ),
                )
        try:
            cameras = self._platform.camera_class_devices()
            executable, digest, version = self._platform.ffmpeg_authority()
            ffmpeg_lease_opened = True
            executable_digest = self._platform.sha256_of_executable(executable)
            ffmpeg_size, ffmpeg_identity, _ = _platform_ffmpeg_identity(
                self._platform, digest, version
            )
            current = cameras[0] if len(cameras) == 1 else None
        except Exception:
            if ffmpeg_lease_opened:
                _close_platform_ffmpeg_lease(self._platform)
            return self._terminalize(
                prepared,
                _receipt(
                    NativeOutcome.NO_GO,
                    NativeFailure.SCHEMA_INCOMPATIBLE,
                    prepared=prepared,
                    authority_consumed=True,
                ),
            )
        if (
            current is None
            or not current.present
            or not current.status_ok
            or not _safe_directshow_name(current.friendly_name)
            or not _is_digest(digest)
            or executable_digest != digest
            or digest != prepared.ffmpeg_sha256
            or version != prepared.ffmpeg_version
            or ffmpeg_size != prepared.ffmpeg_size_bytes
            or ffmpeg_identity != prepared.ffmpeg_identity_digest
        ):
            _close_platform_ffmpeg_lease(self._platform)
            return self._terminalize(
                prepared,
                _receipt(
                    NativeOutcome.NO_GO,
                    NativeFailure.SCHEMA_INCOMPATIBLE,
                    prepared=prepared,
                    authority_consumed=True,
                ),
            )
        try:
            mutex = self._platform.named_mutex()
            acquired = mutex.acquire()
        except Exception:
            lease_closed = _close_platform_ffmpeg_lease(self._platform)
            return self._terminalize(
                prepared,
                _receipt(
                    NativeOutcome.NO_GO,
                    NativeFailure.SCHEMA_INCOMPATIBLE,
                    prepared=prepared,
                    media_closed=_close_media(self._media),
                    ffmpeg_lease_closed=lease_closed,
                    authority_consumed=True,
                ),
            )
        if not acquired:
            lease_closed = _close_platform_ffmpeg_lease(self._platform)
            return self._terminalize(
                prepared,
                _receipt(
                    NativeOutcome.NO_GO,
                    NativeFailure.SCHEMA_INCOMPATIBLE,
                    prepared=prepared,
                    media_closed=_close_media(self._media),
                    ffmpeg_lease_closed=lease_closed,
                    authority_consumed=True,
                ),
            )
        child: VideoChild | None = None
        reader: _FrameReader | None = None
        buffers: tuple[bytearray, bytearray] | None = None
        state = _RunState()
        raw_retained = True
        fixed_argv_digest: str | None = None
        try:
            buffers = (bytearray(FRAME_BYTES), bytearray(FRAME_BYTES))
            argv = _fixed_argv(executable, current.friendly_name)
            fixed_argv_digest = _fixed_argv_template_digest()
            if self._event_sink is not None:
                self._event_sink(
                    "CAPTURE_STARTING", self._platform.monotonic_ns()
                )
            child = self._platform.launch_video_only(argv)
            reader = _FrameReader(child.stdout, buffers, self._platform.monotonic_ns)
            reader.start()
            while True:
                frame_event = reader.next()
                if frame_event is None:
                    state.failure = (
                        NativeFailure.FRAME_STALLED
                        if reader.alive()
                        else NativeFailure.FRAME_READER_EXCEPTION
                    )
                    break
                disposition, buffer_index, count, ingress = frame_event
                if disposition in {
                    _ReaderDisposition.READ_EXCEPTION,
                    _ReaderDisposition.INGRESS_CLOCK_EXCEPTION,
                }:
                    state.failure = NativeFailure.FRAME_READER_EXCEPTION
                    break
                if disposition is _ReaderDisposition.EOF:
                    state.failure = (
                        NativeFailure.INPUT_UNAVAILABLE
                        if state.delivered_frames == 0
                        else NativeFailure.INPUT_MALFORMED
                    )
                    break
                if disposition is not _ReaderDisposition.FRAME or count is None:
                    state.failure = NativeFailure.FRAME_READER_EXCEPTION
                    break
                if count != FRAME_BYTES:
                    state.failure = NativeFailure.INPUT_MALFORMED
                    break
                if ingress is None:
                    state.failure = NativeFailure.FRAME_READER_EXCEPTION
                    break
                dequeued = self._platform.monotonic_ns()
                if dequeued < ingress:
                    state.failure = NativeFailure.CLOCK_REGRESSION
                    break
                state.max_backlog_ns = max(state.max_backlog_ns, dequeued - ingress)
                if state.first_ingress_ns is None:
                    state.first_ingress_ns = ingress
                    if self._event_sink is not None:
                        self._event_sink("FIRST_FRAME", ingress)
                if state.previous_ingress_ns is not None:
                    gap = ingress - state.previous_ingress_ns
                    if gap <= 0:
                        state.failure = NativeFailure.CLOCK_REGRESSION
                        break
                    if gap >= 1_000_000_000:
                        state.failure = NativeFailure.FRAME_STALLED
                        break
                timestamp_ms = (ingress - state.first_ingress_ns) // 1_000_000
                if timestamp_ms <= state.previous_video_timestamp_ms:
                    state.failure = NativeFailure.CLOCK_REGRESSION
                    break
                state.previous_video_timestamp_ms = timestamp_ms
                frame = memoryview(buffers[buffer_index])
                try:
                    if self._media.inspect_face(frame, timestamp_ms):
                        state.face_detections += 1
                        state.failure = NativeFailure.PRIVACY_STOP
                        state.privacy_stop_count = 1
                        break
                except Exception:
                    state.failure = NativeFailure.PRIVACY_STOP
                    state.privacy_stop_count = 1
                    break
                try:
                    if self._media.inspect_pose(frame, timestamp_ms):
                        state.pose_detections += 1
                        state.failure = NativeFailure.PRIVACY_STOP
                        state.privacy_stop_count = 1
                        break
                except Exception:
                    state.failure = NativeFailure.POSE_ENGINE_EXCEPTION
                    break
                state.privacy_checked_frames += 1
                completed = self._platform.monotonic_ns()
                if completed < ingress:
                    state.failure = NativeFailure.CLOCK_REGRESSION
                    break
                state.record(ingress, completed - ingress)
                state.previous_ingress_ns = ingress
                if ingress - state.first_ingress_ns >= PREFLIGHT_SECONDS * 1_000_000_000:
                    reader.release(buffer_index)
                    break
                reader.release(buffer_index)
        except Exception:
            if state.failure is None:
                state.failure = NativeFailure.CAPTURE_RUNTIME_EXCEPTION
        finally:
            pipe_closed, child_terminated, reader_stopped = _cleanup_child(child, reader)
            buffers_zeroed = reader_stopped and buffers is not None
            if buffers_zeroed and buffers is not None:
                for buffer in buffers:
                    try:
                        buffer[:] = b"\0" * len(buffer)
                        buffers_zeroed = buffers_zeroed and not any(buffer)
                    except Exception:
                        buffers_zeroed = False
            raw_retained = not buffers_zeroed
            media_closed = _close_media(self._media)
            ffmpeg_lease_closed = _close_platform_ffmpeg_lease(self._platform)
            mutex_released = _release_mutex(mutex)
            cleanup_complete = all(
                (
                    buffers_zeroed,
                    pipe_closed,
                    child_terminated,
                    reader_stopped,
                    media_closed,
                    ffmpeg_lease_closed,
                    mutex_released,
                )
            )
            if not cleanup_complete and state.failure is not NativeFailure.PRIVACY_STOP:
                state.failure = NativeFailure.CLEANUP_INCOMPLETE
            if (
                self._event_sink is not None
                and child is not None
                and pipe_closed
                and child_terminated
                and reader_stopped
            ):
                try:
                    self._event_sink("CAPTURE_CLOSED", self._platform.monotonic_ns())
                except Exception:
                    if state.failure is not NativeFailure.PRIVACY_STOP:
                        state.failure = NativeFailure.CAPTURE_RUNTIME_EXCEPTION
        if state.failure is NativeFailure.PRIVACY_STOP:
            candidate = _receipt(
                NativeOutcome.NO_GO,
                state.failure,
                prepared=prepared,
                privacy_checked_frames=state.privacy_checked_frames,
                privacy_stop_count=1,
                face_detections=state.face_detections,
                pose_detections=state.pose_detections,
                fixed_argv_digest=fixed_argv_digest,
                ffmpeg_sha256=digest,
                ffmpeg_version=version,
                mutex_released=mutex_released,
                child_terminated=child_terminated,
                pipe_closed=pipe_closed,
                reader_stopped=reader_stopped,
                media_closed=media_closed,
                authority_consumed=True,
                raw_retained=raw_retained,
                ffmpeg_size_bytes=ffmpeg_size,
                ffmpeg_identity_digest=ffmpeg_identity,
                ffmpeg_lease_verified=_platform_ffmpeg_verified(self._platform),
                ffmpeg_lease_closed=ffmpeg_lease_closed,
            )
            return self._terminalize(prepared, candidate)
        candidate = _result_receipt(
            prepared,
            state,
            mutex_released=mutex_released,
            child_terminated=child_terminated,
            pipe_closed=pipe_closed,
            reader_stopped=reader_stopped,
            media_closed=media_closed,
            raw_retained=raw_retained,
            fixed_argv_digest=fixed_argv_digest,
            ffmpeg_sha256=digest,
            ffmpeg_version=version,
            ffmpeg_size_bytes=ffmpeg_size,
            ffmpeg_identity_digest=ffmpeg_identity,
            ffmpeg_lease_verified=_platform_ffmpeg_verified(self._platform),
            ffmpeg_lease_closed=ffmpeg_lease_closed,
        )
        return self._terminalize(prepared, candidate)

    def _terminalize(self, prepared: PreparedAuthority, receipt: NativeReceipt) -> NativeReceipt:
        if self._defer_terminalization:
            return receipt
        run_nonce = secrets.token_hex(32)
        core_candidate = replace(
            receipt,
            run_nonce=run_nonce,
            terminal_receipt_digest=None,
            terminal_state_digest=None,
            result_digest="",
        )
        core_digest = core_candidate.recompute_core_digest()
        try:
            terminal = self._store.finalize_terminal(
                prepared,
                run_nonce=run_nonce,
                receipt_core_digest=core_digest,
                outcome=receipt.outcome,
                failure=receipt.failure_code,
            )
        except Exception:
            terminal = None
        if terminal is None:
            failed = replace(
                receipt,
                outcome=NativeOutcome.NO_GO,
                failure_code=NativeFailure.AUTHORITY_FINALIZATION_FAILED,
                run_nonce=None,
                terminal_receipt_digest=None,
                terminal_state_digest=None,
                result_digest="",
            )
            return replace(failed, result_digest=failed.recompute_digest())
        final = replace(
            core_candidate,
            terminal_receipt_digest=core_digest,
            terminal_state_digest=terminal.record_digest,
        )
        return replace(final, result_digest=final.recompute_digest())

    def verify_terminal_receipt(self, receipt: NativeReceipt) -> bool:
        return _verify_terminal_receipt_with_store(receipt, self._store)


@dataclass(slots=True)
class _RunState:
    first_ingress_ns: int | None = None
    previous_ingress_ns: int | None = None
    previous_video_timestamp_ms: int = -1
    delivered_frames: int = 0
    processed_frames: int = 0
    post_warmup_processed_frames: int = 0
    privacy_checked_frames: int = 0
    privacy_stop_count: int = 0
    face_detections: int = 0
    pose_detections: int = 0
    max_backlog_ns: int = 0
    gaps_ms: list[float] | None = None
    latencies_ms: list[float] | None = None
    failure: NativeFailure | None = None

    def record(self, ingress: int, latency_ns: int) -> None:
        assert self.first_ingress_ns is not None
        if ingress - self.first_ingress_ns >= WARMUP_SECONDS * 1_000_000_000:
            if self.previous_ingress_ns is not None and self.delivered_frames:
                self.gaps_ms = (self.gaps_ms or []) + [
                    (ingress - self.previous_ingress_ns) / 1_000_000
                ]
            self.latencies_ms = (self.latencies_ms or []) + [latency_ns / 1_000_000]
            self.post_warmup_processed_frames += 1
        self.delivered_frames += 1
        self.processed_frames += 1


def _result_receipt(
    prepared: PreparedAuthority,
    state: _RunState,
    *,
    mutex_released: bool,
    child_terminated: bool,
    pipe_closed: bool,
    reader_stopped: bool,
    media_closed: bool,
    raw_retained: bool,
    fixed_argv_digest: str | None,
    ffmpeg_sha256: str,
    ffmpeg_version: str,
    ffmpeg_size_bytes: int,
    ffmpeg_identity_digest: str,
    ffmpeg_lease_verified: bool,
    ffmpeg_lease_closed: bool,
) -> NativeReceipt:
    if state.first_ingress_ns is None or state.previous_ingress_ns is None:
        return _receipt(
            NativeOutcome.NO_GO,
            state.failure or NativeFailure.INPUT_UNAVAILABLE,
            prepared=prepared,
            mutex_released=mutex_released,
            child_terminated=child_terminated,
            pipe_closed=pipe_closed,
            reader_stopped=reader_stopped,
            media_closed=media_closed,
            authority_consumed=True,
            raw_retained=raw_retained,
        )
    total = (state.previous_ingress_ns - state.first_ingress_ns) / 1_000_000_000
    post = max(total - WARMUP_SECONDS, 0.0)
    gaps = tuple(state.gaps_ms or ())
    latencies = tuple(state.latencies_ms or ())
    failure = state.failure or _threshold_failure(state, total, post, gaps, latencies)
    return _receipt(
        NativeOutcome.NO_GO if failure else NativeOutcome.D1_N1_PREFLIGHT_PASS,
        failure,
        prepared=prepared,
        fixed_argv_digest=fixed_argv_digest,
        ffmpeg_sha256=ffmpeg_sha256,
        ffmpeg_version=ffmpeg_version,
        ffmpeg_size_bytes=ffmpeg_size_bytes,
        ffmpeg_identity_digest=ffmpeg_identity_digest,
        ffmpeg_lease_verified=ffmpeg_lease_verified,
        ffmpeg_lease_closed=ffmpeg_lease_closed,
        measured_total_seconds=total,
        measured_post_warmup_seconds=post,
        delivered_frames_per_second=(
            state.post_warmup_processed_frames / post if post else None
        ),
        p95_ingress_gap_ms=nearest_rank(gaps, 95) if gaps else None,
        p95_pose_latency_ms=nearest_rank(latencies, 95) if latencies else None,
        p99_pose_latency_ms=nearest_rank(latencies, 99) if latencies else None,
        backlog_ms=state.max_backlog_ns / 1_000_000,
        mutex_released=mutex_released,
        child_terminated=child_terminated,
        pipe_closed=pipe_closed,
        reader_stopped=reader_stopped,
        media_closed=media_closed,
        capture_worker_supervised=True,
        capture_deadline_enforced=True,
        capture_job_drained=True,
        capture_worker_executable_sha256=_digest(["injected-capture-worker-sha256"]),
        capture_worker_identity_digest=_digest(["injected-capture-worker-identity"]),
        capture_worker_lease_closed=True,
        authority_consumed=True,
        raw_retained=raw_retained,
        received_frames=state.delivered_frames,
        warmup_frames=state.delivered_frames - state.post_warmup_processed_frames,
        post_attempted_frames=state.post_warmup_processed_frames,
        post_successful_frames=state.post_warmup_processed_frames,
        post_elapsed_ns=int(post * 1_000_000_000),
        max_stall_gap_ns=int(max(gaps) * 1_000_000) if gaps else 0,
        backlog_ns=state.max_backlog_ns,
    )


def _threshold_failure(
    state: _RunState,
    total: float,
    post: float,
    gaps: tuple[float, ...],
    latencies: tuple[float, ...],
) -> NativeFailure | None:
    if total < PREFLIGHT_SECONDS or post < PREFLIGHT_SECONDS - WARMUP_SECONDS:
        return NativeFailure.INPUT_MALFORMED
    if not gaps or not latencies or state.processed_frames == 0:
        return NativeFailure.QUALITY_INSUFFICIENT
    fps = state.post_warmup_processed_frames / post
    if (
        state.max_backlog_ns > 2_000_000_000
        or
        fps < 13.5
        or nearest_rank(gaps, 95) > 200
        or nearest_rank(latencies, 95) > 200
        or nearest_rank(latencies, 99) > 500
    ):
        return NativeFailure.QUALITY_INSUFFICIENT
    return None


def _worker_job_policy_digest() -> str:
    return _digest(
        [
            "d1-n1-worker-job-policy-v1",
            "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
            "JOB_OBJECT_LIMIT_ACTIVE_PROCESS",
            2,
            WORKER_CAPTURE_TIMEOUT_SECONDS,
        ]
    )


def _worker_argv_digest() -> str:
    return _digest(
        ["d1-n1-worker-argv-v1", "-I", "-u", "-c", WORKER_BOOTSTRAP]
    )


def _worker_grant_is_valid(grant: object, *, allow_revoked: bool) -> bool:
    if not isinstance(grant, WorkerGrant):
        return False
    allowed_states = {"ISSUED", "REVOKED"} if allow_revoked else {"ISSUED"}
    digest_fields = (
        grant.grant_id,
        grant.challenge_digest,
        grant.capability_digest,
        grant.consumed_authority_digest,
        grant.supervisor_executable_sha256,
        grant.worker_executable_sha256,
        grant.worker_identity_digest,
        grant.worker_argv_digest,
        grant.source_sha256,
        grant.lock_sha256,
        grant.pose_model_sha256,
        grant.face_model_sha256,
        grant.ffmpeg_sha256,
        grant.ffmpeg_version,
        grant.ffmpeg_identity_digest,
        grant.job_policy_digest,
        grant.record_digest,
    )
    return (
        grant.schema_version == 1
        and grant.state in allowed_states
        and all(_is_digest(value) for value in digest_fields)
        and type(grant.ffmpeg_size_bytes) is int
        and grant.ffmpeg_size_bytes > 0
        and type(grant.issued_unix_ns) is int
        and type(grant.expires_unix_ns) is int
        and grant.issued_unix_ns > 0
        and grant.issued_unix_ns < grant.expires_unix_ns
        and grant.expires_unix_ns - grant.issued_unix_ns
        <= WORKER_GRANT_VALIDITY_SECONDS * 1_000_000_000
        and grant.record_digest == grant.recompute_digest()
    )


def _new_worker_grant(
    prepared: PreparedAuthority,
    challenge: str,
    capability: bytes,
    binding: FfmpegBinding,
) -> WorkerGrant:
    if len(capability) != WORKER_CAPABILITY_BYTES or not _is_nonce(challenge):
        raise ValueError("worker launch capability is malformed")
    issued = time.time_ns()
    consumed = replace(prepared, state=AuthorizationState.CONSUMED)
    grant = WorkerGrant(
        schema_version=1,
        state="ISSUED",
        grant_id=secrets.token_hex(32),
        challenge_digest=_digest(["d1-n1-worker-challenge-v1", challenge]),
        capability_digest=hashlib.sha256(capability).hexdigest(),
        consumed_authority_digest=_digest(asdict(consumed)),
        supervisor_executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        worker_executable_sha256=binding.sha256,
        worker_identity_digest=binding.identity_digest,
        worker_argv_digest=_worker_argv_digest(),
        source_sha256=_source_sha256(),
        lock_sha256=_lock_sha256(),
        pose_model_sha256=POSE_MODEL_SHA256,
        face_model_sha256=FACE_MODEL_SHA256,
        ffmpeg_sha256=prepared.ffmpeg_sha256,
        ffmpeg_version=prepared.ffmpeg_version,
        ffmpeg_size_bytes=prepared.ffmpeg_size_bytes,
        ffmpeg_identity_digest=prepared.ffmpeg_identity_digest,
        job_policy_digest=_worker_job_policy_digest(),
        issued_unix_ns=issued,
        expires_unix_ns=issued + WORKER_GRANT_VALIDITY_SECONDS * 1_000_000_000,
        record_digest="",
    )
    grant = replace(grant, record_digest=grant.recompute_digest())
    if not _worker_grant_is_valid(grant, allow_revoked=False):
        raise ValueError("worker grant construction failed")
    return grant


def _worker_grant_from_payload(raw: object) -> WorkerGrant:
    if not isinstance(raw, dict) or set(raw) != set(WorkerGrant.__dataclass_fields__):
        raise ValueError("worker grant payload is malformed")
    grant = WorkerGrant(**cast(dict[str, Any], raw))
    if not _worker_grant_is_valid(grant, allow_revoked=False):
        raise ValueError("worker grant payload is invalid")
    return grant


def _send_worker_proceed(
    child: subprocess.Popen[bytes],
    challenge_digest: str,
    grant: WorkerGrant,
    capability: bytes,
) -> None:
    if child.stdin is None or len(capability) != WORKER_CAPABILITY_BYTES:
        raise OSError("worker capability channel is unavailable")
    message = {
        "event": "PROCEED",
        "challenge_digest": challenge_digest,
        "payload": {"grant": asdict(grant), "capability": capability.hex()},
    }
    encoded = json.dumps(
        message,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    if len(encoded) + 1 > WORKER_MESSAGE_MAX_BYTES:
        raise ValueError("worker capability message is oversized")
    try:
        child.stdin.write(encoded + b"\n")
        child.stdin.flush()
    finally:
        child.stdin.close()


def _receive_worker_launch_grant(
    challenge: str, prepared: PreparedAuthority
) -> WorkerGrant:
    line = sys.stdin.buffer.readline(WORKER_MESSAGE_MAX_BYTES + 1)
    if not line or len(line) > WORKER_MESSAGE_MAX_BYTES:
        raise ValueError("worker capability message size is invalid")
    message = _strict_worker_message(line)
    challenge_digest = _digest(["d1-n1-worker-challenge-v1", challenge])
    payload = message.get("payload")
    if (
        set(message) != {"event", "challenge_digest", "payload"}
        or message.get("event") != "PROCEED"
        or message.get("challenge_digest") != challenge_digest
        or not isinstance(payload, dict)
        or set(payload) != {"grant", "capability"}
        or not isinstance(payload["capability"], str)
    ):
        raise ValueError("worker capability message is malformed")
    capability_text = payload["capability"]
    if len(capability_text) != WORKER_CAPABILITY_BYTES * 2:
        raise ValueError("worker capability is malformed")
    try:
        capability = bytes.fromhex(capability_text)
    except ValueError:
        raise ValueError("worker capability is malformed") from None
    grant = _worker_grant_from_payload(payload["grant"])
    if FixedWorkerGrantReader().load() != grant:
        raise ValueError("worker grant lacks durable consumed issuance")
    worker_lease = _WindowsWorkerExecutableLease()
    try:
        worker_binding = worker_lease.binding
    finally:
        worker_lease_closed = worker_lease.close()
    expected_ffmpeg = (
        prepared.ffmpeg_sha256,
        prepared.ffmpeg_version,
        prepared.ffmpeg_size_bytes,
        prepared.ffmpeg_identity_digest,
    )
    if (
        not worker_lease_closed
        or not secrets.compare_digest(
            hashlib.sha256(capability).hexdigest(), grant.capability_digest
        )
        or grant.challenge_digest != challenge_digest
        or grant.worker_executable_sha256 != worker_binding.sha256
        or grant.worker_identity_digest != worker_binding.identity_digest
        or grant.worker_argv_digest != _worker_argv_digest()
        or grant.source_sha256 != _source_sha256()
        or grant.lock_sha256 != _lock_sha256()
        or grant.pose_model_sha256 != POSE_MODEL_SHA256
        or grant.face_model_sha256 != FACE_MODEL_SHA256
        or (
            grant.ffmpeg_sha256,
            grant.ffmpeg_version,
            grant.ffmpeg_size_bytes,
            grant.ffmpeg_identity_digest,
        )
        != expected_ffmpeg
        or grant.job_policy_digest != _worker_job_policy_digest()
        or time.time_ns() > grant.expires_unix_ns
    ):
        raise ValueError("worker launch grant does not match the fixed runtime")
    return grant


_WORKER_PRIVATE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "opaque_device_token",
        "prepared_ffmpeg_sha256",
        "prepared_ffmpeg_version",
        "prepared_ffmpeg_size_bytes",
        "prepared_ffmpeg_identity_digest",
        "prepared_config_digest",
        "device_gate_decision",
        "d1_go",
        "offline",
        "video_only",
        "audio_requested",
        "audio_seal_active",
        "network_guard_active",
        "outbound_network_attempts",
        "raw_retained",
        "stages",
        "mutex_released",
        "child_terminated",
        "pipe_closed",
        "reader_stopped",
        "media_closed",
        "ffmpeg_lease_closed",
        "source_sha256",
        "lock_sha256",
        "pose_model_sha256",
        "face_model_sha256",
        "pose_model_bytes",
        "face_model_bytes",
        "runtime_dependency_version",
        "dependency_pin",
        "requested_duration_seconds",
        "warmup_seconds",
        "frame_bytes",
        "authority_consumed",
        "capture_worker_supervised",
        "capture_deadline_enforced",
        "capture_job_drained",
        "capture_worker_executable_sha256",
        "capture_worker_identity_digest",
        "capture_worker_lease_closed",
        "run_nonce",
        "terminal_receipt_digest",
        "terminal_state_digest",
        "result_digest",
    }
)


@dataclass(frozen=True, slots=True)
class _WorkerMonitorResult:
    payload: dict[str, object] | None
    authorized: bool
    first_frame: bool
    capture_closed: bool
    timed_out: bool
    malformed: bool
    job_drained: bool
    pipe_closed: bool
    reader_stopped: bool
    forced_termination: bool
    exit_code: int | None
    privacy_ready: bool = False
    capture_starting: bool = False
    capture_starting_monotonic_ns: int | None = None
    timeout_failure: NativeFailure | None = None


def _worker_environment(
    challenge: str, prepared: PreparedAuthority | None = None
) -> dict[str, str]:
    if not _is_nonce(challenge):
        raise OSError("fixed worker environment is unavailable")
    system32 = WINDOWS_SYSTEM_DIRECTORY
    system_root = str(Path(system32).parent)
    powershell = str(Path(POWERSHELL_CANONICAL_PATH).parent)
    environment = {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "PATH": os.pathsep.join((powershell, system32)),
        WORKER_CHALLENGE_ENV: challenge,
        "GLOG_minloglevel": "3",
    }
    if prepared is not None:
        environment.update(
            {
                "PDU_D1_N1_FFMPEG_SHA256": prepared.ffmpeg_sha256,
                "PDU_D1_N1_FFMPEG_VERSION": prepared.ffmpeg_version,
                "PDU_D1_N1_FFMPEG_SIZE_BYTES": str(prepared.ffmpeg_size_bytes),
                "PDU_D1_N1_FFMPEG_IDENTITY_DIGEST": prepared.ffmpeg_identity_digest,
            }
        )
    return environment


def _worker_prepared_from_environment(challenge: str) -> PreparedAuthority:
    ffmpeg_sha256 = os.environ.get("PDU_D1_N1_FFMPEG_SHA256", "")
    ffmpeg_version = os.environ.get("PDU_D1_N1_FFMPEG_VERSION", "")
    ffmpeg_identity = os.environ.get("PDU_D1_N1_FFMPEG_IDENTITY_DIGEST", "")
    size_raw = os.environ.get("PDU_D1_N1_FFMPEG_SIZE_BYTES", "")
    if not all(
        _is_nonce(value)
        for value in (challenge, ffmpeg_sha256, ffmpeg_version, ffmpeg_identity)
    ) or not size_raw.isascii() or not size_raw.isdigit():
        raise ValueError("worker FFmpeg configuration is malformed")
    prepared = PreparedAuthority(
        schema_version=2,
        opaque_device_token=_digest(["worker-surrogate-device-v1", challenge]),
        authority_revision=AUTHORITY_REVISION,
        state=AuthorizationState.PREPARED,
        ffmpeg_sha256=ffmpeg_sha256,
        ffmpeg_version=ffmpeg_version,
        ffmpeg_size_bytes=int(size_raw),
        ffmpeg_identity_digest=ffmpeg_identity,
        authorization_nonce=_digest(["worker-surrogate-authority-v1", challenge]),
    )
    if not _prepared_is_valid(prepared):
        raise ValueError("worker FFmpeg configuration is invalid")
    return prepared


class _UnavailableWorkerAuthority:
    def __getattr__(self, name: str) -> object:
        raise OSError(f"worker authority access is forbidden: {name}")


def _json_ready(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_ready(item) for item in value]
    return value


def _emit_worker_message(
    event: str, challenge_digest: str, payload: dict[str, object] | None = None
) -> None:
    message: dict[str, object] = {"event": event, "challenge_digest": challenge_digest}
    if payload is not None:
        message["payload"] = payload
    encoded = json.dumps(
        _json_ready(message),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    if len(encoded.encode("utf-8")) > WORKER_MESSAGE_MAX_BYTES:
        raise ValueError("worker message is oversized")
    sys.stdout.write(encoded + "\n")
    sys.stdout.flush()


def _strict_worker_message(line: bytes) -> dict[str, object]:
    if not line or len(line) > WORKER_MESSAGE_MAX_BYTES:
        raise ValueError("worker message size is invalid")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("worker message has duplicate keys")
            result[key] = value
        return result

    value = json.loads(
        line.decode("utf-8", errors="strict"),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constants are forbidden")),
    )
    if not isinstance(value, dict):
        raise ValueError("worker message root is malformed")
    return cast(dict[str, object], value)


def _serialize_worker_receipt(receipt: NativeReceipt) -> dict[str, object]:
    raw = cast(dict[str, object], asdict(receipt))
    return {
        key: _json_ready(value)
        for key, value in raw.items()
        if key not in _WORKER_PRIVATE_RECEIPT_FIELDS
    }


def _deserialize_worker_receipt(
    payload: dict[str, object],
    prepared: PreparedAuthority,
    *,
    worker_binding: FfmpegBinding,
    worker_supervised: bool,
    deadline_enforced: bool,
    job_drained: bool,
    pipe_closed: bool,
    reader_stopped: bool,
    worker_lease_closed: bool,
    privacy_ready: bool = False,
    capture_starting: bool = False,
    first_frame: bool = False,
    capture_closed: bool = False,
    phase_checked: bool = False,
) -> NativeReceipt:
    expected = set(NativeReceipt.__dataclass_fields__) - _WORKER_PRIVATE_RECEIPT_FIELDS
    if set(payload) != expected:
        raise ValueError("worker receipt fields are malformed")
    outcome_value = payload.get("outcome")
    failure_value = payload.get("failure_code")
    if not isinstance(outcome_value, str) or (
        failure_value is not None and not isinstance(failure_value, str)
    ):
        raise ValueError("worker receipt outcome is malformed")
    outcome = NativeOutcome(outcome_value)
    failure = NativeFailure(failure_value) if failure_value is not None else None
    if failure is NativeFailure.WORKER_PROTOCOL_FAILURE:
        raise ValueError("worker cannot supply a parent protocol failure")
    worker_cleanup_complete = payload.get("worker_cleanup_complete")
    if type(worker_cleanup_complete) is not bool:
        raise ValueError("worker cleanup assertion is malformed")
    if (
        phase_checked
        and outcome is NativeOutcome.NO_GO
        and not _worker_failure_phases_valid(
            failure,
            privacy_ready=privacy_ready,
            capture_starting=capture_starting,
            first_frame=first_frame,
            capture_closed=capture_closed,
            worker_cleanup_complete=worker_cleanup_complete,
        )
    ):
        raise ValueError("worker failure phase is malformed")
    base = _receipt(
        outcome,
        failure,
        prepared=prepared,
        privacy_stop_count=1 if failure is NativeFailure.PRIVACY_STOP else 0,
        mutex_released=job_drained,
        child_terminated=job_drained,
        pipe_closed=pipe_closed and job_drained,
        reader_stopped=reader_stopped and job_drained,
        worker_cleanup_complete=(
            worker_cleanup_complete
            and job_drained
            and pipe_closed
            and reader_stopped
            and worker_lease_closed
        ),
        media_closed=job_drained,
        raw_retained=not job_drained,
        ffmpeg_lease_closed=job_drained,
        capture_worker_supervised=worker_supervised,
        capture_deadline_enforced=deadline_enforced,
        capture_job_drained=job_drained,
        capture_worker_executable_sha256=worker_binding.sha256,
        capture_worker_identity_digest=worker_binding.identity_digest,
        capture_worker_lease_closed=worker_lease_closed,
        authority_consumed=True,
    )
    if outcome is NativeOutcome.NO_GO:
        return base
    raw = cast(dict[str, Any], dict(payload))
    base_raw = asdict(base)
    raw.update(
        {
            name: base_raw[name]
            for name in _WORKER_PRIVATE_RECEIPT_FIELDS
            if name in base_raw
        }
    )
    raw["outcome"] = outcome
    raw["failure_code"] = failure
    receipt = NativeReceipt(**raw)
    return replace(receipt, result_digest=receipt.recompute_digest())


def _candidate_semantics_are_valid(candidate: NativeReceipt) -> bool:
    core = replace(
        candidate,
        run_nonce="0" * 64,
        terminal_receipt_digest=None,
        terminal_state_digest=None,
        result_digest="",
    )
    core_digest = core.recompute_core_digest()
    sealed = replace(
        core,
        terminal_receipt_digest=core_digest,
        terminal_state_digest="1" * 64,
    )
    sealed = replace(sealed, result_digest=sealed.recompute_digest())
    return verify_receipt_semantics(sealed)


def _worker_failure_phases_valid(
    failure: NativeFailure | None,
    *,
    privacy_ready: bool,
    capture_starting: bool,
    first_frame: bool,
    capture_closed: bool,
    worker_cleanup_complete: bool = True,
) -> bool:
    """Accept only worker-originated NO_GO codes at their reachable phase."""
    if failure in {
        None,
        NativeFailure.WORKER_PROTOCOL_FAILURE,
        NativeFailure.CAPTURE_STARTUP_TIMEOUT,
        NativeFailure.PRIVACY_GUARD_TIMEOUT,
        NativeFailure.REAUTHORIZATION_REQUIRED,
        NativeFailure.AUTHORITY_FINALIZATION_FAILED,
        NativeFailure.EXECUTABLE_IDENTITY_UNAVAILABLE,
        NativeFailure.EXECUTABLE_LEASE_INCOMPATIBLE,
        NativeFailure.UNKNOWN_TECHNICAL_FAILURE,
    }:
        return False
    if failure is NativeFailure.POSE_ENGINE_UNAVAILABLE:
        return not privacy_ready and not capture_starting and not first_frame and not capture_closed
    if failure is NativeFailure.SCHEMA_INCOMPATIBLE:
        return privacy_ready and not capture_starting and not first_frame and not capture_closed
    if failure is NativeFailure.INPUT_UNAVAILABLE:
        return privacy_ready and capture_starting and not first_frame and capture_closed
    if failure is NativeFailure.CLEANUP_INCOMPLETE:
        return (
            privacy_ready
            and capture_starting
            and (capture_closed or not worker_cleanup_complete)
        )
    if failure in {
        NativeFailure.PRIVACY_STOP,
        NativeFailure.POSE_ENGINE_EXCEPTION,
        NativeFailure.POSE_OUTPUT_INVALID,
        NativeFailure.QUALITY_INSUFFICIENT,
    }:
        return (
            privacy_ready
            and capture_starting
            and first_frame
            and (capture_closed or not worker_cleanup_complete)
        )
    return privacy_ready and capture_starting


def _emit_worker_phase(event: str, challenge_digest: str, monotonic_ns: int) -> None:
    if event == "PRIVACY_READY":
        _emit_worker_message(event, challenge_digest)
        return
    if event == "CAPTURE_STARTING":
        _emit_worker_message(
            event, challenge_digest, {"worker_monotonic_ns": monotonic_ns}
        )
        return
    raise ValueError("worker phase is invalid")


def _monitor_capture_worker(
    child: subprocess.Popen[bytes],
    job: _WindowsCaptureJob,
    challenge_digest: str,
    grant_id: str,
    *,
    startup_timeout: float = WORKER_AUTHORIZATION_TIMEOUT_SECONDS,
    capture_timeout: float = WORKER_CAPTURE_TIMEOUT_SECONDS,
    report_timeout: float = WORKER_REPORT_TIMEOUT_SECONDS,
) -> _WorkerMonitorResult:
    if child.stdout is None:
        raise OSError("worker output pipe is unavailable")
    stdout = child.stdout
    messages: queue.Queue[bytes | None] = queue.Queue(maxsize=8)

    def read_messages() -> None:
        try:
            while True:
                line = stdout.readline()
                if not line:
                    break
                messages.put(line)
        except Exception:
            pass
        finally:
            try:
                messages.put_nowait(None)
            except queue.Full:
                pass

    reader = threading.Thread(target=read_messages, daemon=True)
    reader.start()
    deadline = time.monotonic() + startup_timeout
    authorized = False
    privacy_ready = False
    capture_starting = False
    capture_starting_monotonic_ns: int | None = None
    first_frame = False
    first_frame_monotonic_ns: int | None = None
    capture_closed = False
    timed_out = False
    timeout_failure: NativeFailure | None = None
    malformed = False
    payload: dict[str, object] | None = None
    while payload is None and not malformed:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            timeout_failure = (
                NativeFailure.WORKER_PROTOCOL_FAILURE
                if not authorized or capture_closed
                else NativeFailure.PRIVACY_GUARD_TIMEOUT
                if not privacy_ready or first_frame
                else NativeFailure.CAPTURE_STARTUP_TIMEOUT
            )
            break
        try:
            line = messages.get(timeout=remaining)
        except queue.Empty:
            timed_out = True
            timeout_failure = (
                NativeFailure.WORKER_PROTOCOL_FAILURE
                if not authorized or capture_closed
                else NativeFailure.PRIVACY_GUARD_TIMEOUT
                if not privacy_ready or first_frame
                else NativeFailure.CAPTURE_STARTUP_TIMEOUT
            )
            break
        if line is None:
            break
        try:
            message = _strict_worker_message(line)
            if message.get("challenge_digest") != challenge_digest:
                raise ValueError("worker challenge mismatch")
            event = message.get("event")
            if event == "AUTHORIZED":
                evidence = message.get("payload")
                if (
                    set(message) != {"event", "challenge_digest", "payload"}
                    or authorized
                    or first_frame
                    or not isinstance(evidence, dict)
                    or set(evidence) != {"grant_id"}
                    or evidence["grant_id"] != grant_id
                ):
                    raise ValueError("worker authorization event is malformed")
                authorized = True
                deadline = time.monotonic() + WORKER_PRIVACY_READY_TIMEOUT_SECONDS
            elif event == "PRIVACY_READY":
                if (
                    set(message) != {"event", "challenge_digest"}
                    or not authorized
                    or privacy_ready
                    or capture_starting
                    or first_frame
                ):
                    raise ValueError("worker privacy-ready event is malformed")
                privacy_ready = True
                deadline = time.monotonic() + WORKER_DEVICE_SETUP_TIMEOUT_SECONDS
            elif event == "CAPTURE_STARTING":
                evidence = message.get("payload")
                if (
                    set(message) != {"event", "challenge_digest", "payload"}
                    or not privacy_ready
                    or capture_starting
                    or first_frame
                    or not isinstance(evidence, dict)
                    or set(evidence) != {"worker_monotonic_ns"}
                    or type(evidence["worker_monotonic_ns"]) is not int
                ):
                    raise ValueError("worker capture-start event is malformed")
                capture_starting_monotonic_ns = evidence["worker_monotonic_ns"]
                observed_ns = time.monotonic_ns()
                if (
                    capture_starting_monotonic_ns <= 0
                    or capture_starting_monotonic_ns > observed_ns
                ):
                    raise ValueError("worker capture-start timestamp is malformed")
                capture_starting = True
                deadline = (
                    capture_starting_monotonic_ns / 1_000_000_000
                    + WORKER_FIRST_FRAME_TIMEOUT_SECONDS
                )
            elif event == "FIRST_FRAME":
                evidence = message.get("payload")
                if (
                    set(message) != {"event", "challenge_digest", "payload"}
                    or not authorized
                    or not privacy_ready
                    or not capture_starting
                    or capture_starting_monotonic_ns is None
                    or first_frame
                    or not isinstance(evidence, dict)
                    or set(evidence) != {"worker_monotonic_ns"}
                    or type(evidence["worker_monotonic_ns"]) is not int
                ):
                    raise ValueError("worker first-frame event is malformed")
                first_frame_monotonic_ns = evidence["worker_monotonic_ns"]
                observed_ns = time.monotonic_ns()
                if (
                    first_frame_monotonic_ns <= 0
                    or first_frame_monotonic_ns > observed_ns
                    or first_frame_monotonic_ns < capture_starting_monotonic_ns
                ):
                    raise ValueError("worker first-frame timestamp is malformed")
                first_frame = True
                deadline = first_frame_monotonic_ns / 1_000_000_000 + capture_timeout
                if deadline <= time.monotonic():
                    timed_out = True
                    break
            elif event == "CAPTURE_CLOSED":
                evidence = message.get("payload")
                if (
                    set(message) != {"event", "challenge_digest", "payload"}
                    or not authorized
                    or not privacy_ready
                    or not capture_starting
                    or capture_closed
                    or capture_starting_monotonic_ns is None
                    or not isinstance(evidence, dict)
                    or set(evidence) != {"worker_monotonic_ns"}
                    or type(evidence["worker_monotonic_ns"]) is not int
                ):
                    raise ValueError("worker capture-close event is malformed")
                capture_closed_ns = evidence["worker_monotonic_ns"]
                observed_ns = time.monotonic_ns()
                if (
                    capture_closed_ns <= 0
                    or capture_closed_ns < capture_starting_monotonic_ns
                    or capture_closed_ns > observed_ns
                    or (
                        first_frame_monotonic_ns is not None
                        and (
                            capture_closed_ns < first_frame_monotonic_ns
                            or capture_closed_ns - first_frame_monotonic_ns
                            > int(capture_timeout * 1_000_000_000)
                        )
                    )
                ):
                    raise ValueError("worker capture-close timestamp is malformed")
                capture_closed = True
                deadline = time.monotonic() + report_timeout
            elif event == "RECEIPT":
                if set(message) != {"event", "challenge_digest", "payload"}:
                    raise ValueError("worker receipt event is malformed")
                raw_payload = message["payload"]
                if not isinstance(raw_payload, dict):
                    raise ValueError("worker receipt payload is malformed")
                payload = cast(dict[str, object], raw_payload)
            else:
                raise ValueError("worker event is unknown")
        except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            malformed = True
    job_drained = False
    forced_termination = False
    if payload is not None and not malformed and not timed_out:
        job_drained = job.wait_drained(child, report_timeout)
    if not job_drained:
        forced_termination = True
        job_drained = job.terminate_and_drain(child)
    exit_code = child.returncode
    pipe_closed = False
    try:
        stdout.close()
        pipe_closed = True
    except Exception:
        pipe_closed = False
    reader.join(timeout=1.0)
    return _WorkerMonitorResult(
        payload=payload,
        authorized=authorized,
        first_frame=first_frame,
        capture_closed=capture_closed,
        timed_out=timed_out,
        malformed=malformed,
        job_drained=job_drained,
        pipe_closed=pipe_closed,
        reader_stopped=not reader.is_alive(),
        forced_termination=forced_termination,
        exit_code=exit_code,
        privacy_ready=privacy_ready,
        capture_starting=capture_starting,
        capture_starting_monotonic_ns=capture_starting_monotonic_ns,
        timeout_failure=timeout_failure,
    )


def _monitor_allows_candidate(monitor: _WorkerMonitorResult) -> bool:
    return (
        monitor.payload is not None
        and monitor.authorized
        and not monitor.timed_out
        and not monitor.malformed
        and monitor.job_drained
        and monitor.pipe_closed
        and monitor.reader_stopped
        and not monitor.forced_termination
        and monitor.exit_code == 0
    )


def _monitor_failure_code(
    monitor: _WorkerMonitorResult, *, worker_lease_closed: bool, job_closed: bool
) -> NativeFailure:
    """Classify only parent-observed worker supervision evidence."""
    if monitor.timed_out:
        if monitor.timeout_failure is not None:
            return monitor.timeout_failure
        if not monitor.authorized or monitor.capture_closed:
            return NativeFailure.WORKER_PROTOCOL_FAILURE
        if not monitor.privacy_ready or monitor.first_frame:
            return NativeFailure.PRIVACY_GUARD_TIMEOUT
        return NativeFailure.CAPTURE_STARTUP_TIMEOUT
    if not worker_lease_closed or not job_closed or not monitor.job_drained:
        return NativeFailure.CLEANUP_INCOMPLETE
    return NativeFailure.WORKER_PROTOCOL_FAILURE


def _supervisor_failure_receipt(
    prepared: PreparedAuthority,
    failure: NativeFailure,
    binding: FfmpegBinding,
    *,
    worker_supervised: bool,
    deadline_enforced: bool,
    job_drained: bool,
    pipe_closed: bool,
    reader_stopped: bool,
    worker_lease_closed: bool,
) -> NativeReceipt:
    return _receipt(
        NativeOutcome.NO_GO,
        failure,
        prepared=prepared,
        mutex_released=job_drained,
        child_terminated=job_drained,
        pipe_closed=pipe_closed and job_drained,
        reader_stopped=reader_stopped and job_drained,
        worker_cleanup_complete=False,
        media_closed=job_drained,
        raw_retained=not job_drained,
        ffmpeg_lease_closed=job_drained,
        capture_worker_supervised=worker_supervised,
        capture_deadline_enforced=deadline_enforced,
        capture_job_drained=job_drained,
        capture_worker_executable_sha256=binding.sha256,
        capture_worker_identity_digest=binding.identity_digest,
        capture_worker_lease_closed=worker_lease_closed,
        authority_consumed=True,
    )


def _run_windows_capture_worker(
    prepared: PreparedAuthority,
    challenge: str,
    grant: WorkerGrant,
    capability: bytes,
) -> NativeReceipt:
    challenge_digest = _digest(["d1-n1-worker-challenge-v1", challenge])
    if FixedWorkerGrantReader().load() != grant:
        raise OSError("worker grant lacks durable consumed issuance")
    lease = _WindowsWorkerExecutableLease()
    binding = lease.binding
    if (
        grant.challenge_digest != challenge_digest
        or grant.worker_executable_sha256 != binding.sha256
        or grant.worker_identity_digest != binding.identity_digest
    ):
        lease.close()
        raise OSError("worker grant does not match the leased worker image")
    job = _WindowsCaptureJob(_worker_job_name(challenge))
    child: subprocess.Popen[bytes] | None = None
    monitor: _WorkerMonitorResult | None = None
    worker_lease_closed = False
    job_closed = False
    try:
        argv = (
            lease.executable,
            "-I",
            "-u",
            "-c",
            WORKER_BOOTSTRAP,
        )
        child = lease._launch_suspended(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            before_resume=job.assign,
            env=_worker_environment(challenge, prepared),
            cwd=POWERSHELL_WORKING_DIRECTORY,
        )
        _send_worker_proceed(child, challenge_digest, grant, capability)
        monitor = _monitor_capture_worker(
            child, job, challenge_digest, grant.grant_id
        )
    finally:
        try:
            worker_lease_closed = lease.close() is True
        except Exception:
            worker_lease_closed = False
        try:
            job_closed = job.close() is True
        except Exception:
            job_closed = False
    if child is None or monitor is None:
        raise OSError("capture worker did not start")
    supervised = job.assigned and monitor.authorized
    deadline_enforced = supervised
    if (
        not _monitor_allows_candidate(monitor)
        or not worker_lease_closed
        or not job_closed
    ):
        failure = _monitor_failure_code(
            monitor, worker_lease_closed=worker_lease_closed, job_closed=job_closed
        )
        return _supervisor_failure_receipt(
            prepared,
            failure,
            binding,
            worker_supervised=supervised,
            deadline_enforced=deadline_enforced,
            job_drained=monitor.job_drained,
            pipe_closed=monitor.pipe_closed,
            reader_stopped=monitor.reader_stopped,
            worker_lease_closed=worker_lease_closed,
        )
    assert monitor.payload is not None
    try:
        candidate = _deserialize_worker_receipt(
            monitor.payload,
            prepared,
            worker_binding=binding,
            worker_supervised=supervised,
            deadline_enforced=deadline_enforced,
            job_drained=monitor.job_drained,
            pipe_closed=monitor.pipe_closed,
            reader_stopped=monitor.reader_stopped,
            worker_lease_closed=worker_lease_closed,
            privacy_ready=monitor.privacy_ready,
            capture_starting=monitor.capture_starting,
            first_frame=monitor.first_frame,
            capture_closed=monitor.capture_closed,
            phase_checked=True,
        )
    except (TypeError, ValueError):
        return _supervisor_failure_receipt(
            prepared,
            NativeFailure.WORKER_PROTOCOL_FAILURE,
            binding,
            worker_supervised=supervised,
            deadline_enforced=deadline_enforced,
            job_drained=monitor.job_drained,
            pipe_closed=monitor.pipe_closed,
            reader_stopped=monitor.reader_stopped,
            worker_lease_closed=worker_lease_closed,
        )
    if (
        candidate.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
        and (
            not monitor.privacy_ready
            or not monitor.capture_starting
            or not monitor.first_frame
            or not monitor.capture_closed
        )
    ) or not _candidate_semantics_are_valid(candidate):
        return _supervisor_failure_receipt(
            prepared,
            NativeFailure.WORKER_PROTOCOL_FAILURE,
            binding,
            worker_supervised=supervised,
            deadline_enforced=deadline_enforced,
            job_drained=monitor.job_drained,
            pipe_closed=monitor.pipe_closed,
            reader_stopped=monitor.reader_stopped,
            worker_lease_closed=worker_lease_closed,
        )
    return candidate


def _capture_worker_main() -> int:
    challenge = os.environ.get(WORKER_CHALLENGE_ENV, "")
    if not _is_nonce(challenge):
        return 2
    challenge_digest = _digest(["d1-n1-worker-challenge-v1", challenge])
    try:
        if not _current_process_in_expected_worker_job(challenge):
            return 3
        prepared = _worker_prepared_from_environment(challenge)
        grant = _receive_worker_launch_grant(challenge, prepared)
        _emit_worker_message(
            "AUTHORIZED", challenge_digest, {"grant_id": grant.grant_id}
        )
        store = cast(FixedLocalAuthorityStore, _UnavailableWorkerAuthority())

        def event_sink(event: str, worker_monotonic_ns: int) -> None:
            _emit_worker_phase(event, challenge_digest, worker_monotonic_ns)

        service = NativePreflightService(
            platform=WindowsNativePlatform(store),
            media=MediaPipeTasksRuntime(),
            store=store,
            defer_terminalization=True,
            event_sink=event_sink,
        )
        candidate = service._run_consumed(prepared)
        _emit_worker_message(
            "RECEIPT", challenge_digest, _serialize_worker_receipt(candidate)
        )
        return 0
    except BaseException:
        return 4


def _fixed_argv(executable: str, current_friendly_name: str) -> tuple[str, ...]:
    return (
        (executable,)
        + FFMPEG_PREFIX
        + (
            "-i",
            f"video={current_friendly_name}",
            "-map",
            "0:v:0",
            "-an",
            "-sn",
            "-dn",
            "-c:v",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        )
    )


def _fixed_argv_template_digest() -> str:
    return _digest(list(_fixed_argv("<EXECUTABLE>", "<SERVER_CAMERA>")))


def nearest_rank(values: tuple[float, ...], percentile: int) -> float:
    if not values or not 1 <= percentile <= 100:
        raise ValueError("nearest rank inputs are malformed")
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * percentile / 100) - 1]


def _bounded_readinto(pipe: RawPipe, buffer: bytearray) -> int | None:
    result: list[int] = []

    def read() -> None:
        try:
            result.append(pipe.readinto(buffer))
        except Exception:
            return

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(timeout=1.0)
    return result[0] if not reader.is_alive() and result else None


def _close_media(media: MediaRuntime) -> bool:
    try:
        media.close()
    except Exception:
        return False
    return True


def _release_mutex(mutex: NamedMutex) -> bool:
    try:
        result = mutex.release()
    except Exception:
        return False
    return result is not False


def _cleanup_child(
    child: VideoChild | None, reader: _FrameReader | None
) -> tuple[bool, bool, bool]:
    pipe_closed = False
    child_terminated = False
    if child is not None:
        terminated = False
        try:
            child.terminate()
            child.wait(timeout=2.0)
            terminated = True
        except Exception:
            kill = getattr(child, "kill", None)
            if callable(kill):
                try:
                    kill()
                    child.wait(timeout=2.0)
                    terminated = True
                except Exception:
                    terminated = False
        child_terminated = terminated
    try:
        reader_stopped = reader is None or reader.stop()
    except Exception:
        reader_stopped = False
    if child is not None and reader_stopped:
        try:
            child.stdout.close()
            pipe_closed = True
        except Exception:
            pipe_closed = False
    return pipe_closed, child_terminated, reader_stopped


def verify_receipt_semantics(receipt: NativeReceipt) -> bool:
    if not isinstance(receipt, NativeReceipt) or receipt.schema_version != 2:
        return False
    if receipt.result_digest != receipt.recompute_digest():
        return False
    if receipt.authority_consumed:
        if (
            receipt.outcome is NativeOutcome.PREPARED
            or not _is_nonce(receipt.run_nonce)
            or not _is_digest(receipt.terminal_receipt_digest)
            or not _is_digest(receipt.terminal_state_digest)
            or receipt.terminal_receipt_digest != receipt.recompute_core_digest()
        ):
            return False
    elif any(
        value is not None
        for value in (
            receipt.run_nonce,
            receipt.terminal_receipt_digest,
            receipt.terminal_state_digest,
        )
    ):
        return False
    if receipt.device_gate_decision is not DeviceGateDecision.UNVERIFIED or receipt.d1_go:
        return False
    if receipt.frame_bytes != FRAME_BYTES or receipt.audio_requested:
        return False
    if receipt.raw_retained and receipt.failure_code not in {
        NativeFailure.PRIVACY_STOP,
        NativeFailure.CLEANUP_INCOMPLETE,
    }:
        return False
    if (
        receipt.source_sha256 != _source_sha256()
            or receipt.lock_sha256 != _lock_sha256()
            or receipt.pose_model_sha256 != POSE_MODEL_SHA256
            or receipt.face_model_sha256 != FACE_MODEL_SHA256
            or receipt.pose_model_bytes != POSE_MODEL_BYTES
            or receipt.face_model_bytes != FACE_MODEL_BYTES
            or receipt.runtime_dependency_version != "1.0.1"
            or receipt.dependency_pin != DEPENDENCY_PIN
        or receipt.offline is not True
        or receipt.video_only is not True
            or receipt.audio_seal_active is not True
            or receipt.network_guard_active is not True
            or receipt.outbound_network_attempts != 0
    ):
        return False
    if receipt.stages != (StageState.NOT_ATTEMPTED,) * 4:
        return False
    if receipt.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS:
        if (
            receipt.failure_code is not None
            or receipt.privacy_stop_count != 0
            or receipt.face_detections != 0
            or receipt.pose_detections != 0
            or receipt.processed_frames + receipt.dropped_explicit_frames + receipt.failed_frames
            != receipt.delivered_frames
            or receipt.measured_total_seconds < PREFLIGHT_SECONDS
            or receipt.measured_post_warmup_seconds < PREFLIGHT_SECONDS - WARMUP_SECONDS
            or receipt.delivered_frames_per_second is None
            or receipt.delivered_frames_per_second < 13.5
            or receipt.p95_ingress_gap_ms is None
            or receipt.p95_ingress_gap_ms > 200
            or receipt.p95_pose_latency_ms is None
            or receipt.p95_pose_latency_ms > 200
            or receipt.p99_pose_latency_ms is None
            or receipt.p99_pose_latency_ms > 500
            or receipt.backlog_ms is None
            or receipt.backlog_ms > 2000
            or not receipt.mutex_released
            or not receipt.child_terminated
            or not receipt.pipe_closed
            or not receipt.reader_stopped
            or not receipt.worker_cleanup_complete
            or not receipt.media_closed
            or not receipt.capture_worker_supervised
            or not receipt.capture_deadline_enforced
            or not receipt.capture_job_drained
            or not _is_digest(receipt.capture_worker_executable_sha256)
            or not _is_digest(receipt.capture_worker_identity_digest)
            or not receipt.capture_worker_lease_closed
            or not receipt.authority_consumed
            or receipt.prepared_config_digest is None
            or not _is_digest(receipt.fixed_argv_digest)
            or receipt.fixed_argv_digest != _fixed_argv_template_digest()
            or not _is_digest(receipt.prepared_config_digest)
            or not _is_digest(receipt.ffmpeg_sha256)
            or receipt.ffmpeg_version is None
            or receipt.ffmpeg_sha256 != receipt.prepared_ffmpeg_sha256
            or receipt.ffmpeg_version != receipt.prepared_ffmpeg_version
            or receipt.ffmpeg_size_bytes is None
            or receipt.ffmpeg_size_bytes <= 0
            or receipt.ffmpeg_size_bytes != receipt.prepared_ffmpeg_size_bytes
            or not _is_digest(receipt.ffmpeg_identity_digest)
            or receipt.ffmpeg_identity_digest != receipt.prepared_ffmpeg_identity_digest
            or not receipt.ffmpeg_lease_verified
            or not receipt.ffmpeg_lease_closed
        ):
            return False
        numeric = (
            receipt.measured_total_seconds,
            receipt.measured_post_warmup_seconds,
            receipt.delivered_frames_per_second,
            receipt.p95_ingress_gap_ms,
            receipt.p95_pose_latency_ms,
            receipt.p99_pose_latency_ms,
            receipt.backlog_ms,
        )
        if not all(
            isinstance(value, float) and math.isfinite(value) and value >= 0 for value in numeric
        ):
            return False
        counts = (
            receipt.delivered_frames,
            receipt.processed_frames,
            receipt.dropped_explicit_frames,
            receipt.failed_frames,
            receipt.privacy_checked_frames,
            receipt.privacy_stop_count,
        )
        if not all(type(value) is int and value >= 0 for value in counts):
            return False
        basis = (
            receipt.received_frames,
            receipt.warmup_frames,
            receipt.post_attempted_frames,
            receipt.post_successful_frames,
            receipt.dropped_short_frames,
            receipt.inference_failure_frames,
            receipt.privacy_terminal_frames,
            receipt.delivery_failure_frames,
            receipt.post_elapsed_ns,
            receipt.max_stall_gap_ns,
            receipt.backlog_ns,
        )
        if not all(type(value) is int and value >= 0 for value in basis):
            return False
        if receipt.received_frames != receipt.warmup_frames + receipt.post_attempted_frames:
            return False
        if receipt.post_attempted_frames != (
            receipt.post_successful_frames
            + receipt.dropped_short_frames
            + receipt.inference_failure_frames
            + receipt.privacy_terminal_frames
            + receipt.delivery_failure_frames
        ):
            return False
        if (
            receipt.delivered_frames != receipt.received_frames
            or receipt.processed_frames != receipt.warmup_frames + receipt.post_successful_frames
            or receipt.dropped_explicit_frames != receipt.dropped_short_frames
            or receipt.failed_frames
            != receipt.inference_failure_frames
            + receipt.privacy_terminal_frames
            + receipt.delivery_failure_frames
            or receipt.privacy_checked_frames != receipt.processed_frames
        ):
            return False
        if (
            receipt.post_elapsed_ns == 0
            or receipt.max_stall_gap_ns >= 1_000_000_000
            or receipt.backlog_ns > 2_000_000_000
            or receipt.delivery_failure_frames != 0
            or receipt.privacy_terminal_frames != 0
            or receipt.post_successful_frames * 100 < receipt.post_attempted_frames * 99
            or (
                receipt.dropped_short_frames + receipt.inference_failure_frames
            ) * 100
            > receipt.post_attempted_frames
        ):
            return False
        expected_fps = receipt.post_successful_frames * 1_000_000_000 / receipt.post_elapsed_ns
        if not math.isclose(receipt.delivered_frames_per_second, expected_fps, abs_tol=0.000001):
            return False
        if not math.isclose(
            receipt.measured_post_warmup_seconds,
            receipt.post_elapsed_ns / 1_000_000_000,
            abs_tol=0.000001,
        ):
            return False
        if not math.isclose(receipt.backlog_ms, receipt.backlog_ns / 1_000_000, abs_tol=0.000001):
            return False
    elif receipt.outcome is NativeOutcome.NO_GO:
        if receipt.failure_code is None:
            return False
        if receipt.failure_code in {
            NativeFailure.FRAME_READER_EXCEPTION,
            NativeFailure.CAPTURE_RUNTIME_EXCEPTION,
            NativeFailure.CLEANUP_INCOMPLETE,
            NativeFailure.WORKER_PROTOCOL_FAILURE,
        } and receipt.outcome is not NativeOutcome.NO_GO:
            return False
        if receipt.failure_code is NativeFailure.CLEANUP_INCOMPLETE and (
            receipt.worker_cleanup_complete
            and all(
                (
                    receipt.mutex_released,
                    receipt.child_terminated,
                    receipt.pipe_closed,
                    receipt.reader_stopped,
                    receipt.media_closed,
                    receipt.ffmpeg_lease_closed,
                    receipt.capture_job_drained,
                    receipt.capture_worker_lease_closed,
                )
            )
        ):
            return False
        if receipt.failure_code is not NativeFailure.PRIVACY_STOP and any(
            (
                receipt.privacy_stop_count,
                receipt.face_detections,
                receipt.pose_detections,
                receipt.privacy_terminal_frames,
            )
        ):
            return False
        if receipt.failure_code is NativeFailure.PRIVACY_STOP and (
            receipt.delivered_frames != 0
            or receipt.processed_frames != 0
            or receipt.privacy_stop_count != 1
        ):
            return False
    elif receipt.outcome is not NativeOutcome.PREPARED:
        return False
    return True


def _verify_terminal_receipt_with_store(
    receipt: NativeReceipt, store: AuthorityStore
) -> bool:
    if not verify_receipt_semantics(receipt) or not receipt.authority_consumed:
        return False
    try:
        terminal = store.load_terminal()
    except Exception:
        return False
    if terminal is None:
        return False
    return (
        terminal.prepared_config_digest == receipt.prepared_config_digest
        and terminal.run_nonce == receipt.run_nonce
        and terminal.receipt_core_digest == receipt.terminal_receipt_digest
        and terminal.outcome == receipt.outcome.value
        and terminal.failure_code
        == (receipt.failure_code.value if receipt.failure_code is not None else "NONE")
        and terminal.record_digest == receipt.terminal_state_digest
        and receipt.source_sha256 == _source_sha256()
        and receipt.lock_sha256 == _lock_sha256()
        and receipt.pose_model_sha256 == POSE_MODEL_SHA256
        and receipt.face_model_sha256 == FACE_MODEL_SHA256
        and receipt.runtime_dependency_version == "1.0.1"
    )


def verify_terminal_receipt(receipt: NativeReceipt) -> bool:
    """Parameter-free durable verification; it never enumerates or opens a device."""

    return _verify_terminal_receipt_with_store(receipt, FixedLocalAuthorityStore())


def _prepared_is_valid(value: PreparedAuthority | None) -> bool:
    return (
        isinstance(value, PreparedAuthority)
        and type(value.schema_version) is int
        and value.schema_version == 2
        and _is_digest(value.opaque_device_token)
        and type(value.authority_revision) is str
        and value.authority_revision == AUTHORITY_REVISION
        and type(value.state) is AuthorizationState
        and value.state
        in {
            AuthorizationState.PENDING,
            AuthorizationState.PREPARED,
            AuthorizationState.CONSUMED,
            AuthorizationState.TERMINAL,
        }
        and _is_digest(value.ffmpeg_sha256)
        and _is_digest(value.ffmpeg_version)
        and type(value.ffmpeg_size_bytes) is int
        and value.ffmpeg_size_bytes > 0
        and _is_digest(value.ffmpeg_identity_digest)
        and _is_nonce(value.authorization_nonce)
    )


def _safe_directshow_name(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9 _().-]{1,128}", value) is not None


def _platform_ffmpeg_identity(
    platform: NativePlatform, digest: str, version: str
) -> tuple[int, str, bool]:
    method = getattr(platform, "ffmpeg_identity", None)
    if callable(method):
        size, identity, verified = method()
        if type(size) is not int or size <= 0 or not _is_digest(identity):
            raise ValueError("FFmpeg identity evidence is malformed")
        return size, identity, bool(verified)
    return 1, _digest(["injected-native-platform", digest, version]), True


def _platform_ffmpeg_verified(platform: NativePlatform) -> bool:
    method = getattr(platform, "ffmpeg_lease_verified", None)
    return bool(method()) if callable(method) else True


def _close_platform_ffmpeg_lease(platform: NativePlatform) -> bool:
    method = getattr(platform, "close_ffmpeg_lease", None)
    if not callable(method):
        return True
    try:
        return bool(method())
    except Exception:
        return False


@contextmanager
def _authority_write_guard() -> Iterator[None]:
    mutex = WindowsNamedMutex(AUTHORITY_MUTEX_NAME)
    if not mutex.acquire():
        raise OSError("authority writer is unavailable")
    try:
        yield
    finally:
        if mutex.release() is not True:
            raise OSError("authority writer cleanup failed")


def _receipt(
    outcome: NativeOutcome,
    failure: NativeFailure | None,
    *,
    prepared: PreparedAuthority | None = None,
    fixed_argv_digest: str | None = None,
    ffmpeg_sha256: str | None = None,
    ffmpeg_version: str | None = None,
    ffmpeg_size_bytes: int | None = None,
    ffmpeg_identity_digest: str | None = None,
    ffmpeg_lease_verified: bool = False,
    ffmpeg_lease_closed: bool = True,
    delivered_frames: int = 0,
    processed_frames: int = 0,
    privacy_checked_frames: int = 0,
    privacy_stop_count: int = 0,
    face_detections: int = 0,
    pose_detections: int = 0,
    measured_total_seconds: float = 0.0,
    measured_post_warmup_seconds: float = 0.0,
    delivered_frames_per_second: float | None = None,
    p95_ingress_gap_ms: float | None = None,
    p95_pose_latency_ms: float | None = None,
    p99_pose_latency_ms: float | None = None,
    backlog_ms: float | None = None,
    raw_retained: bool = False,
    mutex_released: bool = False,
    child_terminated: bool = False,
    pipe_closed: bool = False,
    reader_stopped: bool = False,
    worker_cleanup_complete: bool | None = None,
    media_closed: bool = False,
    capture_worker_supervised: bool = False,
    capture_deadline_enforced: bool = False,
    capture_job_drained: bool = False,
    capture_worker_executable_sha256: str | None = None,
    capture_worker_identity_digest: str | None = None,
    capture_worker_lease_closed: bool = False,
    authority_consumed: bool = False,
    received_frames: int = 0,
    warmup_frames: int = 0,
    post_attempted_frames: int = 0,
    post_successful_frames: int = 0,
    dropped_short_frames: int = 0,
    inference_failure_frames: int = 0,
    privacy_terminal_frames: int = 0,
    delivery_failure_frames: int = 0,
    post_elapsed_ns: int = 0,
    max_stall_gap_ns: int = 0,
    backlog_ns: int = 0,
) -> NativeReceipt:
    derived_attempted = (
        post_successful_frames
        + dropped_short_frames
        + inference_failure_frames
        + privacy_terminal_frames
        + delivery_failure_frames
    )
    if post_attempted_frames not in {0, derived_attempted}:
        raise ValueError("aggregate attempts are inconsistent")
    post_attempted_frames = derived_attempted
    received_frames = warmup_frames + post_attempted_frames
    delivered_frames = received_frames
    processed_frames = warmup_frames + post_successful_frames
    dropped_explicit_frames = dropped_short_frames
    failed_frames = inference_failure_frames + privacy_terminal_frames + delivery_failure_frames
    if outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS:
        if privacy_stop_count or privacy_terminal_frames or face_detections or pose_detections:
            raise ValueError("privacy evidence cannot issue a pass receipt")
        privacy_checked_frames = processed_frames
    pose_hash, face_hash, pose_bytes, face_bytes, installed = _observed_runtime_binding()
    receipt = NativeReceipt(
        schema_version=2,
        outcome=outcome,
        failure_code=failure,
        device_gate_decision=DeviceGateDecision.UNVERIFIED,
        d1_go=False,
        opaque_device_token=prepared.opaque_device_token if prepared else None,
        ffmpeg_sha256=ffmpeg_sha256,
        ffmpeg_version=ffmpeg_version,
        prepared_ffmpeg_sha256=prepared.ffmpeg_sha256 if prepared else None,
        prepared_ffmpeg_version=prepared.ffmpeg_version if prepared else None,
        prepared_ffmpeg_size_bytes=prepared.ffmpeg_size_bytes if prepared else None,
        prepared_ffmpeg_identity_digest=prepared.ffmpeg_identity_digest if prepared else None,
        ffmpeg_size_bytes=(
            ffmpeg_size_bytes
            if ffmpeg_size_bytes is not None
            else prepared.ffmpeg_size_bytes
            if prepared
            else None
        ),
        ffmpeg_identity_digest=(
            ffmpeg_identity_digest
            if ffmpeg_identity_digest is not None
            else prepared.ffmpeg_identity_digest
            if prepared
            else None
        ),
        ffmpeg_lease_verified=ffmpeg_lease_verified,
        ffmpeg_lease_closed=ffmpeg_lease_closed,
        fixed_argv_digest=fixed_argv_digest,
        frame_bytes=FRAME_BYTES,
        requested_duration_seconds=PREFLIGHT_SECONDS,
        warmup_seconds=WARMUP_SECONDS,
        delivered_frames=delivered_frames,
        processed_frames=processed_frames,
        dropped_explicit_frames=dropped_explicit_frames,
        failed_frames=failed_frames,
        privacy_checked_frames=privacy_checked_frames,
        privacy_stop_count=privacy_stop_count,
        face_detections=face_detections,
        pose_detections=pose_detections,
        measured_total_seconds=measured_total_seconds,
        measured_post_warmup_seconds=measured_post_warmup_seconds,
        delivered_frames_per_second=delivered_frames_per_second,
        p95_ingress_gap_ms=p95_ingress_gap_ms,
        p95_pose_latency_ms=p95_pose_latency_ms,
        p99_pose_latency_ms=p99_pose_latency_ms,
        backlog_ms=backlog_ms,
        raw_retained=raw_retained,
        audio_requested=False,
        stages=(StageState.NOT_ATTEMPTED,) * 4,
        mutex_released=mutex_released,
        child_terminated=child_terminated,
        pipe_closed=pipe_closed,
        reader_stopped=reader_stopped,
        worker_cleanup_complete=(
            worker_cleanup_complete
            if worker_cleanup_complete is not None
            else not raw_retained
            and mutex_released
            and child_terminated
            and pipe_closed
            and reader_stopped
            and media_closed
            and ffmpeg_lease_closed
        ),
        media_closed=media_closed,
        capture_worker_supervised=capture_worker_supervised,
        capture_deadline_enforced=capture_deadline_enforced,
        capture_job_drained=capture_job_drained,
        capture_worker_executable_sha256=capture_worker_executable_sha256,
        capture_worker_identity_digest=capture_worker_identity_digest,
        capture_worker_lease_closed=capture_worker_lease_closed,
        source_sha256=_source_sha256(),
        lock_sha256=_lock_sha256(),
        pose_model_sha256=pose_hash,
        face_model_sha256=face_hash,
        pose_model_bytes=pose_bytes,
        face_model_bytes=face_bytes,
        runtime_dependency_version=installed,
        prepared_config_digest=_digest(asdict(prepared)) if prepared else None,
        dependency_pin=DEPENDENCY_PIN,
        offline=_install_network_guard() and _OUTBOUND_NETWORK_ATTEMPTS == 0,
        video_only=True,
        audio_seal_active=_install_audio_import_seal(),
        network_guard_active=_NETWORK_GUARD_ACTIVE,
        outbound_network_attempts=_OUTBOUND_NETWORK_ATTEMPTS,
        authority_consumed=authority_consumed,
        received_frames=received_frames,
        warmup_frames=warmup_frames,
        post_attempted_frames=post_attempted_frames,
        post_successful_frames=post_successful_frames,
        dropped_short_frames=dropped_short_frames,
        inference_failure_frames=inference_failure_frames,
        privacy_terminal_frames=privacy_terminal_frames,
        delivery_failure_frames=delivery_failure_frames,
        post_elapsed_ns=post_elapsed_ns,
        max_stall_gap_ns=max_stall_gap_ns,
        backlog_ns=backlog_ns,
        run_nonce=None,
        terminal_receipt_digest=None,
        terminal_state_digest=None,
        result_digest="",
    )
    issued = replace(receipt, result_digest=receipt.recompute_digest())
    return issued


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _is_nonce(value: object) -> bool:
    return _is_digest(value)


def _strict_json_object(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) > 32_768:
        raise ValueError("authority JSON is oversized")
    text = data.decode("utf-8", errors="strict")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("authority JSON has duplicate keys")
            result[key] = value
        return result

    value = json.loads(
        text,
        object_pairs_hook=pairs,
        parse_float=lambda _: (_ for _ in ()).throw(ValueError("floats are forbidden")),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constants are forbidden")),
    )
    if not isinstance(value, dict):
        raise ValueError("authority JSON root is malformed")
    return value


def _atomic_json_write(path: Path, value: object, *, create_only: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    if len(encoded) > 32_768:
        raise ValueError("authority JSON is oversized")
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if create_only:
            _atomic_move_without_replace(temporary, path)
        else:
            os.replace(temporary, path)
        if path.read_bytes() != encoded:
            raise OSError("authority readback mismatch")
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _atomic_move_without_replace(source: Path, destination: Path) -> None:
    if os.name == "nt" and hasattr(ctypes, "WinDLL"):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
        kernel32.MoveFileExW.restype = ctypes.c_int
        if not kernel32.MoveFileExW(str(source), str(destination), 0x8):
            error = ctypes.get_last_error()
            if error in {80, 183}:
                raise FileExistsError(destination.name)
            raise ctypes.WinError(error)
        return
    os.link(source, destination)
    source.unlink()


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _lock_sha256() -> str:
    return hashlib.sha256((Path(__file__).parents[2] / "uv.lock").read_bytes()).hexdigest()


if __name__ == "__main__":
    if sys.argv[1:] != [WORKER_ARGUMENT]:
        raise SystemExit(2)
    raise SystemExit(_capture_worker_main())
