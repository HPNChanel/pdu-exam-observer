import asyncio
import hashlib
import hmac
import json
import math
import sys
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_bytes, token_urlsafe

from pdu_exam_observer.contracts import ConfidenceStatus, SessionSnapshot, SessionState
from pdu_exam_observer.domain.state import InvalidTransition, transition
from pdu_exam_observer.repositories.in_memory import InMemorySessionRepository, SessionRecord


class IdempotencyConflict(InvalidTransition):
    """An idempotency key was reused for a different request body."""


class ReviewerClockInvalid(RuntimeError):
    """A reviewer bearer cannot be issued from invalid clock evidence."""


REVIEWER_BEARER_TTL_SECONDS = 2 * 60 * 60


@dataclass(frozen=True)
class LoginResult:
    accepted: bool
    retry_after: int | None = None


@dataclass
class ReviewerAuthenticator:
    """Startup-only PIN verifier; the input PIN is never retained."""

    pin: str
    max_failures: int = 5
    cooldown_seconds: int = 60
    _salt: bytes = field(init=False, repr=False)
    _pin_hash: bytes = field(init=False, repr=False)
    _failures: dict[str, tuple[int, float]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._salt = token_bytes(16)
        self._pin_hash = hashlib.scrypt(
            self.pin.encode("utf-8"), salt=self._salt, n=2**14, r=8, p=1, dklen=32
        )
        self.pin = ""

    def authenticate(self, pin: str, client_key: str, now: float) -> LoginResult:
        attempts, blocked_until = self._failures.get(client_key, (0, 0.0))
        if blocked_until > now:
            return LoginResult(False, max(1, math.ceil(blocked_until - now)))
        candidate_hash = hashlib.scrypt(
            pin.encode("utf-8"), salt=self._salt, n=2**14, r=8, p=1, dklen=32
        )
        if hmac.compare_digest(candidate_hash, self._pin_hash):
            self._failures.pop(client_key, None)
            return LoginResult(True)
        attempts += 1
        if attempts >= self.max_failures:
            self._failures[client_key] = (attempts, now + self.cooldown_seconds)
            return LoginResult(False, self.cooldown_seconds)
        self._failures[client_key] = (attempts, 0.0)
        return LoginResult(False)


def _runtime_demo_fixture() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    return root / "demo" / "events.jsonl"


@dataclass
class M0Backend:
    sessions: InMemorySessionRepository = field(default_factory=InMemorySessionRepository)
    clock: Callable[[], float] = time.time
    monotonic_clock: Callable[[], float] = time.monotonic
    duration_seconds: int = 2700
    candidate_tokens: dict[str, str] = field(default_factory=dict)
    candidate_csrf_tokens: dict[str, str] = field(default_factory=dict)
    pairing_codes: dict[str, str] = field(default_factory=dict)
    demo_fixture: Path = field(default_factory=_runtime_demo_fixture)
    _reviewer_token_digest: bytes | None = field(default=None, init=False, repr=False)
    _reviewer_token_issued_at: float | None = field(default=None, init=False, repr=False)
    _reviewer_token_expiry: float | None = field(default=None, init=False, repr=False)
    _reviewer_token_monotonic_issued: float | None = field(
        default=None, init=False, repr=False
    )
    _reviewer_token_monotonic_expiry: float | None = field(
        default=None, init=False, repr=False
    )
    _reviewer_session_revocation_callback: Callable[[str], None] | None = field(
        default=None, init=False, repr=False
    )
    _subscribers: dict[str, list[asyncio.Queue[dict[str, object]]]] = field(default_factory=dict)

    def append_event(
        self, session_id: str, event_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        event = self.sessions.append_event(session_id, event_type, payload).as_dict()
        for subscriber in self._subscribers.get(session_id, []):
            subscriber.put_nowait(event)
        return event

    def append_demo_event(self, session_id: str, payload: dict[str, object]) -> dict[str, object]:
        return self.append_event(session_id, "DemoEvent", payload)

    def issue_reviewer_token(self) -> str:
        issued_at = self.clock()
        monotonic_issued = self.monotonic_clock()
        expiry = issued_at + REVIEWER_BEARER_TTL_SECONDS
        monotonic_expiry = monotonic_issued + REVIEWER_BEARER_TTL_SECONDS
        if not all(
            math.isfinite(value)
            for value in (issued_at, expiry, monotonic_issued, monotonic_expiry)
        ):
            self._invalidate_reviewer_session()
            raise ReviewerClockInvalid("CLOCK_INVALID")
        self._invalidate_reviewer_session()
        token = token_urlsafe(32)
        self._reviewer_token_digest = hashlib.sha256(token.encode("utf-8")).digest()
        self._reviewer_token_issued_at = issued_at
        self._reviewer_token_expiry = expiry
        self._reviewer_token_monotonic_issued = monotonic_issued
        self._reviewer_token_monotonic_expiry = monotonic_expiry
        return token

    def register_reviewer_session_revocation(
        self, callback: Callable[[str], None]
    ) -> None:
        self._reviewer_session_revocation_callback = callback

    def _invalidate_reviewer_session(self) -> None:
        digest = self._reviewer_token_digest
        try:
            if digest is not None and self._reviewer_session_revocation_callback is not None:
                self._reviewer_session_revocation_callback(digest.hex())
        finally:
            self._clear_reviewer_token()

    def _clear_reviewer_token(self) -> None:
        self._reviewer_token_digest = None
        self._reviewer_token_issued_at = None
        self._reviewer_token_expiry = None
        self._reviewer_token_monotonic_issued = None
        self._reviewer_token_monotonic_expiry = None

    def reviewer_expiry(self, token: str | None) -> float | None:
        expiry = self._reviewer_token_expiry
        digest = self._reviewer_token_digest
        issued_at = self._reviewer_token_issued_at
        monotonic_issued = self._reviewer_token_monotonic_issued
        monotonic_expiry = self._reviewer_token_monotonic_expiry
        if (
            expiry is None
            or digest is None
            or issued_at is None
            or monotonic_issued is None
            or monotonic_expiry is None
        ):
            return None
        now = self.clock()
        monotonic_now = self.monotonic_clock()
        if (
            not all(
                math.isfinite(value)
                for value in (
                    now,
                    expiry,
                    issued_at,
                    monotonic_now,
                    monotonic_issued,
                    monotonic_expiry,
                )
            )
            or monotonic_now < monotonic_issued
            or monotonic_expiry <= monotonic_now
            or now < issued_at
            or expiry <= now
        ):
            self._invalidate_reviewer_session()
            return None
        if token is None:
            return None
        candidate_digest = hashlib.sha256(token.encode("utf-8")).digest()
        return expiry if hmac.compare_digest(digest, candidate_digest) else None

    def is_reviewer(self, token: str | None) -> bool:
        return self.reviewer_expiry(token) is not None

    def reviewer_session_digest(self, token: str | None) -> str | None:
        """Return the current bearer binding without returning or persisting the bearer."""

        if self.reviewer_expiry(token) is None or token is None:
            return None
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def revoke_reviewer_token(self, token: str | None) -> None:
        if token is None or self._reviewer_token_digest is None:
            return
        candidate_digest = hashlib.sha256(token.encode("utf-8")).digest()
        if hmac.compare_digest(self._reviewer_token_digest, candidate_digest):
            self._invalidate_reviewer_session()

    def create_session(self) -> tuple[SessionRecord, str]:
        session_id = token_urlsafe(18)
        pairing_code = token_urlsafe(12)
        record = self.sessions.create(session_id)
        record.duration_seconds = self.duration_seconds
        self.pairing_codes[pairing_code] = session_id
        return record, pairing_code

    def consume_pairing_code(self, pairing_code: str) -> tuple[str, str] | None:
        session_id = self.pairing_codes.pop(pairing_code, None)
        if session_id is None:
            return None
        token = token_urlsafe(32)
        self.candidate_tokens[token] = session_id
        return token, session_id

    def candidate_session(self, token: str | None) -> str | None:
        return self.candidate_tokens.get(token) if token is not None else None

    def issue_candidate_csrf(self, token: str) -> str:
        csrf = token_urlsafe(32)
        self.candidate_csrf_tokens[token] = csrf
        return csrf

    def has_candidate_csrf(self, token: str | None, csrf: str | None) -> bool:
        return (
            token is not None and csrf is not None and self.candidate_csrf_tokens.get(token) == csrf
        )

    def snapshot(self, session_id: str) -> SessionSnapshot | None:
        record = self.sessions.get(session_id)
        if record is None:
            return None
        remaining = None
        started_at_utc = None
        if record.started_at is not None:
            elapsed = max(0, int(self.clock() - record.started_at))
            remaining = max(0, record.duration_seconds - elapsed)
            started_at_utc = (
                datetime.fromtimestamp(record.started_at, UTC).isoformat().replace("+00:00", "Z")
            )
        return SessionSnapshot(
            session_id=record.session_id,
            state=record.state,
            event_seq=record.event_seq,
            submitted=record.submitted,
            duration_seconds=record.duration_seconds,
            remaining_seconds=remaining,
            started_at_utc=started_at_utc,
        )

    def apply_session_action(self, session_id: str, action: str) -> SessionSnapshot | None:
        record = self.sessions.get(session_id)
        if record is None:
            return None
        next_state = transition(record.state, action)
        if next_state != record.state:
            if action == "start":
                record.started_at = self.clock()
            record.state = next_state
            self.append_event(session_id, "SessionStateChanged", {"state": record.state})
        return self.snapshot(session_id)

    def record_answer(
        self, session_id: str, idempotency_key: str, payload: dict[str, object]
    ) -> dict[str, object]:
        record = self.sessions.get(session_id)
        if record is None:
            raise KeyError(session_id)
        existing = record.answers.get(idempotency_key)
        if existing is not None:
            if existing != payload:
                raise IdempotencyConflict(
                    "Idempotency key was reused with a different answer payload"
                )
            return record.answer_results[idempotency_key]
        if record.state is not SessionState.RECORDING or record.submitted:
            raise InvalidTransition("Answers are accepted only while the session is recording")
        result: dict[str, object] = {"schema_version": 1, "accepted": True}
        record.answers[idempotency_key] = payload
        record.answer_results[idempotency_key] = result
        self.append_event(session_id, "AnswerRecorded", {"answer_id": payload["answer_id"]})
        return result

    def submit_exam(self, session_id: str, idempotency_key: str) -> dict[str, object]:
        record = self.sessions.get(session_id)
        if record is None:
            raise KeyError(session_id)
        existing = record.submit_results.get(idempotency_key)
        if existing is not None:
            return existing
        if record.state is not SessionState.RECORDING:
            raise InvalidTransition("Exam can be submitted only while the session is recording")
        if record.submitted:
            raise IdempotencyConflict("Exam was already submitted with a different idempotency key")
        result: dict[str, object] = {"schema_version": 1, "submitted": True}
        record.submitted = True
        record.submit_results[idempotency_key] = result
        self.append_event(session_id, "ExamSubmitted", {})
        return result

    def events_after(self, session_id: str, event_seq: int) -> list[dict[str, object]]:
        return [event.as_dict() for event in self.sessions.events_after(session_id, event_seq)]

    async def stream_events(
        self, session_id: str, event_seq: int, heartbeat_seconds: float = 15.0
    ) -> AsyncGenerator[dict[str, object] | None, None]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        subscribers = self._subscribers.setdefault(session_id, [])
        subscribers.append(queue)
        try:
            snapshot = self.snapshot(session_id)
            if snapshot is None:
                raise KeyError(session_id)
            yield {"type": "SessionSnapshot", **snapshot.model_dump(mode="json")}
            last_delivered = event_seq
            for event in self.events_after(session_id, last_delivered):
                sequence = event["event_seq"]
                if not isinstance(sequence, int):
                    continue
                last_delivered = sequence
                yield event
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                    sequence = event["event_seq"]
                    if isinstance(sequence, int) and sequence > last_delivered:
                        last_delivered = sequence
                        yield event
                except TimeoutError:
                    yield None
        finally:
            subscribers.remove(queue)

    async def stream_reviewer_events(
        self,
        session_id: str,
        event_seq: int,
        token: str,
        heartbeat_seconds: float = 15.0,
    ) -> AsyncIterator[dict[str, object] | None]:
        stream = self.stream_events(session_id, event_seq, heartbeat_seconds)
        try:
            while True:
                try:
                    event = await anext(stream)
                except StopAsyncIteration:
                    return
                if not self.is_reviewer(token):
                    return
                yield event
        finally:
            await stream.aclose()

    def _fixture_events(self) -> list[dict[str, object]]:
        if not self.demo_fixture.is_file():
            raise FileNotFoundError(f"Deterministic demo fixture is missing: {self.demo_fixture}")
        events = [
            json.loads(line)
            for line in self.demo_fixture.read_text(encoding="utf-8").splitlines()
            if line
        ]
        previous_seq = 0
        for fixture in events:
            seq = fixture.get("event_seq")
            if not isinstance(seq, int) or seq <= previous_seq:
                raise ValueError("Demo fixture event_seq must be strictly increasing")
            if fixture.get("confidence") is not None:
                raise ValueError("Demo fixture confidence must be null")
            try:
                ConfidenceStatus(str(fixture.get("confidence_status")))
            except ValueError as exc:
                raise ValueError("Demo fixture confidence_status is invalid") from exc
            if not isinstance(fixture.get("event_type"), str) or not isinstance(
                fixture.get("payload"), dict
            ):
                raise ValueError("Demo fixture event shape is invalid")
            previous_seq = seq
        return events

    def replay_demo_alerts(self, session_id: str) -> list[dict[str, object]]:
        if self.sessions.get(session_id) is None:
            raise KeyError(session_id)
        events = self._fixture_events()
        for fixture in events:
            self.append_demo_event(
                session_id,
                {
                    "fixture_event_type": fixture["event_type"],
                    "confidence": fixture["confidence"],
                    "confidence_status": fixture["confidence_status"],
                    "source_kind": fixture["source_kind"],
                    "payload": fixture["payload"],
                },
            )
        return self.events_after(session_id, 0)[-len(events) :]
