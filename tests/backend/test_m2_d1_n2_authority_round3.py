"""Fake-only H3 authority lifecycle tests; no native or filesystem access."""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field

import pytest

from pdu_exam_observer.m2_d1_n2_a0 import ApprovedRP2Triple
from pdu_exam_observer.m2_d1_n2_canonical import (
    PREPARED_TTL_NS,
    WORKER_GRANT_TTL_NS,
    AuthorityLeaf,
    BeginResult,
    CanonicalInjectableAuthorityLifecycle,
    CanonicalInspection,
    CanonicalLifecycleState,
    DurabilityStatus,
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
from pdu_exam_observer.m2_d1_n2_evidence import (
    CAPTURE_POLICY_DIGEST,
    WATCHDOG_POLICY_DIGEST,
    RetainedLeaseCleanup,
    build_sanitized_no_go_evidence,
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


@dataclass
class _Clock:
    now: int = 100

    def __call__(self) -> int:
        return self.now


def _attestation(*, issued_unix_ns: int = 1_000) -> PreparedBindingAttestation:
    return PreparedBindingAttestation(
        authority_revision="d1-n2-authority-v1",
        schema_version=3,
        static_bindings_digest="a" * 64,
        binding_schema_digest="b" * 64,
        manifest_sha256="c" * 64,
        camera_count=1,
        camera_status="PRESENT_OK",
        opaque_device_token="d" * 64,
        supervisor_path_digest="e" * 64,
        supervisor_sha256="f" * 64,
        supervisor_size_bytes=100,
        supervisor_identity_digest="1" * 64,
        ffmpeg_path_digest="2" * 64,
        ffmpeg_sha256="3" * 64,
        ffmpeg_size_bytes=200,
        ffmpeg_identity_digest="4" * 64,
        ffmpeg_version_digest="5" * 64,
        dependency_observation_digest="6" * 64,
        pose_model_sha256="7" * 64,
        pose_model_size_bytes=300,
        face_model_sha256="8" * 64,
        face_model_size_bytes=400,
        authorization_nonce_digest="9" * 64,
        issued_unix_ns=issued_unix_ns,
        expires_unix_ns=issued_unix_ns + PREPARED_TTL_NS,
    )


def _approved() -> ApprovedRP2Triple:
    return ApprovedRP2Triple(
        static_bindings_digest="a" * 64,
        binding_schema_canonical_sha256="b" * 64,
        candidate_exact_bytes_sha256="c" * 64,
        a0_approval_digest="0" * 64,
        approval_id_digest="1" * 64,
        issued_unix_ns=1,
        expires_unix_ns=900_000_000_001,
    )


def _worker_binding(
    lifecycle: CanonicalInjectableAuthorityLifecycle,
) -> WorkerGrantBindingAttestation:
    assert lifecycle.prepared_record is not None
    return WorkerGrantBindingAttestation(
        prepared_authority_digest=hashlib.sha256(lifecycle.prepared_record).hexdigest(),
        worker_sha256="b" * 64,
        worker_size_bytes=1,
        worker_identity_digest="c" * 64,
        worker_argv_digest="d" * 64,
        worker_job_policy_digest="e" * 64,
        challenge_digest="2" * 64,
        job_name_digest="3" * 64,
        duration_seconds=60,
        video_only=True,
        retry=False,
    )


def _terminal_binding(
    lifecycle: CanonicalInjectableAuthorityLifecycle | None = None,
) -> TerminalBindingAttestation:
    prepared_digest = "a" * 64
    grant_digest = "a" * 64
    challenge_digest = "a" * 64
    job_name_digest = "a" * 64
    runtime_digest = "a" * 64
    pose_model_sha256 = "a" * 64
    face_model_sha256 = "a" * 64
    if lifecycle is not None:
        assert lifecycle.prepared_record is not None
        prepared_digest = hashlib.sha256(lifecycle.prepared_record).hexdigest()
        if lifecycle.grant_record is not None:
            grant_digest = hashlib.sha256(lifecycle.grant_record).hexdigest()
            grant = json.loads(lifecycle.grant_record)
            challenge_digest = grant["challenge_digest"]
            job_name_digest = grant["job_name_digest"]
        runtime_digest = "6" * 64
        pose_model_sha256 = "7" * 64
        face_model_sha256 = "8" * 64
    evidence = build_sanitized_no_go_evidence(
        failure_code="AUTHORIZATION_FAILED",
        authority_digest=prepared_digest,
        grant_record_digest=grant_digest,
        challenge_digest=challenge_digest,
        job_name_digest=job_name_digest,
        static_bindings_digest="a" * 64,
        capture_policy_digest=CAPTURE_POLICY_DIGEST,
        watchdog_policy_digest=WATCHDOG_POLICY_DIGEST,
        runtime_digest=runtime_digest,
        pose_model_sha256=pose_model_sha256,
        face_model_sha256=face_model_sha256,
        retained_cleanup=RetainedLeaseCleanup(True, True, True),
    )
    assert evidence is not None
    return TerminalBindingAttestation.from_evidence(evidence, 0)


@dataclass
class _Session:
    log: list[str]
    write_permitted: bool = True
    before: list[ValidationStatus] = field(default_factory=list)
    after: list[ValidationStatus] = field(default_factory=list)
    durable: list[DurabilityStatus] = field(default_factory=list)
    a0: list[ApprovedRP2Triple | None] = field(default_factory=list)
    attest: list[PreparedBindingAttestation | None] = field(default_factory=list)
    lease_close: StepStatus = StepStatus.CLEAN
    mutex_release: StepStatus = StepStatus.CLEAN
    mutex_close: StepStatus = StepStatus.CLEAN

    @staticmethod
    def _pop(values: list[object], default: object) -> object:
        return values.pop(0) if values else default

    def validate_before(self) -> ValidationStatus:
        self.log.append("validate_before")
        return self._pop(self.before, ValidationStatus.VALID)  # type: ignore[return-value]

    def validate_after(self) -> ValidationStatus:
        self.log.append("validate_after")
        return self._pop(self.after, ValidationStatus.VALID)  # type: ignore[return-value]

    def parent_durable(self) -> DurabilityStatus:
        self.log.append("parent_durable")
        return self._pop(self.durable, DurabilityStatus.VERIFIED)  # type: ignore[return-value]

    def attest_a0_before_pending(self) -> ApprovedRP2Triple | None:
        self.log.append("attest_a0_before_pending")
        return self._pop(self.a0, _approved())  # type: ignore[return-value]

    def attest_pending(self) -> PreparedBindingAttestation | None:
        self.log.append("attest_pending")
        return self._pop(self.attest, _attestation())  # type: ignore[return-value]

    def close_leases(self) -> StepStatus:
        self.log.append("close_leases")
        return self.lease_close

    def release_mutex(self) -> StepStatus:
        self.log.append("release_mutex")
        return self.mutex_release

    def close_mutex(self) -> StepStatus:
        self.log.append("close_mutex")
        return self.mutex_close


class _Guard:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.queue: list[BeginResult] = []

    def enqueue(
        self,
        session: _Session | None = None,
        owner: OwnerStatus = OwnerStatus.ACQUIRED,
    ) -> _Session:
        selected = session or _Session(self.log)
        self.queue.append(BeginResult(owner, selected))
        return selected

    def begin(self, operation: OperationKind) -> BeginResult:
        self.log.append(f"begin:{operation.value}")
        if self.queue:
            return self.queue.pop(0)
        return BeginResult(OwnerStatus.ACQUIRED, _Session(self.log))


class _Store:
    def __init__(self) -> None:
        self.records: dict[AuthorityLeaf, bytes] = {}
        self.durability: dict[AuthorityLeaf, DurabilityStatus] = {}
        self.inspection_states: dict[AuthorityLeaf, CanonicalLifecycleState] = {}
        self.create_results: list[WriteResult] = []
        self.cas_results: list[WriteResult] = []
        self.write_calls: list[tuple[str, AuthorityLeaf]] = []

    @staticmethod
    def _state(record: bytes) -> CanonicalLifecycleState:
        try:
            domain = json.loads(record)["domain"]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
            return CanonicalLifecycleState.PRESENT_INVALID
        return {
            "D1N2/PENDING/v1": CanonicalLifecycleState.PENDING,
            "D1N2/PREPARED/v1": CanonicalLifecycleState.PREPARED,
            "D1N2/CONSUMED/v1": CanonicalLifecycleState.CONSUMED_NO_GRANT,
            "D1N2/GRANT_ISSUED/v1": CanonicalLifecycleState.ISSUED,
            "D1N2/GRANT_REVOKED/v1": CanonicalLifecycleState.REVOKED_TERMINAL_PENDING,
            "D1N2/TERMINAL/v1": CanonicalLifecycleState.TERMINAL,
        }.get(domain, CanonicalLifecycleState.PRESENT_INVALID)

    def inspect(self, session: _Session, leaf: AuthorityLeaf) -> CanonicalInspection:
        session.log.append(f"inspect:{leaf.value}")
        record = self.records.get(leaf)
        return CanonicalInspection(
            self.inspection_states.get(
                leaf,
                CanonicalLifecycleState.ABSENT if record is None else self._state(record),
            ),
            record,
            self.durability.get(leaf, DurabilityStatus.VERIFIED),
        )

    @staticmethod
    def _apply(
        records: dict[AuthorityLeaf, bytes],
        leaf: AuthorityLeaf,
        record: bytes,
        result: WriteResult,
    ) -> WriteResult:
        observed = result.observed_bytes
        if result.disposition is WriteDisposition.PRESENT_VALID:
            observed = record if observed is None else observed
            records[leaf] = observed
        elif result.disposition is WriteDisposition.PRESENT_INVALID:
            observed = b"{"
            records[leaf] = observed
        elif result.disposition is WriteDisposition.PRESENT_UNKNOWN:
            observed = b"partial"
            records[leaf] = observed
        return WriteResult(result.outcome, result.disposition, observed)

    def create_exact(
        self, session: _Session, leaf: AuthorityLeaf, record: bytes
    ) -> WriteResult:
        session.log.append(f"create:{leaf.value}")
        self.write_calls.append(("create", leaf))
        if leaf in self.records:
            return WriteResult(
                PersistenceOutcome.CREATE_FAILED, WriteDisposition.ZERO_WRITE
            )
        result = self.create_results.pop(0) if self.create_results else WriteResult(
            PersistenceOutcome.OK, WriteDisposition.PRESENT_VALID
        )
        return self._apply(self.records, leaf, record, result)

    def cas_exact(
        self,
        session: _Session,
        leaf: AuthorityLeaf,
        prior: bytes,
        record: bytes,
    ) -> WriteResult:
        session.log.append(f"cas:{leaf.value}")
        self.write_calls.append(("cas", leaf))
        if self.records.get(leaf) != prior:
            return WriteResult(
                PersistenceOutcome.CAS_MISMATCH, WriteDisposition.ZERO_WRITE
            )
        result = self.cas_results.pop(0) if self.cas_results else WriteResult(
            PersistenceOutcome.OK, WriteDisposition.PRESENT_VALID
        )
        return self._apply(self.records, leaf, record, result)


def _new(
    *,
    store: _Store | None = None,
    guard: _Guard | None = None,
    epoch: bytes = b"e" * 32,
    grant: bytes = b"g" * 32,
    clock: _Clock | None = None,
    unix_clock: _Clock | None = None,
) -> tuple[CanonicalInjectableAuthorityLifecycle, _Store, _Guard, _Clock]:
    selected_store = store or _Store()
    selected_guard = guard or _Guard()
    selected_clock = clock or _Clock()
    lifecycle = CanonicalInjectableAuthorityLifecycle(
        selected_store,
        selected_guard,
        entropy=lambda _: epoch,
        grant_entropy=lambda _: grant,
        clock_ns=selected_clock,
        unix_clock_ns=unix_clock or _Clock(1_000),
    )
    selected_guard.log.clear()
    return lifecycle, selected_store, selected_guard, selected_clock


def _consumed() -> tuple[
    CanonicalInjectableAuthorityLifecycle, _Store, _Guard, _Clock
]:
    lifecycle, store, guard, clock = _new()
    assert lifecycle.prepare() is PersistenceOutcome.OK
    assert lifecycle.consume() is PersistenceOutcome.OK
    return lifecycle, store, guard, clock


def test_round3_fixed_leaves_and_parameter_free_policy() -> None:
    assert {leaf.value for leaf in AuthorityLeaf} == {
        "prepared.v3.json",
        "worker-grant.v2.json",
        "terminal.v3.json",
    }
    assert list(
        inspect.signature(CanonicalInjectableAuthorityLifecycle.prepare).parameters
    ) == ["self"]
    assert list(
        inspect.signature(CanonicalInjectableAuthorityLifecycle.issue_grant).parameters
    ) == ["self", "binding"]
    assert list(
        inspect.signature(CanonicalInjectableAuthorityLifecycle.authorize_grant).parameters
    ) == ["self", "presented_raw"]


def test_round3_prepare_consume_exact_order() -> None:
    lifecycle, store, guard, _ = _new()
    assert lifecycle.prepare() is PersistenceOutcome.OK
    assert guard.log == [
        "begin:PREPARE",
        "validate_before",
        "inspect:prepared.v3.json",
        "attest_a0_before_pending",
        "create:prepared.v3.json",
        "validate_after",
        "parent_durable",
        "attest_pending",
        "validate_before",
        "cas:prepared.v3.json",
        "validate_after",
        "parent_durable",
        "close_leases",
        "release_mutex",
        "close_mutex",
    ]
    assert json.loads(store.records[AuthorityLeaf.PREPARED])["domain"] == "D1N2/PREPARED/v1"
    guard.log.clear()
    assert lifecycle.consume() is PersistenceOutcome.OK
    assert json.loads(store.records[AuthorityLeaf.PREPARED])["domain"] == "D1N2/CONSUMED/v1"
    assert guard.log[-3:] == ["close_leases", "release_mutex", "close_mutex"]


def test_round3_missing_a0_writes_no_pending_or_native_attestation() -> None:
    lifecycle, store, guard, _ = _new()
    session = _Session(guard.log, a0=[None])
    guard.enqueue(session)

    assert lifecycle.prepare() is PersistenceOutcome.ATTESTATION_FAILED
    assert AuthorityLeaf.PREPARED not in store.records
    assert "attest_pending" not in guard.log


def test_round3_rp2_mismatch_leaves_a0_bound_pending_sticky() -> None:
    lifecycle, store, guard, _ = _new()
    mismatched = _attestation()
    object.__setattr__(mismatched, "manifest_sha256", "f" * 64)
    guard.enqueue(_Session(guard.log, attest=[mismatched]))

    assert lifecycle.prepare() is PersistenceOutcome.ATTESTATION_FAILED
    pending = json.loads(store.records[AuthorityLeaf.PREPARED])
    assert pending["domain"] == "D1N2/PENDING/v1"
    assert pending["a0_approval_digest"] == "0" * 64
    assert lifecycle.prepare() is PersistenceOutcome.INPUT_INVALID


def test_round3_restart_prepared_is_stale_without_write() -> None:
    lifecycle, store, _, _ = _new(epoch=b"a" * 32)
    assert lifecycle.prepare() is PersistenceOutcome.OK
    writes = len(store.write_calls)
    restarted, _, _, _ = _new(store=store, epoch=b"z" * 32)
    assert restarted.state is CanonicalLifecycleState.STALE_PREPARED_NONLAUNCHABLE
    assert restarted.consume() is PersistenceOutcome.CAS_MISMATCH
    assert len(store.write_calls) == writes


@pytest.mark.parametrize("step", ["lease_close", "mutex_release", "mutex_close"])
def test_round3_not_held_cleanup_never_yields_live_authority(step: str) -> None:
    lifecycle, _, guard, _ = _new()
    session = _Session(guard.log)
    setattr(session, step, StepStatus.NOT_HELD)
    guard.enqueue(session)
    assert lifecycle.prepare() is PersistenceOutcome.CLEANUP_FAILED
    assert lifecycle.state is CanonicalLifecycleState.PREPARED_NONLAUNCHABLE
    assert session.log[-3:] == ["close_leases", "release_mutex", "close_mutex"]
    assert lifecycle.consume() is PersistenceOutcome.CAS_MISMATCH


@pytest.mark.parametrize(
    ("result", "state"),
    [
        (
            WriteResult(PersistenceOutcome.READBACK_FAILED, WriteDisposition.PRESENT_VALID),
            CanonicalLifecycleState.PENDING,
        ),
        (
            WriteResult(PersistenceOutcome.CLOSE_FAILED, WriteDisposition.PRESENT_INVALID),
            CanonicalLifecycleState.PRESENT_INVALID,
        ),
    ],
)
def test_round3_ambiguous_create_is_sticky(
    result: WriteResult, state: CanonicalLifecycleState
) -> None:
    store = _Store()
    store.create_results.append(result)
    lifecycle, _, _, _ = _new(store=store)
    assert lifecycle.prepare() is result.outcome
    assert lifecycle.state is state
    calls = len(store.write_calls)
    assert lifecycle.prepare() is PersistenceOutcome.INPUT_INVALID
    assert len(store.write_calls) == calls


def test_round3_fixed_ttl_and_clock_bound_authorization() -> None:
    lifecycle, store, _, clock = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    issued = json.loads(store.records[AuthorityLeaf.GRANT])
    assert issued["issued_monotonic_ns"] == 100
    assert issued["expires_monotonic_ns"] == 100 + WORKER_GRANT_TTL_NS
    raw = lifecycle.take_grant_capability()
    assert raw == b"g" * 32
    clock.now = 100 + WORKER_GRANT_TTL_NS
    assert lifecycle.authorize_grant(raw) is PersistenceOutcome.OK
    assert lifecycle.authorize_grant(raw) is PersistenceOutcome.GRANT_NOT_AUTHORIZED


def test_round3_expired_grant_cannot_use_but_can_revoke() -> None:
    lifecycle, _, _, clock = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    raw = lifecycle.take_grant_capability()
    assert raw is not None
    clock.now = 101 + WORKER_GRANT_TTL_NS
    assert lifecycle.authorize_grant(raw) is PersistenceOutcome.GRANT_NOT_AUTHORIZED
    assert lifecycle.revoke_grant() is PersistenceOutcome.OK


def test_round3_grant_failure_terminalizes_not_issued() -> None:
    lifecycle, store, _, _ = _consumed()
    lifecycle._grant_entropy = lambda _: (_ for _ in ()).throw(RuntimeError("entropy"))
    assert (
        lifecycle.issue_grant(_worker_binding(lifecycle))
        is PersistenceOutcome.GRANT_ENTROPY_FAILED
    )
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is PersistenceOutcome.OK
    terminal = json.loads(store.records[AuthorityLeaf.TERMINAL])
    assert terminal["grant_disposition"] == "NOT_ISSUED"


def test_round3_revoked_terminal_survives_strict_restart_validation() -> None:
    lifecycle, store, _, _ = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    assert lifecycle.revoke_grant() is PersistenceOutcome.OK
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is PersistenceOutcome.OK
    restarted, _, _, _ = _new(store=store, epoch=b"z" * 32)
    assert restarted.state is CanonicalLifecycleState.TERMINAL


def test_round3_restart_rejects_self_consistent_receipt_detached_from_consumed() -> None:
    lifecycle, store, _, _ = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    assert lifecycle.revoke_grant() is PersistenceOutcome.OK
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is PersistenceOutcome.OK
    terminal = json.loads(store.records[AuthorityLeaf.TERMINAL])
    receipt = json.loads(terminal["receipt_json"])
    receipt["static_bindings_digest"] = "0" * 64
    terminal["receipt_json"] = _canonical(receipt).decode()
    terminal["receipt_digest"] = hashlib.sha256(
        terminal["receipt_json"].encode()
    ).hexdigest()
    store.records[AuthorityLeaf.TERMINAL] = _canonical(terminal)

    restarted, _, _, _ = _new(store=store, epoch=b"z" * 32)

    assert restarted.state is CanonicalLifecycleState.PRESENT_INVALID


@pytest.mark.parametrize(
    "field",
    [
        "authority_digest",
        "grant_record_digest",
        "challenge_digest",
        "job_name_digest",
        "static_bindings_digest",
        "runtime_digest",
        "pose_model_sha256",
        "face_model_sha256",
    ],
)
def test_round3_self_consistent_receipt_cannot_detach_from_lifecycle(
    field: str,
) -> None:
    lifecycle, _, _, _ = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    assert lifecycle.revoke_grant() is PersistenceOutcome.OK
    valid = _terminal_binding(lifecycle)
    receipt = json.loads(valid.receipt_json)
    receipt[field] = "0" * 64
    receipt_json = _canonical(receipt).decode()
    detached = TerminalBindingAttestation(
        receipt_json=receipt_json,
        receipt_digest=hashlib.sha256(receipt_json.encode()).hexdigest(),
        failure_ledger_json=valid.failure_ledger_json,
        failure_ledger_digest=valid.failure_ledger_digest,
        retained_a0_clean=valid.retained_a0_clean,
        retained_rp2_clean=valid.retained_rp2_clean,
        retained_preparation_clean=valid.retained_preparation_clean,
        native_side_effect_count=valid.native_side_effect_count,
    )
    assert detached.valid()

    assert (
        lifecycle.terminalize(detached)
        is PersistenceOutcome.TERMINAL_NOT_AUTHORIZED
    )


def test_round3_standalone_or_extra_field_terminal_is_invalid() -> None:
    base = {
        "consumed_digest": "c" * 64,
        "domain": "D1N2/TERMINAL/v1",
        "durability_policy": "REVERIFY_PARENT_ON_INSPECTION",
        "grant_disposition": "NOT_ISSUED",
        "grant_record_digest": None,
        "schema_version": 3,
        "state": "TERMINAL",
    }
    for terminal in (base, {**base, "extra": "accepted-by-domain-only-mutant"}):
        store = _Store()
        store.records[AuthorityLeaf.TERMINAL] = _canonical(terminal)
        lifecycle, _, _, _ = _new(store=store)
        assert lifecycle.state is CanonicalLifecycleState.PRESENT_INVALID


def test_round3_terminal_wrong_consumed_digest_is_invalid() -> None:
    lifecycle, store, _, _ = _consumed()
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is PersistenceOutcome.OK
    terminal = json.loads(store.records[AuthorityLeaf.TERMINAL])
    terminal["consumed_digest"] = "0" * 64
    store.records[AuthorityLeaf.TERMINAL] = _canonical(terminal)
    restarted, _, _, _ = _new(store=store)
    assert restarted.state is CanonicalLifecycleState.PRESENT_INVALID


@pytest.mark.parametrize(
    "create_result",
    [
        WriteResult(PersistenceOutcome.READBACK_FAILED, WriteDisposition.PRESENT_VALID),
        WriteResult(PersistenceOutcome.CLOSE_FAILED, WriteDisposition.PRESENT_VALID),
    ],
)
def test_round3_ambiguous_terminal_never_launders_on_restart(
    create_result: WriteResult,
) -> None:
    lifecycle, store, _, _ = _consumed()
    store.create_results.append(create_result)
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is create_result.outcome
    assert lifecycle.state is CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED
    store.durability[AuthorityLeaf.TERMINAL] = DurabilityStatus.UNVERIFIED
    restarted, _, _, _ = _new(store=store, epoch=b"z" * 32)
    assert restarted.state is CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED


def test_round3_parent_durability_failure_requires_fresh_verified_inspection() -> None:
    lifecycle, store, guard, _ = _consumed()
    guard.enqueue(session=_Session(guard.log, durable=[DurabilityStatus.UNVERIFIED]))
    assert (
        lifecycle.terminalize(_terminal_binding(lifecycle))
        is PersistenceOutcome.DURABILITY_FAILED
    )
    store.durability[AuthorityLeaf.TERMINAL] = DurabilityStatus.UNVERIFIED
    restarted, _, _, _ = _new(store=store, epoch=b"z" * 32)
    assert restarted.state is CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED
    store.durability[AuthorityLeaf.TERMINAL] = DurabilityStatus.VERIFIED
    reverified, _, _, _ = _new(store=store, epoch=b"q" * 32)
    assert reverified.state is CanonicalLifecycleState.TERMINAL


def test_round3_terminal_cleanup_failure_stays_unverified_after_restart() -> None:
    lifecycle, store, guard, _ = _consumed()
    guard.enqueue(session=_Session(guard.log, mutex_close=StepStatus.NOT_HELD))
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is PersistenceOutcome.CLEANUP_FAILED
    assert lifecycle.state is CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED
    store.durability[AuthorityLeaf.TERMINAL] = DurabilityStatus.UNVERIFIED
    restarted, _, _, _ = _new(store=store, epoch=b"z" * 32)
    assert restarted.state is CanonicalLifecycleState.TERMINAL_DURABILITY_UNVERIFIED


def test_round3_terminal_rejects_recomputed_revoked_record_with_wrong_epoch() -> None:
    lifecycle, store, _, _ = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    assert lifecycle.revoke_grant() is PersistenceOutcome.OK
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is PersistenceOutcome.OK
    grant = json.loads(store.records[AuthorityLeaf.GRANT])
    grant["epoch_digest"] = "0" * 64
    store.records[AuthorityLeaf.GRANT] = _canonical(grant)
    terminal = json.loads(store.records[AuthorityLeaf.TERMINAL])
    terminal["grant_record_digest"] = hashlib.sha256(
        store.records[AuthorityLeaf.GRANT]
    ).hexdigest()
    store.records[AuthorityLeaf.TERMINAL] = _canonical(terminal)
    restarted, _, _, _ = _new(store=store, epoch=b"z" * 32)
    assert restarted.state is CanonicalLifecycleState.PRESENT_INVALID


@pytest.mark.parametrize("field", ["consumed_digest", "epoch_digest"])
def test_round3_grant_cross_binding_is_strict(field: str) -> None:
    lifecycle, store, _, _ = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    grant = json.loads(store.records[AuthorityLeaf.GRANT])
    grant[field] = "0" * 64
    store.records[AuthorityLeaf.GRANT] = _canonical(grant)
    restarted, _, _, _ = _new(store=store)
    assert restarted.state is CanonicalLifecycleState.PRESENT_INVALID


def test_round3_records_never_persist_raw_or_path_command_fields() -> None:
    lifecycle, store, _, _ = _consumed()
    assert lifecycle.issue_grant(_worker_binding(lifecycle)) is PersistenceOutcome.OK
    assert lifecycle.revoke_grant() is PersistenceOutcome.OK
    assert lifecycle.terminalize(_terminal_binding(lifecycle)) is PersistenceOutcome.OK
    forbidden = {
        "raw",
        "capability",
        "nonce",
        "path",
        "root",
        "friendly_name",
        "device_name",
        "argv",
        "command",
    }
    for record in store.records.values():
        assert b"e" * 32 not in record
        assert b"g" * 32 not in record
        assert forbidden.isdisjoint(json.loads(record))


def test_round3_shared_leaf_validator_rejects_extra_fields_and_wrong_leaf() -> None:
    lifecycle, store, _, _ = _consumed()
    consumed = store.records[AuthorityLeaf.PREPARED]
    assert (
        classify_canonical_leaf_record(AuthorityLeaf.PREPARED, consumed)
        is CanonicalLifecycleState.CONSUMED_NO_GRANT
    )
    assert classify_canonical_leaf_record(AuthorityLeaf.GRANT, consumed) is None
    tampered = json.loads(consumed)
    tampered["material"] = "https://host/C:/raw/capability"
    assert classify_canonical_leaf_record(AuthorityLeaf.PREPARED, _canonical(tampered)) is None


def test_round3_abandoned_mutex_is_inspection_only() -> None:
    lifecycle, store, guard, _ = _new()
    guard.enqueue(owner=OwnerStatus.ABANDONED_INSPECTION_ONLY)
    assert lifecycle.prepare() is PersistenceOutcome.OWNER_ABANDONED
    assert store.write_calls == []


@pytest.mark.parametrize(
    ("owner", "before"),
    [
        (OwnerStatus.UNAVAILABLE, []),
        (OwnerStatus.ERROR, []),
        (OwnerStatus.ABANDONED_INSPECTION_ONLY, [ValidationStatus.DRIFT]),
        (OwnerStatus.ACQUIRED, [ValidationStatus.DRIFT]),
    ],
)
def test_round3_startup_denial_or_validation_failure_always_cleans(
    owner: OwnerStatus, before: list[ValidationStatus]
) -> None:
    store = _Store()
    guard = _Guard()
    session = _Session(guard.log, before=list(before))
    guard.enqueue(session=session, owner=owner)
    lifecycle = CanonicalInjectableAuthorityLifecycle(
        store,
        guard,
        entropy=lambda _: b"e" * 32,
        grant_entropy=lambda _: b"g" * 32,
        clock_ns=_Clock(),
    )
    assert lifecycle.state is CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE
    assert session.log[-3:] == ["close_leases", "release_mutex", "close_mutex"]
    assert store.write_calls == []


@pytest.mark.parametrize(
    ("inspection_state", "expected"),
    [
        (
            CanonicalLifecycleState.PRESENT_INVALID,
            CanonicalLifecycleState.PRESENT_INVALID,
        ),
        (
            CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE,
            CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE,
        ),
    ],
)
def test_round3_suppressed_inspection_payload_never_becomes_absent(
    inspection_state: CanonicalLifecycleState,
    expected: CanonicalLifecycleState,
) -> None:
    store = _Store()
    store.inspection_states[AuthorityLeaf.PREPARED] = inspection_state
    lifecycle, _, _, _ = _new(store=store)
    assert lifecycle.state is expected
