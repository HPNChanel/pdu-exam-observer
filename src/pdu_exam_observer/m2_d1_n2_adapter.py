"""Fixed D1-N2 guard composition without persistence or native execution on import."""

from __future__ import annotations

import hashlib
import json
import ntpath
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn, Protocol

from pdu_exam_observer.m2_d1_n2_a0 import (
    A0VerificationResult,
    A0VerificationStatus,
    ApprovedRP2Triple,
    FixedA0Verifier,
)
from pdu_exam_observer.m2_d1_n2_bootstrap_win32 import (
    BootstrapPaths,
    CtypesBootstrapHandleOps,
    FixedA0ApprovalSource,
    FixedBootstrapReader,
    LazyFixedA0ApprovalSource,
    LazyWindowsProvisionedA0Bootstrap,
)
from pdu_exam_observer.m2_d1_n2_canonical import (
    AuthorityLeaf,
    BeginResult,
    CanonicalAuthorityPersistence,
    CanonicalInjectableAuthorityLifecycle,
    CanonicalInspection,
    CanonicalLifecycleState,
    DurabilityStatus,
    MutationGuardFactory,
    MutationSession,
    OperationKind,
    OwnerStatus,
    PersistenceOutcome,
    PreparedBindingAttestation,
    StepStatus,
    TerminalBindingAttestation,
    ValidationStatus,
    WorkerGrantBindingAttestation,
    WriteDisposition,
    WriteResult,
    classify_canonical_leaf_record,
)
from pdu_exam_observer.m2_d1_n2_cng import verify_ecdsa_p256_sha256_p1363
from pdu_exam_observer.m2_d1_n2_evidence import RetainedLeaseCleanup
from pdu_exam_observer.m2_d1_n2_prepare import (
    D1N2NoStreamAttestor,
    NoStreamAttestationOutcome,
    NoStreamAttestationStatus,
    verify_fixed_rp2,
)
from pdu_exam_observer.m2_d1_n2_win32 import (
    MAX_AUTHORITY_RECORD_BYTES,
    CtypesHandleOps,
    LeafFailure,
    LeafResult,
    SameHandleLeaf,
)
from pdu_exam_observer.m2_d1_n2_win32_store import (
    AUTHORITY_MUTEX_NAME,
    CleanupFailure,
    CtypesDirectoryOps,
    CtypesMutexOps,
    DirectoryCleanupStatus,
    DirectoryDurability,
    DirectoryLease,
    DirectoryOps,
    KnownFolderAuthorityPaths,
    MutexOps,
    MutexStatus,
    resolve_known_folder_authority_root,
)


class _Lease(Protocol):
    def validate(self) -> bool: ...

    def durable(self) -> DirectoryDurability: ...

    def close(self) -> bool: ...


class _NoStreamAttestor(Protocol):
    def attest(self, expected: ApprovedRP2Triple) -> NoStreamAttestationOutcome: ...

    def revalidate_device(self, expected_name: str) -> bool: ...


class _A0Verifier(Protocol):
    def verify(self) -> A0VerificationResult: ...


class _BootstrapDirectoryParent:
    def __init__(self, lease: DirectoryLease) -> None:
        self._lease = lease
        self.identity = lease.identities[-1] if lease.identities else ""

    def validate(self) -> bool:
        return bool(self.identity and self._lease.validate())

    def durable(self) -> bool:
        return self._lease.durable() is DirectoryDurability.VERIFIED

    def close(self) -> bool:
        return self._lease.close()


def _acquire_bootstrap_parent(
    paths: KnownFolderAuthorityPaths,
) -> _BootstrapDirectoryParent | None:
    acquisition = DirectoryLease.acquire(CtypesDirectoryOps(), paths)
    if (
        acquisition.lease is None
        or acquisition.failure is not None
        or acquisition.cleanup_status is not DirectoryCleanupStatus.CLEAN
    ):
        return None
    return _BootstrapDirectoryParent(acquisition.lease)


def _production_bootstrap_reader() -> FixedBootstrapReader | None:
    known = resolve_known_folder_authority_root()
    if known is None:
        return None
    parent = _acquire_bootstrap_parent(known)
    if parent is None:
        return None
    try:
        paths = BootstrapPaths.for_root(known.authority)
        ops = CtypesBootstrapHandleOps()
        return FixedBootstrapReader(
            paths,
            ops,
            parent,
            verify_ecdsa_p256_sha256_p1363,
        )
    except BaseException:
        parent.close()
        return None


