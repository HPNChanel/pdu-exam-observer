from __future__ import annotations

import hashlib
import inspect
import json
import ntpath

import pytest

import pdu_exam_observer.m2_d1_n2_adapter as adapter
import pdu_exam_observer.m2_d1_n2_canonical as canonical
from pdu_exam_observer.m2_d1_n2_a0 import (
    A0VerificationResult,
    A0VerificationStatus,
    ApprovedRP2Triple,
)
from pdu_exam_observer.m2_d1_n2_canonical import (
    AUTHORITY_REVISION,
    PREPARED_TTL_NS,
    AuthorityLeaf,
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
)
from pdu_exam_observer.m2_d1_n2_evidence import (
    CAPTURE_POLICY_DIGEST,
    WATCHDOG_POLICY_DIGEST,
    RetainedLeaseCleanup,
    build_sanitized_no_go_evidence,
)
from pdu_exam_observer.m2_d1_n2_prepare import (
    NoStreamAttestationOutcome,
    NoStreamAttestationStatus,
)
from pdu_exam_observer.m2_d1_n2_win32 import LeafFailure, LeafResult
from pdu_exam_observer.m2_d1_n2_win32_store import (
    AUTHORITY_MUTEX_NAME,
    DirectoryAcquireFailure,
    DirectoryCleanupStatus,
    DirectoryDurability,
    DirectoryLeaseAcquisition,
    KnownFolderAuthorityPaths,
    MutexStatus,
)


class _Mutex:
    def __init__(self, status: MutexStatus = MutexStatus.ACQUIRED) -> None:
        self.status = status
        self.calls: list[object] = []
        self.release_result = True
        self.close_result = True
        self.acquire_error: BaseException | None = None
        self.release_error: BaseException | None = None
        self.close_error: BaseException | None = None

    def acquire(self, name: str) -> MutexStatus:
        self.calls.append(("acquire", name))
        if self.acquire_error is not None:
            raise self.acquire_error
        return self.status

    def release(self) -> bool:
        self.calls.append("release")
        if self.release_error is not None:
            raise self.release_error
        return self.release_result

    def close(self) -> bool:
        self.calls.append("close")
        if self.close_error is not None:
            raise self.close_error
        return self.close_result


class _Lease:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.valid = True
        self.durability = DirectoryDurability.VERIFIED
        self.close_result = True

    def validate(self) -> bool:
        self.calls.append("validate")
        return self.valid

    def durable(self) -> DirectoryDurability:
        self.calls.append("durable")
        return self.durability

    def close(self) -> bool:
        self.calls.append("close")
        return self.close_result


@pytest.fixture
def fixed_paths() -> KnownFolderAuthorityPaths:
    return KnownFolderAuthorityPaths(
        r"C:\\Local",
        r"C:\\Local\\PDUExamObserver",
        r"C:\\Local\\PDUExamObserver\\d1-n2-authority-v1",
    )


class _DefaultAttestor:
    pass


_DEFAULT_ATTESTOR = _DefaultAttestor()


def _factory(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    mutex: _Mutex,
    acquisition: DirectoryLeaseAcquisition,
    attestor: PreparedBindingAttestation | None | _DefaultAttestor = _DEFAULT_ATTESTOR,
) -> adapter._B1GuardFactory:
    calls: list[object] = []
    directory_ops = object()

    def resolver() -> KnownFolderAuthorityPaths | None:
        calls.append("resolve")
        return fixed_paths

    def mutex_factory() -> _Mutex:
        calls.append("mutex_factory")
        return mutex

    def directory_factory() -> object:
        calls.append("directory_factory")
        return directory_ops

    def acquire(
        directory_ops: object, paths: KnownFolderAuthorityPaths
    ) -> DirectoryLeaseAcquisition:
        calls.append(("lease_acquire", directory_ops, paths))
        return acquisition

    monkeypatch.setattr(adapter.DirectoryLease, "acquire", acquire)
    resolved_attestor = (
        _attestation() if isinstance(attestor, _DefaultAttestor) else attestor
    )
    factory = adapter._B1GuardFactory(
        resolver=resolver,
        mutex_factory=mutex_factory,
        directory_ops_factory=directory_factory,
        attestor=lambda: resolved_attestor,
        a0_attestor=lambda: _approved() if resolved_attestor is not None else None,
    )
    factory.test_calls = calls  # type: ignore[attr-defined]
    factory.test_directory_ops = directory_ops  # type: ignore[attr-defined]
    return factory


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


def _approved() -> ApprovedRP2Triple:
    return ApprovedRP2Triple(
        static_bindings_digest="a" * 64,
        binding_schema_canonical_sha256="a" * 64,
        candidate_exact_bytes_sha256="a" * 64,
        a0_approval_digest="0" * 64,
        approval_id_digest="1" * 64,
        issued_unix_ns=1,
        expires_unix_ns=900_000_000_001,
    )


def _worker_binding(prepared_digest: str = "a" * 64) -> WorkerGrantBindingAttestation:
    return WorkerGrantBindingAttestation(
        prepared_digest,
        "b" * 64,
        1,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "2" * 64,
        "3" * 64,
        60,
        True,
        False,
    )


