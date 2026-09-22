from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from pdu_exam_observer.research_runtime import (
    AuthorityDenied,
    InvalidTransition,
    ResearchRuntimeService,
    RevisionConflict,
)


def _authority(root: Path, reference: str) -> dict[str, str]:
    return {
        "authority_reference": reference,
        "status": "APPROVED",
        "consent_policy_sha256": "a" * 64,
        "institutional_approval_sha256": "b" * 64,
        "retention_record_sha256": "c" * 64,
        "native_root_digest": ResearchRuntimeService.root_digest(root),
        "participant_pseudonym": "participant-approved-01",
        "consent_status": "CONFIRMED",
        "retention_expires_at": time.time() + 3600,
        "protocol_version": "protocol-2026-v1",
        "consent_receipt_id": "receipt-2026-001",
        "consent_version": "consent-v1",
        "operator_pseudonym": "operator-7f2a",
        "device_gate_decision": "UNVERIFIED",
    }


def _service(root: Path) -> ResearchRuntimeService:
    class _BlockedCamera:
        def isOpened(self) -> bool:
            return True

        def set(self, *_: object) -> bool:
            return True

        def read(self) -> tuple[bool, object]:
            time.sleep(0.2)
            return False, None

        def release(self) -> None:
            return None

    return ResearchRuntimeService(
        root,
        authority_resolver=lambda reference: _authority(root, reference),
        diagnostic_provider=lambda: {"camera": "READY", "display": "READY", "disk": "READY"},
        camera_factory=_BlockedCamera,
    )


REAL_PREFLIGHT = {"camera": "READY", "display": "READY", "disk": "READY"}


