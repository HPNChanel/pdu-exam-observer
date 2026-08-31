from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import pdu_exam_observer.m2_d1_n2_authority as authority
from pdu_exam_observer.m2_d1_n2_authority import (
    AUTHORITY_MUTEX_NAME,
    D1N2PlatformUnsupported,
    D1N2State,
    TerminalCode,
    WorkerGrantState,
    _D1N2AuthorityStore,
    _FaultPlan,
    _LegacyTestOnlyProductionAuthorityStore,
    _TestNamedMutex,
    _WindowsNamedMutex,
)


def _digest(value: str) -> str:
    return authority._digest(value)


def _static() -> authority.StaticBindingAttestation:
    return authority.StaticBindingAttestation(_digest("static"), _digest("schema"))


def _inert() -> authority.InertPrepareAttestation:
    return authority.InertPrepareAttestation(
        supervisor_sha256=_digest("supervisor"),
        supervisor_size_bytes=1,
        supervisor_identity_digest=_digest("supervisor-id"),
        worker_sha256=_digest("supervisor"),
        worker_size_bytes=1,
        worker_identity_digest=_digest("supervisor-id"),
        ffmpeg_sha256=_digest("ffmpeg"),
        ffmpeg_size_bytes=1,
        ffmpeg_identity_digest=_digest("ffmpeg-id"),
        ffmpeg_version_digest=_digest("ffmpeg-version"),
        executable_lease_verified=True,
    )


def _consumed(store: _D1N2AuthorityStore) -> authority.AuthorityRecord:
    pending = store.reserve_pending()
    assert pending is not None
    prepared = store.finalize_prepared(pending.record_digest, _static(), _inert())
    assert prepared is not None
    consumed = store.consume(prepared.record_digest, _digest("consumed"))
    assert consumed is not None
    return consumed


def test_round1_legacy_test_adapter_is_private_unwired_and_has_no_env_root() -> None:
    assert list(inspect.signature(_LegacyTestOnlyProductionAuthorityStore).parameters) == []
    source = Path(
        inspect.getsourcefile(_LegacyTestOnlyProductionAuthorityStore) or ""
    ).read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "m2_d1_native" not in source
    assert "d1-n1" not in source.lower()
    assert "SHGetKnownFolderPath" in source
    assert "_WindowsNamedMutex(AUTHORITY_MUTEX_NAME)" in source
    assert AUTHORITY_MUTEX_NAME in source


def test_round1_legacy_test_adapter_rejects_non_windows_before_store_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authority.os, "name", "posix")
    with pytest.raises(D1N2PlatformUnsupported):
        _LegacyTestOnlyProductionAuthorityStore()


def test_round1_terminal_requires_exact_revoked_digest_only_grant(tmp_path: Path) -> None:
    store = _D1N2AuthorityStore(tmp_path, _TestNamedMutex("round1-terminal"))
    consumed = _consumed(store)
    issued = store.issue_worker_grant(
        consumed.record_digest, _digest("challenge"), _digest("capability")
    )
    assert issued is not None and issued.state is WorkerGrantState.ISSUED
    assert (
        store.finalize_terminal(
            consumed.record_digest, TerminalCode.NONLAUNCHING_NO_GO, issued.record_digest
        )
        is None
    )
    revoked = store.revoke_worker_grant(issued.record_digest)
    assert revoked is not None and revoked.state is WorkerGrantState.REVOKED
    terminal = store.finalize_terminal(
        consumed.record_digest, TerminalCode.NONLAUNCHING_NO_GO, revoked.record_digest
    )
    assert terminal is not None
    raw = json.loads(store.worker_grant_path.read_text(encoding="utf-8"))
    assert set(raw) == {
        "schema_version",
        "state",
        "consumed_record_digest",
        "challenge_digest",
        "capability_digest",
        "issued_monotonic_ns",
        "expires_monotonic_ns",
        "record_digest",
    }


