"""No-stream Windows preparation port for the D1-N2 authority revision.

The module is constructor-inert and deliberately exposes no capture or stream
operation. Legacy native primitives are loaded lazily only inside an operation;
no legacy authority store is constructed or consulted.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, cast

from pdu_exam_observer.m2_d1_n2_canonical import (
    AuthorityLeaf,
    CanonicalLifecycleState,
    PersistenceOutcome,
    PreparedBindingAttestation,
    TerminalBindingAttestation,
    WorkerGrantBindingAttestation,
    classify_canonical_leaf_record,
)
from pdu_exam_observer.m2_d1_n2_evidence import (
    RetainedLeaseCleanup,
    build_verified_terminal_evidence,
    verify_worker_candidate_envelope,
)
from pdu_exam_observer.m2_d1_n2_prepare import (
    CameraDeviceObservation,
    CameraEnumerationObservation,
    ExecutableObservation,
)


def _load_native_primitives() -> ModuleType:
    from pdu_exam_observer import m2_d1_native

    return m2_d1_native


def _path_digest(path: str) -> str:
    normalized = os.path.normcase(os.path.abspath(path)).encode("utf-8")
    return hashlib.sha256(b"d1-n2-canonical-path-v1\0" + normalized).hexdigest()


class _ExecutableLeaseAdapter:
    def __init__(self, lease: object) -> None:
        self._lease = lease
        self._closed = False

    def validate(self) -> bool:
        if self._closed:
            return False
        recheck = getattr(self._lease, "_recheck", None)
        if not callable(recheck):
            return False
        try:
            recheck()
            return True
        except Exception:
            return False

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        close = getattr(self._lease, "close", None)
        if not callable(close):
            return False
        try:
            return bool(close())
        except BaseException:
            return False


def _observation(
    lease: object,
    *,
    version_output_digest: str | None,
) -> ExecutableObservation:
    executable = getattr(lease, "executable", None)
    binding = getattr(lease, "binding", None)
    if type(executable) is not str or binding is None:
        raise OSError("executable binding is unavailable")
    return ExecutableObservation(
        canonical_path_digest=_path_digest(executable),
        sha256=str(binding.sha256),
        size_bytes=int(binding.size_bytes),
        identity_digest=str(binding.identity_digest),
        version_output_digest=version_output_digest,
        lease=_ExecutableLeaseAdapter(lease),
    )


def _production_supervisor_observation() -> ExecutableObservation:
    native = _load_native_primitives()
    base = native.WindowsExecutableLease
    supervisor_path = str(
        Path(str(getattr(sys, "_base_executable", sys.executable))).resolve(strict=True)
    )

    class _D1N2SupervisorLease(base):  # type: ignore[misc, valid-type]
        _canonical_path = supervisor_path
        _identity_namespace = "d1-n2-supervisor-file-id-v1"
        _display_name = "D1-N2 supervisor"

    lease = _D1N2SupervisorLease()
    return _observation(lease, version_output_digest=None)


def _decode_camera_rows(payload: bytes) -> tuple[CameraDeviceObservation, ...] | None:
    if type(payload) is not bytes or not payload or len(payload) > 32_768:
        return None
    try:
        raw = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    rows = raw if type(raw) is list else [raw]
    if len(rows) > 32:
        return None
    result: list[CameraDeviceObservation] = []
    for row in rows:
        if (
            type(row) is not dict
            or set(row) != {"FriendlyName", "Present", "Status"}
            or type(row.get("FriendlyName")) is not str
            or type(row.get("Present")) is not bool
            or type(row.get("Status")) is not str
        ):
            return None
        result.append(
            CameraDeviceObservation(
                row["FriendlyName"],
                row["Present"],
                row["Status"] == "OK",
            )
        )
    return tuple(result)


def _production_camera_enumeration() -> CameraEnumerationObservation:
    native = _load_native_primitives()
    base = native._WindowsPowerShellExecutableLease

    class _D1N2PowerShellLease(base):  # type: ignore[misc, valid-type]
        _identity_namespace = "d1-n2-powershell-file-id-v1"
        _display_name = "D1-N2 Windows PowerShell"

    lease = _D1N2PowerShellLease()
    adapter = _ExecutableLeaseAdapter(lease)
    command = (
        lease.executable,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-PnpDevice -Class Camera -PresentOnly | "
        "Select-Object FriendlyName,Status,Present | ConvertTo-Json -Compress",
    )
    system32 = str(native.WINDOWS_SYSTEM_DIRECTORY)
    powershell = str(Path(str(native.POWERSHELL_CANONICAL_PATH)).parent)
    environment = {
        "SystemRoot": str(Path(system32).parent),
        "WINDIR": str(Path(system32).parent),
        "PATH": os.pathsep.join((powershell, system32)),
    }
    child: subprocess.Popen[bytes] | None = None
    try:
        launch = lease._launch_suspended
        child = launch(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            cwd=str(native.POWERSHELL_WORKING_DIRECTORY),
        )
        output, _ = child.communicate(timeout=10.0)
        devices = _decode_camera_rows(output)
        if child.returncode != 0 or not lease.image_verified or devices is None:
            raise OSError("camera enumeration evidence is invalid")
        if not adapter.validate():
            raise OSError("camera enumerator lease drifted")
        return CameraEnumerationObservation(devices, adapter)
    except Exception:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=2.0)
        adapter.close()
        raise


def _production_ffmpeg_observation() -> ExecutableObservation:
    native = _load_native_primitives()
    lease = native.WindowsExecutableLease()
    try:
        binding = lease.probe_version()
        return _observation(
            lease,
            version_output_digest=str(binding.version_output_sha256),
        )
    except Exception:
        lease.close()
        raise


def _production_dependency_observation_digest() -> str:
    installed = metadata.version("mediapipe")
    payload = json.dumps(
        {
            "declared_pin": "mediapipe==1.0.1",
            "installed_version": installed,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if installed != "1.0.1":
        raise OSError("installed dependency does not match the fixed pin")
    return hashlib.sha256(payload).hexdigest()


class D1N2WindowsPreparationPort:
    """Parameterless production port; construction performs no native work."""

    def attest_supervisor(self) -> ExecutableObservation:
        return _production_supervisor_observation()

    def enumerate_camera_class(self) -> CameraEnumerationObservation:
        return _production_camera_enumeration()

    def attest_ffmpeg(self) -> ExecutableObservation:
        return _production_ffmpeg_observation()

    def dependency_observation_digest(self) -> str:
        return _production_dependency_observation_digest()


class D1N2DriverStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class D1N2ExecutionRequest:
    grant_capability: bytes
    grant_record: bytes
    device_name: str
    prepared_authority_digest: str
    raw_challenge: bytes
    prepared_attestation: PreparedBindingAttestation | None = None
    duration_seconds: int = 60
    video_only: bool = True
    retry: bool = False


@dataclass(frozen=True, slots=True)
class D1N2DriverResult:
    status: D1N2DriverStatus
    native_side_effect_count: int
    receipt_digest: str | None
    worker_supervised: bool
    job_drained: bool
    worker_lease_closed: bool
    receipt_bytes: bytes | None = None
    failure_ledger_bytes: bytes | None = None


class _ExecutionAuthority(Protocol):
    def revalidate_for_run(self) -> bool: ...

    def consume(self) -> PersistenceOutcome: ...

    def issue_grant(self, binding: WorkerGrantBindingAttestation) -> PersistenceOutcome: ...

    def take_grant_capability(self) -> bytes | None: ...

    def grant_record_bytes(self) -> bytes | None: ...

    def authorize_grant(self, capability: bytes) -> PersistenceOutcome: ...

    def revoke_grant(self) -> PersistenceOutcome: ...

    def close_retained_for_terminal(self) -> RetainedLeaseCleanup | None: ...

    def terminalize(self, binding: TerminalBindingAttestation) -> PersistenceOutcome: ...


class _ExecutionDriver(Protocol):
    def run(self, request: D1N2ExecutionRequest) -> D1N2DriverResult: ...


class D1N2ExecutionStatus(StrEnum):
    TERMINAL = "TERMINAL"
    FAILED_NONLAUNCHABLE = "FAILED_NONLAUNCHABLE"
    ALREADY_USED = "ALREADY_USED"


@dataclass(frozen=True, slots=True)
class D1N2ExecutionResult:
    status: D1N2ExecutionStatus
    native_side_effect_count: int = 0
    receipt_digest: str | None = None


class D1N2ExecutionBridge:
    """Single-use state bridge; only the injected driver owns native capture."""

    def __init__(
        self,
        authority: _ExecutionAuthority,
        driver: _ExecutionDriver,
        *,
        device_name: str,
        prepared_authority_digest: str,
        prepared_attestation: PreparedBindingAttestation | None = None,
        challenge_entropy: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self._authority = authority
        self._driver = driver
        self._device_name = device_name
        self._prepared_authority_digest = prepared_authority_digest
        self._prepared_attestation = prepared_attestation
        self._challenge_entropy = challenge_entropy
        self._used = False

    def run(self) -> D1N2ExecutionResult:
        if self._used:
            return D1N2ExecutionResult(D1N2ExecutionStatus.ALREADY_USED)
        self._used = True
        grant_attempted = False
        grant_issued = False
        driver_result: D1N2DriverResult | None = None
        cleanup_ok = True
        capability = b""
        raw_challenge = b""
        challenge_digest = ""
        job_name_digest = ""
        grant_record = b""
        terminal_receipt_digest: str | None = None
        try:
            if (
                not _safe_device_name(self._device_name)
                or not _is_lower_digest(self._prepared_authority_digest)
                or not self._authority.revalidate_for_run()
                or self._authority.consume() is not PersistenceOutcome.OK
            ):
                return D1N2ExecutionResult(
                    D1N2ExecutionStatus.FAILED_NONLAUNCHABLE
                )
            attestation = self._prepared_attestation
            if attestation is None:
                return D1N2ExecutionResult(D1N2ExecutionStatus.FAILED_NONLAUNCHABLE)
            raw_challenge = self._challenge_entropy(32)
            if type(raw_challenge) is not bytes or len(raw_challenge) != 32:
                return D1N2ExecutionResult(D1N2ExecutionStatus.FAILED_NONLAUNCHABLE)
            challenge = raw_challenge.hex()
            challenge_digest = _d1n2_challenge_digest(challenge)
            job_name_digest = _d1n2_job_name_digest(challenge)
            worker_binding = WorkerGrantBindingAttestation(
                self._prepared_authority_digest,
                attestation.supervisor_sha256,
                attestation.supervisor_size_bytes,
                attestation.supervisor_identity_digest,
                _d1n2_worker_argv_digest(),
                _d1n2_worker_job_policy_digest(),
                challenge_digest,
                job_name_digest,
                60,
                True,
                False,
            )
            grant_attempted = True
            if self._authority.issue_grant(worker_binding) is not PersistenceOutcome.OK:
                return D1N2ExecutionResult(D1N2ExecutionStatus.FAILED_NONLAUNCHABLE)
            grant_issued = True
            value = self._authority.take_grant_capability()
            if type(value) is not bytes or len(value) != 32:
                return D1N2ExecutionResult(D1N2ExecutionStatus.FAILED_NONLAUNCHABLE)
            capability = value
            grant_record = self._authority.grant_record_bytes() or b""
            if type(grant_record) is not bytes or not grant_record:
                return D1N2ExecutionResult(D1N2ExecutionStatus.FAILED_NONLAUNCHABLE)
            if self._authority.authorize_grant(capability) is not PersistenceOutcome.OK:
                return D1N2ExecutionResult(D1N2ExecutionStatus.FAILED_NONLAUNCHABLE)
            driver_result = self._driver.run(
                D1N2ExecutionRequest(
                    capability,
                    grant_record,
                    self._device_name,
                    self._prepared_authority_digest,
                    raw_challenge,
                    self._prepared_attestation,
                )
            )
        except Exception:
            driver_result = None
        finally:
            capability = b""
            raw_challenge = b""
            revoke_needed = grant_issued
            if grant_attempted and not revoke_needed:
                try:
                    revoke_needed = self._authority.grant_record_bytes() is not None
                except Exception:
                    cleanup_ok = False
            if revoke_needed:
                try:
                    cleanup_ok = (
                        self._authority.revoke_grant() is PersistenceOutcome.OK
                        and cleanup_ok
                    )
                except Exception:
                    cleanup_ok = False
            try:
                revoked_record = (
                    self._authority.grant_record_bytes() if grant_issued else None
                )
                retained = self._authority.close_retained_for_terminal()
                cleanup_ok = retained is not None and cleanup_ok
                receipt_bytes: bytes | None = None
                if (
                    cleanup_ok
                    and driver_result is not None
                    and type(driver_result.receipt_bytes) is bytes
                    and type(revoked_record) is bytes
                    and revoked_record
                    and self._prepared_attestation is not None
                ):
                    candidate = json.loads(driver_result.receipt_bytes.decode("utf-8"))
                    if type(candidate) is dict:
                        candidate.update(
                            {
                                "authority_digest": self._prepared_authority_digest,
                                "grant_record_digest": hashlib.sha256(
                                    revoked_record
                                ).hexdigest(),
                                "challenge_digest": challenge_digest,
                                "job_name_digest": job_name_digest,
                                "static_bindings_digest": (
                                    self._prepared_attestation.static_bindings_digest
                                ),
                                "capture_policy_digest": _d1n2_capture_policy_digest(),
                                "watchdog_policy_digest": _d1n2_watchdog_policy_digest(),
                                "runtime_digest": (
                                    self._prepared_attestation.dependency_observation_digest
                                ),
                                "pose_model_sha256": (
                                    self._prepared_attestation.pose_model_sha256
                                ),
                                "face_model_sha256": (
                                    self._prepared_attestation.face_model_sha256
                                ),
                            }
                        )
                        receipt_bytes = _canonical_json_bytes(candidate)
                evidence = (
                    build_verified_terminal_evidence(
                        receipt_bytes,
                        driver_result.failure_ledger_bytes,
                        retained,
                    )
                    if cleanup_ok
                    and driver_result is not None
                    and type(receipt_bytes) is bytes
                    and type(driver_result.failure_ledger_bytes) is bytes
                    and retained is not None
                    else None
                )
                if evidence is None or driver_result is None:
                    cleanup_ok = False
                else:
                    terminal_receipt_digest = evidence.receipt_digest
                    terminal_binding = TerminalBindingAttestation.from_evidence(
                        evidence,
                        driver_result.native_side_effect_count,
                    )
                    terminal = self._authority.terminalize(terminal_binding)
                    cleanup_ok = terminal in {
                        PersistenceOutcome.OK,
                        PersistenceOutcome.TERMINAL_ALREADY_PRESENT,
                    } and cleanup_ok
            except Exception:
                cleanup_ok = False

        if (
            not cleanup_ok
            or driver_result is None
            or driver_result.status is not D1N2DriverStatus.COMPLETED
            or type(driver_result.native_side_effect_count) is not int
            or driver_result.native_side_effect_count not in {0, 1}
            or not _is_lower_digest(terminal_receipt_digest)
            or not driver_result.worker_supervised
            or not driver_result.job_drained
            or not driver_result.worker_lease_closed
        ):
            return D1N2ExecutionResult(
                D1N2ExecutionStatus.FAILED_NONLAUNCHABLE,
                0 if driver_result is None else driver_result.native_side_effect_count,
            )
        return D1N2ExecutionResult(
            D1N2ExecutionStatus.TERMINAL,
            driver_result.native_side_effect_count,
            terminal_receipt_digest,
        )


def _safe_device_name(value: object) -> bool:
    if type(value) is not str or not 1 <= len(value) <= 128:
        return False
    return all(character.isalnum() or character in " _().-" for character in value)


def _is_lower_digest(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


_D1N2_WORKER_ARGUMENT = "--d1-n2-capture-worker-v1"
_D1N2_WORKER_CHALLENGE_ENV = "PDU_D1_N2_WORKER_CHALLENGE"
_D1N2_JOB_PREFIX = "Local\\PDUExamObserver.D1N2.Capture."
_D1N2_VIDEO_MUTEX = "Local\\PDUExamObserver.D1N2.VideoOnly"
_D1N2_WORKER_MESSAGE_MAX_BYTES = 65_536


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _decode_grant_record(payload: bytes, capability: bytes) -> dict[str, object] | None:
    if (
        type(payload) is not bytes
        or classify_canonical_leaf_record(AuthorityLeaf.GRANT, payload)
        is not CanonicalLifecycleState.ISSUED
        or type(capability) is not bytes
        or len(capability) != 32
    ):
        return None
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (
        type(decoded) is not dict
        or _canonical_json_bytes(decoded) != payload
        or decoded.get("grant_digest") != hashlib.sha256(capability).hexdigest()
        or type(decoded.get("issued_monotonic_ns")) is not int
        or type(decoded.get("expires_monotonic_ns")) is not int
        or time.perf_counter_ns() > decoded["expires_monotonic_ns"]
    ):
        return None
    return decoded


def _valid_execution_request(request: object) -> bool:
    if not (
        type(request) is D1N2ExecutionRequest
        and _decode_grant_record(request.grant_record, request.grant_capability) is not None
        and _safe_device_name(request.device_name)
        and _is_lower_digest(request.prepared_authority_digest)
        and type(request.raw_challenge) is bytes
        and len(request.raw_challenge) == 32
        and type(request.prepared_attestation) is PreparedBindingAttestation
        and request.prepared_attestation.valid()
        and request.duration_seconds == 60
        and request.video_only is True
        and request.retry is False
    ):
        return False
    grant = _decode_grant_record(request.grant_record, request.grant_capability)
    if grant is None:
        return False
    challenge = request.raw_challenge.hex()
    return (
        grant.get("challenge_digest") == _d1n2_challenge_digest(challenge)
        and grant.get("job_name_digest") == _d1n2_job_name_digest(challenge)
    )


def _d1n2_challenge_digest(challenge: str) -> str:
    return hashlib.sha256(
        b"d1-n2-worker-challenge-v1\0" + challenge.encode("ascii")
    ).hexdigest()


def _d1n2_job_name(challenge: str) -> str:
    if not _is_lower_digest(challenge):
        raise ValueError("worker challenge is invalid")
    return _D1N2_JOB_PREFIX + challenge


def _d1n2_job_name_digest(challenge: str) -> str:
    return hashlib.sha256(
        b"d1-n2-job-name-v1\0" + _d1n2_job_name(challenge).encode("utf-8")
    ).hexdigest()


def _d1n2_worker_bootstrap() -> str:
    project_root = Path(__file__).parents[2]
    source_root = str(project_root / "src")
    site_packages = str(project_root / ".venv" / "Lib" / "site-packages")
    return (
        "import runpy,sys;"
        f"sys.path[:0]=[{source_root!r},{site_packages!r}];"
        f"sys.argv=['pdu_exam_observer.m2_d1_n2_native',{_D1N2_WORKER_ARGUMENT!r}];"
        "runpy.run_module('pdu_exam_observer.m2_d1_n2_native',run_name='__main__')"
    )


def _d1n2_worker_argv_digest() -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            ["d1-n2-worker-argv-v1", "-I", "-u", "-c", _d1n2_worker_bootstrap()]
        )
    ).hexdigest()


def _d1n2_worker_job_policy_digest() -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "active_process_limit": 2,
                "capture_seconds": 60,
                "kill_on_close": True,
                "retry": False,
            }
        )
    ).hexdigest()


def _d1n2_capture_policy_digest() -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "canonicalization": "json-v1-sort-keys-compact-utf8",
                "fields": {"fps": 15, "height": 720, "width": 1280},
                "projection": "d1-n2.fixed-capture-profile",
                "source_id": "SRC_M2_D1_N2_NATIVE_PY",
                "version": 1,
            }
        )
    ).hexdigest()


def _d1n2_watchdog_policy_digest() -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {
                "canonicalization": "json-v1-sort-keys-compact-utf8",
                "fields": {"capture_seconds": 60, "phase_count": 6, "retry": False},
                "projection": "d1-n2.phased-watchdog",
                "source_id": "SRC_M2_D1_N2_NATIVE_PY",
                "version": 1,
            }
        )
    ).hexdigest()


def _d1n2_worker_environment(native: ModuleType, challenge: str) -> dict[str, str]:
    system32 = str(native.WINDOWS_SYSTEM_DIRECTORY)
    system_root = str(Path(system32).parent)
    powershell = str(Path(str(native.POWERSHELL_CANONICAL_PATH)).parent)
    return {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "PATH": os.pathsep.join((powershell, system32)),
        _D1N2_WORKER_CHALLENGE_ENV: challenge,
        "GLOG_minloglevel": "3",
    }


def _worker_lease(native: ModuleType) -> Any:
    base = native.WindowsExecutableLease
    worker_path = str(
        Path(str(getattr(sys, "_base_executable", sys.executable))).resolve(strict=True)
    )

    class _D1N2WorkerLease(base):  # type: ignore[misc, valid-type]
        _canonical_path = worker_path
        _identity_namespace = "d1-n2-worker-file-id-v1"
        _display_name = "D1-N2 capture worker"

    return _D1N2WorkerLease()


def _send_d1n2_worker_request(
    child: subprocess.Popen[bytes],
    request: D1N2ExecutionRequest,
    challenge_digest: str,
    grant_id: str,
) -> None:
    if child.stdin is None or request.prepared_attestation is None:
        raise OSError("worker input channel is unavailable")
    message = {
        "attestation": request.prepared_attestation.record_fields(),
        "capability": request.grant_capability.hex(),
        "challenge_digest": challenge_digest,
        "device_name": request.device_name,
        "grant_id": grant_id,
        "grant_record": request.grant_record.decode("ascii"),
        "prepared_authority_digest": request.prepared_authority_digest,
    }
    encoded = _canonical_json_bytes(message)
    if len(encoded) + 1 > _D1N2_WORKER_MESSAGE_MAX_BYTES:
        raise ValueError("worker request is oversized")
    try:
        child.stdin.write(encoded + b"\n")
        child.stdin.flush()
    finally:
        child.stdin.close()


def _verify_d1n2_worker_payload(payload: object) -> bool:
    return verify_worker_candidate_envelope(payload)


class D1N2WindowsCaptureDriver:
    """Dormant one-attempt Windows worker driver; construction is inert."""

    def run(self, request: D1N2ExecutionRequest) -> D1N2DriverResult:
        if not _valid_execution_request(request):
            return D1N2DriverResult(D1N2DriverStatus.FAILED, 0, None, False, False, False)
        native = _load_native_primitives()
        challenge = request.raw_challenge.hex()
        challenge_digest = _d1n2_challenge_digest(challenge)
        if _d1n2_job_name_digest(challenge) != json.loads(
            request.grant_record.decode("utf-8")
        ).get("job_name_digest"):
            return D1N2DriverResult(D1N2DriverStatus.FAILED, 0, None, False, False, False)
        grant_id = hashlib.sha256(request.grant_record).hexdigest()
        lease: Any | None = None
        job: Any | None = None
        child: subprocess.Popen[bytes] | None = None
        monitor: object | None = None
        lease_closed = False
        job_closed = False
        attempted = 0
        try:
            lease = _worker_lease(native)
            binding = lease.binding
            attestation = request.prepared_attestation
            assert attestation is not None
            if (
                binding.sha256 != attestation.supervisor_sha256
                or binding.size_bytes != attestation.supervisor_size_bytes
                or binding.identity_digest != attestation.supervisor_identity_digest
            ):
                raise OSError("worker image differs from prepared supervisor")
            job = native._WindowsCaptureJob(_d1n2_job_name(challenge))
            argv = (lease.executable, "-I", "-u", "-c", _d1n2_worker_bootstrap())
            child = lease._launch_suspended(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                before_resume=job.assign,
                env=_d1n2_worker_environment(native, challenge),
                cwd=str(native.POWERSHELL_WORKING_DIRECTORY),
            )
            attempted = 1
            _send_d1n2_worker_request(child, request, challenge_digest, grant_id)
            monitor = native._monitor_capture_worker(
                child,
                job,
                challenge_digest,
                grant_id,
            )
        except Exception:
            if child is not None and child.poll() is None and job is not None:
                try:
                    job.terminate_and_drain(child)
                except Exception:
                    pass
        finally:
            if lease is not None:
                try:
                    lease_closed = bool(lease.close())
                except Exception:
                    lease_closed = False
            if job is not None:
                try:
                    job_closed = bool(job.close())
                except Exception:
                    job_closed = False
        if monitor is None:
            return D1N2DriverResult(
                D1N2DriverStatus.FAILED,
                attempted,
                None,
                False,
                False,
                lease_closed,
            )
        payload = getattr(monitor, "payload", None)
        supervised = bool(getattr(job, "assigned", False)) and bool(
            getattr(monitor, "authorized", False)
        )
        drained = bool(getattr(monitor, "job_drained", False)) and job_closed
        clean = (
            type(payload) is dict
            and _verify_d1n2_worker_payload(payload)
            and not bool(getattr(monitor, "timed_out", True))
            and not bool(getattr(monitor, "malformed", True))
            and bool(getattr(monitor, "pipe_closed", False))
            and bool(getattr(monitor, "reader_stopped", False))
            and not bool(getattr(monitor, "forced_termination", True))
            and getattr(monitor, "exit_code", None) == 0
            and supervised
            and drained
            and lease_closed
        )
        receipt_object = payload.get("receipt") if type(payload) is dict else None
        ledger_object = payload.get("failure_ledger") if type(payload) is dict else None
        if type(receipt_object) is dict and request.prepared_attestation is not None:
            receipt_object = dict(receipt_object)
            prepared = request.prepared_attestation
            receipt_object.update(
                {
                    "authority_digest": request.prepared_authority_digest,
                    "grant_record_digest": hashlib.sha256(request.grant_record).hexdigest(),
                    "challenge_digest": challenge_digest,
                    "job_name_digest": _d1n2_job_name_digest(challenge),
                    "static_bindings_digest": prepared.static_bindings_digest,
                    "capture_policy_digest": _d1n2_capture_policy_digest(),
                    "watchdog_policy_digest": _d1n2_watchdog_policy_digest(),
                    "runtime_digest": prepared.dependency_observation_digest,
                    "pose_model_sha256": prepared.pose_model_sha256,
                    "face_model_sha256": prepared.face_model_sha256,
                    "watchdog_authorized": bool(getattr(monitor, "authorized", False)),
                    "privacy_ready": bool(getattr(monitor, "privacy_ready", False)),
                    "capture_starting": bool(getattr(monitor, "capture_starting", False)),
                    "first_frame": bool(getattr(monitor, "first_frame", False)),
                    "capture_closed": bool(getattr(monitor, "capture_closed", False)),
                    "receipt_received": payload is not None,
                    "worker_supervised": supervised,
                    "job_drained": drained,
                    "worker_lease_closed": lease_closed,
                }
            )
        receipt_bytes = (
            _canonical_json_bytes(receipt_object)
            if clean and type(receipt_object) is dict
            else None
        )
        failure_ledger_bytes = (
            _canonical_json_bytes(ledger_object)
            if clean and type(ledger_object) is list
            else None
        )
        receipt_digest = hashlib.sha256(receipt_bytes).hexdigest() if receipt_bytes else None
        return D1N2DriverResult(
            D1N2DriverStatus.COMPLETED if clean else D1N2DriverStatus.FAILED,
            attempted,
            receipt_digest,
            supervised,
            drained,
            lease_closed,
            receipt_bytes,
            failure_ledger_bytes,
        )


def _current_process_in_d1n2_job(native: ModuleType, challenge: str) -> bool:
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
    handle = kernel32.OpenJobObjectW(native.JOB_OBJECT_QUERY, False, _d1n2_job_name(challenge))
    if not handle:
        return False
    try:
        in_job = ctypes.c_int(0)
        limits = native._JobExtendedLimitInformation()
        if not kernel32.IsProcessInJob(
            kernel32.GetCurrentProcess(), handle, ctypes.byref(in_job)
        ) or not kernel32.QueryInformationJobObject(
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


def _strict_json_object(payload: bytes) -> dict[str, object] | None:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate worker field")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _value: (_ for _ in ()).throw(ValueError("float")),
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return decoded if type(decoded) is dict else None


def _receive_d1n2_worker_request(
    challenge: str,
) -> tuple[D1N2ExecutionRequest, str] | None:
    line = sys.stdin.buffer.readline(_D1N2_WORKER_MESSAGE_MAX_BYTES + 1)
    if not line or len(line) > _D1N2_WORKER_MESSAGE_MAX_BYTES:
        return None
    raw = _strict_json_object(line)
    expected_keys = {
        "attestation",
        "capability",
        "challenge_digest",
        "device_name",
        "grant_id",
        "grant_record",
        "prepared_authority_digest",
    }
    if raw is None or set(raw) != expected_keys:
        return None
    if raw.get("challenge_digest") != _d1n2_challenge_digest(challenge):
        return None
    capability_text = raw.get("capability")
    grant_record_text = raw.get("grant_record")
    attestation_raw = raw.get("attestation")
    if (
        type(capability_text) is not str
        or len(capability_text) != 64
        or type(grant_record_text) is not str
        or type(attestation_raw) is not dict
        or set(attestation_raw) != set(PreparedBindingAttestation.__dataclass_fields__)
    ):
        return None
    try:
        capability = bytes.fromhex(capability_text)
        grant_record = grant_record_text.encode("ascii")
        attestation = PreparedBindingAttestation(**attestation_raw)
    except (TypeError, ValueError, UnicodeEncodeError):
        return None
    request = D1N2ExecutionRequest(
        capability,
        grant_record,
        str(raw.get("device_name")),
        str(raw.get("prepared_authority_digest")),
        bytes.fromhex(challenge),
        attestation,
    )
    grant_id = raw.get("grant_id")
    if (
        not _valid_execution_request(request)
        or not _is_lower_digest(grant_id)
        or grant_id != hashlib.sha256(grant_record).hexdigest()
    ):
        return None
    return request, cast(str, grant_id)


class _D1N2WorkerPlatform:
    def __init__(self, native: ModuleType, expected_device_name: str) -> None:
        self._native = native
        self._expected_device_name = expected_device_name
        self._ffmpeg_lease: Any | None = None
        self._ffmpeg_verified = False

    def camera_class_devices(self) -> tuple[Any, ...]:
        enumeration = _production_camera_enumeration()
        try:
            devices = enumeration.devices
            if (
                not enumeration.lease.validate()
                or len(devices) != 1
                or devices[0].friendly_name != self._expected_device_name
            ):
                return ()
            return tuple(
                self._native.CameraCandidate(
                    device.friendly_name,
                    device.present,
                    device.status_ok,
                )
                for device in devices
            )
        finally:
            if not enumeration.lease.close():
                raise OSError("camera enumerator cleanup failed")

    def ffmpeg_authority(self) -> tuple[str, str, str]:
        if self._ffmpeg_lease is not None:
            raise OSError("FFmpeg lease already exists")
        lease = self._native.WindowsExecutableLease()
        binding = lease.probe_version()
        self._ffmpeg_lease = lease
        return (
            str(lease.executable),
            str(binding.sha256),
            str(binding.version_output_sha256),
        )

    def sha256_of_executable(self, executable: str) -> str:
        lease = self._ffmpeg_lease
        if lease is None or executable != lease.executable:
            raise OSError("FFmpeg executable is not leased")
        return str(lease.binding.sha256)

    def ffmpeg_identity(self) -> tuple[int, str, bool]:
        lease = self._ffmpeg_lease
        if lease is None:
            raise OSError("FFmpeg lease is unavailable")
        binding = lease.binding
        return (
            int(binding.size_bytes),
            str(binding.identity_digest),
            bool(lease.image_verified),
        )

    def ffmpeg_lease_verified(self) -> bool:
        return self._ffmpeg_verified

    def close_ffmpeg_lease(self) -> bool:
        if self._ffmpeg_lease is None:
            return True
        lease, self._ffmpeg_lease = self._ffmpeg_lease, None
        return bool(lease.close())

    def named_mutex(self) -> Any:
        return self._native.WindowsNamedMutex(_D1N2_VIDEO_MUTEX)

    def launch_video_only(self, argv: tuple[str, ...]) -> Any:
        lease = self._ffmpeg_lease
        if lease is None:
            raise OSError("FFmpeg lease is unavailable")
        child = lease.launch_video_only(argv)
        self._ffmpeg_verified = bool(lease.image_verified)
        return child

    def monotonic_ns(self) -> int:
        return time.perf_counter_ns()


def _emit_d1n2_phase(native: ModuleType, event: str, digest: str, value: int) -> None:
    if event == "PRIVACY_READY":
        native._emit_worker_message(event, digest)
    elif event in {"CAPTURE_STARTING", "FIRST_FRAME", "CAPTURE_CLOSED"}:
        native._emit_worker_message(event, digest, {"worker_monotonic_ns": value})
    else:
        raise ValueError("worker phase is invalid")


def _d1n2_capture_payload(
    native: ModuleType,
    state: Any,
    *,
    failure: Any | None,
    raw_retained: bool,
    mutex_released: bool,
    child_terminated: bool,
    pipe_closed: bool,
    reader_stopped: bool,
    media_closed: bool,
    ffmpeg_lease_verified: bool,
    ffmpeg_lease_closed: bool,
    ffmpeg_sha256: str | None,
    ffmpeg_version_digest: str | None,
    ffmpeg_size_bytes: int | None,
    ffmpeg_identity_digest: str | None,
    fixed_argv_digest: str | None,
) -> dict[str, object]:
    first = state.first_ingress_ns
    previous = state.previous_ingress_ns
    total_ns = (
        previous - first
        if type(first) is int and type(previous) is int and previous >= first
        else 0
    )
    post_ns = max(total_ns - native.WARMUP_SECONDS * 1_000_000_000, 0)
    gaps = tuple(state.gaps_ms or ())
    latencies = tuple(state.latencies_ms or ())
    if failure is None:
        failure = (
            native.NativeFailure.INPUT_UNAVAILABLE
            if first is None or previous is None
            else native._threshold_failure(
                state,
                total_ns / 1_000_000_000,
                post_ns / 1_000_000_000,
                gaps,
                latencies,
            )
        )
    raw_failure = None if failure is None else str(failure.value)
    failure_code = None
    failure_stage = None
    if raw_failure is not None:
        if raw_failure == "PRIVACY_STOP":
            failure_code, failure_stage = "PRIVACY_STOP", "PRIVACY"
        elif raw_failure in {"FRAME_STALLED", "CLOCK_REGRESSION"}:
            failure_code, failure_stage = "FRAME_STALLED", "WATCHDOG"
        elif raw_failure == "QUALITY_INSUFFICIENT":
            failure_code, failure_stage = "QUALITY_INSUFFICIENT", "ACCOUNTING"
        elif raw_failure == "CLEANUP_INCOMPLETE":
            failure_code, failure_stage = "CLEANUP_INCOMPLETE", "CLEANUP"
        else:
            failure_code, failure_stage = "CAPTURE_RUNTIME_FAILED", "CAPTURE"
    delivered = int(state.delivered_frames)
    processed = int(state.processed_frames)
    inference_failed = max(delivered - processed, 0)
    post_successful = int(state.post_warmup_processed_frames)
    receipt = {
        "schema_version": 1,
        "outcome": "D1_N2_PREFLIGHT_PASS" if failure is None else "NO_GO",
        "failure_code": failure_code,
        "duration_seconds": 60,
        "video_only": True,
        "audio_requested": False,
        "network_authorized": False,
        "network_transport_constructed": False,
        "outbound_attempt_count": 0,
        "retry": False,
        "device_gate_decision": "UNVERIFIED",
        "d1_go": False,
        "raw_retained": raw_retained,
        "privacy_checked_frames": processed,
        "privacy_stop_count": int(state.privacy_stop_count),
        "face_detections": int(state.face_detections),
        "pose_detections": int(state.pose_detections),
        "received_frames": delivered,
        "delivered_frames": delivered,
        "processed_frames": processed,
        "dropped_explicit_frames": 0,
        "dropped_short_frames": 0,
        "failed_frames": inference_failed,
        "inference_failure_frames": inference_failed,
        "privacy_terminal_frames": 0,
        "delivery_failure_frames": 0,
        "post_attempted_frames": post_successful,
        "post_successful_frames": post_successful,
        "measured_total_ns": total_ns,
        "measured_post_warmup_ns": post_ns,
        "post_elapsed_ns": post_ns,
        "p95_ingress_gap_us": (
            int(native.nearest_rank(gaps, 95) * 1_000) if gaps else 0
        ),
        "p95_pose_latency_us": (
            int(native.nearest_rank(latencies, 95) * 1_000) if latencies else 0
        ),
        "p99_pose_latency_us": (
            int(native.nearest_rank(latencies, 99) * 1_000) if latencies else 0
        ),
        "backlog_ns": int(state.max_backlog_ns),
        "max_stall_gap_ns": int(max(gaps) * 1_000_000) if gaps else 0,
        "mutex_released": mutex_released,
        "pipe_closed": pipe_closed,
        "media_closed": media_closed,
        "ffmpeg_lease_closed": ffmpeg_lease_closed,
        "buffers_cleared": not raw_retained and reader_stopped,
        "worker_supervised": False,
        "job_drained": False,
        "worker_lease_closed": False,
        "watchdog_authorized": False,
        "privacy_ready": True,
        "capture_starting": True,
        "first_frame": delivered > 0,
        "capture_closed": child_terminated,
        "receipt_received": False,
        "authority_digest": "0" * 64,
        "grant_record_digest": "0" * 64,
        "challenge_digest": "0" * 64,
        "job_name_digest": "0" * 64,
        "static_bindings_digest": "0" * 64,
        "capture_policy_digest": "0" * 64,
        "watchdog_policy_digest": "0" * 64,
        "runtime_digest": "0" * 64,
        "pose_model_sha256": "0" * 64,
        "face_model_sha256": "0" * 64,
    }
    del ffmpeg_lease_verified, ffmpeg_sha256, ffmpeg_version_digest
    del ffmpeg_size_bytes, ffmpeg_identity_digest, fixed_argv_digest
    ledger = (
        []
        if failure_code is None
        else [
            {
                "code": failure_code,
                "count": 1,
                "precedence": 0,
                "stage": failure_stage,
            }
        ]
    )
    return {"failure_ledger": ledger, "receipt": receipt}


def _run_d1n2_capture(
    native: ModuleType,
    platform: _D1N2WorkerPlatform,
    media: Any,
    attestation: PreparedBindingAttestation,
    event_sink: Any,
) -> dict[str, object]:
    state = native._RunState()
    failure: Any | None = None
    raw_retained = False
    mutex_released = False
    child_terminated = False
    pipe_closed = False
    reader_stopped = False
    media_closed = False
    ffmpeg_lease_verified = False
    ffmpeg_lease_closed = True
    ffmpeg_sha256: str | None = None
    ffmpeg_version_digest: str | None = None
    ffmpeg_size_bytes: int | None = None
    ffmpeg_identity_digest: str | None = None
    fixed_argv_digest: str | None = None
    mutex: Any | None = None
    child: Any | None = None
    reader: Any | None = None
    buffers: tuple[bytearray, bytearray] | None = None
    capture_scope = False

    if native._runtime_prerequisites() is None:
        failure = native.NativeFailure.POSE_ENGINE_UNAVAILABLE
        media_closed = native._close_media(media)
        return _d1n2_capture_payload(
            native,
            state,
            failure=failure,
            raw_retained=False,
            mutex_released=False,
            child_terminated=False,
            pipe_closed=False,
            reader_stopped=False,
            media_closed=media_closed,
            ffmpeg_lease_verified=False,
            ffmpeg_lease_closed=True,
            ffmpeg_sha256=None,
            ffmpeg_version_digest=None,
            ffmpeg_size_bytes=None,
            ffmpeg_identity_digest=None,
            fixed_argv_digest=None,
        )
    try:
        runtime_live = bool(media.liveness())
    except Exception:
        runtime_live = False
    if not runtime_live:
        failure = native.NativeFailure.POSE_ENGINE_UNAVAILABLE
        media_closed = native._close_media(media)
        return _d1n2_capture_payload(
            native,
            state,
            failure=failure,
            raw_retained=False,
            mutex_released=False,
            child_terminated=False,
            pipe_closed=False,
            reader_stopped=False,
            media_closed=media_closed,
            ffmpeg_lease_verified=False,
            ffmpeg_lease_closed=True,
            ffmpeg_sha256=None,
            ffmpeg_version_digest=None,
            ffmpeg_size_bytes=None,
            ffmpeg_identity_digest=None,
            fixed_argv_digest=None,
        )
    try:
        event_sink("PRIVACY_READY", platform.monotonic_ns())
        cameras = platform.camera_class_devices()
        executable, ffmpeg_sha256, ffmpeg_version_digest = platform.ffmpeg_authority()
        ffmpeg_lease_closed = False
        executable_digest = platform.sha256_of_executable(executable)
        ffmpeg_size_bytes, ffmpeg_identity_digest, _ = platform.ffmpeg_identity()
        current = cameras[0] if len(cameras) == 1 else None
        if (
            current is None
            or not current.present
            or not current.status_ok
            or not native._safe_directshow_name(current.friendly_name)
            or executable_digest != ffmpeg_sha256
            or ffmpeg_sha256 != attestation.ffmpeg_sha256
            or ffmpeg_version_digest != attestation.ffmpeg_version_digest
            or ffmpeg_size_bytes != attestation.ffmpeg_size_bytes
            or ffmpeg_identity_digest != attestation.ffmpeg_identity_digest
        ):
            failure = native.NativeFailure.SCHEMA_INCOMPATIBLE
            return _d1n2_capture_payload(
                native,
                state,
                failure=failure,
                raw_retained=False,
                mutex_released=False,
                child_terminated=False,
                pipe_closed=False,
                reader_stopped=False,
                media_closed=native._close_media(media),
                ffmpeg_lease_verified=False,
                ffmpeg_lease_closed=native._close_platform_ffmpeg_lease(platform),
                ffmpeg_sha256=ffmpeg_sha256,
                ffmpeg_version_digest=ffmpeg_version_digest,
                ffmpeg_size_bytes=ffmpeg_size_bytes,
                ffmpeg_identity_digest=ffmpeg_identity_digest,
                fixed_argv_digest=None,
            )
        mutex = platform.named_mutex()
        if not mutex.acquire():
            failure = native.NativeFailure.SCHEMA_INCOMPATIBLE
            return _d1n2_capture_payload(
                native,
                state,
                failure=failure,
                raw_retained=False,
                mutex_released=False,
                child_terminated=False,
                pipe_closed=False,
                reader_stopped=False,
                media_closed=native._close_media(media),
                ffmpeg_lease_verified=False,
                ffmpeg_lease_closed=native._close_platform_ffmpeg_lease(platform),
                ffmpeg_sha256=ffmpeg_sha256,
                ffmpeg_version_digest=ffmpeg_version_digest,
                ffmpeg_size_bytes=ffmpeg_size_bytes,
                ffmpeg_identity_digest=ffmpeg_identity_digest,
                fixed_argv_digest=None,
            )
        capture_scope = True
        failure = None
        raw_retained = True
        buffers = (bytearray(native.FRAME_BYTES), bytearray(native.FRAME_BYTES))
        argv = native._fixed_argv(executable, current.friendly_name)
        fixed_argv_digest = hashlib.sha256(
            _canonical_json_bytes(native._fixed_argv("<EXECUTABLE>", "<SERVER_CAMERA>"))
        ).hexdigest()
        event_sink("CAPTURE_STARTING", platform.monotonic_ns())
        child = platform.launch_video_only(argv)
        reader = native._FrameReader(child.stdout, buffers, platform.monotonic_ns)
        reader.start()
        while True:
            frame_event = reader.next()
            if frame_event is None:
                failure = (
                    native.NativeFailure.FRAME_STALLED
                    if reader.alive()
                    else native.NativeFailure.FRAME_READER_EXCEPTION
                )
                break
            disposition, buffer_index, count, ingress = frame_event
            if disposition in {
                native._ReaderDisposition.READ_EXCEPTION,
                native._ReaderDisposition.INGRESS_CLOCK_EXCEPTION,
            }:
                failure = native.NativeFailure.FRAME_READER_EXCEPTION
                break
            if disposition is native._ReaderDisposition.EOF:
                failure = (
                    native.NativeFailure.INPUT_UNAVAILABLE
                    if state.delivered_frames == 0
                    else native.NativeFailure.INPUT_MALFORMED
                )
                break
            if disposition is not native._ReaderDisposition.FRAME or count is None:
                failure = native.NativeFailure.FRAME_READER_EXCEPTION
                break
            if count != native.FRAME_BYTES:
                failure = native.NativeFailure.INPUT_MALFORMED
                break
            if ingress is None:
                failure = native.NativeFailure.FRAME_READER_EXCEPTION
                break
            dequeued = platform.monotonic_ns()
            if dequeued < ingress:
                failure = native.NativeFailure.CLOCK_REGRESSION
                break
            state.max_backlog_ns = max(state.max_backlog_ns, dequeued - ingress)
            if state.first_ingress_ns is None:
                state.first_ingress_ns = ingress
                event_sink("FIRST_FRAME", ingress)
            if state.previous_ingress_ns is not None:
                gap = ingress - state.previous_ingress_ns
                if gap <= 0:
                    failure = native.NativeFailure.CLOCK_REGRESSION
                    break
                if gap >= 1_000_000_000:
                    failure = native.NativeFailure.FRAME_STALLED
                    break
            timestamp_ms = (ingress - state.first_ingress_ns) // 1_000_000
            if timestamp_ms <= state.previous_video_timestamp_ms:
                failure = native.NativeFailure.CLOCK_REGRESSION
                break
            state.previous_video_timestamp_ms = timestamp_ms
            frame = memoryview(buffers[buffer_index])
            try:
                if media.inspect_face(frame, timestamp_ms):
                    state.face_detections += 1
                    state.privacy_stop_count = 1
                    failure = native.NativeFailure.PRIVACY_STOP
                    break
            except Exception:
                state.privacy_stop_count = 1
                failure = native.NativeFailure.PRIVACY_STOP
                break
            try:
                if media.inspect_pose(frame, timestamp_ms):
                    state.pose_detections += 1
                    state.privacy_stop_count = 1
                    failure = native.NativeFailure.PRIVACY_STOP
                    break
            except Exception:
                failure = native.NativeFailure.POSE_ENGINE_EXCEPTION
                break
            state.privacy_checked_frames += 1
            completed = platform.monotonic_ns()
            if completed < ingress:
                failure = native.NativeFailure.CLOCK_REGRESSION
                break
            state.record(ingress, completed - ingress)
            state.previous_ingress_ns = ingress
            reader.release(buffer_index)
            if ingress - state.first_ingress_ns >= 60 * 1_000_000_000:
                break
    except Exception:
        if failure is None:
            failure = native.NativeFailure.CAPTURE_RUNTIME_EXCEPTION
        if not capture_scope:
            media_closed = native._close_media(media)
            ffmpeg_lease_closed = native._close_platform_ffmpeg_lease(platform)
    finally:
        if capture_scope:
            pipe_closed, child_terminated, reader_stopped = native._cleanup_child(
                child, reader
            )
            buffers_zeroed = reader_stopped and buffers is not None
            if buffers_zeroed and buffers is not None:
                for buffer in buffers:
                    try:
                        buffer[:] = b"\0" * len(buffer)
                        buffers_zeroed = buffers_zeroed and not any(buffer)
                    except Exception:
                        buffers_zeroed = False
            raw_retained = bool(buffers is not None and not buffers_zeroed)
            media_closed = native._close_media(media)
            ffmpeg_lease_verified = platform.ffmpeg_lease_verified()
            ffmpeg_lease_closed = native._close_platform_ffmpeg_lease(platform)
            mutex_released = mutex is not None and native._release_mutex(mutex)
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
            if (
                not cleanup_complete
                and failure is not native.NativeFailure.PRIVACY_STOP
            ):
                failure = native.NativeFailure.CLEANUP_INCOMPLETE
            if child is not None and pipe_closed and child_terminated and reader_stopped:
                try:
                    event_sink("CAPTURE_CLOSED", platform.monotonic_ns())
                except Exception:
                    if failure is not native.NativeFailure.PRIVACY_STOP:
                        failure = native.NativeFailure.CAPTURE_RUNTIME_EXCEPTION
    return _d1n2_capture_payload(
        native,
        state,
        failure=failure,
        raw_retained=raw_retained,
        mutex_released=mutex_released,
        child_terminated=child_terminated,
        pipe_closed=pipe_closed,
        reader_stopped=reader_stopped,
        media_closed=media_closed,
        ffmpeg_lease_verified=ffmpeg_lease_verified,
        ffmpeg_lease_closed=ffmpeg_lease_closed,
        ffmpeg_sha256=ffmpeg_sha256,
        ffmpeg_version_digest=ffmpeg_version_digest,
        ffmpeg_size_bytes=ffmpeg_size_bytes,
        ffmpeg_identity_digest=ffmpeg_identity_digest,
        fixed_argv_digest=fixed_argv_digest,
    )


def _d1n2_capture_worker_main() -> int:
    challenge = os.environ.get(_D1N2_WORKER_CHALLENGE_ENV, "")
    if not _is_lower_digest(challenge):
        return 2
    native = _load_native_primitives()
    if not _current_process_in_d1n2_job(native, challenge):
        return 3
    received = _receive_d1n2_worker_request(challenge)
    if received is None:
        return 4
    request, grant_id = received
    worker = _worker_lease(native)
    binding_matches = False
    try:
        binding = worker.binding
        attestation = request.prepared_attestation
        binding_matches = not (
            attestation is None
            or binding.sha256 != attestation.supervisor_sha256
            or binding.size_bytes != attestation.supervisor_size_bytes
            or binding.identity_digest != attestation.supervisor_identity_digest
        )
    finally:
        worker_closed = bool(worker.close())
    if not worker_closed:
        return 6
    if not binding_matches:
        return 5
    challenge_digest = _d1n2_challenge_digest(challenge)
    native._emit_worker_message(
        "AUTHORIZED", challenge_digest, {"grant_id": grant_id}
    )
    assert request.prepared_attestation is not None
    attestation = request.prepared_attestation
    platform = _D1N2WorkerPlatform(native, request.device_name)

    def event_sink(event: str, value: int) -> None:
        _emit_d1n2_phase(native, event, challenge_digest, value)

    candidate = _run_d1n2_capture(
        native,
        platform,
        native.MediaPipeTasksRuntime(),
        attestation,
        event_sink,
    )
    native._emit_worker_message(
        "RECEIPT",
        challenge_digest,
        candidate,
    )
    return 0


def _main() -> int:
    if sys.argv[1:] == [_D1N2_WORKER_ARGUMENT]:
        return _d1n2_capture_worker_main()
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