def test_synthetic_lifecycle_persists_monotonic_events_and_recovers(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session(source_kind="AI_RENDERED")
    service.preflight(session["session_id"])
    started = service.start_synthetic_demo(session["session_id"])
    assert started["state"] == "RECORDING"
    events = service.events_after(session["session_id"])
    assert [event["event_seq"] for event in events] == list(range(1, len(events) + 1))
    assert all(event["source_kind"] == "AI_RENDERED" for event in events)
    service.stop(session["session_id"])
    sealed = service.seal(session["session_id"])
    service.close()

    reopened = _service(tmp_path)
    assert reopened.get_session(session["session_id"])["state"] == "SEALED"
    assert reopened.get_session(session["session_id"])["revision"] == sealed["revision"]
    reopened.close()


def test_real_collection_needs_native_resolved_authority_and_one_active_owner(
    tmp_path: Path,
) -> None:
    denied = ResearchRuntimeService(
        tmp_path,
        authority_resolver=lambda _reference: None,
        diagnostic_provider=lambda: REAL_PREFLIGHT,
        camera_factory=lambda: None,
    )
    first = denied.create_session(source_kind="REAL", participant_pseudonym="participant-01")
    denied.preflight(first["session_id"], REAL_PREFLIGHT)
    with pytest.raises(AuthorityDenied):
        denied.start_real_collection(first["session_id"], "study-2026")
    denied.close()

    service = _service(tmp_path)
    first = service.get_session(first["session_id"])
    assert first["state"] == "PREFLIGHT_READY"
    service._authority_resolver = lambda ref: _authority(tmp_path, ref) | {
        "session_pseudonym": first["session_id"]
    }
    service.start_real_collection(first["session_id"], "study-2026")
    second = service.create_session(source_kind="REAL", participant_pseudonym="participant-02")
    service.preflight(second["session_id"], REAL_PREFLIGHT)
    service._authority_resolver = lambda ref: _authority(tmp_path, ref) | {
        "session_pseudonym": second["session_id"]
    }
    with pytest.raises(InvalidTransition, match="active collection"):
        service.start_real_collection(second["session_id"], "study-2026")
    service.close()


def test_frame_failure_fails_closed_and_sealed_preview_exists(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session(source_kind="AI_RENDERED")
    service.preflight(session["session_id"])
    service.start_synthetic_demo(session["session_id"])
    failed = service.ingest_frame(session["session_id"], np.zeros((1, 1), dtype=np.uint8))
    assert failed["state"] == "FAILED"
    with pytest.raises(InvalidTransition):
        service.seal(session["session_id"])
    service.close()


def test_interrupted_recording_is_failed_on_recovery(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session(source_kind="AI_RENDERED")
    service.preflight(session["session_id"])
    service.start_synthetic_demo(session["session_id"])
    service.close()

    recovered = _service(tmp_path)
    state = recovered.get_session(session["session_id"])
    assert state["state"] == "FAILED"
    assert state["failure_reason"] == "RECOVERY_REQUIRED"
    assert recovered.events_after(session["session_id"])[-1]["event_type"] == "TECHNICAL_FAILURE"
    recovered.close()


def test_review_revision_lock_export_privacy_and_test_artifact_withdrawal(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session(source_kind="AI_RENDERED")
    service.preflight(session["session_id"])
    service.start_synthetic_demo(session["session_id"])
    service.stop(session["session_id"])
    sealed = service.seal(session["session_id"])
    event = next(
        event
        for event in service.events_after(session["session_id"])
        if event["event_type"] == "OBSERVABLE_EVENT"
    )
    service.review(
        session["session_id"],
        event["event_id"],
        "UNCERTAIN",
        "UNCERTAIN",
        0,
        1000,
        "insufficient visual evidence",
        sealed["revision"],
    )
    with pytest.raises(RevisionConflict):
        service.review(
            session["session_id"],
            event["event_id"],
            "UNCERTAIN",
            "UNCERTAIN",
            0,
            1000,
            "stale",
            sealed["revision"],
        )
    service.lock(session["session_id"])
    bundle = service.export_allowlisted(session["session_id"])
    assert bundle.payload[:2] == b"PK"
    with __import__("zipfile").ZipFile(__import__("io").BytesIO(bundle.payload)) as archive:
        records = archive.read("records.jsonl").decode("utf-8")
    for exported in map(json.loads, records.splitlines()):
        assert set(exported["focus"]) == {"state", "signal_age_ms", "contaminated_by_operator"}
        assert type(exported["focus"]["contaminated_by_operator"]) is bool
        assert not {"operator_id", "operator_name", "operator_audit", "audit", "path"} & set(
            exported
        )
    assert "raw_video" not in records.lower()
    assert set(json.loads(records.splitlines()[0])) == {
        "export_id",
        "manifest_sha256",
        "schema_version",
        "record_count",
        "sample_id",
        "participant_pseudonym",
        "session_pseudonym",
        "source_kind",
        "parent_provenance_id",
        "pose",
        "label",
        "quality",
        "focus",
        "timing",
    }
    withdrawn = service.withdraw_test_artifacts(session["session_id"])
    assert withdrawn["state"] == "WITHDRAWN"
    assert not Path(withdrawn["artifact_directory"]).exists()
    service.close()


def test_lock_rejects_unreviewed_event_and_frame_artifacts_are_streamed(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session(source_kind="AI_RENDERED")
    service.preflight(session["session_id"])
    service.start_synthetic_demo(session["session_id"])
    with pytest.raises(InvalidTransition, match="UNREVIEWED_EVENT"):
        service.stop(session["session_id"])
        service.seal(session["session_id"])
        service.lock(session["session_id"])
    service.close()


def test_pose_and_video_are_streamed_to_sealed_local_artifacts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.create_session(source_kind="AI_RENDERED")
    service.preflight(session["session_id"])
    service.start_synthetic_demo(session["session_id"])
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert service.ingest_frame(session["session_id"], frame)["state"] == "RECORDING"
    stopped = service.stop(session["session_id"])
    service.seal(session["session_id"])
    directory = Path(stopped["artifact_directory"])
    assert (directory / "pose_timeline.jsonl").is_file()
    assert service.preview_path(session["session_id"]).name == "raw_video.mp4"
    assert not list(directory.glob("*.partial*"))
    service.close()


def test_real_withdrawal_requires_native_delete_decision_for_owned_test_artifacts(
    tmp_path: Path,
) -> None:
    record = _authority(tmp_path, "withdrawal-fixture") | {
        "withdrawal_authority_sha256": "d" * 64,
        "withdrawal_decision": "DELETE_OWNED_RUNTIME_ARTIFACTS",
    }
    service = ResearchRuntimeService(
        tmp_path,
        authority_resolver=lambda _reference: record,
        diagnostic_provider=lambda: REAL_PREFLIGHT,
        camera_factory=lambda: type(
            "ClosedCamera",
            (),
            {"isOpened": lambda _self: False, "release": lambda _self: None},
        )(),
    )
    session = service.create_session(source_kind="REAL")
    record["session_pseudonym"] = session["session_id"]
    service.preflight(session["session_id"])
    service.start_real_collection(session["session_id"], "withdrawal-fixture")
    withdrawn = service.withdraw(session["session_id"], "withdrawal-fixture")
    assert withdrawn["state"] == "WITHDRAWN"
    assert not Path(withdrawn["artifact_directory"]).exists()
    service.close()
