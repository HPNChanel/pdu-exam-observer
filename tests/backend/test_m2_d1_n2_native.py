from __future__ import annotations

import builtins
import hashlib
import inspect
import json
from pathlib import Path

import pytest

import pdu_exam_observer.m2_d1_n2_native as native
from pdu_exam_observer.m2_d1_n2_canonical import (
    AUTHORITY_REVISION,
    PREPARED_TTL_NS,
    PersistenceOutcome,
    PreparedBindingAttestation,
)
from pdu_exam_observer.m2_d1_n2_evidence import (
    CAPTURE_POLICY_DIGEST,
    WATCHDOG_POLICY_DIGEST,
    RetainedLeaseCleanup,
    build_sanitized_no_go_evidence,
)
from pdu_exam_observer.m2_d1_n2_prepare import (
    CameraDeviceObservation,
    CameraEnumerationObservation,
    ExecutableObservation,
)


class _Lease:
    def __init__(self) -> None:
        self.closed = False

    def validate(self) -> bool:
        return not self.closed

    def close(self) -> bool:
        self.closed = True
        return True


def _executable(*, version: bool) -> ExecutableObservation:
    digest = "a" * 64
    return ExecutableObservation(
        canonical_path_digest=digest,
        sha256=digest,
        size_bytes=1,
        identity_digest=digest,
        version_output_digest=digest if version else None,
        lease=_Lease(),
    )


def test_windows_preparation_port_constructor_is_inert_and_has_no_stream_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pdu_exam_observer.m2_d1_native":
            raise AssertionError("legacy native module must be loaded only by an operation")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    port = native.D1N2WindowsPreparationPort()

    assert not hasattr(port, "open_stream")
    assert not hasattr(port, "capture")
    assert list(inspect.signature(native.D1N2WindowsPreparationPort).parameters) == []


def test_windows_preparation_port_delegates_only_fixed_parameterless_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    supervisor = _executable(version=False)
    ffmpeg = _executable(version=True)
    camera = CameraEnumerationObservation(
        (CameraDeviceObservation("Integrated Camera", True, True),),
        _Lease(),
    )

    monkeypatch.setattr(
        native,
        "_production_supervisor_observation",
        lambda: events.append("supervisor") or supervisor,
    )
    monkeypatch.setattr(
        native,
        "_production_camera_enumeration",
        lambda: events.append("camera") or camera,
    )
    monkeypatch.setattr(
        native,
        "_production_ffmpeg_observation",
        lambda: events.append("ffmpeg") or ffmpeg,
    )
    monkeypatch.setattr(
        native,
        "_production_dependency_observation_digest",
        lambda: events.append("dependency") or "b" * 64,
    )
    port = native.D1N2WindowsPreparationPort()

    assert port.attest_supervisor() is supervisor
    assert port.enumerate_camera_class() is camera
    assert port.attest_ffmpeg() is ffmpeg
    assert port.dependency_observation_digest() == "b" * 64
    assert events == ["supervisor", "camera", "ffmpeg", "dependency"]


def test_native_preparation_source_has_no_d1_n1_authority_or_capture_entrypoint() -> None:
    source = Path(inspect.getsourcefile(native) or "").read_text(encoding="utf-8").lower()
    assert "fixedlocalauthoritystore" not in source
    assert "d1-n1-authority" not in source
    assert "prepare_native_preflight" not in source
    assert "run_native_preflight" not in source
    assert "native.preparedauthority" not in source
    assert "native.nativepreflightservice" not in source
    assert "native.authority_revision" not in source


def test_runtime_policy_digests_match_the_closed_terminal_verifier() -> None:
    assert native._d1n2_capture_policy_digest() == CAPTURE_POLICY_DIGEST
    assert native._d1n2_watchdog_policy_digest() == WATCHDOG_POLICY_DIGEST


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            b'{"FriendlyName":"Integrated Camera","Present":true,"Status":"OK"}',
            (CameraDeviceObservation("Integrated Camera", True, True),),
        ),
        (b"[]", ()),
        (b"not-json", None),
        (b'{"FriendlyName":7,"Present":true,"Status":"OK"}', None),
    ],
)
def test_camera_enumeration_decoder_is_closed_and_sanitized(
    payload: bytes,
    expected: tuple[CameraDeviceObservation, ...] | None,
) -> None:
    assert native._decode_camera_rows(payload) == expected


