from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from pdu_exam_observer.research_runtime import (
    AuthorityDenied,
    InvalidTransition,
    ResearchRuntimeService,
)


def authority(root: Path) -> dict[str, object]:
    return {
        "authority_reference": "unit-fixture",
        "status": "APPROVED",
        "consent_policy_sha256": "a" * 64,
        "institutional_approval_sha256": "b" * 64,
        "retention_record_sha256": "c" * 64,
        "native_root_digest": ResearchRuntimeService.root_digest(root),
        "participant_pseudonym": "unit-participant",
        "consent_status": "CONFIRMED",
        "retention_expires_at": time.time() + 3600,
        "withdrawal_authority_sha256": "d" * 64,
        "withdrawal_decision": "DELETE_OWNED_RUNTIME_ARTIFACTS",
    }


def sealed_authority_fixture(root: Path):
    record = authority(root)
    service = ResearchRuntimeService(root, authority_resolver=lambda _: record)
    sid = str(service.create_session()["session_id"])
    service.preflight(sid)
    service.start_synthetic_demo(sid)
    service.stop(sid)
    service.seal(sid)
    # In-memory authority test setup only; never exported as research data.
    with service._connection:
        service._update_session_locked(
            sid,
            source_kind="REAL",
            participant_pseudonym="unit-participant",
            authority_reference="unit-fixture",
            locked=1,
        )
    record["session_pseudonym"] = sid
    return service, sid, record


def test_revoked_authority_blocks_preview_export_and_next_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, sid, record = sealed_authority_fixture(tmp_path)
    try:
        with service.open_preview(sid) as handle:
            assert handle.read(12)
        record.update(status="REVOKED", consent_status="WITHDRAWN")
        with pytest.raises(AuthorityDenied):
            service.open_preview(sid)
        with pytest.raises(AuthorityDenied):
            service.export_allowlisted(sid)
        with service._connection:
            service._update_session_locked(sid, state="RECORDING")
        writes: list[object] = []
        monkeypatch.setattr(service, "_write_frame_locked", lambda *args: writes.append(args))
        result = service.ingest_frame(sid, np.zeros((720, 1280, 3), dtype=np.uint8))
        assert result["state"] == "FAILED"
        assert result["failure_reason"] == "COLLECTION_AUTHORITY_INVALID"
        assert not writes
    finally:
        service.close()


def test_replaced_authority_must_still_bind_the_same_session(tmp_path: Path) -> None:
    service, sid, record = sealed_authority_fixture(tmp_path)
    try:
        record["session_pseudonym"] = "another-session"
        with pytest.raises(AuthorityDenied, match="AUTHORITY_SESSION_MISMATCH"):
            service.open_preview(sid)
        with pytest.raises(AuthorityDenied, match="AUTHORITY_SESSION_MISMATCH"):
            service.export_allowlisted(sid)
    finally:
        service.close()


@pytest.mark.parametrize("real", [False, True])
def test_withdrawal_preserves_untracked_files_and_verifies_owned_inventory(
    tmp_path: Path,
    real: bool,
) -> None:
    service, sid, _record = sealed_authority_fixture(tmp_path)
    if not real:
        with service._connection:
            service._update_session_locked(sid, source_kind="AI_RENDERED")
    directory = Path(str(service.get_session(sid)["artifact_directory"]))
    extra = directory / "not-owned.txt"
    extra.write_text("preserve this untracked file")
    try:
        with pytest.raises(InvalidTransition, match="UNOWNED_ARTIFACT_PRESENT"):
            service.withdraw(sid, "unit-fixture") if real else service.withdraw_test_artifacts(sid)
        assert extra.read_text() == "preserve this untracked file"
        assert (directory / "raw_video.mp4").is_file()
        assert service.get_session(sid)["state"] == "SEALED"
        extra.unlink()  # Remove this test's own injected file before the positive control.
        result = (
            service.withdraw(sid, "unit-fixture") if real else service.withdraw_test_artifacts(sid)
        )
        assert result["state"] == "WITHDRAWN"
        assert not directory.exists()
        if real:
            receipt = service.events_after(sid)[-1]
            assert {item["name"] for item in receipt["artifacts"]} == {
                "raw_video.mp4",
                "pose_timeline.jsonl",
            }
    finally:
        service.close()


def test_withdrawal_does_not_delete_or_release_ownership_while_camera_thread_lives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = threading.Event(), threading.Event()

    class BlockedCamera:
        def isOpened(self):
            return True

        def set(self, *_args):
            return True

        def read(self):
            entered.set()
            release.wait(20)
            return False, None

        def release(self):
            pass

    record = authority(tmp_path)
    service = ResearchRuntimeService(
        tmp_path,
        authority_resolver=lambda _: record,
        camera_factory=BlockedCamera,
        diagnostic_provider=lambda: {"camera": "READY", "display": "READY", "disk": "READY"},
    )
    sid = str(service.create_session(source_kind="REAL")["session_id"])
    record["session_pseudonym"] = sid
    service.preflight(sid)
    service.start_real_collection(sid, "unit-fixture")
    worker = service._capture_threads[sid]
    actual_join = worker.join
    try:
        assert entered.wait(2)
        monkeypatch.setattr(worker, "join", lambda timeout: None)
        result = service.withdraw(sid, "unit-fixture")
        assert result["state"] == "FAILED"
        assert result["failure_reason"] == "CAMERA_STOP_TIMEOUT"
        assert Path(str(result["artifact_directory"])).is_dir()
        assert service._capture_threads[sid].is_alive()
        next_sid = str(service.create_session()["session_id"])
        service.preflight(next_sid)
        with pytest.raises(InvalidTransition, match="active collection"):
            service.start_synthetic_demo(next_sid)
    finally:
        release.set()
        actual_join(timeout=5)
        service.close()