def _production_a0_source() -> FixedA0ApprovalSource | None:
    known = resolve_known_folder_authority_root()
    if known is None:
        return None
    try:
        paths = BootstrapPaths.for_root(known.authority)
        ops = CtypesBootstrapHandleOps()
    except BaseException:
        return None

    def parent_factory() -> _BootstrapDirectoryParent:
        parent = _acquire_bootstrap_parent(known)
        if parent is None:
            raise RuntimeError("fixed A0 parent is unavailable")
        return parent

    return FixedA0ApprovalSource(paths, ops, parent_factory)


@dataclass(frozen=True, slots=True)
class D1N2PreparationResult:
    outcome: PersistenceOutcome
    attestation: PreparedBindingAttestation | None = None
    prepared_bytes: bytes | None = None
    prepared_authority_digest: str | None = None
    retained_device_name: str | None = None
    a0_status: A0VerificationStatus | None = None


class AbortStatus(StrEnum):
    CLEAN = "CLEAN"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class AbortReport:
    a0_close: StepStatus
    preparation_close: StepStatus
    status: AbortStatus


class _B1CompositionCapability:
    pass


def _not_issued_attestor() -> PreparedBindingAttestation | None:
    """No production activation exists in this construction-only slice."""
    return None


def _not_issued_a0() -> ApprovedRP2Triple | None:
    return None


def _raise_after_mutex_failure(
    mutex: MutexOps,
    primary: BaseException,
    *,
    release_required: bool,
) -> NoReturn:
    cleanup: list[BaseException] = []
    if release_required:
        try:
            released = mutex.release()
        except BaseException:
            released = False
        if not released:
            cleanup.append(CleanupFailure("MUTEX_RELEASE_FAILED"))
    try:
        closed = mutex.close()
    except BaseException:
        closed = False
    if not closed:
        cleanup.append(CleanupFailure("MUTEX_CLOSE_FAILED"))
    if not cleanup:
        raise primary
    raise BaseExceptionGroup(
        "D1-N2 guard primary and cleanup failure",
        [primary, *cleanup],
    )


class _B1MutationSession(MutationSession):
    def __init__(
        self,
        mutex: MutexOps,
        owner: MutexStatus,
        lease: _Lease | None,
        lease_cleanup: DirectoryCleanupStatus,
        attestor: Callable[[], PreparedBindingAttestation | None],
        paths: KnownFolderAuthorityPaths | None = None,
        operation: OperationKind = OperationKind.INSPECT,
        capability: _B1CompositionCapability | None = None,
        a0_attestor: Callable[[], ApprovedRP2Triple | None] = _not_issued_a0,
    ) -> None:
        self._mutex = mutex
        self._owner = owner
        self._lease = lease
        self._lease_cleanup = lease_cleanup
        self._attestor = attestor
        self._a0_attestor = a0_attestor
        self._paths = paths
        self._operation = operation
        self._capability = capability
        self._active = True
        self._attested = False
        self._lease_close: StepStatus | None = None
        self._mutex_release: StepStatus | None = None
        self._mutex_close: StepStatus | None = None

    @property
    def write_permitted(self) -> bool:
        return (
            self._owner is MutexStatus.ACQUIRED
            and self._lease is not None
            and self._lease_cleanup is DirectoryCleanupStatus.CLEAN
            and self._active
        )

    def validate_before(self) -> ValidationStatus:
        return self._validate()

    def validate_after(self) -> ValidationStatus:
        return self._validate()

    def _validate(self) -> ValidationStatus:
        if not self.write_permitted:
            return ValidationStatus.DRIFT
        try:
            valid = self._lease is not None and self._lease.validate()
            return ValidationStatus.VALID if valid else ValidationStatus.DRIFT
        except Exception:
            return ValidationStatus.ERROR

    def parent_durable(self) -> DurabilityStatus:
        if not self.write_permitted:
            return DurabilityStatus.UNVERIFIED
        try:
            durable = self._lease and self._lease.durable()
        except Exception:
            return DurabilityStatus.ERROR
        return (
            DurabilityStatus.VERIFIED
            if durable is DirectoryDurability.VERIFIED
            else DurabilityStatus.UNVERIFIED
        )

    def attest_pending(self) -> PreparedBindingAttestation | None:
        if not self._active:
            return None
        try:
            attestation = self._attestor()
        except Exception:
            return None
        if attestation is not None and attestation.valid():
            self._attested = True
            return attestation
        return None

    def attest_a0_before_pending(self) -> ApprovedRP2Triple | None:
        if not self._active:
            return None
        try:
            approved = self._a0_attestor()
        except Exception:
            return None
        return approved if type(approved) is ApprovedRP2Triple and approved.valid() else None

    def close_leases(self) -> StepStatus:
        if self._lease_close is not None:
            return self._lease_close
        self._active = False
        if self._lease is None:
            self._lease_close = StepStatus.NOT_HELD
            return self._lease_close
        try:
            clean = self._lease.close()
        except BaseException:
            clean = False
        self._lease_close = StepStatus.CLEAN if clean else StepStatus.FAILED
        return self._lease_close

    def release_mutex(self) -> StepStatus:
        if self._mutex_release is not None:
            return self._mutex_release
        self._active = False
        if self._owner not in {MutexStatus.ACQUIRED, MutexStatus.ABANDONED}:
            self._mutex_release = StepStatus.NOT_HELD
            return self._mutex_release
        try:
            clean = self._mutex.release()
        except BaseException:
            clean = False
        self._mutex_release = StepStatus.CLEAN if clean else StepStatus.FAILED
        return self._mutex_release

    def close_mutex(self) -> StepStatus:
        if self._mutex_close is not None:
            return self._mutex_close
        self._active = False
        try:
            clean = self._mutex.close()
        except BaseException:
            clean = False
        self._mutex_close = StepStatus.CLEAN if clean else StepStatus.FAILED
        return self._mutex_close

    def _persistence_path(self) -> str | None:
        if (
            not self.write_permitted
            or self._paths is None
            or self._lease_close is not None
            or not self._active
        ):
            return None
        return self._paths.authority


