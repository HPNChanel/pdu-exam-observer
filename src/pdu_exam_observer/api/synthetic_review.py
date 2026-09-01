"""Authenticated monitor-only routes for bounded synthetic M2 review."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from fastapi import Depends, FastAPI, Header, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from pdu_exam_observer.m2_synthetic_evidence import SyntheticEvidenceExport
from pdu_exam_observer.m2_synthetic_review import (
    SyntheticReviewRunKind,
    SyntheticReviewRunRecord,
    SyntheticReviewServiceError,
    SyntheticReviewServiceFailureCode,
)

_REQUEST_ID = re.compile(r"synrun-[0-9a-f]{32}\Z")
_KEY = re.compile(r"[A-Za-z0-9._-]{16,128}\Z")


class SyntheticReviewServiceLike(Protocol):
    def submit(
        self, run_kind: SyntheticReviewRunKind, *, idempotency_key: str
    ) -> SyntheticReviewRunRecord: ...

    def list(self) -> tuple[SyntheticReviewRunRecord, ...]: ...

    def get(self, request_id: str) -> SyntheticReviewRunRecord: ...

    def export_evidence(self, request_id: str) -> SyntheticEvidenceExport: ...


class SyntheticRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_kind: SyntheticReviewRunKind


_AUTHORITY: dict[str, object] = {
    "capability_status": "SYNTHETIC_REVIEW_ONLY",
    "authority_status": "AUTHORITY_NOT_ISSUED",
    "collection_authorized": False,
    "d1_go": False,
    "device_gate_decision": "UNVERIFIED",
    "evidence_kind": "SIMULATED",
    "execution_authorized": False,
    "package_contains_integration": False,
    "participant_collection_authorized": False,
    "physical_camera_access_authorized": False,
    "production_reconciler_implemented": False,
    "production_reconciler_real_storage_verified": False,
    "real_data_deletion_authorized": False,
    "research_ready": False,
    "schema_version": 1,
}


def _record_envelope(record: SyntheticReviewRunRecord) -> dict[str, object]:
    return {**_AUTHORITY, "run": record.as_dict()}


def _error(http_status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=http_status, content={"code": code, "message": message})


def _request_invalid() -> JSONResponse:
    return _error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "REQUEST_INVALID",
        "Synthetic review request is invalid.",
    )


def _service_error(exc: SyntheticReviewServiceError) -> JSONResponse:
    code = exc.code
    if code is SyntheticReviewServiceFailureCode.RUN_ALREADY_ACTIVE:
        return _error(
            status.HTTP_409_CONFLICT,
            "SYNTHETIC_RUN_ALREADY_ACTIVE",
            "A synthetic review run is already active.",
        )
    if code is SyntheticReviewServiceFailureCode.IDEMPOTENCY_CONFLICT:
        return _error(
            status.HTTP_409_CONFLICT,
            code.value,
            "The idempotency key conflicts with an existing request.",
        )
    if code is SyntheticReviewServiceFailureCode.EVIDENCE_NOT_EXPORTABLE:
        return _error(
            status.HTTP_409_CONFLICT,
            "SYNTHETIC_EVIDENCE_NOT_EXPORTABLE",
            "Synthetic evidence is not exportable for this run.",
        )
    if code is SyntheticReviewServiceFailureCode.EVIDENCE_INTEGRITY_FAILED:
        return _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "SYNTHETIC_EVIDENCE_INTEGRITY_FAILED",
            "Synthetic evidence integrity verification failed.",
        )
    return _error(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        code.value,
        "Synthetic review service is unavailable.",
    )


def register_synthetic_review_routes(
    app: FastAPI,
    service: SyntheticReviewServiceLike,
    require_reviewer: Callable[..., str],
) -> None:
    @app.exception_handler(RequestValidationError)
    async def synthetic_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if request.url.path.startswith("/api/v1/synthetic-runs"):
            return _request_invalid()
        return await request_validation_exception_handler(request, exc)

    @app.post(
        "/api/v1/synthetic-runs",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=None,
    )
    async def submit_synthetic_run(
        payload: SyntheticRunRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
        _reviewer: str = Depends(require_reviewer),
    ) -> dict[str, object] | JSONResponse:
        if request.query_params:
            return _request_invalid()
        if not _KEY.fullmatch(idempotency_key):
            return _request_invalid()
        try:
            return _record_envelope(
                service.submit(payload.run_kind, idempotency_key=idempotency_key)
            )
        except SyntheticReviewServiceError as exc:
            return _service_error(exc)
        except Exception:
            return _error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "UNEXPECTED_FAILURE",
                "Synthetic review request failed.",
            )

    @app.get("/api/v1/synthetic-runs", response_model=None)
    async def list_synthetic_runs(
        request: Request,
        _reviewer: str = Depends(require_reviewer),
    ) -> dict[str, object] | JSONResponse:
        if request.query_params:
            return _request_invalid()
        try:
            return {**_AUTHORITY, "runs": [record.as_dict() for record in service.list()]}
        except SyntheticReviewServiceError as exc:
            return _service_error(exc)
        except Exception:
            return _error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "UNEXPECTED_FAILURE",
                "Synthetic review request failed.",
            )

    @app.get("/api/v1/synthetic-runs/{request_id}", response_model=None)
    async def get_synthetic_run(
        request_id: str,
        request: Request,
        _reviewer: str = Depends(require_reviewer),
    ) -> dict[str, object] | JSONResponse:
        if request.query_params:
            return _request_invalid()
        if not _REQUEST_ID.fullmatch(request_id):
            return _request_invalid()
        try:
            return _record_envelope(service.get(request_id))
        except KeyError:
            return _error(
                status.HTTP_404_NOT_FOUND,
                "SYNTHETIC_RUN_NOT_FOUND",
                "Synthetic review run was not found.",
            )
        except SyntheticReviewServiceError as exc:
            return _service_error(exc)
        except Exception:
            return _error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "UNEXPECTED_FAILURE",
                "Synthetic review request failed.",
            )

    @app.get("/api/v1/synthetic-runs/{request_id}/evidence", response_model=None)
    async def download_synthetic_evidence(
        request_id: str,
        request: Request,
        _reviewer: str = Depends(require_reviewer),
    ) -> Response:
        if request.query_params or not _REQUEST_ID.fullmatch(request_id):
            return _request_invalid()
        try:
            exported = service.export_evidence(request_id)
            payload = exported.payload
            digest = exported.sha256
            filename = exported.filename
            return Response(
                content=payload,
                status_code=status.HTTP_200_OK,
                headers={
                    "Cache-Control": "no-store",
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": "application/json",
                    "X-Content-Type-Options": "nosniff",
                    "X-PDU-Evidence-SHA256": digest,
                },
            )
        except KeyError:
            return _error(
                status.HTTP_404_NOT_FOUND,
                "SYNTHETIC_RUN_NOT_FOUND",
                "Synthetic review run was not found.",
            )
        except SyntheticReviewServiceError as exc:
            return _service_error(exc)
        except Exception:
            return _error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "UNEXPECTED_FAILURE",
                "Synthetic evidence request failed.",
            )