@pytest.mark.parametrize(
    "fault",
    (
        "pending_create",
        "pending_create_flush",
        "prepared_transition",
        "prepared_transition_flush",
        "consumed_transition",
        "grant_issue",
        "grant_issue_flush",
        "grant_revoke",
        "terminal_create",
        "terminal_create_flush",
        "mutex_acquire",
    ),
)
def test_round1_faults_fail_closed_without_reopening(tmp_path: Path, fault: str) -> None:
    store = _D1N2AuthorityStore(
        tmp_path, _TestNamedMutex(f"round1-{fault}"), _FaultPlan(frozenset({fault}))
    )
    pending = store.reserve_pending()
    if fault in {"pending_create", "mutex_acquire"}:
        assert pending is None
        assert not store.directory.exists()
        return
    if fault == "pending_create_flush":
        assert pending is None and store.inspect().state is D1N2State.PENDING
        return
    assert pending is not None
    prepared = store.finalize_prepared(pending.record_digest, _static(), _inert())
    if fault in {"prepared_transition", "prepared_transition_flush"}:
        assert prepared is None and store.inspect().state is D1N2State.PENDING
        return
    assert prepared is not None
    consumed = store.consume(prepared.record_digest, _digest("consumed"))
    if fault == "consumed_transition":
        assert consumed is None and store.inspect().state is D1N2State.PREPARED
        return
    assert consumed is not None
    issued = store.issue_worker_grant(
        consumed.record_digest, _digest("challenge"), _digest("capability")
    )
    if fault in {"grant_issue", "grant_issue_flush"}:
        assert issued is None and store.inspect().state is D1N2State.CONSUMED
        return
    assert issued is not None
    revoked = store.revoke_worker_grant(issued.record_digest)
    if fault == "grant_revoke":
        assert revoked is None and store.inspect().state is D1N2State.CONSUMED
        return
    assert revoked is not None
    assert (
        store.finalize_terminal(
            consumed.record_digest, TerminalCode.NONLAUNCHING_NO_GO, revoked.record_digest
        )
        is None
    )
    if fault == "terminal_create_flush":
        # Create-only terminal ambiguity is accepted only as its exact durable record.
        assert store.inspect().state is D1N2State.TERMINAL
    else:
        assert store.inspect().state is D1N2State.CONSUMED


def test_round1_temp_symlink_or_parent_swap_is_present_invalid(tmp_path: Path) -> None:
    store = _D1N2AuthorityStore(tmp_path, _TestNamedMutex("round1-swap"))
    store.directory.parent.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "outside"
    target.mkdir()
    try:
        store.directory.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("temporary symlink creation is unavailable")
    assert store.inspect().invalid is True
    assert store.reserve_pending() is None


def test_round1_mutex_refusal_permits_no_write(tmp_path: Path) -> None:
    class RefusingMutex:
        def acquire(self) -> bool:
            return False

        def release(self) -> bool:
            raise AssertionError("release must not run without ownership")

    store = _D1N2AuthorityStore(tmp_path, RefusingMutex())
    assert store.reserve_pending() is None
    assert not store.directory.exists()


def test_round1_win32_named_mutex_contract_uses_the_fixed_cross_process_name() -> None:
    class FakeKernel32:
        def __init__(self) -> None:
            self.name = ""

        def CreateMutexW(self, _security: object, _owned: bool, name: str) -> int:
            self.name = name
            return 41

        def WaitForSingleObject(self, handle: int, timeout: int) -> int:
            assert handle == 41 and timeout == 10_000
            return 0

        def ReleaseMutex(self, handle: int) -> int:
            assert handle == 41
            return 1

    api = FakeKernel32()
    mutex = _WindowsNamedMutex(AUTHORITY_MUTEX_NAME, api)
    assert api.name == AUTHORITY_MUTEX_NAME
    assert mutex.acquire() is True
    assert mutex.release() is True


def test_round1_worker_grant_extra_or_wrong_type_is_sticky_invalid(tmp_path: Path) -> None:
    store = _D1N2AuthorityStore(tmp_path, _TestNamedMutex("round1-grant-closed"))
    consumed = _consumed(store)
    issued = store.issue_worker_grant(
        consumed.record_digest, _digest("challenge"), _digest("capability")
    )
    assert issued is not None
    payload = json.loads(store.worker_grant_path.read_text(encoding="utf-8"))
    payload["unexpected"] = "x"
    store.worker_grant_path.write_text(json.dumps(payload), encoding="utf-8")
    assert store.inspect().invalid is True
    assert store.revoke_worker_grant(issued.record_digest) is None
