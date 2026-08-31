from __future__ import annotations

import ctypes
import hashlib
import inspect
import json
import socket
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

import pdu_exam_observer.m2_d1_native as native
from pdu_exam_observer.m2_d1_native import (
    FFMPEG_PREFIX,
    FRAME_BYTES,
    AuthorizationState,
    CameraCandidate,
    DeviceGateDecision,
    FixedLocalAuthorityStore,
    MediaPipeTasksRuntime,
    NativeFailure,
    NativeOutcome,
    NativePreflightService,
    PreparedAuthority,
    StageState,
    TerminalAuthority,
    WindowsExecutableLease,
    WindowsNamedMutex,
    _RunState,
    _threshold_failure,
    verify_receipt_semantics,
)


class FakeStore:
    def __init__(self, prepared: PreparedAuthority | None = None) -> None:
        self.prepared = prepared
        self.saved: PreparedAuthority | None = None
        self.consumed = False
        self.terminal: TerminalAuthority | None = None
        self.worker_grant: native.WorkerGrant | None = None

    def load(self) -> PreparedAuthority | None:
        return self.prepared

    def save(self, value: PreparedAuthority) -> None:
        self.saved = value
        self.prepared = value

    def finalize(self, value: PreparedAuthority) -> bool:
        if self.prepared != value or value.state is not AuthorizationState.PENDING:
            return False
        self.prepared = replace(value, state=AuthorizationState.PREPARED)
        self.saved = self.prepared
        return True

    def consume(self, value: PreparedAuthority) -> bool:
        if self.consumed or self.prepared != value or self.terminal is not None:
            return False
        self.consumed = True
        self.prepared = replace(value, state=AuthorizationState.CONSUMED)
        return True

    def issue_worker_grant(
        self, value: PreparedAuthority, grant: native.WorkerGrant
    ) -> bool:
        if (
            self.worker_grant is not None
            or self.prepared != replace(value, state=AuthorizationState.CONSUMED)
            or self.terminal is not None
        ):
            return False
        self.worker_grant = grant
        return True

    def load_worker_grant(self) -> native.WorkerGrant | None:
        return self.worker_grant

    def revoke_worker_grant(self, grant: native.WorkerGrant) -> bool:
        if self.worker_grant != grant:
            return False
        revoked = replace(grant, state="REVOKED", record_digest="")
        self.worker_grant = replace(
            revoked, record_digest=revoked.recompute_digest()
        )
        return True

    def finalize_terminal(
        self,
        value: PreparedAuthority,
        *,
        run_nonce: str,
        receipt_core_digest: str,
        outcome: NativeOutcome,
        failure: NativeFailure | None,
    ) -> TerminalAuthority | None:
        if (
            self.terminal is not None
            or self.prepared != replace(value, state=AuthorizationState.CONSUMED)
            or outcome is NativeOutcome.PREPARED
        ):
            return None
        core = {
            "schema_version": 2,
            "authority_revision": native.AUTHORITY_REVISION,
            "prepared_config_digest": native._digest(native.asdict(value)),
            "run_nonce": run_nonce,
            "receipt_core_digest": receipt_core_digest,
            "outcome": outcome.value,
            "failure_code": failure.value if failure is not None else "NONE",
        }
        self.terminal = TerminalAuthority(**core, record_digest=native._digest(core))
        return self.terminal

    def load_terminal(self) -> TerminalAuthority | None:
        return self.terminal


class FakeMutex:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired = acquired
        self.released = 0

    def acquire(self) -> bool:
        return self.acquired

    def release(self) -> None:
        self.released += 1


class FakePipe:
    def __init__(self, frames: int) -> None:
        self.frames = frames
        self.closed = False

    def readinto(self, buffer: bytearray) -> int:
        if self.frames <= 0:
            return 0
        self.frames -= 1
        return len(buffer)

    def close(self) -> None:
        self.closed = True


class FakeChild:
    def __init__(self, frames: int) -> None:
        self.stdout = FakePipe(frames)
        self.terminated = 0

    def terminate(self) -> None:
        self.terminated += 1

    def wait(self, timeout: float) -> None:
        del timeout


class FakePlatform:
    def __init__(
        self,
        *,
        cameras: tuple[CameraCandidate, ...] = (CameraCandidate("camera-1", True, True),),
        executable_hash: str = "a" * 64,
        frames: int = 902,
    ) -> None:
        self.cameras = cameras
        self.executable_hash = executable_hash
        self.frames = frames
        self.mutex = FakeMutex()
        self.argv: tuple[str, ...] | None = None
        self.child: FakeChild | None = None
        self.started = 0
        self.clock = 1_000_000_000

    def camera_class_devices(self) -> tuple[CameraCandidate, ...]:
        return self.cameras

    def ffmpeg_authority(self) -> tuple[str, str, str]:
        return ("C:\\fixed\\ffmpeg.exe", self.executable_hash, "c" * 64)

    def sha256_of_executable(self, executable: str) -> str:
        assert executable == "C:\\fixed\\ffmpeg.exe"
        return self.executable_hash

    def named_mutex(self) -> FakeMutex:
        return self.mutex

    def launch_video_only(self, argv: tuple[str, ...]) -> FakeChild:
        self.argv = argv
        self.started += 1
        self.child = FakeChild(self.frames)
        return self.child

    def monotonic_ns(self) -> int:
        result = self.clock
        self.clock += 1_000_000_000 // 45
        return result


class FakeMedia:
    def __init__(self, *, face_at: int | None = None, pose_at: int | None = None) -> None:
        self.face_at = face_at
        self.pose_at = pose_at
        self.live = 0
        self.faces = 0
        self.poses = 0
        self.closed = 0

    def liveness(self) -> bool:
        self.live += 1
        return True

    def inspect_face(self, frame: memoryview, timestamp_ms: int) -> bool:
        del frame, timestamp_ms
        self.faces += 1
        return self.face_at == self.faces

    def inspect_pose(self, frame: memoryview, timestamp_ms: int) -> bool:
        del frame, timestamp_ms
        self.poses += 1
        return self.pose_at == self.poses

    def close(self) -> None:
        self.closed += 1


def _prepared(platform: FakePlatform) -> PreparedAuthority:
    return PreparedAuthority(
        schema_version=2,
        opaque_device_token=hashlib.sha256(b"camera-1").hexdigest(),
        authority_revision="d1-n1-authority-v2",
        state=AuthorizationState.PREPARED,
        ffmpeg_sha256=platform.executable_hash,
        ffmpeg_version="c" * 64,
        ffmpeg_size_bytes=1,
        ffmpeg_identity_digest=native._digest(
            ["injected-native-platform", platform.executable_hash, "c" * 64]
        ),
        authorization_nonce="d" * 64,
    )


def test_prepare_requires_one_camera_and_liveness_before_authority_save() -> None:
    platform = FakePlatform()
    media = FakeMedia()
    store = FakeStore()
    service = NativePreflightService(platform=platform, media=media, store=store)
    receipt = service.prepare()
    assert receipt.outcome is NativeOutcome.PREPARED
    assert receipt.device_gate_decision is DeviceGateDecision.UNVERIFIED
    assert receipt.opaque_device_token != "camera-1"
    assert store.saved is not None and store.saved.opaque_device_token != "camera-1"
    assert media.live == 1 and platform.started == 0
    malformed = NativePreflightService(
        platform=FakePlatform(cameras=()), media=FakeMedia(), store=FakeStore()
    ).prepare()
    assert malformed.failure_code is NativeFailure.SCHEMA_INCOMPATIBLE
    second = NativePreflightService(
        platform=FakePlatform(), media=FakeMedia(), store=FakeStore()
    ).prepare()
    assert second.opaque_device_token != receipt.opaque_device_token


@pytest.mark.parametrize("raw", (b"{", b'{"extra":true}', b'{"schema_version":"1"}'))
def test_present_invalid_fixed_store_is_never_treated_as_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: bytes
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    store = FixedLocalAuthorityStore(tmp_path)
    store._root.mkdir(parents=True)  # type: ignore[attr-defined]
    store._prepared_path.write_bytes(raw)  # type: ignore[attr-defined]
    platform = FakePlatform()
    receipt = NativePreflightService(platform=platform, media=FakeMedia(), store=store).prepare()
    assert receipt.failure_code is NativeFailure.SCHEMA_INCOMPATIBLE
    assert store._prepared_path.read_bytes() == raw  # type: ignore[attr-defined]


def test_consumed_fixed_store_survives_restart_and_prepare_cannot_reset_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    platform = FakePlatform()
    store = FixedLocalAuthorityStore(tmp_path)
    store.save(replace(_prepared(platform), state=AuthorizationState.CONSUMED))
    before = store._prepared_path.read_bytes()  # type: ignore[attr-defined]
    restarted = FixedLocalAuthorityStore(tmp_path)
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=restarted
    ).prepare()
    assert receipt.failure_code is NativeFailure.REAUTHORIZATION_REQUIRED
    assert restarted._prepared_path.read_bytes() == before  # type: ignore[attr-defined]


def test_preflight_uses_only_the_exact_fixed_video_only_argv_and_cleans_up() -> None:
    platform = FakePlatform()
    media = FakeMedia()
    service = NativePreflightService(
        platform=platform, media=media, store=FakeStore(_prepared(platform))
    )
    receipt = service.preflight()
    assert receipt.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    assert receipt.device_gate_decision is DeviceGateDecision.UNVERIFIED
    assert receipt.d1_go is False
    assert platform.argv == ("C:\\fixed\\ffmpeg.exe",) + FFMPEG_PREFIX + (
        "-i",
        "video=camera-1",
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
    assert receipt.frame_bytes == FRAME_BYTES and receipt.raw_retained is False
    assert receipt.audio_requested is False
    assert receipt.p95_ingress_gap_ms is not None and receipt.p95_ingress_gap_ms > 60
    assert receipt.stages == (StageState.NOT_ATTEMPTED,) * 4
    assert platform.mutex.released == 1
    assert platform.child is not None and platform.child.terminated == 1
    assert media.closed == 1
    assert verify_receipt_semantics(receipt)


def test_preflight_hash_mismatch_fails_before_process_start() -> None:
    platform = FakePlatform(executable_hash="not-a-sha256")
    service = NativePreflightService(
        platform=platform,
        media=FakeMedia(),
        store=FakeStore(_prepared(platform)),
    )
    receipt = service.preflight()
    assert receipt.failure_code is NativeFailure.SCHEMA_INCOMPATIBLE
    assert platform.started == 0


def test_prepared_ffmpeg_comparison_mismatch_fails_before_process_start() -> None:
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform,
        media=FakeMedia(),
        store=FakeStore(replace(_prepared(platform), ffmpeg_sha256="b" * 64)),
    ).preflight()
    assert receipt.failure_code is NativeFailure.SCHEMA_INCOMPATIBLE
    assert platform.started == 0


