from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

import pdu_exam_observer.m2_d1_n2_entrypoint as entrypoint
from pdu_exam_observer.m2_d1_n2_adapter import D1N2PreparationResult
from pdu_exam_observer.m2_d1_n2_canonical import (
    AUTHORITY_REVISION,
    PREPARED_TTL_NS,
    PersistenceOutcome,
    PreparedBindingAttestation,
    TerminalBindingAttestation,
    WorkerGrantBindingAttestation,
)
from pdu_exam_observer.m2_d1_n2_evidence import (
    CAPTURE_POLICY_DIGEST,
    WATCHDOG_POLICY_DIGEST,
    RetainedLeaseCleanup,
    build_sanitized_no_go_evidence,
)
from pdu_exam_observer.m2_d1_n2_native import (
    D1N2DriverResult,
    D1N2DriverStatus,
    D1N2ExecutionRequest,
)


def _attestation() -> PreparedBindingAttestation:
    digest = "a" * 64
    return PreparedBindingAttestation(
        authority_revision=AUTHORITY_REVISION,
        schema_version=3,
        static_bindings_digest=digest,
        binding_schema_digest=digest,
        manifest_sha256=digest,
        camera_count=1,
        camera_status="PRESENT_OK",
        opaque_device_token=digest,
        supervisor_path_digest=digest,
        supervisor_sha256=digest,
        supervisor_size_bytes=1,
        supervisor_identity_digest=digest,
        ffmpeg_path_digest=digest,
        ffmpeg_sha256=digest,
        ffmpeg_size_bytes=1,
        ffmpeg_identity_digest=digest,
        ffmpeg_version_digest=digest,
        dependency_observation_digest=digest,
        pose_model_sha256=digest,
        pose_model_size_bytes=1,
        face_model_sha256=digest,
        face_model_size_bytes=1,
        authorization_nonce_digest=digest,
        issued_unix_ns=1_000,
        expires_unix_ns=1_000 + PREPARED_TTL_NS,
    )


class _Composition:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def prepare(self) -> D1N2PreparationResult:
        self.events.append("prepare")
        return D1N2PreparationResult(
            PersistenceOutcome.OK,
            _attestation(),
            b"prepared",
            "b" * 64,
            "Integrated Camera",
        )

    def abort_pre_bridge(self) -> object:
        self.events.append("abort_pre_bridge")
        return SimpleNamespace(status=entrypoint.AbortStatus.CLEAN)

    def transfer_to_bridge(self):  # type: ignore[no-untyped-def]
        self.events.append("transfer")
        return self

    def abort_after_transfer(self) -> object:
        self.events.append("abort_after_transfer")
        return SimpleNamespace(status=entrypoint.AbortStatus.CLEAN)

    def revalidate_for_run(self) -> bool:
        self.events.append("revalidate")
        return True

    def consume(self) -> PersistenceOutcome:
        self.events.append("consume")
        return PersistenceOutcome.OK

    def issue_grant(self, binding: WorkerGrantBindingAttestation) -> PersistenceOutcome:
        self.events.append("issue")
        assert binding.valid()
        return PersistenceOutcome.OK

    def take_grant_capability(self) -> bytes | None:
        self.events.append("take")
        return b"g" * 32

    def grant_record_bytes(self) -> bytes | None:
        self.events.append("record")
        return b"grant-record"

    def authorize_grant(self, _capability: bytes) -> PersistenceOutcome:
        self.events.append("authorize")
        return PersistenceOutcome.OK

    def revoke_grant(self) -> PersistenceOutcome:
        self.events.append("revoke")
        return PersistenceOutcome.OK

    def close_retained_for_terminal(self) -> RetainedLeaseCleanup:
        self.events.append("close_retained")
        return RetainedLeaseCleanup(True, True, True)

    def terminalize(self, binding: TerminalBindingAttestation) -> PersistenceOutcome:
        self.events.append("terminal")
        assert binding.valid()
        return PersistenceOutcome.OK


class _CompositionFactory:
    def __init__(self, composition: _Composition, events: list[str]) -> None:
        self.composition = composition
        self.events = events

    def open(self) -> _Composition:
        self.events.append("open")
        return self.composition


class _Driver:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def run(self, request: D1N2ExecutionRequest) -> D1N2DriverResult:
        self.events.append("driver")
        assert request.device_name == "Integrated Camera"
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
        return D1N2DriverResult(
            D1N2DriverStatus.COMPLETED,
            1,
            evidence.receipt_digest,
            True,
            True,
            True,
            evidence.receipt_json.encode(),
            evidence.failure_ledger_json.encode(),
        )


