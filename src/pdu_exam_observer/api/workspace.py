"""Reviewer-only research workspace; paths and authority never come from HTTP."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import BinaryIO, Literal, Protocol

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field


class WorkspacePort(Protocol):
    def summary(self) -> dict[str, object]: ...
    def create(self, source_kind: str, key: str) -> dict[str, object]: ...
    def detail(self, session_id: str) -> dict[str, object]: ...
    def action(self, session_id: str, action: str, key: str) -> dict[str, object]: ...
    def decide(
        self, session_id: str, payload: dict[str, object], key: str
    ) -> dict[str, object]: ...
    def export(self, session_id: str) -> bytes: ...
    def preview(self, session_id: str) -> Path: ...
    def import_model(self, payload: bytes, key: str) -> dict[str, object]: ...
    def close(self) -> None: ...
    def focus(self, exam_session_id: str, focused: bool) -> None: ...


class FocusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    focused: bool


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_kind: Literal["AI_RENDERED", "REAL"] = "AI_RENDERED"


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event_id: str = Field(default="", max_length=80)
    label: Literal[
        "NORMAL",
        "BENIGN_CONFOUNDER",
        "PROLONGED_HEAD_DOWN",
        "PROLONGED_SIDE_LOOK",
        "NO_PERSON",
        "MULTIPLE_PEOPLE",
        "UNCERTAIN",
    ]
    review_status: Literal["CONFIRMED", "REJECTED", "UNCERTAIN"]
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)
    expected_revision: int = Field(ge=0)


def register_workspace_routes(
    app: FastAPI,
    service: WorkspacePort,
    require_reviewer: Callable[..., str],
) -> None:
    router = APIRouter(prefix="/api/v1/workspace", dependencies=[Depends(require_reviewer)])

    def key(value: str | None) -> str:
        if value is None or not 8 <= len(value) <= 128 or not value.isascii():
            raise HTTPException(422, detail="IDEMPOTENCY_KEY_REQUIRED")
        return value

    def invoke(operation: Callable[[], dict[str, object]]) -> dict[str, object]:
        try:
            return operation()
        except KeyError as exc:
            raise HTTPException(404, detail="WORKSPACE_RECORD_NOT_FOUND") from exc
        except (ValueError, RuntimeError, OSError) as exc:
            # Native exceptions can include sensitive absolute paths; never reflect them.
            code = str(exc)
            if (
                not code
                or len(code) > 80
                or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in code)
            ):
                code = "TECHNICAL_INSUFFICIENT"
            raise HTTPException(409, detail=code) from exc

    @router.get("")
    def summary() -> dict[str, object]:
        return invoke(service.summary)

    @router.post("/sessions", status_code=201)
    def create(
        payload: CreateRequest, idempotency_key: str | None = Header(default=None)
    ) -> dict[str, object]:
        request_key = key(idempotency_key)
        return invoke(lambda: service.create(payload.source_kind, request_key))

    @router.get("/sessions/{session_id}")
    def detail(session_id: str) -> dict[str, object]:
        return invoke(lambda: service.detail(session_id))

    @router.post("/sessions/{session_id}/{action}")
    def action(
        session_id: str,
        action: Literal[
            "preflight",
            "start",
            "stop",
            "seal",
            "lock",
            "withdraw-test",
            "withdraw",
            "mark-contamination",
        ],
        idempotency_key: str | None = Header(default=None),
    ) -> dict[str, object]:
        request_key = key(idempotency_key)
        return invoke(lambda: service.action(session_id, action, request_key))

    # A distinct suffix avoids the generic action route above.
    @router.put("/sessions/{session_id}/decision")
    def decision(
        session_id: str,
        payload: DecisionRequest,
        idempotency_key: str | None = Header(default=None),
    ) -> dict[str, object]:
        request_key = key(idempotency_key)
        return invoke(lambda: service.decide(session_id, payload.model_dump(), request_key))

    @router.get("/sessions/{session_id}/export")
    def export(session_id: str) -> Response:
        result: list[bytes] = []

        def collect_export() -> dict[str, object]:
            result.append(service.export(session_id))
            return {}

        invoke(collect_export)
        return Response(
            result[0],
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="pdu-pose-export.zip"',
                "Cache-Control": "no-store",
            },
        )

    @router.get("/sessions/{session_id}/preview")
    def preview(session_id: str) -> Response:
        opener = getattr(service, "open_preview", None)
        if callable(opener):
            handles: list[BinaryIO] = []

            def open_verified() -> dict[str, object]:
                handles.append(opener(session_id))
                return {}

            invoke(open_verified)

            def chunks() -> Iterator[bytes]:
                with handles[0] as handle:
                    while chunk := handle.read(1024 * 1024):
                        yield chunk

            return StreamingResponse(
                chunks(), media_type="video/mp4", headers={"Cache-Control": "no-store"}
            )
        paths: list[Path] = []

        def collect_preview() -> dict[str, object]:
            paths.append(service.preview(session_id))
            return {}

        invoke(collect_preview)
        return FileResponse(paths[0], media_type="video/mp4", headers={"Cache-Control": "no-store"})

    @router.post("/models/import")
    async def import_model(
        request: Request, idempotency_key: str | None = Header(default=None)
    ) -> dict[str, object]:
        request_key = key(idempotency_key)
        if request.headers.get("content-type", "").split(";")[0] != "application/zip":
            raise HTTPException(415, detail="MODEL_ZIP_REQUIRED")
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 64 * 1024 * 1024:
                raise HTTPException(413, detail="MODEL_BUNDLE_TOO_LARGE")
        return invoke(lambda: service.import_model(bytes(payload), request_key))

    app.include_router(router)
