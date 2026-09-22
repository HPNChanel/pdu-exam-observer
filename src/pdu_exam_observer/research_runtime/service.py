"""Persisted runtime collection primitives.

This module deliberately has no HTTP dependency.  The launcher authenticates a
reviewer and owns the M1 exam lifecycle; this service owns the high-rate local
artifacts and refuses to manufacture real-collection authority from request
data.  A synthetic fixture is a separate source kind and is never promoted to
``REAL`` by this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, BinaryIO, cast

from pdu_exam_observer.showcase.export_contract import build_research_export
from pdu_exam_observer.showcase.model_runtime import aggregate_context_rows
from pdu_exam_observer.showcase.preprocessing import resample_pose_window

from .artifact_io import open_regular_read
from .camera_worker import CaptureError, NativeCapture
from .root_lease import RootLease, has_reparse_component
from .rules import RuleEvent, RulePolicy, TemporalRuleEngine, orientation_proxy_degrees

try:  # numpy is a packaged dependency; retaining this guard keeps import errors explicit.
    import numpy as np
except ImportError:  # pragma: no cover - package gate covers it
    np = None  # type: ignore[assignment]


SCHEMA_VERSION = 1
CAPTURE_PROFILE = "capture.v1.1280x720@15fps.no-audio"
ALLOWED_SOURCE_KINDS = frozenset({"REAL", "AI_RENDERED", "AUGMENTED"})
ALLOWED_FOCUS = frozenset({"EXAM_FOCUSED", "EXAM_NOT_FOCUSED", "FOCUS_UNKNOWN"})
ALLOWED_LABELS = frozenset(
    {
        "NORMAL",
        "BENIGN_CONFOUNDER",
        "PROLONGED_HEAD_DOWN",
        "PROLONGED_SIDE_LOOK",
        "NO_PERSON",
        "MULTIPLE_PEOPLE",
        "UNCERTAIN",
    }
)
ALLOWED_REVIEW_STATUS = frozenset({"CONFIRMED", "REJECTED", "UNCERTAIN"})
EXPORT_FIELDS = (
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
)


class RuntimeErrorBase(RuntimeError):
    pass


class InvalidTransition(RuntimeErrorBase):
    pass


class AuthorityDenied(RuntimeErrorBase):
    pass


class RevisionConflict(RuntimeErrorBase):
    pass


@dataclass(frozen=True)
class ExportBundle:
    payload: bytes
    manifest: dict[str, object]
    export_id: str


@dataclass
class _ArtifactStream:
    """Bounded local writers; frames are never retained in a Python list."""

    pose_partial: Path
    pose_handle: Any
    video_partial: Path
    video_writer: Any
    origin_ns: int = 0
    written_frames: int = 0
    last_frame: Any = None


AuthorityResolver = Callable[[str], Mapping[str, object] | None]
ModelProvider = Callable[[Mapping[str, Any]], Mapping[str, object] | None]
DiagnosticProvider = Callable[[], Mapping[str, object]]


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


class NativeAuthorityResolver:
    """Reads one trusted native authority record, never a browser request body.

    The host integration creates this local file through an operator-only native
    workflow.  This class validates binding and completeness; it does not claim
    that the referenced institutional approval is authentic.
    """

    filename = "collection-authority.v1.json"

    def __init__(self, native_root: Path) -> None:
        self._root = native_root.resolve()
        self._path = self._root / ".pdu_exam_observer" / self.filename

    def __call__(self, authority_reference: str) -> Mapping[str, object] | None:
        if not authority_reference or "/" in authority_reference or "\\" in authority_reference:
            return None
        if has_reparse_component(self._path):
            return None
        try:
            with open_regular_read(self._path) as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            return None
        if not isinstance(record, dict) or record.get("authority_reference") != authority_reference:
            return None
        return record


class ResearchRuntimeService:
    """Owns one local collection runtime database and per-session artifacts."""

    def __init__(
        self,
        native_root: Path,
        *,
        authority_resolver: AuthorityResolver | None = None,
        model_provider: ModelProvider | None = None,
        diagnostic_provider: DiagnosticProvider | None = None,
        camera_factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not native_root.is_absolute():
            raise ValueError("native_root must be absolute")
        if has_reparse_component(native_root):
            raise ValueError("UNSAFE_STORAGE_ROOT")
        self.root = native_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts_root = self.root / "runtime-artifacts"
        database = self.root / "research-runtime.v1.sqlite3"
        if any(
            has_reparse_component(path)
            for path in (
                self.artifacts_root,
                database,
                Path(str(database) + "-wal"),
                Path(str(database) + "-shm"),
            )
        ):
            raise ValueError("UNSAFE_STORAGE_ROOT")
        self.artifacts_root.mkdir(exist_ok=True)
        self._root_lease = RootLease(self.root)
        self._clock = clock
        self._authority_resolver = authority_resolver or NativeAuthorityResolver(self.root)
        self._model_provider = model_provider
        self._diagnostic_provider = diagnostic_provider or self._native_preflight
        self._camera_factory = camera_factory
        self._connection = sqlite3.connect(
            self.root / "research-runtime.v1.sqlite3", check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.RLock()
        self._streams: dict[str, _ArtifactStream] = {}
        self._capture_threads: dict[str, threading.Thread] = {}
        self._capture_stops: dict[str, threading.Event] = {}
        self._rule_engines: dict[str, TemporalRuleEngine] = {}
        self._model_engines: dict[str, TemporalRuleEngine] = {}
        self._logical_events: dict[tuple[str, str], str] = {}
        self._pose_buffers: dict[str, deque[dict[str, Any]]] = {}
        self._capture_origins: dict[str, int] = {}
        self._focus_times: dict[str, float] = {}
        self._last_model_times: dict[str, int] = {}
        self._pose_landmarker: Any | None = None
        try:
            self._initialize()
            self.recover()
        except Exception:
            self.close()
            raise

    @staticmethod
    def root_digest(root: Path) -> str:
        return _sha256(str(root.resolve()).encode("utf-8"))

    def close(self) -> None:
        with self._lock:
            stops = tuple(self._capture_stops.values())
            threads = tuple(self._capture_threads.values())
        for stop in stops:
            stop.set()
        for thread in threads:
            thread.join(timeout=10.0)
        with self._lock:
            if any(thread.is_alive() for thread in threads):
                raise RuntimeErrorBase("CAMERA_STOP_TIMEOUT")
            for session_id in tuple(self._streams):
                self._close_stream_locked(session_id, finalize=False)
            self._capture_threads.clear()
            self._capture_stops.clear()
            landmarker, self._pose_landmarker = self._pose_landmarker, None
            if landmarker is not None:
                close = getattr(landmarker, "close", None)
                if callable(close):
                    close()
            if self._connection is not None:
                self._connection.close()
                self._connection = None  # type: ignore[assignment]
            self._root_lease.close()

    def _initialize(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, SCHEMA_VERSION}:
            self._connection.close()
            self._root_lease.close()
            raise ValueError("RUNTIME_SCHEMA_INCOMPATIBLE")
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_sessions(
                  session_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL,
                  participant_pseudonym TEXT NOT NULL, state TEXT NOT NULL,
                  revision INTEGER NOT NULL, created_at REAL NOT NULL,
                  started_at REAL, stopped_at REAL, sealed_at REAL,
                  failure_code TEXT, locked INTEGER NOT NULL DEFAULT 0,
                  frame_seq INTEGER NOT NULL DEFAULT 0, focus_state TEXT NOT NULL,
                  quality_state TEXT NOT NULL, authority_reference TEXT,
                  artifact_directory TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runtime_events(
                  event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                  event_seq INTEGER NOT NULL, event_type TEXT NOT NULL,
                  payload_json TEXT NOT NULL, created_at REAL NOT NULL,
                  UNIQUE(session_id,event_seq),
                  FOREIGN KEY(session_id) REFERENCES runtime_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS runtime_reviews(
                  review_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, event_id TEXT NOT NULL,
                  label TEXT NOT NULL, review_status TEXT NOT NULL, start_ms INTEGER NOT NULL,
                  end_ms INTEGER NOT NULL, reason TEXT NOT NULL, revision INTEGER NOT NULL,
                  created_at REAL NOT NULL,
                  FOREIGN KEY(session_id) REFERENCES runtime_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS runtime_exports(
                  export_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                  manifest_sha256 TEXT NOT NULL, created_at REAL NOT NULL,
                  FOREIGN KEY(session_id) REFERENCES runtime_sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS runtime_artifacts(
                  session_id TEXT NOT NULL, name TEXT NOT NULL, sha256 TEXT NOT NULL,
                  size_bytes INTEGER NOT NULL, PRIMARY KEY(session_id,name),
                  FOREIGN KEY(session_id) REFERENCES runtime_sessions(session_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS runtime_single_recording
                  ON runtime_sessions((1)) WHERE state='RECORDING';
                PRAGMA user_version=1;
                """
            )

    def create_session(
        self, source_kind: str = "AI_RENDERED", participant_pseudonym: str | None = None
    ) -> dict[str, object]:
        if source_kind not in ALLOWED_SOURCE_KINDS:
            raise ValueError("unsupported source_kind")
        session_id = str(uuid.uuid4())
        pseudonym = participant_pseudonym or f"pending-{uuid.uuid4().hex[:12]}"
        artifact_directory = self.artifacts_root / session_id
        artifact_directory.mkdir()
        now = self._clock()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO runtime_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    source_kind,
                    pseudonym,
                    "DRAFT",
                    0,
                    now,
                    None,
                    None,
                    None,
                    None,
                    0,
                    0,
                    "FOCUS_UNKNOWN",
                    "UNKNOWN",
                    None,
                    str(artifact_directory),
                ),
            )
            self._append_event_locked(session_id, "SESSION_CREATED", {"source_kind": source_kind})
        return self.get_session(session_id)

    def list_sessions(self) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT session_id FROM runtime_sessions ORDER BY created_at DESC"
            ).fetchall()
        return [self.get_session(str(row["session_id"])) for row in rows]

    def get_session(self, session_id: str) -> dict[str, object]:
        with self._lock:
            row = self._session_row(session_id)
            count = self._connection.execute(
                "SELECT COUNT(*) FROM runtime_events WHERE session_id=? "
                "AND event_type='OBSERVABLE_EVENT'",
                (session_id,),
            ).fetchone()[0]
            result = self._session_dict(row, event_count=int(count))
            inference = self._connection.execute(
                "SELECT payload_json FROM runtime_events WHERE session_id=? "
                "AND event_type IN ('MODEL_STATE','TECHNICAL_STATE') "
                "ORDER BY event_seq DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            result["inference_state"] = (
                json.loads(inference[0]).get("state", "TECHNICAL_INSUFFICIENT")
                if inference
                else "TECHNICAL_INSUFFICIENT"
            )
            return result

    def preflight(
        self, session_id: str, diagnostic: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        """Records a completed technical preflight; callers may provide native diagnostic facts."""
        with self._lock, self._connection:
            session = self._require_state(session_id, {"DRAFT"})
            # A real browser never supplies these facts.  Test injection is constructor-only.
            if session["source_kind"] == "REAL":
                diagnostic = self._diagnostic_provider()
            else:
                diagnostic = diagnostic or {"disk": "READY", "source": "synthetic"}
            required: tuple[str, ...] = ("disk",)
            if session["source_kind"] == "REAL":
                required = ("camera", "display", "disk")
            status = (
                "READY"
                if all(diagnostic.get(field) == "READY" for field in required)
                else "TECHNICAL_INSUFFICIENT"
            )
            state = "PREFLIGHT_READY" if status == "READY" else "FAILED"
            self._update_session_locked(
                session_id,
                state=state,
                failure_code=None if state != "FAILED" else "PREFLIGHT_FAILED",
            )
            self._append_event_locked(
                session_id,
                "TECHNICAL_PREFLIGHT",
                {"status": status, "diagnostic": dict(diagnostic)},
            )
        return self.get_session(session_id)

    def start_synthetic_demo(
        self, session_id: str, fixture_name: str = "nominal"
    ) -> dict[str, object]:
        with self._lock, self._connection:
            row = self._require_state(session_id, {"PREFLIGHT_READY"})
            if row["source_kind"] == "REAL":
                raise InvalidTransition("REAL sessions must use start_real_collection")
            self._assert_no_active_collection_locked()
            self._update_session_locked(session_id, state="RECORDING", started_at=self._clock())
            self._append_event_locked(
                session_id,
                "SYNTHETIC_FIXTURE_STARTED",
                {"fixture_name": fixture_name, "synthetic": True},
            )
            # A deterministic, explicitly synthetic event sequence creates reviewable UI data.
            self._append_event_locked(
                session_id, "TECHNICAL_STATE", {"state": "READY", "synthetic": True}
            )
            self._append_event_locked(
                session_id,
                "OBSERVABLE_EVENT",
                self._event_payload(
                    row, "BENIGN_CONFOUNDER", 0, 6000, ["synthetic_fixture"], "NOT_APPLICABLE", None
                ),
            )
            try:
                self._write_synthetic_fixture_locked(session_id)
            except (OSError, RuntimeErrorBase):
                self._fail_locked(session_id, "SYNTHETIC_FIXTURE_FAILED")
        return self.get_session(session_id)

    def start_real_collection(self, session_id: str, authority_reference: str) -> dict[str, object]:
        with self._lock, self._connection:
            row = self._require_state(session_id, {"PREFLIGHT_READY"})
            if row["source_kind"] != "REAL":
                raise InvalidTransition("only REAL sessions can start real collection")
            authority = self._validate_authority(authority_reference)
            if authority.get("session_pseudonym") != session_id:
                raise AuthorityDenied("AUTHORITY_SESSION_MISMATCH")
            self._assert_no_active_collection_locked()
            self._update_session_locked(
                session_id,
                state="RECORDING",
                started_at=self._clock(),
                authority_reference=authority_reference,
                participant_pseudonym=authority["participant_pseudonym"],
            )
            self._append_event_locked(
                session_id, "COLLECTION_STARTED", {"capture_profile": CAPTURE_PROFILE}
            )
            stop = threading.Event()
            worker = threading.Thread(
                target=self._camera_worker,
                args=(session_id, stop),
                name=f"pdu-capture-{session_id[:8]}",
                daemon=True,
            )
            self._capture_stops[session_id] = stop
            self._capture_threads[session_id] = worker
            worker.start()
        return self.get_session(session_id)

    def ingest_frame(
        self, session_id: str, frame: Any, captured_at: float | None = None
    ) -> dict[str, object]:
        """Stores a frame locally and emits a technical-insufficient failure on bad input."""
        captured_at = time.perf_counter() if captured_at is None else captured_at
        with self._lock, self._connection:
            row = self._require_state(session_id, {"RECORDING"})
            if row["source_kind"] == "REAL":
                try:
                    self._validate_export_authority(row)
                except AuthorityDenied:
                    self._fail_locked(session_id, "COLLECTION_AUTHORITY_INVALID")
                    return self.get_session(session_id)
            if not math.isfinite(captured_at):
                self._fail_locked(session_id, "CAPTURE_TIMESTAMP_INVALID")
                return self.get_session(session_id)
            if (
                np is None
                or not isinstance(frame, np.ndarray)
                or frame.ndim != 3
                or frame.shape[2] not in {3, 4}
            ):
                self._fail_locked(session_id, "FRAME_INVALID")
                return self.get_session(session_id)
            if frame.shape[0] != 720 or frame.shape[1] != 1280:
                self._fail_locked(session_id, "CAPTURE_PROFILE_MISMATCH")
                return self.get_session(session_id)
            frame_seq = int(row["frame_seq"]) + 1
            captured_ns = int(captured_at * 1_000_000_000)
            history = self._pose_buffers.setdefault(session_id, deque(maxlen=180))
            if history and captured_ns <= history[-1]["captured_ns"]:
                self._fail_locked(session_id, "CAPTURE_TIMESTAMP_INVALID")
                return self.get_session(session_id)
            quality, landmarks, pose_count, pose_error = self._analyze_frame(frame)
            if pose_error:
                self._fail_locked(session_id, pose_error)
                return self.get_session(session_id)
            focus_age = max(0.0, (self._clock() - self._focus_times.get(session_id, 0)) * 1000)
            focus_state = row["focus_state"] if focus_age <= 6000 else "FOCUS_UNKNOWN"
            gap = (
                0.0
                if not history
                else max(0.0, (captured_ns - history[-1]["captured_ns"]) / 66_666_667 - 1)
            )
            quality.update(
                visibility_mean=float(np.mean([p["visibility"] for p in landmarks[0]]))
                if pose_count == 1
                else 0.0,
                frame_gap_ratio=min(gap, 1.0),
            )
            observation = {
                "frame_seq": frame_seq,
                "captured_ns": captured_ns,
                "pose_count": pose_count,
                "landmarks": landmarks,
                "quality": quality,
                "focus": focus_state,
                "focus_age_ms": min(focus_age, 6001.0),
            }
            try:
                self._write_frame_locked(
                    session_id,
                    frame,
                    observation,
                )
            except (OSError, RuntimeErrorBase):
                self._fail_locked(session_id, "ARTIFACT_WRITE_FAILED")
                return self.get_session(session_id)
            self._update_session_locked(
                session_id, frame_seq=frame_seq, quality_state=quality["state"]
            )
            history.append(observation)
            payload = dict(observation)
            self._append_event_locked(session_id, "POSE_OBSERVATION", payload)
            self._emit_model_or_rule_locked(session_id, row, payload, landmarks)
        return self.get_session(session_id)

    def record_focus_context(self, session_id: str, focus_enum: str) -> dict[str, object]:
        if focus_enum not in ALLOWED_FOCUS:
            raise ValueError("invalid focus state")
        with self._lock, self._connection:
            self._require_state(session_id, {"PREFLIGHT_READY", "RECORDING"})
            self._focus_times[session_id] = self._clock()
            self._update_session_locked(session_id, focus_state=focus_enum)
            self._append_event_locked(session_id, "FOCUS_CONTEXT", {"state": focus_enum})
        return self.get_session(session_id)

    def stop(self, session_id: str) -> dict[str, object]:
        with self._lock:
            self._require_state(session_id, {"RECORDING"})
            stop = self._capture_stops.get(session_id)
            worker = self._capture_threads.get(session_id)
            if stop is not None:
                stop.set()
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=10.0)
        with self._lock, self._connection:
            self._require_state(session_id, {"RECORDING"})
            if worker is not None and worker.is_alive():
                self._fail_locked(session_id, "CAMERA_STOP_TIMEOUT")
                return self.get_session(session_id)
            self._capture_stops.pop(session_id, None)
            self._capture_threads.pop(session_id, None)
            try:
                self._close_stream_locked(session_id, finalize=True)
            except (OSError, RuntimeErrorBase, subprocess.SubprocessError):
                self._fail_locked(session_id, "ARTIFACT_WRITE_FAILED")
                return self.get_session(session_id)
            row = self._session_row(session_id)
            history = self._pose_buffers.get(session_id)
            for registry, signal in (
                (self._rule_engines, "INDEPENDENT_TEMPORAL_RULES"),
                (self._model_engines, "ST_GCN_TEMPORAL_MODEL"),
            ):
                engine = registry.pop(session_id, None)
                if engine is not None and history:
                    endpoint = (
                        history[-1]["captured_ns"] - self._capture_origins[session_id]
                    ) // 1_000_000 + 67
                    self._persist_rule_events_locked(
                        session_id, row, engine.close(endpoint), signal=signal, policy=engine.policy
                    )
            self._update_session_locked(session_id, state="STOPPED", stopped_at=self._clock())
            self._append_event_locked(session_id, "COLLECTION_STOPPED", {})
        return self.get_session(session_id)

    def _camera_worker(self, session_id: str, stop: threading.Event) -> None:
        """The only runtime camera owner; device index is fixed by native code."""
        capture = None
        try:
            if self._camera_factory is None:
                with NativeCapture() as native:
                    while not stop.is_set():
                        frame, captured_ns, _dropped = native.read()
                        if stop.is_set():
                            return
                        self.ingest_frame(session_id, frame, captured_ns / 1_000_000_000)
                        if self.get_session(session_id)["state"] != "RECORDING":
                            return
                return
            capture = self._camera_factory()
            if not capture.isOpened():
                raise RuntimeErrorBase("CAMERA_OPEN_FAILED")
            capture.set(3, 1280)
            capture.set(4, 720)
            capture.set(5, 15)
            while not stop.is_set():
                okay, frame = capture.read()
                if not okay or frame is None:
                    raise RuntimeErrorBase("CAMERA_READ_FAILED")
                self.ingest_frame(session_id, frame)
                if self.get_session(session_id)["state"] != "RECORDING":
                    return
                stop.wait(1 / 15)
        except (RuntimeErrorBase, CaptureError, OSError, ValueError, sqlite3.Error) as exc:
            with self._lock, self._connection:
                if self._session_row(session_id)["state"] == "RECORDING":
                    code = str(exc)
                    safe = (
                        code
                        and len(code) < 80
                        and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_" for c in code)
                    )
                    self._fail_locked(session_id, code if safe else "CAPTURE_PIPELINE_FAILED")
        finally:
            if capture is not None:
                capture.release()

    def seal(self, session_id: str) -> dict[str, object]:
        with self._lock, self._connection:
            row = self._require_state(session_id, {"STOPPED"})
            self._verify_artifacts_locked(row)
            self._update_session_locked(session_id, state="SEALED", sealed_at=self._clock())
            self._append_event_locked(session_id, "SESSION_SEALED", {})
        return self.get_session(session_id)

    def events_after(self, session_id: str, seq: int = 0) -> list[dict[str, object]]:
        if seq < 0:
            raise ValueError("seq must be non-negative")
        with self._lock:
            self._session_row(session_id)
            rows = self._connection.execute(
                "SELECT * FROM runtime_events WHERE session_id=? "
                "AND event_seq>? ORDER BY event_seq",
                (session_id, seq),
            ).fetchall()
        return [self._event_dict(row) for row in rows]

    def live_observation(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._session_row(session_id)
            if row["state"] != "RECORDING":
                return {}
            history = self._pose_buffers.get(session_id)
            if not history:
                return {"state": "TECHNICAL_INSUFFICIENT"}
            latest = history[-1]
            return {
                "frame_seq": latest["frame_seq"],
                "landmarks": latest["landmarks"],
                "pose_count": latest["pose_count"],
                "quality": latest["quality"],
                "focus": latest["focus"],
                "source_kind": row["source_kind"],
            }

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
    ) -> dict[str, object]:
        if label not in ALLOWED_LABELS or review_status not in ALLOWED_REVIEW_STATUS:
            raise ValueError("invalid review label or status")
        if start_ms < 0 or end_ms <= start_ms or not reason.strip():
            raise ValueError("invalid review boundary or reason")
        with self._lock, self._connection:
            row = self._require_state(session_id, {"SEALED"})
            if row["locked"]:
                raise InvalidTransition("session is locked")
            if int(row["revision"]) != expected_revision:
                raise RevisionConflict("session revision changed")
            duration = self._duration_ms_locked(row)
            if end_ms > duration:
                raise ValueError("REVIEW_OUTSIDE_TIMELINE")
            if not event_id:
                created = self._append_event_locked(
                    session_id,
                    "OBSERVABLE_EVENT",
                    self._event_payload(
                        row,
                        "UNCERTAIN",
                        start_ms,
                        end_ms,
                        ["MANUAL_ANNOTATION"],
                        "NOT_APPLICABLE",
                        None,
                    ),
                )
                event_id = str(created["event_id"])
            event = self._connection.execute(
                "SELECT 1 FROM runtime_events WHERE session_id=? AND event_id=? "
                "AND event_type='OBSERVABLE_EVENT'",
                (session_id, event_id),
            ).fetchone()
            if event is None:
                raise ValueError("event does not belong to session")
            revision = expected_revision + 1
            review_id = str(uuid.uuid4())
            self._connection.execute(
                "INSERT INTO runtime_reviews VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    session_id,
                    event_id,
                    label,
                    review_status,
                    start_ms,
                    end_ms,
                    reason.strip(),
                    revision,
                    self._clock(),
                ),
            )
            self._update_session_locked(session_id, revision=revision)
            self._append_event_locked(
                session_id,
                "REVIEW_DECISION",
                {
                    "event_id": event_id,
                    "label": label,
                    "review_status": review_status,
                    "review_id": review_id,
                },
            )
        return {
            "review_id": review_id,
            "revision": revision,
            "event_id": event_id,
            "label": label,
            "review_status": review_status,
        }

    def list_reviews(self, session_id: str) -> list[dict[str, object]]:
        with self._lock:
            self._session_row(session_id)
            rows = self._connection.execute(
                "SELECT * FROM runtime_reviews WHERE session_id=? ORDER BY revision",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def lock(self, session_id: str) -> dict[str, object]:
        with self._lock, self._connection:
            row = self._require_state(session_id, {"SEALED"})
            if row["locked"]:
                return self.get_session(session_id)
            unreviewed = self._connection.execute(
                "SELECT e.event_id FROM runtime_events e "
                "LEFT JOIN runtime_reviews r ON r.event_id=e.event_id "
                "WHERE e.session_id=? AND e.event_type='OBSERVABLE_EVENT' "
                "GROUP BY e.event_id HAVING COUNT(r.review_id)=0 LIMIT 1",
                (session_id,),
            ).fetchone()
            if unreviewed is not None:
                raise InvalidTransition("UNREVIEWED_EVENT")
            latest = {str(review["event_id"]): review for review in self.list_reviews(session_id)}
            accepted = sorted(
                (review for review in latest.values() if review["review_status"] != "REJECTED"),
                key=lambda review: int(cast(int, review["start_ms"])),
            )
            for i, current in enumerate(accepted):
                for other in accepted[i + 1 :]:
                    if int(cast(int, other["start_ms"])) >= int(cast(int, current["end_ms"])):
                        break
                    if current["label"] != other["label"]:
                        raise InvalidTransition("CONFLICTING_REVIEW_INTERVALS")
            self._update_session_locked(session_id, locked=1)
            self._append_event_locked(session_id, "SESSION_LOCKED", {})
        return self.get_session(session_id)

    def preview_path(self, session_id: str) -> Path:
        with self._lock:
            row = self._require_state(session_id, {"SEALED"})
            if row["source_kind"] == "REAL":
                self._validate_export_authority(row)
            self._verify_artifacts_locked(row)
            target = self._owned_artifact_directory(row) / "raw_video.mp4"
            if has_reparse_component(target):
                raise AuthorityDenied("ARTIFACT_SCOPE_INVALID")
            if not target.is_file():
                raise FileNotFoundError("no local preview is available")
            return target

    def export_allowlisted(self, session_id: str) -> ExportBundle:
        with self._lock:
            row = self._require_state(session_id, {"SEALED"})
            self._verify_artifacts_locked(row)
            if not row["locked"]:
                raise InvalidTransition("seal and lock before export")
            if row["source_kind"] == "REAL" and not row["participant_pseudonym"]:
                raise AuthorityDenied("REAL export requires pseudonymous binding")
            if row["source_kind"] == "REAL":
                self._validate_export_authority(row)
            reviews = self.list_reviews(session_id)
            event_rows = self.events_after(session_id)
            records = self._export_records(row, reviews, event_rows)
        export_id = str(uuid.uuid4())
        payload, manifest = build_research_export(records, export_id=export_id)
        manifest_sha256 = str(manifest["manifest_sha256"])
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO runtime_exports VALUES(?,?,?,?)",
                (export_id, session_id, manifest_sha256, self._clock()),
            )
        return ExportBundle(payload, manifest, export_id)

    def open_preview(self, session_id: str) -> BinaryIO:
        with self._lock:
            path = self.preview_path(session_id)
            handle = open_regular_read(path)
            expected = self._connection.execute(
                "SELECT sha256 FROM runtime_artifacts WHERE session_id=? AND name='raw_video.mp4'",
                (session_id,),
            ).fetchone()[0]
            digest = hashlib.sha256()
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
            if digest.hexdigest() != expected:
                handle.close()
                raise InvalidTransition("ARTIFACT_INTEGRITY_FAILED")
            handle.seek(0)
            return handle

    def withdraw(self, session_id: str, authority_reference: str) -> dict[str, object]:
        """Apply a native withdrawal decision to this runtime's owned artifacts only."""
        with self._lock:
            row = self._session_row(session_id)
            if row["source_kind"] != "REAL":
                raise AuthorityDenied("synthetic sessions use withdraw_test_artifacts")
            if row["state"] in {"WITHDRAWN", "DRAFT"}:
                raise InvalidTransition("WITHDRAWAL_NOT_AVAILABLE")
            authority = self._validate_authority(authority_reference, withdrawal=True)
            if (
                authority.get("session_pseudonym") != session_id
                or authority.get("participant_pseudonym") != row["participant_pseudonym"]
            ):
                raise AuthorityDenied("AUTHORITY_SESSION_MISMATCH")
            decision = authority.get("withdrawal_decision")
            if decision not in {"DELETE_OWNED_RUNTIME_ARTIFACTS", "QUARANTINE_RUNTIME_ARTIFACTS"}:
                raise AuthorityDenied("WITHDRAWAL_DECISION_REQUIRED")
            if not _is_digest(authority.get("withdrawal_authority_sha256")):
                raise AuthorityDenied("WITHDRAWAL_AUTHORITY_REQUIRED")
            stop = self._capture_stops.get(session_id)
            worker = self._capture_threads.get(session_id)
            if stop is not None:
                stop.set()
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=5.0)
        with self._lock, self._connection:
            if worker is not None and worker.is_alive():
                self._fail_locked(session_id, "CAMERA_STOP_TIMEOUT")
                return self.get_session(session_id)
            self._capture_stops.pop(session_id, None)
            self._capture_threads.pop(session_id, None)
            directory = self._owned_artifact_directory(row)
            self._close_stream_locked(session_id, finalize=False)
            inventory = self._withdrawal_artifact_inventory_locked(self._session_row(session_id))
            if decision == "DELETE_OWNED_RUNTIME_ARTIFACTS" and directory.exists():
                for item in inventory:
                    (directory / str(item["name"])).unlink()
                directory.rmdir()
            elif decision == "QUARANTINE_RUNTIME_ARTIFACTS" and directory.exists():
                directory.replace(directory.with_name(directory.name + ".withdrawn.quarantine"))
            exported = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM runtime_exports WHERE session_id=?", (session_id,)
                ).fetchone()[0]
            )
            receipt: dict[str, object] = {
                "authority_reference": authority_reference,
                "withdrawal_authority_sha256": authority["withdrawal_authority_sha256"],
                "decision": decision,
                "external_export_follow_up_required": exported > 0,
                "export_count": exported,
                "artifacts": inventory,
            }
            receipt["receipt_sha256"] = _sha256(_canonical(receipt))
            self._update_session_locked(session_id, state="WITHDRAWN")
            self._append_event_locked(session_id, "WITHDRAWAL_RECORDED", receipt)
        return self.get_session(session_id)

    def withdraw_test_artifacts(self, session_id: str) -> dict[str, object]:
        """Deletion rehearsal only: real participant artifacts remain outside this API."""
        with self._lock, self._connection:
            row = self._session_row(session_id)
            if row["source_kind"] == "REAL":
                raise AuthorityDenied("real participant withdrawal uses governed reconciliation")
            if row["state"] not in {"SEALED", "FAILED"}:
                raise InvalidTransition("only terminal test artifacts can be withdrawn")
            artifact_directory = self._owned_artifact_directory(row)
            inventory = self._withdrawal_artifact_inventory_locked(row)
            if artifact_directory.exists():
                for item in inventory:
                    (artifact_directory / str(item["name"])).unlink()
                artifact_directory.rmdir()
            self._update_session_locked(session_id, state="WITHDRAWN")
            self._append_event_locked(session_id, "TEST_ARTIFACTS_WITHDRAWN", {})
        result = self.get_session(session_id)
        result["artifact_directory"] = str(artifact_directory)
        return result

    def recover(self) -> list[dict[str, object]]:
        """Fail closed after interruption; a partial recording is never sealed."""
        recovered: list[dict[str, object]] = []
        with self._lock, self._connection:
            rows = self._connection.execute(
                "SELECT * FROM runtime_sessions WHERE state='RECORDING'"
            ).fetchall()
            for row in rows:
                directory = self._owned_artifact_directory(row)
                for partial in directory.glob("*.partial*"):
                    if has_reparse_component(partial):
                        raise AuthorityDenied("ARTIFACT_SCOPE_INVALID")
                    partial.replace(partial.with_name(partial.name + ".quarantine"))
                self._update_session_locked(
                    str(row["session_id"]), state="FAILED", failure_code="RECOVERY_REQUIRED"
                )
                self._append_event_locked(
                    str(row["session_id"]), "TECHNICAL_FAILURE", {"code": "RECOVERY_REQUIRED"}
                )
                recovered.append(self.get_session(str(row["session_id"])))
        return recovered

    def diagnose_current_camera(self) -> dict[str, object]:
        """Bounded transient diagnostic; no media or participant record is written."""
        with self._lock:
            self._assert_no_active_collection_locked()
            try:
                with NativeCapture() as capture:
                    timestamps: list[int] = []
                    frame: Any = None
                    for _ in range(16):
                        frame, timestamp, _dropped = capture.read()
                        timestamps.append(timestamp)
                elapsed = (timestamps[-1] - timestamps[0]) / 1_000_000_000
                fps = 15 / elapsed if elapsed > 0 else 0.0
                profile_ok = frame.shape[:2] == (720, 1280) and 12 <= fps <= 18
                return {
                    "camera": "READY" if profile_ok else "UNAVAILABLE",
                    "recording": False,
                    "requested_profile": CAPTURE_PROFILE,
                    "observed_width": int(frame.shape[1]),
                    "observed_height": int(frame.shape[0]),
                    "measured_fps": fps,
                    "frames_measured": len(timestamps),
                }
            except (CaptureError, OSError, ValueError) as exc:
                return {
                    "camera": "UNAVAILABLE",
                    "reason": str(exc)
                    if isinstance(exc, CaptureError)
                    else "CAMERA_DIAGNOSTIC_FAILED",
                    "recording": False,
                }

    def _native_preflight(self) -> Mapping[str, object]:
        camera = self.diagnose_current_camera()
        display = "UNAVAILABLE"
        if os.name == "nt":
            try:
                import ctypes

                display = (
                    "READY" if ctypes.windll.user32.GetSystemMetrics(80) >= 2 else "UNAVAILABLE"
                )
            except Exception:
                display = "UNAVAILABLE"
        try:
            probe = self.root / ".runtime-disk-probe"
            probe.write_bytes(b"pdu")
            with probe.open("r+b") as handle:
                os.fsync(handle.fileno())
            probe.unlink()
            disk = "READY"
        except OSError:
            disk = "UNAVAILABLE"
        return {"camera": camera["camera"], "display": display, "disk": disk}

    def _validate_authority(
        self, reference: str, *, withdrawal: bool = False
    ) -> Mapping[str, object]:
        record = self._authority_resolver(reference)
        if not isinstance(record, Mapping):
            raise AuthorityDenied("native collection authority was not found")
        required = (
            "consent_policy_sha256",
            "institutional_approval_sha256",
            "retention_record_sha256",
        )
        retention_expires_at = record.get("retention_expires_at")
        if (
            record.get("authority_reference") != reference
            or record.get("status") not in ({"APPROVED", "REVOKED"} if withdrawal else {"APPROVED"})
            or record.get("native_root_digest") != self.root_digest(self.root)
            or not isinstance(record.get("participant_pseudonym"), str)
            or not str(record["participant_pseudonym"]).strip()
            or record.get("consent_status")
            not in ({"CONFIRMED", "WITHDRAWN"} if withdrawal else {"CONFIRMED"})
            or not isinstance(retention_expires_at, int | float)
            or isinstance(retention_expires_at, bool)
            or not math.isfinite(retention_expires_at)
            or (not withdrawal and float(retention_expires_at) <= self._clock())
            or any(not _is_digest(record.get(field)) for field in required)
        ):
            raise AuthorityDenied(
                "native collection authority is incomplete or does not bind this root"
            )
        return record

    def _validate_export_authority(self, row: sqlite3.Row) -> None:
        reference = row["authority_reference"]
        if not isinstance(reference, str) or not reference:
            raise AuthorityDenied("EXPORT_AUTHORITY_REQUIRED")
        record = self._validate_authority(reference)
        if (
            record.get("session_pseudonym") != row["session_id"]
            or record.get("participant_pseudonym") != row["participant_pseudonym"]
        ):
            raise AuthorityDenied("AUTHORITY_SESSION_MISMATCH")
        if record.get("consent_status") == "WITHDRAWN":
            raise AuthorityDenied("CONSENT_WITHDRAWN")
        expiry = record.get("retention_expires_at")
        if not isinstance(expiry, int | float) or float(expiry) <= self._clock():
            raise AuthorityDenied("RETENTION_EXPIRED")

    def _owned_artifact_directory(self, row: sqlite3.Row) -> Path:
        candidate = Path(str(row["artifact_directory"]))
        directory = candidate.resolve()
        expected = self.artifacts_root / str(row["session_id"])
        if has_reparse_component(candidate) or directory != expected:
            raise AuthorityDenied("ARTIFACT_SCOPE_INVALID")
        return directory

    def _analyze_frame(
        self, frame: Any
    ) -> tuple[dict[str, object], list[list[dict[str, float]]], int, str | None]:
        # Quality is intentionally conservative.  The pose engine failure fails the session closed.
        grayscale = frame[..., :3].mean(axis=2)
        blur = float(np.var(np.diff(grayscale, axis=0)))
        exposure = float(grayscale.mean())
        quality: dict[str, object] = {
            "state": "SUFFICIENT" if blur >= 1.0 and 10.0 <= exposure <= 245.0 else "INSUFFICIENT",
            "blur": blur,
            "exposure": exposure,
        }
        try:
            import mediapipe as mp  # type: ignore[import-untyped]
            from mediapipe.tasks import python  # type: ignore[import-untyped]
            from mediapipe.tasks.python import vision  # type: ignore[import-untyped]

            if self._pose_landmarker is None:
                task_bytes = (
                    resources.files("pdu_exam_observer")
                    .joinpath("assets/models/pose_landmarker_lite.task")
                    .read_bytes()
                )
                options = vision.PoseLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_buffer=task_bytes),
                    running_mode=vision.RunningMode.IMAGE,
                    num_poses=2,
                )
                self._pose_landmarker = vision.PoseLandmarker.create_from_options(options)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame[..., :3][..., ::-1])
            result = self._pose_landmarker.detect(image)
        except Exception:
            return quality, [], 0, "POSE_ENGINE_FAILED"
        if not result.pose_landmarks:
            return quality, [], 0, None
        landmarks = [
            [
                {
                    "x": float(item.x),
                    "y": float(item.y),
                    "z": float(item.z),
                    "visibility": float(item.visibility),
                }
                for item in pose
            ]
            for pose in result.pose_landmarks
        ]
        if (
            len(landmarks) > 2
            or any(len(pose) != 33 for pose in landmarks)
            or any(
                not all(math.isfinite(value) for value in point.values())
                or not 0 <= point["visibility"] <= 1
                for pose in landmarks
                for point in pose
            )
        ):
            return quality, [], 0, "POSE_SCHEMA_FAILED"
        return quality, landmarks, len(landmarks), None

    def _policy_for_session(self, row: sqlite3.Row) -> RulePolicy | None:
        if row["source_kind"] != "REAL":
            return RulePolicy.demo()
        path = self.root / ".pdu_exam_observer" / "frozen-rules.v1.json"
        try:
            with open_regular_read(path) as handle:
                document = json.load(handle)
            unsigned = dict(document)
            digest = unsigned.pop("protocol_freeze_sha256")
            authority = self._validate_authority(str(row["authority_reference"]))
            if _sha256(_canonical(unsigned)) != digest or document.get(
                "protocol_version"
            ) != authority.get("protocol_version"):
                return None
            return RulePolicy.from_protocol_freeze(document)
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _persist_rule_events_locked(
        self,
        session_id: str,
        row: sqlite3.Row,
        events: list[RuleEvent],
        *,
        signal: str,
        policy: RulePolicy,
        confidence: float | None = None,
    ) -> None:
        for event in events:
            payload = self._event_payload(
                row,
                event.label,
                event.start_ms,
                event.end_ms,
                [signal],
                "CALIBRATED" if confidence is not None else "NOT_APPLICABLE",
                confidence,
            )
            payload.update(
                logical_id=event.logical_id,
                event_state=event.kind,
                eligible_onset_ms=event.eligible_onset_ms,
                policy_version=policy.policy_version,
            )
            key = (session_id, event.logical_id)
            existing = self._logical_events.get(key)
            if existing is None:
                saved = self._append_event_locked(session_id, "OBSERVABLE_EVENT", payload)
                self._logical_events[key] = str(saved["event_id"])
            else:
                self._connection.execute(
                    "UPDATE runtime_events SET payload_json=? WHERE event_id=?",
                    (_canonical(payload).decode("utf-8"), existing),
                )
                self._append_event_locked(
                    session_id,
                    "EVENT_BOUNDARY_UPDATE",
                    {
                        "event_id": existing,
                        "start_ms": event.start_ms,
                        "end_ms": event.end_ms,
                        "event_state": event.kind,
                    },
                )

    def _emit_model_or_rule_locked(
        self,
        session_id: str,
        row: sqlite3.Row,
        observation: Mapping[str, Any],
        landmarks: list[list[dict[str, float]]],
    ) -> None:
        captured_ns = int(observation["captured_ns"])
        origin = self._capture_origins.setdefault(session_id, captured_ns)
        timestamp_ms = (captured_ns - origin) // 1_000_000
        quality = observation["quality"]
        count = int(observation["pose_count"])
        policy = self._policy_for_session(row)
        if policy is None:
            if int(observation["frame_seq"]) == 1:
                self._append_event_locked(
                    session_id,
                    "TECHNICAL_STATE",
                    {"state": "TECHNICAL_INSUFFICIENT", "reason": "RULE_POLICY_NOT_FROZEN"},
                )
            return
        engine = self._rule_engines.setdefault(session_id, TemporalRuleEngine(policy))
        policy = engine.policy
        if int(observation["frame_seq"]) == 1:
            self._append_event_locked(session_id, "RULE_POLICY_BOUND", policy.to_document())
        down = side = 0.0
        quality_ok = quality["state"] in {"SUFFICIENT", "SYNTHETIC"}
        if count == 1:
            try:
                down, side = orientation_proxy_degrees(landmarks[0])
            except ValueError:
                quality_ok = False
        self._persist_rule_events_locked(
            session_id,
            row,
            engine.advance(timestamp_ms, count, down, side, quality_ok=quality_ok),
            signal="INDEPENDENT_TEMPORAL_RULES",
            policy=policy,
        )
        if self._model_provider is None:
            return
        buffer = self._pose_buffers.get(session_id, deque())
        if len(buffer) < 2 or captured_ns - buffer[0]["captured_ns"] < 5_933_333_334:
            return
        if timestamp_ms - self._last_model_times.get(session_id, -1000) < 500:
            return
        self._last_model_times[session_id] = timestamp_ms
        cutoff = captured_ns - 6_000_000_000
        frames = [item for item in buffer if item["captured_ns"] >= cutoff]
        model_engine = self._model_engines.setdefault(session_id, TemporalRuleEngine(policy))
        prediction: Mapping[str, object] | None = None
        if quality_ok and all(item["pose_count"] == 1 for item in frames):
            try:
                values = np.asarray(
                    [
                        [
                            [point[k] for k in ("x", "y", "z", "visibility")]
                            for point in item["landmarks"][0]
                        ]
                        for item in frames
                    ],
                    dtype=np.float32,
                )
                processed = resample_pose_window(
                    np.asarray([item["captured_ns"] for item in frames], dtype=np.int64),
                    values,
                    values[..., 3] > 0,
                )
                context = aggregate_context_rows(
                    [
                        {
                            "visibility_mean": float(item["quality"]["visibility_mean"]),
                            "blur_score": float(item["quality"].get("blur") or 0),
                            "exposure_score": float(item["quality"].get("exposure") or 0),
                            "frame_gap_ratio": float(item["quality"]["frame_gap_ratio"]),
                            "focus_fraction": float(item["focus"] == "EXAM_FOCUSED"),
                            "scaled_focus_signal_age": min(float(item["focus_age_ms"]) / 6000, 1),
                        }
                        for item in frames
                    ]
                )
                if observation.get("focus") != "FOCUS_UNKNOWN":
                    prediction = self._model_provider(
                        {
                            "pose_tensor": processed.tensor,
                            "context": context,
                            "source_kind": row["source_kind"],
                        }
                    )
            except (ValueError, TypeError, RuntimeError, KeyError):
                prediction = None
        label = prediction.get("label") if prediction else None
        valid = label in {
            "NORMAL",
            "BENIGN_CONFOUNDER",
            "PROLONGED_HEAD_DOWN",
            "PROLONGED_SIDE_LOOK",
        }
        confidence = prediction.get("confidence") if prediction else None
        valid = (
            valid
            and isinstance(confidence, float | int)
            and np.isfinite(confidence)
            and 0 <= confidence <= 1
        )
        self._append_event_locked(
            session_id,
            "MODEL_STATE",
            {
                "state": "READY" if valid else "TECHNICAL_INSUFFICIENT",
                "reason": "PREDICTION" if valid else "MODEL_OR_INPUT_UNAVAILABLE",
                "frame_seq": observation["frame_seq"],
                "model_version": prediction.get("model_version") if prediction else None,
                "policy_version": prediction.get("policy_version") if prediction else None,
                "model_invoked": prediction is not None,
                "model_outcome": prediction.get("operator_outcome") if prediction else None,
                "source_signals": prediction.get("source_signals") if prediction else None,
            },
        )
        events = model_engine.advance(
            timestamp_ms,
            1,
            0,
            0,
            quality_ok=bool(valid),
            prediction_label=str(label) if valid else "UNCERTAIN",
        )
        self._persist_rule_events_locked(
            session_id,
            row,
            events,
            signal="ST_GCN_TEMPORAL_MODEL",
            policy=policy,
            confidence=float(cast(float, confidence)) if valid else None,
        )

    def _event_payload(
        self,
        row: sqlite3.Row,
        label: str,
        start_ms: int,
        end_ms: int,
        signals: list[str],
        confidence_status: str,
        confidence: float | None,
    ) -> dict[str, object]:
        return {
            "research_label": label,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "source_signals": signals,
            "confidence_status": confidence_status,
            "confidence": confidence,
            "source_kind": row["source_kind"],
            "policy_version": "runtime-policy.v1",
            "schema_version": SCHEMA_VERSION,
        }

    def _write_frame_locked(
        self, session_id: str, frame: Any, observation: Mapping[str, object]
    ) -> None:
        stream = self._streams.get(session_id)
        if stream is None:
            directory = Path(str(self._session_row(session_id)["artifact_directory"]))
            pose_partial = directory / "pose_timeline.jsonl.partial"
            video_partial = directory / "raw_video.partial.avi"
            try:
                import cv2

                writer = cv2.VideoWriter(
                    str(video_partial),
                    cv2.VideoWriter_fourcc(*"MJPG"),  # type: ignore[attr-defined]
                    15.0,
                    (1280, 720),
                )
            except ImportError as exc:
                raise RuntimeErrorBase("ENCODER_UNAVAILABLE") from exc
            if not writer.isOpened():
                raise RuntimeErrorBase("ENCODER_MP4_UNAVAILABLE")
            stream = _ArtifactStream(
                pose_partial=pose_partial,
                pose_handle=pose_partial.open("x", encoding="utf-8"),
                video_partial=video_partial,
                video_writer=writer,
                origin_ns=int(cast(int, observation["captured_ns"])),
            )
            self._streams[session_id] = stream
        # Repeat only the last received frame to keep fixed-FPS playback aligned
        # with monotonic pose timestamps; never compress a dropped-frame interval.
        target_index = round(
            (int(cast(int, observation["captured_ns"])) - stream.origin_ns) * 15 / 1_000_000_000
        )
        if target_index - stream.written_frames > 45:
            raise RuntimeErrorBase("FRAME_GAP_EXCEEDED")
        while stream.written_frames < target_index and stream.last_frame is not None:
            stream.video_writer.write(stream.last_frame)
            stream.written_frames += 1
        stream.last_frame = np.ascontiguousarray(frame[..., :3])
        stream.video_writer.write(stream.last_frame)
        stream.written_frames += 1
        stream.pose_handle.write(_canonical(dict(observation)).decode("utf-8") + "\n")
        stream.pose_handle.flush()

    def _write_synthetic_fixture_locked(self, session_id: str) -> None:
        """Emit a tiny drawn skeleton clip, never a camera frame or generated person image."""
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeErrorBase("SYNTHETIC_RENDERER_UNAVAILABLE") from exc
        base_ns = time.perf_counter_ns() - 6_100_000_000
        coordinates = [
            (0.50, 0.20),
            (0.49, 0.19),
            (0.48, 0.19),
            (0.47, 0.19),
            (0.51, 0.19),
            (0.52, 0.19),
            (0.53, 0.19),
            (0.46, 0.21),
            (0.54, 0.21),
            (0.49, 0.23),
            (0.51, 0.23),
            (0.42, 0.34),
            (0.58, 0.34),
            (0.35, 0.47),
            (0.65, 0.47),
            (0.32, 0.60),
            (0.68, 0.60),
            (0.31, 0.62),
            (0.69, 0.62),
            (0.32, 0.63),
            (0.68, 0.63),
            (0.34, 0.61),
            (0.66, 0.61),
            (0.45, 0.59),
            (0.55, 0.59),
            (0.44, 0.76),
            (0.56, 0.76),
            (0.43, 0.92),
            (0.57, 0.92),
            (0.44, 0.94),
            (0.56, 0.94),
            (0.40, 0.95),
            (0.60, 0.95),
        ]
        edges = (
            (0, 11),
            (0, 12),
            (11, 12),
            (11, 13),
            (13, 15),
            (12, 14),
            (14, 16),
            (11, 23),
            (12, 24),
            (23, 24),
            (23, 25),
            (25, 27),
            (24, 26),
            (26, 28),
            (27, 31),
            (28, 32),
        )
        # Exactly six seconds at the locked 15 fps preprocessing contract.
        for frame_seq in range(1, 91):
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            shift = math.sin(frame_seq / 15) * 0.01
            landmark_template = [
                {"x": x + shift, "y": y, "z": 0.0, "visibility": 1.0} for x, y in coordinates
            ]
            points = [
                (int(point["x"] * 1280), int(point["y"] * 720)) for point in landmark_template
            ]
            for start, end in edges:
                cv2.line(frame, points[start], points[end], (130, 220, 80), 5)
            for point in points:
                cv2.circle(frame, point, 5, (220, 220, 220), -1)
            captured_ns = base_ns + frame_seq * 66_666_667
            observation = {
                "frame_seq": frame_seq,
                "captured_ns": captured_ns,
                "pose_count": 1,
                "landmarks": [landmark_template],
                "quality": {
                    "state": "SYNTHETIC",
                    "blur": 5.0,
                    "exposure": 128.0,
                    "visibility_mean": 1.0,
                    "frame_gap_ratio": 0.0,
                },
                "focus": "EXAM_FOCUSED",
                "focus_age_ms": 0.0,
            }
            self._write_frame_locked(session_id, frame, observation)
            self._pose_buffers.setdefault(session_id, deque(maxlen=180)).append(observation)
            self._emit_model_or_rule_locked(
                session_id, self._session_row(session_id), observation, [landmark_template]
            )
            self._update_session_locked(session_id, frame_seq=frame_seq, quality_state="SYNTHETIC")
            self._append_event_locked(
                session_id,
                "POSE_OBSERVATION",
                {"frame_seq": frame_seq, "captured_ns": captured_ns, "pose_count": 1},
            )

    def _close_stream_locked(self, session_id: str, *, finalize: bool) -> None:
        stream = self._streams.pop(session_id, None)
        if stream is None:
            return
        try:
            stream.pose_handle.flush()
            os.fsync(stream.pose_handle.fileno())
        finally:
            stream.pose_handle.close()
            stream.video_writer.release()
        if not finalize:
            return
        if not stream.video_partial.is_file() or stream.video_partial.stat().st_size == 0:
            raise RuntimeErrorBase("ENCODER_WRITE_FAILED")
        video_destination = stream.video_partial.with_name("raw_video.mp4")
        video_partial = video_destination.with_name("raw_video.partial.mp4")
        ffmpeg = self._ffmpeg_path()
        if ffmpeg is None:
            raise RuntimeErrorBase("ENCODER_FFMPEG_UNAVAILABLE")
        result = subprocess.run(
            [
                str(ffmpeg),
                "-nostdin",
                "-y",
                "-i",
                str(stream.video_partial),
                "-map_metadata",
                "-1",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(video_partial),
            ],
            check=False,
            capture_output=True,
            timeout=60,
        )
        if (
            result.returncode != 0
            or not video_partial.is_file()
            or video_partial.stat().st_size == 0
        ):
            raise RuntimeErrorBase("ENCODER_TRANSCODE_FAILED")
        pose_destination = stream.pose_partial.with_name("pose_timeline.jsonl")
        with video_partial.open("r+b") as handle:
            os.fsync(handle.fileno())
        video_partial.replace(video_destination)
        stream.video_partial.unlink(missing_ok=True)
        stream.pose_partial.replace(pose_destination)
        for path in (video_destination, pose_destination):
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            self._connection.execute(
                "INSERT OR REPLACE INTO runtime_artifacts VALUES(?,?,?,?)",
                (session_id, path.name, digest, path.stat().st_size),
            )

    def _verify_artifacts_locked(self, row: sqlite3.Row) -> None:
        directory = self._owned_artifact_directory(row)
        records = self._connection.execute(
            "SELECT * FROM runtime_artifacts WHERE session_id=?", (row["session_id"],)
        ).fetchall()
        if {record["name"] for record in records} != {"raw_video.mp4", "pose_timeline.jsonl"}:
            raise InvalidTransition("ARTIFACT_MANIFEST_MISSING")
        for record in records:
            path = directory / record["name"]
            if (
                has_reparse_component(path)
                or not path.is_file()
                or path.stat().st_size != record["size_bytes"]
            ):
                raise InvalidTransition("ARTIFACT_INTEGRITY_FAILED")
            digest = hashlib.sha256()
            with open_regular_read(path) as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != record["sha256"]:
                raise InvalidTransition("ARTIFACT_INTEGRITY_FAILED")

    def _withdrawal_artifact_inventory_locked(self, row: sqlite3.Row) -> list[dict[str, object]]:
        directory = self._owned_artifact_directory(row)
        if not directory.exists():
            return []
        records = {
            record["name"]: record
            for record in self._connection.execute(
                "SELECT * FROM runtime_artifacts WHERE session_id=?", (row["session_id"],)
            ).fetchall()
        }
        if row["state"] == "SEALED":
            self._verify_artifacts_locked(row)
            allowed = set(records)
        else:
            partials = {
                "raw_video.partial.avi",
                "raw_video.partial.mp4",
                "pose_timeline.jsonl.partial",
            }
            allowed = (
                {"raw_video.mp4", "pose_timeline.jsonl"}
                | partials
                | {name + ".quarantine" for name in partials}
            )
        inventory: list[dict[str, object]] = []
        for path in sorted(directory.iterdir()):
            if path.name not in allowed or has_reparse_component(path) or not path.is_file():
                raise InvalidTransition("UNOWNED_ARTIFACT_PRESENT")
            hasher = hashlib.sha256()
            with open_regular_read(path) as handle:
                while chunk := handle.read(1024 * 1024):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
            size = path.stat().st_size
            expected = records.get(path.name)
            if expected is not None and (
                expected["sha256"] != digest or expected["size_bytes"] != size
            ):
                raise InvalidTransition("ARTIFACT_INTEGRITY_FAILED")
            inventory.append({"name": path.name, "sha256": digest, "size_bytes": size})
        return inventory

    def _duration_ms_locked(self, row: sqlite3.Row) -> int:
        timeline = self._owned_artifact_directory(row) / "pose_timeline.jsonl"
        first: int | None = None
        last = 0
        with open_regular_read(timeline) as handle:
            for line in handle:
                stamp = int(json.loads(line)["captured_ns"])
                first = stamp if first is None else first
                last = stamp
        return 0 if first is None else (last - first) // 1_000_000 + 67

    def _open_current_camera(self) -> Any:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeErrorBase("CAMERA_UNAVAILABLE") from exc
        if os.name == "nt":
            return cv2.VideoCapture(0, cv2.CAP_DSHOW)
        return cv2.VideoCapture(0)

    @staticmethod
    def _ffmpeg_path() -> Path | None:
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "tools" / "ffmpeg.exe"
        if bundled.is_file():
            return bundled.resolve()
        discovered = shutil.which("ffmpeg")
        return Path(discovered).resolve() if discovered else None

    def _export_records(
        self, row: sqlite3.Row, reviews: list[dict[str, object]], events: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        timeline = self._owned_artifact_directory(row) / "pose_timeline.jsonl"
        if row["source_kind"] == "REAL" and not timeline.is_file():
            raise InvalidTransition("POSE_TIMELINE_UNAVAILABLE")
        observations: list[dict[str, object]] = []
        if timeline.is_file():
            with open_regular_read(timeline) as handle:
                content = handle.read()
                expected = self._connection.execute(
                    "SELECT sha256 FROM runtime_artifacts WHERE session_id=? "
                    "AND name='pose_timeline.jsonl'",
                    (row["session_id"],),
                ).fetchone()
                if expected is None or _sha256(content) != expected[0]:
                    raise InvalidTransition("ARTIFACT_INTEGRITY_FAILED")
                handle.seek(0)
                observations = [json.loads(line) for line in handle if line.strip()]
        if row["source_kind"] == "REAL" and not observations:
            raise InvalidTransition("POSE_TIMELINE_UNAVAILABLE")
        latest = {str(review["event_id"]): review for review in reviews}
        boundaries = [review for review in latest.values() if review["review_status"] != "REJECTED"]
        phase = "DEMO"
        if row["source_kind"] == "REAL":
            authority = self._validate_authority(str(row["authority_reference"]))
            phase = str(authority.get("cohort", ""))
            if phase not in {"PILOT", "CONFIRMATORY"}:
                raise AuthorityDenied("COHORT_REQUIRED")
        origin_ns = 0
        if observations:
            first_ns = observations[0].get("captured_ns")
            if not isinstance(first_ns, int):
                raise InvalidTransition("POSE_TIMELINE_INVALID")
            origin_ns = first_ns
        result: list[dict[str, object]] = []
        for observation in observations:
            captured_ns = observation.get("captured_ns")
            if not isinstance(captured_ns, int):
                raise InvalidTransition("POSE_TIMELINE_INVALID")
            offset_ms = (captured_ns - origin_ns) // 1_000_000
            matching = next(
                (
                    review
                    for review in boundaries
                    if isinstance(review.get("start_ms"), int)
                    and isinstance(review.get("end_ms"), int)
                    and cast(int, review["start_ms"]) <= offset_ms < cast(int, review["end_ms"])
                ),
                None,
            )
            label = (
                matching["label"]
                if matching is not None and matching["review_status"] == "CONFIRMED"
                else "UNCERTAIN"
            )
            result.append(
                {
                    "export_id": "",
                    "manifest_sha256": "",
                    "schema_version": SCHEMA_VERSION,
                    "record_count": 0,
                    "sample_id": str(uuid.uuid4()),
                    "participant_pseudonym": str(row["participant_pseudonym"]),
                    "session_pseudonym": str(row["session_id"]),
                    "source_kind": str(row["source_kind"]),
                    "parent_provenance_id": f"{row['session_id']}:{observation['frame_seq']}",
                    "pose": {
                        "topology": "mediapipe-33",
                        "landmarks": observation["landmarks"],
                        "pose_count": observation["pose_count"],
                    },
                    "label": label,
                    "quality": observation["quality"],
                    "focus": {
                        "state": observation["focus"],
                        "signal_age_ms": observation.get("focus_age_ms", 6001),
                        "contaminated_by_operator": False,
                    },
                    "timing": {
                        "captured_ns": observation["captured_ns"],
                        "offset_ms": offset_ms,
                        "phase": phase,
                    },
                }
            )
        if observations:
            return result
        # Synthetic fixtures remain exportable for UI/training plumbing, with explicit provenance.
        for event in events:
            if event["event_type"] == "OBSERVABLE_EVENT":
                result.append(
                    {
                        "export_id": "",
                        "manifest_sha256": "",
                        "schema_version": SCHEMA_VERSION,
                        "record_count": 0,
                        "sample_id": str(uuid.uuid4()),
                        "participant_pseudonym": str(row["participant_pseudonym"]),
                        "session_pseudonym": str(row["session_id"]),
                        "source_kind": str(row["source_kind"]),
                        "parent_provenance_id": str(event["event_id"]),
                        "pose": {"topology": "synthetic-fixture"},
                        "label": "UNCERTAIN",
                        "quality": {"state": "SYNTHETIC"},
                        "focus": {"state": "FOCUS_UNKNOWN"},
                        "timing": {"start_ms": 0, "end_ms": 0},
                    }
                )
        return result

    def _session_row(self, session_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM runtime_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError("unknown runtime session")
        return cast(sqlite3.Row, row)

    def _require_state(self, session_id: str, states: set[str]) -> sqlite3.Row:
        row = self._session_row(session_id)
        if row["state"] not in states:
            raise InvalidTransition(f"session state {row['state']} cannot perform this operation")
        return row

    def _assert_no_active_collection_locked(self) -> None:
        active = self._connection.execute(
            "SELECT session_id FROM runtime_sessions WHERE state='RECORDING' LIMIT 1"
        ).fetchone()
        if active is not None or any(
            worker.is_alive() for worker in self._capture_threads.values()
        ):
            raise InvalidTransition("an active collection session already owns the camera")

    def _update_session_locked(self, session_id: str, **changes: object) -> None:
        if not changes:
            return
        columns = ", ".join(f"{name}=?" for name in changes)
        self._connection.execute(
            f"UPDATE runtime_sessions SET {columns} WHERE session_id=?",
            (*changes.values(), session_id),
        )

    def _append_event_locked(
        self, session_id: str, event_type: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        next_seq = int(
            self._connection.execute(
                "SELECT COALESCE(MAX(event_seq),0)+1 FROM runtime_events WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
        )
        event_id = str(uuid.uuid4())
        source_kind = str(self._session_row(session_id)["source_kind"])
        persisted_payload = {
            "source_kind": source_kind,
            "schema_version": SCHEMA_VERSION,
            **dict(payload),
        }
        self._connection.execute(
            "INSERT INTO runtime_events VALUES(?,?,?,?,?,?)",
            (
                event_id,
                session_id,
                next_seq,
                event_type,
                _canonical(persisted_payload).decode("utf-8"),
                self._clock(),
            ),
        )
        return {
            "event_id": event_id,
            "event_seq": next_seq,
            "event_type": event_type,
            **persisted_payload,
        }

    def _fail_locked(self, session_id: str, failure_code: str) -> None:
        self._close_stream_locked(session_id, finalize=False)
        self._update_session_locked(
            session_id,
            state="FAILED",
            failure_code=failure_code,
            quality_state="TECHNICAL_INSUFFICIENT",
        )
        self._append_event_locked(
            session_id,
            "TECHNICAL_FAILURE",
            {"code": failure_code, "confidence_status": "INSUFFICIENT"},
        )

    @staticmethod
    def _event_dict(row: sqlite3.Row) -> dict[str, object]:
        return {
            "event_id": row["event_id"],
            "event_seq": row["event_seq"],
            "event_type": row["event_type"],
            "created_at": row["created_at"],
            **json.loads(row["payload_json"]),
        }

    @staticmethod
    def _session_dict(row: sqlite3.Row, *, event_count: int) -> dict[str, object]:
        return {
            "session_id": row["session_id"],
            "source_kind": row["source_kind"],
            "participant_pseudonym": row["participant_pseudonym"],
            "state": row["state"],
            "revision": row["revision"],
            "event_count": event_count,
            "locked": bool(row["locked"]),
            "artifacts": {"directory": row["artifact_directory"]},
            "artifact_directory": row["artifact_directory"],
            "quality_state": row["quality_state"],
            "focus_state": row["focus_state"],
            "failure_reason": row["failure_code"],
            "capture_profile": CAPTURE_PROFILE,
        }