class _Authority:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.consume_outcome = PersistenceOutcome.OK
        self.issue_outcome = PersistenceOutcome.OK
        self.persist_on_issue_failure = False
        self.record_present = False
        self.binding: native.WorkerGrantBindingAttestation | None = None
        self.terminal_binding: native.TerminalBindingAttestation | None = None

    def revalidate_for_run(self) -> bool:
        self.events.append("revalidate")
        return True

    def consume(self) -> PersistenceOutcome:
        self.events.append("consume")
        return self.consume_outcome

    def issue_grant(self, binding: native.WorkerGrantBindingAttestation) -> PersistenceOutcome:
        self.events.append("issue")
        assert binding.valid()
        self.binding = binding
        self.record_present = (
            self.issue_outcome is PersistenceOutcome.OK
            or self.persist_on_issue_failure
        )
        return self.issue_outcome

    def take_grant_capability(self) -> bytes | None:
        self.events.append("take")
        return b"g" * 32

    def grant_record_bytes(self) -> bytes | None:
        self.events.append("record")
        return b"grant-record" if self.record_present else None

    def authorize_grant(self, capability: bytes) -> PersistenceOutcome:
        self.events.append("authorize")
        assert capability == b"g" * 32
        return PersistenceOutcome.OK

    def revoke_grant(self) -> PersistenceOutcome:
        self.events.append("revoke")
        return PersistenceOutcome.OK

    def close_retained_for_terminal(self) -> RetainedLeaseCleanup:
        self.events.append("close_retained")
        return RetainedLeaseCleanup(True, True, True)

    def terminalize(self, binding: native.TerminalBindingAttestation) -> PersistenceOutcome:
        self.events.append("terminal")
        assert binding.valid()
        self.terminal_binding = binding
        return PersistenceOutcome.OK


class _Driver:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = 0
        self.request: native.D1N2ExecutionRequest | None = None

    def run(self, request: native.D1N2ExecutionRequest) -> native.D1N2DriverResult:
        self.events.append("driver")
        self.calls += 1
        self.request = request
        assert request.grant_capability == b"g" * 32
        assert request.duration_seconds == 60
        assert request.video_only and not request.retry
        evidence = build_sanitized_no_go_evidence(
            failure_code="QUALITY_INSUFFICIENT",
            authority_digest="a" * 64,
            grant_record_digest="a" * 64,
            challenge_digest="a" * 64,
            job_name_digest="a" * 64,
            static_bindings_digest="a" * 64,
            capture_policy_digest=CAPTURE_POLICY_DIGEST,
            watchdog_policy_digest=WATCHDOG_POLICY_DIGEST,
            runtime_digest="a" * 64,
            pose_model_sha256="a" * 64,
            face_model_sha256="a" * 64,
            retained_cleanup=RetainedLeaseCleanup(True, True, True),
        )
        assert evidence is not None
        return native.D1N2DriverResult(
            native.D1N2DriverStatus.COMPLETED,
            native_side_effect_count=1,
            receipt_digest=evidence.receipt_digest,
            worker_supervised=True,
            job_drained=True,
            worker_lease_closed=True,
            receipt_bytes=evidence.receipt_json.encode(),
            failure_ledger_bytes=evidence.failure_ledger_json.encode(),
        )


