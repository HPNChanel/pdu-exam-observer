"""Fixed D1-N2 RP2 verification and retained artifact leases.

Construction and import are inert. The parameterless production boundary derives
all paths from this installed module and performs no search or environment lookup.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Protocol

from pdu_exam_observer.m2_d1_n2_a0 import ApprovedRP2Triple
from pdu_exam_observer.m2_d1_n2_canonical import (
    AUTHORITY_REVISION,
    PREPARED_TTL_NS,
    PreparedBindingAttestation,
)
from pdu_exam_observer.m2_d1_n2_win32 import CtypesHandleOps, HandleInfo

_SCHEMA_RELATIVE_PATH = "docs/spec/M2_D1_N2_AUTHORITY_BINDING.schema.json"
_CANDIDATE_RELATIVE_PATH = "docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json"
_MAX_BOUND_ARTIFACT_BYTES = 64 * 1024 * 1024


class _LeaseOps(Protocol):
    def open_inspection(self, path: str) -> int | None: ...

    def info(self, handle: int) -> HandleInfo: ...

    def seek_start(self, handle: int) -> bool: ...

    def read(self, handle: int, limit: int) -> bytes | None: ...

    def close(self, handle: int) -> bool: ...


class _RetainedLease(Protocol):
    def validate(self) -> bool: ...

    def close(self) -> bool: ...


class RP2VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    CLEANUP_FAILED = "CLEANUP_FAILED"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _normalized_path(path: str | Path) -> str:
    value = os.path.abspath(os.fspath(path))
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return os.path.normcase(value)


def _valid_info(info: HandleInfo, expected_path: Path) -> bool:
    return (
        info.disk
        and not info.reparse
        and not info.directory
        and not info.delete_pending
        and info.links == 1
        and bool(info.identity)
        and 0 < info.size <= _MAX_BOUND_ARTIFACT_BYTES
        and _normalized_path(info.final_path) == _normalized_path(expected_path)
    )


@dataclass(slots=True)
class _BoundArtifactLease:
    ops: _LeaseOps
    handle: int
    path: Path
    identity: str
    size: int
    sha256: str
    _closed: bool = False

    def validate(self) -> bool:
        return self.read_verified() is not None

    def read_verified(self) -> bytes | None:
        if self._closed:
            return None
        before = self.ops.info(self.handle)
        if (
            not _valid_info(before, self.path)
            or before.identity != self.identity
            or before.size != self.size
            or not self.ops.seek_start(self.handle)
        ):
            return None
        payload = self.ops.read(self.handle, self.size + 1)
        after = self.ops.info(self.handle)
        if (
            payload is None
            or len(payload) != self.size
            or _sha256(payload) != self.sha256
            or not _valid_info(after, self.path)
            or after.identity != self.identity
            or after.size != self.size
        ):
            return None
        return payload

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        try:
            return self.ops.close(self.handle)
        except BaseException:
            return False


class PreparedLeaseBundle:
    """Retains every RP2 handle until terminalization or fail-closed cleanup."""

    def __init__(self, leases: tuple[_RetainedLease, ...]) -> None:
        self._leases = leases
        self._closed = False

    def validate(self) -> bool:
        return not self._closed and all(lease.validate() for lease in self._leases)

    def close(self) -> bool:
        if self._closed:
            return True
        self._closed = True
        clean = True
        for lease in reversed(self._leases):
            clean = lease.close() and clean
        return clean


@dataclass(frozen=True, slots=True)
class RP2VerificationResult:
    status: RP2VerificationStatus
    static_bindings_digest: str | None = None
    binding_schema_digest: str | None = None
    manifest_sha256: str | None = None
    supervisor_candidate_sha256: str | None = None
    supervisor_candidate_size_bytes: int | None = None
    pose_model_sha256: str | None = None
    pose_model_size_bytes: int | None = None
    face_model_sha256: str | None = None
    face_model_size_bytes: int | None = None
    lease_bundle: PreparedLeaseBundle | None = None


@dataclass(frozen=True, slots=True)
class CameraDeviceObservation:
    friendly_name: str
    present: bool
    status_ok: bool


@dataclass(frozen=True, slots=True)
class CameraEnumerationObservation:
    devices: tuple[CameraDeviceObservation, ...]
    lease: _RetainedLease


@dataclass(frozen=True, slots=True)
class ExecutableObservation:
    canonical_path_digest: str
    sha256: str
    size_bytes: int
    identity_digest: str
    version_output_digest: str | None
    lease: _RetainedLease


class _NativePreparationPort(Protocol):
    def attest_supervisor(self) -> ExecutableObservation | None: ...

    def enumerate_camera_class(self) -> CameraEnumerationObservation | None: ...

    def attest_ffmpeg(self) -> ExecutableObservation | None: ...

    def dependency_observation_digest(self) -> str | None: ...


class NoStreamAttestationStatus(StrEnum):
    ATTESTED = "ATTESTED"
    INVALID = "INVALID"
    CLEANUP_FAILED = "CLEANUP_FAILED"


@dataclass(frozen=True, slots=True)
class NoStreamAttestationOutcome:
    status: NoStreamAttestationStatus
    attestation: PreparedBindingAttestation | None = None
    lease_bundle: PreparedLeaseBundle | None = None
    retained_device_name: str | None = None


def _schema_type_matches(value: object, expected: str) -> bool:
    return {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
        "number": type(value) in {int, float},
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(expected, False)


def _validate_schema_value(value: object, rule: object) -> bool:
    if type(rule) is not dict:
        return False
    expected_type = rule.get("type")
    if type(expected_type) is str and not _schema_type_matches(value, expected_type):
        return False
    if "const" in rule and value != rule["const"]:
        return False
    if "minimum" in rule:
        minimum = rule["minimum"]
        if type(value) not in {int, float} or type(minimum) not in {int, float} or value < minimum:
            return False
    if "pattern" in rule:
        pattern = rule["pattern"]
        if (
            type(value) is not str
            or type(pattern) is not str
            or re.fullmatch(pattern, value) is None
        ):
            return False
    if type(value) is dict:
        properties = rule.get("properties", {})
        required = rule.get("required", [])
        if type(properties) is not dict or type(required) is not list:
            return False
        if any(type(name) is not str or name not in value for name in required):
            return False
        if rule.get("additionalProperties") is False and not set(value).issubset(properties):
            return False
        for name, child in value.items():
            if name in properties and not _validate_schema_value(child, properties[name]):
                return False
    if type(value) is list and "items" in rule:
        return all(_validate_schema_value(item, rule["items"]) for item in value)
    return True


def _safe_artifact_path(root: Path, relative: object) -> Path | None:
    if type(relative) is not str or "\\" in relative:
        return None
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return root.joinpath(*pure.parts)


class FixedRP2Verifier:
    """Injectable verifier whose production instance has one fixed repository root."""

    def __init__(self, root: Path, ops: _LeaseOps) -> None:
        self._root = Path(os.path.abspath(root))
        self._ops = ops

    def _open(
        self,
        path: Path,
        leases: list[_BoundArtifactLease],
        *,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> bytes | None:
        try:
            handle = self._ops.open_inspection(str(path))
            if handle is None:
                return None
            info = self._ops.info(handle)
            if not _valid_info(info, path):
                self._ops.close(handle)
                return None
            if expected_size is not None and info.size != expected_size:
                self._ops.close(handle)
                return None
            if not self._ops.seek_start(handle):
                self._ops.close(handle)
                return None
            payload = self._ops.read(handle, info.size + 1)
            after = self._ops.info(handle)
            if (
                payload is None
                or len(payload) != info.size
                or not _valid_info(after, path)
                or after.identity != info.identity
                or after.size != info.size
            ):
                self._ops.close(handle)
                return None
            digest = _sha256(payload)
            if expected_sha256 is not None and digest != expected_sha256:
                self._ops.close(handle)
                return None
            leases.append(
                _BoundArtifactLease(
                    self._ops,
                    handle,
                    path,
                    info.identity,
                    info.size,
                    digest,
                )
            )
            return payload
        except Exception:
            return None

    @staticmethod
    def _close_failed(leases: list[_BoundArtifactLease]) -> RP2VerificationResult:
        clean = True
        for lease in reversed(leases):
            clean = lease.close() and clean
        return RP2VerificationResult(
            RP2VerificationStatus.INVALID if clean else RP2VerificationStatus.CLEANUP_FAILED
        )

    def verify(self, expected: ApprovedRP2Triple) -> RP2VerificationResult:
        leases: list[_BoundArtifactLease] = []
        if type(expected) is not ApprovedRP2Triple or not expected.valid():
            return RP2VerificationResult(RP2VerificationStatus.INVALID)
        candidate_bytes = self._open(self._root / _CANDIDATE_RELATIVE_PATH, leases)
        schema_bytes = self._open(self._root / _SCHEMA_RELATIVE_PATH, leases)
        if candidate_bytes is None or schema_bytes is None:
            return self._close_failed(leases)
        if _sha256(candidate_bytes) != expected.candidate_exact_bytes_sha256:
            return self._close_failed(leases)
        try:
            candidate = json.loads(candidate_bytes.decode("utf-8"))
            schema = json.loads(schema_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._close_failed(leases)
        if (
            type(candidate) is not dict
            or type(schema) is not dict
            or candidate_bytes != _pretty_bytes(candidate)
            or schema_bytes != _pretty_bytes(schema)
            or not _validate_schema_value(candidate, schema)
        ):
            return self._close_failed(leases)

        static = candidate.get("static_bindings")
        static_digest = candidate.get("static_bindings_digest")
        if type(static) is not dict or type(static_digest) is not str:
            return self._close_failed(leases)
        if _sha256(_canonical_bytes(static)) != static_digest:
            return self._close_failed(leases)
        policy_digests = static.get("policy_digests")
        preimages = static.get("policy_preimages")
        if type(policy_digests) is not dict or type(preimages) is not dict:
            return self._close_failed(leases)
        schema_digest = _sha256(_canonical_bytes(schema))
        if (
            static_digest != expected.static_bindings_digest
            or schema_digest != expected.binding_schema_canonical_sha256
            or policy_digests.get("binding_schema_canonical_sha256") != schema_digest
        ):
            return self._close_failed(leases)
        for name, preimage in preimages.items():
            if policy_digests.get(name) != _sha256(_canonical_bytes(preimage)):
                return self._close_failed(leases)

        artifacts = static.get("artifacts")
        if type(artifacts) is not dict or type(artifacts.get("source_inventory")) is not dict:
            return self._close_failed(leases)
        inventory: list[object] = list(artifacts["source_inventory"].values())
        inventory.extend(
            artifacts.get(name)
            for name in ("uv_lock", "pose_landmarker_lite_task", "blaze_face_short_range_tflite")
        )
        seen_paths: set[str] = {
            _normalized_path(self._root / _CANDIDATE_RELATIVE_PATH),
            _normalized_path(self._root / _SCHEMA_RELATIVE_PATH),
        }
        seen_identities = {lease.identity for lease in leases}
        records: dict[str, dict[str, object]] = {}
        for raw_record in inventory:
            if type(raw_record) is not dict:
                return self._close_failed(leases)
            artifact_id = raw_record.get("artifact_id")
            size = raw_record.get("size_bytes")
            digest = raw_record.get("sha256")
            path = _safe_artifact_path(self._root, raw_record.get("path"))
            if (
                type(artifact_id) is not str
                or type(size) is not int
                or size <= 0
                or type(digest) is not str
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or path is None
                or _normalized_path(path) in seen_paths
            ):
                return self._close_failed(leases)
            payload = self._open(path, leases, expected_size=size, expected_sha256=digest)
            if payload is None or leases[-1].identity in seen_identities:
                return self._close_failed(leases)
            seen_paths.add(_normalized_path(path))
            seen_identities.add(leases[-1].identity)
            records[artifact_id] = raw_record

        pose = records.get("POSE_LANDMARKER_LITE_TASK")
        face = records.get("BLAZE_FACE_SHORT_RANGE_TFLITE")
        environment = candidate.get("environment_candidates")
        supervisor_candidate = (
            environment.get("supervisor_executable_candidate")
            if type(environment) is dict
            else None
        )
        supervisor_size = (
            supervisor_candidate.get("size_bytes")
            if type(supervisor_candidate) is dict
            else None
        )
        pose_size = pose.get("size_bytes") if pose is not None else None
        face_size = face.get("size_bytes") if face is not None else None
        if (
            pose is None
            or face is None
            or type(supervisor_candidate) is not dict
            or not _is_digest(supervisor_candidate.get("sha256"))
            or type(supervisor_size) is not int
            or type(pose_size) is not int
            or type(face_size) is not int
        ):
            return self._close_failed(leases)
        return RP2VerificationResult(
            status=RP2VerificationStatus.VERIFIED,
            static_bindings_digest=static_digest,
            binding_schema_digest=schema_digest,
            manifest_sha256=_sha256(candidate_bytes),
            supervisor_candidate_sha256=str(supervisor_candidate["sha256"]),
            supervisor_candidate_size_bytes=supervisor_size,
            pose_model_sha256=str(pose["sha256"]),
            pose_model_size_bytes=pose_size,
            face_model_sha256=str(face["sha256"]),
            face_model_size_bytes=face_size,
            lease_bundle=PreparedLeaseBundle(tuple(leases)),
        )


def _is_digest(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _valid_executable_observation(
    observation: ExecutableObservation,
    *,
    require_version: bool,
) -> bool:
    return (
        _is_digest(observation.canonical_path_digest)
        and _is_digest(observation.sha256)
        and type(observation.size_bytes) is int
        and observation.size_bytes > 0
        and _is_digest(observation.identity_digest)
        and (
            _is_digest(observation.version_output_digest)
            if require_version
            else observation.version_output_digest is None
        )
        and observation.lease.validate()
    )


def _safe_camera_name(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9 _().-]{1,128}", value) is not None


class D1N2NoStreamAttestor:
    """Builds one sanitized prepared attestation without opening a capture input."""

    def __init__(
        self,
        verify_rp2: Callable[[ApprovedRP2Triple], RP2VerificationResult],
        native: _NativePreparationPort,
        *,
        entropy: Callable[[int], bytes] = secrets.token_bytes,
        unix_clock_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        self._verify_rp2 = verify_rp2
        self._native = native
        self._entropy = entropy
        self._unix_clock_ns = unix_clock_ns

    @staticmethod
    def _failed(
        retained: list[_RetainedLease],
        status: NoStreamAttestationStatus = NoStreamAttestationStatus.INVALID,
    ) -> NoStreamAttestationOutcome:
        clean = True
        for lease in reversed(retained):
            try:
                clean = lease.close() and clean
            except BaseException:
                clean = False
        if not clean:
            status = NoStreamAttestationStatus.CLEANUP_FAILED
        return NoStreamAttestationOutcome(status)

    def attest(self, expected: ApprovedRP2Triple) -> NoStreamAttestationOutcome:
        retained: list[_RetainedLease] = []
        try:
            if type(expected) is not ApprovedRP2Triple or not expected.valid():
                return NoStreamAttestationOutcome(NoStreamAttestationStatus.INVALID)
            rp2 = self._verify_rp2(expected)
            if (
                rp2.status is not RP2VerificationStatus.VERIFIED
                or rp2.lease_bundle is None
            ):
                return NoStreamAttestationOutcome(
                    NoStreamAttestationStatus.CLEANUP_FAILED
                    if rp2.status is RP2VerificationStatus.CLEANUP_FAILED
                    else NoStreamAttestationStatus.INVALID
                )
            retained.append(rp2.lease_bundle)

            supervisor = self._native.attest_supervisor()
            if supervisor is None:
                return self._failed(retained)
            retained.append(supervisor.lease)
            if (
                not _valid_executable_observation(supervisor, require_version=False)
                or supervisor.sha256 != rp2.supervisor_candidate_sha256
                or supervisor.size_bytes != rp2.supervisor_candidate_size_bytes
            ):
                return self._failed(retained)

            camera_enumeration = self._native.enumerate_camera_class()
            if camera_enumeration is None:
                return self._failed(retained)
            retained.append(camera_enumeration.lease)
            cameras = camera_enumeration.devices
            if (
                not camera_enumeration.lease.validate()
                or type(cameras) is not tuple
                or len(cameras) != 1
                or type(cameras[0]) is not CameraDeviceObservation
                or not cameras[0].present
                or not cameras[0].status_ok
                or not _safe_camera_name(cameras[0].friendly_name)
            ):
                return self._failed(retained)

            ffmpeg = self._native.attest_ffmpeg()
            if ffmpeg is None:
                return self._failed(retained)
            retained.append(ffmpeg.lease)
            if not _valid_executable_observation(ffmpeg, require_version=True):
                return self._failed(retained)

            dependency_digest = self._native.dependency_observation_digest()
            if not _is_digest(dependency_digest):
                return self._failed(retained)
            nonce = self._entropy(32)
            issued = self._unix_clock_ns()
            if type(nonce) is not bytes or len(nonce) != 32 or type(issued) is not int:
                return self._failed(retained)
            required_rp2_values = (
                rp2.static_bindings_digest,
                rp2.binding_schema_digest,
                rp2.manifest_sha256,
                rp2.pose_model_sha256,
                rp2.pose_model_size_bytes,
                rp2.face_model_sha256,
                rp2.face_model_size_bytes,
            )
            if (
                not all(_is_digest(value) for value in required_rp2_values[:4])
                or type(rp2.pose_model_size_bytes) is not int
                or not _is_digest(rp2.face_model_sha256)
                or type(rp2.face_model_size_bytes) is not int
            ):
                return self._failed(retained)
            opaque_device_token = _sha256(
                b"d1-n2-device-token-v1\0"
                + nonce
                + cameras[0].friendly_name.encode("ascii")
            )
            attestation = PreparedBindingAttestation(
                authority_revision=AUTHORITY_REVISION,
                schema_version=3,
                static_bindings_digest=str(rp2.static_bindings_digest),
                binding_schema_digest=str(rp2.binding_schema_digest),
                manifest_sha256=str(rp2.manifest_sha256),
                camera_count=1,
                camera_status="PRESENT_OK",
                opaque_device_token=opaque_device_token,
                supervisor_path_digest=supervisor.canonical_path_digest,
                supervisor_sha256=supervisor.sha256,
                supervisor_size_bytes=supervisor.size_bytes,
                supervisor_identity_digest=supervisor.identity_digest,
                ffmpeg_path_digest=ffmpeg.canonical_path_digest,
                ffmpeg_sha256=ffmpeg.sha256,
                ffmpeg_size_bytes=ffmpeg.size_bytes,
                ffmpeg_identity_digest=ffmpeg.identity_digest,
                ffmpeg_version_digest=str(ffmpeg.version_output_digest),
                dependency_observation_digest=str(dependency_digest),
                pose_model_sha256=str(rp2.pose_model_sha256),
                pose_model_size_bytes=int(rp2.pose_model_size_bytes),
                face_model_sha256=str(rp2.face_model_sha256),
                face_model_size_bytes=int(rp2.face_model_size_bytes),
                authorization_nonce_digest=_sha256(nonce),
                issued_unix_ns=issued,
                expires_unix_ns=issued + PREPARED_TTL_NS,
            )
            if not attestation.valid():
                return self._failed(retained)
            return NoStreamAttestationOutcome(
                NoStreamAttestationStatus.ATTESTED,
                attestation,
                PreparedLeaseBundle(tuple(retained)),
                cameras[0].friendly_name,
            )
        except Exception:
            return self._failed(retained)

    def revalidate_device(self, expected_name: str) -> bool:
        """Re-enumerate only Camera-class identity and always close the new lease."""

        enumeration: CameraEnumerationObservation | None = None
        valid = False
        try:
            enumeration = self._native.enumerate_camera_class()
            if enumeration is None or not enumeration.lease.validate():
                return False
            devices = enumeration.devices
            valid = (
                _safe_camera_name(expected_name)
                and type(devices) is tuple
                and len(devices) == 1
                and type(devices[0]) is CameraDeviceObservation
                and devices[0].friendly_name == expected_name
                and devices[0].present
                and devices[0].status_ok
            )
        except Exception:
            valid = False
        finally:
            if enumeration is not None:
                try:
                    valid = enumeration.lease.close() and valid
                except BaseException:
                    valid = False
        return valid


def verify_fixed_rp2(expected: ApprovedRP2Triple) -> RP2VerificationResult:
    """Verify the one installed RP2 path; no cwd, PATH, env, or caller input."""

    root = Path(__file__).absolute().parents[2]
    return FixedRP2Verifier(root, CtypesHandleOps()).verify(expected)
