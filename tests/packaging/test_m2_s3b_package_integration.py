from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "build_m2_s3b_candidate.py"
SPEC = ROOT / "packaging" / "PDU-Exam-Observer.current-source.spec"
README = ROOT / "packaging" / "README_M2_S3B_CANDIDATE.txt"
CANDIDATE_ROOT = ROOT / "packaging" / "candidates" / "m2-s3b-current-source"
BUNDLE_ROOT = CANDIDATE_ROOT / "PDU-Exam-Observer"
LOCAL_VALIDATION = CANDIDATE_ROOT / "M2_S3B_BUILD_VALIDATION.json"
AI_RECEIPT = ROOT / "docs" / "ai" / "M2_S3B_PACKAGE_INTEGRATION.json"
S3A_AUDIT = ROOT / "docs" / "ai" / "M2_S3A_PACKAGE_GAP_AUDIT.json"
STATUS = (
    "M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_"
    "STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY"
)
REQUIRED_MODULES = {
    "fastapi",
    "pdu_exam_observer.api.synthetic_review",
    "pdu_exam_observer.m2_d1_contract",
    "pdu_exam_observer.m2_persistence",
    "pdu_exam_observer.m2_synthetic",
    "pdu_exam_observer.m2_synthetic_environment",
    "pdu_exam_observer.m2_synthetic_evidence",
    "pdu_exam_observer.m2_synthetic_integration",
    "pdu_exam_observer.m2_synthetic_nominal_fixture",
    "pdu_exam_observer.m2_synthetic_preflight_fixture",
    "pdu_exam_observer.m2_synthetic_reproduction",
    "pdu_exam_observer.m2_synthetic_review",
    "pydantic",
    "uvicorn",
}
HISTORICAL_HASHES = {
    "packaging/PDU-Exam-Observer.spec": (
        "1ed8a4a36560c3c48b5fa10d505322366d28999caa262644b7e872d6f35e0286"
    ),
    "packaging/README.txt": ("bb5d18a6173d3beced8f8a6ec4aa7e38adf4385f705fba469b4b451e7cfb6e0f"),
    "packaging/RELEASE_MANIFEST.json": (
        "9c4dde09bce5833ceaac4eb863171ba0b524368c329d6254e4c360d10d77c256"
    ),
    "packaging/release/PDU-Exam-Observer/PDUExamObserver.exe": (
        "ec0d26a9f63ae3ec56ef1a2ac75235df5e419884697d86c1db37100604dfd7ff"
    ),
}


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_m2_s3b_candidate", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical(document: dict[str, object]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def test_builder_cli_is_closed_bounded_and_default_check_is_read_only() -> None:
    before = AI_RECEIPT.read_bytes() if AI_RECEIPT.exists() else None
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode in {0, 2}
    assert result.stderr == b""
    assert result.stdout.count(b"\n") == 1
    assert Path(result.stdout.decode("utf-8")).is_absolute() is False
    assert (AI_RECEIPT.read_bytes() if AI_RECEIPT.exists() else None) == before

    rejected = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", "elsewhere"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["failure_code"] == "REQUEST_INVALID"
    assert rejected.stderr == b""


def test_candidate_contract_locks_toolchain_environment_and_hidden_imports() -> None:
    builder = _load_builder()
    contract = builder.contract_snapshot()
    assert contract == {
        "build_time_utc": "2026-09-01T00:00:00Z",
        "node": "24.11.0",
        "npm": "11.14.1",
        "product_version": "0.2.0-m2s3b-candidate",
        "pyinstaller": "6.10.0",
        "python": "3.11.9",
        "python_hash_seed": "1",
        "schema_version": "release-manifest.v1",
        "source_date_epoch": "1788220800",
        "target_architecture": "x64",
        "target_os": "Windows 11",
        "uv": "0.10.10",
    }
    assert set(builder.required_modules()) == REQUIRED_MODULES
    assert builder.runtime_build_environment_contract() == {
        "project_dependency_names": [
            "fastapi",
            "mediapipe",
            "pydantic",
            "sse-starlette",
            "uvicorn",
        ],
        "project_sync_args": ["sync", "--locked", "--no-dev"],
    }
    assert SPEC.is_file()
    spec_text = SPEC.read_text(encoding="utf-8")
    assert "exclude_binaries=True" in spec_text
    assert "a.scripts,\n    [],\n    exclude_binaries=True" in spec_text


