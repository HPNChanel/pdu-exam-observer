"""Run the fixed packaged S2D export and S2E reproduction round-trip."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn, Protocol, cast

_IMPORT_ROOT = Path(__file__).resolve().parents[1]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from pdu_exam_observer.m2_synthetic_evidence import (  # noqa: E402
    MAX_EVIDENCE_BYTES,
    load_verified_synthetic_evidence_bytes,
)
from scripts import build_m2_s3d_candidate as builder  # noqa: E402
from scripts import run_m2_s3c_packaged_smoke as smoke  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PARENT = ROOT / "packaging" / "candidates"
CANDIDATE_ROOT = CANDIDATE_PARENT / "m2-s3d-round-trip"
BUNDLE_ROOT = CANDIDATE_ROOT / "PDU-Exam-Observer"
EXECUTABLE = BUNDLE_ROOT / "PDUExamObserver.exe"
LOCAL_VALIDATION = CANDIDATE_ROOT / "M2_S3D_BUILD_VALIDATION.json"
S3B_RECEIPT = ROOT / "docs" / "ai" / "M2_S3B_PACKAGE_INTEGRATION.json"
S3C_RECEIPT = ROOT / "docs" / "ai" / "M2_S3C_PACKAGED_SYNTHETIC_SMOKE.json"
REPRODUCTION_RUNTIME_MODE = "m2synthetic-reproduce"
REVIEWER_PIN = "m2-s3d-round-trip-process-only"
STATUS = (
    "M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_LOCALLY_VERIFIED_"
    "SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)
FAILURE_STATUS = "M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_NOT_VERIFIED"
HISTORICAL_RECEIPT_SHA256 = {
    "s3b": "bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd",
    "s3c": "479aa2e364216a8f4560fbf98a31a6935829d847dfbace65f7c66fae8778bbb7",
}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_REPRODUCTION_RECEIPT_FIELDS = frozenset(
    {
        "artifact_kind",
        "authority_status",
        "classification",
        "collection_authorized",
        "current_environment_binding_digest",
        "d1_go",
        "device_gate_decision",
        "evidence_kind",
        "execution_authorized",
        "failure_code",
        "mismatch_fields",
        "package_contains_integration",
        "participant_collection_authorized",
        "physical_camera_access_authorized",
        "production_reconciler_implemented",
        "production_reconciler_real_storage_verified",
        "real_data_deletion_authorized",
        "reproduced_artifact_sha256",
        "reproduced_bundle_sha256",
        "reproduced_d1_failure_code",
        "reproduced_d1_outcome",
        "reproduced_d1_receipt_digest",
        "reproduced_observation_count",
        "reproduced_observation_digest",
        "reproduced_result_digest",
        "research_ready",
        "result_digest",
        "run_kind",
        "schema_version",
        "source_artifact_sha256",
        "source_bundle_sha256",
        "source_d1_failure_code",
        "source_d1_outcome",
        "source_d1_receipt_digest",
        "source_environment_binding_digest",
        "source_observation_count",
        "source_observation_digest",
        "source_result_digest",
        "status",
        "temporary_workspace_state",
    }
)


class RoundTripFailureCode(StrEnum):
    REQUEST_INVALID = "REQUEST_INVALID"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    HISTORICAL_EVIDENCE_MISMATCH = "HISTORICAL_EVIDENCE_MISMATCH"
    CANDIDATE_INPUT_MISMATCH = "CANDIDATE_INPUT_MISMATCH"
    PROCESS_START_FAILED = "PROCESS_START_FAILED"
    HEALTH_TIMEOUT = "HEALTH_TIMEOUT"
    LOOPBACK_SCOPE_VIOLATION = "LOOPBACK_SCOPE_VIOLATION"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    SYNTHETIC_RUN_REJECTED = "SYNTHETIC_RUN_REJECTED"
    SYNTHETIC_RUN_TIMEOUT = "SYNTHETIC_RUN_TIMEOUT"
    EVIDENCE_EXPORT_REJECTED = "EVIDENCE_EXPORT_REJECTED"
    EVIDENCE_BUNDLE_INVALID = "EVIDENCE_BUNDLE_INVALID"
    REPRODUCTION_PROCESS_FAILED = "REPRODUCTION_PROCESS_FAILED"
    REPRODUCTION_RECEIPT_INVALID = "REPRODUCTION_RECEIPT_INVALID"
    REPRODUCIBILITY_MISMATCH = "REPRODUCIBILITY_MISMATCH"
    AUTHORITY_CEILING_VIOLATION = "AUTHORITY_CEILING_VIOLATION"
    PROCESS_CLEANUP_FAILED = "PROCESS_CLEANUP_FAILED"
    TEMP_CLEANUP_FAILED = "TEMP_CLEANUP_FAILED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


class _RoundTripError(RuntimeError):
    def __init__(self, code: RoundTripFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


def _canonical(document: object, *, trailing_lf: bool = True) -> bytes:
    suffix = "\n" if trailing_lf else ""
    return (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + suffix
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise _RoundTripError(RoundTripFailureCode.CANDIDATE_INPUT_MISMATCH) from exc


def round_trip_contract() -> dict[str, object]:
    return {
        "cycle_count": 2,
        "process_count": 6,
        "reproduction_runtime_mode": REPRODUCTION_RUNTIME_MODE,
        "retry_count": 0,
        "run_order": ["PREFLIGHT_60S", "NOMINAL_20M"],
    }


def authority_ceiling() -> dict[str, object]:
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
        "packaged_evidence_round_trip_verified": True,
        "packaged_runtime_smoke_verified": True,
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
        "production_reconciler_implemented": False,
        "production_reconciler_real_storage_verified": False,
        "real_data_deletion_authorized": False,
        "release_authorized": False,
        "research_ready": False,
        "same_host_portable_verified": False,
    }


def _gap_projection() -> list[dict[str, str]]:
    open_ids = {
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT",
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT",
    }
    return [
        {
            "gap_id": gap_id,
            "status": "OPEN" if gap_id in open_ids else "CLOSED_FOR_CURRENT_CANDIDATE",
        }
        for gap_id in (
            "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
            "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED",
            "GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT",
            "GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT",
            "GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT",
            "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT",
            "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE",
            "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT",
        )
    ]


def _fake_digest(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def canonical_recorded_cycle() -> dict[str, object]:
    return {
        run: {
            "artifact_sha256": _fake_digest(f"{run}-artifact"),
            "bundle_sha256": _fake_digest(f"{run}-bundle"),
            "d1_receipt_digest": _fake_digest(f"{run}-d1"),
            "reproduction_result_digest": _fake_digest(f"{run}-reproduction"),
        }
        for run in ("preflight", "nominal")
    }


def project_cycle(cycle: dict[str, object]) -> dict[str, str]:
    projection: dict[str, str] = {}
    for run in ("preflight", "nominal"):
        value = cycle.get(run)
        if not isinstance(value, dict):
            raise _RoundTripError(RoundTripFailureCode.EVIDENCE_BUNDLE_INVALID)
        for source, target in (
            ("artifact_sha256", f"{run}_artifact_sha256"),
            ("bundle_sha256", f"{run}_bundle_sha256"),
            ("d1_receipt_digest", f"{run}_d1_receipt_digest"),
            ("reproduction_result_digest", f"{run}_reproduction_result_digest"),
        ):
            item = value.get(source)
            if not isinstance(item, str) or not _HEX64.fullmatch(item):
                raise _RoundTripError(RoundTripFailureCode.EVIDENCE_BUNDLE_INVALID)
            projection[target] = item
    return projection


def failure_document(code: RoundTripFailureCode) -> dict[str, object]:
    return {
        "failure_code": code.value,
        "result": "PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_NOT_VERIFIED",
        "status": FAILURE_STATUS,
    }


def _safe_cleanup_root(root: Path, parent: Path) -> None:
    try:
        resolved_parent = parent.resolve(strict=True)
        resolved_root = root.resolve(strict=False)
    except OSError as exc:
        raise _RoundTripError(RoundTripFailureCode.TEMP_CLEANUP_FAILED) from exc
    if (
        resolved_root.parent != resolved_parent
        or not resolved_root.name.startswith(".pdu-m2-s3d-")
        or not resolved_root.exists()
        or smoke._is_link_or_reparse(resolved_root)
    ):
        raise _RoundTripError(RoundTripFailureCode.TEMP_CLEANUP_FAILED)
    try:
        shutil.rmtree(resolved_root)
    except OSError as exc:
        raise _RoundTripError(RoundTripFailureCode.TEMP_CLEANUP_FAILED) from exc
    if resolved_root.exists():
        raise _RoundTripError(RoundTripFailureCode.TEMP_CLEANUP_FAILED)


def _validate_fixed_inputs() -> dict[str, str]:
    if (
        _sha256_file(S3B_RECEIPT) != HISTORICAL_RECEIPT_SHA256["s3b"]
        or _sha256_file(S3C_RECEIPT) != HISTORICAL_RECEIPT_SHA256["s3c"]
    ):
        raise _RoundTripError(RoundTripFailureCode.HISTORICAL_EVIDENCE_MISMATCH)
    try:
        builder.check_candidate()
        validation = json.loads(LOCAL_VALIDATION.read_bytes())
    except Exception as exc:
        raise _RoundTripError(RoundTripFailureCode.CANDIDATE_INPUT_MISMATCH) from exc
    if not isinstance(validation, dict) or not isinstance(validation.get("body"), dict):
        raise _RoundTripError(RoundTripFailureCode.CANDIDATE_INPUT_MISMATCH)
    body = cast(dict[str, object], validation["body"])
    candidate = body.get("candidate_package")
    if not isinstance(candidate, dict):
        raise _RoundTripError(RoundTripFailureCode.CANDIDATE_INPUT_MISMATCH)
    return {
        "build_validation_sha256": _sha256_file(LOCAL_VALIDATION),
        "executable_sha256": _sha256_file(EXECUTABLE),
        "manifest_sha256": _sha256_file(CANDIDATE_ROOT / "RELEASE_MANIFEST.json"),
        "tree_sha256": str(candidate.get("tree_sha256")),
    }


def _download_evidence(origin: str, token: str, request_id: str) -> bytes:
    request = urllib.request.Request(
        f"{origin}/api/v1/synthetic-runs/{request_id}/evidence",
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = cast(bytes, response.read(MAX_EVIDENCE_BYTES + 1))
            header_digest = response.headers.get("X-PDU-Evidence-SHA256")
            status = response.status
    except (OSError, urllib.error.URLError) as exc:
        raise _RoundTripError(RoundTripFailureCode.EVIDENCE_EXPORT_REJECTED) from exc
    if (
        status != 200
        or len(payload) > MAX_EVIDENCE_BYTES
        or header_digest != _sha256_bytes(payload)
    ):
        raise _RoundTripError(RoundTripFailureCode.EVIDENCE_EXPORT_REJECTED)
    try:
        load_verified_synthetic_evidence_bytes(payload)
    except Exception as exc:
        raise _RoundTripError(RoundTripFailureCode.EVIDENCE_BUNDLE_INVALID) from exc
    return payload


def _login(origin: str) -> str:
    status, payload = smoke._request_json(
        "POST",
        f"{origin}/api/v1/reviewer/login",
        headers={"Content-Type": "application/json", "Origin": origin},
        body={"pin": REVIEWER_PIN},
    )
    token = payload.get("access_token")
    if status != 200 or not isinstance(token, str) or not token:
        raise _RoundTripError(RoundTripFailureCode.AUTHENTICATION_FAILED)
    return token


def _reproduce(payload: bytes, root: Path) -> dict[str, object]:
    environment = dict(os.environ)
    environment.update(
        {
            "PDU_RUNTIME_MODE": REPRODUCTION_RUNTIME_MODE,
            "TEMP": str(root.resolve()),
            "TMP": str(root.resolve()),
        }
    )
    try:
        completed = subprocess.run(
            [str(EXECUTABLE)],
            cwd=BUNDLE_ROOT,
            env=environment,
            input=payload,
            capture_output=True,
            check=False,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _RoundTripError(RoundTripFailureCode.REPRODUCTION_PROCESS_FAILED) from exc
    try:
        document = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _RoundTripError(RoundTripFailureCode.REPRODUCTION_RECEIPT_INVALID) from exc
    source = load_verified_synthetic_evidence_bytes(payload)
    digest_payload = dict(document) if isinstance(document, dict) else {}
    observed_result_digest = digest_payload.pop("result_digest", None)
    expected_source = {
        "source_artifact_sha256": source.artifact_sha256,
        "source_bundle_sha256": source.bundle_sha256,
        "source_d1_failure_code": (
            source.d1_failure_code.value if source.d1_failure_code else None
        ),
        "source_d1_outcome": source.d1_outcome.value,
        "source_d1_receipt_digest": source.d1_receipt_digest,
        "source_environment_binding_digest": source.environment_binding_digest,
        "source_observation_count": source.observation_count,
        "source_observation_digest": source.observation_digest,
        "source_result_digest": source.source_result_digest,
    }
    paired_fields = (
        ("source_artifact_sha256", "reproduced_artifact_sha256"),
        ("source_bundle_sha256", "reproduced_bundle_sha256"),
        ("source_d1_failure_code", "reproduced_d1_failure_code"),
        ("source_d1_outcome", "reproduced_d1_outcome"),
        ("source_d1_receipt_digest", "reproduced_d1_receipt_digest"),
        ("source_observation_count", "reproduced_observation_count"),
        ("source_observation_digest", "reproduced_observation_digest"),
        ("source_result_digest", "reproduced_result_digest"),
    )
    false_authority = (
        "collection_authorized",
        "d1_go",
        "execution_authorized",
        "package_contains_integration",
        "participant_collection_authorized",
        "physical_camera_access_authorized",
        "production_reconciler_implemented",
        "production_reconciler_real_storage_verified",
        "real_data_deletion_authorized",
        "research_ready",
    )
    if (
        completed.returncode != 0
        or completed.stderr
        or not isinstance(document, dict)
        or completed.stdout != _canonical(document)
        or set(document) != _REPRODUCTION_RECEIPT_FIELDS
        or observed_result_digest != _sha256_bytes(_canonical(digest_payload, trailing_lf=False))
        or document.get("classification") != "EXACTLY_REPRODUCED"
        or document.get("failure_code") is not None
        or document.get("mismatch_fields") != []
        or document.get("temporary_workspace_state") != "REMOVED"
        or document.get("artifact_kind")
        != "M2_SYNTHETIC_EVIDENCE_REPRODUCTION_RECEIPT"
        or document.get("schema_version") != 1
        or document.get("evidence_kind") != "SIMULATED"
        or document.get("device_gate_decision") != "UNVERIFIED"
        or document.get("authority_status") != "AUTHORITY_NOT_ISSUED"
        or any(document.get(key) is not False for key in false_authority)
        or any(document.get(key) != value for key, value in expected_source.items())
        or any(
            document.get(source_key) != document.get(reproduced_key)
            for source_key, reproduced_key in paired_fields
        )
    ):
        raise _RoundTripError(RoundTripFailureCode.REPRODUCTION_RECEIPT_INVALID)
    return cast(dict[str, object], document)


class _CycleAdapter(Protocol):
    def run_cycle(self, cycle_number: int) -> dict[str, object]: ...


class _SubprocessCycleAdapter:
    def run_cycle(self, cycle_number: int) -> dict[str, object]:
        if cycle_number not in {1, 2}:
            raise _RoundTripError(RoundTripFailureCode.REQUEST_INVALID)
        before = _validate_fixed_inputs()
        try:
            root = Path(tempfile.mkdtemp(prefix=".pdu-m2-s3d-", dir=CANDIDATE_PARENT))
        except OSError as exc:
            raise _RoundTripError(RoundTripFailureCode.TEMP_CLEANUP_FAILED) from exc
        process: subprocess.Popen[bytes] | None = None
        primary: _RoundTripError | None = None
        result: dict[str, object] | None = None
        try:
            exam_port = smoke._free_port()
            monitor_port = smoke._free_port()
            while monitor_port == exam_port:
                monitor_port = smoke._free_port()
            environment = dict(os.environ)
            environment.update(
                {
                    "PDU_EXAM_PORT": str(exam_port),
                    "PDU_MONITOR_PORT": str(monitor_port),
                    "PDU_OPEN_BROWSER": "0",
                    "PDU_REVIEWER_PIN": REVIEWER_PIN,
                    "PDU_RUNTIME_MODE": "m2synthetic",
                    "TEMP": str(root.resolve()),
                    "TMP": str(root.resolve()),
                }
            )
            try:
                with (root / "child.stdout.log").open("wb") as stdout, (
                    root / "child.stderr.log"
                ).open("wb") as stderr:
                    process = subprocess.Popen(
                        [str(EXECUTABLE)],
                        cwd=BUNDLE_ROOT,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    exam_origin = f"http://127.0.0.1:{exam_port}"
                    monitor_origin = f"http://localhost:{monitor_port}"
                    smoke._wait_for_health(f"{exam_origin}/api/v1/health")
                    smoke._wait_for_health(f"{monitor_origin}/api/v1/health")
                    expected_ports = frozenset({exam_port, monitor_port})
                    smoke._validate_listener_scope(
                        smoke._inspect_listeners(expected_ports), expected_ports
                    )
                    token = _login(monitor_origin)
                    preflight_record = smoke._submit_and_poll(
                        monitor_origin,
                        token,
                        "PREFLIGHT_60S",
                        "m2-s3d-preflight-0001",
                        30.0,
                    )
                    nominal_record = smoke._submit_and_poll(
                        monitor_origin,
                        token,
                        "NOMINAL_20M",
                        "m2-s3d-nominal-0001",
                        60.0,
                    )
                    preflight_projection = smoke._project_terminal_run(
                        preflight_record,
                        expected_kind="PREFLIGHT_60S",
                        expected_sequence=1,
                        expected_count=977,
                    )
                    nominal_projection = smoke._project_terminal_run(
                        nominal_record,
                        expected_kind="NOMINAL_20M",
                        expected_sequence=2,
                        expected_count=18077,
                    )
                    preflight_payload = _download_evidence(
                        monitor_origin, token, cast(str, preflight_record["request_id"])
                    )
                    nominal_payload = _download_evidence(
                        monitor_origin, token, cast(str, nominal_record["request_id"])
                    )
                if process is None or smoke._terminate_process_tree(process) is not True:
                    raise _RoundTripError(RoundTripFailureCode.PROCESS_CLEANUP_FAILED)
                process = None
                if smoke._inspect_listeners(expected_ports):
                    raise _RoundTripError(RoundTripFailureCode.PROCESS_CLEANUP_FAILED)
                preflight_reproduction = _reproduce(preflight_payload, root)
                nominal_reproduction = _reproduce(nominal_payload, root)
                if smoke._inspect_listeners(expected_ports):
                    raise _RoundTripError(RoundTripFailureCode.LOOPBACK_SCOPE_VIOLATION)
                result = {
                    "preflight": {
                        "artifact_sha256": preflight_projection["artifact_sha256"],
                        "bundle_sha256": _sha256_bytes(preflight_payload),
                        "d1_receipt_digest": preflight_projection["d1_receipt_digest"],
                        "reproduction_result_digest": preflight_reproduction["result_digest"],
                    },
                    "nominal": {
                        "artifact_sha256": nominal_projection["artifact_sha256"],
                        "bundle_sha256": _sha256_bytes(nominal_payload),
                        "d1_receipt_digest": nominal_projection["d1_receipt_digest"],
                        "reproduction_result_digest": nominal_reproduction["result_digest"],
                    },
                    "process_tree_terminated": True,
                    "temporary_workspace_state": "REMOVED",
                }
            except smoke._SmokeError as exc:
                mapping = {
                    smoke.PackagedSmokeFailureCode.HEALTH_TIMEOUT: (
                        RoundTripFailureCode.HEALTH_TIMEOUT
                    ),
                    smoke.PackagedSmokeFailureCode.LOOPBACK_SCOPE_VIOLATION: (
                        RoundTripFailureCode.LOOPBACK_SCOPE_VIOLATION
                    ),
                    smoke.PackagedSmokeFailureCode.AUTHENTICATION_FAILED: (
                        RoundTripFailureCode.AUTHENTICATION_FAILED
                    ),
                    smoke.PackagedSmokeFailureCode.SYNTHETIC_RUN_TIMEOUT: (
                        RoundTripFailureCode.SYNTHETIC_RUN_TIMEOUT
                    ),
                }
                code = mapping.get(exc.code, RoundTripFailureCode.SYNTHETIC_RUN_REJECTED)
                raise _RoundTripError(code) from exc
            except _RoundTripError:
                raise
            except OSError as exc:
                raise _RoundTripError(RoundTripFailureCode.PROCESS_START_FAILED) from exc
        except _RoundTripError as exc:
            primary = exc
        finally:
            cleanup_error: _RoundTripError | None = None
            if process is not None:
                try:
                    smoke._terminate_process_tree(process)
                except smoke._SmokeError:
                    cleanup_error = _RoundTripError(RoundTripFailureCode.PROCESS_CLEANUP_FAILED)
            try:
                _safe_cleanup_root(root, CANDIDATE_PARENT)
            except _RoundTripError as exc:
                cleanup_error = exc
            if cleanup_error is not None:
                primary = cleanup_error
        if primary is not None:
            raise primary
        if result is None or _validate_fixed_inputs() != before:
            raise _RoundTripError(RoundTripFailureCode.CANDIDATE_INPUT_MISMATCH)
        return result


@dataclass(frozen=True, slots=True)
class PackagedRoundTripReceipt:
    body: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact_kind": "M2_S3D_PACKAGED_EVIDENCE_ROUND_TRIP_RECEIPT",
            "body": self.body,
            "body_sha256": _sha256_bytes(_canonical(self.body, trailing_lf=False)),
            "schema_version": 1,
            "status": STATUS,
        }


def _run_with(adapter: _CycleAdapter) -> PackagedRoundTripReceipt:
    fixed = _validate_fixed_inputs()
    first = adapter.run_cycle(1)
    second = adapter.run_cycle(2)
    first_projection = project_cycle(first)
    second_projection = project_cycle(second)
    first_digest = _sha256_bytes(_canonical(first_projection, trailing_lf=False))
    second_digest = _sha256_bytes(_canonical(second_projection, trailing_lf=False))
    if first_projection != second_projection:
        raise _RoundTripError(RoundTripFailureCode.REPRODUCIBILITY_MISMATCH)
    body: dict[str, object] = {
        "authority_ceiling": authority_ceiling(),
        "candidate_binding": fixed,
        "cycle_a": first,
        "cycle_b": second,
        "gap_projection": _gap_projection(),
        "historical_receipts": dict(HISTORICAL_RECEIPT_SHA256),
        "observed_on": "2026-09-02",
        "reproducibility": {
            "byte_identical": True,
            "cycle_a_projection_sha256": first_digest,
            "cycle_b_projection_sha256": second_digest,
            "mismatch_fields": [],
        },
        "result": "PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_VERIFIED",
        "round_trip_contract": round_trip_contract(),
        "runtime_boundary": {
            "browser_opened": False,
            "camera_or_device_input_supplied": False,
            "candidate_process_count": 6,
            "candidate_processes_terminated": True,
            "evidence_export_invoked": True,
            "loopback_only": True,
            "temporary_workspace_state": "REMOVED",
        },
    }
    return PackagedRoundTripReceipt(body)


def run_packaged_round_trip() -> PackagedRoundTripReceipt:
    return _run_with(_SubprocessCycleAdapter())


def _emit(document: dict[str, object], exit_code: int) -> NoReturn:
    sys.stdout.buffer.write(_canonical(document))
    raise SystemExit(exit_code)


def main(argv: list[str] | None = None) -> NoReturn:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        _emit(failure_document(RoundTripFailureCode.REQUEST_INVALID), 2)
    try:
        receipt = run_packaged_round_trip()
    except _RoundTripError as exc:
        _emit(failure_document(exc.code), 2)
    except Exception:
        _emit(failure_document(RoundTripFailureCode.UNEXPECTED_FAILURE), 2)
    _emit(receipt.as_dict(), 0)


if __name__ == "__main__":
    main()
