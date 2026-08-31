"""Injectable schema-v3 authority lifecycle with no native execution.

The production adapter is intentionally separate.  This module owns only the
canonical state machine and protocols needed to compose the approved H1/H2
Win32 primitives without accepting caller-controlled paths or names.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, cast

from pdu_exam_observer.m2_d1_n2_a0 import ApprovedRP2Triple
from pdu_exam_observer.m2_d1_n2_evidence import (
    RetainedLeaseCleanup,
    VerifiedTerminalEvidence,
    verify_terminal_evidence,
)

WORKER_GRANT_TTL_NS = 300_000_000_000
PREPARED_TTL_NS = 900_000_000_000
_MAX_SIGNED_NS = (1 << 63) - 1
AUTHORITY_REVISION = "d1-n2-authority-v1"


class CanonicalLifecycleState(StrEnum):
    UNKNOWN_NONLAUNCHABLE = "UNKNOWN_NONLAUNCHABLE"
    ABSENT = "ABSENT"
    PENDING = "PENDING"
    PRESENT_INVALID = "PRESENT_INVALID"
    PREPARED = "PREPARED"
    PREPARED_NONLAUNCHABLE = "PREPARED_NONLAUNCHABLE"
    STALE_PREPARED_NONLAUNCHABLE = "STALE_PREPARED_NONLAUNCHABLE"
    CONSUMED_NO_GRANT = "CONSUMED_NO_GRANT"
    ISSUED = "ISSUED"
    REVOKED_TERMINAL_PENDING = "REVOKED_TERMINAL_PENDING"
    TERMINAL = "TERMINAL"
    TERMINAL_DURABILITY_UNVERIFIED = "TERMINAL_DURABILITY_UNVERIFIED"


class PersistenceOutcome(StrEnum):
    OK = "OK"
    INPUT_INVALID = "INPUT_INVALID"
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE"
    OWNER_ABANDONED = "OWNER_ABANDONED"
    OWNER_FAILED = "OWNER_FAILED"
    LEASE_DRIFT = "LEASE_DRIFT"
    ATTESTATION_FAILED = "ATTESTATION_FAILED"
    CREATE_FAILED = "CREATE_FAILED"
    CAS_MISMATCH = "CAS_MISMATCH"
    READBACK_FAILED = "READBACK_FAILED"
    CLOSE_FAILED = "CLOSE_FAILED"
    DURABILITY_FAILED = "DURABILITY_FAILED"
    CLEANUP_FAILED = "CLEANUP_FAILED"
    GRANT_ENTROPY_FAILED = "GRANT_ENTROPY_FAILED"
    GRANT_NOT_AUTHORIZED = "GRANT_NOT_AUTHORIZED"
    TERMINAL_NOT_AUTHORIZED = "TERMINAL_NOT_AUTHORIZED"
    TERMINAL_ALREADY_PRESENT = "TERMINAL_ALREADY_PRESENT"


class AuthorityLeaf(StrEnum):
    PREPARED = "prepared.v3.json"
    GRANT = "worker-grant.v2.json"
    TERMINAL = "terminal.v3.json"


class OperationKind(StrEnum):
    INSPECT = "INSPECT"
    PREPARE = "PREPARE"
    CONSUME = "CONSUME"
    ISSUE_GRANT = "ISSUE_GRANT"
    REVOKE_GRANT = "REVOKE_GRANT"
    TERMINALIZE = "TERMINALIZE"


class OwnerStatus(StrEnum):
    ACQUIRED = "ACQUIRED"
    ABANDONED_INSPECTION_ONLY = "ABANDONED_INSPECTION_ONLY"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    DRIFT = "DRIFT"
    ERROR = "ERROR"


class DurabilityStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    ERROR = "ERROR"


class StepStatus(StrEnum):
    CLEAN = "CLEAN"
    FAILED = "FAILED"
    NOT_HELD = "NOT_HELD"


class WriteDisposition(StrEnum):
    ZERO_WRITE = "ZERO_WRITE"
    PRESENT_VALID = "PRESENT_VALID"
    PRESENT_INVALID = "PRESENT_INVALID"
    PRESENT_UNKNOWN = "PRESENT_UNKNOWN"


class GrantDisposition(StrEnum):
    NOT_ISSUED = "NOT_ISSUED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class CanonicalInspection:
    state: CanonicalLifecycleState
    record: bytes | None
    durability: DurabilityStatus = DurabilityStatus.UNVERIFIED


@dataclass(frozen=True, slots=True)
class WriteResult:
    outcome: PersistenceOutcome
    disposition: WriteDisposition
    observed_bytes: bytes | None = None


@dataclass(frozen=True, slots=True)
class CleanupReport:
    lease_close: StepStatus
    mutex_release: StepStatus
    mutex_close: StepStatus


class MutationSession(Protocol):
    @property
    def write_permitted(self) -> bool: ...

    def validate_before(self) -> ValidationStatus: ...

    def validate_after(self) -> ValidationStatus: ...

    def parent_durable(self) -> DurabilityStatus: ...

    def attest_a0_before_pending(self) -> ApprovedRP2Triple | None: ...

    def attest_pending(self) -> PreparedBindingAttestation | None: ...

    def close_leases(self) -> StepStatus: ...

    def release_mutex(self) -> StepStatus: ...

    def close_mutex(self) -> StepStatus: ...


@dataclass(frozen=True, slots=True)
class BeginResult:
    owner: OwnerStatus
    session: MutationSession | None


class MutationGuardFactory(Protocol):
    def begin(self, operation: OperationKind) -> BeginResult: ...


class CanonicalAuthorityPersistence(Protocol):
    def inspect(self, session: MutationSession, leaf: AuthorityLeaf) -> CanonicalInspection: ...

    def create_exact(
        self, session: MutationSession, leaf: AuthorityLeaf, record: bytes
    ) -> WriteResult: ...

    def cas_exact(
        self,
        session: MutationSession,
        leaf: AuthorityLeaf,
        prior: bytes,
        record: bytes,
    ) -> WriteResult: ...


class CanonicalCleanupFailure(RuntimeError):
    """Sanitized cleanup failure that retains in-memory exception objects only."""

    def __init__(self, report: CleanupReport, causes: tuple[BaseException, ...] = ()) -> None:
        super().__init__("canonical authority cleanup failed")
        self.report = report
        self.causes = causes


@dataclass(frozen=True, slots=True)
class PreparedBindingAttestation:
    authority_revision: str
    schema_version: int
    static_bindings_digest: str
    binding_schema_digest: str
    manifest_sha256: str
    camera_count: int
    camera_status: str
    opaque_device_token: str
    supervisor_path_digest: str
    supervisor_sha256: str
    supervisor_size_bytes: int
    supervisor_identity_digest: str
    ffmpeg_path_digest: str
    ffmpeg_sha256: str
    ffmpeg_size_bytes: int
    ffmpeg_identity_digest: str
    ffmpeg_version_digest: str
    dependency_observation_digest: str
    pose_model_sha256: str
    pose_model_size_bytes: int
    face_model_sha256: str
    face_model_size_bytes: int
    authorization_nonce_digest: str
    issued_unix_ns: int
    expires_unix_ns: int

    def valid(self) -> bool:
        digests = (
            self.static_bindings_digest,
            self.binding_schema_digest,
            self.manifest_sha256,
            self.opaque_device_token,
            self.supervisor_path_digest,
            self.supervisor_sha256,
            self.supervisor_identity_digest,
            self.ffmpeg_path_digest,
            self.ffmpeg_sha256,
            self.ffmpeg_identity_digest,
            self.ffmpeg_version_digest,
            self.dependency_observation_digest,
            self.pose_model_sha256,
            self.face_model_sha256,
            self.authorization_nonce_digest,
        )
        sizes = (
            self.supervisor_size_bytes,
            self.ffmpeg_size_bytes,
            self.pose_model_size_bytes,
            self.face_model_size_bytes,
        )
        return (
            type(self.authority_revision) is str
            and self.authority_revision == AUTHORITY_REVISION
            and type(self.schema_version) is int
            and self.schema_version == 3
            and all(_is_digest(value) for value in digests)
            and type(self.camera_count) is int
            and self.camera_count == 1
            and type(self.camera_status) is str
            and self.camera_status == "PRESENT_OK"
            and all(type(value) is int and value > 0 for value in sizes)
            and type(self.issued_unix_ns) is int
            and type(self.expires_unix_ns) is int
            and 0 <= self.issued_unix_ns <= _MAX_SIGNED_NS - PREPARED_TTL_NS
            and self.expires_unix_ns - self.issued_unix_ns == PREPARED_TTL_NS
        )

    def record_fields(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class WorkerGrantBindingAttestation:
    prepared_authority_digest: str
    worker_sha256: str
    worker_size_bytes: int
    worker_identity_digest: str
    worker_argv_digest: str
    worker_job_policy_digest: str
    challenge_digest: str
    job_name_digest: str
    duration_seconds: int
    video_only: bool
    retry: bool

    def valid(self) -> bool:
        return (
            all(
                _is_digest(value)
                for value in (
                    self.prepared_authority_digest,
                    self.worker_sha256,
                    self.worker_identity_digest,
                    self.worker_argv_digest,
                    self.worker_job_policy_digest,
                    self.challenge_digest,
                    self.job_name_digest,
                )
            )
            and type(self.worker_size_bytes) is int
            and self.worker_size_bytes > 0
            and self.duration_seconds == 60
            and self.video_only is True
            and self.retry is False
        )

    def record_fields(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class TerminalBindingAttestation:
    receipt_json: str
    receipt_digest: str
    failure_ledger_json: str
    failure_ledger_digest: str
    retained_a0_clean: bool
    retained_rp2_clean: bool
    retained_preparation_clean: bool
    native_side_effect_count: int

    def valid(self) -> bool:
        evidence = VerifiedTerminalEvidence(
            receipt_json=self.receipt_json,
            receipt_digest=self.receipt_digest,
            failure_ledger_json=self.failure_ledger_json,
            failure_ledger_digest=self.failure_ledger_digest,
            retained_cleanup=RetainedLeaseCleanup(
                self.retained_a0_clean,
                self.retained_rp2_clean,
                self.retained_preparation_clean,
            ),
        )
        return (
            verify_terminal_evidence(evidence)
            and type(self.native_side_effect_count) is int
            and self.native_side_effect_count in {0, 1}
        )

    @classmethod
    def from_evidence(
        cls,
        evidence: VerifiedTerminalEvidence,
        native_side_effect_count: int,
    ) -> TerminalBindingAttestation:
        cleanup = evidence.retained_cleanup
        return cls(
            evidence.receipt_json,
            evidence.receipt_digest,
            evidence.failure_ledger_json,
            evidence.failure_ledger_digest,
            cleanup.a0_clean,
            cleanup.rp2_clean,
            cleanup.preparation_clean,
            native_side_effect_count,
        )

    def record_fields(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def _terminal_receipt_matches_lifecycle(
    terminal_fields: dict[str, object],
    consumed_fields: dict[str, object],
    revoked_grant_record: bytes | None,
) -> bool:
    receipt_json = terminal_fields.get("receipt_json")
    if type(receipt_json) is not str:
        return False
    try:
        receipt = json.loads(receipt_json)
    except (TypeError, json.JSONDecodeError):
        return False
    projections = {
        "authority_digest": "prepared_digest",
        "static_bindings_digest": "static_bindings_digest",
        "runtime_digest": "dependency_observation_digest",
        "pose_model_sha256": "pose_model_sha256",
        "face_model_sha256": "face_model_sha256",
    }
    if type(receipt) is not dict or any(
        receipt.get(receipt_key) != consumed_fields.get(consumed_key)
        for receipt_key, consumed_key in projections.items()
    ):
        return False
    if revoked_grant_record is None:
        return True
    revoked = _validated_record(revoked_grant_record, "D1N2/GRANT_REVOKED/v1")
    return (
        revoked is not None
        and receipt.get("grant_record_digest") == _sha256_bytes(revoked_grant_record)
        and receipt.get("challenge_digest") == revoked.get("challenge_digest")
        and receipt.get("job_name_digest") == revoked.get("job_name_digest")
    )


class ProcessEpochV2:
    """Raw epoch capability is retained privately by one live supervisor."""

    __slots__ = ("__raw", "digest")

    def __init__(self, entropy: Callable[[int], bytes] = secrets.token_bytes) -> None:
        raw = entropy(32)
        if type(raw) is not bytes or len(raw) != 32:
            raise ValueError("process epoch entropy must be exactly 32 bytes")
        self.__raw = raw
        self.digest = hashlib.sha256(raw).hexdigest()

    def proves(self, persisted_digest: str) -> bool:
        actual = hashlib.sha256(self.__raw).hexdigest()
        return hmac.compare_digest(actual, persisted_digest)


@dataclass(frozen=True, slots=True)
class CanonicalGrantInspection:
    digest: str
    issued_monotonic_ns: int
    expires_monotonic_ns: int
    used: bool


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _record(domain: str, values: dict[str, object]) -> bytes:
    return _canonical_bytes(
        {
            "domain": domain,
            "schema_version": 3,
            **values,
        }
    )


def _decode_record(value: bytes | None) -> dict[str, object] | None:
    if value is None:
        return None
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict) or _canonical_bytes(decoded) != value:
        return None
    if any(not isinstance(key, str) for key in decoded):
        return None
    return {str(key): item for key, item in decoded.items()}


_RECORD_KEYS = {
    "D1N2/PENDING/v1": {
        "a0_approval_digest",
        "approval_id_digest",
        "binding_schema_canonical_sha256",
        "candidate_exact_bytes_sha256",
        "domain",
        "epoch_digest",
        "expires_unix_ns",
        "issued_unix_ns",
        "schema_version",
        "state",
        "static_bindings_digest",
    },
    "D1N2/PREPARED/v1": set(PreparedBindingAttestation.__dataclass_fields__) | {
        "domain",
        "epoch_digest",
        "pending_digest",
        "state",
    },
    "D1N2/CONSUMED/v1": {
        "dependency_observation_digest",
        "domain",
        "epoch_digest",
        "face_model_sha256",
        "pose_model_sha256",
        "prepared_digest",
        "schema_version",
        "state",
        "static_bindings_digest",
    },
    "D1N2/GRANT_ISSUED/v1": set(WorkerGrantBindingAttestation.__dataclass_fields__) | {
        "consumed_digest",
        "domain",
        "epoch_digest",
        "expires_monotonic_ns",
        "grant_digest",
        "grant_size",
        "issued_monotonic_ns",
        "schema_version",
        "state",
    },
    "D1N2/GRANT_REVOKED/v1": {
        "challenge_digest",
        "consumed_digest",
        "domain",
        "epoch_digest",
        "expires_monotonic_ns",
        "grant_digest",
        "issued_monotonic_ns",
        "issued_record_digest",
        "job_name_digest",
        "schema_version",
        "state",
    },
    "D1N2/TERMINAL/v1": set(TerminalBindingAttestation.__dataclass_fields__) | {
        "consumed_digest",
        "domain",
        "durability_policy",
        "grant_disposition",
        "grant_record_digest",
        "schema_version",
        "state",
    },
}

_RECORD_STATES = {
    "D1N2/PENDING/v1": "PENDING",
    "D1N2/PREPARED/v1": "PREPARED",
    "D1N2/CONSUMED/v1": "CONSUMED",
    "D1N2/GRANT_ISSUED/v1": "ISSUED",
    "D1N2/GRANT_REVOKED/v1": "REVOKED",
    "D1N2/TERMINAL/v1": "TERMINAL",
}


def _validated_record(
    value: bytes | None, expected_domain: str | None = None
) -> dict[str, object] | None:
    decoded = _decode_record(value)
    if decoded is None:
        return None
    domain = decoded.get("domain")
    if not isinstance(domain, str) or domain not in _RECORD_KEYS:
        return None
    if expected_domain is not None and domain != expected_domain:
        return None
    if set(decoded) != _RECORD_KEYS[domain]:
        return None
    if type(decoded.get("schema_version")) is not int or decoded["schema_version"] != 3:
        return None
    if decoded.get("state") != _RECORD_STATES[domain]:
        return None
    for key, item in decoded.items():
        if (
            key.endswith("_digest")
            and key != "grant_record_digest"
            and not _is_digest(item)
        ):
            return None
    if domain == "D1N2/TERMINAL/v1":
        if decoded.get("durability_policy") != "REVERIFY_PARENT_ON_INSPECTION":
            return None
        disposition = decoded.get("grant_disposition")
        grant_digest = decoded.get("grant_record_digest")
        if disposition == GrantDisposition.NOT_ISSUED.value:
            if grant_digest is not None:
                return None
        elif disposition == GrantDisposition.REVOKED.value:
            if not _is_digest(grant_digest):
                return None
        else:
            return None
        try:
            terminal_attestation = TerminalBindingAttestation(
                **cast(Any, {
                    name: decoded[name]
                    for name in TerminalBindingAttestation.__dataclass_fields__
                })
            )
        except (KeyError, TypeError):
            return None
        if not terminal_attestation.valid():
            return None
    if domain == "D1N2/PENDING/v1":
        try:
            approved = ApprovedRP2Triple(
                static_bindings_digest=str(decoded["static_bindings_digest"]),
                binding_schema_canonical_sha256=str(
                    decoded["binding_schema_canonical_sha256"]
                ),
                candidate_exact_bytes_sha256=str(
                    decoded["candidate_exact_bytes_sha256"]
                ),
                a0_approval_digest=str(decoded["a0_approval_digest"]),
                approval_id_digest=str(decoded["approval_id_digest"]),
                issued_unix_ns=cast(int, decoded["issued_unix_ns"]),
                expires_unix_ns=cast(int, decoded["expires_unix_ns"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if not approved.valid():
            return None
    if domain == "D1N2/GRANT_ISSUED/v1":
        try:
            worker_attestation = WorkerGrantBindingAttestation(
                **cast(Any, {
                    name: decoded[name]
                    for name in WorkerGrantBindingAttestation.__dataclass_fields__
                })
            )
        except (KeyError, TypeError):
            return None
        if not worker_attestation.valid():
            return None
    if domain == "D1N2/PREPARED/v1":
        try:
            attestation = PreparedBindingAttestation(
                **cast(Any, {
                    name: decoded[name]
                    for name in PreparedBindingAttestation.__dataclass_fields__
                })
            )
        except (KeyError, TypeError):
            return None
        if not attestation.valid():
            return None
    if domain in {"D1N2/GRANT_ISSUED/v1", "D1N2/GRANT_REVOKED/v1"}:
        issued = decoded.get("issued_monotonic_ns")
        expires = decoded.get("expires_monotonic_ns")
        if (
            type(issued) is not int
            or type(expires) is not int
            or issued < 0
            or expires > _MAX_SIGNED_NS
            or expires - issued != WORKER_GRANT_TTL_NS
        ):
            return None
        if domain == "D1N2/GRANT_ISSUED/v1" and decoded.get("grant_size") != 32:
            return None
    return decoded


def _domain(value: bytes | None) -> str | None:
    decoded = _validated_record(value)
    return str(decoded["domain"]) if decoded is not None else None


def classify_canonical_leaf_record(
    leaf: AuthorityLeaf, value: bytes
) -> CanonicalLifecycleState | None:
    """Validate one exact canonical record and its fixed leaf/domain pairing."""

    decoded = _validated_record(value)
    if decoded is None:
        return None
    domain = decoded["domain"]
    allowed = {
        AuthorityLeaf.PREPARED: {
            "D1N2/PENDING/v1": CanonicalLifecycleState.PENDING,
            "D1N2/PREPARED/v1": CanonicalLifecycleState.PREPARED,
            "D1N2/CONSUMED/v1": CanonicalLifecycleState.CONSUMED_NO_GRANT,
        },
        AuthorityLeaf.GRANT: {
            "D1N2/GRANT_ISSUED/v1": CanonicalLifecycleState.ISSUED,
            "D1N2/GRANT_REVOKED/v1": (
                CanonicalLifecycleState.REVOKED_TERMINAL_PENDING
            ),
        },
        AuthorityLeaf.TERMINAL: {
            "D1N2/TERMINAL/v1": CanonicalLifecycleState.TERMINAL,
        },
    }
    return allowed[leaf].get(str(domain))


def _cleanup_is_clean(report: CleanupReport) -> bool:
    return all(
        status is StepStatus.CLEAN
        for status in (report.lease_close, report.mutex_release, report.mutex_close)
    )


class CanonicalInjectableAuthorityLifecycle:
    """Fake-first authority lifecycle; it performs no native or path operation."""

    def __init__(
        self,
        persistence: CanonicalAuthorityPersistence,
        guard_factory: MutationGuardFactory,
        *,
        entropy: Callable[[int], bytes] = secrets.token_bytes,
        grant_entropy: Callable[[int], bytes] = secrets.token_bytes,
        clock_ns: Callable[[], int] = time.monotonic_ns,
        unix_clock_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        self._persistence = persistence
        self._guard_factory = guard_factory
        self._epoch = ProcessEpochV2(entropy)
        self._grant_entropy = grant_entropy
        self._clock_ns = clock_ns
        self._unix_clock_ns = unix_clock_ns
        self.state = CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE
        self._pending: bytes | None = None
        self._prepared: bytes | None = None
        self._consumed: bytes | None = None
        self._live_prepared = False
        self._live_consumed = False
        self._grant_raw: bytes | None = None
        self._grant_handed_off = False
        self._grant: CanonicalGrantInspection | None = None
        self._grant_record: bytes | None = None
        self._approved_rp2: ApprovedRP2Triple | None = None
        self._load_existing_state()

    @property
    def epoch_digest(self) -> str:
        return self._epoch.digest

    @property
    def prepared_record(self) -> bytes | None:
        return self._prepared

    @property
    def grant_record(self) -> bytes | None:
        return self._grant_record

    def _collect_cleanup(
        self, session: MutationSession
    ) -> tuple[CleanupReport, tuple[BaseException, ...]]:
        statuses: list[StepStatus] = []
        causes: list[BaseException] = []
        for operation in (
            session.close_leases,
            session.release_mutex,
            session.close_mutex,
        ):
            try:
                statuses.append(operation())
            except BaseException as error:
                statuses.append(StepStatus.FAILED)
                causes.append(error)
        return CleanupReport(*statuses), tuple(causes)

    def _finish(
        self, session: MutationSession, primary: BaseException | None = None
    ) -> CleanupReport:
        report, causes = self._collect_cleanup(session)
        clean = _cleanup_is_clean(report)
        if primary is not None:
            failures: list[BaseException] = [primary, *causes]
            if not clean and not causes:
                failures.append(CanonicalCleanupFailure(report))
            if len(failures) > 1:
                raise BaseExceptionGroup("authority operation and cleanup failed", failures)
            raise primary
        if causes:
            raise CanonicalCleanupFailure(report, causes)
        return report

    def _begin_mutation(
        self, operation: OperationKind
    ) -> tuple[PersistenceOutcome, MutationSession | None]:
        begun = self._guard_factory.begin(operation)
        if begun.owner is not OwnerStatus.ACQUIRED or begun.session is None:
            outcome = {
                OwnerStatus.ABANDONED_INSPECTION_ONLY: PersistenceOutcome.OWNER_ABANDONED,
                OwnerStatus.UNAVAILABLE: PersistenceOutcome.OWNER_UNAVAILABLE,
                OwnerStatus.ERROR: PersistenceOutcome.OWNER_FAILED,
                OwnerStatus.ACQUIRED: PersistenceOutcome.OWNER_FAILED,
            }[begun.owner]
            if begun.session is not None:
                report = self._finish(begun.session)
                if not _cleanup_is_clean(report):
                    return PersistenceOutcome.CLEANUP_FAILED, None
            return outcome, None
        session = begun.session
        if not session.write_permitted:
            report = self._finish(session)
            return (
                PersistenceOutcome.OWNER_FAILED
                if _cleanup_is_clean(report)
                else PersistenceOutcome.CLEANUP_FAILED,
                None,
            )
        try:
            validation = session.validate_before()
        except BaseException as error:
            self._finish(session, error)
            raise AssertionError("unreachable") from error
        if validation is not ValidationStatus.VALID:
            report = self._finish(session)
            return (
                PersistenceOutcome.LEASE_DRIFT
                if _cleanup_is_clean(report)
                else PersistenceOutcome.CLEANUP_FAILED,
                None,
            )
        return PersistenceOutcome.OK, session

    def _inspect_with_session(
        self, session: MutationSession, leaf: AuthorityLeaf
    ) -> CanonicalInspection:
        return self._persistence.inspect(session, leaf)

    def _load_existing_state(self) -> None:
        begun = self._guard_factory.begin(OperationKind.INSPECT)
        session = begun.session
        if session is None:
            return
        inspection_allowed = begun.owner in {
            OwnerStatus.ACQUIRED,
            OwnerStatus.ABANDONED_INSPECTION_ONLY,
        }
        validation = ValidationStatus.ERROR
        prepared: CanonicalInspection | None = None
        grant: CanonicalInspection | None = None
        terminal: CanonicalInspection | None = None
        try:
            if inspection_allowed:
                validation = session.validate_before()
                if validation is ValidationStatus.VALID:
                    prepared = self._inspect_with_session(session, AuthorityLeaf.PREPARED)
                    grant = self._inspect_with_session(session, AuthorityLeaf.GRANT)
                    terminal = self._inspect_with_session(session, AuthorityLeaf.TERMINAL)
        except BaseException as error:
            self._finish(session, error)
            raise AssertionError("unreachable") from error
        report = self._finish(session)
        if (
            not _cleanup_is_clean(report)
            or validation is not ValidationStatus.VALID
            or prepared is None
            or grant is None
            or terminal is None
        ):
            return
        for inspection in (prepared, grant, terminal):
            if inspection.record is None and inspection.state is not CanonicalLifecycleState.ABSENT:
                self.state = (
                    CanonicalLifecycleState.PRESENT_INVALID
                    if inspection.state is CanonicalLifecycleState.PRESENT_INVALID
                    else CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE
                )
                return
        terminal_values = _validated_record(terminal.record)
        prepared_values = _validated_record(prepared.record)
        grant_values = _validated_record(grant.record)
        if terminal.record is not None:
            if (
                terminal_values is None
                or terminal_values.get("domain") != "D1N2/TERMINAL/v1"
                or prepared_values is None
                or prepared_values.get("domain") != "D1N2/CONSUMED/v1"
                or terminal_values.get("consumed_digest")
                != _sha256_bytes(prepared.record or b"")
            ):
                self.state = CanonicalLifecycleState.PRESENT_INVALID
                return
            disposition = terminal_values["grant_disposition"]
            if disposition == GrantDisposition.NOT_ISSUED.value:
                valid_terminal = grant.record is None
                revoked_record = None
            else:
                revoked_record = grant.record
                valid_terminal = (
                    grant_values is not None
                    and grant_values.get("domain") == "D1N2/GRANT_REVOKED/v1"
                    and terminal_values.get("grant_record_digest")
                    == _sha256_bytes(grant.record or b"")
                    and grant_values.get("consumed_digest")
                    == _sha256_bytes(prepared.record or b"")
                    and grant_values.get("epoch_digest")
                    == prepared_values.get("epoch_digest")
                )
            valid_terminal = valid_terminal and _terminal_receipt_matches_lifecycle(
                terminal_values,
                prepared_values,
                revoked_record,
            )
            if not valid_terminal:
                self.state = CanonicalLifecycleState.PRESENT_INVALID
            elif terminal.durability is DurabilityStatus.VERIFIED:
                self.state = CanonicalLifecycleState.TERMINAL
            else:
                self.state = CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED
            return
        prepared_domain = (
            str(prepared_values["domain"]) if prepared_values is not None else None
        )
        grant_domain = str(grant_values["domain"]) if grant_values is not None else None
        if prepared.record is None:
            self.state = (
                CanonicalLifecycleState.ABSENT
                if grant.record is None
                else CanonicalLifecycleState.PRESENT_INVALID
            )
            return
        if prepared_domain == "D1N2/PENDING/v1":
            self._pending = prepared.record
            self.state = CanonicalLifecycleState.PENDING
            return
        if prepared_domain == "D1N2/PREPARED/v1":
            self._prepared = prepared.record
            self.state = CanonicalLifecycleState.STALE_PREPARED_NONLAUNCHABLE
            return
        if prepared_domain != "D1N2/CONSUMED/v1":
            self.state = CanonicalLifecycleState.PRESENT_INVALID
            return
        self._consumed = prepared.record
        if grant.record is None:
            self.state = CanonicalLifecycleState.CONSUMED_NO_GRANT
            return
        if grant_values is None:
            self.state = CanonicalLifecycleState.PRESENT_INVALID
            return
        digest = grant_values.get("grant_digest")
        issued = grant_values.get("issued_monotonic_ns")
        expires = grant_values.get("expires_monotonic_ns")
        consumed_digest = _sha256_bytes(prepared.record)
        consumed_epoch = prepared_values.get("epoch_digest") if prepared_values else None
        if (
            not _is_digest(digest)
            or type(issued) is not int
            or type(expires) is not int
            or grant_values.get("consumed_digest") != consumed_digest
            or grant_values.get("epoch_digest") != consumed_epoch
        ):
            self.state = CanonicalLifecycleState.PRESENT_INVALID
            return
        self._grant = CanonicalGrantInspection(str(digest), int(issued), int(expires), False)
        self._grant_record = grant.record
        if grant_domain == "D1N2/GRANT_ISSUED/v1":
            self.state = CanonicalLifecycleState.ISSUED
        elif grant_domain == "D1N2/GRANT_REVOKED/v1":
            self.state = CanonicalLifecycleState.REVOKED_TERMINAL_PENDING
        else:
            self.state = CanonicalLifecycleState.PRESENT_INVALID

    @staticmethod
    def _write_status(result: WriteResult, expected: bytes) -> tuple[PersistenceOutcome, bool]:
        exact = (
            result.disposition is WriteDisposition.PRESENT_VALID
            and result.observed_bytes == expected
        )
        if result.outcome is PersistenceOutcome.OK:
            return (
                (PersistenceOutcome.OK, True)
                if exact
                else (
                    PersistenceOutcome.READBACK_FAILED,
                    False,
                )
            )
        return result.outcome, exact

    @staticmethod
    def _post_write(session: MutationSession) -> PersistenceOutcome:
        if session.validate_after() is not ValidationStatus.VALID:
            return PersistenceOutcome.LEASE_DRIFT
        if session.parent_durable() is not DurabilityStatus.VERIFIED:
            return PersistenceOutcome.DURABILITY_FAILED
        return PersistenceOutcome.OK

    def prepare(self) -> PersistenceOutcome:
        if self.state is not CanonicalLifecycleState.ABSENT:
            return PersistenceOutcome.INPUT_INVALID
        started, session = self._begin_mutation(OperationKind.PREPARE)
        if session is None:
            return started
        outcome = PersistenceOutcome.OK
        try:
            inspection = self._inspect_with_session(session, AuthorityLeaf.PREPARED)
            if (
                inspection.state is not CanonicalLifecycleState.ABSENT
                or inspection.record is not None
            ):
                self.state = (
                    inspection.state
                    if inspection.state is not CanonicalLifecycleState.ABSENT
                    else CanonicalLifecycleState.PRESENT_INVALID
                )
                outcome = PersistenceOutcome.CREATE_FAILED
            else:
                approved = session.attest_a0_before_pending()
                if (
                    type(approved) is not ApprovedRP2Triple
                    or not approved.valid()
                ):
                    outcome = PersistenceOutcome.ATTESTATION_FAILED
                else:
                    self._approved_rp2 = approved
            if outcome is PersistenceOutcome.OK:
                assert self._approved_rp2 is not None
                pending = _record(
                    "D1N2/PENDING/v1",
                    {
                        **self._approved_rp2.pending_fields(),
                        "epoch_digest": self.epoch_digest,
                        "state": "PENDING",
                    },
                )
                created = self._persistence.create_exact(session, AuthorityLeaf.PREPARED, pending)
                outcome, exact_pending = self._write_status(created, pending)
                if outcome is not PersistenceOutcome.OK:
                    if exact_pending:
                        self._pending, self.state = pending, CanonicalLifecycleState.PENDING
                    elif created.disposition is not WriteDisposition.ZERO_WRITE:
                        self.state = CanonicalLifecycleState.PRESENT_INVALID
                else:
                    self._pending, self.state = pending, CanonicalLifecycleState.PENDING
                    outcome = self._post_write(session)
                    if outcome is PersistenceOutcome.OK:
                        attestation = session.attest_pending()
                        if (
                            attestation is None
                            or not attestation.valid()
                            or attestation.static_bindings_digest
                            != self._approved_rp2.static_bindings_digest
                            or attestation.binding_schema_digest
                            != self._approved_rp2.binding_schema_canonical_sha256
                            or attestation.manifest_sha256
                            != self._approved_rp2.candidate_exact_bytes_sha256
                        ):
                            outcome = PersistenceOutcome.ATTESTATION_FAILED
                        elif session.validate_before() is not ValidationStatus.VALID:
                            outcome = PersistenceOutcome.LEASE_DRIFT
                    if outcome is PersistenceOutcome.OK:
                        assert attestation is not None
                        prepared = _record(
                            "D1N2/PREPARED/v1",
                            {
                                **attestation.record_fields(),
                                "epoch_digest": self.epoch_digest,
                                "pending_digest": _sha256_bytes(pending),
                                "state": "PREPARED",
                            },
                        )
                        replaced = self._persistence.cas_exact(
                            session,
                            AuthorityLeaf.PREPARED,
                            pending,
                            prepared,
                        )
                        outcome, exact_prepared = self._write_status(replaced, prepared)
                        if outcome is PersistenceOutcome.OK:
                            self._prepared = prepared
                            self.state = CanonicalLifecycleState.PREPARED
                            outcome = self._post_write(session)
                            if outcome is not PersistenceOutcome.OK:
                                self._live_prepared = False
                                self.state = CanonicalLifecycleState.PREPARED_NONLAUNCHABLE
                        elif exact_prepared:
                            self._prepared = prepared
                            self.state = CanonicalLifecycleState.PREPARED_NONLAUNCHABLE
                        elif replaced.disposition is not WriteDisposition.ZERO_WRITE:
                            self.state = CanonicalLifecycleState.PRESENT_INVALID
        except BaseException as error:
            self._finish(session, error)
            raise AssertionError("unreachable") from error
        report = self._finish(session)
        if not _cleanup_is_clean(report):
            if self.state is CanonicalLifecycleState.PREPARED:
                self.state = CanonicalLifecycleState.PREPARED_NONLAUNCHABLE
            return PersistenceOutcome.CLEANUP_FAILED
        if outcome is PersistenceOutcome.OK and self.state is CanonicalLifecycleState.PREPARED:
            self._live_prepared = True
        return outcome

    def consume(self) -> PersistenceOutcome:
        if (
            self.state is not CanonicalLifecycleState.PREPARED
            or self._prepared is None
            or not self._live_prepared
        ):
            return PersistenceOutcome.CAS_MISMATCH
        prepared_values = _validated_record(self._prepared, "D1N2/PREPARED/v1")
        try:
            now_unix_ns = self._unix_clock_ns()
        except Exception:
            now_unix_ns = -1
        issued_unix_ns = (
            prepared_values.get("issued_unix_ns")
            if prepared_values is not None
            else None
        )
        expires_unix_ns = (
            prepared_values.get("expires_unix_ns")
            if prepared_values is not None
            else None
        )
        if (
            prepared_values is None
            or type(now_unix_ns) is not int
            or type(issued_unix_ns) is not int
            or type(expires_unix_ns) is not int
            or now_unix_ns < issued_unix_ns
            or now_unix_ns > expires_unix_ns
        ):
            self._live_prepared = False
            self.state = CanonicalLifecycleState.STALE_PREPARED_NONLAUNCHABLE
            return PersistenceOutcome.CAS_MISMATCH
        started, session = self._begin_mutation(OperationKind.CONSUME)
        if session is None:
            return started
        outcome = PersistenceOutcome.OK
        try:
            inspection = self._inspect_with_session(session, AuthorityLeaf.PREPARED)
            if inspection.record != self._prepared:
                self.state = CanonicalLifecycleState.PRESENT_INVALID
                outcome = PersistenceOutcome.CAS_MISMATCH
            else:
                prepared_values = _validated_record(
                    self._prepared, "D1N2/PREPARED/v1"
                )
                epoch_digest = (
                    prepared_values.get("epoch_digest") if prepared_values is not None else None
                )
                if not isinstance(epoch_digest, str) or not self._epoch.proves(epoch_digest):
                    self.state = CanonicalLifecycleState.STALE_PREPARED_NONLAUNCHABLE
                    outcome = PersistenceOutcome.CAS_MISMATCH
                else:
                    assert prepared_values is not None
                    consumed = _record(
                        "D1N2/CONSUMED/v1",
                        {
                            "dependency_observation_digest": prepared_values[
                                "dependency_observation_digest"
                            ],
                            "epoch_digest": self.epoch_digest,
                            "face_model_sha256": prepared_values["face_model_sha256"],
                            "pose_model_sha256": prepared_values["pose_model_sha256"],
                            "prepared_digest": _sha256_bytes(self._prepared),
                            "state": "CONSUMED",
                            "static_bindings_digest": prepared_values[
                                "static_bindings_digest"
                            ],
                        },
                    )
                    replaced = self._persistence.cas_exact(
                        session,
                        AuthorityLeaf.PREPARED,
                        self._prepared,
                        consumed,
                    )
                    outcome, exact_consumed = self._write_status(replaced, consumed)
                    if outcome is PersistenceOutcome.OK:
                        self._consumed = consumed
                        self.state = CanonicalLifecycleState.CONSUMED_NO_GRANT
                        outcome = self._post_write(session)
                    elif exact_consumed:
                        self._consumed = consumed
                        self.state = CanonicalLifecycleState.CONSUMED_NO_GRANT
                    elif replaced.disposition is not WriteDisposition.ZERO_WRITE:
                        self.state = CanonicalLifecycleState.PRESENT_INVALID
        except BaseException as error:
            self._finish(session, error)
            raise AssertionError("unreachable") from error
        report = self._finish(session)
        clean = _cleanup_is_clean(report)
        if not clean:
            return PersistenceOutcome.CLEANUP_FAILED
        if (
            outcome is PersistenceOutcome.OK
            and self.state is CanonicalLifecycleState.CONSUMED_NO_GRANT
        ):
            self._live_consumed = True
        return outcome

    def issue_grant(
        self, binding: WorkerGrantBindingAttestation
    ) -> PersistenceOutcome:
        if (
            type(binding) is not WorkerGrantBindingAttestation
            or not binding.valid()
            or self._prepared is None
            or binding.prepared_authority_digest != _sha256_bytes(self._prepared)
            or self.state is not CanonicalLifecycleState.CONSUMED_NO_GRANT
            or self._consumed is None
            or not self._live_consumed
        ):
            return PersistenceOutcome.GRANT_NOT_AUTHORIZED
        started, session = self._begin_mutation(OperationKind.ISSUE_GRANT)
        if session is None:
            return started
        outcome = PersistenceOutcome.OK
        raw: bytes | None = None
        try:
            consumed = self._inspect_with_session(session, AuthorityLeaf.PREPARED)
            grant = self._inspect_with_session(session, AuthorityLeaf.GRANT)
            if consumed.record != self._consumed or grant.record is not None:
                outcome = PersistenceOutcome.CAS_MISMATCH
            else:
                issued_monotonic_ns = self._clock_ns()
                if (
                    type(issued_monotonic_ns) is not int
                    or issued_monotonic_ns < 0
                    or issued_monotonic_ns > _MAX_SIGNED_NS - WORKER_GRANT_TTL_NS
                ):
                    outcome = PersistenceOutcome.GRANT_NOT_AUTHORIZED
                try:
                    raw = (
                        self._grant_entropy(32)
                        if outcome is PersistenceOutcome.OK
                        else None
                    )
                except Exception:
                    outcome = PersistenceOutcome.GRANT_ENTROPY_FAILED
                if outcome is PersistenceOutcome.OK and (type(raw) is not bytes or len(raw) != 32):
                    outcome = PersistenceOutcome.GRANT_ENTROPY_FAILED
                if outcome is PersistenceOutcome.OK:
                    assert raw is not None
                    digest = hashlib.sha256(raw).hexdigest()
                    record = _record(
                        "D1N2/GRANT_ISSUED/v1",
                        {
                            **binding.record_fields(),
                            "consumed_digest": _sha256_bytes(self._consumed),
                            "epoch_digest": self.epoch_digest,
                            "expires_monotonic_ns": (
                                issued_monotonic_ns + WORKER_GRANT_TTL_NS
                            ),
                            "grant_digest": digest,
                            "grant_size": 32,
                            "issued_monotonic_ns": issued_monotonic_ns,
                            "state": "ISSUED",
                        },
                    )
                    created = self._persistence.create_exact(session, AuthorityLeaf.GRANT, record)
                    outcome, exact_grant = self._write_status(created, record)
                    if outcome is PersistenceOutcome.OK:
                        self._grant_record = record
                        self.state = CanonicalLifecycleState.ISSUED
                        outcome = self._post_write(session)
                    elif exact_grant:
                        self._grant_record = record
                        self.state = CanonicalLifecycleState.ISSUED
                    elif created.disposition is not WriteDisposition.ZERO_WRITE:
                        self.state = CanonicalLifecycleState.PRESENT_INVALID
                    if self.state is CanonicalLifecycleState.ISSUED:
                        self._grant = CanonicalGrantInspection(
                            digest,
                            issued_monotonic_ns,
                            issued_monotonic_ns + WORKER_GRANT_TTL_NS,
                            False,
                        )
        except BaseException as error:
            self._finish(session, error)
            raise AssertionError("unreachable") from error
        report = self._finish(session)
        clean = _cleanup_is_clean(report)
        if not clean:
            raw = None
            outcome = PersistenceOutcome.CLEANUP_FAILED
        if outcome is PersistenceOutcome.OK and clean:
            self._grant_raw = raw
        else:
            self._grant_raw = None
        return outcome

    def take_grant_capability(self) -> bytes | None:
        if (
            self.state is not CanonicalLifecycleState.ISSUED
            or self._grant_handed_off
            or self._grant_raw is None
        ):
            return None
        self._grant_handed_off = True
        return self._grant_raw

    def authorize_grant(self, presented_raw: bytes) -> PersistenceOutcome:
        now_ns = self._clock_ns()
        if (
            self.state is not CanonicalLifecycleState.ISSUED
            or self._grant is None
            or not self._grant_handed_off
            or self._grant.used
            or type(now_ns) is not int
            or now_ns < self._grant.issued_monotonic_ns
            or now_ns > self._grant.expires_monotonic_ns
            or type(presented_raw) is not bytes
            or len(presented_raw) != 32
        ):
            return PersistenceOutcome.GRANT_NOT_AUTHORIZED
        presented_digest = hashlib.sha256(presented_raw).hexdigest()
        if not hmac.compare_digest(presented_digest, self._grant.digest):
            return PersistenceOutcome.GRANT_NOT_AUTHORIZED
        self._grant = CanonicalGrantInspection(
            self._grant.digest,
            self._grant.issued_monotonic_ns,
            self._grant.expires_monotonic_ns,
            True,
        )
        return PersistenceOutcome.OK

    def revoke_grant(self) -> PersistenceOutcome:
        if (
            self.state is not CanonicalLifecycleState.ISSUED
            or self._grant is None
            or self._grant_record is None
            or self._consumed is None
        ):
            return PersistenceOutcome.GRANT_NOT_AUTHORIZED
        self._grant_raw = None
        self._grant_handed_off = True
        started, session = self._begin_mutation(OperationKind.REVOKE_GRANT)
        if session is None:
            return started
        outcome = PersistenceOutcome.OK
        try:
            inspection = self._inspect_with_session(session, AuthorityLeaf.GRANT)
            if inspection.record != self._grant_record:
                outcome = PersistenceOutcome.CAS_MISMATCH
            else:
                issued_values = _validated_record(
                    self._grant_record,
                    "D1N2/GRANT_ISSUED/v1",
                )
                if issued_values is None:
                    outcome = PersistenceOutcome.CAS_MISMATCH
                else:
                    revoked = _record(
                        "D1N2/GRANT_REVOKED/v1",
                        {
                            "challenge_digest": issued_values["challenge_digest"],
                            "consumed_digest": _sha256_bytes(self._consumed),
                            "epoch_digest": self.epoch_digest,
                            "expires_monotonic_ns": self._grant.expires_monotonic_ns,
                            "grant_digest": self._grant.digest,
                            "issued_monotonic_ns": self._grant.issued_monotonic_ns,
                            "issued_record_digest": _sha256_bytes(self._grant_record),
                            "job_name_digest": issued_values["job_name_digest"],
                            "state": "REVOKED",
                        },
                    )
                    replaced = self._persistence.cas_exact(
                        session,
                        AuthorityLeaf.GRANT,
                        self._grant_record,
                        revoked,
                    )
                    outcome, exact_revoked = self._write_status(replaced, revoked)
                    if outcome is PersistenceOutcome.OK or exact_revoked:
                        self._grant_record = revoked
                        self.state = CanonicalLifecycleState.REVOKED_TERMINAL_PENDING
                    elif replaced.disposition is not WriteDisposition.ZERO_WRITE:
                        self.state = CanonicalLifecycleState.PRESENT_INVALID
                    if outcome is PersistenceOutcome.OK:
                        outcome = self._post_write(session)
        except BaseException as error:
            self._finish(session, error)
            raise AssertionError("unreachable") from error
        report = self._finish(session)
        if not _cleanup_is_clean(report):
            return PersistenceOutcome.CLEANUP_FAILED
        return outcome

    def terminalize(
        self, binding: TerminalBindingAttestation
    ) -> PersistenceOutcome:
        if type(binding) is not TerminalBindingAttestation or not binding.valid():
            return PersistenceOutcome.TERMINAL_NOT_AUTHORIZED
        if self.state in {
            CanonicalLifecycleState.TERMINAL,
            CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED,
        }:
            return PersistenceOutcome.TERMINAL_ALREADY_PRESENT
        if self.state is CanonicalLifecycleState.CONSUMED_NO_GRANT:
            disposition = GrantDisposition.NOT_ISSUED
        elif self.state is CanonicalLifecycleState.REVOKED_TERMINAL_PENDING:
            disposition = GrantDisposition.REVOKED
        else:
            return PersistenceOutcome.TERMINAL_NOT_AUTHORIZED
        if self._consumed is None:
            return PersistenceOutcome.TERMINAL_NOT_AUTHORIZED
        consumed_values = _validated_record(self._consumed, "D1N2/CONSUMED/v1")
        revoked_record = (
            self._grant_record if disposition is GrantDisposition.REVOKED else None
        )
        if consumed_values is None or not _terminal_receipt_matches_lifecycle(
            binding.record_fields(),
            consumed_values,
            revoked_record,
        ):
            return PersistenceOutcome.TERMINAL_NOT_AUTHORIZED
        started, session = self._begin_mutation(OperationKind.TERMINALIZE)
        if session is None:
            return started
        outcome = PersistenceOutcome.OK
        try:
            consumed = self._inspect_with_session(session, AuthorityLeaf.PREPARED)
            terminal = self._inspect_with_session(session, AuthorityLeaf.TERMINAL)
            if consumed.record != self._consumed:
                outcome = PersistenceOutcome.CAS_MISMATCH
            elif terminal.record is not None:
                outcome = PersistenceOutcome.TERMINAL_ALREADY_PRESENT
            else:
                grant_record_digest: str | None = None
                if disposition is GrantDisposition.REVOKED:
                    grant = self._inspect_with_session(session, AuthorityLeaf.GRANT)
                    if grant.record != self._grant_record:
                        outcome = PersistenceOutcome.CAS_MISMATCH
                    elif self._grant_record is not None:
                        grant_record_digest = _sha256_bytes(self._grant_record)
                if outcome is PersistenceOutcome.OK:
                    terminal_record = _record(
                        "D1N2/TERMINAL/v1",
                        {
                            **binding.record_fields(),
                            "consumed_digest": _sha256_bytes(self._consumed),
                            "durability_policy": "REVERIFY_PARENT_ON_INSPECTION",
                            "grant_disposition": disposition.value,
                            "grant_record_digest": grant_record_digest,
                            "state": "TERMINAL",
                        },
                    )
                    created = self._persistence.create_exact(
                        session, AuthorityLeaf.TERMINAL, terminal_record
                    )
                    outcome, exact_terminal = self._write_status(created, terminal_record)
                    if outcome is PersistenceOutcome.OK:
                        self.state = CanonicalLifecycleState.TERMINAL
                        outcome = self._post_write(session)
                        if outcome is not PersistenceOutcome.OK:
                            self.state = CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED
                    elif exact_terminal:
                        self.state = CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED
                    elif created.disposition is not WriteDisposition.ZERO_WRITE:
                        self.state = CanonicalLifecycleState.PRESENT_INVALID
        except BaseException as error:
            self._finish(session, error)
            raise AssertionError("unreachable") from error
        report = self._finish(session)
        if not _cleanup_is_clean(report):
            if self.state is CanonicalLifecycleState.TERMINAL:
                self.state = CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED
            return PersistenceOutcome.CLEANUP_FAILED
        return outcome


# Compatibility names now resolve to the single canonical seam; the unsafe H3-A
# facade no longer exists.
InjectableAuthorityState = CanonicalLifecycleState
ProcessEpoch = ProcessEpochV2
InjectableWorkerGrant = CanonicalGrantInspection
InjectableAuthorityLifecycle = CanonicalInjectableAuthorityLifecycle


__all__ = [
    "AuthorityLeaf",
    "BeginResult",
    "CanonicalAuthorityPersistence",
    "CanonicalCleanupFailure",
    "CanonicalGrantInspection",
    "CanonicalInjectableAuthorityLifecycle",
    "CanonicalInspection",
    "CanonicalLifecycleState",
    "classify_canonical_leaf_record",
    "CleanupReport",
    "DurabilityStatus",
    "GrantDisposition",
    "InjectableAuthorityLifecycle",
    "InjectableAuthorityState",
    "InjectableWorkerGrant",
    "MutationGuardFactory",
    "MutationSession",
    "OperationKind",
    "OwnerStatus",
    "PersistenceOutcome",
    "ProcessEpoch",
    "ProcessEpochV2",
    "StepStatus",
    "ValidationStatus",
    "WriteDisposition",
    "WriteResult",
]
