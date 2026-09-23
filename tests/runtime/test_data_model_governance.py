"""Task-07 research data-model gates: accounting, contamination, authority fields."""

from __future__ import annotations

import io
import json
import sqlite3
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest

from pdu_exam_observer.research_runtime import (
    AuthorityDenied,
    InvalidTransition,
    ResearchRuntimeService,
)
from pdu_exam_observer.services.core import M0Backend


def authority(root: Path, reference: str = "unit-authority") -> dict[str, object]:
    return {
        "authority_reference": reference,
        "status": "APPROVED",
        "cohort": "PILOT",
        "protocol_version": "protocol-2026-v1",
        "consent_receipt_id": "receipt-2026-001",
        "consent_version": "consent-v1",
        "operator_pseudonym": "operator-7f2a",
        "device_gate_decision": "UNVERIFIED",
        "consent_policy_sha256": "a" * 64,
        "institutional_approval_sha256": "b" * 64,
        "retention_record_sha256": "c" * 64,
        "native_root_digest": ResearchRuntimeService.root_digest(root),
        "participant_pseudonym": "participant-01",
        "consent_status": "CONFIRMED",
        "retention_expires_at": time.time() + 3600,
        "withdrawal_authority_sha256": "d" * 64,
        "withdrawal_decision": "DELETE_OWNED_RUNTIME_ARTIFACTS",
    }


def _frame() -> np.ndarray:
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def _synthetic_recording(service: ResearchRuntimeService) -> str:
    session = service.create_session(source_kind="AI_RENDERED")
    session_id = str(session["session_id"])
    service.preflight(session_id)
    service.start_synthetic_demo(session_id)
    return session_id


def _export_records(bundle: object) -> list[dict[str, object]]:
    with zipfile.ZipFile(io.BytesIO(bundle.payload)) as archive:  # type: ignore[attr-defined]
        text = archive.read("records.jsonl").decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_frame_drop_and_gap_accounting_is_persisted(tmp_path: Path) -> None:
    service = ResearchRuntimeService(tmp_path)
    try:
        session_id = _synthetic_recording(service)
        base = time.perf_counter()
        service.ingest_frame(session_id, _frame(), captured_at=base, dropped_frames=3)
        service.ingest_frame(session_id, _frame(), captured_at=base + 0.067, dropped_frames=7)
        session = service.get_session(session_id)
        # The 10 reported drops are a lower bound: the fixture-boundary
        # timestamp hole is also missing capture and joins the count.
        assert session["dropped_frames"] >= 10
        assert session["gap_events"] == 2
        assert session["max_gap_frames"] >= 7

        service.stop(session_id)
        service.seal(session_id)
        # One owner per root: close before reopening to verify persistence.
        service.close()
        reopened = ResearchRuntimeService(tmp_path)
        try:
            persisted = reopened.get_session(session_id)
            assert persisted["dropped_frames"] >= 10
            assert persisted["gap_events"] == 2
            assert persisted["max_gap_frames"] >= 7
        finally:
            reopened.close()
    finally:
        service.close()


def test_write_side_frame_gap_is_counted_and_large_gap_fails_closed(
    tmp_path: Path,
) -> None:
    service = ResearchRuntimeService(tmp_path)
    try:
        session_id = _synthetic_recording(service)
        base = time.perf_counter()
        service.ingest_frame(session_id, _frame(), captured_at=base)
        # ~10 missing 66.7ms frames: the writer fills the interval by repeating
        # the last frame; that fill must be accounted, not silently absorbed.
        service.ingest_frame(session_id, _frame(), captured_at=base + 11 * 0.0667)
        session = service.get_session(session_id)
        # No drop was reported, but the fill frames are still missing real
        # captures: the hole joins dropped_frames and the gap counters.
        assert session["dropped_frames"] >= 9
        assert session["gap_events"] >= 1
        assert session["max_gap_frames"] >= 9

        failed = service.ingest_frame(session_id, _frame(), captured_at=base + 60 * 0.0667)
        assert failed["state"] == "FAILED"
        assert failed["failure_reason"] == "FRAME_GAP_EXCEEDED"
    finally:
        service.close()


def test_mark_contamination_flags_subsequent_exported_focus(tmp_path: Path) -> None:
    service = ResearchRuntimeService(tmp_path)
    try:
        session_id = _synthetic_recording(service)
        marked = service.mark_contamination(session_id)
        assert marked["contaminated_by_operator"] is True
        service.ingest_frame(session_id, _frame())
        service.stop(session_id)
        sealed = service.seal(session_id)
        for event in service.events_after(session_id):
            if event["event_type"] != "OBSERVABLE_EVENT":
                continue
            sealed = service.review(
                session_id,
                str(event["event_id"]),
                "NORMAL",
                "CONFIRMED",
                0,
                6000,
                "synthetic review",
                int(sealed["revision"]),
            )
        service.lock(session_id)
        records = _export_records(service.export_allowlisted(session_id))
        contaminated = [r for r in records if r["focus"].get("contaminated_by_operator")]
        clean = [r for r in records if not r["focus"].get("contaminated_by_operator")]
        assert contaminated and clean
        assert all(int(r["parent_provenance_id"].rsplit(":", 1)[1]) >= 91 for r in contaminated)

        with pytest.raises(InvalidTransition):
            service.mark_contamination(session_id)
    finally:
        service.close()


