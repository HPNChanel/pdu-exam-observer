"""Exercise the deterministic M2-S3E handoff at two same-host relocations."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_m2_s3b_candidate as base  # noqa: E402
from scripts import build_m2_s3e_handoff_pack as builder  # noqa: E402
from scripts import release_manifest  # noqa: E402

STATUS = builder.STATUS
OWNERSHIP_MARKER = ".pdu-m2-s3e-owned"
RESPONSE_LEAF = "M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.json"
PROFILES = ("PATH_WITH_SPACES", "UNICODE_PATH_WITH_SPACES")
PROJECTION_FIELDS = (
    "preflight_bundle_sha256",
    "preflight_reproduction_result_digest",
    "preflight_artifact_sha256",
    "preflight_d1_receipt_digest",
    "nominal_bundle_sha256",
    "nominal_reproduction_result_digest",
    "nominal_artifact_sha256",
    "nominal_d1_receipt_digest",
)


class SameHostPortabilityFailureCode(StrEnum):
    REQUEST_INVALID = "REQUEST_INVALID"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    HANDOFF_INPUT_MISMATCH = "HANDOFF_INPUT_MISMATCH"
    PROCESS_NOT_STANDARD_USER = "PROCESS_NOT_STANDARD_USER"
    RELOCATION_SETUP_FAILED = "RELOCATION_SETUP_FAILED"
    POWERSHELL_PROBE_FAILED = "POWERSHELL_PROBE_FAILED"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    RUN_REPRODUCIBILITY_MISMATCH = "RUN_REPRODUCIBILITY_MISMATCH"
    NETWORK_SCOPE_VIOLATION = "NETWORK_SCOPE_VIOLATION"
    AUTHORITY_CEILING_VIOLATION = "AUTHORITY_CEILING_VIOLATION"
    CANDIDATE_MUTATION_DETECTED = "CANDIDATE_MUTATION_DETECTED"
    PROCESS_CLEANUP_FAILED = "PROCESS_CLEANUP_FAILED"
    TEMP_CLEANUP_FAILED = "TEMP_CLEANUP_FAILED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


class PortabilityError(RuntimeError):
    """Bounded portability failure."""


def canonical_bytes(document: object, *, trailing_lf: bool = True) -> bytes:
    payload = json.dumps(
        document, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return payload + (b"\n" if trailing_lf else b"")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fake_digest(label: str) -> str:
    return _sha256_bytes(label.encode("utf-8"))


def authority_ceiling() -> dict[str, object]:
    return {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "candidate_package_contains_integration": True,
        "candidate_package_unchanged": True,
        "clean_environment_handoff_ready": True,
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
        "same_host_portable_verified": True,
    }


def _external_authority_ceiling() -> dict[str, object]:
    return {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "clean_machine_verified": False,
        "collection_authorized": False,
        "d1_go": False,
        "device_gate_decision": "UNVERIFIED",
        "distribution_ready": False,
        "execution_authorized": False,
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
        "release_authorized": False,
        "research_ready": False,
    }


def _gap_projection() -> list[dict[str, str]]:
    open_ids = {
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT",
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT",
    }
    ids = (
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
        "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED",
        "GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT",
        "GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT",
        "GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT",
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT",
        "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE",
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT",
    )
    return [
        {
            "gap_id": gap_id,
            "status": "OPEN" if gap_id in open_ids else "CLOSED_FOR_CURRENT_CANDIDATE",
        }
        for gap_id in ids
    ]


def canonical_recorded_projection() -> dict[str, str]:
    return {field: _fake_digest(field) for field in PROJECTION_FIELDS}


def canonical_recorded_response() -> dict[str, Any]:
    projection = canonical_recorded_projection()
    body: dict[str, object] = {
        "authority_ceiling": _external_authority_ceiling(),
        "cleanup": {
            "candidate_bytes_unchanged": True,
            "process_tree_terminated": True,
            "temporary_workspace_state": "REMOVED",
        },
        "environment_observations": {
            "air_gapped_machine_verified": False,
            "child_path_sanitized": True,
            "external_environment_classification": "UNVERIFIED_PENDING_SOURCE_IMPORT",
            "external_runtime_dependency_supplied": False,
            "network_scope": "LOOPBACK_ONLY_OBSERVED",
            "process_elevated": False,
            "windows_powershell_5_1_or_newer": True,
            "windows_x64": True,
        },
        "failure_code": None,
        "handoff_binding": {
            "handoff_manifest_sha256": _fake_digest("handoff-manifest"),
            "s3d_candidate_tree_sha256": builder.S3D_HASHES["tree_sha256"],
        },
        "projection": projection,
        "result": "CLEAN_ENVIRONMENT_PROBE_COMPLETED",
        "run_contract": {
            "candidate_process_count": 3,
            "full_cycle_count": 1,
            "nominal_observation_count": 18077,
            "preflight_observation_count": 977,
            "reproduction_count": 2,
        },
    }
    return {
        "artifact_kind": "M2_S3E_CLEAN_ENVIRONMENT_RESPONSE",
        "body": body,
        "body_sha256": _sha256_bytes(canonical_bytes(body, trailing_lf=False)),
        "schema_version": 1,
        "status": "M2_S3E_CLEAN_ENVIRONMENT_PROBE_COMPLETED_PENDING_IMPORT_VALIDATION",
    }


def validate_response(document: dict[str, Any]) -> dict[str, str]:
    body = document.get("body")
    if (
        set(document) != {"artifact_kind", "body", "body_sha256", "schema_version", "status"}
        or document.get("artifact_kind") != "M2_S3E_CLEAN_ENVIRONMENT_RESPONSE"
        or document.get("schema_version") != 1
        or document.get("status")
        != "M2_S3E_CLEAN_ENVIRONMENT_PROBE_COMPLETED_PENDING_IMPORT_VALIDATION"
        or not isinstance(body, dict)
        or document.get("body_sha256") != _sha256_bytes(canonical_bytes(body, trailing_lf=False))
    ):
        raise PortabilityError(SameHostPortabilityFailureCode.RESPONSE_INVALID)
    authority = body.get("authority_ceiling")
    environment = body.get("environment_observations")
    cleanup = body.get("cleanup")
    contract = body.get("run_contract")
    projection = body.get("projection")
    if (
        body.get("result") != "CLEAN_ENVIRONMENT_PROBE_COMPLETED"
        or body.get("failure_code") is not None
        or authority != _external_authority_ceiling()
        or not isinstance(environment, dict)
        or environment.get("network_scope") != "LOOPBACK_ONLY_OBSERVED"
        or environment.get("air_gapped_machine_verified") is not False
        or environment.get("external_environment_classification")
        != "UNVERIFIED_PENDING_SOURCE_IMPORT"
        or environment.get("process_elevated") is not False
        or environment.get("child_path_sanitized") is not True
        or environment.get("external_runtime_dependency_supplied") is not False
        or not isinstance(cleanup, dict)
        or any(
            cleanup.get(key) is not True
            for key in ("candidate_bytes_unchanged", "process_tree_terminated")
        )
        or cleanup.get("temporary_workspace_state") != "REMOVED"
        or contract
        != {
            "candidate_process_count": 3,
            "full_cycle_count": 1,
            "nominal_observation_count": 18077,
            "preflight_observation_count": 977,
            "reproduction_count": 2,
        }
        or not isinstance(projection, dict)
        or set(projection) != set(PROJECTION_FIELDS)
        or any(
            not isinstance(projection.get(field), str) or len(cast(str, projection[field])) != 64
            for field in PROJECTION_FIELDS
        )
    ):
        raise PortabilityError(SameHostPortabilityFailureCode.RESPONSE_INVALID)
    return {field: cast(str, projection[field]) for field in PROJECTION_FIELDS}


def canonical_fixed_inputs() -> dict[str, object]:
    return {
        "handoff_build_validation_sha256": _fake_digest("handoff-build-validation"),
        "handoff_manifest_sha256": _fake_digest("handoff-manifest"),
        "handoff_zip_sha256": _fake_digest("handoff-zip"),
        "s3d_binding": builder.S3D_HASHES | {"source_revision": builder.S3D_SOURCE_REVISION},
        "source_revision": builder.S3D_SOURCE_REVISION,
    }


@dataclass(frozen=True, slots=True)
class SameHostPortabilityReceipt:
    status: str
    body: dict[str, object]

    def canonical_payload(self) -> dict[str, object]:
        return dict(self.body)

    def recompute_digest(self) -> str:
        return _sha256_bytes(canonical_bytes(self.canonical_payload(), trailing_lf=False))

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact_kind": "M2_S3E_A_SAME_HOST_PORTABILITY_RECEIPT",
            "body": self.canonical_payload(),
            "body_sha256": self.recompute_digest(),
            "schema_version": 1,
            "status": self.status,
        }


class RelocationAdapter(Protocol):
    def run_relocation(self, profile: str) -> dict[str, Any]: ...


def run_with_adapter(
    adapter: RelocationAdapter, fixed_inputs: dict[str, object]
) -> SameHostPortabilityReceipt:
    responses = [adapter.run_relocation(profile) for profile in PROFILES]
    projections = [validate_response(response) for response in responses]
    encoded = [canonical_bytes(projection, trailing_lf=False) for projection in projections]
    if encoded[0] != encoded[1]:
        raise PortabilityError(SameHostPortabilityFailureCode.RUN_REPRODUCIBILITY_MISMATCH)
    projection_digest = _sha256_bytes(encoded[0])
    body: dict[str, object] = {
        "authority_ceiling": authority_ceiling(),
        "gap_projection": _gap_projection(),
        "handoff_binding": fixed_inputs,
        "observed_on": "2026-09-02",
        "relocation_a": responses[0]["body"],
        "relocation_b": responses[1]["body"],
        "relocation_contract": {
            "full_cycle_count": 2,
            "profiles": list(PROFILES),
            "relocation_count": 2,
            "retry_count": 0,
        },
        "reproducibility": {
            "byte_identical": True,
            "mismatch_fields": [],
            "relocation_a_projection_sha256": projection_digest,
            "relocation_b_projection_sha256": projection_digest,
        },
        "result": "SAME_HOST_ISOLATED_PORTABILITY_VERIFIED",
        "runtime_boundary": {
            "air_gapped_machine_verified": False,
            "candidate_bytes_unchanged": True,
            "candidate_process_count": 6,
            "child_path_sanitized": True,
            "external_runtime_dependency_supplied": False,
            "full_cycle_count": 2,
            "loopback_only_observed": True,
            "relocation_count": 2,
            "standard_user_observed": True,
            "temporary_workspaces_removed": True,
        },
        "s3d_binding": builder.S3D_HASHES | {"source_revision": builder.S3D_SOURCE_REVISION},
    }
    return SameHostPortabilityReceipt(status=STATUS, body=body)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PortabilityError(SameHostPortabilityFailureCode.TEMP_CLEANUP_FAILED) from exc
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def safe_cleanup_root(root: Path, parent: Path) -> None:
    try:
        resolved_parent = parent.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        if (
            resolved_root.parent != resolved_parent
            or _is_link_or_reparse(root)
            or not (root / OWNERSHIP_MARKER).is_file()
            or _is_link_or_reparse(root / OWNERSHIP_MARKER)
        ):
            raise PortabilityError(SameHostPortabilityFailureCode.TEMP_CLEANUP_FAILED)
        for current, dirs, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            if any(_is_link_or_reparse(current_path / name) for name in (*dirs, *files)):
                raise PortabilityError(SameHostPortabilityFailureCode.TEMP_CLEANUP_FAILED)
        shutil.rmtree(root)
    except PortabilityError:
        raise
    except OSError as exc:
        raise PortabilityError(SameHostPortabilityFailureCode.TEMP_CLEANUP_FAILED) from exc


def _candidate_records(extracted: Path) -> list[dict[str, object]]:
    records = base._tree_records(extracted)
    return [
        record
        for record in records
        if str(record["path"]) == "RELEASE_MANIFEST.json"
        or str(record["path"]).startswith("PDU-Exam-Observer/")
    ]


def _validate_extracted_candidate(extracted: Path) -> None:
    try:
        release_manifest.verify_manifest(
            extracted / "PDU-Exam-Observer",
            extracted / "PDU-Exam-Observer" / "RELEASE_MANIFEST.json",
            extracted / "RELEASE_MANIFEST.json",
        )
        digest = base._tree_digest(_candidate_records(extracted))
    except Exception as exc:
        raise PortabilityError(SameHostPortabilityFailureCode.CANDIDATE_MUTATION_DETECTED) from exc
    if digest != builder.S3D_HASHES["tree_sha256"]:
        raise PortabilityError(SameHostPortabilityFailureCode.CANDIDATE_MUTATION_DETECTED)


def _extract_handoff(root: Path) -> None:
    try:
        entries = builder.inspect_zip_bytes(builder.HANDOFF_ZIP.read_bytes())
        for name, payload in entries.items():
            target = root.joinpath(*name.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    except (OSError, builder.HandoffError) as exc:
        raise PortabilityError(SameHostPortabilityFailureCode.RELOCATION_SETUP_FAILED) from exc


class _PowerShellRelocationAdapter:
    def __init__(self, parent: Path) -> None:
        self._parent = parent

    def run_relocation(self, profile: str) -> dict[str, Any]:
        if profile not in PROFILES:
            raise PortabilityError(SameHostPortabilityFailureCode.REQUEST_INVALID)
        prefix = "S3E Path With Spaces " if profile == PROFILES[0] else "S3E Đối chiếu Unicode "
        try:
            root = Path(tempfile.mkdtemp(prefix=prefix, dir=self._parent))
            (root / OWNERSHIP_MARKER).write_text("owned\n", encoding="utf-8", newline="\n")
        except OSError as exc:
            raise PortabilityError(SameHostPortabilityFailureCode.RELOCATION_SETUP_FAILED) from exc
        primary: PortabilityError | None = None
        response: dict[str, Any] | None = None
        try:
            _extract_handoff(root)
            _validate_extracted_candidate(root)
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(root / "VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1"),
                ],
                cwd=root,
                capture_output=True,
                check=False,
                timeout=360,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            response_path = root / RESPONSE_LEAF
            response_bytes = response_path.read_bytes() if response_path.is_file() else b""
            if completed.returncode != 0 or completed.stderr or completed.stdout != response_bytes:
                raise PortabilityError(SameHostPortabilityFailureCode.POWERSHELL_PROBE_FAILED)
            try:
                parsed = json.loads(response_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PortabilityError(SameHostPortabilityFailureCode.RESPONSE_INVALID) from exc
            if not isinstance(parsed, dict) or response_bytes != canonical_bytes(parsed):
                raise PortabilityError(SameHostPortabilityFailureCode.RESPONSE_INVALID)
            response = cast(dict[str, Any], parsed)
            validate_response(response)
            _validate_extracted_candidate(root)
        except PortabilityError as exc:
            primary = exc
        except (OSError, subprocess.SubprocessError) as exc:
            primary = PortabilityError(SameHostPortabilityFailureCode.POWERSHELL_PROBE_FAILED)
            primary.__cause__ = exc
        try:
            safe_cleanup_root(root, self._parent)
        except PortabilityError as exc:
            primary = primary or exc
        if primary is not None:
            raise primary
        if response is None:
            raise PortabilityError(SameHostPortabilityFailureCode.RESPONSE_INVALID)
        return response


def _fixed_inputs() -> dict[str, object]:
    try:
        builder.check_handoff_pack()
        validation_bytes = builder.HANDOFF_VALIDATION.read_bytes()
        validation = json.loads(validation_bytes)
        zip_entries = builder.inspect_zip_bytes(builder.HANDOFF_ZIP.read_bytes())
        manifest = zip_entries["M2_S3E_HANDOFF_MANIFEST.json"]
    except Exception as exc:
        raise PortabilityError(SameHostPortabilityFailureCode.HANDOFF_INPUT_MISMATCH) from exc
    body = validation.get("body") if isinstance(validation, dict) else None
    source_revision = body.get("source_revision") if isinstance(body, dict) else None
    return {
        "handoff_build_validation_sha256": _sha256_bytes(validation_bytes),
        "handoff_manifest_sha256": _sha256_bytes(manifest),
        "handoff_zip_sha256": _sha256_bytes(builder.HANDOFF_ZIP.read_bytes()),
        "s3d_binding": builder.S3D_HASHES | {"source_revision": builder.S3D_SOURCE_REVISION},
        "source_revision": source_revision,
    }


def run_same_host_portability() -> SameHostPortabilityReceipt:
    if os.name != "nt":
        raise PortabilityError(SameHostPortabilityFailureCode.PLATFORM_UNSUPPORTED)
    fixed = _fixed_inputs()
    try:
        builder.HANDOFF_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PortabilityError(SameHostPortabilityFailureCode.RELOCATION_SETUP_FAILED) from exc
    return run_with_adapter(_PowerShellRelocationAdapter(builder.HANDOFF_ROOT), fixed)


def failure_document(code: SameHostPortabilityFailureCode) -> dict[str, object]:
    return {
        "failure_code": code.value,
        "result": "SAME_HOST_ISOLATED_PORTABILITY_NOT_VERIFIED",
        "status": None,
    }


def _emit(document: dict[str, object], exit_code: int) -> NoReturn:
    sys.stdout.buffer.write(canonical_bytes(document))
    raise SystemExit(exit_code)


def main(argv: list[str] | None = None) -> NoReturn:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        _emit(failure_document(SameHostPortabilityFailureCode.REQUEST_INVALID), 2)
    try:
        receipt = run_same_host_portability()
    except PortabilityError as exc:
        try:
            code = SameHostPortabilityFailureCode(str(exc))
        except ValueError:
            code = SameHostPortabilityFailureCode.UNEXPECTED_FAILURE
        _emit(failure_document(code), 2)
    except Exception:
        _emit(failure_document(SameHostPortabilityFailureCode.UNEXPECTED_FAILURE), 2)
    _emit(receipt.as_dict(), 0)


if __name__ == "__main__":
    main()