def test_source_binding_matches_s3a_historical_inputs_and_current_rp2() -> None:
    builder = _load_builder()
    binding = builder.source_binding_snapshot()
    assert binding["s3a_audit_sha256"] == hashlib.sha256(S3A_AUDIT.read_bytes()).hexdigest()
    for relative, expected in HISTORICAL_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    assert binding["historical_inputs_verified"] is True
    assert set(binding["rp2"]) == {
        "binding_schema_exact_bytes_sha256",
        "candidate_exact_bytes_sha256",
        "static_bindings_digest",
    }


def test_canonical_receipt_has_closed_envelope_and_valid_body_hash() -> None:
    document = json.loads(AI_RECEIPT.read_text(encoding="utf-8"))
    assert AI_RECEIPT.read_bytes() == _canonical(document)
    assert set(document) == {"artifact_kind", "body", "body_sha256", "schema_version", "status"}
    assert document["artifact_kind"] == "M2_S3B_PACKAGE_INTEGRATION_RECEIPT"
    assert document["schema_version"] == 1
    assert document["status"] == STATUS
    assert document["body_sha256"] == hashlib.sha256(_canonical(document["body"])).hexdigest()


def test_candidate_records_prove_two_byte_identical_manifest_valid_builds() -> None:
    builder = _load_builder()
    receipt = json.loads(LOCAL_VALIDATION.read_text(encoding="utf-8"))
    source_revision = receipt["body"]["source_revision"]
    result = builder._check_candidate(source_revision, require_ai_receipt_match=False)
    assert result["result"] == "CANDIDATE_PACKAGE_INTEGRATED"
    with pytest.raises(builder.CandidateError) as wrong_revision:
        builder._check_candidate(
            {**source_revision, "static_bindings_digest": "0" * 64},
            require_ai_receipt_match=False,
        )
    assert wrong_revision.value.code == "RP2_INVALID"

    reproducibility = receipt["body"]["reproducibility"]
    assert reproducibility["byte_identical"] is True
    assert reproducibility["mismatch_paths"] == []
    assert reproducibility["build_a_tree_sha256"] == reproducibility["build_b_tree_sha256"]
    assert builder.verify_candidate_manifest() is True


def test_recursive_executable_inventory_contains_every_required_module() -> None:
    builder = _load_builder()
    inventory = set(builder.read_candidate_archive_inventory())
    assert REQUIRED_MODULES <= inventory
    receipt = json.loads(LOCAL_VALIDATION.read_text(encoding="utf-8"))["body"]
    inclusion = receipt["python_runtime_inclusion"]
    assert inclusion["inventory_source"] == "EXECUTABLE_RECURSIVE_ARCHIVE"
    assert set(inclusion["required_modules"]) == REQUIRED_MODULES
    assert inclusion["all_present"] is True


def test_candidate_frontend_and_readme_preserve_the_synthetic_boundary() -> None:
    builder = _load_builder()
    receipt = json.loads(LOCAL_VALIDATION.read_text(encoding="utf-8"))["body"]
    frontend = receipt["frontend_inclusion"]
    assert frontend["byte_identical"] is True
    assert frontend["isolated_tree_sha256"] == frontend["packaged_tree_sha256"]
    assert builder.verify_candidate_frontend() is True
    readme = README.read_text(encoding="utf-8")
    packaged = (BUNDLE_ROOT / "README.txt").read_text(encoding="utf-8")
    assert packaged == readme
    for marker in builder.required_readme_markers():
        assert marker in packaged


def test_gap_projection_authority_ceiling_and_historical_package_remain_closed() -> None:
    body = json.loads(AI_RECEIPT.read_text(encoding="utf-8"))["body"]
    gap_projection = body["gap_projection"]
    assert [
        item["gap_id"]
        for item in gap_projection
        if item["status"] == "CLOSED_FOR_CURRENT_CANDIDATE"
    ] == [
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
        "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED",
        "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE",
    ]
    assert len([item for item in gap_projection if item["status"] == "OPEN"]) == 5
    ceiling = body["authority_ceiling"]
    assert ceiling["historical_package_unchanged"] is True
    assert ceiling["candidate_package_contains_integration"] is True
    assert ceiling["packaged_runtime_smoke_verified"] is False
    assert ceiling["distribution_ready"] is False
    assert ceiling["release_authorized"] is False
    assert ceiling["authority_status"] == "AUTHORITY_NOT_ISSUED"
    for relative, expected in HISTORICAL_HASHES.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
