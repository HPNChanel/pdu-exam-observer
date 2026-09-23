from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import sqlite3
import time
from pathlib import Path

import pytest

from pdu_exam_observer.research_runtime import InvalidTransition
from pdu_exam_observer.research_runtime.service import (
    AuthorityDenied,
    ResearchRuntimeService,
)


def _lease_probe(root: str, result: object) -> None:
    try:
        service = ResearchRuntimeService(Path(root))
    except ValueError as error:
        result.put(str(error))  # type: ignore[union-attr]
    else:
        service.close()
        result.put("OPENED")  # type: ignore[union-attr]


def _write_tiny_synthetic_fixture(service: ResearchRuntimeService, session_id: str) -> None:
    """Avoid video rendering while preserving the real artifact-manifest path."""
    row = service._session_row(session_id)
    directory = service._owned_artifact_directory(row)
    video = directory / "raw_video.mp4"
    timeline = directory / "pose_timeline.jsonl"
    video.write_bytes(b"synthetic-video-bytes")
    observations = [
        {
            "frame_seq": index,
            "captured_ns": index * 1_000_000_000,
            "pose_count": 1,
            "landmarks": [],
            "quality": {"state": "SYNTHETIC"},
            "focus": "EXAM_FOCUSED",
            "focus_age_ms": 0,
        }
        for index in (1, 2)
    ]
    timeline.write_text("".join(json.dumps(item) + "\n" for item in observations), encoding="utf-8")
    for artifact in (video, timeline):
        service._connection.execute(
            "INSERT INTO runtime_artifacts VALUES(?,?,?,?)",
            (
                session_id,
                artifact.name,
                hashlib.sha256(artifact.read_bytes()).hexdigest(),
                artifact.stat().st_size,
            ),
        )


@pytest.fixture
def sealed_synthetic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[ResearchRuntimeService, dict[str, object], dict[str, object]]:
    monkeypatch.setattr(
        ResearchRuntimeService,
        "_write_synthetic_fixture_locked",
        _write_tiny_synthetic_fixture,
    )
    service = ResearchRuntimeService(tmp_path)
    session = service.create_session(source_kind="AI_RENDERED")
    service.preflight(str(session["session_id"]))
    service.start_synthetic_demo(str(session["session_id"]))
    service.stop(str(session["session_id"]))
    sealed = service.seal(str(session["session_id"]))
    try:
        yield service, session, sealed
    finally:
        service.close()


def _observable_event(service: ResearchRuntimeService, session_id: str) -> dict[str, object]:
    return next(
        event
        for event in service.events_after(session_id)
        if event["event_type"] == "OBSERVABLE_EVENT"
    )


def test_second_process_cannot_claim_the_same_runtime_root(tmp_path: Path) -> None:
    service = ResearchRuntimeService(tmp_path)
    context = mp.get_context("spawn")
    results = context.Queue()
    child = context.Process(target=_lease_probe, args=(str(tmp_path), results))
    child.start()
    child.join(timeout=10)
    try:
        assert child.exitcode == 0
        assert results.get(timeout=1) == "RUNTIME_ROOT_ALREADY_OWNED"
    finally:
        service.close()


