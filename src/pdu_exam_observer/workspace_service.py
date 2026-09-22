"""Connect persistent exam capabilities to the research runtime without sharing labels."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, cast

from pdu_exam_observer.contracts import SessionSnapshot
from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.services.core import M0Backend


class WorkspaceBackend(M1Backend):
    """Persist exam work and close its writable state when capture fails or ends."""

    runtime_state: Callable[[str], str | None] | None = None

    def _reconcile_runtime(self, session_id: str) -> None:
        if self.runtime_state is None:
            return
        state = self.runtime_state(session_id)
        target = {
            "FAILED": "FAILED",
            "WITHDRAWN": "WITHDRAWN",
            "STOPPED": "SEALED",
            "SEALED": "SEALED",
        }.get(state or "")
        if target is None:
            return
        with self.store.transaction() as connection:
            changed = connection.execute(
                "UPDATE sessions SET state=? WHERE id=? AND state='RECORDING'",
                (target, session_id),
            ).rowcount
            if changed:
                self._event(connection, session_id, "SessionStateChanged", {"state": target})

    def snapshot(self, session_id: str) -> SessionSnapshot | None:
        self._reconcile_runtime(session_id)
        return super().snapshot(session_id)

    def record_answer(
        self, session_id: str, idempotency_key: str, payload: dict[str, object]
    ) -> dict[str, object]:
        self._reconcile_runtime(session_id)
        return super().record_answer(session_id, idempotency_key, payload)

    def submit_exam(self, session_id: str, idempotency_key: str) -> dict[str, object]:
        self._reconcile_runtime(session_id)
        return super().submit_exam(session_id, idempotency_key)


class RuntimePort(Protocol):
    def create_session(self, source_kind: str = "AI_RENDERED") -> dict[str, Any]: ...
    def get_session(self, session_id: str) -> dict[str, Any]: ...
    def list_sessions(self) -> list[dict[str, Any]]: ...
    def preflight(self, session_id: str) -> dict[str, Any]: ...
    def start_synthetic_demo(self, session_id: str) -> dict[str, Any]: ...
    def start_real_collection(
        self, session_id: str, authority_reference: str
    ) -> dict[str, Any]: ...
    def stop(self, session_id: str) -> dict[str, Any]: ...
    def seal(self, session_id: str) -> dict[str, Any]: ...
    def events_after(self, session_id: str, seq: int = 0) -> list[dict[str, Any]]: ...
    def list_reviews(self, session_id: str) -> list[dict[str, Any]]: ...
    def review(
        self,
        session_id: str,
        event_id: str,
        label: str,
        review_status: str,
        start_ms: int,
        end_ms: int,
        reason: str,
        expected_revision: int,
    ) -> dict[str, object]: ...
    def lock(self, session_id: str) -> dict[str, Any]: ...
    def preview_path(self, session_id: str) -> Path: ...
    def export_allowlisted(self, session_id: str) -> Any: ...
    def withdraw_test_artifacts(self, session_id: str) -> dict[str, Any]: ...
    def withdraw(self, session_id: str, authority_reference: str) -> dict[str, Any]: ...
    def record_focus_context(self, session_id: str, focus_enum: str) -> Any: ...
    def close(self) -> None: ...


class ModelPort(Protocol):
    def status(self) -> dict[str, Any]: ...
    def import_bytes(self, payload: bytes) -> dict[str, Any]: ...


class WorkspaceService:
    def __init__(
        self,
        root: Path,
        backend: M0Backend,
        runtime: RuntimePort,
        models: ModelPort | None = None,
        authority_reference: str | None = None,
    ) -> None:
        root = Path(root)
        if root.is_symlink() or any(p.is_symlink() for p in root.parents):
            raise ValueError("UNSAFE_STORAGE_ROOT")
        root.mkdir(parents=True, exist_ok=True)
        database = root / "workspace.sqlite3"
        if any(
            p.is_symlink()
            for p in (database, Path(str(database) + "-wal"), Path(str(database) + "-shm"))
        ):
            raise ValueError("UNSAFE_STORAGE_ROOT")
        self.backend, self.runtime, self.models = backend, runtime, models
        self.authority_reference = authority_reference
        self._lock = RLock()
        self._closed = False
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS links("
            "runtime_id TEXT PRIMARY KEY, exam_id TEXT UNIQUE NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS requests("
            "key TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT NOT NULL)"
        )
        self.db.commit()
        if isinstance(backend, WorkspaceBackend):
            backend.runtime_state = self.runtime_state

    def runtime_state(self, exam_session_id: str) -> str | None:
        with self._lock:
            row = self.db.execute(
                "SELECT runtime_id FROM links WHERE exam_id=?", (exam_session_id,)
            ).fetchone()
            return None if row is None else str(self.runtime.get_session(str(row[0]))["state"])

    def _once(
        self, key: str, request: dict[str, object], operation: Callable[[], dict[str, object]]
    ) -> dict[str, object]:
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with self._lock:
            cached = self.db.execute(
                "SELECT digest,result FROM requests WHERE key=?", (key,)
            ).fetchone()
            if cached:
                if cached["digest"] != digest:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return cast(dict[str, object], json.loads(cached["result"]))
            result = operation()
            # Pairing capability is memory-only, as in M1. Never persist it in an idempotency row.
            stored = {k: v for k, v in result.items() if k != "pairing_code"}
            self.db.execute("INSERT INTO requests VALUES(?,?,?)", (key, digest, json.dumps(stored)))
            self.db.commit()
            return result

    def _exam_id(self, session_id: str) -> str:
        row = self.db.execute(
            "SELECT exam_id FROM links WHERE runtime_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return str(row["exam_id"])

    def summary(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": 1,
                "sessions": [self._public_session(row) for row in self.runtime.list_sessions()],
                "model": self.models.status() if self.models else {"status": "MODEL_UNAVAILABLE"},
            }

    @staticmethod
    def _public_session(row: dict[str, Any]) -> dict[str, object]:
        fields = {
            "session_id",
            "source_kind",
            "participant_pseudonym",
            "state",
            "revision",
            "event_count",
            "locked",
            "quality_state",
            "focus_state",
            "failure_reason",
            "capture_profile",
            "inference_state",
        }
        return {key: value for key, value in row.items() if key in fields}

    def detail(self, session_id: str) -> dict[str, object]:
        with self._lock:
            row = self._public_session(self.runtime.get_session(session_id))
            exam_id = self._exam_id(session_id)
            row["exam_session_id"] = exam_id
            reviews = self.runtime.list_reviews(session_id)
            latest_reviews = {str(review["event_id"]): review for review in reviews}
            event_rows = []
            for event in self.runtime.events_after(session_id):
                if event.get("event_type") != "OBSERVABLE_EVENT":
                    continue
                reviewed = latest_reviews.get(str(event["event_id"]), {})
                event_rows.append(
                    {
                        **event,
                        **{
                            k: v
                            for k, v in reviewed.items()
                            if k in {"label", "review_status", "start_ms", "end_ms", "reason"}
                        },
                        "revision": row.get("revision", 0),
                    }
                )
            row["events"] = event_rows
            live = getattr(self.runtime, "live_observation", None)
            row["live"] = live(session_id) if callable(live) else {}
            row["report"] = {
                "schema_version": 1,
                "source_kind": row["source_kind"],
                "event_count": len(event_rows),
                "reviewed_count": len(latest_reviews),
                "counts_by_label": {
                    label: sum(
                        event.get("label", event.get("research_label")) == label
                        for event in event_rows
                    )
                    for label in {
                        str(event.get("label", event.get("research_label"))) for event in event_rows
                    }
                },
                "research_performance": "UNVERIFIED",
                "interpretation": "HUMAN_REVIEW_ONLY",
            }
            row["review_history"] = reviews
            exam = self.backend.snapshot(exam_id)
            row["exam_state"] = None if exam is None else exam.state
            if row.get("state") not in {"SEALED", "FAILED", "WITHDRAWN"}:
                pairing = next(
                    (k for k, v in self.backend.pairing_codes.items() if v == exam_id), None
                )
                if pairing:
                    row["pairing_code"] = pairing
            # Paths and file inventories are operational, not browser capabilities.
            return row

    def create(self, source_kind: str, key: str) -> dict[str, object]:
        def operation() -> dict[str, object]:
            row = self.runtime.create_session(source_kind=source_kind)
            record, _ = self.backend.create_session()
            self.db.execute("INSERT INTO links VALUES(?,?)", (row["session_id"], record.session_id))
            self.db.commit()
            return self.detail(str(row["session_id"]))

        result = self._once(key, {"operation": "create", "source_kind": source_kind}, operation)
        return self.detail(str(result["session_id"]))

    def action(self, session_id: str, action: str, key: str) -> dict[str, object]:
        def operation() -> dict[str, object]:
            exam_id = self._exam_id(session_id)
            snapshot = self.backend.snapshot(exam_id)
            if action == "preflight":
                self.runtime.preflight(session_id)
            elif action == "start":
                if snapshot is None or snapshot.state != "PREFLIGHT_READY":
                    raise ValueError("EXAM_NOT_READY")
                row = self.runtime.get_session(session_id)
                if row["source_kind"] == "REAL":
                    if not self.authority_reference:
                        raise ValueError("AUTHORITY_NOT_ISSUED")
                    self.runtime.start_real_collection(session_id, self.authority_reference)
                else:
                    self.runtime.start_synthetic_demo(session_id)
                try:
                    self.backend.apply_session_action(exam_id, "start")
                except Exception:
                    self.runtime.stop(session_id)
                    raise
            elif action in {"stop", "seal"}:
                if self.runtime.get_session(session_id)["state"] == "RECORDING":
                    self.runtime.stop(session_id)
                if snapshot is not None and snapshot.state == "RECORDING":
                    self.backend.apply_session_action(exam_id, "stop")
                if action == "seal":
                    self.runtime.seal(session_id)
            elif action == "lock":
                self.runtime.lock(session_id)
            elif action == "withdraw-test":
                self.runtime.withdraw_test_artifacts(session_id)
            elif action == "withdraw":
                if not self.authority_reference:
                    raise ValueError("WITHDRAWAL_AUTHORITY_REQUIRED")
                self.runtime.withdraw(session_id, self.authority_reference)
                if snapshot is not None and snapshot.state == "RECORDING":
                    self.backend.apply_session_action(exam_id, "stop")
            else:
                raise ValueError("UNKNOWN_ACTION")
            return self.detail(session_id)

        return self._once(key, {"operation": action, "session_id": session_id}, operation)

    def decide(self, session_id: str, payload: dict[str, object], key: str) -> dict[str, object]:
        def operation() -> dict[str, object]:
            self.runtime.review(
                session_id,
                str(payload["event_id"]),
                str(payload["label"]),
                str(payload["review_status"]),
                cast(int, payload["start_ms"]),
                cast(int, payload["end_ms"]),
                str(payload["reason"]),
                cast(int, payload["expected_revision"]),
            )
            return self.detail(session_id)

        return self._once(
            key, {"operation": "decision", "session_id": session_id, **payload}, operation
        )

    def focus(self, exam_session_id: str, focused: bool) -> None:
        with self._lock:
            row = self.db.execute(
                "SELECT runtime_id FROM links WHERE exam_id=?", (exam_session_id,)
            ).fetchone()
            if row is not None and self.runtime.get_session(str(row[0]))["state"] == "RECORDING":
                self.runtime.record_focus_context(
                    str(row[0]), "EXAM_FOCUSED" if focused else "EXAM_NOT_FOCUSED"
                )

    def export(self, session_id: str) -> bytes:
        with self._lock:
            self._exam_id(session_id)
            return cast(bytes, self.runtime.export_allowlisted(session_id).payload)

    def preview(self, session_id: str) -> Path:
        with self._lock:
            self._exam_id(session_id)
            return self.runtime.preview_path(session_id)

    def open_preview(self, session_id: str) -> Any:
        with self._lock:
            self._exam_id(session_id)
            opener = getattr(self.runtime, "open_preview", None)
            if not callable(opener):
                raise ValueError("PREVIEW_READER_UNAVAILABLE")
            return opener(session_id)

    def import_model(self, payload: bytes, key: str) -> dict[str, object]:
        if self.models is None:
            raise ValueError("MODEL_RUNTIME_UNAVAILABLE")
        if any(row.get("state") == "RECORDING" for row in self.runtime.list_sessions()):
            raise ValueError("ACTIVE_CAPTURE_MODEL_CHANGE_DENIED")
        models = self.models
        return self._once(
            key,
            {"operation": "model_import", "sha256": hashlib.sha256(payload).hexdigest()},
            lambda: models.import_bytes(payload),
        )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self.runtime.close()
            finally:
                self.db.close()
                self._closed = True