def _terminal_binding(
    prepared_authority_digest: str = "a" * 64,
    grant_record: bytes | None = None,
) -> TerminalBindingAttestation:
    grant_record_digest = "a" * 64
    challenge_digest = "a" * 64
    job_name_digest = "a" * 64
    if grant_record is not None:
        grant_record_digest = hashlib.sha256(grant_record).hexdigest()
        grant = json.loads(grant_record)
        challenge_digest = grant["challenge_digest"]
        job_name_digest = grant["job_name_digest"]
    evidence = build_sanitized_no_go_evidence(
        failure_code="AUTHORIZATION_FAILED",
        authority_digest=prepared_authority_digest,
        grant_record_digest=grant_record_digest,
        challenge_digest=challenge_digest,
        job_name_digest=job_name_digest,
        static_bindings_digest="a" * 64,
        capture_policy_digest=CAPTURE_POLICY_DIGEST,
        watchdog_policy_digest=WATCHDOG_POLICY_DIGEST,
        runtime_digest="a" * 64,
        pose_model_sha256="a" * 64,
        face_model_sha256="a" * 64,
        retained_cleanup=RetainedLeaseCleanup(True, True, True),
    )
    assert evidence is not None
    return TerminalBindingAttestation.from_evidence(evidence, 0)


def test_b1a_acquired_session_uses_fixed_name_paths_and_exact_order(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    mutex = _Mutex()
    lease = _Lease()
    factory = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(lease, None, DirectoryCleanupStatus.CLEAN),
    )
    begun = factory.begin(OperationKind.PREPARE)
    assert begun.owner is OwnerStatus.ACQUIRED
    assert begun.session is not None and begun.session.write_permitted
    assert factory.test_calls == [  # type: ignore[attr-defined]
        "resolve",
        "mutex_factory",
        "directory_factory",
        ("lease_acquire", factory.test_directory_ops, fixed_paths),  # type: ignore[attr-defined]
    ]
    assert mutex.calls == [("acquire", AUTHORITY_MUTEX_NAME)]
    assert begun.session.validate_before() is ValidationStatus.VALID
    assert begun.session.validate_after() is ValidationStatus.VALID
    assert begun.session.parent_durable() is DurabilityStatus.VERIFIED
    assert begun.session.attest_pending() == _attestation()
    assert begun.session.close_leases() is StepStatus.CLEAN
    assert begun.session.release_mutex() is StepStatus.CLEAN
    assert begun.session.close_mutex() is StepStatus.CLEAN
    assert lease.calls == ["validate", "validate", "durable", "close"]
    assert mutex.calls[-2:] == ["release", "close"]


def test_b1a_abandoned_is_inspection_only_and_still_releases_and_closes(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    mutex = _Mutex(MutexStatus.ABANDONED)
    factory = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(
            None,
            DirectoryAcquireFailure.OPEN_FAILED,
            DirectoryCleanupStatus.CLEAN,
        ),
    )
    begun = factory.begin(OperationKind.INSPECT)
    assert begun.owner is OwnerStatus.ABANDONED_INSPECTION_ONLY
    assert begun.session is not None and not begun.session.write_permitted
    assert factory.test_calls == ["resolve", "mutex_factory"]  # type: ignore[attr-defined]
    assert begun.session.close_leases() is StepStatus.NOT_HELD
    assert begun.session.release_mutex() is StepStatus.CLEAN
    assert begun.session.close_mutex() is StepStatus.CLEAN
    assert mutex.calls == [("acquire", AUTHORITY_MUTEX_NAME), "release", "close"]


@pytest.mark.parametrize("status", [MutexStatus.UNAVAILABLE])
def test_b1a_unavailable_mutex_never_acquires_directories_but_closes(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    status: MutexStatus,
) -> None:
    mutex = _Mutex(status)
    factory = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(
            None,
            DirectoryAcquireFailure.OPEN_FAILED,
            DirectoryCleanupStatus.CLEAN,
        ),
    )
    begun = factory.begin(OperationKind.PREPARE)
    assert begun.owner is OwnerStatus.UNAVAILABLE
    assert begun.session is not None and not begun.session.write_permitted
    assert factory.test_calls == ["resolve", "mutex_factory"]  # type: ignore[attr-defined]
    assert begun.session.release_mutex() is StepStatus.NOT_HELD
    assert begun.session.close_mutex() is StepStatus.CLEAN


def test_b1a_lease_failure_drift_durability_and_cleanup_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    mutex = _Mutex()
    lease = _Lease()
    lease.valid = False
    lease.durability = DirectoryDurability.UNVERIFIED
    lease.close_result = False
    factory = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(lease, None, DirectoryCleanupStatus.CLEAN),
    )
    session = factory.begin(OperationKind.CONSUME).session
    assert session is not None and session.write_permitted
    assert session.validate_before() is ValidationStatus.DRIFT
    assert session.parent_durable() is DurabilityStatus.UNVERIFIED
    assert session.close_leases() is StepStatus.FAILED
    assert session.close_leases() is StepStatus.FAILED
    assert lease.calls.count("close") == 1


def test_b1a_release_and_close_failures_are_separate_and_idempotent(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    mutex = _Mutex()
    mutex.release_result = False
    mutex.close_result = False
    lease = _Lease()
    factory = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(lease, None, DirectoryCleanupStatus.CLEAN),
    )
    session = factory.begin(OperationKind.PREPARE).session
    assert session is not None
    assert session.release_mutex() is StepStatus.FAILED
    assert session.release_mutex() is StepStatus.FAILED
    assert session.close_mutex() is StepStatus.FAILED
    assert session.close_mutex() is StepStatus.FAILED
    assert mutex.calls.count("release") == 1
    assert mutex.calls.count("close") == 1


