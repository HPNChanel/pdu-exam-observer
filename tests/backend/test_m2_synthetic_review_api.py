from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app
from pdu_exam_observer.m2_synthetic_evidence import SyntheticEvidenceExport
from pdu_exam_observer.m2_synthetic_review import (
    SyntheticReviewJobStatus,
    SyntheticReviewRunKind,
    SyntheticReviewRunRecord,
    SyntheticReviewServiceError,
    SyntheticReviewServiceFailureCode,
)


@dataclass
class _Service:
    record: SyntheticReviewRunRecord
    export_error: SyntheticReviewServiceFailureCode | None = None

    def submit(
        self, run_kind: SyntheticReviewRunKind, *, idempotency_key: str
    ) -> SyntheticReviewRunRecord:
        if idempotency_key == "conflict-key-0001":
            raise SyntheticReviewServiceError(SyntheticReviewServiceFailureCode.RUN_ALREADY_ACTIVE)
        if idempotency_key == "capacity-key-0001":
            raise SyntheticReviewServiceError(SyntheticReviewServiceFailureCode.CAPACITY_EXHAUSTED)
        if idempotency_key == "unexpected-key-01":
            raise RuntimeError("D:/private/path must never escape")
        assert run_kind is self.record.run_kind
        return self.record

    def list(self) -> tuple[SyntheticReviewRunRecord, ...]:
        return (self.record,)

    def get(self, request_id: str) -> SyntheticReviewRunRecord:
        if request_id != self.record.request_id:
            raise KeyError(request_id)
        return self.record

    def export_evidence(self, request_id: str) -> SyntheticEvidenceExport:
        if request_id != self.record.request_id:
            raise KeyError(request_id)
        if self.export_error is not None:
            raise SyntheticReviewServiceError(self.export_error)
        payload = b'{"artifact_kind":"M2_SYNTHETIC_EVIDENCE_BUNDLE"}\n'
        return SyntheticEvidenceExport(
            payload=payload,
            sha256="a" * 64,
            filename=f"m2-s2d-{request_id}.json",
        )


def _record() -> SyntheticReviewRunRecord:
    return SyntheticReviewRunRecord(
        schema_version=1,
        request_id="synrun-0123456789abcdef0123456789abcdef",
        run_sequence=1,
        run_kind=SyntheticReviewRunKind.PREFLIGHT_60S,
        job_status=SyntheticReviewJobStatus.QUEUED,
        service_failure_code=None,
        receipt=None,
    )


def _clients(service: object | None) -> tuple[TestClient, TestClient, str]:
    config = AppConfig(
        reviewer_pin="123456",
        exam_origin="http://exam.local",
        monitor_origin="http://monitor.local",
        allowed_hosts=("exam.local", "monitor.local"),
        synthetic_review_service=service,  # type: ignore[arg-type]
    )
    exam = TestClient(create_exam_app(config), base_url=config.exam_origin)
    monitor = TestClient(create_monitor_app(config), base_url=config.monitor_origin)
    login = monitor.post(
        "/api/v1/reviewer/login", json={"pin": "123456"}, headers={"Origin": config.monitor_origin}
    )
    return exam, monitor, str(login.json()["access_token"])


def _headers(token: str, key: str = "request-key-000001") -> dict[str, str]:
    return {
        "Origin": "http://monitor.local",
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": key,
    }