class _B1GuardFactory(MutationGuardFactory):
    """Private injectable composition used by fake-only adapter tests."""

    def __init__(
        self,
        *,
        resolver: Callable[[], KnownFolderAuthorityPaths | None],
        mutex_factory: Callable[[], MutexOps],
        directory_ops_factory: Callable[[], DirectoryOps],
        attestor: Callable[[], PreparedBindingAttestation | None],
        a0_attestor: Callable[[], ApprovedRP2Triple | None] = _not_issued_a0,
        capability: _B1CompositionCapability | None = None,
    ) -> None:
        self._resolver = resolver
        self._mutex_factory = mutex_factory
        self._directory_ops_factory = directory_ops_factory
        self._attestor = attestor
        self._a0_attestor = a0_attestor
        self._capability = (
            _B1CompositionCapability() if capability is None else capability
        )

    def begin(self, _operation: OperationKind) -> BeginResult:
        try:
            paths = self._resolver()
        except Exception:
            return BeginResult(OwnerStatus.ERROR, None)
        if paths is None:
            return BeginResult(OwnerStatus.ERROR, None)
        try:
            mutex = self._mutex_factory()
        except Exception:
            return BeginResult(OwnerStatus.ERROR, None)
        try:
            owner = mutex.acquire(AUTHORITY_MUTEX_NAME)
        except BaseException as primary:
            _raise_after_mutex_failure(
                mutex,
                primary,
                release_required=True,
            )
        if owner is MutexStatus.ABANDONED:
            return BeginResult(
                OwnerStatus.ABANDONED_INSPECTION_ONLY,
                _B1MutationSession(
                    mutex,
                    owner,
                    None,
                    DirectoryCleanupStatus.CLEAN,
                    self._attestor,
                    paths,
                    _operation,
                    self._capability,
                    self._a0_attestor,
                ),
            )
        if owner is not MutexStatus.ACQUIRED:
            return BeginResult(
                OwnerStatus.UNAVAILABLE,
                _B1MutationSession(
                    mutex,
                    owner,
                    None,
                    DirectoryCleanupStatus.CLEAN,
                    self._attestor,
                    paths,
                    _operation,
                    self._capability,
                    self._a0_attestor,
                ),
            )
        lease: _Lease | None = None
        cleanup = DirectoryCleanupStatus.CLEAN
        try:
            acquisition = DirectoryLease.acquire(self._directory_ops_factory(), paths)
            lease = acquisition.lease
            cleanup = acquisition.cleanup_status
        except BaseException as primary:
            _raise_after_mutex_failure(
                mutex,
                primary,
                release_required=True,
            )
        return BeginResult(
            OwnerStatus.ACQUIRED,
            _B1MutationSession(
                mutex,
                owner,
                lease,
                cleanup,
                self._attestor,
                paths,
                _operation,
                self._capability,
                self._a0_attestor,
            ),
        )

    def persistence(
        self, leaf_factory: Callable[[str], _B1Leaf] | None = None
    ) -> _B1CanonicalPersistence:
        return _B1CanonicalPersistence(
            self._capability,
            _production_leaf_factory if leaf_factory is None else leaf_factory,
        )