def test_b1a_default_attestor_denies_and_production_construction_is_inert(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("production constructor must remain inert")

    monkeypatch.setattr(adapter, "CtypesMutexOps", explode)
    monkeypatch.setattr(adapter, "CtypesDirectoryOps", explode)
    monkeypatch.setattr(adapter, "resolve_known_folder_authority_root", explode)
    production = adapter.D1N2ProductionGuardFactory()
    assert production is not None
    assert adapter._not_issued_attestor() is None


class _PrimaryStop(BaseException):
    pass


class _CleanupStop(BaseException):
    pass


@pytest.mark.parametrize("failure_stage", ["acquire", "directory", "lease"])
@pytest.mark.parametrize(
    ("release_mode", "close_mode"),
    [
        ("clean", "clean"),
        ("false", "clean"),
        ("raise", "clean"),
        ("clean", "false"),
        ("clean", "raise"),
    ],
)
def test_b1a_primary_failure_cleans_mutex_or_preserves_sanitized_cleanup_group(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    failure_stage: str,
    release_mode: str,
    close_mode: str,
) -> None:
    mutex = _Mutex()
    mutex.release_result = release_mode != "false"
    mutex.close_result = close_mode != "false"
    mutex.release_error = _CleanupStop() if release_mode == "raise" else None
    mutex.close_error = _CleanupStop() if close_mode == "raise" else None
    lease = _Lease()
    factory = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(lease, None, DirectoryCleanupStatus.CLEAN),
    )
    if failure_stage == "acquire":
        mutex.acquire_error = _PrimaryStop()
    elif failure_stage == "directory":
        factory._directory_ops_factory = lambda: (_ for _ in ()).throw(_PrimaryStop())
    else:
        def fail_lease(
            _ops: object, _paths: KnownFolderAuthorityPaths
        ) -> DirectoryLeaseAcquisition:
            raise _PrimaryStop()

        monkeypatch.setattr(adapter.DirectoryLease, "acquire", fail_lease)

    cleanup_fails = release_mode != "clean" or close_mode != "clean"
    if cleanup_fails:
        with pytest.raises(BaseExceptionGroup) as raised:
            factory.begin(OperationKind.PREPARE)
        assert any(isinstance(error, _PrimaryStop) for error in raised.value.exceptions)
        assert any(
            isinstance(error, adapter.CleanupFailure) for error in raised.value.exceptions
        )
    else:
        with pytest.raises(_PrimaryStop):
            factory.begin(OperationKind.PREPARE)
    assert mutex.calls == [("acquire", AUTHORITY_MUTEX_NAME), "release", "close"]


def test_b1a_ordinary_exception_uses_the_same_mutex_cleanup_boundary(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    mutex = _Mutex()
    factory = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(
            None,
            DirectoryAcquireFailure.OPEN_FAILED,
            DirectoryCleanupStatus.CLEAN,
        ),
    )
    mutex.acquire_error = RuntimeError("primary")
    with pytest.raises(RuntimeError, match="primary"):
        factory.begin(OperationKind.CONSUME)
    assert mutex.calls == [("acquire", AUTHORITY_MUTEX_NAME), "release", "close"]


def _canonical(domain: str) -> bytes:
    digest = "a" * 64
    values: dict[str, object] = {
        "D1N2/PENDING/v1": {
            **_approved().pending_fields(),
            "epoch_digest": digest,
            "state": "PENDING",
        },
        "D1N2/PREPARED/v1": {
            **_attestation().record_fields(),
            "epoch_digest": digest,
            "pending_digest": digest,
            "state": "PREPARED",
        },
        "D1N2/CONSUMED/v1": {
            "dependency_observation_digest": digest,
            "epoch_digest": digest,
            "face_model_sha256": digest,
            "pose_model_sha256": digest,
            "prepared_digest": digest,
            "state": "CONSUMED",
            "static_bindings_digest": digest,
        },
        "D1N2/GRANT_ISSUED/v1": {
            **_worker_binding().record_fields(),
            "consumed_digest": digest,
            "epoch_digest": digest,
            "expires_monotonic_ns": canonical.WORKER_GRANT_TTL_NS,
            "grant_digest": digest,
            "grant_size": 32,
            "issued_monotonic_ns": 0,
            "state": "ISSUED",
        },
        "D1N2/GRANT_REVOKED/v1": {
            "challenge_digest": digest,
            "consumed_digest": digest,
            "epoch_digest": digest,
            "expires_monotonic_ns": canonical.WORKER_GRANT_TTL_NS,
            "grant_digest": digest,
            "issued_monotonic_ns": 0,
            "issued_record_digest": digest,
            "job_name_digest": digest,
            "state": "REVOKED",
        },
        "D1N2/TERMINAL/v1": {
            **_terminal_binding().record_fields(),
            "consumed_digest": digest,
            "durability_policy": "REVERIFY_PARENT_ON_INSPECTION",
            "grant_disposition": "NOT_ISSUED",
            "grant_record_digest": None,
            "state": "TERMINAL",
        },
    }
    return canonical._record(domain, values[domain])


class _Leaf:
    def __init__(self, result: LeafResult) -> None:
        self.result = result
        self.inspect_calls = 0
        self.create_calls: list[bytes] = []
        self.transition_calls: list[tuple[bytes, bytes]] = []

    def inspect(self, _codec: object) -> LeafResult:
        self.inspect_calls += 1
        return self.result

    def create(self, payload: bytes, _codec: object) -> LeafResult:
        self.create_calls.append(payload)
        return self.result

    def transition(self, prior: bytes, payload: bytes, _codec: object) -> LeafResult:
        self.transition_calls.append((prior, payload))
        return self.result


class _MemoryLeaves:
    """In-memory H1 leaf double retaining exact canonical bytes only."""

    def __init__(self) -> None:
        self.records: dict[str, bytes] = {}
        self.mutations: list[tuple[str, str]] = []
        self.transition_failure: LeafFailure | None = None

    def __call__(self, path: str) -> _MemoryLeaf:
        return _MemoryLeaf(self, path)