def test_authority_requires_consent_receipt_operator_and_gate_fields(
    tmp_path: Path,
) -> None:
    for missing in (
        "consent_receipt_id",
        "consent_version",
        "operator_pseudonym",
        "protocol_version",
        "device_gate_decision",
    ):
        root = tmp_path / missing
        root.mkdir()
        record = authority(root)
        del record[missing]
        service = ResearchRuntimeService(
            root,
            authority_resolver=lambda _ref, record=record: record,
            diagnostic_provider=lambda: {
                "camera": "READY",
                "display": "READY",
                "disk": "READY",
            },
            camera_factory=lambda: type(
                "BlockedCamera",
                (),
                {
                    "isOpened": lambda _self: True,
                    "set": lambda *_a: True,
                    "read": lambda *_a: (False, None),
                    "release": lambda _self: None,
                },
            )(),
        )
        try:
            session = service.create_session(source_kind="REAL")
            record["session_pseudonym"] = session["session_id"]
            service.preflight(session["session_id"])
            with pytest.raises(AuthorityDenied):
                service.start_real_collection(str(session["session_id"]), "unit-authority")
        finally:
            service.close()


def test_fabricated_device_gate_go_is_rejected(tmp_path: Path) -> None:
    for fabricated in ("GO", "D1_GO", "VERIFIED", "PASS"):
        root = tmp_path / fabricated.replace("_", "-")
        root.mkdir()
        record = authority(root) | {"device_gate_decision": fabricated}
        service = ResearchRuntimeService(
            root,
            authority_resolver=lambda _ref, record=record: record,
            diagnostic_provider=lambda: {
                "camera": "READY",
                "display": "READY",
                "disk": "READY",
            },
            camera_factory=lambda: type(
                "BlockedCamera",
                (),
                {
                    "isOpened": lambda _self: True,
                    "set": lambda *_a: True,
                    "read": lambda *_a: (False, None),
                    "release": lambda _self: None,
                },
            )(),
        )
        try:
            session = service.create_session(source_kind="REAL")
            record["session_pseudonym"] = session["session_id"]
            service.preflight(session["session_id"])
            with pytest.raises(AuthorityDenied):
                service.start_real_collection(str(session["session_id"]), "unit-authority")
        finally:
            service.close()


def test_protocol_version_and_operator_pseudonym_are_stamped_on_start(
    tmp_path: Path,
) -> None:
    record = authority(tmp_path)
    service = ResearchRuntimeService(
        tmp_path,
        authority_resolver=lambda _ref: record,
        diagnostic_provider=lambda: {"camera": "READY", "display": "READY", "disk": "READY"},
        camera_factory=lambda: type(
            "BlockedCamera",
            (),
            {
                "isOpened": lambda _self: True,
                "set": lambda *_a: True,
                "read": lambda *_a: (False, None),
                "release": lambda _self: None,
            },
        )(),
    )
    try:
        session = service.create_session(source_kind="REAL")
        session_id = str(session["session_id"])
        record["session_pseudonym"] = session_id
        service.preflight(session_id)
        started = service.start_real_collection(session_id, "unit-authority")
        assert started["protocol_version"] == "protocol-2026-v1"
        assert started["operator_pseudonym"] == "operator-7f2a"
    finally:
        service.close()


def test_review_and_export_rows_carry_operator_pseudonym(tmp_path: Path) -> None:
    record = authority(tmp_path)
    service = ResearchRuntimeService(tmp_path, authority_resolver=lambda _ref: record)
    try:
        session_id = _synthetic_recording(service)
        service.stop(session_id)
        sealed = service.seal(session_id)
        with service._connection:
            service._update_session_locked(
                session_id,
                source_kind="REAL",
                participant_pseudonym="participant-01",
                authority_reference="unit-authority",
                operator_pseudonym="operator-7f2a",
            )
        record["session_pseudonym"] = session_id
        event = next(
            event
            for event in service.events_after(session_id)
            if event["event_type"] == "OBSERVABLE_EVENT"
        )
        service.review(
            session_id,
            str(event["event_id"]),
            "UNCERTAIN",
            "UNCERTAIN",
            0,
            1000,
            "bounded review",
            int(sealed["revision"]),
        )
        service.lock(session_id)
        service.export_allowlisted(session_id)
        review_rows = service._connection.execute(
            "SELECT operator_pseudonym FROM runtime_reviews WHERE session_id=?",
            (session_id,),
        ).fetchall()
        export_rows = service._connection.execute(
            "SELECT operator_pseudonym FROM runtime_exports WHERE session_id=?",
            (session_id,),
        ).fetchall()
        assert [str(row[0]) for row in review_rows] == ["operator-7f2a"]
        assert [str(row[0]) for row in export_rows] == ["operator-7f2a"]
    finally:
        service.close()


