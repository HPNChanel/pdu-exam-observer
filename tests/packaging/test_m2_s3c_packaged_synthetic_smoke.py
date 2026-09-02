from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "run_m2_s3c_packaged_smoke.py"
RECEIPT = ROOT / "docs" / "ai" / "M2_S3C_PACKAGED_SYNTHETIC_SMOKE.json"
STATUS = (
    "M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_"
    "SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)
S3B_RECEIPT_SHA256 = "bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd"
EXECUTABLE_SHA256 = "9a90abf58e7a0c36c5050c44213ec2f478070b5c8bfdd05570bed4bdc40efbec"
MANIFEST_SHA256 = "e0b279a1e667cc39e5c5f62d6aa169e6973c2c2f957f78118f86f9de972e620f"
TREE_SHA256 = "29a0d7749e8069978f54d9c0087261fe709da3c016c73acca9cffb5034f8c37e"
README_SHA256 = "653585fd4c0e25a81ebca9ed1107d791ac8494cfffdea26370d005a41bff7570"


def _load_module():
    assert SCRIPT.is_file(), "S3C harness is not implemented"
    spec = importlib.util.spec_from_file_location("run_m2_s3c_packaged_smoke", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_record(run_kind: str, sequence: int, count: int, marker: str) -> dict[str, object]:
    return {
        "job_status": "TERMINAL",
        "request_id": f"synrun-{marker * 32}",
        "run_kind": run_kind,
        "run_sequence": sequence,
        "schema_version": 1,
        "service_failure_code": None,
        "receipt": {
            "artifact_sha256": marker * 64,
            "authority_status": "AUTHORITY_NOT_ISSUED",
            "collection_authorized": False,
            "d1_go": False,
            "d1_outcome": "BACKEND_CONTRACT_PASS",
            "d1_receipt_digest": ("b" if marker == "a" else "e") * 64,
            "device_gate_decision": "UNVERIFIED",
            "evidence_kind": "SIMULATED",
            "integration_status": "PERSISTED",
            "observation_count": count,
            "observation_digest": ("c" if marker == "a" else "f") * 64,
            "participant_collection_authorized": False,
            "physical_camera_access_authorized": False,
            "result_digest": ("d" if marker == "a" else "9") * 64,
        },
    }


def _invocation() -> dict[str, object]:
    return {
        "browser_opened": False,
        "camera_or_device_input_supplied": False,
        "candidate_bytes_unchanged": True,
        "evidence_export_invoked": False,
        "loopback_listener_scope_verified": True,
        "nominal": _run_record("NOMINAL_20M", 2, 18077, "2"),
        "preflight": _run_record("PREFLIGHT_60S", 1, 977, "1"),
        "process_tree_terminated": True,
        "reviewer_auth_verified": True,
        "runtime_envelope_package_contains_integration": False,
        "temporary_workspace_state": "REMOVED",
    }


class _FakeAdapter:
    def __init__(self, first: dict[str, object], second: dict[str, object]) -> None:
        self._items = (first, second)
        self.calls: list[int] = []

    def run_invocation(self, invocation_number: int) -> dict[str, object]:
        self.calls.append(invocation_number)
        return self._items[invocation_number - 1]


def test_cli_is_no_argument_and_pins_exact_candidate_inputs() -> None:
    module = _load_module()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--candidate", "C:/forged.exe"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "failure_code": "REQUEST_INVALID",
        "result": "PACKAGED_SYNTHETIC_RUNTIME_SMOKE_NOT_VERIFIED",
        "status": "M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_NOT_VERIFIED",
    }
    assert module._validate_fixed_inputs() == {
        "candidate_executable_sha256": EXECUTABLE_SHA256,
        "candidate_manifest_sha256": MANIFEST_SHA256,
        "candidate_readme_sha256": README_SHA256,
        "candidate_tree_sha256": TREE_SHA256,
        "s3b_receipt_sha256": S3B_RECEIPT_SHA256,
    }


def test_orchestrator_uses_fixed_environment_and_exactly_two_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    static_bindings = {"artifacts": {}, "policy_preimages": {}}
    static_bytes = json.dumps(
        static_bindings,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    candidate = {
        "artifact_kind": "D1_N2_STATIC_BINDING_CANDIDATE",
        "static_bindings": static_bindings,
        "static_bindings_digest": hashlib.sha256(static_bytes).hexdigest(),
    }
    candidate_path = tmp_path / "candidate.json"
    schema_path = tmp_path / "schema.json"
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    schema_path.write_text("schema\n", encoding="utf-8")
    monkeypatch.setattr(module, "RP2_CANDIDATE", candidate_path)
    monkeypatch.setattr(module, "RP2_SCHEMA", schema_path)
    revision = module._load_harness_revision()
    assert revision == {
        "binding_schema_exact_bytes_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        "candidate_exact_bytes_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "static_bindings_digest": candidate["static_bindings_digest"],
    }
    candidate["static_bindings"]["authority_status"] = "ISSUED"
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(module._SmokeError) as tampered:
        module._load_harness_revision()
    assert tampered.value.code is module.PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH

    environment = module._build_child_environment({}, tmp_path, 12001, 12002)
    assert environment == {
        "PDU_EXAM_PORT": "12001",
        "PDU_MONITOR_PORT": "12002",
        "PDU_OPEN_BROWSER": "0",
        "PDU_REVIEWER_PIN": "m2-s3c-smoke-process-only",
        "PDU_RUNTIME_MODE": "m2synthetic",
        "TEMP": str(tmp_path.resolve()),
        "TMP": str(tmp_path.resolve()),
    }
    adapter = _FakeAdapter(_invocation(), _invocation())
    receipt = module._run_packaged_smoke_with(
        adapter,
        smoke_harness_revision={
            "binding_schema_exact_bytes_sha256": "a" * 64,
            "candidate_exact_bytes_sha256": "b" * 64,
            "static_bindings_digest": "c" * 64,
        },
    )
    assert adapter.calls == [1, 2]
    assert receipt.status == STATUS
    assert receipt.failure_code is None


def test_loopback_listener_and_reviewer_authority_checks_fail_closed() -> None:
    module = _load_module()
    module._validate_listener_scope(
        (
            {"local_address": "127.0.0.1", "local_port": 12001},
            {"local_address": "::1", "local_port": 12002},
        ),
        frozenset({12001, 12002}),
    )
    with pytest.raises(module._SmokeError) as lan:
        module._validate_listener_scope(
            ({"local_address": "0.0.0.0", "local_port": 12001},),
            frozenset({12001, 12002}),
        )
    assert lan.value.code is module.PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION
    envelope = {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "collection_authorized": False,
        "d1_go": False,
        "device_gate_decision": "UNVERIFIED",
        "evidence_kind": "SIMULATED",
        "package_contains_integration": False,
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
        "research_ready": False,
    }
    module._validate_authority_envelope(envelope)
    envelope["d1_go"] = True
    with pytest.raises(module._SmokeError) as opened:
        module._validate_authority_envelope(envelope)
    assert opened.value.code is module.PackagedSmokeFailureCode.AUTHORITY_CEILING_VIOLATION


def test_terminal_preflight_and_nominal_projection_is_exact_and_discriminating() -> None:
    module = _load_module()
    preflight = module._project_terminal_run(
        _run_record("PREFLIGHT_60S", 1, 977, "1"),
        expected_kind="PREFLIGHT_60S",
        expected_sequence=1,
        expected_count=977,
    )
    nominal = module._project_terminal_run(
        _run_record("NOMINAL_20M", 2, 18077, "2"),
        expected_kind="NOMINAL_20M",
        expected_sequence=2,
        expected_count=18077,
    )
    assert preflight == {
        "artifact_sha256": "1" * 64,
        "d1_receipt_digest": "e" * 64,
        "observation_digest": "f" * 64,
        "result_digest": "9" * 64,
    }
    assert nominal == {
        "artifact_sha256": "2" * 64,
        "d1_receipt_digest": "e" * 64,
        "observation_digest": "f" * 64,
        "result_digest": "9" * 64,
    }
    malformed = _run_record("PREFLIGHT_60S", 1, 976, "1")
    with pytest.raises(module._SmokeError) as wrong_count:
        module._project_terminal_run(
            malformed,
            expected_kind="PREFLIGHT_60S",
            expected_sequence=1,
            expected_count=977,
        )
    assert wrong_count.value.code is module.PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID


def test_success_receipt_separates_runtime_disclosure_from_candidate_inclusion() -> None:
    module = _load_module()
    receipt = module._run_packaged_smoke_with(
        _FakeAdapter(_invocation(), _invocation()),
        smoke_harness_revision={
            "binding_schema_exact_bytes_sha256": "a" * 64,
            "candidate_exact_bytes_sha256": "b" * 64,
            "static_bindings_digest": "c" * 64,
        },
    ).as_dict()
    body = receipt["body"]
    assert body["runtime_boundary"]["runtime_envelope_package_contains_integration"] is False
    assert body["runtime_boundary"]["runtime_envelope_classification"] == (
        "CONSERVATIVE_SOURCE_ERA_DISCLOSURE_NOT_CANDIDATE_ATTESTATION"
    )
    assert body["authority_ceiling"]["candidate_package_contains_integration"] is True
    assert body["authority_ceiling"]["packaged_runtime_smoke_verified"] is True
    assert body["authority_ceiling"]["same_host_portable_verified"] is False
    assert body["authority_ceiling"]["authority_status"] == "AUTHORITY_NOT_ISSUED"


def test_failures_are_bounded_canonical_and_never_disclose_exception_text() -> None:
    module = _load_module()
    receipt = module._failure_receipt(module.PackagedSmokeFailureCode.UNEXPECTED_FAILURE)
    encoded = json.dumps(receipt.as_dict(), sort_keys=True, separators=(",", ":"))
    assert receipt.failure_code is module.PackagedSmokeFailureCode.UNEXPECTED_FAILURE
    assert receipt.status == "M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_NOT_VERIFIED"
    for forbidden in ("C:/", "D:/", "\\", "private", "token", "traceback"):
        assert forbidden not in encoded.lower()
    assert receipt.as_dict()["body_sha256"] == receipt.recompute_digest()


def test_cleanup_removes_only_owned_root_and_incomplete_runtime_never_passes(
    tmp_path: Path,
) -> None:
    module = _load_module()

    class _AlreadyExitedProcess:
        def poll(self) -> int:
            return 1

    assert module._terminate_process_tree(_AlreadyExitedProcess()) is False

    parent = tmp_path / "candidates"
    owned = parent / ".pdu-m2-s3c-owned"
    owned.mkdir(parents=True)
    (owned / "child.log").write_text("synthetic", encoding="utf-8")
    module._safe_cleanup_root(owned, parent)
    assert not owned.exists()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(module._SmokeError) as unsafe:
        module._safe_cleanup_root(outside, parent)
    assert unsafe.value.code is module.PackagedSmokeFailureCode.TEMP_CLEANUP_FAILED
    incomplete = _invocation()
    incomplete["process_tree_terminated"] = False
    with pytest.raises(module._SmokeError) as cleanup:
        module._run_packaged_smoke_with(
            _FakeAdapter(incomplete, _invocation()),
            smoke_harness_revision={
                "binding_schema_exact_bytes_sha256": "a" * 64,
                "candidate_exact_bytes_sha256": "b" * 64,
                "static_bindings_digest": "c" * 64,
            },
        )
    assert cleanup.value.code is module.PackagedSmokeFailureCode.PROCESS_CLEANUP_FAILED


def test_recorded_receipt_is_canonical_hash_bound_and_closes_only_gap_03() -> None:
    assert RECEIPT.is_file(), "authorized runtime receipt has not been materialized"
    payload = RECEIPT.read_bytes()
    document = json.loads(payload)
    assert payload == (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    body_bytes = json.dumps(
        document["body"], ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert document["body_sha256"] == hashlib.sha256(body_bytes).hexdigest()
    assert document["status"] == STATUS
    gaps = {item["gap_id"]: item["status"] for item in document["body"]["gap_projection"]}
    assert gaps == {
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED": (
            "CLOSED_FOR_CURRENT_CANDIDATE"
        ),
        "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED": "CLOSED_FOR_CURRENT_CANDIDATE",
        "GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT": (
            "CLOSED_FOR_CURRENT_CANDIDATE"
        ),
        "GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT": "OPEN",
        "GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT": "OPEN",
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT": "OPEN",
        "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE": (
            "CLOSED_FOR_CURRENT_CANDIDATE"
        ),
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT": "OPEN",
    }
    ceiling = document["body"]["authority_ceiling"]
    assert ceiling["packaged_runtime_smoke_verified"] is True
    assert ceiling["same_host_portable_verified"] is False
    assert ceiling["clean_machine_verified"] is False
    assert ceiling["release_authorized"] is False
    assert ceiling["distribution_ready"] is False
    assert ceiling["physical_camera_access_authorized"] is False
    assert ceiling["d1_go"] is False
    assert ceiling["authority_status"] == "AUTHORITY_NOT_ISSUED"