class _MemoryLeaf:
    def __init__(self, owner: _MemoryLeaves, path: str) -> None:
        self._owner = owner
        self._path = path

    def inspect(self, codec: object) -> LeafResult:
        record = self._owner.records.get(self._path)
        if record is None:
            return LeafResult(None, LeafFailure.ABSENT)
        return LeafResult(
            record,
            None if callable(codec) and codec(record) else LeafFailure.CODEC_INVALID,
        )

    def create(self, payload: bytes, codec: object) -> LeafResult:
        if self._path in self._owner.records:
            return LeafResult(None, LeafFailure.CREATE_CONFLICT)
        if not callable(codec) or not codec(payload):
            return LeafResult(None, LeafFailure.CODEC_INVALID)
        self._owner.records[self._path] = payload
        self._owner.mutations.append(("create", self._path))
        return LeafResult(payload, None)

    def transition(self, prior: bytes, payload: bytes, codec: object) -> LeafResult:
        if self._owner.transition_failure is not None:
            return LeafResult(None, self._owner.transition_failure)
        if self._owner.records.get(self._path) != prior:
            return LeafResult(None, LeafFailure.STALE_CAS)
        if not callable(codec) or not codec(payload):
            return LeafResult(None, LeafFailure.CODEC_INVALID)
        self._owner.records[self._path] = payload
        self._owner.mutations.append(("transition", self._path))
        return LeafResult(payload, None)


def _persistence(
    leaf: _Leaf, session: object
) -> tuple[adapter._B1CanonicalPersistence, list[str]]:
    paths: list[str] = []

    def leaf_factory(path: str) -> _Leaf:
        paths.append(path)
        return leaf

    return adapter._B1CanonicalPersistence(session._capability, leaf_factory), paths  # type: ignore[attr-defined]


def _live_session(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    operation: OperationKind = OperationKind.PREPARE,
) -> object:
    factory = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    session = factory.begin(operation).session
    assert session is not None
    return session


@pytest.mark.parametrize(
    ("leaf", "domain", "state"),
    [
        (AuthorityLeaf.PREPARED, "D1N2/PENDING/v1", CanonicalLifecycleState.PENDING),
        (AuthorityLeaf.PREPARED, "D1N2/PREPARED/v1", CanonicalLifecycleState.PREPARED),
        (
            AuthorityLeaf.PREPARED,
            "D1N2/CONSUMED/v1",
            CanonicalLifecycleState.CONSUMED_NO_GRANT,
        ),
        (AuthorityLeaf.GRANT, "D1N2/GRANT_ISSUED/v1", CanonicalLifecycleState.ISSUED),
        (
            AuthorityLeaf.GRANT,
            "D1N2/GRANT_REVOKED/v1",
            CanonicalLifecycleState.REVOKED_TERMINAL_PENDING,
        ),
        (AuthorityLeaf.TERMINAL, "D1N2/TERMINAL/v1", CanonicalLifecycleState.TERMINAL),
    ],
)
def test_b1b_inspect_maps_fixed_leaf_domains_with_one_read_only_call(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    leaf: AuthorityLeaf,
    domain: str,
    state: CanonicalLifecycleState,
) -> None:
    payload = _canonical(domain)
    fake_leaf = _Leaf(LeafResult(payload, None))
    session = _live_session(monkeypatch, fixed_paths)
    persistence, paths = _persistence(fake_leaf, session)
    inspected = persistence.inspect(session, leaf)
    assert inspected.state is state
    assert inspected.record == payload
    assert fake_leaf.inspect_calls == 1
    assert not fake_leaf.create_calls and not fake_leaf.transition_calls
    assert paths == [fixed_paths.authority + "\\" + leaf.value]


@pytest.mark.parametrize(
    ("failure", "state"),
    [
        (LeafFailure.ABSENT, CanonicalLifecycleState.ABSENT),
        (LeafFailure.CODEC_INVALID, CanonicalLifecycleState.PRESENT_INVALID),
        (LeafFailure.HANDLE_VALIDATION_FAILED, CanonicalLifecycleState.PRESENT_INVALID),
        (LeafFailure.OPEN_FAILED, CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE),
        (LeafFailure.READ_FAILED, CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE),
        (LeafFailure.IDENTITY_CHANGED, CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE),
        (LeafFailure.CLOSE_FAILED, CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE),
    ],
)
def test_b1b_inspect_failure_mapping_is_closed_and_never_reopens(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    failure: LeafFailure,
    state: CanonicalLifecycleState,
) -> None:
    fake_leaf = _Leaf(LeafResult(None, failure))
    session = _live_session(monkeypatch, fixed_paths)
    persistence, _paths = _persistence(fake_leaf, session)
    inspected = persistence.inspect(session, AuthorityLeaf.PREPARED)
    assert inspected.state is state and inspected.record is None
    assert fake_leaf.inspect_calls == 1
    assert not fake_leaf.create_calls and not fake_leaf.transition_calls