def test_execution_bridge_orders_one_attempt_and_terminalizes() -> None:
    events: list[str] = []
    authority = _Authority(events)
    driver = _Driver(events)
    bridge = native.D1N2ExecutionBridge(
        authority,
        driver,
        device_name="Integrated Camera",
        prepared_authority_digest="a" * 64,
        prepared_attestation=_prepared_attestation(),
        challenge_entropy=lambda size: events.append("challenge") or b"c" * size,
    )

    result = bridge.run()

    assert result.status is native.D1N2ExecutionStatus.TERMINAL
    assert result.native_side_effect_count == 1
    assert result.receipt_digest is not None
    assert events == [
        "revalidate",
        "consume",
        "challenge",
        "issue",
        "take",
        "record",
        "authorize",
        "driver",
        "revoke",
        "record",
        "close_retained",
        "terminal",
    ]
    assert authority.binding is not None
    challenge = (b"c" * 32).hex()
    assert authority.binding.challenge_digest == native._d1n2_challenge_digest(challenge)
    assert authority.binding.job_name_digest == native._d1n2_job_name_digest(challenge)
    assert driver.request is not None and driver.request.raw_challenge == b"c" * 32
    assert authority.terminal_binding is not None
    receipt = json.loads(authority.terminal_binding.receipt_json)
    assert receipt["challenge_digest"] == authority.binding.challenge_digest
    assert receipt["job_name_digest"] == authority.binding.job_name_digest
    assert receipt["grant_record_digest"] == hashlib.sha256(b"grant-record").hexdigest()
    assert bridge.run().status is native.D1N2ExecutionStatus.ALREADY_USED
    assert driver.calls == 1


@pytest.mark.parametrize(
    "failure",
    [
        "invalid_device",
        "invalid_digest",
        "revalidate",
        "consume",
        "issue_durability_ambiguous",
        "issue_lease_ambiguous",
        "issue_cleanup_ambiguous",
        "issue_exception_ambiguous",
        "driver_supervision",
    ],
)
def test_execution_bridge_fails_closed_without_retry(
    failure: str,
) -> None:
    events: list[str] = []
    authority = _Authority(events)
    driver = _Driver(events)
    device_name = "Integrated Camera"
    prepared_digest = "a" * 64
    if failure == "invalid_device":
        device_name = "unsafe/device"
    elif failure == "invalid_digest":
        prepared_digest = "INVALID"
    elif failure == "revalidate":
        authority.revalidate_for_run = lambda: events.append("revalidate") or False  # type: ignore[method-assign]
    elif failure == "consume":
        authority.consume_outcome = PersistenceOutcome.CAS_MISMATCH
    elif failure in {
        "issue_durability_ambiguous",
        "issue_lease_ambiguous",
        "issue_cleanup_ambiguous",
    }:
        authority.issue_outcome = {
            "issue_durability_ambiguous": PersistenceOutcome.DURABILITY_FAILED,
            "issue_lease_ambiguous": PersistenceOutcome.LEASE_DRIFT,
            "issue_cleanup_ambiguous": PersistenceOutcome.CLEANUP_FAILED,
        }[failure]
        authority.persist_on_issue_failure = True
    elif failure == "issue_exception_ambiguous":
        def fail_after_persist(
            binding: native.WorkerGrantBindingAttestation,
        ) -> PersistenceOutcome:
            events.append("issue")
            assert binding.valid()
            authority.binding = binding
            authority.record_present = True
            raise RuntimeError("simulated post-persist issue failure")

        authority.issue_grant = fail_after_persist  # type: ignore[method-assign]
    else:
        driver.run = lambda _request: native.D1N2DriverResult(  # type: ignore[method-assign]
            native.D1N2DriverStatus.COMPLETED,
            native_side_effect_count=1,
            receipt_digest="d" * 64,
            worker_supervised=False,
            job_drained=True,
            worker_lease_closed=True,
        )
    bridge = native.D1N2ExecutionBridge(
        authority,
        driver,
        device_name=device_name,
        prepared_authority_digest=prepared_digest,
        prepared_attestation=_prepared_attestation(),
    )

    result = bridge.run()

    assert result.status is native.D1N2ExecutionStatus.FAILED_NONLAUNCHABLE
    assert bridge.run().status is native.D1N2ExecutionStatus.ALREADY_USED
    assert driver.calls <= 1
    if failure in {"invalid_device", "invalid_digest", "revalidate", "consume"}:
        assert "driver" not in events
        assert events[-1:] == ["close_retained"]
        assert "record" not in events
        assert "terminal" not in events
    if failure == "driver_supervision":
        assert events[-3:] == ["revoke", "record", "close_retained"]
        assert "terminal" not in events
    if failure.startswith("issue_"):
        assert events[-4:] == ["issue", "record", "revoke", "close_retained"]
        assert "driver" not in events
        assert "terminal" not in events