def test_unknown_runtime_schema_fails_closed_and_releases_its_lease(tmp_path: Path) -> None:
    database = tmp_path / "research-runtime.v1.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="RUNTIME_SCHEMA_INCOMPATIBLE"):
        ResearchRuntimeService(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version=0")
    reopened = ResearchRuntimeService(tmp_path)
    reopened.close()


def test_tampered_sealed_artifacts_block_preview_and_export(
    sealed_synthetic: tuple[ResearchRuntimeService, dict[str, object], dict[str, object]],
) -> None:
    service, session, sealed = sealed_synthetic
    session_id = str(session["session_id"])
    event = _observable_event(service, session_id)
    service.review(
        session_id,
        str(event["event_id"]),
        "NORMAL",
        "CONFIRMED",
        0,
        1000,
        "bounded synthetic review",
        int(sealed["revision"]),
    )
    service.lock(session_id)
    timeline = Path(service.get_session(session_id)["artifact_directory"]) / "pose_timeline.jsonl"
    timeline.write_text("tampered", encoding="utf-8")
    with pytest.raises(InvalidTransition, match="ARTIFACT_INTEGRITY_FAILED"):
        service.preview_path(session_id)
    with pytest.raises(InvalidTransition, match="ARTIFACT_INTEGRITY_FAILED"):
        service.export_allowlisted(session_id)


def test_review_requires_observable_positive_in_timeline_nonconflicting_intervals(
    sealed_synthetic: tuple[ResearchRuntimeService, dict[str, object], dict[str, object]],
) -> None:
    service, session, sealed = sealed_synthetic
    session_id = str(session["session_id"])
    event = _observable_event(service, session_id)
    revision = int(sealed["revision"])
    with pytest.raises(ValueError, match="event does not belong"):
        service.review(
            session_id, "not-an-observable-event", "NORMAL", "CONFIRMED", 0, 1, "reason", revision
        )
    with pytest.raises(ValueError, match="invalid review boundary"):
        service.review(
            session_id, str(event["event_id"]), "NORMAL", "CONFIRMED", 0, 0, "reason", revision
        )
    with pytest.raises(ValueError, match="REVIEW_OUTSIDE_TIMELINE"):
        service.review(
            session_id, str(event["event_id"]), "NORMAL", "CONFIRMED", 0, 1068, "reason", revision
        )

    first = service.review(
        session_id,
        str(event["event_id"]),
        "NORMAL",
        "CONFIRMED",
        0,
        800,
        "first decision",
        revision,
    )
    overlapping = service.review(
        session_id,
        "",
        "MULTIPLE_PEOPLE",
        "CONFIRMED",
        500,
        1000,
        "manual overlap",
        int(first["revision"]),
    )
    with pytest.raises(InvalidTransition, match="CONFLICTING_REVIEW_INTERVALS"):
        service.lock(session_id)
    replacement = service.review(
        session_id,
        str(overlapping["event_id"]),
        "MULTIPLE_PEOPLE",
        "REJECTED",
        500,
        1000,
        "newest decision wins",
        int(overlapping["revision"]),
    )
    reviews = service.list_reviews(session_id)
    assert [review["revision"] for review in reviews] == [
        int(first["revision"]),
        int(overlapping["revision"]),
        int(replacement["revision"]),
    ]
    service.lock(session_id)


def test_symlinked_artifact_directory_cannot_escape_preview_scope(
    sealed_synthetic: tuple[ResearchRuntimeService, dict[str, object], dict[str, object]],
    tmp_path: Path,
) -> None:
    service, session, _sealed = sealed_synthetic
    directory = Path(service.get_session(str(session["session_id"]))["artifact_directory"])
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "raw_video.mp4").write_bytes(b"outside")
    staged = directory.with_name(directory.name + ".staged")
    directory.rename(staged)
    try:
        directory.symlink_to(outside, target_is_directory=True)
    except OSError:
        staged.rename(directory)
        pytest.skip("directory symlink creation is unavailable on this Windows configuration")
    with pytest.raises(AuthorityDenied, match="ARTIFACT_SCOPE_INVALID"):
        service.preview_path(str(session["session_id"]))
    assert (outside / "raw_video.mp4").read_bytes() == b"outside"


def test_revoked_session_bound_authority_allows_owned_deletion_but_not_collection(
    tmp_path: Path,
) -> None:
    reference = "withdrawal-2026"
    record: dict[str, object] = {
        "authority_reference": reference,
        "status": "APPROVED",
        "consent_status": "CONFIRMED",
        "participant_pseudonym": "participant-01",
        "native_root_digest": ResearchRuntimeService.root_digest(tmp_path),
        "consent_policy_sha256": "a" * 64,
        "institutional_approval_sha256": "b" * 64,
        "retention_record_sha256": "c" * 64,
        "retention_expires_at": time.time() + 3600,
        "protocol_version": "protocol-2026-v1",
        "consent_receipt_id": "receipt-2026-001",
        "consent_version": "consent-v1",
        "operator_pseudonym": "operator-7f2a",
        "device_gate_decision": "UNVERIFIED",
    }
    service = ResearchRuntimeService(
        tmp_path,
        authority_resolver=lambda _reference: record,
        diagnostic_provider=lambda: {"camera": "READY", "display": "READY", "disk": "READY"},
        camera_factory=lambda: type(
            "ClosedCamera",
            (),
            {"isOpened": lambda _self: False, "release": lambda _self: None},
        )(),
    )
    try:
        session = service.create_session(source_kind="REAL")
        session_id = str(session["session_id"])
        record["session_pseudonym"] = session_id
        service.preflight(session_id)
        service.start_real_collection(session_id, reference)
        artifact = (
            Path(service.get_session(session_id)["artifact_directory"]) / "raw_video.partial.avi"
        )
        artifact.write_text("owned runtime artifact", encoding="utf-8")

        record.update(
            status="REVOKED",
            consent_status="WITHDRAWN",
            retention_expires_at=1,
            withdrawal_authority_sha256="d" * 64,
            withdrawal_decision="DELETE_OWNED_RUNTIME_ARTIFACTS",
        )
        withdrawn = service.withdraw(session_id, reference)
        assert withdrawn["state"] == "WITHDRAWN"
        assert not artifact.exists()

        blocked = service.create_session(source_kind="REAL")
        blocked_id = str(blocked["session_id"])
        record["session_pseudonym"] = blocked_id
        service.preflight(blocked_id)
        with pytest.raises(AuthorityDenied):
            service.start_real_collection(blocked_id, reference)
    finally:
        service.close()