def test_b1b_terminal_durability_requires_parent_directory_proof(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    session = _live_session(monkeypatch, fixed_paths)
    session._lease.durability = DirectoryDurability.UNVERIFIED  # type: ignore[attr-defined]
    payload = _canonical("D1N2/TERMINAL/v1")
    persistence, _paths = _persistence(_Leaf(LeafResult(payload, None)), session)
    inspection = persistence.inspect(session, AuthorityLeaf.TERMINAL)
    assert inspection.durability is DurabilityStatus.UNVERIFIED


def test_b1b_terminal_durability_is_verified_only_after_leaf_validation(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    session = _live_session(monkeypatch, fixed_paths)
    payload = _canonical("D1N2/TERMINAL/v1")
    fake_leaf = _Leaf(LeafResult(payload, None))
    persistence, _paths = _persistence(fake_leaf, session)
    inspection = persistence.inspect(session, AuthorityLeaf.TERMINAL)
    assert inspection.state is CanonicalLifecycleState.TERMINAL
    assert inspection.durability is DurabilityStatus.VERIFIED
    assert fake_leaf.inspect_calls == 1


@pytest.mark.parametrize(
    "payload",
    [
        b"{",
        b'{"domain":"D1N2/PENDING/v1", "domain":"x"}',
        b'{"domain":1.0}',
        pytest.param(b"x" * 32_769, id="oversize"),
    ],
)
def test_b1b_codec_rejects_malformed_duplicate_float_and_oversize(payload: bytes) -> None:
    assert not adapter._canonical_leaf_codec(payload)


def _extra_field(record: bytes, key: str, value: object) -> bytes:
    decoded = json.loads(record.decode("utf-8"))
    decoded[key] = value
    return json.dumps(decoded, separators=(",", ":"), sort_keys=True).encode("utf-8")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("material", "raw-value"),
        ("url", "https://invalid.example"),
        ("source_path", "C:\\private"),
        ("forward_path", "relative/secret"),
    ],
)
def test_b1b_exact_validator_rejects_extra_material_url_and_paths(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    key: str,
    value: str,
) -> None:
    session = _live_session(monkeypatch, fixed_paths)
    payload = _extra_field(_canonical("D1N2/PENDING/v1"), key, value)
    fake_leaf = _Leaf(LeafResult(payload, None))
    persistence, _paths = _persistence(fake_leaf, session)
    inspected = persistence.inspect(session, AuthorityLeaf.PREPARED)
    assert inspected.state is CanonicalLifecycleState.PRESENT_INVALID


