"""Run the fixed same-host synthetic smoke against the immutable S3B candidate."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PARENT = ROOT / "packaging" / "candidates"
CANDIDATE_ROOT = CANDIDATE_PARENT / "m2-s3b-current-source"
BUNDLE_ROOT = CANDIDATE_ROOT / "PDU-Exam-Observer"
EXECUTABLE = BUNDLE_ROOT / "PDUExamObserver.exe"
BUNDLED_MANIFEST = BUNDLE_ROOT / "RELEASE_MANIFEST.json"
DETACHED_MANIFEST = CANDIDATE_ROOT / "RELEASE_MANIFEST.json"
CANDIDATE_README = BUNDLE_ROOT / "README.txt"
S3B_VALIDATION = CANDIDATE_ROOT / "M2_S3B_BUILD_VALIDATION.json"
S3B_RECEIPT = ROOT / "docs" / "ai" / "M2_S3B_PACKAGE_INTEGRATION.json"
RP2_CANDIDATE = ROOT / "docs" / "spec" / "M2_D1_N2_STATIC_BINDING_CANDIDATE.json"
RP2_SCHEMA = ROOT / "docs" / "spec" / "M2_D1_N2_AUTHORITY_BINDING.schema.json"
RELEASE_MANIFEST_SCRIPT = ROOT / "scripts" / "release_manifest.py"

STATUS = (
    "M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_"
    "SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)
FAILURE_STATUS = "M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_NOT_VERIFIED"
S3B_RECEIPT_SHA256 = "bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd"
EXECUTABLE_SHA256 = "9a90abf58e7a0c36c5050c44213ec2f478070b5c8bfdd05570bed4bdc40efbec"
MANIFEST_SHA256 = "e0b279a1e667cc39e5c5f62d6aa169e6973c2c2f957f78118f86f9de972e620f"
TREE_SHA256 = "29a0d7749e8069978f54d9c0087261fe709da3c016c73acca9cffb5034f8c37e"
README_SHA256 = "653585fd4c0e25a81ebca9ed1107d791ac8494cfffdea26370d005a41bff7570"
CANDIDATE_SOURCE_REVISION: dict[str, str] = {
    "binding_schema_exact_bytes_sha256": (
        "3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca"
    ),
    "candidate_exact_bytes_sha256": (
        "a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639"
    ),
    "static_bindings_digest": (
        "a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f"
    ),
}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST_ID = re.compile(r"synrun-[0-9a-f]{32}\Z")


class PackagedSmokeFailureCode(StrEnum):
    REQUEST_INVALID = "REQUEST_INVALID"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    S3B_RECEIPT_MISMATCH = "S3B_RECEIPT_MISMATCH"
    CANDIDATE_INPUT_MISMATCH = "CANDIDATE_INPUT_MISMATCH"
    MANIFEST_MISMATCH = "MANIFEST_MISMATCH"
    PROCESS_START_FAILED = "PROCESS_START_FAILED"
    HEALTH_TIMEOUT = "HEALTH_TIMEOUT"
    LOOPBACK_SCOPE_VIOLATION = "LOOPBACK_SCOPE_VIOLATION"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    SYNTHETIC_RUN_REJECTED = "SYNTHETIC_RUN_REJECTED"
    SYNTHETIC_RUN_TIMEOUT = "SYNTHETIC_RUN_TIMEOUT"
    SYNTHETIC_RECEIPT_INVALID = "SYNTHETIC_RECEIPT_INVALID"
    RUN_REPRODUCIBILITY_MISMATCH = "RUN_REPRODUCIBILITY_MISMATCH"
    AUTHORITY_CEILING_VIOLATION = "AUTHORITY_CEILING_VIOLATION"
    PROCESS_CLEANUP_FAILED = "PROCESS_CLEANUP_FAILED"
    TEMP_CLEANUP_FAILED = "TEMP_CLEANUP_FAILED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


class _SmokeError(RuntimeError):
    def __init__(self, code: PackagedSmokeFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


def _canonical_bytes(document: object, *, trailing_lf: bool = True) -> bytes:
    suffix = "\n" if trailing_lf else ""
    return (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + suffix
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH) from exc
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH) from exc
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _strict_json(
    path: Path,
    code: PackagedSmokeFailureCode,
    *,
    canonical_required: bool = True,
) -> dict[str, Any]:
    if not path.is_file() or _is_link_or_reparse(path):
        raise _SmokeError(code)
    try:
        payload = path.read_bytes()
        document = json.loads(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _SmokeError(code) from exc
    if not isinstance(document, dict) or (
        canonical_required and payload != _canonical_bytes(document)
    ):
        raise _SmokeError(code)
    return cast(dict[str, Any], document)


def _tree_records(root: Path) -> list[dict[str, object]]:
    if not root.is_dir() or _is_link_or_reparse(root):
        raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
    records: list[dict[str, object]] = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in dirs:
            if _is_link_or_reparse(current_path / name):
                raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
        for name in files:
            path = current_path / name
            if _is_link_or_reparse(path):
                raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
            relative = path.relative_to(root).as_posix()
            if relative == "M2_S3B_BUILD_VALIDATION.json":
                continue
            if not relative or ".." in Path(relative).parts or "\\" in relative:
                raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
            records.append(
                {"path": relative, "sha256": _sha256_file(path), "size": path.stat().st_size}
            )
    records.sort(key=lambda item: str(item["path"]))
    return records


def _tree_digest(root: Path) -> str:
    return _sha256_bytes(_canonical_bytes(_tree_records(root)))


def _verify_manifest() -> None:
    command = [
        sys.executable,
        str(RELEASE_MANIFEST_SCRIPT),
        "verify",
        "--bundle-root",
        str(BUNDLE_ROOT),
        "--bundled",
        str(BUNDLED_MANIFEST),
        "--detached",
        str(DETACHED_MANIFEST),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _SmokeError(PackagedSmokeFailureCode.MANIFEST_MISMATCH) from exc
    if completed.returncode != 0:
        raise _SmokeError(PackagedSmokeFailureCode.MANIFEST_MISMATCH)


def _validate_s3b_receipt(document: dict[str, Any]) -> None:
    if set(document) != {"artifact_kind", "body", "body_sha256", "schema_version", "status"}:
        raise _SmokeError(PackagedSmokeFailureCode.S3B_RECEIPT_MISMATCH)
    body = document.get("body")
    if (
        document.get("artifact_kind") != "M2_S3B_PACKAGE_INTEGRATION_RECEIPT"
        or document.get("schema_version") != 1
        or not isinstance(body, dict)
        or document.get("body_sha256") != _sha256_bytes(_canonical_bytes(body))
        or body.get("source_revision") != CANDIDATE_SOURCE_REVISION
    ):
        raise _SmokeError(PackagedSmokeFailureCode.S3B_RECEIPT_MISMATCH)


def _validate_fixed_inputs() -> dict[str, str]:
    if platform.system() != "Windows":
        raise _SmokeError(PackagedSmokeFailureCode.PLATFORM_UNSUPPORTED)
    if _sha256_file(S3B_RECEIPT) != S3B_RECEIPT_SHA256:
        raise _SmokeError(PackagedSmokeFailureCode.S3B_RECEIPT_MISMATCH)
    if _sha256_file(S3B_VALIDATION) != S3B_RECEIPT_SHA256:
        raise _SmokeError(PackagedSmokeFailureCode.S3B_RECEIPT_MISMATCH)
    receipt = _strict_json(S3B_RECEIPT, PackagedSmokeFailureCode.S3B_RECEIPT_MISMATCH)
    validation = _strict_json(S3B_VALIDATION, PackagedSmokeFailureCode.S3B_RECEIPT_MISMATCH)
    _validate_s3b_receipt(receipt)
    _validate_s3b_receipt(validation)
    if receipt != validation:
        raise _SmokeError(PackagedSmokeFailureCode.S3B_RECEIPT_MISMATCH)
    observed = {
        "candidate_executable_sha256": _sha256_file(EXECUTABLE),
        "candidate_manifest_sha256": _sha256_file(DETACHED_MANIFEST),
        "candidate_readme_sha256": _sha256_file(CANDIDATE_README),
        "candidate_tree_sha256": _tree_digest(CANDIDATE_ROOT),
        "s3b_receipt_sha256": _sha256_file(S3B_RECEIPT),
    }
    expected = {
        "candidate_executable_sha256": EXECUTABLE_SHA256,
        "candidate_manifest_sha256": MANIFEST_SHA256,
        "candidate_readme_sha256": README_SHA256,
        "candidate_tree_sha256": TREE_SHA256,
        "s3b_receipt_sha256": S3B_RECEIPT_SHA256,
    }
    if observed != expected:
        raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
    if _sha256_file(BUNDLED_MANIFEST) != MANIFEST_SHA256:
        raise _SmokeError(PackagedSmokeFailureCode.MANIFEST_MISMATCH)
    _verify_manifest()
    return observed


def _load_harness_revision() -> dict[str, str]:
    candidate = _strict_json(
        RP2_CANDIDATE,
        PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH,
        canonical_required=False,
    )
    static_bindings = candidate.get("static_bindings")
    static_digest = candidate.get("static_bindings_digest")
    if (
        not isinstance(static_bindings, dict)
        or not isinstance(static_digest, str)
        or _sha256_bytes(_canonical_bytes(static_bindings, trailing_lf=False))
        != static_digest
    ):
        raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
    revision = {
        "binding_schema_exact_bytes_sha256": _sha256_file(RP2_SCHEMA),
        "candidate_exact_bytes_sha256": _sha256_file(RP2_CANDIDATE),
        "static_bindings_digest": static_digest,
    }
    if not all(isinstance(value, str) and _HEX64.fullmatch(value) for value in revision.values()):
        raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
    return revision


@dataclass(frozen=True, slots=True)
class PackagedSyntheticSmokeReceipt:
    status: str
    failure_code: PackagedSmokeFailureCode | None
    body: dict[str, object]

    def canonical_payload(self) -> dict[str, object]:
        return dict(self.body)

    def recompute_digest(self) -> str:
        return _sha256_bytes(_canonical_bytes(self.canonical_payload(), trailing_lf=False))

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact_kind": "M2_S3C_PACKAGED_SYNTHETIC_SMOKE_RECEIPT",
            "body": self.canonical_payload(),
            "body_sha256": self.recompute_digest(),
            "schema_version": 1,
            "status": self.status,
        }


class _SmokeAdapter(Protocol):
    def run_invocation(self, invocation_number: int) -> dict[str, object]: ...


def _build_child_environment(
    _base: dict[str, str], root: Path, exam_port: int, monitor_port: int
) -> dict[str, str]:
    return {
        "PDU_EXAM_PORT": str(exam_port),
        "PDU_MONITOR_PORT": str(monitor_port),
        "PDU_OPEN_BROWSER": "0",
        "PDU_REVIEWER_PIN": "m2-s3c-smoke-process-only",
        "PDU_RUNTIME_MODE": "m2synthetic",
        "TEMP": str(root.resolve()),
        "TMP": str(root.resolve()),
    }


def _validate_listener_scope(
    listeners: tuple[dict[str, object], ...], expected_ports: frozenset[int]
) -> None:
    if not listeners:
        raise _SmokeError(PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION)
    observed: set[int] = set()
    for listener in listeners:
        address = listener.get("local_address")
        port = listener.get("local_port")
        if address not in {"127.0.0.1", "::1"} or not isinstance(port, int):
            raise _SmokeError(PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION)
        if port not in expected_ports:
            raise _SmokeError(PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION)
        observed.add(port)
    if observed != set(expected_ports):
        raise _SmokeError(PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION)


def _validate_authority_envelope(envelope: dict[str, object]) -> None:
    required: dict[str, object] = {
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
    if any(envelope.get(key) != value for key, value in required.items()):
        raise _SmokeError(PackagedSmokeFailureCode.AUTHORITY_CEILING_VIOLATION)


def _project_terminal_run(
    run: dict[str, object], *, expected_kind: str, expected_sequence: int, expected_count: int
) -> dict[str, str]:
    if (
        run.get("job_status") != "TERMINAL"
        or run.get("run_kind") != expected_kind
        or run.get("run_sequence") != expected_sequence
        or run.get("schema_version") != 1
        or run.get("service_failure_code") is not None
        or not isinstance(run.get("request_id"), str)
        or not _REQUEST_ID.fullmatch(cast(str, run["request_id"]))
    ):
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
    receipt = run.get("receipt")
    if not isinstance(receipt, dict):
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
    expected: dict[str, object] = {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "collection_authorized": False,
        "d1_go": False,
        "d1_outcome": "BACKEND_CONTRACT_PASS",
        "d1_receipt_digest": receipt.get("d1_receipt_digest"),
        "device_gate_decision": "UNVERIFIED",
        "evidence_kind": "SIMULATED",
        "integration_status": "PERSISTED",
        "observation_count": expected_count,
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
    projection: dict[str, str] = {}
    for key in ("artifact_sha256", "d1_receipt_digest", "observation_digest", "result_digest"):
        value = receipt.get(key)
        if not isinstance(value, str) or not _HEX64.fullmatch(value):
            raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
        projection[key] = value
    return projection


def _project_invocation(invocation: dict[str, object]) -> dict[str, object]:
    cleanup = {
        "candidate_bytes_unchanged": True,
        "process_tree_terminated": True,
        "temporary_workspace_state": "REMOVED",
    }
    if any(invocation.get(key) != value for key, value in cleanup.items()):
        code = (
            PackagedSmokeFailureCode.PROCESS_CLEANUP_FAILED
            if invocation.get("process_tree_terminated") is not True
            else PackagedSmokeFailureCode.TEMP_CLEANUP_FAILED
        )
        raise _SmokeError(code)
    boundary = {
        "browser_opened": False,
        "camera_or_device_input_supplied": False,
        "evidence_export_invoked": False,
        "loopback_listener_scope_verified": True,
        "reviewer_auth_verified": True,
        "runtime_envelope_package_contains_integration": False,
    }
    if any(invocation.get(key) != value for key, value in boundary.items()):
        raise _SmokeError(PackagedSmokeFailureCode.AUTHORITY_CEILING_VIOLATION)
    preflight = invocation.get("preflight")
    nominal = invocation.get("nominal")
    if not isinstance(preflight, dict) or not isinstance(nominal, dict):
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
    projection: dict[str, object] = {
        "nominal": _project_terminal_run(
            nominal, expected_kind="NOMINAL_20M", expected_sequence=2, expected_count=18077
        ),
        "preflight": _project_terminal_run(
            preflight, expected_kind="PREFLIGHT_60S", expected_sequence=1, expected_count=977
        ),
    }
    projection["projection_sha256"] = _sha256_bytes(
        _canonical_bytes(projection, trailing_lf=False)
    )
    return projection


def _gap_projection() -> list[dict[str, str]]:
    states = (
        (
            "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
            "CLOSED_FOR_CURRENT_CANDIDATE",
        ),
        ("GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED", "CLOSED_FOR_CURRENT_CANDIDATE"),
        ("GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT", "CLOSED_FOR_CURRENT_CANDIDATE"),
        ("GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT", "OPEN"),
        ("GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT", "OPEN"),
        ("GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT", "OPEN"),
        ("GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE", "CLOSED_FOR_CURRENT_CANDIDATE"),
        ("GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT", "OPEN"),
    )
    return [{"gap_id": gap_id, "status": status} for gap_id, status in states]


def _authority_ceiling() -> dict[str, object]:
    return {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "candidate_package_contains_integration": True,
        "candidate_package_unchanged": True,
        "clean_machine_verified": False,
        "collection_authorized": False,
        "d1_go": False,
        "device_gate_decision": "UNVERIFIED",
        "distribution_ready": False,
        "execution_authorized": False,
        "historical_package_unchanged": True,
        "packaged_runtime_smoke_verified": True,
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
        "production_reconciler_implemented": False,
        "production_reconciler_real_storage_verified": False,
        "real_data_deletion_authorized": False,
        "release_authorized": False,
        "research_ready": False,
        "same_host_portable_verified": False,
        "smoke_execution_scope": "LOCAL_SYNTHETIC_CANDIDATE_ONLY",
    }


def _run_packaged_smoke_with(
    adapter: _SmokeAdapter, *, smoke_harness_revision: dict[str, str]
) -> PackagedSyntheticSmokeReceipt:
    if set(smoke_harness_revision) != set(CANDIDATE_SOURCE_REVISION) or not all(
        _HEX64.fullmatch(value) for value in smoke_harness_revision.values()
    ):
        raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
    first = _project_invocation(adapter.run_invocation(1))
    second = _project_invocation(adapter.run_invocation(2))
    first_projection = {key: value for key, value in first.items() if key != "projection_sha256"}
    second_projection = {key: value for key, value in second.items() if key != "projection_sha256"}
    if first_projection != second_projection:
        raise _SmokeError(PackagedSmokeFailureCode.RUN_REPRODUCIBILITY_MISMATCH)
    first_digest = cast(str, first["projection_sha256"])
    second_digest = cast(str, second["projection_sha256"])
    body: dict[str, object] = {
        "authority_ceiling": _authority_ceiling(),
        "candidate_binding": {
            "candidate_executable_sha256": EXECUTABLE_SHA256,
            "candidate_manifest_sha256": MANIFEST_SHA256,
            "candidate_readme_classification": "CONSERVATIVE_PRE_SMOKE_BUILD_SNAPSHOT",
            "candidate_readme_sha256": README_SHA256,
            "candidate_tree_sha256": TREE_SHA256,
        },
        "candidate_source_revision": dict(CANDIDATE_SOURCE_REVISION),
        "gap_projection": _gap_projection(),
        "invocation_a": first,
        "invocation_b": second,
        "observed_on": "2026-09-02",
        "reproducibility": {
            "byte_identical": True,
            "invocation_a_projection_sha256": first_digest,
            "invocation_b_projection_sha256": second_digest,
            "mismatch_fields": [],
        },
        "result": "PACKAGED_SYNTHETIC_RUNTIME_SMOKE_VERIFIED",
        "runtime_boundary": {
            "browser_opened": False,
            "camera_or_device_input_supplied": False,
            "candidate_bytes_unchanged": True,
            "candidate_inclusion_evidence": "S3B_STATIC_ARCHIVE_AND_MANIFEST_BINDING",
            "candidate_package_contains_integration": True,
            "candidate_process_invocation_count": 2,
            "evidence_export_invoked": False,
            "graceful_shutdown_verified": False,
            "loopback_listener_scope_verified": True,
            "process_tree_terminated": True,
            "reviewer_auth_verified": True,
            "runtime_envelope_classification": (
                "CONSERVATIVE_SOURCE_ERA_DISCLOSURE_NOT_CANDIDATE_ATTESTATION"
            ),
            "runtime_envelope_package_contains_integration": False,
            "runtime_mode": "m2synthetic",
            "shutdown_mode": "FORCED_PROCESS_TREE_TERMINATION",
            "temporary_workspace_state": "REMOVED",
        },
        "s3b_receipt_sha256": S3B_RECEIPT_SHA256,
        "smoke_contract": {
            "invocation_count": 2,
            "nominal_frame_count": 18077,
            "nominal_timeout_seconds": 60,
            "preflight_frame_count": 977,
            "preflight_timeout_seconds": 30,
            "retry_count": 0,
            "run_order": ["PREFLIGHT_60S", "NOMINAL_20M"],
        },
        "smoke_harness_revision": dict(smoke_harness_revision),
    }
    return PackagedSyntheticSmokeReceipt(status=STATUS, failure_code=None, body=body)


def _failure_receipt(code: PackagedSmokeFailureCode) -> PackagedSyntheticSmokeReceipt:
    return PackagedSyntheticSmokeReceipt(
        status=FAILURE_STATUS,
        failure_code=code,
        body={
            "authority_status": "AUTHORITY_NOT_ISSUED",
            "collection_authorized": False,
            "d1_go": False,
            "device_gate_decision": "UNVERIFIED",
            "failure_code": code.value,
            "physical_camera_access_authorized": False,
            "result": "PACKAGED_SYNTHETIC_RUNTIME_SMOKE_NOT_VERIFIED",
        },
    )


def _safe_cleanup_root(root: Path, parent: Path) -> None:
    try:
        resolved_parent = parent.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        if resolved_root.parent != resolved_parent or not resolved_root.name.startswith(
            ".pdu-m2-s3c-"
        ):
            raise _SmokeError(PackagedSmokeFailureCode.TEMP_CLEANUP_FAILED)
        shutil.rmtree(resolved_root)
        if resolved_root.exists():
            raise _SmokeError(PackagedSmokeFailureCode.TEMP_CLEANUP_FAILED)
    except _SmokeError:
        raise
    except OSError as exc:
        raise _SmokeError(PackagedSmokeFailureCode.TEMP_CLEANUP_FAILED) from exc


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
    timeout: float = 2.0,
) -> tuple[int, dict[str, Any]]:
    payload = None if body is None else _canonical_bytes(body, trailing_lf=False)
    request = urllib.request.Request(url, data=payload, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            decoded = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            decoded = json.loads(exc.read())
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {}
        status = exc.code
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise _SmokeError(PackagedSmokeFailureCode.HEALTH_TIMEOUT) from exc
    if not isinstance(decoded, dict):
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
    return status, cast(dict[str, Any], decoded)


def _wait_for_health(url: str, deadline_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        try:
            status, payload = _request_json("GET", url)
            if status == 200 and payload.get("status") == "ok":
                return
        except _SmokeError:
            pass
        time.sleep(0.1)
    raise _SmokeError(PackagedSmokeFailureCode.HEALTH_TIMEOUT)


def _inspect_listeners(ports: frozenset[int]) -> tuple[dict[str, object], ...]:
    ordered = sorted(ports)
    command = (
        "$ErrorActionPreference='Stop';"
        f"$p=@({ordered[0]},{ordered[1]});"
        "@(Get-NetTCPConnection -State Listen | Where-Object { $p -contains $_.LocalPort } | "
        "ForEach-Object { [ordered]@{local_address=$_.LocalAddress;local_port=$_.LocalPort} }) | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        parsed = json.loads(completed.stdout) if completed.stdout.strip() else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise _SmokeError(PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION) from exc
    if completed.returncode != 0 or not isinstance(parsed, list):
        raise _SmokeError(PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION)
    result: list[dict[str, object]] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise _SmokeError(PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION)
        result.append(
            {
                "local_address": item.get("local_address"),
                "local_port": item.get("local_port"),
            }
        )
    return tuple(result)


def _login(monitor_origin: str) -> str:
    status, payload = _request_json(
        "POST",
        f"{monitor_origin}/api/v1/reviewer/login",
        headers={"Content-Type": "application/json", "Origin": monitor_origin},
        body={"pin": "m2-s3c-smoke-process-only"},
    )
    token = payload.get("access_token")
    if status != 200 or not isinstance(token, str) or not token:
        raise _SmokeError(PackagedSmokeFailureCode.AUTHENTICATION_FAILED)
    return token


def _submit_and_poll(
    monitor_origin: str, token: str, run_kind: str, idempotency_key: str, timeout: float
) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "Origin": monitor_origin,
    }
    status, submitted = _request_json(
        "POST",
        f"{monitor_origin}/api/v1/synthetic-runs",
        headers=headers,
        body={"run_kind": run_kind},
    )
    if status != 202:
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RUN_REJECTED)
    _validate_authority_envelope(cast(dict[str, object], submitted))
    run = submitted.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("request_id"), str):
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
    request_id = cast(str, run["request_id"])
    if not _REQUEST_ID.fullmatch(request_id):
        raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
    poll_headers = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        poll_status, current = _request_json(
            "GET",
            f"{monitor_origin}/api/v1/synthetic-runs/{request_id}",
            headers=poll_headers,
        )
        if poll_status != 200:
            raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RUN_REJECTED)
        _validate_authority_envelope(cast(dict[str, object], current))
        record = current.get("run")
        if not isinstance(record, dict):
            raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RECEIPT_INVALID)
        if record.get("job_status") == "TERMINAL":
            return cast(dict[str, object], record)
        time.sleep(0.1)
    raise _SmokeError(PackagedSmokeFailureCode.SYNTHETIC_RUN_TIMEOUT)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> bool:
    if process.poll() is not None:
        return False
    try:
        completed = subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=15,
        )
        process.wait(timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _SmokeError(PackagedSmokeFailureCode.PROCESS_CLEANUP_FAILED) from exc
    if completed.returncode != 0 or process.poll() is None:
        raise _SmokeError(PackagedSmokeFailureCode.PROCESS_CLEANUP_FAILED)
    return True


class _SubprocessSmokeAdapter:
    def run_invocation(self, invocation_number: int) -> dict[str, object]:
        if invocation_number not in {1, 2}:
            raise _SmokeError(PackagedSmokeFailureCode.REQUEST_INVALID)
        before = _validate_fixed_inputs()
        try:
            root = Path(tempfile.mkdtemp(prefix=".pdu-m2-s3c-", dir=CANDIDATE_PARENT))
        except OSError as exc:
            raise _SmokeError(PackagedSmokeFailureCode.TEMP_CLEANUP_FAILED) from exc
        process: subprocess.Popen[bytes] | None = None
        primary: _SmokeError | None = None
        result: dict[str, object] | None = None
        stdout_path = root / "child.stdout.log"
        stderr_path = root / "child.stderr.log"
        try:
            exam_port = _free_port()
            monitor_port = _free_port()
            while monitor_port == exam_port:
                monitor_port = _free_port()
            environment = dict(os.environ)
            environment.update(_build_child_environment({}, root, exam_port, monitor_port))
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                    process = subprocess.Popen(
                        [str(EXECUTABLE)],
                        cwd=BUNDLE_ROOT,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        creationflags=creationflags,
                    )
                    exam_origin = f"http://127.0.0.1:{exam_port}"
                    monitor_origin = f"http://localhost:{monitor_port}"
                    _wait_for_health(f"{exam_origin}/api/v1/health")
                    _wait_for_health(f"{monitor_origin}/api/v1/health")
                    listeners = _inspect_listeners(frozenset({exam_port, monitor_port}))
                    _validate_listener_scope(listeners, frozenset({exam_port, monitor_port}))
                    token = _login(monitor_origin)
                    preflight = _submit_and_poll(
                        monitor_origin,
                        token,
                        "PREFLIGHT_60S",
                        "m2-s3c-preflight-0001",
                        30.0,
                    )
                    nominal = _submit_and_poll(
                        monitor_origin,
                        token,
                        "NOMINAL_20M",
                        "m2-s3c-nominal-0001",
                        60.0,
                    )
                    result = {
                        "browser_opened": False,
                        "camera_or_device_input_supplied": False,
                        "candidate_bytes_unchanged": True,
                        "evidence_export_invoked": False,
                        "loopback_listener_scope_verified": True,
                        "nominal": nominal,
                        "preflight": preflight,
                        "process_tree_terminated": True,
                        "reviewer_auth_verified": True,
                        "runtime_envelope_package_contains_integration": False,
                        "temporary_workspace_state": "REMOVED",
                    }
            except _SmokeError:
                raise
            except OSError as exc:
                raise _SmokeError(PackagedSmokeFailureCode.PROCESS_START_FAILED) from exc
        except _SmokeError as exc:
            primary = exc
        finally:
            cleanup_error: _SmokeError | None = None
            forced_termination: bool | None = None
            if process is not None:
                try:
                    forced_termination = _terminate_process_tree(process)
                except _SmokeError as exc:
                    cleanup_error = exc
            try:
                _safe_cleanup_root(root, CANDIDATE_PARENT)
            except _SmokeError as exc:
                cleanup_error = exc
            if cleanup_error is not None:
                primary = cleanup_error
            elif primary is None and forced_termination is not True:
                primary = _SmokeError(PackagedSmokeFailureCode.PROCESS_CLEANUP_FAILED)
        if primary is not None:
            raise primary
        if result is None:
            raise _SmokeError(PackagedSmokeFailureCode.UNEXPECTED_FAILURE)
        after = _validate_fixed_inputs()
        if after != before:
            raise _SmokeError(PackagedSmokeFailureCode.CANDIDATE_INPUT_MISMATCH)
        return result


def run_packaged_smoke() -> PackagedSyntheticSmokeReceipt:
    _validate_fixed_inputs()
    return _run_packaged_smoke_with(
        _SubprocessSmokeAdapter(), smoke_harness_revision=_load_harness_revision()
    )


def _failure_summary(code: PackagedSmokeFailureCode) -> dict[str, object]:
    return {
        "failure_code": code.value,
        "result": "PACKAGED_SYNTHETIC_RUNTIME_SMOKE_NOT_VERIFIED",
        "status": FAILURE_STATUS,
    }


def _emit(document: dict[str, object], exit_code: int) -> NoReturn:
    sys.stdout.buffer.write(_canonical_bytes(document))
    raise SystemExit(exit_code)


def main(argv: list[str] | None = None) -> NoReturn:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        _emit(_failure_summary(PackagedSmokeFailureCode.REQUEST_INVALID), 2)
    try:
        receipt = run_packaged_smoke()
    except _SmokeError as exc:
        _emit(_failure_summary(exc.code), 2)
    except Exception:
        _emit(_failure_summary(PackagedSmokeFailureCode.UNEXPECTED_FAILURE), 2)
    _emit(receipt.as_dict(), 0)


if __name__ == "__main__":
    main()
