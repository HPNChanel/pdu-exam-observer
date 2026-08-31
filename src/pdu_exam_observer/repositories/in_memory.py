from dataclasses import dataclass, field
from typing import Protocol

from pdu_exam_observer.contracts import SessionState


@dataclass
class SessionRecord:
    session_id: str
    state: SessionState = SessionState.DRAFT
    event_seq: int = 0
    submitted: bool = False
    duration_seconds: int = 2700
    started_at: float | None = None
    answers: dict[str, dict[str, object]] = field(default_factory=dict)
    answer_results: dict[str, dict[str, object]] = field(default_factory=dict)
    submit_results: dict[str, dict[str, object]] = field(default_factory=dict)
    events: list["EventRecord"] = field(default_factory=list)


@dataclass(frozen=True)
class EventRecord:
    event_seq: int
    type: str
    payload: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {"event_seq": self.event_seq, "type": self.type, **self.payload}


class SessionRepository(Protocol):
    def create(self, session_id: str) -> SessionRecord: ...

    def get(self, session_id: str) -> SessionRecord | None: ...

    def append_event(
        self, session_id: str, event_type: str, payload: dict[str, object]
    ) -> EventRecord: ...

    def events_after(self, session_id: str, event_seq: int) -> list[EventRecord]: ...


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def create(self, session_id: str) -> SessionRecord:
        record = SessionRecord(session_id=session_id)
        self._sessions[session_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def append_event(
        self, session_id: str, event_type: str, payload: dict[str, object]
    ) -> EventRecord:
        record = self._sessions[session_id]
        record.event_seq += 1
        event = EventRecord(record.event_seq, event_type, payload)
        record.events.append(event)
        return event

    def events_after(self, session_id: str, event_seq: int) -> list[EventRecord]:
        record = self._sessions.get(session_id)
        if record is None:
            return []
        return [event for event in record.events if event.event_seq > event_seq]