def test_b1b_exact_validator_rejects_wrong_leaf_domain_pairing(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    session = _live_session(monkeypatch, fixed_paths)
    fake_leaf = _Leaf(LeafResult(_canonical("D1N2/PENDING/v1"), None))
    persistence, _paths = _persistence(fake_leaf, session)
    assert (
        persistence.inspect(session, AuthorityLeaf.GRANT).state
        is CanonicalLifecycleState.PRESENT_INVALID
    )


def test_b1b_write_mapping_rejects_mismatch_foreign_and_closed_session(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    requested = _canonical("D1N2/PENDING/v1")
    fake_leaf = _Leaf(LeafResult(_canonical("D1N2/PREPARED/v1"), None))
    session = _live_session(monkeypatch, fixed_paths)
    persistence, _paths = _persistence(fake_leaf, session)
    result = persistence.create_exact(session, AuthorityLeaf.PREPARED, requested)
    assert result.outcome is PersistenceOutcome.READBACK_FAILED
    assert result.disposition is WriteDisposition.PRESENT_UNKNOWN
    assert result.observed_bytes is None
    assert len(fake_leaf.create_calls) == 1
    foreign = persistence.cas_exact(
        object(), AuthorityLeaf.PREPARED, requested, requested
    )
    assert foreign.outcome is PersistenceOutcome.INPUT_INVALID
    session.close_leases()
    closed = persistence.create_exact(session, AuthorityLeaf.PREPARED, requested)
    assert closed.outcome is PersistenceOutcome.CLOSE_FAILED


@pytest.mark.parametrize(
    ("failure", "outcome"),
    [
        (LeafFailure.ABSENT, PersistenceOutcome.CREATE_FAILED),
        (LeafFailure.OPEN_FAILED, PersistenceOutcome.CREATE_FAILED),
        (LeafFailure.CREATE_CONFLICT, PersistenceOutcome.CREATE_FAILED),
        (LeafFailure.HANDLE_VALIDATION_FAILED, PersistenceOutcome.LEASE_DRIFT),
        (LeafFailure.READ_FAILED, PersistenceOutcome.READBACK_FAILED),
        (LeafFailure.CODEC_INVALID, PersistenceOutcome.INPUT_INVALID),
        (LeafFailure.STALE_CAS, PersistenceOutcome.CAS_MISMATCH),
        (LeafFailure.WRITE_FAILED, PersistenceOutcome.CREATE_FAILED),
        (LeafFailure.TRUNCATE_FAILED, PersistenceOutcome.CREATE_FAILED),
        (LeafFailure.FLUSH_FAILED, PersistenceOutcome.DURABILITY_FAILED),
        (LeafFailure.READBACK_FAILED, PersistenceOutcome.READBACK_FAILED),
        (LeafFailure.IDENTITY_CHANGED, PersistenceOutcome.LEASE_DRIFT),
        (LeafFailure.CLOSE_FAILED, PersistenceOutcome.CLOSE_FAILED),
    ],
)
def test_b1b_every_h1_write_failure_is_conservative_without_reopen(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    failure: LeafFailure,
    outcome: PersistenceOutcome,
) -> None:
    fake_leaf = _Leaf(LeafResult(None, failure))
    session = _live_session(monkeypatch, fixed_paths)
    persistence, _paths = _persistence(fake_leaf, session)
    result = persistence.create_exact(
        session,
        AuthorityLeaf.PREPARED,
        _canonical("D1N2/PENDING/v1"),
    )
    assert result.outcome is outcome
    assert result.disposition is WriteDisposition.PRESENT_UNKNOWN
    assert result.observed_bytes is None
    assert len(fake_leaf.create_calls) == 1
    assert not fake_leaf.transition_calls and fake_leaf.inspect_calls == 0


def test_b1b_production_leaf_construction_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "CtypesHandleOps", lambda: pytest.fail("must stay inert"))
    assert adapter._B1CanonicalPersistence(adapter._B1CompositionCapability()) is not None


def test_b1b_cross_composition_session_is_rejected_before_leaf_construction(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    first = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    second = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    session = first.begin(OperationKind.INSPECT).session
    assert session is not None
    fake_leaf = _Leaf(LeafResult(_canonical("D1N2/PENDING/v1"), None))
    inspection = second.persistence(lambda _path: fake_leaf).inspect(
        session, AuthorityLeaf.PREPARED
    )
    assert inspection.state is CanonicalLifecycleState.UNKNOWN_NONLAUNCHABLE
    assert fake_leaf.inspect_calls == 0


@pytest.mark.parametrize("cleanup", ["close_leases", "release_mutex", "close_mutex"])
def test_b1b_cleanup_first_invalidates_persistence_before_any_h1_call(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    cleanup: str,
) -> None:
    factory = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    session = factory.begin(OperationKind.PREPARE).session
    assert session is not None
    fake_leaf = _Leaf(LeafResult(_canonical("D1N2/PENDING/v1"), None))
    persistence = factory.persistence(lambda _path: fake_leaf)
    getattr(session, cleanup)()
    assert not session.write_permitted
    assert session.attest_pending() is None
    assert session.parent_durable() is DurabilityStatus.UNVERIFIED
    assert persistence.inspect(session, AuthorityLeaf.PREPARED).record is None
    denied = persistence.create_exact(
        session, AuthorityLeaf.PREPARED, _canonical("D1N2/PENDING/v1")
    )
    assert denied.outcome is not PersistenceOutcome.OK
    assert fake_leaf.inspect_calls == 0
    assert not fake_leaf.create_calls and not fake_leaf.transition_calls


@pytest.mark.parametrize(
    ("operation", "leaf", "prior_domain", "target_domain", "allowed"),
    [
        (OperationKind.PREPARE, AuthorityLeaf.PREPARED, None, "D1N2/PENDING/v1", True),
        (OperationKind.PREPARE, AuthorityLeaf.PREPARED, None, "D1N2/PREPARED/v1", False),
        (
            OperationKind.PREPARE,
            AuthorityLeaf.PREPARED,
            "D1N2/PENDING/v1",
            "D1N2/PREPARED/v1",
            True,
        ),
        (
            OperationKind.CONSUME,
            AuthorityLeaf.PREPARED,
            "D1N2/PREPARED/v1",
            "D1N2/CONSUMED/v1",
            True,
        ),
        (OperationKind.ISSUE_GRANT, AuthorityLeaf.GRANT, None, "D1N2/GRANT_ISSUED/v1", True),
        (
            OperationKind.REVOKE_GRANT,
            AuthorityLeaf.GRANT,
            "D1N2/GRANT_ISSUED/v1",
            "D1N2/GRANT_REVOKED/v1",
            True,
        ),
        (OperationKind.TERMINALIZE, AuthorityLeaf.TERMINAL, None, "D1N2/TERMINAL/v1", True),
        (OperationKind.CONSUME, AuthorityLeaf.PREPARED, None, "D1N2/PENDING/v1", False),
        (OperationKind.REVOKE_GRANT, AuthorityLeaf.GRANT, None, "D1N2/GRANT_ISSUED/v1", False),
    ],
)
def test_b1b_operation_matrix_allows_only_exact_transition(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
    operation: OperationKind,
    leaf: AuthorityLeaf,
    prior_domain: str | None,
    target_domain: str,
    allowed: bool,
) -> None:
    factory = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    session = factory.begin(operation).session
    assert session is not None
    target = _canonical(target_domain)
    fake_leaf = _Leaf(LeafResult(target, None))
    persistence = factory.persistence(lambda _path: fake_leaf)
    result = (
        persistence.create_exact(session, leaf, target)
        if prior_domain is None
        else persistence.cas_exact(session, leaf, _canonical(prior_domain), target)
    )
    assert (result.outcome is PersistenceOutcome.OK) is allowed
    assert len(fake_leaf.create_calls) + len(fake_leaf.transition_calls) == int(allowed)


def test_b1b_prepare_cas_requires_attestation_and_default_denial_cannot_bypass(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    denied = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
        attestor=None,
    )
    session = denied.begin(OperationKind.PREPARE).session
    assert session is not None
    target = _canonical("D1N2/PREPARED/v1")
    fake_leaf = _Leaf(LeafResult(target, None))
    result = denied.persistence(lambda _path: fake_leaf).cas_exact(
        session,
        AuthorityLeaf.PREPARED,
        _canonical("D1N2/PENDING/v1"),
        target,
    )
    assert result.outcome is PersistenceOutcome.INPUT_INVALID
    assert not fake_leaf.create_calls and not fake_leaf.transition_calls


def test_b1c_parameterless_production_factory_is_constructor_inert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("production construction must remain inert")

    monkeypatch.setattr(adapter, "CtypesMutexOps", explode)
    monkeypatch.setattr(adapter, "CtypesDirectoryOps", explode)
    monkeypatch.setattr(adapter, "CtypesHandleOps", explode)
    monkeypatch.setattr(adapter, "resolve_known_folder_authority_root", explode)

    factory = adapter.D1N2CanonicalProductionFactory()

    assert list(inspect.signature(factory.open).parameters) == []
    assert not hasattr(factory, "activate")
    assert not hasattr(factory, "set_attestor")


def test_b1c_shared_fake_composition_runs_one_terminal_lifecycle(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    mutex = _Mutex()
    lease = _Lease()
    guard = _factory(
        monkeypatch,
        fixed_paths,
        mutex,
        DirectoryLeaseAcquisition(lease, None, DirectoryCleanupStatus.CLEAN),
    )
    leaves = _MemoryLeaves()
    lifecycle = canonical.CanonicalInjectableAuthorityLifecycle(
        guard.persistence(leaves),
        guard,
        entropy=lambda size: b"e" * size,
        grant_entropy=lambda size: b"g" * size,
        clock_ns=lambda: 100,
        unix_clock_ns=lambda: 1_000,
    )

    assert lifecycle.prepare() is PersistenceOutcome.OK
    assert lifecycle.consume() is PersistenceOutcome.OK
    assert lifecycle.prepared_record is not None
    binding = _worker_binding(hashlib.sha256(lifecycle.prepared_record).hexdigest())
    assert lifecycle.issue_grant(binding) is PersistenceOutcome.OK
    raw_grant = lifecycle.take_grant_capability()
    assert raw_grant == b"g" * 32
    assert lifecycle.take_grant_capability() is None
    assert lifecycle.authorize_grant(raw_grant) is PersistenceOutcome.OK
    assert lifecycle.revoke_grant() is PersistenceOutcome.OK
    prepared_digest = hashlib.sha256(lifecycle.prepared_record).hexdigest()
    terminal_binding = _terminal_binding(prepared_digest, lifecycle.grant_record)
    assert lifecycle.terminalize(terminal_binding) is PersistenceOutcome.OK
    assert (
        lifecycle.terminalize(terminal_binding)
        is PersistenceOutcome.TERMINAL_ALREADY_PRESENT
    )
    assert lifecycle.prepare() is PersistenceOutcome.INPUT_INVALID
    assert lifecycle.state is CanonicalLifecycleState.TERMINAL

    prepared = ntpath.join(fixed_paths.authority, AuthorityLeaf.PREPARED.value)
    grant = ntpath.join(fixed_paths.authority, AuthorityLeaf.GRANT.value)
    terminal = ntpath.join(fixed_paths.authority, AuthorityLeaf.TERMINAL.value)
    assert leaves.mutations == [
        ("create", prepared),
        ("transition", prepared),
        ("transition", prepared),
        ("create", grant),
        ("transition", grant),
        ("create", terminal),
    ]
    persisted = b"".join(leaves.records.values())
    assert b"e" * 32 not in persisted
    assert b"g" * 32 not in persisted
    assert all("\\\\" not in value.decode("ascii") for value in leaves.records.values())
    assert mutex.calls.count("release") == mutex.calls.count("close")
    assert mutex.calls.count("release") > 0


def test_b1c_default_unissued_a0_writes_no_pending(
    monkeypatch: pytest.MonkeyPatch, fixed_paths: KnownFolderAuthorityPaths
) -> None:
    guard = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
        attestor=None,
    )
    leaves = _MemoryLeaves()
    lifecycle = canonical.CanonicalInjectableAuthorityLifecycle(
        guard.persistence(leaves),
        guard,
        entropy=lambda size: b"e" * size,
    )

    assert lifecycle.prepare() is PersistenceOutcome.ATTESTATION_FAILED
    assert lifecycle.state is CanonicalLifecycleState.ABSENT
    assert leaves.mutations == []
    assert leaves.records == {}


class _RetainedBundle:
    def __init__(self) -> None:
        self.valid = True
        self.closed = False
        self.close_calls = 0
        self.close_ok = True

    def validate(self) -> bool:
        return self.valid and not self.closed

    def close(self) -> bool:
        self.close_calls += 1
        self.closed = True
        return self.close_ok


class _NoStreamAttestor:
    def __init__(self, bundle: _RetainedBundle) -> None:
        self.bundle = bundle
        self.calls = 0
        self.revalidation_calls = 0

    def attest(self, expected: ApprovedRP2Triple) -> NoStreamAttestationOutcome:
        self.calls += 1
        assert expected.static_bindings_digest == "a" * 64
        return NoStreamAttestationOutcome(
            NoStreamAttestationStatus.ATTESTED,
            _attestation(),
            self.bundle,  # type: ignore[arg-type]
            "Integrated Camera",
        )

    def revalidate_device(self, expected_name: str) -> bool:
        self.revalidation_calls += 1
        return expected_name == "Integrated Camera"


class _A0Verifier:
    def __init__(self) -> None:
        self.lease = _RetainedBundle()
        self.bootstrap = _RetainedBundle()
        self.calls = 0

    def verify(self) -> A0VerificationResult:
        self.calls += 1
        return A0VerificationResult(
            A0VerificationStatus.VERIFIED,
            _approved(),
            self.lease,  # type: ignore[arg-type]
            self.bootstrap,  # type: ignore[arg-type]
        )


def test_preparation_composition_retains_exact_attestation_and_prepared_digest(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
) -> None:
    guard = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    leaves = _MemoryLeaves()
    bundle = _RetainedBundle()
    no_stream = _NoStreamAttestor(bundle)
    a0 = _A0Verifier()
    composition = adapter._D1N2PreparationComposition(
        guard.persistence(leaves),
        guard,
        no_stream,
        entropy=lambda size: b"e" * size,
        grant_entropy=lambda size: b"g" * size,
        unix_clock_ns=lambda: 1_000,
        a0_verifier=a0,
    )

    result = composition.prepare()

    assert result.outcome is PersistenceOutcome.OK
    assert result.attestation == _attestation()
    assert result.prepared_bytes is not None
    assert result.prepared_authority_digest == hashlib.sha256(result.prepared_bytes).hexdigest()
    assert not bundle.closed and not a0.lease.closed and not a0.bootstrap.closed
    assert result.retained_device_name == "Integrated Camera"
    assert no_stream.calls == 1
    assert composition.revalidate_for_run()
    assert no_stream.revalidation_calls == 1
    assert composition.consume() is PersistenceOutcome.OK
    assert result.prepared_authority_digest is not None
    assert (
        composition.issue_grant(_worker_binding(result.prepared_authority_digest))
        is PersistenceOutcome.OK
    )
    capability = composition.take_grant_capability()
    assert capability == b"g" * 32
    assert composition.authorize_grant(capability) is PersistenceOutcome.OK
    assert composition.revoke_grant() is PersistenceOutcome.OK
    assert composition.close_retained_for_terminal() == RetainedLeaseCleanup(True, True, True)
    assert result.prepared_authority_digest is not None
    assert composition.terminalize(
        _terminal_binding(
            result.prepared_authority_digest,
            composition.grant_record_bytes(),
        )
    ) is PersistenceOutcome.OK
    assert bundle.closed and a0.lease.closed and a0.bootstrap.closed


def test_preparation_composition_closes_retained_native_leases_when_cas_fails(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
) -> None:
    guard = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    leaves = _MemoryLeaves()
    leaves.transition_failure = LeafFailure.STALE_CAS
    bundle = _RetainedBundle()
    a0 = _A0Verifier()
    composition = adapter._D1N2PreparationComposition(
        guard.persistence(leaves),
        guard,
        _NoStreamAttestor(bundle),
        entropy=lambda size: b"e" * size,
        grant_entropy=lambda size: b"g" * size,
        unix_clock_ns=lambda: 1_000,
        a0_verifier=a0,
    )

    result = composition.prepare()

    assert result.outcome is PersistenceOutcome.CAS_MISMATCH
    assert result.prepared_bytes is None
    assert bundle.closed and a0.lease.closed and a0.bootstrap.closed


def test_pre_bridge_abort_is_idempotent_and_closes_each_owner_once(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
) -> None:
    guard = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    bundle = _RetainedBundle()
    a0 = _A0Verifier()
    composition = adapter._D1N2PreparationComposition(
        guard.persistence(_MemoryLeaves()),
        guard,
        _NoStreamAttestor(bundle),
        entropy=lambda size: b"e" * size,
        unix_clock_ns=lambda: 1_000,
        a0_verifier=a0,
    )
    assert composition.prepare().outcome is PersistenceOutcome.OK

    first = composition.abort_pre_bridge()
    second = composition.abort_pre_bridge()

    assert first is second
    assert first.status is adapter.AbortStatus.CLEAN
    assert bundle.close_calls == 1
    assert a0.lease.close_calls == 1
    assert a0.bootstrap.close_calls == 1


def test_retained_close_failure_writes_no_terminal(
    monkeypatch: pytest.MonkeyPatch,
    fixed_paths: KnownFolderAuthorityPaths,
) -> None:
    guard = _factory(
        monkeypatch,
        fixed_paths,
        _Mutex(),
        DirectoryLeaseAcquisition(_Lease(), None, DirectoryCleanupStatus.CLEAN),
    )
    leaves = _MemoryLeaves()
    bundle = _RetainedBundle()
    bundle.close_ok = False
    a0 = _A0Verifier()
    composition = adapter._D1N2PreparationComposition(
        guard.persistence(leaves),
        guard,
        _NoStreamAttestor(bundle),
        entropy=lambda size: b"e" * size,
        grant_entropy=lambda size: b"g" * size,
        unix_clock_ns=lambda: 1_000,
        a0_verifier=a0,
    )
    prepared = composition.prepare()
    assert prepared.outcome is PersistenceOutcome.OK
    assert composition.consume() is PersistenceOutcome.OK
    assert prepared.prepared_authority_digest is not None
    assert (
        composition.issue_grant(_worker_binding(prepared.prepared_authority_digest))
        is PersistenceOutcome.OK
    )
    assert composition.revoke_grant() is PersistenceOutcome.OK

    assert composition.close_retained_for_terminal() is None
    assert composition.terminalize(_terminal_binding()) is PersistenceOutcome.CLEANUP_FAILED
    assert all(not path.endswith(AuthorityLeaf.TERMINAL.value) for path in leaves.records)


def test_prepared_production_factory_is_parameterless_and_constructor_inert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("production construction must not touch native state")

    monkeypatch.setattr(adapter, "CtypesMutexOps", explode)
    monkeypatch.setattr(adapter, "CtypesDirectoryOps", explode)
    monkeypatch.setattr(adapter, "CtypesHandleOps", explode)
    monkeypatch.setattr(adapter, "resolve_known_folder_authority_root", explode)

    factory = adapter.D1N2PreparedProductionFactory()

    assert list(inspect.signature(factory.open).parameters) == []


def test_prepared_production_factory_open_wires_lazy_fixed_bootstrap_without_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("lazy fixed bootstrap must not touch Windows during open")

    monkeypatch.setattr(adapter, "resolve_known_folder_authority_root", explode)
    monkeypatch.setattr(adapter, "CtypesBootstrapHandleOps", explode)
    monkeypatch.setattr(adapter, "CtypesDirectoryOps", explode)

    composition = adapter.D1N2PreparedProductionFactory().open()

    verifier = composition._a0_verifier
    assert verifier is not None
    assert isinstance(verifier._bootstrap, adapter.LazyWindowsProvisionedA0Bootstrap)
    assert isinstance(verifier._source, adapter.LazyFixedA0ApprovalSource)