def test_retained_controller_prepare_stops_for_a1_then_same_process_run_terminalizes() -> None:
    events: list[str] = []
    composition = _Composition(events)
    controller = entrypoint._RetainedEpochController(
        _CompositionFactory(composition, events),
        lambda: events.append("driver_factory") or _Driver(events),
    )

    prepared = controller.prepare()

    assert prepared.status is entrypoint.D1N2EntrypointStatus.PREPARED_WAITING_A1
    assert prepared.prepared_authority_digest == "b" * 64
    assert prepared.static_bindings_digest == "a" * 64
    assert prepared.native_side_effect_count == 0
    assert events == ["open", "prepare"]
    assert controller.prepare().status is entrypoint.D1N2EntrypointStatus.ALREADY_USED

    terminal = controller.run()

    assert terminal.status is entrypoint.D1N2EntrypointStatus.TERMINAL
    assert terminal.native_side_effect_count == 1
    assert terminal.receipt_digest is not None
    assert events == [
        "open",
        "prepare",
        "driver_factory",
        "transfer",
        "revalidate",
        "consume",
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
    assert controller.run().status is entrypoint.D1N2EntrypointStatus.ALREADY_USED


def test_retained_controller_run_without_live_prepare_has_zero_native_side_effects() -> None:
    events: list[str] = []
    controller = entrypoint._RetainedEpochController(
        _CompositionFactory(_Composition(events), events),
        lambda: events.append("driver_factory") or _Driver(events),
    )

    result = controller.run()

    assert result.status is entrypoint.D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
    assert result.native_side_effect_count == 0
    assert events == []


def test_controller_aborts_pre_transfer_on_driver_factory_exception() -> None:
    events: list[str] = []
    composition = _Composition(events)
    controller = entrypoint._RetainedEpochController(
        _CompositionFactory(composition, events),
        lambda: (_ for _ in ()).throw(RuntimeError("driver factory failed")),
    )
    assert controller.prepare().status is entrypoint.D1N2EntrypointStatus.PREPARED_WAITING_A1

    result = controller.run()

    assert result.status is entrypoint.D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
    assert events == ["open", "prepare", "abort_pre_bridge"]


def test_controller_preserves_keyboard_interrupt_after_pre_bridge_abort() -> None:
    events: list[str] = []
    composition = _Composition(events)
    composition.prepare = lambda: (_ for _ in ()).throw(KeyboardInterrupt())  # type: ignore[method-assign]
    controller = entrypoint._RetainedEpochController(
        _CompositionFactory(composition, events),
        lambda: _Driver(events),
    )

    with pytest.raises(KeyboardInterrupt):
        controller.prepare()

    assert events == ["open", "abort_pre_bridge"]


def test_controller_aborts_transferred_owner_if_bridge_construction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    composition = _Composition(events)
    controller = entrypoint._RetainedEpochController(
        _CompositionFactory(composition, events),
        lambda: _Driver(events),
    )
    assert controller.prepare().status is entrypoint.D1N2EntrypointStatus.PREPARED_WAITING_A1
    monkeypatch.setattr(
        entrypoint,
        "D1N2ExecutionBridge",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("bridge failed")),
    )

    result = controller.run()

    assert result.status is entrypoint.D1N2EntrypointStatus.FAILED_NONLAUNCHABLE
    assert events == [
        "open",
        "prepare",
        "transfer",
        "abort_after_transfer",
    ]


def test_public_entrypoints_are_parameter_free_without_invoking_production_wrappers() -> None:
    assert list(inspect.signature(entrypoint.prepare_d1_n2).parameters) == []
    assert list(inspect.signature(entrypoint.run_d1_n2_preflight).parameters) == []
    assert "_controller.prepare()" in inspect.getsource(entrypoint.prepare_d1_n2)
    assert "_controller.run()" in inspect.getsource(entrypoint.run_d1_n2_preflight)
    assert entrypoint.verify_d1_n2_receipt_semantics({"outcome": "PASS"}) is False
    assert entrypoint.verify_d1_n2_terminal({"terminal": True}) is False
    with pytest.raises(TypeError):
        entrypoint.prepare_d1_n2("unexpected")  # type: ignore[call-arg]


def _valid_worker_receipt() -> dict[str, object]:
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
    return {
        "receipt": json.loads(evidence.receipt_json),
        "failure_ledger": json.loads(evidence.failure_ledger_json),
    }


def test_pure_receipt_and_terminal_verifiers_accept_only_closed_pass_shapes() -> None:
    receipt = _valid_worker_receipt()
    terminal = entrypoint.D1N2EntrypointResult(
        entrypoint.D1N2EntrypointStatus.TERMINAL,
        native_side_effect_count=1,
        receipt_digest="c" * 64,
    )

    assert entrypoint.verify_d1_n2_receipt_semantics(receipt)
    assert entrypoint.verify_d1_n2_terminal(terminal)
    assert not entrypoint.verify_d1_n2_receipt_semantics(
        {**receipt, "receipt": {**receipt["receipt"], "raw_retained": 0.0}}
    )
    assert not entrypoint.verify_d1_n2_receipt_semantics(
        {**receipt, "authority_revision": AUTHORITY_REVISION}
    )
    assert not entrypoint.verify_d1_n2_receipt_semantics(
        {
            **receipt,
            "receipt": {**receipt["receipt"], "device_gate_decision": "D1_GO"},
        }
    )
    assert not entrypoint.verify_d1_n2_terminal(
        entrypoint.D1N2EntrypointResult(
            entrypoint.D1N2EntrypointStatus.TERMINAL,
            native_side_effect_count=0,
            receipt_digest="c" * 64,
        )
    )


def test_production_controller_construction_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("production dependencies must remain lazy")

    monkeypatch.setattr(entrypoint, "D1N2PreparedProductionFactory", explode)
    controller = entrypoint._RetainedEpochController.production()

    assert controller.state is entrypoint.D1N2ControllerState.UNINITIALIZED
