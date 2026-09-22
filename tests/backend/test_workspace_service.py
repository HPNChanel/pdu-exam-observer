from pathlib import Path

import pytest

from pdu_exam_observer.services.core import M0Backend
from pdu_exam_observer.workspace_service import WorkspaceBackend, WorkspaceService


class Runtime:
    def __init__(self) -> None:
        self.row = {"session_id": "r1", "source_kind": "AI_RENDERED", "state": "DRAFT"}
        self.created = 0

    def create_session(self, source_kind: str) -> dict[str, object]:
        self.created += 1
        self.row["source_kind"] = source_kind
        return self.row.copy()

    def get_session(self, sid: str) -> dict[str, object]:
        return self.row.copy()

    def list_sessions(self) -> list[dict[str, object]]:
        return [self.row.copy()] if self.created else []

    def events_after(self, sid: str) -> list[dict[str, object]]:
        return []

    def list_reviews(self, sid: str) -> list[dict[str, object]]:
        return []

    def preflight(self, sid: str) -> dict[str, object]:
        self.row["state"] = "PREFLIGHT_READY"
        return self.row.copy()

    def start_synthetic_demo(self, sid: str) -> dict[str, object]:
        self.row["state"] = "RECORDING"
        return self.row.copy()

    def close(self) -> None:
        pass


def test_start_requires_paired_exam_readiness_and_create_is_idempotent(tmp_path: Path) -> None:
    runtime = Runtime()
    backend = M0Backend()
    service = WorkspaceService(tmp_path, backend, runtime)
    row = service.create("AI_RENDERED", "create-key")
    assert service.create("AI_RENDERED", "create-key")["session_id"] == row["session_id"]
    assert runtime.created == 1
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        service.create("REAL", "create-key")
    with pytest.raises(ValueError, match="EXAM_NOT_READY"):
        service.action("r1", "start", "start-one")
    exam_id = row["exam_session_id"]
    backend.apply_session_action(exam_id, "consent")
    backend.apply_session_action(exam_id, "preflight")
    service.action("r1", "preflight", "preflight-one")
    assert service.action("r1", "start", "start-two")["state"] == "RECORDING"
    assert backend.snapshot(exam_id).state == "RECORDING"
    service.close()


def test_runtime_failure_stops_exam_answers(tmp_path: Path) -> None:
    backend = WorkspaceBackend(tmp_path, encryption_status="UNVERIFIED", acl_status="UNVERIFIED")
    record, _ = backend.create_session()
    for action in ("consent", "preflight", "start"):
        backend.apply_session_action(record.session_id, action)
    backend.runtime_state = lambda _: "FAILED"
    with pytest.raises(ValueError):
        backend.record_answer(record.session_id, "answer-fault", {"answer_id": "a1"})
    assert backend.snapshot(record.session_id).state == "FAILED"
    backend.store.close()
