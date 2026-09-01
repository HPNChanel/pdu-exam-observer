from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from pdu_exam_observer.m2_synthetic_integration import SyntheticIntegrationReceipt
from pdu_exam_observer.m2_synthetic_review import (
    SyntheticReviewJobStatus,
    SyntheticReviewRunKind,
    SyntheticReviewService,
    SyntheticReviewServiceError,
    SyntheticReviewServiceFailureCode,
)


@dataclass(frozen=True)
class _Receipt:
    outcome: str = "BACKEND_CONTRACT_PASS"

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "integration_status": "PERSISTED",
            "evidence_kind": "SIMULATED",
            "d1_outcome": self.outcome,
            "device_gate_decision": "UNVERIFIED",
            "d1_go": False,
            "authority_status": "AUTHORITY_NOT_ISSUED",
            "physical_camera_access_authorized": False,
            "participant_collection_authorized": False,
            "collection_authorized": False,
            "package_contains_integration": False,
        }


def _receipt(outcome: str = "BACKEND_CONTRACT_PASS") -> SyntheticIntegrationReceipt:
    return cast(SyntheticIntegrationReceipt, _Receipt(outcome))


def _wait(service: SyntheticReviewService, request_id: str) -> object:
    for _ in range(200):
        record = service.get(request_id)
        if record.job_status is SyntheticReviewJobStatus.TERMINAL:
            return record
        time.sleep(0.005)
    raise AssertionError("synthetic review worker did not terminate")


def test_service_assigns_deterministic_opaque_ids_and_newest_first_records() -> None:
    service = SyntheticReviewService._for_tests(lambda: _receipt(), lambda: _receipt())
    try:
        first = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="review-key-00000001"
        )
        _wait(service, first.request_id)
        second = service.submit(
            SyntheticReviewRunKind.NOMINAL_20M, idempotency_key="review-key-00000002"
        )
        _wait(service, second.request_id)
        assert first.request_id.startswith("synrun-") and len(first.request_id) == 39
        assert [item.run_sequence for item in service.list()] == [2, 1]
        assert "review-key" not in str(service.list())
    finally:
        service.close()


def test_service_replays_same_intent_and_rejects_changed_run_kind() -> None:
    service = SyntheticReviewService._for_tests(lambda: _receipt(), lambda: _receipt())
    try:
        first = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="same-key-000000001"
        )
        replay = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="same-key-000000001"
        )
        assert replay.request_id == first.request_id
        with pytest.raises(SyntheticReviewServiceError) as raised:
            service.submit(SyntheticReviewRunKind.NOMINAL_20M, idempotency_key="same-key-000000001")
        assert raised.value.code is SyntheticReviewServiceFailureCode.IDEMPOTENCY_CONFLICT
    finally:
        service.close()


def test_service_is_single_flight_without_a_queue() -> None:
    entered, release = threading.Event(), threading.Event()

    def blocked() -> SyntheticIntegrationReceipt:
        entered.set()
        release.wait(timeout=2)
        return _receipt()

    service = SyntheticReviewService._for_tests(blocked, lambda: _receipt())
    try:
        first = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="active-key-00000001"
        )
        assert entered.wait(timeout=1)
        with pytest.raises(SyntheticReviewServiceError) as raised:
            service.submit(
                SyntheticReviewRunKind.NOMINAL_20M, idempotency_key="other-key-000000002"
            )
        assert raised.value.code is SyntheticReviewServiceFailureCode.RUN_ALREADY_ACTIVE
        release.set()
        _wait(service, first.request_id)
    finally:
        release.set()
        service.close()


def test_service_enforces_closed_idempotency_key_and_capacity() -> None:
    service = SyntheticReviewService._for_tests(
        lambda: _receipt(), lambda: _receipt(), max_records=2
    )
    try:
        with pytest.raises(SyntheticReviewServiceError):
            service.submit(SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="short")
        for index in range(2):
            item = service.submit(
                SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key=f"capacity-key-{index:08d}"
            )
            _wait(service, item.request_id)
        with pytest.raises(SyntheticReviewServiceError) as raised:
            service.submit(
                SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="capacity-key-99999999"
            )
        assert raised.value.code is SyntheticReviewServiceFailureCode.CAPACITY_EXHAUSTED
    finally:
        service.close()


