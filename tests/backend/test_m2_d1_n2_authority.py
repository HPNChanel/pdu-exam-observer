from __future__ import annotations

import hashlib
import inspect
import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest

import pdu_exam_observer.m2_d1_n2_authority as authority
from pdu_exam_observer.m2_d1_n2_authority import (
    AUTHORITY_MUTEX_NAME,
    AUTHORITY_REVISION,
    DIRECTORY_LEAF,
    JOB_NAME_PREFIX,
    PREPARED_RECORD_NAME,
    SCHEMA_VERSION,
    TERMINAL_RECORD_NAME,
    VIDEO_MUTEX_NAME,
    WORKER_GRANT_RECORD_NAME,
    D1N2PrepareStatus,
    D1N2State,
    InertPrepareAttestation,
    StaticBindingAttestation,
    TerminalCode,
    _D1N2AuthorityStore,
    _prepare_once,
    _TestNamedMutex,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _static() -> StaticBindingAttestation:
    return StaticBindingAttestation(
        static_bindings_digest=_digest("static-bindings"),
        binding_schema_digest=_digest("binding-schema"),
    )


def _inert() -> InertPrepareAttestation:
    return InertPrepareAttestation(
        supervisor_sha256=_digest("supervisor"),
        supervisor_size_bytes=1,
        supervisor_identity_digest=_digest("supervisor-identity"),
        worker_sha256=_digest("supervisor"),
        worker_size_bytes=1,
        worker_identity_digest=_digest("supervisor-identity"),
        ffmpeg_sha256=_digest("ffmpeg"),
        ffmpeg_size_bytes=1,
        ffmpeg_identity_digest=_digest("ffmpeg-identity"),
        ffmpeg_version_digest=_digest("ffmpeg-version"),
        executable_lease_verified=True,
    )


def _store(root: Path) -> _D1N2AuthorityStore:
    return _D1N2AuthorityStore(root, _TestNamedMutex(f"i0-{root.name}"))


def _revoked(store: _D1N2AuthorityStore, consumed_digest: str) -> str:
    issued = store.issue_worker_grant(consumed_digest, _digest("challenge"), _digest("capability"))
    assert issued is not None
    revoked = store.revoke_worker_grant(issued.record_digest)
    assert revoked is not None
    return revoked.record_digest


def test_i0_exact_isolated_namespace_and_closed_filenames(tmp_path: Path) -> None:
    store = _store(tmp_path)

    assert SCHEMA_VERSION == 3
    assert AUTHORITY_REVISION == "d1-n2-authority-v1"
    assert DIRECTORY_LEAF == "d1-n2-authority-v1"
    assert PREPARED_RECORD_NAME == "prepared.v3.json"
    assert TERMINAL_RECORD_NAME == "terminal.v3.json"
    assert WORKER_GRANT_RECORD_NAME == "worker-grant.v2.json"
    assert AUTHORITY_MUTEX_NAME == r"Local\PDUExamObserver.D1N2.AuthorityV1"
    assert VIDEO_MUTEX_NAME == r"Local\PDUExamObserver.D1N2.VideoOnly"
    assert JOB_NAME_PREFIX == r"Local\PDUExamObserver.D1N2.Capture."
    assert store.directory == tmp_path / DIRECTORY_LEAF
    assert store.inspect().state is D1N2State.ABSENT


def test_i0_pending_prepared_consumed_terminal_are_monotonic_and_no_overwrite(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    pending = store.reserve_pending()
    assert pending is not None and pending.state is D1N2State.PENDING
    pending_bytes = store.prepared_path.read_bytes()
    assert store.reserve_pending() is None
    assert store.prepared_path.read_bytes() == pending_bytes

    prepared = store.finalize_prepared(pending.record_digest, _static(), _inert())
    assert prepared is not None and prepared.state is D1N2State.PREPARED
    assert store.finalize_prepared(pending.record_digest, _static(), _inert()) is None

    consumed = store.consume(prepared.record_digest, _digest("run"))
    assert consumed is not None and consumed.state is D1N2State.CONSUMED
    assert store.consume(prepared.record_digest, _digest("second-run")) is None

    terminal = store.finalize_terminal(
        consumed.record_digest,
        TerminalCode.NONLAUNCHING_NO_GO,
        _revoked(store, consumed.record_digest),
    )
    assert terminal is not None and terminal.state is D1N2State.TERMINAL
    terminal_bytes = store.terminal_path.read_bytes()
    assert (
        store.finalize_terminal(
            consumed.record_digest, TerminalCode.NONLAUNCHING_NO_GO, _digest("wrong-grant")
        )
        is None
    )
    assert store.terminal_path.read_bytes() == terminal_bytes
    assert store.inspect().state is D1N2State.TERMINAL


@pytest.mark.parametrize("state", (D1N2State.PENDING, D1N2State.CONSUMED))
def test_i0_crash_observed_pending_or_consumed_is_permanently_nonlaunchable(
    tmp_path: Path, state: D1N2State
) -> None:
    store = _store(tmp_path)
    pending = store.reserve_pending()
    assert pending is not None
    if state is D1N2State.CONSUMED:
        prepared = store.finalize_prepared(pending.record_digest, _static(), _inert())
        assert prepared is not None
        assert store.consume(prepared.record_digest, _digest("run")) is not None

    restarted = _store(tmp_path)
    result = _prepare_once(restarted, _static, _inert)
    assert result.status is D1N2PrepareStatus.STATE_CLOSED
    assert result.native_side_effects is False
    assert restarted.inspect().state is state


def test_i0_invalid_record_is_closed_and_preserved(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.directory.mkdir(parents=True)
    malformed = b'{"state":"PREPARED"}'
    store.prepared_path.write_bytes(malformed)

    inspection = store.inspect()
    assert inspection.state is None and inspection.invalid is True
    assert store.reserve_pending() is None
    assert store.prepared_path.read_bytes() == malformed


@pytest.mark.parametrize(
    "mutant",
    ("duplicate", "missing", "extra", "wrong_type", "revision", "nonfinite", "nonregular"),
)
def test_i0_closed_record_parser_rejects_canonical_mutants(tmp_path: Path, mutant: str) -> None:
    store = _store(tmp_path)
    pending = store.reserve_pending()
    assert pending is not None
    original = store.prepared_path.read_bytes()
    if mutant == "duplicate":
        mutated = original.replace(b'"schema_version":3', b'"schema_version":3,"schema_version":3')
        store.prepared_path.write_bytes(mutated)
    elif mutant == "nonfinite":
        store.prepared_path.write_bytes(b'{"schema_version":NaN}')
    elif mutant == "nonregular":
        store.prepared_path.unlink()
        store.prepared_path.mkdir()
    else:
        raw = json.loads(original)
        if mutant == "missing":
            raw.pop("record_digest")
        elif mutant == "extra":
            raw["unexpected"] = True
        elif mutant == "wrong_type":
            raw["schema_version"] = True
        else:
            raw["authority_revision"] = "wrong"
        store.prepared_path.write_text(json.dumps(raw), encoding="utf-8")

    assert store.inspect().invalid is True
    assert store.reserve_pending() is None


def test_i0_concurrent_reserve_has_one_winner(tmp_path: Path) -> None:
    first = _store(tmp_path)
    second = _store(tmp_path)
    barrier = threading.Barrier(2)
    results: list[object] = []

    def reserve(store: _D1N2AuthorityStore) -> None:
        barrier.wait()
        results.append(store.reserve_pending())

    workers = [threading.Thread(target=reserve, args=(store,)) for store in (first, second)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert sum(result is not None for result in results) == 1


@pytest.mark.parametrize("fault", ("static", "inert"))
def test_i1_post_pending_attestation_fault_is_sticky(tmp_path: Path, fault: str) -> None:
    def broken_static() -> StaticBindingAttestation:
        raise RuntimeError("inert static fault")

    def broken_inert() -> InertPrepareAttestation:
        raise RuntimeError("inert binding fault")

    result = _prepare_once(
        _store(tmp_path),
        broken_static if fault == "static" else _static,
        broken_inert if fault == "inert" else _inert,
    )
    assert result.status is D1N2PrepareStatus.PENDING_NONLAUNCHABLE
    assert _store(tmp_path).inspect().state is D1N2State.PENDING


def test_i0_prepared_record_persists_only_a_sanitized_binding_digest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    pending = store.reserve_pending()
    assert pending is not None
    assert store.finalize_prepared(pending.record_digest, _static(), _inert()) is not None

    payload = json.loads(store.prepared_path.read_text(encoding="utf-8"))
    assert "attestation" not in payload
    assert set(payload) == {
        "schema_version",
        "authority_revision",
        "state",
        "static_bindings_digest",
        "binding_schema_digest",
        "prepared_binding_digest",
        "record_digest",
    }


def test_i0_terminal_requires_the_exact_persisted_consumed_digest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    pending = store.reserve_pending()
    assert pending is not None
    prepared = store.finalize_prepared(pending.record_digest, _static(), _inert())
    assert prepared is not None
    consumed = store.consume(prepared.record_digest, _digest("consumed"))
    assert consumed is not None
    revoked_digest = _revoked(store, consumed.record_digest)
    assert (
        store.finalize_terminal(
            consumed.record_digest, TerminalCode.NONLAUNCHING_NO_GO, revoked_digest
        )
        is not None
    )

    terminal = json.loads(store.terminal_path.read_text(encoding="utf-8"))
    terminal["consumed_record_digest"] = _digest("different-consumed-record")
    terminal["record_digest"] = authority._digest(
        {key: value for key, value in terminal.items() if key != "record_digest"}
    )
    store.terminal_path.write_text(json.dumps(terminal), encoding="utf-8")

    assert store.inspect().invalid is True
    assert (
        store.finalize_terminal(
            consumed.record_digest, TerminalCode.NONLAUNCHING_NO_GO, revoked_digest
        )
        is None
    )


def test_i0_never_contacts_legacy_parent_or_imports_native_adapter(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy-authority-sentinel.json"
    legacy.write_text("untouched", encoding="utf-8")
    store = _store(tmp_path)
    assert store.reserve_pending() is not None

    assert legacy.read_text(encoding="utf-8") == "untouched"
    source = Path(inspect.getsourcefile(_D1N2AuthorityStore) or "").read_text(encoding="utf-8")
    assert "m2_d1_native" not in source
    assert "d1-n1" not in source.lower()


def test_i1_inert_prepare_binds_static_values_and_stays_nonlaunching(
    tmp_path: Path,
) -> None:
    result = _prepare_once(_store(tmp_path), _static, _inert)

    assert result.status is D1N2PrepareStatus.PREPARED_NONLAUNCHING
    assert result.native_side_effects is False
    assert result.record is not None and result.record.state is D1N2State.PREPARED
    payload = json.loads((tmp_path / DIRECTORY_LEAF / PREPARED_RECORD_NAME).read_text())
    assert payload["static_bindings_digest"] == _static().static_bindings_digest
    assert payload["binding_schema_digest"] == _static().binding_schema_digest
    assert payload["prepared_binding_digest"] == _inert().binding_digest()

    def mismatch() -> StaticBindingAttestation:
        return replace(_static(), static_bindings_digest="not-a-digest")

    failed = _prepare_once(_store(tmp_path / "mismatch"), mismatch, _inert)
    assert failed.status is D1N2PrepareStatus.PENDING_NONLAUNCHABLE
