"""HTTP application factories and routes."""
# ruff: noqa: E501

import json
import sqlite3
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import InitVar, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pdu_exam_observer.contracts import (
    SCHEMA_VERSION,
    AnswerRequest,
    ConsentConfirmationRequest,
    DemoReplayRequest,
    EventStreamRequest,
    ExternalDeletionAttestationRequest,
    PairingRequest,
    ParticipantWithdrawalResponse,
    ReconciliationChallengeRequest,
    ReconciliationExecutionRequest,
    ResearchParticipantCreateRequest,
    ResearchSessionCreateRequest,
    ResearchStudyCreateRequest,
    ReviewerLoginRequest,
    ReviewerLoginResponse,
    ReviewerSessionResponse,
    SessionCreateResponse,
    SessionSnapshot,
)
from pdu_exam_observer.domain.state import InvalidTransition
from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.m1_r1 import M1R1Backend, ResearchStoreV3
from pdu_exam_observer.reconciliation import (
    ChallengeRejected,
    ConfirmationService,
    ReconciliationBlocked,
    ReconciliationPlanner,
)
from pdu_exam_observer.services.core import (
    IdempotencyConflict,
    M0Backend,
    ReviewerAuthenticator,
    ReviewerClockInvalid,
)


@dataclass
class AppConfig:
    reviewer_pin: InitVar[str]
    exam_origin: str
    monitor_origin: str
    allowed_hosts: tuple[str, ...]
    backend: M0Backend = field(default_factory=M0Backend)
    static_dir: Path | None = None
    reviewer_auth: ReviewerAuthenticator = field(init=False, repr=False)

    def __post_init__(self, reviewer_pin: str) -> None:
        self.reviewer_auth = ReviewerAuthenticator(reviewer_pin)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _reviewer_unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Reviewer authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _secure(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    return response


def _static_dir(config: AppConfig) -> Path:
    if config.static_dir is not None:
        return config.static_dir
    package_root = getattr(sys, "_MEIPASS", None)
    if package_root is not None:
        return Path(package_root) / "assets" / "web"
    return Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"


def _create_app(
    title: str,
    config: AppConfig,
    expected_origin: str,
    session_cookie: str | None,
    csrf_cookie: str | None,
    csrf_is_valid: Callable[[str | None, str | None], bool] | None,
    csrf_exempt_paths: frozenset[str] = frozenset(),
) -> FastAPI:
    app = FastAPI(title=title)
    app.state.backend = config.backend
    expected_host = urlsplit(expected_origin).netloc
    json_paths = {
        "/api/v1/reviewer/login",
        "/api/v1/candidate/pair",
        "/api/v1/exam/answers",
        "/api/v1/demo/replay",
        "/api/v1/events/stream",
    }

    @app.middleware("http")
    async def perimeter(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = request.headers.get("host", "")
        host_name = host.split(":", 1)[0]
        if host != expected_host or host_name not in config.allowed_hosts:
            return _secure(JSONResponse({"detail": "Host rejected"}, status_code=403))
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("origin") != expected_origin:
                return _secure(JSONResponse({"detail": "Origin rejected"}, status_code=403))
            content_length = request.headers.get("content-length")
            if (
                request.headers.get("transfer-encoding") is not None
                or content_length is None
                or not content_length.isdigit()
                or int(content_length) > 65536
            ):
                return _secure(JSONResponse({"detail": "Request body too large"}, status_code=413))
            reconciliation_json = request.url.path.startswith(
                "/api/v1/research/sessions/"
            ) and request.url.path.endswith(
                ("/challenges", "/executions", "/external-attestations")
            )
            if (
                (request.url.path in json_paths or reconciliation_json)
                and request.headers.get("content-type", "").split(";", 1)[0] != "application/json"
            ):
                return _secure(JSONResponse({"detail": "JSON content required"}, status_code=415))
            if csrf_is_valid is not None and request.url.path not in csrf_exempt_paths:
                assert session_cookie is not None
                assert csrf_cookie is not None
                session_token = request.cookies.get(session_cookie)
                if not session_token:
                    return _secure(
                        JSONResponse({"detail": "Authentication required"}, status_code=401)
                    )
                csrf = request.cookies.get(csrf_cookie)
                if (
                    not csrf
                    or request.headers.get("x-csrf-token") != csrf
                    or not csrf_is_valid(session_token, csrf)
                ):
                    return _secure(JSONResponse({"detail": "CSRF rejected"}, status_code=403))
        response = await call_next(request)
        if session_cookie is None:
            for legacy_cookie in ("reviewer_session", "pdu_monitor_csrf"):
                if legacy_cookie in request.cookies:
                    response.delete_cookie(legacy_cookie)
        return _secure(response)

    @app.get("/api/v1/health")
    async def health() -> JSONResponse:
        return JSONResponse({"schema_version": SCHEMA_VERSION, "status": "ok"})

    return app


def _set_login_cookies(
    response: Response, session_name: str, token: str, csrf_name: str, csrf: str
) -> None:
    response.set_cookie(session_name, token, httponly=True, samesite="strict")
    response.set_cookie(csrf_name, csrf, httponly=False, samesite="strict")


def _serve_shell(app: FastAPI, config: AppConfig, route: str) -> None:
    static_dir = _static_dir(config)
    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name=f"{route}-assets")

    def static_file(filename: str, media_type: str) -> FileResponse:
        path = static_dir / filename
        if not path.is_file():
            raise HTTPException(
                status_code=503,
                detail="Frontend build is unavailable; build apps/web before launching.",
            )
        return FileResponse(path, media_type=media_type)

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon_svg() -> FileResponse:
        return static_file("favicon.svg", "image/svg+xml")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon_ico() -> FileResponse:
        return static_file("favicon.ico", "image/x-icon")

    @app.get(route, include_in_schema=False)
    async def shell() -> FileResponse:
        index = static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(
                status_code=503,
                detail="Frontend build is unavailable; build apps/web before launching.",
            )
        return FileResponse(index)


def create_monitor_app(config: AppConfig) -> FastAPI:
    app = _create_app(
        "PDU Monitor Origin",
        config,
        config.monitor_origin,
        None,
        None,
        None,
    )
    _serve_shell(app, config, "/monitor")

    def require_reviewer(authorization: str | None = Header(default=None)) -> str:
        if authorization is None:
            raise _reviewer_unauthorized()
        scheme, separator, token = authorization.partition(" ")
        if (
            scheme != "Bearer"
            or separator != " "
            or not token
            or any(character.isspace() for character in token)
            or not config.backend.is_reviewer(token)
        ):
            raise _reviewer_unauthorized()
        return token

    @app.post("/api/v1/reviewer/login")
    async def reviewer_login(
        payload: ReviewerLoginRequest, request: Request
    ) -> ReviewerLoginResponse:
        client_host = request.client.host if request.client is not None else "unknown"
        result = config.reviewer_auth.authenticate(
            payload.pin,
            f"{client_host}|{request.headers.get('origin', '')}",
            config.backend.clock(),
        )
        if result.retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many PIN attempts",
                headers={"Retry-After": str(result.retry_after)},
            )
        if not result.accepted:
            raise HTTPException(status_code=401, detail="Invalid PIN")
        try:
            token = config.backend.issue_reviewer_token()
        except ReviewerClockInvalid as exc:
            raise HTTPException(
                status_code=503, detail={"code": "TECHNICAL_INSUFFICIENT"}
            ) from exc
        expiry = config.backend.reviewer_expiry(token)
        assert expiry is not None
        return ReviewerLoginResponse(
            access_token=token,
            expires_at_utc=datetime.fromtimestamp(expiry, UTC).isoformat().replace("+00:00", "Z"),
            reviewer="Nghi\u00ean c\u1ee9u vi\u00ean",
        )

    @app.get("/api/v1/reviewer/session")
    async def reviewer_session(
        reviewer_token: str = Depends(require_reviewer),
    ) -> ReviewerSessionResponse:
        expiry = config.backend.reviewer_expiry(reviewer_token)
        assert expiry is not None
        return ReviewerSessionResponse(
            expires_at_utc=datetime.fromtimestamp(expiry, UTC).isoformat().replace("+00:00", "Z"),
            reviewer="Nghi\u00ean c\u1ee9u vi\u00ean",
        )

    @app.post("/api/v1/reviewer/logout", status_code=204)
    async def reviewer_logout(
        response: Response, reviewer_token: str = Depends(require_reviewer)
    ) -> Response:
        config.backend.revoke_reviewer_token(reviewer_token)
        response.status_code = 204
        return response

    @app.post("/api/v1/sessions", status_code=201)
    async def create_session(
        _reviewer_token: str = Depends(require_reviewer),
    ) -> SessionCreateResponse:
        record, pairing_code = config.backend.create_session()
        return SessionCreateResponse(session_id=record.session_id, pairing_code=pairing_code)

    @app.get("/api/v1/events")
    async def list_events(
        session_id: str | None = None, _reviewer_token: str = Depends(require_reviewer)
    ) -> dict[str, object]:
        if session_id is None:
            raise HTTPException(status_code=422, detail="session_id is required")
        if config.backend.snapshot(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "schema_version": SCHEMA_VERSION,
            "events": config.backend.events_after(session_id, 0),
        }

    @app.post("/api/v1/events/stream")
    async def stream_events(
        payload: EventStreamRequest,
        reviewer_token: str = Depends(require_reviewer),
    ) -> StreamingResponse:
        if config.backend.snapshot(payload.session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")

        async def body() -> AsyncIterator[str]:
            async for event in config.backend.stream_reviewer_events(
                payload.session_id, payload.after_event_seq, reviewer_token
            ):
                if event is None:
                    yield ": heartbeat\n\n"
                elif event["type"] == "SessionSnapshot":
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"id: {event['event_seq']}\ndata: {json.dumps(event)}\n\n"

        return StreamingResponse(body(), media_type="text/event-stream")

    @app.post("/api/v1/demo/replay")
    async def replay_demo_alerts(
        payload: DemoReplayRequest, _reviewer_token: str = Depends(require_reviewer)
    ) -> dict[str, object]:
        try:
            events = config.backend.replay_demo_alerts(payload.session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        return {"schema_version": SCHEMA_VERSION, "events": events}

    @app.get("/api/v1/sessions/{session_id}/snapshot")
    async def reviewer_snapshot(
        session_id: str, _reviewer_token: str = Depends(require_reviewer)
    ) -> SessionSnapshot:
        snapshot = config.backend.snapshot(session_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return snapshot

    @app.post("/api/v1/sessions/{session_id}/start")
    async def reviewer_start_session(
        session_id: str, _reviewer_token: str = Depends(require_reviewer)
    ) -> SessionSnapshot:
        try:
            snapshot = config.backend.apply_session_action(session_id, "start")
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return snapshot

    @app.post("/api/v1/sessions/{session_id}/stop")
    async def reviewer_stop_session(
        session_id: str, _reviewer_token: str = Depends(require_reviewer)
    ) -> SessionSnapshot:
        try:
            snapshot = config.backend.apply_session_action(session_id, "stop")
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return snapshot

    if isinstance(config.backend, M1Backend):
        backend = config.backend

        def research_not_found() -> NoReturn:
            raise HTTPException(status_code=404, detail="Research session not found")

        def research_conflict(exc: Exception) -> HTTPException:
            return HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)},
            )

        @app.post("/api/v1/research/studies", status_code=201)
        async def create_research_study(
            payload: ResearchStudyCreateRequest,
            idempotency_key: str = Header(alias="Idempotency-Key"),
            _token: str = Depends(require_reviewer),
        ) -> dict[str, object]:
            try:
                return backend.create_study(
                    payload.study_code, idempotency_key=idempotency_key
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Study code already exists") from exc
            except IdempotencyConflict as exc:
                raise research_conflict(exc) from exc

        @app.post("/api/v1/research/participants", status_code=201)
        async def create_research_participant(
            payload: ResearchParticipantCreateRequest,
            idempotency_key: str = Header(alias="Idempotency-Key"),
            _token: str = Depends(require_reviewer),
        ) -> dict[str, object]:
            try:
                return backend.create_participant(
                    payload.study_id, idempotency_key=idempotency_key
                )
            except KeyError:
                research_not_found()
            except IdempotencyConflict as exc:
                raise research_conflict(exc) from exc

        @app.post("/api/v1/research/sessions", status_code=201)
        async def create_research_session(
            payload: ResearchSessionCreateRequest,
            idempotency_key: str = Header(alias="Idempotency-Key"),
            _token: str = Depends(require_reviewer),
        ) -> dict[str, object]:
            try:
                return backend.create_research_session(
                    payload.study_id,
                    payload.participant_id,
                    idempotency_key=idempotency_key,
                    retention_policy_reference=payload.retention_policy_reference,
                    retention_end_date=(
                        payload.retention_end_date.isoformat()
                        if payload.retention_end_date
                        else None
                    ),
                )
            except KeyError:
                research_not_found()
            except (IdempotencyConflict, InvalidTransition) as exc:
                raise research_conflict(exc) from exc

        @app.post("/api/v1/research/sessions/{session_id}/consent-confirmation")
        async def confirm_research_consent(
            session_id: str,
            payload: ConsentConfirmationRequest,
            idempotency_key: str = Header(alias="Idempotency-Key"),
            _token: str = Depends(require_reviewer),
        ) -> dict[str, object]:
            try:
                return backend.confirm_operator_consent(
                    session_id,
                    payload.consent_receipt_id,
                    payload.consent_version,
                    idempotency_key=idempotency_key,
                )
            except KeyError:
                research_not_found()
            except (IdempotencyConflict, InvalidTransition) as exc:
                raise research_conflict(exc) from exc

        @app.get("/api/v1/research/sessions/{session_id}/readiness")
        async def research_readiness(
            session_id: str, _token: str = Depends(require_reviewer)
        ) -> dict[str, object]:
            try:
                return backend.readiness(session_id)
            except KeyError:
                research_not_found()

        @app.post("/api/v1/research/sessions/{session_id}/withdrawal")
        async def withdraw_research_session(
            session_id: str,
            idempotency_key: str = Header(alias="Idempotency-Key"),
            _token: str = Depends(require_reviewer),
        ) -> ParticipantWithdrawalResponse:
            try:
                return ParticipantWithdrawalResponse.model_validate(
                    backend.withdraw(session_id, idempotency_key=idempotency_key)
                )
            except KeyError:
                research_not_found()
            except IdempotencyConflict as exc:
                raise research_conflict(exc) from exc

        @app.get("/api/v1/research/sessions/{session_id}/withdrawal-status")
        async def research_withdrawal_status(
            session_id: str, _token: str = Depends(require_reviewer)
        ) -> ParticipantWithdrawalResponse:
            try:
                return ParticipantWithdrawalResponse.model_validate(
                    backend.withdrawal_status(session_id)
                )
            except KeyError:
                research_not_found()

        @app.get("/api/v1/research/sessions/{session_id}/recovery")
        async def research_recovery(
            session_id: str, _token: str = Depends(require_reviewer)
        ) -> dict[str, object]:
            try:
                return backend.recovery(session_id)
            except KeyError:
                research_not_found()

        if isinstance(backend, M1R1Backend):
            r1_store = cast(ResearchStoreV3, backend.store)
            planner = ReconciliationPlanner(r1_store)
            confirmation = ConfirmationService(
                store=r1_store,
                planner=planner,
                authenticator=config.reviewer_auth,
                reviewer_session_digest=backend.reviewer_session_digest,
                register_reviewer_session_revocation=(
                    backend.register_reviewer_session_revocation
                ),
                clock=backend.clock,
            )

            def reconciliation_conflict(exc: Exception) -> HTTPException:
                code = str(exc).split(":", 1)[0] or "RECONCILIATION_BLOCKED"
                if code in {"CLOCK_INVALID", "MONOTONIC_CLOCK_INVALID"}:
                    return HTTPException(
                        status_code=503,
                        detail={"code": "TECHNICAL_INSUFFICIENT"},
                    )
                return HTTPException(status_code=409, detail={"code": code})

            @app.get("/api/v1/research/sessions/{session_id}/reconciliation")
            async def reconciliation_plan(
                session_id: str, _token: str = Depends(require_reviewer)
            ) -> dict[str, object]:
                try:
                    plan = planner.plan_for_session(session_id)
                    return plan.body | {"plan_sha256": plan.plan_sha256}
                except KeyError:
                    research_not_found()
                except ReconciliationBlocked as exc:
                    raise reconciliation_conflict(exc) from exc

            @app.post(
                "/api/v1/research/sessions/{session_id}/reconciliation/challenges",
                status_code=201,
            )
            async def reconciliation_challenge(
                session_id: str,
                payload: ReconciliationChallengeRequest,
                request: Request,
                reviewer_token: str = Depends(require_reviewer),
            ) -> dict[str, object]:
                client_host = request.client.host if request.client is not None else "unknown"
                try:
                    issued = confirmation.create_challenge(
                        session_id=session_id,
                        reviewer_token=reviewer_token,
                        pin=payload.pin,
                        client_key=f"{client_host}|{request.headers.get('origin', '')}",
                        action=payload.action,
                        target_id=payload.target_id,
                    )
                    return {
                        "challenge_id": issued.challenge_id,
                        "challenge_token": issued.challenge_token,
                        "action": issued.action,
                        "target_id": issued.target_id,
                        "plan_sha256": issued.plan_sha256,
                        "target_state_version": issued.target_state_version,
                        "confirmation_phrase": issued.confirmation_phrase,
                        "expires_at": issued.expires_at,
                    }
                except (ChallengeRejected, ReconciliationBlocked) as exc:
                    raise reconciliation_conflict(exc) from exc

            @app.post(
                "/api/v1/research/sessions/{session_id}/reconciliation/executions"
            )
            async def reconciliation_execution(
                session_id: str,
                _payload: ReconciliationExecutionRequest,
                _token: str = Depends(require_reviewer),
            ) -> None:
                del session_id
                raise HTTPException(
                    status_code=403,
                    detail={"code": "AUTHORITY_NOT_ISSUED"},
                )

            @app.get(
                "/api/v1/research/sessions/{session_id}/reconciliation/runs/{run_id}"
            )
            async def reconciliation_run(
                session_id: str,
                run_id: str,
                _token: str = Depends(require_reviewer),
            ) -> dict[str, object]:
                row = r1_store.connection.execute(
                    "SELECT r.id,r.state,r.failure_code,r.created_at,r.started_at,r.terminal_at "
                    "FROM reconciliation_runs r JOIN participants p ON p.id=r.participant_id "
                    "JOIN sessions s ON s.participant_id=p.id WHERE r.id=? AND s.id=?",
                    (run_id, session_id),
                ).fetchone()
                if row is None:
                    research_not_found()
                return {
                    "run_id": str(row["id"]),
                    "state": str(row["state"]),
                    "failure_code": row["failure_code"],
                    "created_at": float(row["created_at"]),
                    "started_at": row["started_at"],
                    "terminal_at": row["terminal_at"],
                }

            @app.post(
                "/api/v1/research/sessions/{session_id}/reconciliation/external-attestations"
            )
            async def reconciliation_external_attestation(
                session_id: str,
                _payload: ExternalDeletionAttestationRequest,
                _token: str = Depends(require_reviewer),
            ) -> None:
                del session_id
                raise HTTPException(
                    status_code=403,
                    detail={"code": "AUTHORITY_NOT_ISSUED"},
                )

    return app


def create_exam_app(config: AppConfig) -> FastAPI:
    app = _create_app(
        "PDU Exam Origin",
        config,
        config.exam_origin,
        "candidate_session",
        "pdu_exam_csrf",
        config.backend.has_candidate_csrf,
        frozenset({"/api/v1/candidate/pair"}),
    )
    _serve_shell(app, config, "/exam")

    @app.post("/api/v1/candidate/pair")
    async def candidate_pair(payload: PairingRequest, response: Response) -> dict[str, object]:
        pairing = config.backend.consume_pairing_code(payload.pairing_code)
        if pairing is None:
            raise HTTPException(status_code=409, detail="Pairing code is invalid or consumed")
        token, session_id = pairing
        _set_login_cookies(
            response,
            "candidate_session",
            token,
            "pdu_exam_csrf",
            config.backend.issue_candidate_csrf(token),
        )
        return {"schema_version": SCHEMA_VERSION, "session_id": session_id}

    def require_candidate(candidate_session: str | None = Cookie(default=None)) -> str:
        session_id = config.backend.candidate_session(candidate_session)
        if session_id is None:
            raise HTTPException(status_code=401, detail="Candidate authentication required")
        return session_id

    def candidate_snapshot(session_id: str, candidate_session: str | None) -> SessionSnapshot:
        if require_candidate(candidate_session) != session_id:
            raise _forbidden("Candidate is not paired to this session")
        snapshot = config.backend.snapshot(session_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return snapshot

    async def act(
        session_id: str, action: str, candidate_session: str | None = Cookie(default=None)
    ) -> SessionSnapshot:
        candidate_snapshot(session_id, candidate_session)
        try:
            snapshot = config.backend.apply_session_action(session_id, action)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return snapshot

    @app.post("/api/v1/sessions/{session_id}/consent")
    async def confirm_consent(
        session_id: str, candidate_session: str | None = Cookie(default=None)
    ) -> SessionSnapshot:
        return await act(session_id, "consent", candidate_session)

    @app.post("/api/v1/sessions/{session_id}/preflight")
    async def complete_preflight(
        session_id: str, candidate_session: str | None = Cookie(default=None)
    ) -> SessionSnapshot:
        return await act(session_id, "preflight", candidate_session)

    @app.get("/api/v1/exam/status")
    async def exam_status(
        candidate_session: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        session_id = require_candidate(candidate_session)
        snapshot = config.backend.snapshot(session_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "schema_version": SCHEMA_VERSION,
            "session_id": snapshot.session_id,
            "state": snapshot.state,
            "submitted": snapshot.submitted,
            "duration_seconds": snapshot.duration_seconds,
            "remaining_seconds": snapshot.remaining_seconds,
            "started_at_utc": snapshot.started_at_utc,
        }

    @app.post("/api/v1/exam/answers")
    async def save_answer(
        payload: AnswerRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        candidate_session: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        session_id = require_candidate(candidate_session)
        try:
            return config.backend.record_answer(
                session_id, idempotency_key or payload.answer_id, payload.model_dump(mode="json")
            )
        except IdempotencyConflict as exc:
            raise HTTPException(
                status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)}
            ) from exc
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/exam/submit")
    async def submit_exam(
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        candidate_session: str | None = Cookie(default=None),
    ) -> dict[str, object]:
        session_id = require_candidate(candidate_session)
        try:
            return config.backend.submit_exam(session_id, idempotency_key or "submit")
        except IdempotencyConflict as exc:
            raise HTTPException(
                status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)}
            ) from exc
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app