def test_service_publishes_only_terminal_core_receipts() -> None:
    service = SyntheticReviewService._for_tests(lambda: _receipt(), lambda: _receipt("NO_GO"))
    try:
        queued = service.submit(
            SyntheticReviewRunKind.NOMINAL_20M, idempotency_key="terminal-key-000001"
        )
        terminal = _wait(service, queued.request_id)
        assert terminal.job_status is SyntheticReviewJobStatus.TERMINAL
        assert terminal.service_failure_code is None
        assert terminal.receipt is not None
        assert terminal.as_dict()["receipt"]["d1_outcome"] == "NO_GO"  # type: ignore[index]
    finally:
        service.close()


def test_service_sanitizes_worker_exceptions_without_false_receipt() -> None:
    def broken() -> SyntheticIntegrationReceipt:
        raise RuntimeError("C:\\private\\operator\\secret")

    service = SyntheticReviewService._for_tests(broken, broken)
    try:
        queued = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="failure-key-0000001"
        )
        terminal = _wait(service, queued.request_id)
        payload = terminal.as_dict()
        assert payload["service_failure_code"] == "UNEXPECTED_FAILURE"
        assert payload["receipt"] is None
        assert "private" not in str(payload)
    finally:
        service.close()


def test_service_close_is_idempotent_rejects_new_work_and_cleans_owned_root() -> None:
    service = SyntheticReviewService.create_owned()
    root = service._owned_root_for_test()
    assert root.is_dir()
    service.close()
    service.close()
    assert not root.exists()
    with pytest.raises(SyntheticReviewServiceError) as raised:
        service.submit(SyntheticReviewRunKind.PREFLIGHT_60S, idempotency_key="closed-key-00000001")
    assert raised.value.code is SyntheticReviewServiceFailureCode.SERVICE_CLOSED


def test_owned_service_never_uses_an_external_operational_root(tmp_path: Path) -> None:
    sentinel = tmp_path / "operational-root"
    sentinel.mkdir()
    marker = sentinel / "do-not-touch.txt"
    marker.write_text("unchanged", encoding="utf-8")
    service = SyntheticReviewService.create_owned()
    try:
        assert service._owned_root_for_test() != sentinel
        assert marker.read_text(encoding="utf-8") == "unchanged"
        first = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S,
            idempotency_key="owned-run-key-000001",
        )
        first_terminal = _wait(service, first.request_id)
        second = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S,
            idempotency_key="owned-run-key-000002",
        )
        second_terminal = _wait(service, second.request_id)
        assert first_terminal.receipt is not None
        assert second_terminal.receipt is not None
        assert first_terminal.receipt.artifact_id != second_terminal.receipt.artifact_id
    finally:
        service.close()


def test_service_exports_terminal_persisted_evidence_without_rerunning_core() -> None:
    service = SyntheticReviewService.create_owned()
    try:
        queued = service.submit(
            SyntheticReviewRunKind.PREFLIGHT_60S,
            idempotency_key="evidence-export-key-0001",
        )
        terminal = _wait(service, queued.request_id)
        before = service.list()
        first = service.export_evidence(queued.request_id)
        second = service.export_evidence(queued.request_id)
        assert terminal.receipt is not None
        assert first == second
        assert first.filename == f"m2-s2d-{queued.request_id}.json"
        assert service.list() == before
        assert b"M2_SYNTHETIC_EVIDENCE_BUNDLE" in first.payload
    finally:
        service.close()


def test_service_rejects_unknown_nonterminal_and_closed_evidence_requests() -> None:
    entered, release = threading.Event(), threading.Event()

    def blocked() -> SyntheticIntegrationReceipt:
        entered.set()
        release.wait(timeout=2)
        return _receipt()

    service = SyntheticReviewService._for_tests(blocked, blocked)
    queued = service.submit(
        SyntheticReviewRunKind.PREFLIGHT_60S,
        idempotency_key="evidence-blocked-key-01",
    )
    assert entered.wait(timeout=1)
    with pytest.raises(SyntheticReviewServiceError) as nonterminal:
        service.export_evidence(queued.request_id)
    assert nonterminal.value.code is SyntheticReviewServiceFailureCode.EVIDENCE_NOT_EXPORTABLE
    with pytest.raises(KeyError):
        service.export_evidence("synrun-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    release.set()
    _wait(service, queued.request_id)
    service.close()
    with pytest.raises(SyntheticReviewServiceError) as closed:
        service.export_evidence(queued.request_id)
    assert closed.value.code is SyntheticReviewServiceFailureCode.SERVICE_CLOSED