class _B1Leaf(Protocol):
    def inspect(self, codec: Callable[[bytes], bool]) -> LeafResult: ...

    def create(self, payload: bytes, codec: Callable[[bytes], bool]) -> LeafResult: ...

    def transition(
        self, prior: bytes, payload: bytes, codec: Callable[[bytes], bool]
    ) -> LeafResult: ...


def _canonical_leaf_codec(payload: bytes) -> bool:
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_AUTHORITY_RECORD_BYTES:
        return False

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_float(_value: str) -> NoReturn:
        raise ValueError("float")

    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
        if not isinstance(decoded, dict):
            return False
        return json.dumps(
            decoded,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8") == payload
    except (TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False


def _production_leaf_factory(path: str) -> SameHandleLeaf:
    return SameHandleLeaf(CtypesHandleOps(), path)


class _B1CanonicalPersistence(CanonicalAuthorityPersistence):
    """Private H1 bridge; canonical.py remains the strict record authority."""

    def __init__(
        self,
        capability: _B1CompositionCapability,
        leaf_factory: Callable[[str], _B1Leaf] = _production_leaf_factory,
    ) -> None:
        self._capability = capability
        self._leaf_factory = leaf_factory

    def _session_path(self, session: MutationSession, leaf: AuthorityLeaf) -> str | None:
        if type(session) is not _B1MutationSession or type(leaf) is not AuthorityLeaf:
            return None
        if session._capability is not self._capability:
            return None
        authority = session._persistence_path()
        if authority is None or session.validate_before() is not ValidationStatus.VALID:
            return None
        return ntpath.join(authority, leaf.value)

    @staticmethod
    def _write_failure(failure: LeafFailure | None) -> PersistenceOutcome:
        if failure is LeafFailure.STALE_CAS:
            return PersistenceOutcome.CAS_MISMATCH
        if failure in {LeafFailure.READ_FAILED, LeafFailure.READBACK_FAILED}:
            return PersistenceOutcome.READBACK_FAILED
        if failure is LeafFailure.CLOSE_FAILED:
            return PersistenceOutcome.CLOSE_FAILED
        if failure is LeafFailure.FLUSH_FAILED:
            return PersistenceOutcome.DURABILITY_FAILED
        if failure is LeafFailure.CODEC_INVALID:
            return PersistenceOutcome.INPUT_INVALID
        if failure in {LeafFailure.HANDLE_VALIDATION_FAILED, LeafFailure.IDENTITY_CHANGED}:
            return PersistenceOutcome.LEASE_DRIFT
        return PersistenceOutcome.CREATE_FAILED

    def inspect(self, session: MutationSession, leaf: AuthorityLeaf) -> CanonicalInspection:
        path = self._session_path(session, leaf)
        if path is None:
            return CanonicalInspection(CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE, None)
        try:
            result = self._leaf_factory(path).inspect(_canonical_leaf_codec)
        except BaseException:
            return CanonicalInspection(CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE, None)
        if result.failure is LeafFailure.ABSENT:
            return CanonicalInspection(CanonicalLifecycleState.ABSENT, None)
        if result.failure in {LeafFailure.CODEC_INVALID, LeafFailure.HANDLE_VALIDATION_FAILED}:
            return CanonicalInspection(CanonicalLifecycleState.PRESENT_INVALID, None)
        if result.failure is not None or result.payload is None:
            return CanonicalInspection(CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE, None)
        if not _canonical_leaf_codec(result.payload):
            return CanonicalInspection(CanonicalLifecycleState.PRESENT_INVALID, None)
        state = classify_canonical_leaf_record(leaf, result.payload)
        if state is None:
            return CanonicalInspection(CanonicalLifecycleState.PRESENT_INVALID, None)
        durability = DurabilityStatus.UNVERIFIED
        if leaf is AuthorityLeaf.TERMINAL:
            durability = session.parent_durable()
        return CanonicalInspection(state, result.payload, durability)

    def create_exact(
        self, session: MutationSession, leaf: AuthorityLeaf, record: bytes
    ) -> WriteResult:
        return self._write(session, leaf, record, None)

    def cas_exact(
        self, session: MutationSession, leaf: AuthorityLeaf, prior: bytes, record: bytes
    ) -> WriteResult:
        return self._write(session, leaf, record, prior)

    def _write(
        self,
        session: MutationSession,
        leaf: AuthorityLeaf,
        record: bytes,
        prior: bytes | None,
    ) -> WriteResult:
        if type(session) is not _B1MutationSession or type(leaf) is not AuthorityLeaf:
            return WriteResult(PersistenceOutcome.INPUT_INVALID, WriteDisposition.PRESENT_UNKNOWN)
        if session._lease_close is not None:
            return WriteResult(PersistenceOutcome.CLOSE_FAILED, WriteDisposition.PRESENT_UNKNOWN)
        path = self._session_path(session, leaf)
        if path is None:
            return WriteResult(PersistenceOutcome.LEASE_DRIFT, WriteDisposition.PRESENT_UNKNOWN)
        target_state = classify_canonical_leaf_record(leaf, record)
        prior_state = (
            None if prior is None else classify_canonical_leaf_record(leaf, prior)
        )
        if target_state is None or (prior is not None and prior_state is None):
            return WriteResult(PersistenceOutcome.INPUT_INVALID, WriteDisposition.PRESENT_UNKNOWN)
        if not self._operation_allowed(session, target_state, prior_state):
            return WriteResult(PersistenceOutcome.INPUT_INVALID, WriteDisposition.PRESENT_UNKNOWN)
        try:
            target = self._leaf_factory(path)
            result = (
                target.create(record, _canonical_leaf_codec)
                if prior is None
                else target.transition(prior, record, _canonical_leaf_codec)
            )
        except BaseException:
            return WriteResult(PersistenceOutcome.CREATE_FAILED, WriteDisposition.PRESENT_UNKNOWN)
        if result.failure is None and result.payload == record:
            return WriteResult(PersistenceOutcome.OK, WriteDisposition.PRESENT_VALID, record)
        outcome = (
            PersistenceOutcome.READBACK_FAILED
            if result.failure is None
            else self._write_failure(result.failure)
        )
        return WriteResult(outcome, WriteDisposition.PRESENT_UNKNOWN)

    @staticmethod
    def _operation_allowed(
        session: _B1MutationSession,
        target: CanonicalLifecycleState,
        prior: CanonicalLifecycleState | None,
    ) -> bool:
        if prior is None:
            return (
                (
                    session._operation is OperationKind.PREPARE
                    and target is CanonicalLifecycleState.PENDING
                )
                or (
                    session._operation is OperationKind.ISSUE_GRANT
                    and target is CanonicalLifecycleState.ISSUED
                )
                or (
                    session._operation is OperationKind.TERMINALIZE
                    and target is CanonicalLifecycleState.TERMINAL
                )
            )
        if session._operation is OperationKind.PREPARE:
            if (
                prior is CanonicalLifecycleState.PENDING
                and target is CanonicalLifecycleState.PREPARED
            ):
                return session._attested or session.attest_pending() is not None
            return False
        return (
            session._operation is OperationKind.CONSUME
            and prior is CanonicalLifecycleState.PREPARED
            and target is CanonicalLifecycleState.CONSUMED_NO_GRANT
        ) or (
            session._operation is OperationKind.REVOKE_GRANT
            and prior is CanonicalLifecycleState.ISSUED
            and target is CanonicalLifecycleState.REVOKED_TERMINAL_PENDING
        )


class _D1N2PreparationComposition:
    """Owns the one attestor call and transfers live leases only after PREPARED."""

    def __init__(
        self,
        persistence: _B1CanonicalPersistence,
        guard: _B1GuardFactory,
        no_stream_attestor: _NoStreamAttestor,
        *,
        entropy: Callable[[int], bytes],
        unix_clock_ns: Callable[[], int],
        a0_verifier: _A0Verifier | None = None,
        grant_entropy: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        self._no_stream_attestor = no_stream_attestor
        self._attestation_outcome: NoStreamAttestationOutcome | None = None
        self._a0_verifier = a0_verifier
        self._a0_outcome: A0VerificationResult | None = None
        self._unix_clock_ns = unix_clock_ns
        self._leases_closed = False
        self._retained_cleanup_attempted = False
        self._retained_cleanup: RetainedLeaseCleanup | None = None
        self._abort_report: AbortReport | None = None
        self._transferred = False
        self._prepared_digest: str | None = None
        guard._attestor = self._attest_pending
        guard._a0_attestor = self._attest_a0
        self._lifecycle = CanonicalInjectableAuthorityLifecycle(
            persistence,
            guard,
            entropy=entropy,
            grant_entropy=grant_entropy,
            unix_clock_ns=unix_clock_ns,
        )

    def _attest_a0(self) -> ApprovedRP2Triple | None:
        if self._a0_outcome is not None or self._a0_verifier is None:
            return None
        outcome = self._a0_verifier.verify()
        self._a0_outcome = outcome
        if (
            outcome.status is A0VerificationStatus.VERIFIED
            and outcome.approved is not None
            and outcome.lease is not None
            and outcome.bootstrap is not None
        ):
            return outcome.approved
        return None

    def _attest_pending(self) -> PreparedBindingAttestation | None:
        if self._attestation_outcome is not None:
            return None
        approved = self._a0_outcome.approved if self._a0_outcome is not None else None
        if approved is None:
            return None
        outcome = self._no_stream_attestor.attest(approved)
        self._attestation_outcome = outcome
        if (
            outcome.status is NoStreamAttestationStatus.ATTESTED
            and outcome.attestation is not None
            and outcome.lease_bundle is not None
        ):
            return outcome.attestation
        return None

    @staticmethod
    def _close_outcome(outcome: NoStreamAttestationOutcome | None) -> bool:
        if outcome is None or outcome.lease_bundle is None:
            return True
        try:
            return outcome.lease_bundle.close()
        except BaseException:
            return False

    @staticmethod
    def _close_a0(outcome: A0VerificationResult | None) -> bool:
        if outcome is None:
            return True
        clean = True
        if outcome.lease is not None:
            try:
                clean = outcome.lease.close() and clean
            except BaseException:
                clean = False
        if outcome.bootstrap is not None:
            try:
                clean = outcome.bootstrap.close() and clean
            except BaseException:
                clean = False
        return clean

    def abort_pre_bridge(self) -> AbortReport:
        if self._abort_report is not None:
            return self._abort_report
        if self._transferred:
            self._abort_report = AbortReport(
                StepStatus.NOT_HELD,
                StepStatus.NOT_HELD,
                AbortStatus.UNCERTAIN,
            )
            return self._abort_report
        cleanup = self._close_retained()
        preparation_clean = cleanup.preparation_clean
        a0_clean = cleanup.a0_clean
        self._leases_closed = True
        self._attestation_outcome = None
        self._a0_outcome = None
        self._abort_report = AbortReport(
            StepStatus.CLEAN if a0_clean else StepStatus.FAILED,
            StepStatus.CLEAN if preparation_clean else StepStatus.FAILED,
            AbortStatus.CLEAN
            if a0_clean and preparation_clean
            else AbortStatus.UNCERTAIN,
        )
        return self._abort_report

    def _abort_after_transfer(self) -> AbortReport:
        if self._abort_report is not None:
            return self._abort_report
        cleanup = self._close_retained()
        preparation_clean = cleanup.preparation_clean
        a0_clean = cleanup.a0_clean
        self._leases_closed = True
        self._attestation_outcome = None
        self._a0_outcome = None
        self._abort_report = AbortReport(
            StepStatus.CLEAN if a0_clean else StepStatus.FAILED,
            StepStatus.CLEAN if preparation_clean else StepStatus.FAILED,
            AbortStatus.CLEAN
            if a0_clean and preparation_clean
            else AbortStatus.UNCERTAIN,
        )
        return self._abort_report

    def _close_retained(self) -> RetainedLeaseCleanup:
        if self._retained_cleanup_attempted:
            return self._retained_cleanup or RetainedLeaseCleanup(False, False, False)
        self._retained_cleanup_attempted = True
        preparation_clean = self._close_outcome(self._attestation_outcome)
        a0_clean = self._close_a0(self._a0_outcome)
        self._leases_closed = True
        self._retained_cleanup = RetainedLeaseCleanup(
            a0_clean=a0_clean,
            rp2_clean=preparation_clean,
            preparation_clean=preparation_clean,
        )
        return self._retained_cleanup

    def close_retained_for_terminal(self) -> RetainedLeaseCleanup | None:
        cleanup = self._close_retained()
        return cleanup if cleanup.valid() else None

    def transfer_to_bridge(self) -> ExecutionOwnership | None:
        if (
            self._transferred
            or self._leases_closed
            or self._prepared_digest is None
            or self._attestation_outcome is None
            or self._a0_outcome is None
        ):
            return None
        self._transferred = True
        return ExecutionOwnership(self)

    def prepare(self) -> D1N2PreparationResult:
        outcome = self._lifecycle.prepare()
        attested = self._attestation_outcome
        a0_status = self._a0_outcome.status if self._a0_outcome is not None else None
        if outcome is not PersistenceOutcome.OK:
            report = self.abort_pre_bridge()
            return D1N2PreparationResult(
                outcome
                if report.status is AbortStatus.CLEAN
                else PersistenceOutcome.CLEANUP_FAILED,
                a0_status=a0_status,
            )
        prepared = self._lifecycle.prepared_record
        if (
            attested is None
            or attested.status is not NoStreamAttestationStatus.ATTESTED
            or attested.attestation is None
            or attested.lease_bundle is None
            or prepared is None
            or not attested.lease_bundle.validate()
        ):
            report = self.abort_pre_bridge()
            return D1N2PreparationResult(
                PersistenceOutcome.LEASE_DRIFT
                if report.status is AbortStatus.CLEAN
                else PersistenceOutcome.CLEANUP_FAILED,
                a0_status=a0_status,
            )
        self._prepared_digest = hashlib.sha256(prepared).hexdigest()
        return D1N2PreparationResult(
            PersistenceOutcome.OK,
            attested.attestation,
            prepared,
            self._prepared_digest,
            attested.retained_device_name,
            a0_status,
        )

    def revalidate_for_run(self) -> bool:
        outcome = self._attestation_outcome
        prepared = self._lifecycle.prepared_record
        if (
            self._leases_closed
            or outcome is None
            or outcome.attestation is None
            or outcome.lease_bundle is None
            or self._a0_outcome is None
            or self._a0_outcome.approved is None
            or self._a0_outcome.lease is None
            or self._a0_outcome.bootstrap is None
            or not self._a0_outcome.lease.validate()
            or not self._a0_outcome.bootstrap.validate()
            or outcome.retained_device_name is None
            or prepared is None
            or not outcome.lease_bundle.validate()
            or hashlib.sha256(prepared).hexdigest() != self._prepared_digest
        ):
            return False
        now = self._unix_clock_ns()
        if (
            type(now) is not int
            or now < outcome.attestation.issued_unix_ns
            or now > outcome.attestation.expires_unix_ns
        ):
            return False
        return self._no_stream_attestor.revalidate_device(
            outcome.retained_device_name
        )

    def consume(self) -> PersistenceOutcome:
        return self._lifecycle.consume()

    def issue_grant(
        self, binding: WorkerGrantBindingAttestation
    ) -> PersistenceOutcome:
        return self._lifecycle.issue_grant(binding)

    def take_grant_capability(self) -> bytes | None:
        return self._lifecycle.take_grant_capability()

    def grant_record_bytes(self) -> bytes | None:
        return self._lifecycle.grant_record

    def authorize_grant(self, capability: bytes) -> PersistenceOutcome:
        return self._lifecycle.authorize_grant(capability)

    def revoke_grant(self) -> PersistenceOutcome:
        return self._lifecycle.revoke_grant()

    def terminalize(self, binding: TerminalBindingAttestation) -> PersistenceOutcome:
        cleanup = self._retained_cleanup
        if cleanup is None or not cleanup.valid():
            return PersistenceOutcome.CLEANUP_FAILED
        if not (
            binding.retained_a0_clean
            and binding.retained_rp2_clean
            and binding.retained_preparation_clean
        ):
            return PersistenceOutcome.TERMINAL_NOT_AUTHORIZED
        return self._lifecycle.terminalize(binding)


class ExecutionOwnership:
    """Exclusive post-transfer facade; preparation abort cannot close its leases."""

    def __init__(self, composition: _D1N2PreparationComposition) -> None:
        self._composition = composition

    def revalidate_for_run(self) -> bool:
        return self._composition.revalidate_for_run()

    def consume(self) -> PersistenceOutcome:
        return self._composition.consume()

    def issue_grant(self, binding: WorkerGrantBindingAttestation) -> PersistenceOutcome:
        return self._composition.issue_grant(binding)

    def take_grant_capability(self) -> bytes | None:
        return self._composition.take_grant_capability()

    def grant_record_bytes(self) -> bytes | None:
        return self._composition.grant_record_bytes()

    def authorize_grant(self, capability: bytes) -> PersistenceOutcome:
        return self._composition.authorize_grant(capability)

    def revoke_grant(self) -> PersistenceOutcome:
        return self._composition.revoke_grant()

    def terminalize(self, binding: TerminalBindingAttestation) -> PersistenceOutcome:
        return self._composition.terminalize(binding)

    def close_retained_for_terminal(self) -> RetainedLeaseCleanup | None:
        return self._composition.close_retained_for_terminal()

    def abort_after_transfer(self) -> AbortReport:
        return self._composition._abort_after_transfer()


class D1N2ProductionGuardFactory(MutationGuardFactory):
    """Parameterless fixed production composition; construction performs no I/O."""

    def __init__(self) -> None:
        self._delegate = _B1GuardFactory(
            resolver=resolve_known_folder_authority_root,
            mutex_factory=CtypesMutexOps,
            directory_ops_factory=CtypesDirectoryOps,
            attestor=_not_issued_attestor,
        )

    def begin(self, operation: OperationKind) -> BeginResult:
        return self._delegate.begin(operation)


class D1N2CanonicalProductionFactory:
    """Lazy fixed composition; no public call can supply authority inputs."""

    def __init__(self) -> None:
        self.__capability = _B1CompositionCapability()
        self.__guard: _B1GuardFactory | None = None
        self.__persistence: _B1CanonicalPersistence | None = None

    def _compose(self) -> tuple[_B1GuardFactory, _B1CanonicalPersistence]:
        if self.__guard is None or self.__persistence is None:
            guard = _B1GuardFactory(
                resolver=resolve_known_folder_authority_root,
                mutex_factory=CtypesMutexOps,
                directory_ops_factory=CtypesDirectoryOps,
                attestor=_not_issued_attestor,
                capability=self.__capability,
            )
            self.__guard = guard
            self.__persistence = guard.persistence()
        return self.__guard, self.__persistence

    def open(self) -> CanonicalInjectableAuthorityLifecycle:
        """Build the fixed composition only when a future issuer invokes it."""

        guard, persistence = self._compose()
        return CanonicalInjectableAuthorityLifecycle(persistence, guard)


class D1N2PreparedProductionFactory:
    """Lazy fixed preparation composition for the one production prepare call."""

    def __init__(self) -> None:
        self.__capability = _B1CompositionCapability()

    def open(self) -> _D1N2PreparationComposition:
        from pdu_exam_observer.m2_d1_n2_native import D1N2WindowsPreparationPort

        no_stream = D1N2NoStreamAttestor(
            verify_fixed_rp2,
            D1N2WindowsPreparationPort(),
        )
        bootstrap = LazyWindowsProvisionedA0Bootstrap(
            _production_bootstrap_reader,
            verify_ecdsa_p256_sha256_p1363,
        )
        a0_verifier = FixedA0Verifier(
            LazyFixedA0ApprovalSource(_production_a0_source),
            bootstrap,
            time.time_ns,
        )
        guard = _B1GuardFactory(
            resolver=resolve_known_folder_authority_root,
            mutex_factory=CtypesMutexOps,
            directory_ops_factory=CtypesDirectoryOps,
            attestor=_not_issued_attestor,
            capability=self.__capability,
        )
        persistence = guard.persistence()
        return _D1N2PreparationComposition(
            persistence,
            guard,
            no_stream,
            entropy=secrets.token_bytes,
            unix_clock_ns=time.time_ns,
            a0_verifier=a0_verifier,
        )
