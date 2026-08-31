"""Same-process retained-epoch entrypoints for one D1-N2 prepare/run sequence."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pdu_exam_observer.m2_d1_n2_a0 import A0VerificationStatus
from pdu_exam_observer.m2_d1_n2_adapter import (
    AbortStatus,
    D1N2PreparationResult,
    D1N2PreparedProductionFactory,
    ExecutionOwnership,
)
from pdu_exam_observer.m2_d1_n2_canonical import (
    PersistenceOutcome,
    TerminalBindingAttestation,
    WorkerGrantBindingAttestation,
)
from pdu_exam_observer.m2_d1_n2_native import (
    D1N2DriverResult,
    D1N2ExecutionBridge,
    D1N2ExecutionRequest,
    D1N2ExecutionStatus,
)


class D1N2EntrypointStatus(StrEnum):
    AUTHORITY_NOT_ISSUED = "AUTHORITY_NOT_ISSUED"
    PREPARED_WAITING_A1 = "PREPARED_WAITING_A1"
    TERMINAL = "TERMINAL"
    FAILED_NONLAUNCHABLE = "FAILED_NONLAUNCHABLE"
    ALREADY_USED = "ALREADY_USED"


class D1N2ControllerState(StrEnum):
    UNINITIALIZED = "UNINITIALIZED"
    PREPARING = "PREPARING"
    PREPARED_WAITING_A1 = "PREPARED_WAITING_A1"
    CONSUMED = "CONSUMED"
    TERMINAL = "TERMINAL"
    FAILED_NONLAUNCHABLE = "FAILED_NONLAUNCHABLE"


@dataclass(frozen=True, slots=True)
class D1N2EntrypointResult:
    status: D1N2EntrypointStatus
    native_side_effect_count: int = 0
    prepared_authority_digest: str | None = None
    static_bindings_digest: str | None = None
    binding_schema_digest: str | None = None
    manifest_sha256: str | None = None
    issued_unix_ns: int | None = None
    expires_unix_ns: int | None = None
    receipt_digest: str | None = None

    @property
    def native_side_effects(self) -> bool:
        return self.native_side_effect_count > 0


class _PreparationComposition(Protocol):
    def prepare(self) -> D1N2PreparationResult: ...

    def revalidate_for_run(self) -> bool: ...

    def consume(self) -> PersistenceOutcome: ...

    def issue_grant(self, binding: WorkerGrantBindingAttestation) -> PersistenceOutcome: ...

    def take_grant_capability(self) -> bytes | None: ...

    def grant_record_bytes(self) -> bytes | None: ...

    def authorize_grant(self, capability: bytes) -> PersistenceOutcome: ...

    def revoke_grant(self) -> PersistenceOutcome: ...

    def terminalize(self, binding: TerminalBindingAttestation) -> PersistenceOutcome: ...

    def abort_pre_bridge(self) -> object: ...

    def transfer_to_bridge(self) -> ExecutionOwnership | None: ...


class _CompositionFactory(Protocol):
    def open(self) -> _PreparationComposition: ...


class _Driver(Protocol):
    def run(self, request: D1N2ExecutionRequest) -> D1N2DriverResult: ...


class _LazyProductionCompositionFactory:
    def open(self) -> _PreparationComposition:
        return D1N2PreparedProductionFactory().open()


def _production_driver() -> _Driver:
    from pdu_exam_observer.m2_d1_n2_native import D1N2WindowsCaptureDriver

    return D1N2WindowsCaptureDriver()


class _RetainedEpochController:
    """One forward-only controller; persisted PREPARED cannot reconstruct it."""

    def __init__(
        self,
        composition_factory: _CompositionFactory,
        driver_factory: Callable[[], _Driver],
    ) -> None:
        self._composition_factory = composition_factory
        self._driver_factory = driver_factory
        self._state = D1N2ControllerState.UNINITIALIZED
        self._composition: _PreparationComposition | None = None
        self._prepared: D1N2PreparationResult | None = None
        self._lock = threading.RLock()

    @classmethod
    def production(cls) -> _RetainedEpochController:
        return cls(_LazyProductionCompositionFactory(), _production_driver)

    @property
    def state(self) -> D1N2ControllerState:
        return self._state

    def prepare(self) -> D1N2EntrypointResult:
        with self._lock:
            if self._state is not D1N2ControllerState.UNINITIALIZED:
                return D1N2EntrypointResult(D1N2EntrypointStatus.ALREADY_USED)
            self._state = D1N2ControllerState.PREPARING
            composition: _PreparationComposition | None = None
            try:
                composition = self._composition_factory.open()
                prepared = composition.prepare()
            except BaseException as primary:
                report = composition.abort_pre_bridge() if composition is not None else None
                self._state = D1N2ControllerState.FAILED_NONLAUNCHABLE
                if isinstance(primary, KeyboardInterrupt | SystemExit):
                    if getattr(report, "status", None) is AbortStatus.UNCERTAIN:
                        raise BaseExceptionGroup(
                            "D1-N2 preparation interrupted with cleanup ambiguity",
                            [primary, RuntimeError("pre-bridge cleanup uncertain")],
                        ) from primary
                    raise
                return D1N2EntrypointResult(
                    D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
                )
            if (
                prepared.outcome is not PersistenceOutcome.OK
                or prepared.attestation is None
                or prepared.prepared_bytes is None
                or prepared.prepared_authority_digest is None
                or prepared.retained_device_name is None
            ):
                composition.abort_pre_bridge()
                self._state = D1N2ControllerState.FAILED_NONLAUNCHABLE
                if prepared.a0_status is A0VerificationStatus.BOOTSTRAP_UNPROVISIONED:
                    return D1N2EntrypointResult(
                        D1N2EntrypointStatus.AUTHORITY_NOT_ISSUED
                    )
                return D1N2EntrypointResult(
                    D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
                )
            self._composition = composition
            self._prepared = prepared
            self._state = D1N2ControllerState.PREPARED_WAITING_A1
            attestation = prepared.attestation
            return D1N2EntrypointResult(
                D1N2EntrypointStatus.PREPARED_WAITING_A1,
                prepared_authority_digest=prepared.prepared_authority_digest,
                static_bindings_digest=attestation.static_bindings_digest,
                binding_schema_digest=attestation.binding_schema_digest,
                manifest_sha256=attestation.manifest_sha256,
                issued_unix_ns=attestation.issued_unix_ns,
                expires_unix_ns=attestation.expires_unix_ns,
            )

    def run(self) -> D1N2EntrypointResult:
        with self._lock:
            if self._state is D1N2ControllerState.UNINITIALIZED:
                self._state = D1N2ControllerState.FAILED_NONLAUNCHABLE
                return D1N2EntrypointResult(
                    D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
                )
            if self._state is not D1N2ControllerState.PREPARED_WAITING_A1:
                return D1N2EntrypointResult(D1N2EntrypointStatus.ALREADY_USED)
            composition = self._composition
            prepared = self._prepared
            if (
                composition is None
                or prepared is None
                or prepared.retained_device_name is None
                or prepared.prepared_authority_digest is None
            ):
                self._state = D1N2ControllerState.FAILED_NONLAUNCHABLE
                return D1N2EntrypointResult(
                    D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
                )
            self._state = D1N2ControllerState.CONSUMED
            ownership: ExecutionOwnership | None = None
            try:
                driver = self._driver_factory()
                ownership = composition.transfer_to_bridge()
                if ownership is None:
                    composition.abort_pre_bridge()
                    self._state = D1N2ControllerState.FAILED_NONLAUNCHABLE
                    return D1N2EntrypointResult(
                        D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
                    )
                self._composition = None
                bridge = D1N2ExecutionBridge(
                    ownership,
                    driver,
                    device_name=prepared.retained_device_name,
                    prepared_authority_digest=prepared.prepared_authority_digest,
                    prepared_attestation=prepared.attestation,
                )
                result = bridge.run()
            except BaseException as primary:
                report = (
                    ownership.abort_after_transfer()
                    if ownership is not None
                    else composition.abort_pre_bridge()
                )
                self._state = D1N2ControllerState.FAILED_NONLAUNCHABLE
                if isinstance(primary, KeyboardInterrupt | SystemExit):
                    if getattr(report, "status", None) is AbortStatus.UNCERTAIN:
                        raise BaseExceptionGroup(
                            "D1-N2 execution interrupted with cleanup ambiguity",
                            [primary, RuntimeError("execution ownership cleanup uncertain")],
                        ) from primary
                    raise
                return D1N2EntrypointResult(
                    D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
                )
            if result.status is D1N2ExecutionStatus.TERMINAL:
                self._state = D1N2ControllerState.TERMINAL
                return D1N2EntrypointResult(
                    D1N2EntrypointStatus.TERMINAL,
                    native_side_effect_count=result.native_side_effect_count,
                    receipt_digest=result.receipt_digest,
                )
            self._state = D1N2ControllerState.FAILED_NONLAUNCHABLE
            return D1N2EntrypointResult(
                D1N2EntrypointStatus.FAILED_NONLAUNCHABLE,
                native_side_effect_count=result.native_side_effect_count,
            )


_controller_lock = threading.RLock()
_controller = _RetainedEpochController.production()


def prepare_d1_n2() -> D1N2EntrypointResult:
    """Perform one fixed no-stream preparation and then stop for external A1."""

    with _controller_lock:
        return _controller.prepare()


def run_d1_n2_preflight() -> D1N2EntrypointResult:
    """Explicit same-process run boundary; never called automatically by prepare."""

    with _controller_lock:
        return _controller.run()


def verify_d1_n2_receipt_semantics(receipt: object) -> bool:
    from pdu_exam_observer.m2_d1_n2_evidence import verify_worker_candidate_envelope

    return verify_worker_candidate_envelope(receipt)

def verify_d1_n2_terminal(receipt: object) -> bool:
    return (
        type(receipt) is D1N2EntrypointResult
        and receipt.status is D1N2EntrypointStatus.TERMINAL
        and type(receipt.native_side_effect_count) is int
        and receipt.native_side_effect_count == 1
        and type(receipt.receipt_digest) is str
        and len(receipt.receipt_digest) == 64
        and all(character in "0123456789abcdef" for character in receipt.receipt_digest)
        and receipt.prepared_authority_digest is None
        and receipt.static_bindings_digest is None
        and receipt.binding_schema_digest is None
        and receipt.manifest_sha256 is None
        and receipt.issued_unix_ns is None
        and receipt.expires_unix_ns is None
    )