def test_issue_base_exception_after_persist_revokes_and_closes_before_reraise() -> None:
    events: list[str] = []
    authority = _Authority(events)

    def interrupt_after_persist(
        binding: native.WorkerGrantBindingAttestation,
    ) -> PersistenceOutcome:
        events.append("issue")
        assert binding.valid()
        authority.binding = binding
        authority.record_present = True
        raise KeyboardInterrupt

    authority.issue_grant = interrupt_after_persist  # type: ignore[method-assign]
    bridge = native.D1N2ExecutionBridge(
        authority,
        _Driver(events),
        device_name="Integrated Camera",
        prepared_authority_digest="a" * 64,
        prepared_attestation=_prepared_attestation(),
    )

    with pytest.raises(KeyboardInterrupt):
        bridge.run()

    assert events[-4:] == ["issue", "record", "revoke", "close_retained"]
    assert "driver" not in events
    assert "terminal" not in events


def _prepared_attestation() -> PreparedBindingAttestation:
    digest = "a" * 64
    return PreparedBindingAttestation(
        AUTHORITY_REVISION,
        3,
        digest,
        digest,
        digest,
        1,
        "PRESENT_OK",
        digest,
        digest,
        digest,
        1,
        digest,
        digest,
        digest,
        1,
        digest,
        digest,
        digest,
        digest,
        1,
        digest,
        1,
        digest,
        1_000,
        1_000 + PREPARED_TTL_NS,
    )


def test_windows_capture_driver_constructor_is_inert_and_invalid_request_is_zero_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        native,
        "_load_native_primitives",
        lambda: (_ for _ in ()).throw(AssertionError("native load forbidden")),
    )
    driver = native.D1N2WindowsCaptureDriver()
    request = native.D1N2ExecutionRequest(
        b"g" * 32,
        b"invalid-grant-record",
        "Integrated Camera",
        "b" * 64,
        _prepared_attestation(),
    )

    result = driver.run(request)

    assert result.status is native.D1N2DriverStatus.FAILED
    assert result.native_side_effect_count == 0
    assert not result.worker_supervised


class _CaptureMutex:
    def __init__(self) -> None:
        self.released = False

    def acquire(self) -> bool:
        return True

    def release(self) -> bool:
        self.released = True
        return True


class _CapturePipe:
    def close(self) -> None:
        return None


class _CaptureChild:
    def __init__(self) -> None:
        self.stdout = _CapturePipe()

    def terminate(self) -> None:
        return None

    def wait(self, timeout: float) -> None:
        assert timeout == 2.0


class _CapturePlatform:
    def __init__(self, primitives: object) -> None:
        self._primitives = primitives
        self.current_ingress = 0
        self.clock_phase = 0
        self.launches = 0
        self.mutex = _CaptureMutex()
        self.lease_closed = False
        self.lease_close_calls = 0

    def camera_class_devices(self) -> tuple[object, ...]:
        candidate = self._primitives.CameraCandidate
        return (candidate("Integrated Camera", True, True),)

    def ffmpeg_authority(self) -> tuple[str, str, str]:
        return ("fixed-ffmpeg.exe", "a" * 64, "a" * 64)

    def sha256_of_executable(self, executable: str) -> str:
        assert executable == "fixed-ffmpeg.exe"
        return "a" * 64

    def ffmpeg_identity(self) -> tuple[int, str, bool]:
        return (1, "a" * 64, True)

    def ffmpeg_lease_verified(self) -> bool:
        return self.launches == 1

    def close_ffmpeg_lease(self) -> bool:
        self.lease_closed = True
        self.lease_close_calls += 1
        return True

    def named_mutex(self) -> _CaptureMutex:
        return self.mutex

    def launch_video_only(self, argv: tuple[str, ...]) -> _CaptureChild:
        assert "-an" in argv
        self.launches += 1
        return _CaptureChild()

    def monotonic_ns(self) -> int:
        self.clock_phase += 1
        return self.current_ingress + self.clock_phase * 1_000_000