def test_routes_are_monitor_only_optional_and_reviewer_authenticated() -> None:
    exam, monitor, token = _clients(_Service(_record()))
    assert exam.get("/api/v1/synthetic-runs").status_code == 404
    assert monitor.get("/api/v1/synthetic-runs").status_code == 401
    assert (
        monitor.get(
            "/api/v1/synthetic-runs", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )
    _, absent, _ = _clients(None)
    assert (
        absent.get(
            "/api/v1/synthetic-runs", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 404
    )


def test_post_accepts_only_run_kind_and_required_idempotency_key() -> None:
    _, monitor, token = _clients(_Service(_record()))
    accepted = monitor.post(
        "/api/v1/synthetic-runs", json={"run_kind": "PREFLIGHT_60S"}, headers=_headers(token)
    )
    missing_key = monitor.post(
        "/api/v1/synthetic-runs",
        json={"run_kind": "PREFLIGHT_60S"},
        headers={"Origin": "http://monitor.local", "Authorization": f"Bearer {token}"},
    )
    extra = monitor.post(
        "/api/v1/synthetic-runs",
        json={"run_kind": "PREFLIGHT_60S", "path": "C:/camera"},
        headers=_headers(token),
    )
    assert accepted.status_code == 202
    assert accepted.json() == {
        **_authority_envelope(),
        "run": _record().as_dict(),
    }
    for response in (missing_key, extra):
        assert response.status_code == 422
        assert response.json() == {
            "code": "REQUEST_INVALID",
            "message": "Synthetic review request is invalid.",
        }


def test_list_and_get_return_closed_authority_envelopes() -> None:
    _, monitor, token = _clients(_Service(_record()))
    listed = monitor.get("/api/v1/synthetic-runs", headers={"Authorization": f"Bearer {token}"})
    fetched = monitor.get(
        f"/api/v1/synthetic-runs/{_record().request_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.json() == {**_authority_envelope(), "runs": [_record().as_dict()]}
    assert fetched.json() == {**_authority_envelope(), "run": _record().as_dict()}


def test_unknown_request_is_404_without_path_or_exception_disclosure() -> None:
    _, monitor, token = _clients(_Service(_record()))
    response = monitor.get(
        "/api/v1/synthetic-runs/synrun-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json() == {
        "code": "SYNTHETIC_RUN_NOT_FOUND",
        "message": "Synthetic review run was not found.",
    }
    assert "\\" not in response.text and ":/" not in response.text


def test_service_conflicts_map_to_bounded_http_errors() -> None:
    _, monitor, token = _clients(_Service(_record()))
    response = monitor.post(
        "/api/v1/synthetic-runs",
        json={"run_kind": "PREFLIGHT_60S"},
        headers=_headers(token, "conflict-key-0001"),
    )
    assert response.status_code == 409
    assert response.json() == {
        "code": "SYNTHETIC_RUN_ALREADY_ACTIVE",
        "message": "A synthetic review run is already active.",
    }
    capacity = monitor.post(
        "/api/v1/synthetic-runs",
        json={"run_kind": "PREFLIGHT_60S"},
        headers=_headers(token, "capacity-key-0001"),
    )
    assert capacity.status_code == 503
    assert capacity.json() == {
        "code": "CAPACITY_EXHAUSTED",
        "message": "Synthetic review service is unavailable.",
    }
    unexpected = monitor.post(
        "/api/v1/synthetic-runs",
        json={"run_kind": "PREFLIGHT_60S"},
        headers=_headers(token, "unexpected-key-01"),
    )
    assert unexpected.status_code == 500
    assert unexpected.json() == {
        "code": "UNEXPECTED_FAILURE",
        "message": "Synthetic review request failed.",
    }
    assert "private" not in unexpected.text.lower()


def test_api_rejects_query_mutation_and_noncanonical_request_ids() -> None:
    _, monitor, token = _clients(_Service(_record()))
    for response in (
        monitor.get(
            "/api/v1/synthetic-runs?path=C:/camera", headers={"Authorization": f"Bearer {token}"}
        ),
        monitor.get(
            "/api/v1/synthetic-runs/not-a-request", headers={"Authorization": f"Bearer {token}"}
        ),
    ):
        assert response.status_code == 422
        assert response.json() == {
            "code": "REQUEST_INVALID",
            "message": "Synthetic review request is invalid.",
        }


def test_api_payload_never_contains_bearer_idempotency_or_device_fields() -> None:
    _, monitor, token = _clients(_Service(_record()))
    response = monitor.post(
        "/api/v1/synthetic-runs", json={"run_kind": "PREFLIGHT_60S"}, headers=_headers(token)
    )
    text = response.text.lower()
    for forbidden in (
        token.lower(),
        "request-key",
        "camera_id",
        "device_id",
        "participant_id",
        "session_id",
        "local_path",
    ):
        assert forbidden not in text


def _authority_envelope() -> dict[str, object]:
    return {
        "schema_version": 1,
        "capability_status": "SYNTHETIC_REVIEW_ONLY",
        "evidence_kind": "SIMULATED",
        "package_contains_integration": False,
        "production_reconciler_implemented": False,
        "production_reconciler_real_storage_verified": False,
        "real_data_deletion_authorized": False,
        "execution_authorized": False,
        "physical_camera_access_authorized": False,
        "device_gate_decision": "UNVERIFIED",
        "d1_go": False,
        "participant_collection_authorized": False,
        "research_ready": False,
        "collection_authorized": False,
        "authority_status": "AUTHORITY_NOT_ISSUED",
    }


def test_evidence_download_is_authenticated_monitor_only_with_bounded_headers() -> None:
    service = _Service(_record())
    exam, monitor, token = _clients(service)
    path = f"/api/v1/synthetic-runs/{_record().request_id}/evidence"
    assert exam.get(path).status_code == 404
    assert monitor.get(path).status_code == 401
    response = monitor.get(path, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.content == service.export_evidence(_record().request_id).payload
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="m2-s2d-{_record().request_id}.json"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-pdu-evidence-sha256"] == "a" * 64


def test_evidence_download_maps_not_exportable_integrity_and_invalid_requests() -> None:
    path = f"/api/v1/synthetic-runs/{_record().request_id}/evidence"
    for failure, status_code, code in (
        (
            SyntheticReviewServiceFailureCode.EVIDENCE_NOT_EXPORTABLE,
            409,
            "SYNTHETIC_EVIDENCE_NOT_EXPORTABLE",
        ),
        (
            SyntheticReviewServiceFailureCode.EVIDENCE_INTEGRITY_FAILED,
            500,
            "SYNTHETIC_EVIDENCE_INTEGRITY_FAILED",
        ),
    ):
        _, monitor, token = _clients(_Service(_record(), failure))
        response = monitor.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == status_code
        assert response.json()["code"] == code
        assert set(response.json()) == {"code", "message"}
    _, monitor, token = _clients(_Service(_record()))
    for response in (
        monitor.get(
            f"{path}?path=C:/private", headers={"Authorization": f"Bearer {token}"}
        ),
        monitor.get(
            "/api/v1/synthetic-runs/not-a-request/evidence",
            headers={"Authorization": f"Bearer {token}"},
        ),
    ):
        assert response.status_code == 422
        assert response.json()["code"] == "REQUEST_INVALID"


def test_evidence_download_is_byte_identical_and_never_discloses_request_secrets() -> None:
    _, monitor, token = _clients(_Service(_record()))
    path = f"/api/v1/synthetic-runs/{_record().request_id}/evidence"
    first = monitor.get(path, headers={"Authorization": f"Bearer {token}"})
    second = monitor.get(path, headers={"Authorization": f"Bearer {token}"})
    assert first.content == second.content
    text = first.text.lower()
    for forbidden in (token.lower(), "idempotency", "session_id", "participant_id", "local_path"):
        assert forbidden not in text