def test_privacy_stop_is_minimal_and_precedes_later_pose_work() -> None:
    platform = FakePlatform(frames=902)
    media = FakeMedia(face_at=2, pose_at=100)
    receipt = NativePreflightService(
        platform=platform, media=media, store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.failure_code is NativeFailure.PRIVACY_STOP
    assert receipt.delivered_frames == 0 and receipt.processed_frames == 0
    assert receipt.privacy_checked_frames == 1 and receipt.privacy_stop_count == 1
    assert receipt.authority_consumed is True
    assert media.poses == 1
    assert receipt.stages == (StageState.NOT_ATTEMPTED,) * 4
    assert verify_receipt_semantics(receipt)


@pytest.mark.parametrize(
    "frames, code",
    ((0, NativeFailure.INPUT_UNAVAILABLE), (1, NativeFailure.INPUT_MALFORMED)),
)
def test_partial_or_empty_frame_fails_closed(frames: int, code: NativeFailure) -> None:
    platform = FakePlatform(frames=frames)
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.failure_code is code
    assert platform.mutex.released == 1


def test_public_actions_are_parameter_free_and_source_has_no_audio_or_download_surface() -> None:
    assert NativePreflightService.prepare.__code__.co_argcount == 1
    assert NativePreflightService.preflight.__code__.co_argcount == 1
    source = (
        Path(__file__).parents[2] / "src" / "pdu_exam_observer" / "m2_d1_native.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "audio=",
        "-list_devices",
        "-list_options",
        "urllib",
        "requests",
        "__import__",
    ):
        assert forbidden not in source
    assert "self._probe()" in source
    assert "stderr=subprocess.DEVNULL" in source
    assert "_bounded_readinto" in source


@pytest.mark.parametrize(
    ("filename", "size", "digest"),
    (
        (
            "pose_landmarker_lite.task",
            5_777_746,
            "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
        ),
        (
            "blaze_face_short_range.tflite",
            229_746,
            "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f",
        ),
    ),
)
def test_packaged_assets_match_the_repository_provenance(
    filename: str, size: int, digest: str
) -> None:
    root = Path(__file__).parents[2]
    asset = root / "src" / "pdu_exam_observer" / "assets" / "models" / filename
    assert asset.stat().st_size == size
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == digest
    provenance = (root / "docs" / "source" / "M2_D1_NATIVE_ASSET_PROVENANCE.md").read_text(
        encoding="utf-8"
    )
    assert filename in provenance and digest.upper() in provenance


def test_preflight_reresolves_current_authority_and_consumes_it_once() -> None:
    platform = FakePlatform()
    store = FakeStore(_prepared(platform))
    service = NativePreflightService(platform=platform, media=FakeMedia(), store=store)
    first = service.preflight()
    second = service.preflight()
    assert first.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    assert second.failure_code is NativeFailure.REAUTHORIZATION_REQUIRED
    assert platform.started == 1
    changed = FakePlatform(cameras=(CameraCandidate("camera-2", True, True),))
    mutated = NativePreflightService(
        platform=changed, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert mutated.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    assert changed.started == 1


def test_authorization_lifetime_cannot_be_reset_or_launch_twice() -> None:
    platform = FakePlatform()
    store = FakeStore()
    service = NativePreflightService(platform=platform, media=FakeMedia(), store=store)
    assert service.prepare().outcome is NativeOutcome.PREPARED
    assert service.preflight().outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    assert service.prepare().failure_code is NativeFailure.REAUTHORIZATION_REQUIRED
    assert service.preflight().failure_code is NativeFailure.REAUTHORIZATION_REQUIRED
    assert platform.started == 1


def test_stored_authority_has_no_directshow_or_executable_launch_surface() -> None:
    assert "directshow_friendly_name" not in PreparedAuthority.__dataclass_fields__
    assert "ffmpeg_executable" not in PreparedAuthority.__dataclass_fields__
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    assert platform.argv is not None
    assert "audio=" not in platform.argv[platform.argv.index("-i") + 1]


def test_runtime_prerequisite_failure_stops_before_fake_process_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native, "_runtime_prerequisites", lambda: None)
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.failure_code is NativeFailure.POSE_ENGINE_UNAVAILABLE
    assert platform.started == 0


@pytest.mark.parametrize("fault", ("pose_byte", "face_byte", "wrong_size", "missing"))
def test_packaged_model_faults_fail_before_media_or_process(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    package = native.resources.files("pdu_exam_observer")

    class Asset:
        def __init__(self, name: str) -> None:
            self.name = name

        def read_bytes(self) -> bytes:
            if fault == "missing":
                raise FileNotFoundError(self.name)
            value = package.joinpath(self.name).read_bytes()
            if fault == "pose_byte" and "pose_landmarker_lite" in self.name:
                return value[:-1] + bytes((value[-1] ^ 1,))
            if fault == "face_byte" and "blaze_face_short_range" in self.name:
                return value[:-1] + bytes((value[-1] ^ 1,))
            if fault == "wrong_size" and "pose_landmarker_lite" in self.name:
                return value[:-1]
            return value

    class Package:
        def joinpath(self, name: str) -> Asset:
            return Asset(name)

    monkeypatch.setattr(native.resources, "files", lambda _name: Package())
    platform = FakePlatform()
    media = FakeMedia()
    receipt = NativePreflightService(
        platform=platform, media=media, store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.failure_code is NativeFailure.POSE_ENGINE_UNAVAILABLE
    assert media.live == 0 and platform.started == 0


@pytest.mark.parametrize("fault", ("version", "audio", "network", "attempt"))
def test_dependency_and_seal_faults_fail_before_media_or_process(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    if fault == "version":
        monkeypatch.setattr(native.metadata, "version", lambda _name: "0.0.0")
    elif fault == "audio":
        monkeypatch.setattr(native, "_install_audio_import_seal", lambda: False)
    elif fault == "network":
        monkeypatch.setattr(native, "_install_network_guard", lambda: False)
    else:
        monkeypatch.setattr(native, "_OUTBOUND_NETWORK_ATTEMPTS", 1)
    platform = FakePlatform()
    media = FakeMedia()
    receipt = NativePreflightService(
        platform=platform, media=media, store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.failure_code is NativeFailure.POSE_ENGINE_UNAVAILABLE
    assert media.live == 0 and platform.started == 0


def test_prepare_close_exception_is_typed_no_go() -> None:
    class CloseFails(FakeMedia):
        def close(self) -> None:
            raise RuntimeError("close")

    platform = FakePlatform()
    store = FakeStore()
    receipt = NativePreflightService(platform=platform, media=CloseFails(), store=store).prepare()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.failure_code is NativeFailure.CLEANUP_INCOMPLETE
    assert store.prepared is not None and store.prepared.state is AuthorizationState.PENDING


def test_prepare_mutex_release_failure_leaves_pending_nonlaunchable_state() -> None:
    platform = FakePlatform()

    def broken_release() -> None:
        raise RuntimeError("release")

    platform.mutex.release = broken_release  # type: ignore[method-assign]
    store = FakeStore()
    receipt = NativePreflightService(platform=platform, media=FakeMedia(), store=store).prepare()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert store.prepared is not None and store.prepared.state is AuthorizationState.PENDING
    retry = NativePreflightService(
        platform=FakePlatform(), media=FakeMedia(), store=store
    ).prepare()
    assert retry.failure_code is NativeFailure.REAUTHORIZATION_REQUIRED


def test_late_reader_write_is_joined_then_wiped_before_raw_retention_claim() -> None:
    released = threading.Event()

    class LatePipe(FakePipe):
        def __init__(self) -> None:
            super().__init__(0)
            self.written_buffer: bytearray | None = None
            self.calls = 0

        def readinto(self, buffer: bytearray) -> int:
            self.calls += 1
            if self.calls == 1:
                self.written_buffer = buffer
                assert released.wait(timeout=1.0)
                buffer[-1] = 82
                return len(buffer)
            return 0

    class LateChild(FakeChild):
        def __init__(self) -> None:
            self.stdout = LatePipe()
            self.terminated = 0

        def terminate(self) -> None:
            self.terminated += 1
            released.set()

    class LatePlatform(FakePlatform):
        def launch_video_only(self, argv: tuple[str, ...]) -> LateChild:
            self.argv = argv
            self.started += 1
            self.child = LateChild()
            return self.child

    platform = LatePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.reader_stopped and receipt.raw_retained is False
    assert isinstance(platform.child, LateChild)
    assert platform.child.stdout.written_buffer is not None
    assert not any(platform.child.stdout.written_buffer)


def test_permanently_blocked_reader_never_closes_pipe_or_claims_raw_cleanup() -> None:
    blocked = threading.Event()

    class BlockedPipe(FakePipe):
        def __init__(self) -> None:
            super().__init__(0)

        def readinto(self, buffer: bytearray) -> int:
            del buffer
            blocked.wait()
            return 0

    class BlockedChild(FakeChild):
        def __init__(self) -> None:
            self.stdout = BlockedPipe()
            self.terminated = 0

        def terminate(self) -> None:
            self.terminated += 1
            raise RuntimeError("terminate")

        def kill(self) -> None:
            raise RuntimeError("kill")

    class BlockedPlatform(FakePlatform):
        def launch_video_only(self, argv: tuple[str, ...]) -> BlockedChild:
            self.argv = argv
            self.started += 1
            self.child = BlockedChild()
            return self.child

    platform = BlockedPlatform()
    started = native.time.perf_counter()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert native.time.perf_counter() - started < 3.0
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.child_terminated is False and receipt.reader_stopped is False
    assert receipt.pipe_closed is False and receipt.raw_retained is True
    assert isinstance(platform.child, BlockedChild) and platform.child.stdout.closed is False


def test_backlog_threshold_is_exact_and_cannot_promote_a_pass() -> None:
    state = _RunState(processed_frames=743, post_warmup_processed_frames=743)
    state.max_backlog_ns = 2_000_000_000
    assert _threshold_failure(state, 60.0, 55.0, (100.0,), (100.0,)) is None
    state.max_backlog_ns = 2_000_000_001
    assert (
        _threshold_failure(state, 60.0, 55.0, (100.0,), (100.0,))
        is NativeFailure.QUALITY_INSUFFICIENT
    )


def test_outbound_python_network_guard_denies_without_native_connection() -> None:
    native._OUTBOUND_NETWORK_ATTEMPTS = 0
    assert native._install_network_guard()
    with pytest.raises(OSError, match="denies outbound"):
        socket.socket().connect(("198.51.100.1", 443))
    assert native._OUTBOUND_NETWORK_ATTEMPTS == 1
    native._OUTBOUND_NETWORK_ATTEMPTS = 0


def test_timeout_cleanup_is_fail_closed_and_releases_the_mutex() -> None:
    class TimeoutChild(FakeChild):
        def wait(self, timeout: float) -> None:
            del timeout
            raise TimeoutError("wait")

        def kill(self) -> None:
            return None

    class TimeoutPlatform(FakePlatform):
        def launch_video_only(self, argv: tuple[str, ...]) -> TimeoutChild:
            self.argv = argv
            self.started += 1
            self.child = TimeoutChild(0)
            return self.child

    platform = TimeoutPlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.failure_code is NativeFailure.CLEANUP_INCOMPLETE
    assert platform.mutex.released == 1
    assert receipt.media_closed is True and receipt.child_terminated is False


def test_semantic_rehash_and_post_warmup_fps_mutants_fail_closed() -> None:
    receipt = NativePreflightService(
        platform=FakePlatform(), media=FakeMedia(), store=FakeStore(_prepared(FakePlatform()))
    ).preflight()
    forged = replace(receipt, opaque_device_token="1" * 64)
    assert not verify_receipt_semantics(replace(forged, result_digest=forged.recompute_digest()))
    for forged in (
        replace(receipt, source_sha256="0" * 64),
        replace(receipt, lock_sha256="0" * 64),
        replace(receipt, pose_model_sha256="0" * 64),
        replace(receipt, prepared_config_digest=None),
        replace(receipt, fixed_argv_digest=None),
        replace(receipt, ffmpeg_sha256="0" * 64),
        replace(receipt, ffmpeg_version="forged"),
        replace(receipt, prepared_ffmpeg_sha256="0" * 64),
        replace(receipt, measured_total_seconds=float("nan")),
        replace(receipt, delivered_frames=-1),
        replace(receipt, authority_consumed=False),
    ):
        rehashed = replace(forged, result_digest=forged.recompute_digest())
        assert not verify_receipt_semantics(rehashed)

    class SlowPlatform(FakePlatform):
        def __init__(self) -> None:
            super().__init__()
            self.clock = 1_000_000_000

        def monotonic_ns(self) -> int:
            result = self.clock
            self.clock += 25_000_000
            return result

    slow = SlowPlatform()
    low_fps = NativePreflightService(
        platform=slow, media=FakeMedia(), store=FakeStore(_prepared(slow))
    ).preflight()
    assert low_fps.failure_code is NativeFailure.QUALITY_INSUFFICIENT


def test_fresh_vision_import_seal_denies_audio_and_keeps_in_memory_liveness() -> None:
    script = """
import importlib
import socket
import sys
import pdu_exam_observer.m2_d1_native as native
from pdu_exam_observer.m2_d1_native import MediaPipeTasksRuntime

runtime = MediaPipeTasksRuntime()
assert runtime.liveness()
try:
    socket.socket().connect(('198.51.100.1', 443))
except OSError:
    pass
else:
    raise AssertionError('outbound network was not denied')
assert native._OUTBOUND_NETWORK_ATTEMPTS == 1
for root in ('sounddevice', '_sounddevice', 'pyaudio', 'soundcard', 'portaudio'):
    assert not any(name == root or name.startswith(root + '.') for name in sys.modules)
    try:
        importlib.import_module(root)
    except ImportError:
        pass
    else:
        raise AssertionError(root + ' was importable')
print('VISION_AUDIO_SEAL=PASS', flush=True)
try:
    runtime.close()
except TimeoutError:
    print('VISION_CLOSE_TIMEOUT=OBSERVED', flush=True)
else:
    print('VISION_CLOSE=PASS', flush=True)
"""
    try:
        completed = subprocess.run(
            (sys.executable, "-c", script),
            capture_output=True,
            text=True,
            check=False,
            timeout=(
                native.WORKER_AUTHORIZATION_TIMEOUT_SECONDS
                + native.WORKER_PRIVACY_READY_TIMEOUT_SECONDS
            ),
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr or ""
        assert "VISION_AUDIO_SEAL=PASS" in stdout, stdout + stderr
    else:
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "VISION_AUDIO_SEAL=PASS" in completed.stdout


@pytest.mark.parametrize("failure", ("read", "face", "pose", "close", "terminate", "release"))
def test_lifecycle_failures_never_escape_or_promote_to_pass(failure: str) -> None:
    class BrokenPipe(FakePipe):
        def readinto(self, buffer: bytearray) -> int:
            if failure == "read":
                raise RuntimeError("read")
            return super().readinto(buffer)

        def close(self) -> None:
            if failure == "close":
                raise RuntimeError("close")
            super().close()

    class BrokenChild(FakeChild):
        def __init__(self) -> None:
            self.stdout = BrokenPipe(1)
            self.terminated = 0

        def terminate(self) -> None:
            self.terminated += 1
            if failure == "terminate":
                raise RuntimeError("terminate")

    class BrokenPlatform(FakePlatform):
        def launch_video_only(self, argv: tuple[str, ...]) -> BrokenChild:
            self.argv = argv
            self.started += 1
            self.child = BrokenChild()
            return self.child

    class BrokenMedia(FakeMedia):
        def inspect_face(self, frame: memoryview, timestamp_ms: int) -> bool:
            if failure == "face":
                raise RuntimeError("face")
            return super().inspect_face(frame, timestamp_ms)

        def inspect_pose(self, frame: memoryview, timestamp_ms: int) -> bool:
            if failure == "pose":
                raise RuntimeError("pose")
            return super().inspect_pose(frame, timestamp_ms)

    platform = BrokenPlatform()
    if failure == "release":
        original = platform.mutex.release

        def broken_release() -> None:
            original()
            raise RuntimeError("release")

        platform.mutex.release = broken_release  # type: ignore[method-assign]
    receipt = NativePreflightService(
        platform=platform, media=BrokenMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.failure_code is not None
    assert receipt.outcome is not NativeOutcome.D1_N1_PREFLIGHT_PASS


@pytest.mark.parametrize(
    ("fault", "consumed", "started", "cleanup_complete"),
    (
        ("acquire_false", True, 0, False),
        ("acquire_raise", True, 0, False),
        ("authority_hash_raise", True, 0, False),
        ("consume_false", False, 0, False),
        ("start_raise", True, 1, False),
        ("pipe_close_raise", True, 1, False),
        ("terminate_raise", True, 1, True),
        ("first_wait_raise", True, 1, True),
        ("first_wait_timeout", True, 1, True),
        ("kill_raise", True, 1, False),
        ("final_wait_raise", True, 1, False),
        ("final_wait_timeout", True, 1, False),
        ("reader_alive", True, 1, False),
        ("media_close_raise", True, 1, False),
        ("mutex_release_raise", True, 1, False),
    ),
)
def test_lifecycle_cleanup_matrix_is_typed_and_truthful(
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    consumed: bool,
    started: int,
    cleanup_complete: bool,
) -> None:
    trace: list[str] = []

    class MatrixMutex(FakeMutex):
        def acquire(self) -> bool:
            trace.append("mutex.acquire")
            if fault == "acquire_raise":
                raise RuntimeError("acquire")
            return fault != "acquire_false"

        def release(self) -> None:
            trace.append("mutex.release")
            self.released += 1
            if fault == "mutex_release_raise":
                raise RuntimeError("release")

    class MatrixPipe(FakePipe):
        def close(self) -> None:
            trace.append("pipe.close")
            if fault == "pipe_close_raise":
                raise RuntimeError("pipe close")
            super().close()

    class MatrixChild(FakeChild):
        def __init__(self) -> None:
            self.stdout = MatrixPipe(0)
            self.terminated = 0
            self.wait_calls = 0

        def terminate(self) -> None:
            trace.append("child.terminate")
            self.terminated += 1
            if fault in {"terminate_raise", "kill_raise"}:
                raise RuntimeError("terminate")

        def wait(self, timeout: float) -> None:
            del timeout
            self.wait_calls += 1
            trace.append(f"child.wait.{self.wait_calls}")
            if fault == "first_wait_raise" and self.wait_calls == 1:
                raise RuntimeError("first wait")
            if fault == "first_wait_timeout" and self.wait_calls == 1:
                raise subprocess.TimeoutExpired("ffmpeg", 2.0)
            if fault == "final_wait_raise":
                if self.wait_calls == 1:
                    raise subprocess.TimeoutExpired("ffmpeg", 2.0)
                raise RuntimeError("final wait")
            if fault == "final_wait_timeout":
                raise subprocess.TimeoutExpired("ffmpeg", 2.0)

        def kill(self) -> None:
            trace.append("child.kill")
            if fault == "kill_raise":
                raise RuntimeError("kill")

    class MatrixPlatform(FakePlatform):
        def __init__(self) -> None:
            super().__init__(frames=0)
            self.mutex = MatrixMutex()

        def launch_video_only(self, argv: tuple[str, ...]) -> MatrixChild:
            self.argv = argv
            self.started += 1
            trace.append("child.start")
            if fault == "start_raise":
                raise RuntimeError("start")
            self.child = MatrixChild()
            return self.child

        def sha256_of_executable(self, executable: str) -> str:
            if fault == "authority_hash_raise":
                raise RuntimeError("hash")
            return super().sha256_of_executable(executable)

    class MatrixStore(FakeStore):
        def consume(self, value: PreparedAuthority) -> bool:
            trace.append("store.consume")
            if fault == "consume_false":
                return False
            return super().consume(value)

    class MatrixMedia(FakeMedia):
        def close(self) -> None:
            trace.append("media.close")
            self.closed += 1
            if fault == "media_close_raise":
                raise RuntimeError("media close")

    if fault == "reader_alive":
        monkeypatch.setattr(native._FrameReader, "stop", lambda self: False)
    platform = MatrixPlatform()
    store = MatrixStore(_prepared(platform))
    receipt = NativePreflightService(
        platform=platform, media=MatrixMedia(), store=store
    ).preflight()

    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.failure_code is not None
    assert store.consumed is consumed
    assert platform.started == started
    if platform.child is not None and fault != "reader_alive":
        assert trace.index("child.terminate") < trace.index("pipe.close")
        assert trace.index("pipe.close") < trace.index("media.close")
        assert trace.index("media.close") < trace.index("mutex.release")
    if cleanup_complete:
        assert receipt.pipe_closed and receipt.child_terminated and receipt.reader_stopped
        assert receipt.media_closed and receipt.mutex_released
    else:
        assert not all(
            (
                receipt.pipe_closed,
                receipt.child_terminated,
                receipt.reader_stopped,
                receipt.media_closed,
                receipt.mutex_released,
            )
        )
    if fault == "reader_alive":
        assert receipt.raw_retained is True


def test_positive_cleanup_trace_is_ordered_and_complete() -> None:
    trace: list[str] = []

    class TracePipe(FakePipe):
        def close(self) -> None:
            trace.append("pipe.close")
            super().close()

    class TraceChild(FakeChild):
        def __init__(self) -> None:
            self.stdout = TracePipe(0)
            self.terminated = 0

        def terminate(self) -> None:
            trace.append("child.terminate")
            super().terminate()

        def wait(self, timeout: float) -> None:
            del timeout
            trace.append("child.wait.1")

    class TracePlatform(FakePlatform):
        def launch_video_only(self, argv: tuple[str, ...]) -> TraceChild:
            self.argv = argv
            self.started += 1
            self.child = TraceChild()
            return self.child

    class TraceMedia(FakeMedia):
        def close(self) -> None:
            trace.append("media.close")
            super().close()

    platform = TracePlatform(frames=0)
    original_release = platform.mutex.release

    def release() -> None:
        trace.append("mutex.release")
        original_release()

    platform.mutex.release = release  # type: ignore[method-assign]
    receipt = NativePreflightService(
        platform=platform, media=TraceMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.pipe_closed and receipt.child_terminated and receipt.reader_stopped
    assert receipt.media_closed and receipt.mutex_released
    assert trace == [
        "child.terminate",
        "child.wait.1",
        "pipe.close",
        "media.close",
        "mutex.release",
    ]


@pytest.mark.parametrize("failing_task", ("face", "pose"))
def test_mediapipe_task_close_attempts_both_tasks_after_either_failure(failing_task: str) -> None:
    trace: list[str] = []

    class Task:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            trace.append(self.name)
            if self.name == failing_task:
                raise RuntimeError(self.name)

    runtime = MediaPipeTasksRuntime()
    runtime._face = Task("face")
    runtime._pose = Task("pose")
    with pytest.raises(RuntimeError, match=failing_task):
        runtime.close()
    assert sorted(trace) == ["face", "pose"]
    assert runtime._face is None and runtime._pose is None


@pytest.mark.parametrize("name", ("audio=camera", "camera|audio", "camera:input", "camera;cmd"))
def test_unsafe_current_friendly_name_fails_before_process_start(name: str) -> None:
    platform = FakePlatform(cameras=(CameraCandidate(name, True, True),))
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.failure_code is NativeFailure.SCHEMA_INCOMPATIBLE
    assert platform.started == 0


@pytest.mark.parametrize(
    ("post_processed", "gaps", "latencies", "expected"),
    (
        (743, (200.0,), (200.0,) * 100, None),
        (742, (200.0,), (200.0,) * 100, NativeFailure.QUALITY_INSUFFICIENT),
        (743, (200.1,), (200.0,) * 100, NativeFailure.QUALITY_INSUFFICIENT),
        (743, (999.9,), (200.0,) * 100, NativeFailure.QUALITY_INSUFFICIENT),
        (743, (200.0,), (200.1,) * 100, NativeFailure.QUALITY_INSUFFICIENT),
        (743, (200.0,), (200.0,) * 98 + (500.1,) * 2, NativeFailure.QUALITY_INSUFFICIENT),
    ),
)
def test_post_warmup_numeric_threshold_neighbors(
    post_processed: int,
    gaps: tuple[float, ...],
    latencies: tuple[float, ...],
    expected: NativeFailure | None,
) -> None:
    state = _RunState(processed_frames=post_processed, post_warmup_processed_frames=post_processed)
    assert _threshold_failure(state, 60.0, 55.0, gaps, latencies) is expected


def test_semantic_rehash_rejects_all_receipt_field_families() -> None:
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    mutations = (
        {"outcome": NativeOutcome.NO_GO},
        {"device_gate_decision": "FORGED"},
        {"d1_go": True},
        {"offline": False},
        {"video_only": False},
        {"audio_seal_active": False},
        {"mutex_released": False},
        {"child_terminated": False},
        {"pipe_closed": False},
        {"media_closed": False},
        {"capture_worker_supervised": False},
        {"capture_deadline_enforced": False},
        {"capture_job_drained": False},
        {"capture_worker_executable_sha256": "0" * 64},
        {"capture_worker_identity_digest": "0" * 64},
        {"capture_worker_lease_closed": False},
        {"requested_duration_seconds": 61},
        {"warmup_seconds": 4},
        {"frame_bytes": 1},
        {"delivered_frames": True},
        {"processed_frames": -1},
        {"backlog_ms": float("inf")},
    )
    for values in mutations:
        forged = replace(receipt, **values)
        rehashed = replace(forged, result_digest=forged.recompute_digest())
        assert not verify_receipt_semantics(rehashed)


def _seal_for_semantic_test(receipt: object) -> object:
    forged = replace(  # type: ignore[arg-type]
        receipt,
        terminal_receipt_digest=None,
        result_digest="",
    )
    forged = replace(forged, terminal_receipt_digest=forged.recompute_core_digest())
    return replace(forged, result_digest=forged.recompute_digest())


def test_issued_pass_receipt_with_privacy_evidence_cannot_be_rehashed_into_validity() -> None:
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    forged = replace(receipt, privacy_stop_count=1)
    assert not verify_receipt_semantics(_seal_for_semantic_test(forged))  # type: ignore[arg-type]


def test_aggregate_basis_exact_boundaries_and_reconciliation() -> None:
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    basis = replace(
        receipt,
        received_frames=800,
        delivered_frames=800,
        processed_frames=792,
        dropped_explicit_frames=8,
        failed_frames=0,
        privacy_checked_frames=792,
        warmup_frames=0,
        post_attempted_frames=800,
        post_successful_frames=792,
        dropped_short_frames=8,
        inference_failure_frames=0,
        privacy_terminal_frames=0,
        delivery_failure_frames=0,
        post_elapsed_ns=55_000_000_000,
        max_stall_gap_ns=999_999_999,
        backlog_ns=2_000_000_000,
        measured_post_warmup_seconds=55.0,
        delivered_frames_per_second=792 / 55,
        backlog_ms=2_000.0,
    )
    assert verify_receipt_semantics(_seal_for_semantic_test(basis))  # type: ignore[arg-type]
    for changes in (
        {"max_stall_gap_ns": 1_000_000_000},
        {"backlog_ns": 2_000_000_001},
        {"post_successful_frames": 791, "dropped_short_frames": 9},
        {"delivery_failure_frames": 1, "post_successful_frames": 791},
        {"privacy_terminal_frames": 1, "post_successful_frames": 791},
        {"received_frames": 801},
    ):
        assert not verify_receipt_semantics(_seal_for_semantic_test(replace(basis, **changes)))  # type: ignore[arg-type]


def test_terminal_receipt_is_authoritative_after_store_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    platform = FakePlatform()
    store = FixedLocalAuthorityStore(tmp_path)
    service = NativePreflightService(platform=platform, media=FakeMedia(), store=store)
    assert service.prepare().outcome is NativeOutcome.PREPARED
    receipt = service.preflight()
    assert receipt.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    assert service.verify_terminal_receipt(receipt)
    restarted = NativePreflightService(
        platform=FakePlatform(), media=FakeMedia(), store=FixedLocalAuthorityStore(tmp_path)
    )
    assert restarted.verify_terminal_receipt(receipt)
    forged = replace(receipt, post_successful_frames=receipt.post_successful_frames - 1)
    forged = replace(forged, result_digest=forged.recompute_digest())
    assert not restarted.verify_terminal_receipt(forged)
    assert not hasattr(native, "_ISSUED_RECEIPT_DIGESTS")


def test_restored_prepared_bytes_cannot_replay_after_terminal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    platform = FakePlatform()
    store = FixedLocalAuthorityStore(tmp_path)
    service = NativePreflightService(platform=platform, media=FakeMedia(), store=store)
    assert service.prepare().outcome is NativeOutcome.PREPARED
    prepared_bytes = store._prepared_path.read_bytes()  # type: ignore[attr-defined]
    assert service.preflight().outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    terminal_bytes = store._terminal_path.read_bytes()  # type: ignore[attr-defined]
    store._prepared_path.write_bytes(prepared_bytes)  # type: ignore[attr-defined]
    replay_platform = FakePlatform()
    replay = NativePreflightService(
        platform=replay_platform,
        media=FakeMedia(),
        store=FixedLocalAuthorityStore(tmp_path),
    ).preflight()
    assert replay.failure_code is NativeFailure.REAUTHORIZATION_REQUIRED
    assert replay_platform.started == 0
    assert store._terminal_path.read_bytes() == terminal_bytes  # type: ignore[attr-defined]


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 ABI contract")
def test_win32_api_signatures_keep_pointer_width_without_native_launch() -> None:
    high_handle = 0x1_0000_0040
    assert ctypes.c_void_p(high_handle).value == high_handle
    mutex = WindowsNamedMutex("Local\\PDUExamObserver.D1N1.AbiTest")
    assert mutex.acquire()
    assert mutex._kernel32.CloseHandle.argtypes == [ctypes.c_void_p]  # type: ignore[union-attr]
    mutex.release()
    lease = object.__new__(WindowsExecutableLease)
    lease._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    lease._configure_api()
    assert lease._kernel32.ResumeThread.argtypes == [ctypes.c_void_p]
    assert lease._kernel32.Thread32First.argtypes[0] is ctypes.c_void_p
    with pytest.raises(TypeError):
        WindowsExecutableLease("C:\\alternate.exe")  # type: ignore[call-arg]


def test_nonregular_terminal_presence_blocks_before_native_work(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    platform = FakePlatform()
    store = FixedLocalAuthorityStore(tmp_path)
    store.save(_prepared(platform))
    store._terminal_path.mkdir()  # type: ignore[attr-defined]
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=store
    ).preflight()
    assert receipt.failure_code is NativeFailure.SCHEMA_INCOMPATIBLE
    assert platform.started == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 Job Object contract")
@pytest.mark.parametrize("blocked_call", ("inspect_face", "inspect_pose"))
def test_capture_job_watchdog_kills_blocked_inference_tree_and_terminalizes(
    blocked_call: str,
) -> None:
    challenge = "e" * 64
    challenge_digest = native._digest(["d1-n1-worker-challenge-v1", challenge])
    grant_id = "1" * 64
    script = f"""
import json
import subprocess
import os
import sys
import time

sys.path.insert(0, {str(native.WORKER_SOURCE_ROOT)!r})
import pdu_exam_observer.m2_d1_native as worker_native
assert worker_native._current_process_in_expected_worker_job(
    os.environ[worker_native.WORKER_CHALLENGE_ENV]
)
print(json.dumps(
    {{
        "event": "AUTHORIZED",
        "challenge_digest": {challenge_digest!r},
        "payload": {{"grant_id": {grant_id!r}}},
    }},
    sort_keys=True,
    separators=(",", ":"),
), flush=True)

for phase in ("PRIVACY_READY", "CAPTURE_STARTING"):
    payload = (
        {{"payload": {{"worker_monotonic_ns": time.monotonic_ns()}}}}
        if phase == "CAPTURE_STARTING"
        else {{}}
    )
    print(json.dumps(
        {{"event": phase, "challenge_digest": {challenge_digest!r}, **payload}},
        sort_keys=True,
        separators=(",", ":"),
    ), flush=True)

subprocess.Popen(
    (
        os.path.join(os.environ["SystemRoot"], "System32", "ping.exe"),
        "-n",
        "60",
        "127.0.0.1",
    ),
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
print(json.dumps(
    {{
        "event": "FIRST_FRAME",
        "challenge_digest": {challenge_digest!r},
        "payload": {{"worker_monotonic_ns": time.monotonic_ns()}},
    }},
    sort_keys=True,
    separators=(",", ":"),
), flush=True)

def inspect_face():
    time.sleep(60)

def inspect_pose():
    time.sleep(60)

{blocked_call}()
"""
    lease = native._WindowsWorkerExecutableLease()
    binding = lease.binding
    job = native._WindowsCaptureJob(native._worker_job_name(challenge))
    child = lease._launch_suspended(
        (lease.executable, "-I", "-u", "-c", script),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        before_resume=job.assign,
        env=native._worker_environment(challenge),
        cwd=native.POWERSHELL_WORKING_DIRECTORY,
    )
    started = time.perf_counter()
    monitor = native._monitor_capture_worker(
        child,
        job,
        challenge_digest,
        grant_id,
        startup_timeout=5.0,
        capture_timeout=0.1,
        report_timeout=0.1,
    )
    elapsed = time.perf_counter() - started
    worker_lease_closed = lease.close()
    job_closed = job.close()

    assert elapsed < 6.0
    assert monitor.first_frame and monitor.timed_out
    assert monitor.job_drained and monitor.pipe_closed and monitor.reader_stopped
    assert monitor.forced_termination and monitor.exit_code != 0
    assert not native._monitor_allows_candidate(monitor)
    assert worker_lease_closed and job_closed

    platform = FakePlatform()
    prepared = _prepared(platform)
    store = FakeStore(prepared)
    assert store.consume(prepared)
    candidate = native._supervisor_failure_receipt(
        prepared,
        NativeFailure.PRIVACY_GUARD_TIMEOUT,
        binding,
        worker_supervised=True,
        deadline_enforced=True,
        job_drained=monitor.job_drained,
        pipe_closed=monitor.pipe_closed,
        reader_stopped=monitor.reader_stopped,
        worker_lease_closed=worker_lease_closed,
    )
    service = NativePreflightService(platform=platform, media=FakeMedia(), store=store)
    receipt = service._terminalize(prepared, candidate)
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.failure_code is NativeFailure.PRIVACY_GUARD_TIMEOUT
    assert receipt.raw_retained is False
    assert receipt.capture_job_drained and receipt.capture_worker_lease_closed
    assert store.terminal is not None
    assert service.preflight().failure_code is NativeFailure.REAUTHORIZATION_REQUIRED
    assert platform.started == 0


def test_worker_environment_contains_no_real_authority_and_builds_surrogate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    platform = FakePlatform()
    prepared = replace(_prepared(platform), state=AuthorizationState.CONSUMED)
    challenge = "a" * 64
    monkeypatch.setenv("SystemRoot", "C:\\caller-controlled-shadow")
    environment = native._worker_environment(challenge, prepared)

    assert "LOCALAPPDATA" not in environment
    assert ".venv" not in environment["PATH"].lower()
    assert environment["SystemRoot"] == str(
        Path(native.WINDOWS_SYSTEM_DIRECTORY).parent
    )
    assert prepared.opaque_device_token not in environment.values()
    assert prepared.authorization_nonce not in environment.values()
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    surrogate = native._worker_prepared_from_environment(challenge)
    assert surrogate.state is AuthorizationState.PREPARED
    assert surrogate.ffmpeg_sha256 == prepared.ffmpeg_sha256
    assert surrogate.ffmpeg_identity_digest == prepared.ffmpeg_identity_digest
    assert surrogate.opaque_device_token != prepared.opaque_device_token
    assert surrogate.authorization_nonce != prepared.authorization_nonce


def test_worker_main_rejects_missing_capability_before_device_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    platform = FakePlatform()
    prepared = replace(_prepared(platform), state=AuthorizationState.CONSUMED)
    challenge = "9" * 64
    for name, value in native._worker_environment(challenge, prepared).items():
        monkeypatch.setenv(name, value)

    class EmptyInput:
        buffer: EmptyInput

        def __init__(self) -> None:
            self.buffer = self

        def readline(self, size: int) -> bytes:
            del size
            return b""

    def forbidden_device(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("device dependency was constructed before authorization")

    monkeypatch.setattr(native, "_current_process_in_expected_worker_job", lambda _: True)
    monkeypatch.setattr(native.sys, "stdin", EmptyInput())
    monkeypatch.setattr(native, "WindowsNativePlatform", forbidden_device)
    monkeypatch.setattr(native, "MediaPipeTasksRuntime", forbidden_device)
    assert native._capture_worker_main() == 4


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 executable lease contract")
def test_inherited_capability_channel_authenticates_exact_worker_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = replace(_prepared(FakePlatform()), state=AuthorizationState.CONSUMED)
    challenge = "8" * 64
    capability = bytes(range(native.WORKER_CAPABILITY_BYTES))
    lease = native._WindowsWorkerExecutableLease()
    binding = lease.binding
    assert lease.close()
    grant = native._new_worker_grant(prepared, challenge, capability, binding)

    class Channel:
        def __init__(self) -> None:
            self.data = bytearray()
            self.closed = False

        def write(self, value: bytes) -> int:
            self.data.extend(value)
            return len(value)

        def flush(self) -> None:
            return None

        def close(self) -> None:
            self.closed = True

        def readline(self, size: int) -> bytes:
            value = bytes(self.data[:size])
            del self.data[:size]
            return value

    channel = Channel()
    child = type("Child", (), {"stdin": channel})()
    native._send_worker_proceed(  # type: ignore[arg-type]
        child, grant.challenge_digest, grant, capability
    )
    fake_stdin = type("Input", (), {"buffer": channel})()
    monkeypatch.setattr(native.sys, "stdin", fake_stdin)
    monkeypatch.setattr(
        native,
        "FixedWorkerGrantReader",
        lambda: type("Reader", (), {"load": lambda self: grant})(),
    )
    assert native._receive_worker_launch_grant(challenge, prepared) == grant
    assert channel.closed


def test_self_minted_capability_without_durable_issuance_stops_before_worker_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = replace(_prepared(FakePlatform()), state=AuthorizationState.CONSUMED)
    challenge = "0" * 64
    capability = b"z" * native.WORKER_CAPABILITY_BYTES
    grant = native._new_worker_grant(
        prepared,
        challenge,
        capability,
        native.FfmpegBinding("a" * 64, 1, "b" * 64, ""),
    )
    message = json.dumps(
        {
            "event": "PROCEED",
            "challenge_digest": grant.challenge_digest,
            "payload": {
                "grant": native.asdict(grant),
                "capability": capability.hex(),
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii") + b"\n"

    class Input:
        buffer: Input

        def __init__(self) -> None:
            self.buffer = self

        def readline(self, size: int) -> bytes:
            return message[:size]

    class NoGrantReader:
        def load(self) -> None:
            return None

    def forbidden_lease() -> object:
        raise AssertionError("worker image lease opened without durable issuance")

    monkeypatch.setattr(native.sys, "stdin", Input())
    monkeypatch.setattr(native, "FixedWorkerGrantReader", NoGrantReader)
    monkeypatch.setattr(native, "_WindowsWorkerExecutableLease", forbidden_lease)
    with pytest.raises(ValueError, match="durable consumed issuance"):
        native._receive_worker_launch_grant(challenge, prepared)


def test_worker_grant_is_persisted_once_and_terminally_revoked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    prepared = _prepared(FakePlatform())
    store = FixedLocalAuthorityStore(tmp_path)
    store.save(prepared)
    assert store.consume(prepared)
    capability = b"g" * native.WORKER_CAPABILITY_BYTES
    grant = native._new_worker_grant(
        prepared,
        "7" * 64,
        capability,
        native.FfmpegBinding("a" * 64, 1, "b" * 64, ""),
    )
    assert store.issue_worker_grant(prepared, grant)
    assert not store.issue_worker_grant(prepared, grant)
    assert store.load_worker_grant() == grant
    assert native.FixedWorkerGrantReader(tmp_path).load() == grant
    assert store.revoke_worker_grant(grant)
    revoked = store.load_worker_grant()
    assert revoked is not None and revoked.state == "REVOKED"
    assert not native._worker_grant_is_valid(revoked, allow_revoked=False)
    with pytest.raises(ValueError, match="not launchable"):
        native.FixedWorkerGrantReader(tmp_path).load()


def test_supervisor_orders_consumption_grant_revocation_before_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace: list[str] = []
    platform = FakePlatform()
    prepared = _prepared(platform)
    binding = native.FfmpegBinding("6" * 64, 1, "5" * 64, "")

    class OrderedStore(FakeStore):
        def consume(self, value: PreparedAuthority) -> bool:
            trace.append("consume")
            return super().consume(value)

        def issue_worker_grant(
            self, value: PreparedAuthority, grant: native.WorkerGrant
        ) -> bool:
            trace.append("issue")
            return super().issue_worker_grant(value, grant)

        def revoke_worker_grant(self, grant: native.WorkerGrant) -> bool:
            trace.append("revoke")
            return super().revoke_worker_grant(grant)

        def finalize_terminal(self, *args: object, **kwargs: object) -> TerminalAuthority | None:
            trace.append("terminal")
            return super().finalize_terminal(*args, **kwargs)  # type: ignore[arg-type]

    class ProbeLease:
        def __init__(self) -> None:
            self.binding = binding

        def close(self) -> bool:
            return True

    store = OrderedStore(prepared)

    def no_device_runner(
        worker_prepared: PreparedAuthority,
        challenge: str,
        grant: native.WorkerGrant,
        capability: bytes,
    ) -> object:
        trace.append("runner")
        assert worker_prepared == prepared
        assert grant.state == "ISSUED" and store.load_worker_grant() == grant
        assert len(capability) == native.WORKER_CAPABILITY_BYTES
        assert prepared.authorization_nonce.encode() not in capability
        assert native._is_nonce(challenge)
        return native._supervisor_failure_receipt(
            prepared,
            NativeFailure.INPUT_UNAVAILABLE,
            binding,
            worker_supervised=True,
            deadline_enforced=True,
            job_drained=True,
            pipe_closed=True,
            reader_stopped=True,
            worker_lease_closed=True,
        )

    monkeypatch.setattr(native, "_WindowsWorkerExecutableLease", ProbeLease)
    monkeypatch.setattr(native, "_run_windows_capture_worker", no_device_runner)
    service = NativePreflightService(
        platform=platform, media=FakeMedia(), store=store
    )
    receipt = service._supervised_preflight()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert trace == ["consume", "issue", "runner", "revoke", "terminal"]
    assert store.worker_grant is not None and store.worker_grant.state == "REVOKED"
    assert store.terminal is not None


def test_worker_main_never_constructs_or_reads_fixed_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    platform = FakePlatform()
    prepared = replace(_prepared(platform), state=AuthorizationState.CONSUMED)
    candidate = NativePreflightService(
        platform=FakePlatform(),
        media=FakeMedia(),
        store=FakeStore(_prepared(FakePlatform())),
    ).preflight()
    challenge = "b" * 64
    for name, value in native._worker_environment(challenge, prepared).items():
        monkeypatch.setenv(name, value)

    class ForbiddenFixedStore:
        def __init__(self) -> None:
            raise AssertionError("real authority store was constructed")

    observed: dict[str, object] = {}

    class WorkerService:
        def __init__(self, **kwargs: object) -> None:
            observed.update(kwargs)

        def _run_consumed(self, worker_prepared: PreparedAuthority) -> object:
            observed["prepared"] = worker_prepared
            return candidate

    monkeypatch.setattr(native, "FixedLocalAuthorityStore", ForbiddenFixedStore)
    monkeypatch.setattr(native, "_current_process_in_expected_worker_job", lambda _: True)
    monkeypatch.setattr(
        native,
        "_receive_worker_launch_grant",
        lambda *_: type("Grant", (), {"grant_id": "4" * 64})(),
    )
    monkeypatch.setattr(native, "WindowsNativePlatform", lambda store: ("platform", store))
    monkeypatch.setattr(native, "MediaPipeTasksRuntime", lambda: object())
    monkeypatch.setattr(native, "NativePreflightService", WorkerService)
    monkeypatch.setattr(native, "_emit_worker_message", lambda *args: None)

    assert native._capture_worker_main() == 0
    worker_prepared = observed["prepared"]
    assert isinstance(worker_prepared, PreparedAuthority)
    assert worker_prepared.opaque_device_token != prepared.opaque_device_token
    assert isinstance(observed["store"], native._UnavailableWorkerAuthority)


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 Job Object contract")
@pytest.mark.parametrize(
    ("suffix", "forced", "exit_code"),
    (("time.sleep(60)", True, None), ("raise SystemExit(7)", False, 7)),
)
def test_monitor_rejects_pass_payload_before_clean_zero_exit(
    suffix: str, forced: bool, exit_code: int | None
) -> None:
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    challenge = ("c" if forced else "d") * 64
    challenge_digest = native._digest(["d1-n1-worker-challenge-v1", challenge])
    grant_id = "2" * 64
    receipt_message = json.dumps(
        {
            "event": "RECEIPT",
            "challenge_digest": challenge_digest,
            "payload": native._serialize_worker_receipt(receipt),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    script = f"""
import json
import time

def emit(event):
    print(json.dumps(
        {{
            "event": event,
            "challenge_digest": {challenge_digest!r},
            "payload": {{"worker_monotonic_ns": time.monotonic_ns()}},
        }},
        sort_keys=True,
        separators=(",", ":"),
    ), flush=True)

def emit_phase(event):
    payload = (
        {{"payload": {{"worker_monotonic_ns": time.monotonic_ns()}}}}
        if event == "CAPTURE_STARTING"
        else {{}}
    )
    print(json.dumps(
        {{"event": event, "challenge_digest": {challenge_digest!r}, **payload}},
        sort_keys=True,
        separators=(",", ":"),
    ), flush=True)

print(json.dumps(
    {{
        "event": "AUTHORIZED",
        "challenge_digest": {challenge_digest!r},
        "payload": {{"grant_id": {grant_id!r}}},
    }},
    sort_keys=True,
    separators=(",", ":"),
), flush=True)
emit_phase("PRIVACY_READY")
emit_phase("CAPTURE_STARTING")
emit("FIRST_FRAME")
emit("CAPTURE_CLOSED")
print({receipt_message!r}, flush=True)
{suffix}
"""
    lease = native._WindowsWorkerExecutableLease()
    job = native._WindowsCaptureJob(native._worker_job_name(challenge))
    child = lease._launch_suspended(
        (lease.executable, "-I", "-u", "-c", script),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        before_resume=job.assign,
        env=native._worker_environment(challenge),
        cwd=native.POWERSHELL_WORKING_DIRECTORY,
    )
    monitor = native._monitor_capture_worker(
        child,
        job,
        challenge_digest,
        grant_id,
        startup_timeout=2.0,
        capture_timeout=0.2,
        report_timeout=0.1,
    )
    assert lease.close()
    assert job.close()

    assert monitor.payload is not None and monitor.job_drained
    assert monitor.forced_termination is forced
    if exit_code is None:
        assert monitor.exit_code != 0
    else:
        assert monitor.exit_code == exit_code
    assert not native._monitor_allows_candidate(monitor)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("d1_go", True),
        ("raw_retained", True),
        ("audio_requested", True),
        ("outbound_network_attempts", 1),
        ("network_guard_active", False),
        ("privacy_stop_count", 1),
        ("source_sha256", "0" * 64),
        ("pose_model_sha256", "0" * 64),
    ),
)
def test_worker_cannot_supply_parent_owned_no_go_invariants(
    field: str, value: object
) -> None:
    platform = FakePlatform(frames=0)
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    assert receipt.outcome is NativeOutcome.NO_GO
    payload = native._serialize_worker_receipt(receipt)
    if field in native._WORKER_PRIVATE_RECEIPT_FIELDS:
        assert field not in payload
        payload[field] = value
        with pytest.raises(ValueError, match="fields are malformed"):
            native._deserialize_worker_receipt(
                payload,
                _prepared(FakePlatform()),
                worker_binding=object(),  # type: ignore[arg-type]
                worker_supervised=True,
                deadline_enforced=True,
                job_drained=True,
                pipe_closed=True,
                reader_stopped=True,
                worker_lease_closed=True,
            )
    else:
        forged = replace(receipt, **{field: value})
        assert not native._candidate_semantics_are_valid(forged)


def test_camera_enumeration_ignores_shadow_path_and_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "shadow-ran.txt"
    shadow = tmp_path / "powershell.exe"
    shadow.write_text(f"shadow > {marker}\n", encoding="ascii")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    observed: dict[str, object] = {}

    class PowerShellChild:
        returncode = 0

        def communicate(self, timeout: float) -> tuple[bytes, None]:
            observed["timeout"] = timeout
            return b"[]", None

        def poll(self) -> int:
            return 0

    class PowerShellLease:
        executable = native.POWERSHELL_CANONICAL_PATH
        image_verified = True

        def _launch_suspended(
            self, command: tuple[str, ...], **kwargs: object
        ) -> PowerShellChild:
            observed["command"] = command
            observed.update(kwargs)
            return PowerShellChild()

        def close(self) -> bool:
            observed["lease_closed"] = True
            return True

    monkeypatch.setattr(native, "_WindowsPowerShellExecutableLease", PowerShellLease)
    cameras = native.WindowsNativePlatform(FakeStore()).camera_class_devices()  # type: ignore[arg-type]
    assert cameras == ()
    command = observed["command"]
    assert isinstance(command, tuple) and command[0] == native.POWERSHELL_CANONICAL_PATH
    assert observed["cwd"] == native.POWERSHELL_WORKING_DIRECTORY
    environment = observed["env"]
    assert isinstance(environment, dict) and str(tmp_path) not in environment["PATH"]
    assert observed["lease_closed"] is True
    assert not marker.exists()


def test_capture_watchdog_has_no_post_sixty_second_margin() -> None:
    assert native.WORKER_CAPTURE_TIMEOUT_SECONDS == native.PREFLIGHT_SECONDS == 60


def test_first_frame_event_uses_frame_reader_ingress_timestamp() -> None:
    main_thread = threading.current_thread()
    reads: list[tuple[bool, int]] = []
    events: list[tuple[str, int]] = []

    class TimestampPlatform(FakePlatform):
        def monotonic_ns(self) -> int:
            value = super().monotonic_ns()
            reads.append((threading.current_thread() is main_thread, value))
            return value

    platform = TimestampPlatform()
    receipt = NativePreflightService(
        platform=platform,
        media=FakeMedia(),
        store=FakeStore(_prepared(platform)),
        event_sink=lambda event, timestamp: events.append((event, timestamp)),
    ).preflight()
    assert receipt.outcome is NativeOutcome.D1_N1_PREFLIGHT_PASS
    first_event = next(item for item in events if item[0] == "FIRST_FRAME")
    close_event = next(item for item in events if item[0] == "CAPTURE_CLOSED")
    assert any(not on_main and value == first_event[1] for on_main, value in reads)
    assert any(on_main and value == close_event[1] for on_main, value in reads)
    assert close_event[1] > first_event[1]


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 Job Object contract")
def test_capture_deadline_is_anchored_to_worker_first_frame_timestamp() -> None:
    challenge = "f" * 64
    challenge_digest = native._digest(["d1-n1-worker-challenge-v1", challenge])
    grant_id = "3" * 64
    script = f"""
import json
import time
print(json.dumps(
    {{
        "event": "AUTHORIZED",
        "challenge_digest": {challenge_digest!r},
        "payload": {{"grant_id": {grant_id!r}}},
    }},
    sort_keys=True,
    separators=(",", ":"),
), flush=True)
capture_start_ns = time.monotonic_ns() - 2_000_000_000
for phase in ("PRIVACY_READY", "CAPTURE_STARTING"):
    payload = (
        {{"payload": {{"worker_monotonic_ns": capture_start_ns}}}}
        if phase == "CAPTURE_STARTING"
        else {{}}
    )
    print(json.dumps(
        {{"event": phase, "challenge_digest": {challenge_digest!r}, **payload}},
        sort_keys=True,
        separators=(",", ":"),
    ), flush=True)
print(json.dumps(
    {{
        "event": "FIRST_FRAME",
        "challenge_digest": {challenge_digest!r},
        "payload": {{"worker_monotonic_ns": time.monotonic_ns() - 1_000_000_000}},
    }},
    sort_keys=True,
    separators=(",", ":"),
), flush=True)
time.sleep(60)
"""
    lease = native._WindowsWorkerExecutableLease()
    job = native._WindowsCaptureJob(native._worker_job_name(challenge))
    child = lease._launch_suspended(
        (lease.executable, "-I", "-u", "-c", script),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        before_resume=job.assign,
        env=native._worker_environment(challenge),
        cwd=native.POWERSHELL_WORKING_DIRECTORY,
    )
    started = time.perf_counter()
    monitor = native._monitor_capture_worker(
        child,
        job,
        challenge_digest,
        grant_id,
        startup_timeout=2.0,
        capture_timeout=0.1,
        report_timeout=0.1,
    )
    elapsed = time.perf_counter() - started
    assert lease.close()
    assert job.close()

    assert elapsed < 1.0
    assert monitor.first_frame and monitor.timed_out
    assert monitor.forced_termination and monitor.job_drained
    assert not native._monitor_allows_candidate(monitor)


def test_no_go_worker_measurements_are_reconstructed_to_minimal_evidence() -> None:
    platform = FakePlatform(frames=0)
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    payload = native._serialize_worker_receipt(receipt)
    payload.update(
        {
            "delivered_frames": 999,
            "processed_frames": 998,
            "privacy_stop_count": 7,
            "backlog_ms": float("inf"),
        }
    )
    candidate = native._deserialize_worker_receipt(
        payload,
        _prepared(FakePlatform()),
        worker_binding=native.FfmpegBinding("a" * 64, 1, "b" * 64, ""),
        worker_supervised=True,
        deadline_enforced=True,
        job_drained=True,
        pipe_closed=True,
        reader_stopped=True,
        worker_lease_closed=True,
    )
    assert candidate.outcome is NativeOutcome.NO_GO
    assert candidate.failure_code is NativeFailure.INPUT_UNAVAILABLE
    assert candidate.delivered_frames == candidate.processed_frames == 0
    assert candidate.privacy_stop_count == 0 and candidate.backlog_ms is None
    assert native._candidate_semantics_are_valid(candidate)


def test_consumed_terminal_prepared_outcome_is_semantically_impossible() -> None:
    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    forged = replace(
        receipt,
        outcome=NativeOutcome.PREPARED,
        failure_code=None,
        terminal_receipt_digest=None,
        result_digest="",
    )
    forged = replace(forged, terminal_receipt_digest=forged.recompute_core_digest())
    forged = replace(forged, result_digest=forged.recompute_digest())
    assert not verify_receipt_semantics(forged)


def test_terminal_finalization_failure_suppresses_a_technical_pass() -> None:
    class TerminalFails(FakeStore):
        def finalize_terminal(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            return None

    platform = FakePlatform()
    store = TerminalFails(_prepared(platform))
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=store
    ).preflight()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.failure_code is NativeFailure.AUTHORITY_FINALIZATION_FAILED
    assert not receipt.result_digest == ""
    assert not NativePreflightService(
        platform=platform, media=FakeMedia(), store=store
    ).verify_terminal_receipt(receipt)


@pytest.mark.parametrize(
    "code",
    (
        "FRAME_READER_EXCEPTION",
        "CAPTURE_RUNTIME_EXCEPTION",
        "CLEANUP_INCOMPLETE",
        "WORKER_PROTOCOL_FAILURE",
    ),
)
def test_n2_failure_codes_are_explicit_no_go_only(code: str) -> None:
    failure = NativeFailure(code)
    receipt = native._receipt(NativeOutcome.NO_GO, failure)
    assert receipt.failure_code is failure
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.d1_go is False


def test_n2_readinto_and_ingress_clock_faults_are_frame_reader_failures() -> None:
    class FailingPipe(FakePipe):
        def readinto(self, buffer: bytearray) -> int:
            del buffer
            raise RuntimeError("surrogate read failure")

    class ReadPlatform(FakePlatform):
        def launch_video_only(self, argv: tuple[str, ...]) -> FakeChild:
            child = super().launch_video_only(argv)
            child.stdout = FailingPipe(0)
            return child

    class ClockPlatform(FakePlatform):
        def monotonic_ns(self) -> int:
            raise RuntimeError("surrogate ingress clock failure")

    for platform in (ReadPlatform(), ClockPlatform()):
        receipt = NativePreflightService(
            platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
        ).preflight()
        assert receipt.outcome is NativeOutcome.NO_GO
        assert receipt.failure_code is NativeFailure.FRAME_READER_EXCEPTION
        assert receipt.raw_retained is False


def test_n2_uncategorized_capture_exception_and_cleanup_failure_are_distinct() -> None:
    platform = FakePlatform()
    runtime = NativePreflightService(
        platform=platform,
        media=FakeMedia(),
        store=FakeStore(_prepared(platform)),
        event_sink=lambda _event, _timestamp: (_ for _ in ()).throw(
            RuntimeError("surrogate event failure")
        ),
    ).preflight()
    assert runtime.failure_code is NativeFailure.CAPTURE_RUNTIME_EXCEPTION

    class CloseFails(FakeMedia):
        def close(self) -> None:
            raise RuntimeError("surrogate cleanup failure")

    cleanup = NativePreflightService(
        platform=FakePlatform(), media=CloseFails(), store=FakeStore(_prepared(FakePlatform()))
    ).preflight()
    assert cleanup.failure_code is NativeFailure.CLEANUP_INCOMPLETE


def test_n2_worker_cannot_supply_parent_protocol_failure() -> None:
    platform = FakePlatform(frames=0)
    receipt = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    payload = native._serialize_worker_receipt(receipt)
    payload["failure_code"] = "WORKER_PROTOCOL_FAILURE"
    with pytest.raises(ValueError, match="protocol"):
        native._deserialize_worker_receipt(
            payload,
            _prepared(FakePlatform()),
            worker_binding=native.FfmpegBinding("a" * 64, 1, "b" * 64, ""),
            worker_supervised=True,
            deadline_enforced=True,
            job_drained=True,
            pipe_closed=True,
            reader_stopped=True,
            worker_lease_closed=True,
        )


def test_n2_privacy_stop_keeps_precedence_over_cleanup_failure() -> None:
    class CloseFails(FakeMedia):
        def close(self) -> None:
            raise RuntimeError("surrogate cleanup failure")

    platform = FakePlatform()
    receipt = NativePreflightService(
        platform=platform,
        media=CloseFails(face_at=1),
        store=FakeStore(_prepared(platform)),
    ).preflight()
    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.failure_code is NativeFailure.PRIVACY_STOP
    assert receipt.raw_retained is False
    assert receipt.media_closed is False
    assert verify_receipt_semantics(receipt)


@pytest.mark.parametrize(
    "changes",
    (
        {"malformed": True},
        {"payload": None},
        {"authorized": False},
        {"exit_code": 4},
        {"exit_code": 7},
        {"forced_termination": True},
        {"pipe_closed": False},
        {"reader_stopped": False},
    ),
)
def test_n2_non_timeout_worker_lifecycle_rejections_are_protocol_failures(
    changes: dict[str, object],
) -> None:
    raw: dict[str, object] = {
        "payload": {"receipt": "bounded"},
        "authorized": True,
        "first_frame": True,
        "capture_closed": True,
        "timed_out": False,
        "malformed": False,
        "job_drained": True,
        "pipe_closed": True,
        "reader_stopped": True,
        "forced_termination": False,
        "exit_code": 0,
    }
    raw.update(changes)
    monitor = native._WorkerMonitorResult(**raw)  # type: ignore[arg-type]
    assert not native._monitor_allows_candidate(monitor)
    assert (
        native._monitor_failure_code(
            monitor, worker_lease_closed=True, job_closed=True
        )
        is NativeFailure.WORKER_PROTOCOL_FAILURE
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({"timed_out": True, "forced_termination": True}, NativeFailure.PRIVACY_GUARD_TIMEOUT),
        ({"job_drained": False}, NativeFailure.CLEANUP_INCOMPLETE),
    ),
)
def test_n2_worker_monitor_timeout_and_drain_take_precedence(
    changes: dict[str, object], expected: NativeFailure
) -> None:
    raw: dict[str, object] = {
        "payload": None,
        "authorized": True,
        "first_frame": True,
        "capture_closed": False,
        "timed_out": False,
        "malformed": False,
        "job_drained": True,
        "pipe_closed": True,
        "reader_stopped": True,
        "forced_termination": False,
        "exit_code": 0,
    }
    raw.update(changes)
    monitor = native._WorkerMonitorResult(**raw)  # type: ignore[arg-type]
    assert (
        native._monitor_failure_code(
            monitor, worker_lease_closed=True, job_closed=True
        )
        is expected
    )


@pytest.mark.parametrize(
    "failure",
    (
        NativeFailure.FRAME_READER_EXCEPTION,
        NativeFailure.CAPTURE_RUNTIME_EXCEPTION,
        NativeFailure.CLEANUP_INCOMPLETE,
        NativeFailure.WORKER_PROTOCOL_FAILURE,
    ),
)
def test_n2_new_failures_are_semantic_no_go_and_cannot_promote(
    failure: NativeFailure,
) -> None:
    platform = FakePlatform(frames=0)
    original = NativePreflightService(
        platform=platform, media=FakeMedia(), store=FakeStore(_prepared(platform))
    ).preflight()
    no_go = replace(original, failure_code=failure, result_digest="")
    no_go = replace(
        no_go,
        terminal_receipt_digest=no_go.recompute_core_digest(),
        result_digest="",
    )
    no_go = replace(no_go, result_digest=no_go.recompute_digest())
    assert verify_receipt_semantics(no_go)
    promoted = replace(
        no_go,
        outcome=NativeOutcome.D1_N1_PREFLIGHT_PASS,
        failure_code=None,
        result_digest="",
    )
    promoted = replace(
        promoted,
        terminal_receipt_digest=promoted.recompute_core_digest(),
        result_digest="",
    )
    promoted = replace(promoted, result_digest=promoted.recompute_digest())
    assert not verify_receipt_semantics(promoted)


def test_n2_fresh_vision_liveness_reports_its_initialization_stage() -> None:
    script = """
import pdu_exam_observer.m2_d1_native as native
print('N2_IMPORT=PASS', flush=True)
runtime = native.MediaPipeTasksRuntime()
print('N2_RUNTIME=PASS', flush=True)
assert runtime.liveness()
print('N2_LIVENESS=PASS', flush=True)
"""
    try:
        completed = subprocess.run(
            (sys.executable, "-c", script),
            capture_output=True,
            text=True,
            check=False,
            timeout=(
                native.WORKER_AUTHORIZATION_TIMEOUT_SECONDS
                + native.WORKER_PRIVACY_READY_TIMEOUT_SECONDS
            ),
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or ""
        pytest.fail(f"fresh vision liveness timed out after markers: {stdout!r}")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "N2_LIVENESS=PASS" in completed.stdout


def test_n2_worker_phase_timeouts_are_exact() -> None:
    assert native.WORKER_AUTHORIZATION_TIMEOUT_SECONDS == 10.0
    assert native.WORKER_PRIVACY_READY_TIMEOUT_SECONDS == 30.0
    assert native.WORKER_DEVICE_SETUP_TIMEOUT_SECONDS == 25.0
    assert native.WORKER_FIRST_FRAME_TIMEOUT_SECONDS == 10.0
    assert native.WORKER_CAPTURE_TIMEOUT_SECONDS == 60.0
    assert native.WORKER_REPORT_TIMEOUT_SECONDS == 5.0
    assert NativeFailure.CAPTURE_STARTUP_TIMEOUT.value == "CAPTURE_STARTUP_TIMEOUT"


def test_n2_phase_events_bracket_no_device_capture_setup() -> None:
    events: list[str] = []

    class OrderedPlatform(FakePlatform):
        def camera_class_devices(self) -> tuple[CameraCandidate, ...]:
            assert events == ["PRIVACY_READY"]
            return super().camera_class_devices()

        def launch_video_only(self, argv: tuple[str, ...]) -> FakeChild:
            assert events == ["PRIVACY_READY", "CAPTURE_STARTING"]
            return super().launch_video_only(argv)

    platform = OrderedPlatform(frames=0)
    receipt = NativePreflightService(
        platform=platform,
        media=FakeMedia(),
        store=FakeStore(_prepared(platform)),
        event_sink=lambda event, _timestamp: events.append(event),
    ).preflight()
    assert receipt.failure_code is NativeFailure.INPUT_UNAVAILABLE
    assert events[:2] == ["PRIVACY_READY", "CAPTURE_STARTING"]


@pytest.mark.parametrize(
    "mutant",
    (
        "duplicate_privacy_ready",
        "missing_privacy_ready",
        "reordered_capture_starting",
        "payload_bearing_privacy_ready",
        "wrong_challenge_capture_starting",
        "privacy_ready_after_first_frame",
        "first_frame_without_capture_starting",
    ),
)
def test_n2_phase_protocol_mutants_are_parent_protocol_failures(mutant: str) -> None:
    challenge = "a" * 64
    digest = native._digest(["d1-n1-worker-challenge-v1", challenge])

    def message(event: str, payload: dict[str, object] | None = None) -> bytes:
        raw: dict[str, object] = {"event": event, "challenge_digest": digest}
        if payload is not None:
            raw["payload"] = payload
        return (json.dumps(raw) + "\n").encode()

    authorized = message("AUTHORIZED", {"grant_id": "b" * 64})
    privacy = message("PRIVACY_READY")
    starting = message("CAPTURE_STARTING")
    first = message("FIRST_FRAME", {"worker_monotonic_ns": time.monotonic_ns()})
    closed = message("CAPTURE_CLOSED", {"worker_monotonic_ns": time.monotonic_ns()})
    lines = [authorized, privacy, starting, first, closed]
    if mutant == "duplicate_privacy_ready":
        lines.insert(2, privacy)
    elif mutant == "missing_privacy_ready":
        lines.remove(privacy)
    elif mutant == "reordered_capture_starting":
        lines = [authorized, starting, privacy, first, closed]
    elif mutant == "payload_bearing_privacy_ready":
        lines[1] = message("PRIVACY_READY", {})
    elif mutant == "wrong_challenge_capture_starting":
        lines[2] = (
            json.dumps(
                {"event": "CAPTURE_STARTING", "challenge_digest": "0" * 64}
            )
            + "\n"
        ).encode()
    elif mutant == "privacy_ready_after_first_frame":
        lines = [authorized, privacy, starting, first, privacy, closed]
    elif mutant == "first_frame_without_capture_starting":
        lines = [authorized, privacy, first, closed]

    class Pipe:
        def readline(self) -> bytes:
            return lines.pop(0) if lines else b""

        def close(self) -> None:
            return None

    class Child:
        stdout = Pipe()
        returncode = 0

    class Job:
        def wait_drained(self, child: object, timeout: float) -> bool:
            del child, timeout
            return True

        def terminate_and_drain(self, child: object) -> bool:
            del child
            return True

    monitor = native._monitor_capture_worker(
        Child(),  # type: ignore[arg-type]
        Job(),  # type: ignore[arg-type]
        digest,
        "b" * 64,
        startup_timeout=0.1,
        capture_timeout=0.1,
        report_timeout=0.1,
    )
    assert monitor.malformed
    assert (
        native._monitor_failure_code(
            monitor, worker_lease_closed=True, job_closed=True
        )
        is NativeFailure.WORKER_PROTOCOL_FAILURE
    )


@pytest.mark.parametrize("mode", ("false", "raise"))
def test_n2_liveness_failure_emits_no_privacy_ready_or_capture_start(mode: str) -> None:
    events: list[str] = []

    class NoCameraPlatform(FakePlatform):
        def camera_class_devices(self) -> tuple[CameraCandidate, ...]:
            raise AssertionError("camera must not be reached")

    class LivenessFails(FakeMedia):
        def liveness(self) -> bool:
            if mode == "raise":
                raise RuntimeError("surrogate")
            return False

    platform = NoCameraPlatform()
    receipt = NativePreflightService(
        platform=platform,
        media=LivenessFails(),
        store=FakeStore(_prepared(platform)),
        event_sink=lambda event, _timestamp: events.append(event),
    ).preflight()
    assert receipt.failure_code is NativeFailure.POSE_ENGINE_UNAVAILABLE
    assert events == []


@pytest.mark.parametrize(
    ("changes", "expected"),
    (
        ({"job_drained": False}, NativeFailure.CLEANUP_INCOMPLETE),
        (
            {"timed_out": True, "privacy_ready": True, "capture_starting": True},
            NativeFailure.CAPTURE_STARTUP_TIMEOUT,
        ),
        (
            {
                "timed_out": True,
                "privacy_ready": True,
                "capture_starting": True,
                "first_frame": True,
            },
            NativeFailure.PRIVACY_GUARD_TIMEOUT,
        ),
    ),
)
def test_n2_phase_timeout_and_cleanup_precedence(
    changes: dict[str, object], expected: NativeFailure
) -> None:
    monitor = native._WorkerMonitorResult(
        payload=None,
        authorized=True,
        first_frame=False,
        capture_closed=False,
        timed_out=False,
        malformed=False,
        job_drained=True,
        pipe_closed=True,
        reader_stopped=True,
        forced_termination=False,
        exit_code=0,
        privacy_ready=False,
        capture_starting=False,
        timeout_failure=None,
    )
    monitor = replace(monitor, **changes)
    assert (
        native._monitor_failure_code(
            monitor, worker_lease_closed=True, job_closed=True
        )
        is expected
    )


def test_n2_production_phase_serializer_has_exact_privacy_and_capture_wire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[tuple[str, str, dict[str, object] | None]] = []
    monkeypatch.setattr(
        native,
        "_emit_worker_message",
        lambda event, digest, payload=None: messages.append((event, digest, payload)),
    )
    native._emit_worker_phase("PRIVACY_READY", "a" * 64, 101)
    native._emit_worker_phase("CAPTURE_STARTING", "a" * 64, 102)
    assert messages == [
        ("PRIVACY_READY", "a" * 64, None),
        ("CAPTURE_STARTING", "a" * 64, {"worker_monotonic_ns": 102}),
    ]


def test_n2_production_phase_serializer_round_trips_through_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = "c" * 64
    digest = native._digest(["d1-n1-worker-challenge-v1", challenge])
    lines: list[bytes] = []

    def emit(event: str, observed_digest: str, payload: dict[str, object] | None = None) -> None:
        raw: dict[str, object] = {"event": event, "challenge_digest": observed_digest}
        if payload is not None:
            raw["payload"] = payload
        lines.append((json.dumps(raw) + "\n").encode())

    monkeypatch.setattr(native, "_emit_worker_message", emit)
    emit("AUTHORIZED", digest, {"grant_id": "d" * 64})
    start = time.monotonic_ns()
    native._emit_worker_phase("PRIVACY_READY", digest, start)
    native._emit_worker_phase("CAPTURE_STARTING", digest, start)
    emit("FIRST_FRAME", digest, {"worker_monotonic_ns": time.monotonic_ns()})
    emit("CAPTURE_CLOSED", digest, {"worker_monotonic_ns": time.monotonic_ns()})

    class Pipe:
        def readline(self) -> bytes:
            return lines.pop(0) if lines else b""

        def close(self) -> None:
            return None

    class Child:
        stdout = Pipe()
        returncode = 0

    class Job:
        def wait_drained(self, child: object, timeout: float) -> bool:
            del child, timeout
            return True

        def terminate_and_drain(self, child: object) -> bool:
            del child
            return True

    monitor = native._monitor_capture_worker(
        Child(),  # type: ignore[arg-type]
        Job(),  # type: ignore[arg-type]
        digest,
        "d" * 64,
        startup_timeout=0.1,
        capture_timeout=0.1,
        report_timeout=0.1,
    )
    assert monitor.privacy_ready and monitor.capture_starting
    assert monitor.capture_starting_monotonic_ns == start
    assert monitor.first_frame and monitor.capture_closed


@pytest.mark.parametrize(
    "failure",
    (
        NativeFailure.WORKER_PROTOCOL_FAILURE,
        NativeFailure.CAPTURE_STARTUP_TIMEOUT,
        NativeFailure.PRIVACY_GUARD_TIMEOUT,
        NativeFailure.AUTHORITY_FINALIZATION_FAILED,
    ),
)
def test_n2_parent_only_worker_failures_are_rejected(failure: NativeFailure) -> None:
    assert not native._worker_failure_phases_valid(
        failure,
        privacy_ready=True,
        capture_starting=True,
        first_frame=True,
        capture_closed=True,
    )


def test_n2_zero_frame_eof_service_phase_wire_round_trips_as_input_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, int]] = []
    platform = FakePlatform(frames=0)
    receipt = NativePreflightService(
        platform=platform,
        media=FakeMedia(),
        store=FakeStore(_prepared(platform)),
        event_sink=lambda event, timestamp: events.append((event, timestamp)),
    ).preflight()
    assert receipt.failure_code is NativeFailure.INPUT_UNAVAILABLE

    challenge = "e" * 64
    digest = native._digest(["d1-n1-worker-challenge-v1", challenge])
    lines: list[bytes] = []

    def emit(event: str, observed_digest: str, payload: dict[str, object] | None = None) -> None:
        raw: dict[str, object] = {"event": event, "challenge_digest": observed_digest}
        if payload is not None:
            raw["payload"] = payload
        lines.append((json.dumps(raw) + "\n").encode())

    monkeypatch.setattr(native, "_emit_worker_message", emit)
    emit("AUTHORIZED", digest, {"grant_id": "f" * 64})
    wire_start_ns = time.monotonic_ns() - 1_000_000
    for event, timestamp in events:
        if event in {"PRIVACY_READY", "CAPTURE_STARTING"}:
            native._emit_worker_phase(
                event,
                digest,
                wire_start_ns if event == "CAPTURE_STARTING" else timestamp,
            )
        elif event == "CAPTURE_CLOSED":
            emit(event, digest, {"worker_monotonic_ns": wire_start_ns + 1})
    emit("RECEIPT", digest, native._serialize_worker_receipt(receipt))

    class Pipe:
        def readline(self) -> bytes:
            return lines.pop(0) if lines else b""

        def close(self) -> None:
            return None

    class Child:
        stdout = Pipe()
        returncode = 0

    class Job:
        def wait_drained(self, child: object, timeout: float) -> bool:
            del child, timeout
            return True

        def terminate_and_drain(self, child: object) -> bool:
            del child
            return True

    monitor = native._monitor_capture_worker(
        Child(),  # type: ignore[arg-type]
        Job(),  # type: ignore[arg-type]
        digest,
        "f" * 64,
        startup_timeout=0.1,
        capture_timeout=0.1,
        report_timeout=0.1,
    )
    assert not monitor.malformed
    assert monitor.capture_starting and monitor.capture_closed and not monitor.first_frame
    candidate = native._deserialize_worker_receipt(
        monitor.payload or {},
        _prepared(FakePlatform()),
        worker_binding=native.FfmpegBinding("a" * 64, 1, "b" * 64, ""),
        worker_supervised=True,
        deadline_enforced=True,
        job_drained=monitor.job_drained,
        pipe_closed=monitor.pipe_closed,
        reader_stopped=monitor.reader_stopped,
        worker_lease_closed=True,
        privacy_ready=monitor.privacy_ready,
        capture_starting=monitor.capture_starting,
        first_frame=monitor.first_frame,
        capture_closed=monitor.capture_closed,
        phase_checked=True,
    )
    assert candidate.failure_code is NativeFailure.INPUT_UNAVAILABLE


def test_n2_worker_unknown_failure_is_parent_only() -> None:
    assert not native._worker_failure_phases_valid(
        NativeFailure.UNKNOWN_TECHNICAL_FAILURE,
        privacy_ready=True,
        capture_starting=True,
        first_frame=True,
        capture_closed=True,
    )


def test_n2_cleanup_and_privacy_cleanup_phase_round_trips_are_truthful() -> None:
    prepared = _prepared(FakePlatform())
    binding = native.FfmpegBinding("a" * 64, 1, "b" * 64, "")

    cleanup_payload = native._serialize_worker_receipt(
        native._receipt(
            NativeOutcome.NO_GO,
            NativeFailure.CLEANUP_INCOMPLETE,
            worker_cleanup_complete=False,
        )
    )
    cleanup = native._deserialize_worker_receipt(
        cleanup_payload,
        prepared,
        worker_binding=binding,
        worker_supervised=True,
        deadline_enforced=True,
        job_drained=True,
        pipe_closed=True,
        reader_stopped=True,
        worker_lease_closed=True,
        privacy_ready=True,
        capture_starting=True,
        first_frame=False,
        capture_closed=False,
        phase_checked=True,
    )
    assert cleanup.failure_code is NativeFailure.CLEANUP_INCOMPLETE
    assert cleanup.worker_cleanup_complete is False
    assert native._candidate_semantics_are_valid(cleanup)

    privacy_payload = native._serialize_worker_receipt(
        native._receipt(
            NativeOutcome.NO_GO,
            NativeFailure.PRIVACY_STOP,
            worker_cleanup_complete=False,
        )
    )
    privacy = native._deserialize_worker_receipt(
        privacy_payload,
        prepared,
        worker_binding=binding,
        worker_supervised=True,
        deadline_enforced=True,
        job_drained=True,
        pipe_closed=True,
        reader_stopped=True,
        worker_lease_closed=True,
        privacy_ready=True,
        capture_starting=True,
        first_frame=True,
        capture_closed=False,
        phase_checked=True,
    )
    assert privacy.failure_code is NativeFailure.PRIVACY_STOP
    assert privacy.worker_cleanup_complete is False
    assert native._candidate_semantics_are_valid(privacy)

    privacy_payload["worker_cleanup_complete"] = True
    with pytest.raises(ValueError, match="phase"):
        native._deserialize_worker_receipt(
            privacy_payload,
            prepared,
            worker_binding=binding,
            worker_supervised=True,
            deadline_enforced=True,
            job_drained=True,
            pipe_closed=True,
            reader_stopped=True,
            worker_lease_closed=True,
            privacy_ready=True,
            capture_starting=True,
            first_frame=True,
            capture_closed=False,
            phase_checked=True,
        )


def test_n2_worker_cleanup_assertion_is_required_for_pass_and_bounded() -> None:
    receipt = native._receipt(
        NativeOutcome.NO_GO,
        NativeFailure.CLEANUP_INCOMPLETE,
        worker_cleanup_complete=False,
    )
    assert receipt.worker_cleanup_complete is False
    assert receipt.outcome is NativeOutcome.NO_GO


def test_n2_capture_start_source_has_no_dead_phase_blocks_and_prebuilds_argv() -> None:
    source = inspect.getsource(NativePreflightService._run_consumed)
    assert "if False" not in source
    assert source.index("argv = _fixed_argv") < source.index('"CAPTURE_STARTING"')
    assert source.index('"CAPTURE_STARTING"') < source.index("launch_video_only")


def test_n2_invalid_phase_checked_monitor_returns_typed_protocol_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The invalid-monitor branch must not forward phase fields to its receipt helper."""

    platform = FakePlatform()
    prepared = _prepared(platform)
    challenge = "a" * 64
    challenge_digest = native._digest(["d1-n1-worker-challenge-v1", challenge])
    binding = native.FfmpegBinding("b" * 64, 1, "c" * 64, "")
    grant = type(
        "Grant",
        (),
        {
            "challenge_digest": challenge_digest,
            "worker_executable_sha256": binding.sha256,
            "worker_identity_digest": binding.identity_digest,
            "grant_id": "d" * 64,
        },
    )()

    class FakeLease:
        def __init__(self) -> None:
            self.binding = binding
            self.executable = "surrogate-worker"

        def _launch_suspended(self, *args: object, **kwargs: object) -> object:
            return object()

        def close(self) -> bool:
            return True

    class FakeJob:
        assigned = True

        def __init__(self, name: str) -> None:
            del name

        def assign(self, child: object) -> None:
            del child

        def close(self) -> bool:
            return True

    monitor = type(
        "Monitor",
        (),
        {
            "authorized": True,
            "job_drained": True,
            "pipe_closed": True,
            "reader_stopped": True,
            "privacy_ready": False,
            "capture_starting": False,
            "first_frame": False,
            "capture_closed": False,
        },
    )()
    monkeypatch.setattr(
        native,
        "FixedWorkerGrantReader",
        lambda: type("GrantReader", (), {"load": lambda self: grant})(),
    )
    monkeypatch.setattr(native, "_WindowsWorkerExecutableLease", FakeLease)
    monkeypatch.setattr(native, "_WindowsCaptureJob", FakeJob)
    monkeypatch.setattr(native, "_send_worker_proceed", lambda *args: None)
    monkeypatch.setattr(native, "_monitor_capture_worker", lambda *args: monitor)
    monkeypatch.setattr(native, "_monitor_allows_candidate", lambda value: False)
    monkeypatch.setattr(
        native,
        "_monitor_failure_code",
        lambda *args, **kwargs: NativeFailure.WORKER_PROTOCOL_FAILURE,
    )

    receipt = native._run_windows_capture_worker(
        prepared,
        challenge,
        grant,  # type: ignore[arg-type]
        b"capability",
    )

    assert receipt.outcome is NativeOutcome.NO_GO
    assert receipt.failure_code is NativeFailure.WORKER_PROTOCOL_FAILURE


def test_n2_liveness_runs_once_before_privacy_ready_and_enumeration() -> None:
    events: list[str] = []

    class Platform(FakePlatform):
        def camera_class_devices(self) -> tuple[CameraCandidate, ...]:
            assert events == ["PRIVACY_READY"]
            return super().camera_class_devices()

    class Media(FakeMedia):
        def liveness(self) -> bool:
            self.live += 1
            return True

    platform = Platform(frames=0)
    media = Media()
    receipt = NativePreflightService(
        platform=platform,
        media=media,
        store=FakeStore(_prepared(platform)),
        event_sink=lambda event, _timestamp: events.append(event),
    ).preflight()
    assert receipt.failure_code is NativeFailure.INPUT_UNAVAILABLE
    assert media.live == 1