class _CaptureReader:
    def __init__(
        self,
        _pipe: object,
        _buffers: tuple[bytearray, bytearray],
        _clock: object,
        platform: _CapturePlatform,
        disposition: object,
        frame_bytes: int,
    ) -> None:
        self.platform = platform
        self.disposition = disposition
        self.frame_bytes = frame_bytes
        self.frame = 0

    def start(self) -> None:
        return None

    def next(self) -> tuple[object, int, int, int]:
        ingress = self.frame * 66_666_667
        self.platform.current_ingress = ingress
        self.platform.clock_phase = 0
        self.frame += 1
        return (self.disposition, self.frame % 2, self.frame_bytes, ingress)

    def release(self, _index: int) -> None:
        return None

    def alive(self) -> bool:
        return True

    def stop(self) -> bool:
        return True


class _CaptureMedia:
    def liveness(self) -> bool:
        return True

    def inspect_face(self, _frame: memoryview, _timestamp_ms: int) -> bool:
        return False

    def inspect_pose(self, _frame: memoryview, _timestamp_ms: int) -> bool:
        return False

    def close(self) -> None:
        return None


def test_d1n2_capture_core_passes_only_bounded_video_receipt_without_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pdu_exam_observer.m2_d1_n2_entrypoint import (
        verify_d1_n2_receipt_semantics,
    )

    primitives = native._load_native_primitives()
    platform = _CapturePlatform(primitives)
    reader_disposition = primitives._ReaderDisposition.FRAME
    monkeypatch.setattr(primitives, "_runtime_prerequisites", lambda: (b"p", b"f"))
    monkeypatch.setattr(
        primitives,
        "_FrameReader",
        lambda pipe, buffers, clock: _CaptureReader(
            pipe,
            buffers,
            clock,
            platform,
            reader_disposition,
            primitives.FRAME_BYTES,
        ),
    )
    phases: list[str] = []

    payload = native._run_d1n2_capture(
        primitives,
        platform,  # type: ignore[arg-type]
        _CaptureMedia(),
        _prepared_attestation(),
        lambda phase, _value: phases.append(phase),
    )

    receipt = payload["receipt"]
    assert isinstance(receipt, dict)
    assert receipt["outcome"] == "D1_N2_PREFLIGHT_PASS"
    assert receipt["failure_code"] is None
    assert receipt["video_only"] is True
    assert receipt["audio_requested"] is False
    assert receipt["network_authorized"] is False
    assert receipt["retry"] is False
    assert receipt["device_gate_decision"] == "UNVERIFIED"
    assert receipt["d1_go"] is False
    assert receipt["raw_retained"] is False
    assert verify_d1_n2_receipt_semantics(payload)
    assert platform.launches == 1
    assert platform.lease_closed and platform.mutex.released
    assert phases == ["PRIVACY_READY", "CAPTURE_STARTING", "FIRST_FRAME", "CAPTURE_CLOSED"]
    serialized = native._canonical_json_bytes(payload).lower()
    assert b"authority_revision" not in serialized
    assert b"authorization_nonce" not in serialized
    assert b"opaque_device_token" not in serialized


def test_d1n2_capture_core_rejects_changed_ffmpeg_before_launch_and_closes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primitives = native._load_native_primitives()
    platform = _CapturePlatform(primitives)
    monkeypatch.setattr(primitives, "_runtime_prerequisites", lambda: (b"p", b"f"))
    platform.ffmpeg_identity = lambda: (2, "a" * 64, True)  # type: ignore[method-assign]

    payload = native._run_d1n2_capture(
        primitives,
        platform,  # type: ignore[arg-type]
        _CaptureMedia(),
        _prepared_attestation(),
        lambda _phase, _value: None,
    )

    receipt = payload["receipt"]
    assert isinstance(receipt, dict)
    assert receipt["outcome"] == "NO_GO"
    assert receipt["failure_code"] == "CAPTURE_RUNTIME_FAILED"
    assert platform.launches == 0
    assert platform.lease_close_calls == 1
    assert platform.mutex.released is False