def test_withdrawal_creates_export_follow_up_task_rows(tmp_path: Path) -> None:
    record = authority(tmp_path)
    service = ResearchRuntimeService(tmp_path, authority_resolver=lambda _ref: record)
    try:
        session_id = _synthetic_recording(service)
        service.stop(session_id)
        sealed = service.seal(session_id)
        with service._connection:
            service._update_session_locked(
                session_id,
                source_kind="REAL",
                participant_pseudonym="participant-01",
                authority_reference="unit-authority",
                operator_pseudonym="operator-7f2a",
            )
        record["session_pseudonym"] = session_id
        event = next(
            event
            for event in service.events_after(session_id)
            if event["event_type"] == "OBSERVABLE_EVENT"
        )
        service.review(
            session_id,
            str(event["event_id"]),
            "UNCERTAIN",
            "UNCERTAIN",
            0,
            1000,
            "bounded review",
            int(sealed["revision"]),
        )
        service.lock(session_id)
        service.export_allowlisted(session_id)
        withdrawn = service.withdraw(session_id, "unit-authority")
        assert withdrawn["state"] == "WITHDRAWN"
        tasks = service._connection.execute(
            "SELECT task_kind,target_id,status FROM runtime_withdrawal_tasks WHERE session_id=?",
            (session_id,),
        ).fetchall()
        assert len(tasks) == 1
        assert tasks[0]["task_kind"] == "EXTERNAL_EXPORT_FOLLOW_UP"
        assert tasks[0]["status"] == "PENDING"
        receipt = service.events_after(session_id)[-1]
        assert receipt["event_type"] == "WITHDRAWAL_RECORDED"
        assert receipt["external_export_follow_up_required"] is True
        with pytest.raises(InvalidTransition):
            service.withdraw(session_id, "unit-authority")
        assert (
            service._connection.execute(
                "SELECT COUNT(*) FROM runtime_withdrawal_tasks WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
            == 1
        )
    finally:
        service.close()


def test_reviewer_login_logout_emit_audit_rows_without_secrets() -> None:
    captured: list[str] = []
    backend = M0Backend()
    backend.register_reviewer_audit_hook(captured.append)
    token = backend.issue_reviewer_token()
    backend.revoke_reviewer_token(token)
    assert captured == ["REVIEWER_LOGIN", "REVIEWER_LOGOUT"]
    serialized = json.dumps(captured)
    assert token not in serialized


def test_v1_database_migrates_additively(tmp_path: Path) -> None:
    database = tmp_path / "research-runtime.v1.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE runtime_sessions(
              session_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL,
              participant_pseudonym TEXT NOT NULL, state TEXT NOT NULL,
              revision INTEGER NOT NULL, created_at REAL NOT NULL,
              started_at REAL, stopped_at REAL, sealed_at REAL,
              failure_code TEXT, locked INTEGER NOT NULL DEFAULT 0,
              frame_seq INTEGER NOT NULL DEFAULT 0, focus_state TEXT NOT NULL,
              quality_state TEXT NOT NULL, authority_reference TEXT,
              artifact_directory TEXT NOT NULL
            );
            CREATE TABLE runtime_events(
              event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
              event_seq INTEGER NOT NULL, event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL, created_at REAL NOT NULL,
              UNIQUE(session_id,event_seq)
            );
            CREATE TABLE runtime_reviews(
              review_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, event_id TEXT NOT NULL,
              label TEXT NOT NULL, review_status TEXT NOT NULL, start_ms INTEGER NOT NULL,
              end_ms INTEGER NOT NULL, reason TEXT NOT NULL, revision INTEGER NOT NULL,
              created_at REAL NOT NULL
            );
            CREATE TABLE runtime_exports(
              export_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
              manifest_sha256 TEXT NOT NULL, created_at REAL NOT NULL
            );
            CREATE TABLE runtime_artifacts(
              session_id TEXT NOT NULL, name TEXT NOT NULL, sha256 TEXT NOT NULL,
              size_bytes INTEGER NOT NULL, PRIMARY KEY(session_id,name)
            );
            PRAGMA user_version=1;
            """
        )
        connection.execute(
            "INSERT INTO runtime_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-session",
                "AI_RENDERED",
                "participant-legacy",
                "SEALED",
                0,
                time.time(),
                None,
                None,
                time.time(),
                None,
                1,
                0,
                "FOCUS_UNKNOWN",
                "UNKNOWN",
                None,
                str(tmp_path / "runtime-artifacts" / "legacy-session"),
            ),
        )
    service = ResearchRuntimeService(tmp_path)
    try:
        session = service.get_session("legacy-session")
        assert session["state"] == "SEALED"
        assert session["dropped_frames"] == 0
        assert session["protocol_version"] is None
        assert (
            service._connection.execute("PRAGMA user_version").fetchone()[0] == 2
        )
    finally:
        service.close()
