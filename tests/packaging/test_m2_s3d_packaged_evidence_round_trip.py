from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from pdu_exam_observer.m2_packaged_reproduction import (
    PackagedReproductionFailureCode,
    execute_packaged_reproduction,
)
from pdu_exam_observer.m2_synthetic_environment import BOUND_SOURCE_RELATIVE_PATHS
from scripts import build_m2_s3d_candidate as builder
from scripts import run_m2_s3d_packaged_round_trip as round_trip

ROOT = Path(__file__).parents[2]
RECEIPT = ROOT / "docs" / "ai" / "M2_S3D_PACKAGED_EVIDENCE_ROUND_TRIP.json"
S3B_RECEIPT = ROOT / "docs" / "ai" / "M2_S3B_PACKAGE_INTEGRATION.json"
S3C_RECEIPT = ROOT / "docs" / "ai" / "M2_S3C_PACKAGED_SYNTHETIC_SMOKE.json"


def _canonical(document: object) -> bytes:
    return (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def test_packaged_reproduction_is_stdin_only_and_bounded() -> None:
    assert round_trip.REPRODUCTION_RUNTIME_MODE == "m2synthetic-reproduce"
    assert round_trip.MAX_EVIDENCE_BYTES == 4_000_000
    assert execute_packaged_reproduction(b"")["failure_code"] == "INPUT_INVALID"
    oversized = execute_packaged_reproduction(b" " * 4_000_001)
    assert oversized["failure_code"] == "SOURCE_EVIDENCE_REJECTED"
    assert PackagedReproductionFailureCode.REQUEST_INVALID.value == "REQUEST_INVALID"


def test_main_dispatches_reproduction_without_starting_http() -> None:
    environment = dict(os.environ)
    environment["PDU_RUNTIME_MODE"] = "m2synthetic-reproduce"
    completed = subprocess.run(
        [sys.executable, "-m", "pdu_exam_observer"],
        cwd=ROOT,
        env=environment,
        input=b"",
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 2
    assert completed.stderr == b""
    document = json.loads(completed.stdout)
    assert document["classification"] == "REPRODUCTION_FAILED"
    assert document["failure_code"] == "INPUT_INVALID"


def test_environment_binding_covers_reproduction_and_dispatch() -> None:
    required = {
        "src/pdu_exam_observer/__main__.py",
        "src/pdu_exam_observer/m2_packaged_reproduction.py",
        "src/pdu_exam_observer/m2_synthetic_reproduction.py",
    }
    assert required <= set(BOUND_SOURCE_RELATIVE_PATHS)
    assert len(BOUND_SOURCE_RELATIVE_PATHS) == len(set(BOUND_SOURCE_RELATIVE_PATHS))


def test_s3d_builder_uses_a_new_candidate_lineage_and_fixed_contract() -> None:
    assert builder.CANDIDATE_ROOT.name == "m2-s3d-round-trip"
    assert builder.CONTRACT["product_version"] == "0.2.0-m2s3d-candidate"
    assert builder.CONTRACT["python_hash_seed"] == "1"
    assert builder.CONTRACT["source_date_epoch"] == "1788220800"
    assert builder.S3B_CANDIDATE_ROOT.name == "m2-s3b-current-source"
    assert builder.S3B_CANDIDATE_ROOT != builder.CANDIDATE_ROOT


def test_s3d_spec_contains_the_packaged_protocol_and_all_synthetic_modules() -> None:
    source = builder.CANDIDATE_SPEC.read_text(encoding="utf-8")
    for module in builder.REQUIRED_MODULES:
        assert f'"{module}"' in source
    assert "m2_packaged_reproduction" in source
    assert "console=True" in source
    assert "upx=False" in source


def test_round_trip_contract_is_two_cycles_and_six_processes() -> None:
    contract = round_trip.round_trip_contract()
    assert contract == {
        "cycle_count": 2,
        "process_count": 6,
        "reproduction_runtime_mode": "m2synthetic-reproduce",
        "retry_count": 0,
        "run_order": ["PREFLIGHT_60S", "NOMINAL_20M"],
    }
    assert round_trip.REVIEWER_PIN == "m2-s3d-round-trip-process-only"


def test_projection_requires_export_and_exact_reproduction_for_both_runs() -> None:
    cycle = round_trip.canonical_recorded_cycle()
    projection = round_trip.project_cycle(cycle)
    assert set(projection) == {
        "nominal_artifact_sha256",
        "nominal_bundle_sha256",
        "nominal_d1_receipt_digest",
        "nominal_reproduction_result_digest",
        "preflight_artifact_sha256",
        "preflight_bundle_sha256",
        "preflight_d1_receipt_digest",
        "preflight_reproduction_result_digest",
    }
    assert all(isinstance(value, str) and len(value) == 64 for value in projection.values())

    class Adapter:
        calls: list[int] = []

        def run_cycle(self, cycle_number: int) -> dict[str, object]:
            self.calls.append(cycle_number)
            return cycle

    original = round_trip._validate_fixed_inputs
    round_trip._validate_fixed_inputs = lambda: {
        "build_validation_sha256": "0" * 64,
        "executable_sha256": "1" * 64,
        "manifest_sha256": "2" * 64,
        "tree_sha256": "3" * 64,
    }
    try:
        adapter = Adapter()
        receipt = round_trip._run_with(adapter)
    finally:
        round_trip._validate_fixed_inputs = original
    assert adapter.calls == [1, 2]
    assert receipt.body["reproducibility"]["byte_identical"] is True


def test_failure_documents_are_bounded_and_sanitized(tmp_path: Path) -> None:
    document = round_trip.failure_document(round_trip.RoundTripFailureCode.REQUEST_INVALID)
    encoded = _canonical(document)
    assert len(encoded) < 1024
    assert document["failure_code"] == "REQUEST_INVALID"
    forbidden = (str(ROOT).lower(), os.environ.get("USERNAME", "").lower(), "traceback")
    lowered = encoded.decode("utf-8").lower()
    assert all(not item or item not in lowered for item in forbidden)
    owned = tmp_path / ".pdu-m2-s3d-cleanup-test"
    owned.mkdir()
    (owned / "runtime.log").write_text("synthetic", encoding="utf-8")
    round_trip._safe_cleanup_root(owned, tmp_path)
    assert not owned.exists()


def test_recorded_receipt_is_canonical_and_closes_only_s3d_gaps() -> None:
    payload = RECEIPT.read_bytes()
    document = json.loads(payload)
    assert payload == _canonical(document)
    body = document["body"]
    assert document["body_sha256"] == hashlib.sha256(_canonical(body)[:-1]).hexdigest()
    assert document["status"] == round_trip.STATUS
    gaps = {item["gap_id"]: item["status"] for item in body["gap_projection"]}
    assert gaps["GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT"] == "CLOSED_FOR_CURRENT_CANDIDATE"
    assert (
        gaps["GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT"]
        == "CLOSED_FOR_CURRENT_CANDIDATE"
    )
    assert gaps["GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT"] == "OPEN"
    assert gaps["GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT"] == "OPEN"


def test_authority_ceiling_and_historical_receipts_remain_closed() -> None:
    before = {
        "s3b": hashlib.sha256(S3B_RECEIPT.read_bytes()).hexdigest(),
        "s3c": hashlib.sha256(S3C_RECEIPT.read_bytes()).hexdigest(),
    }
    assert before == round_trip.HISTORICAL_RECEIPT_SHA256
    ceiling = round_trip.authority_ceiling()
    assert ceiling["packaged_evidence_round_trip_verified"] is True
    for key in (
        "clean_machine_verified",
        "collection_authorized",
        "d1_go",
        "distribution_ready",
        "execution_authorized",
        "participant_collection_authorized",
        "physical_camera_access_authorized",
        "release_authorized",
        "research_ready",
        "same_host_portable_verified",
    ):
        assert ceiling[key] is False
    assert ceiling["authority_status"] == "AUTHORITY_NOT_ISSUED"
    assert ceiling["device_gate_decision"] == "UNVERIFIED"
