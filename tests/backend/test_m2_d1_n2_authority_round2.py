from __future__ import annotations

import inspect
from pathlib import Path

import pdu_exam_observer.m2_d1_n2_authority as authority
from pdu_exam_observer.m2_d1_n2_authority import (
    _KnownFolderApi,
    _resolve_production_root,
)


class _FakeKnownFolderApi:
    def __init__(self) -> None:
        self.guid: object | None = None
        self.freed = False

    def known_folder_path(self, guid: object) -> str:
        self.guid = guid
        return r"C:\fixed-local-app-data"

    def free(self) -> None:
        self.freed = True


def test_round2_known_folder_abi_uses_real_guid_and_exact_two_tier_path() -> None:
    api = _FakeKnownFolderApi()
    assert isinstance(api, _KnownFolderApi)
    root = _resolve_production_root(api)
    assert root == Path(r"C:\fixed-local-app-data") / "PDUExamObserver" / "d1-n2-authority-v1"
    assert api.freed is True
    assert api.guid is not None
    assert (api.guid.Data1, api.guid.Data2, api.guid.Data3, tuple(api.guid.Data4)) == (
        0xF1B32785,
        0x6FBA,
        0x4FCF,
        (0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
    )


def test_round2_production_source_declares_handle_safe_win32_signatures() -> None:
    source = Path(inspect.getsourcefile(authority) or "").read_text(encoding="utf-8")
    for symbol in (
        "CreateMutexW",
        "WaitForSingleObject",
        "ReleaseMutex",
        "CloseHandle",
        "CreateFileW",
        "GetFileInformationByHandleEx",
        "GetFinalPathNameByHandleW",
        "FlushFileBuffers",
        "SHGetKnownFolderPath",
        "CoTaskMemFree",
    ):
        assert symbol in source
    assert "PDUExamObserver" in source


def test_round2_release_failure_never_returns_authority(tmp_path: Path) -> None:
    class ReleaseFails:
        def acquire(self) -> bool:
            return True

        def release(self) -> bool:
            return False

    store = authority._D1N2AuthorityStore(tmp_path, ReleaseFails())
    assert store.reserve_pending() is None
    restarted = authority._D1N2AuthorityStore(
        tmp_path, authority._TestNamedMutex("round2-release-inspection")
    )
    assert restarted.inspect().state is authority.D1N2State.PENDING


def test_round2_private_grant_requires_bounded_positive_expiry(tmp_path: Path) -> None:
    store = authority._D1N2AuthorityStore(tmp_path, authority._TestNamedMutex("round2-expiry"))
    pending = store.reserve_pending()
    assert pending is not None
    static = authority.StaticBindingAttestation(authority._digest("s"), authority._digest("b"))
    inert = authority.InertPrepareAttestation(
        authority._digest("supervisor"), 1, authority._digest("supervisor-id"),
        authority._digest("supervisor"), 1, authority._digest("supervisor-id"),
        authority._digest("ffmpeg"), 1, authority._digest("ffmpeg-id"),
        authority._digest("version"), True,
    )
    prepared = store.finalize_prepared(pending.record_digest, static, inert)
    assert prepared is not None
    consumed = store.consume(prepared.record_digest, authority._digest("consumed"))
    assert consumed is not None
    assert store.issue_worker_grant(
        consumed.record_digest,
        authority._digest("challenge"),
        authority._digest("capability"),
        0,
    ) is None


def test_round2_parent_durability_failure_is_sticky_and_never_returns_pending(
    tmp_path: Path,
) -> None:
    store = authority._D1N2AuthorityStore(
        tmp_path,
        authority._TestNamedMutex("round2-durability"),
        parent_durability=lambda: False,
    )
    assert store.reserve_pending() is None
    restarted = authority._D1N2AuthorityStore(
        tmp_path, authority._TestNamedMutex("round2-durability-restart")
    )
    assert restarted.inspect().state is authority.D1N2State.PENDING
