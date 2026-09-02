"""Build and verify the deterministic M2-S3D round-trip candidate."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NoReturn

_IMPORT_ROOT = Path(__file__).resolve().parents[1]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from scripts import build_m2_s3b_candidate as base  # noqa: E402

ROOT = base.ROOT
PACKAGING_ROOT = ROOT / "packaging"
CANDIDATE_PARENT = PACKAGING_ROOT / "candidates"
S3B_CANDIDATE_ROOT = CANDIDATE_PARENT / "m2-s3b-current-source"
CANDIDATE_ROOT = CANDIDATE_PARENT / "m2-s3d-round-trip"
BUNDLE_ROOT = CANDIDATE_ROOT / "PDU-Exam-Observer"
DETACHED_MANIFEST = CANDIDATE_ROOT / "RELEASE_MANIFEST.json"
LOCAL_VALIDATION = CANDIDATE_ROOT / "M2_S3D_BUILD_VALIDATION.json"
CANDIDATE_SPEC = PACKAGING_ROOT / "PDU-Exam-Observer.s3d.spec"
CANDIDATE_README = PACKAGING_ROOT / "README_M2_S3D_CANDIDATE.txt"

STATUS = (
    "M2_S3D_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_"
    "ROUND_TRIP_PENDING_NO_RELEASE_AUTHORITY"
)
CONTRACT: dict[str, str] = {
    **base.CONTRACT,
    "build_time_utc": "2026-09-02T00:00:00Z",
    "product_version": "0.2.0-m2s3d-candidate",
}
REQUIRED_MODULES: tuple[str, ...] = (
    *base.REQUIRED_MODULES,
    "pdu_exam_observer.m2_packaged_reproduction",
)
README_MARKERS: tuple[str, ...] = (
    "CURRENT-SOURCE LOCAL CANDIDATE — NOT A RELEASE",
    "SYNTHETIC M2 ONLY",
    "NO CAMERA OR DEVICE VERIFICATION",
    "NO D1_GO",
    "NO PARTICIPANT COLLECTION AUTHORITY",
    "PACKAGED S2D EXPORT AND S2E REPRODUCTION ROUND-TRIP NOT YET RUN",
    "CLEAN-MACHINE PORTABILITY UNVERIFIED",
    "UNSIGNED",
)


@contextmanager
def _configured_base() -> Iterator[None]:
    names = {
        "CANDIDATE_ROOT": CANDIDATE_ROOT,
        "BUNDLE_ROOT": BUNDLE_ROOT,
        "DETACHED_MANIFEST": DETACHED_MANIFEST,
        "LOCAL_VALIDATION": LOCAL_VALIDATION,
        "CANDIDATE_SPEC": CANDIDATE_SPEC,
        "CANDIDATE_README": CANDIDATE_README,
        "CONTRACT": CONTRACT,
        "REQUIRED_MODULES": REQUIRED_MODULES,
        "README_MARKERS": README_MARKERS,
        "STATUS": STATUS,
    }
    previous = {name: getattr(base, name) for name in names}
    try:
        for name, value in names.items():
            setattr(base, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(base, name, value)


def _authority_ceiling() -> dict[str, object]:
    ceiling = base._authority_ceiling()
    ceiling["candidate_package_built"] = True
    return ceiling


def _gap_projection() -> list[dict[str, str]]:
    closed = {
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
        "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED",
        "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE",
    }
    return [
        {
            "authority_effect": "NONE",
            "gap_id": gap_id,
            "status": "CLOSED_FOR_CURRENT_CANDIDATE" if gap_id in closed else "OPEN",
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


def _receipt(
    *,
    rp2: dict[str, str],
    tree_digest: str,
    records: list[dict[str, object]],
    inventory_digest: str,
    isolated_frontend_digest: str,
    packaged_frontend_digest: str,
    readme_digest: str,
) -> dict[str, object]:
    body: dict[str, object] = {
        "authority_ceiling": _authority_ceiling(),
        "build_contract": dict(CONTRACT),
        "candidate_package": {
            "executable_sha256": base._sha256_file(BUNDLE_ROOT / "PDUExamObserver.exe"),
            "file_count": len(records),
            "manifest_sha256": base._sha256_file(DETACHED_MANIFEST),
            "root_role": "LOCAL_IGNORED_M2_S3D_ROUND_TRIP_CANDIDATE",
            "tree_sha256": tree_digest,
        },
        "frontend_inclusion": {
            "byte_identical": True,
            "isolated_tree_sha256": isolated_frontend_digest,
            "packaged_tree_sha256": packaged_frontend_digest,
        },
        "gap_projection": _gap_projection(),
        "observed_on": "2026-09-02",
        "python_runtime_inclusion": {
            "all_present": True,
            "inventory_sha256": inventory_digest,
            "inventory_source": "EXECUTABLE_RECURSIVE_ARCHIVE",
            "required_modules": list(REQUIRED_MODULES),
        },
        "readme_boundary": {"all_markers_present": True, "sha256": readme_digest},
        "reproducibility": {
            "build_a_tree_sha256": tree_digest,
            "build_b_tree_sha256": tree_digest,
            "byte_identical": True,
            "mismatch_paths": [],
        },
        "result": "S3D_CANDIDATE_PACKAGE_INTEGRATED",
        "source_revision": rp2,
    }
    return {
        "artifact_kind": "M2_S3D_CANDIDATE_BUILD_VALIDATION",
        "body": body,
        "body_sha256": base._sha256_bytes(base.canonical_json_bytes(body)),
        "schema_version": 1,
        "status": STATUS,
    }


def _validate_receipt(document: dict[str, Any]) -> dict[str, Any]:
    body = document.get("body")
    if (
        set(document) != {"artifact_kind", "body", "body_sha256", "schema_version", "status"}
        or document.get("artifact_kind") != "M2_S3D_CANDIDATE_BUILD_VALIDATION"
        or document.get("schema_version") != 1
        or document.get("status") != STATUS
        or not isinstance(body, dict)
        or document.get("body_sha256") != base._sha256_bytes(base.canonical_json_bytes(body))
    ):
        raise base.CandidateError("RECEIPT_MISMATCH")
    return document


def _candidate_records() -> list[dict[str, object]]:
    return base._tree_records(
        CANDIDATE_ROOT,
        exclude=frozenset({LOCAL_VALIDATION.name}),
    )


def check_candidate() -> dict[str, object]:
    with _configured_base():
        base._verify_historical_manifest()
        base.verify_candidate_manifest()
        validation = _validate_receipt(base._strict_json(LOCAL_VALIDATION, "RECEIPT_MISMATCH"))
        body = validation["body"]
        if not isinstance(body, dict) or body.get("source_revision") != base._load_rp2():
            raise base.CandidateError("RP2_INVALID")
        records = _candidate_records()
        digest = base._tree_digest(records)
        reproducibility = body.get("reproducibility")
        if not isinstance(reproducibility, dict) or any(
            reproducibility.get(key) != digest
            for key in ("build_a_tree_sha256", "build_b_tree_sha256")
        ):
            raise base.CandidateError("BUILD_REPRODUCIBILITY_MISMATCH")
        _, inventory_digest = base._validate_archive(BUNDLE_ROOT / "PDUExamObserver.exe")
        inclusion = body.get("python_runtime_inclusion")
        if not isinstance(inclusion, dict) or inclusion.get("inventory_sha256") != inventory_digest:
            raise base.CandidateError("ARCHIVE_INVENTORY_INVALID")
        frontend_digest = base._tree_digest(base._frontend_records(BUNDLE_ROOT))
        frontend = body.get("frontend_inclusion")
        if not isinstance(frontend, dict) or any(
            frontend.get(key) != frontend_digest
            for key in ("isolated_tree_sha256", "packaged_tree_sha256")
        ):
            raise base.CandidateError("FRONTEND_INCLUSION_MISMATCH")
        base._validate_readme(BUNDLE_ROOT)
        base._s3a_immutable_inputs()
    return {"failure_code": None, "result": "S3D_CANDIDATE_PACKAGE_INTEGRATED", "status": STATUS}


def build_candidate() -> dict[str, object]:
    with _configured_base():
        source = base.source_binding_snapshot()
        base._verify_historical_manifest()
        base._verify_toolchain()
        CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".pdu-m2-s3d-build-", dir=CANDIDATE_PARENT))
        try:
            frontend_dist = temporary / "frontend-dist"
            base._build_frontend(frontend_dist)
            isolated_digest = base._tree_digest(base._tree_records(frontend_dist))
            tool_python, viewer = base._prepare_tool_environment(temporary)
            rp2_value = source.get("rp2")
            if not isinstance(rp2_value, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in rp2_value.items()
            ):
                raise base.CandidateError("RP2_INVALID")
            rp2 = {str(key): str(value) for key, value in rp2_value.items()}
            first = base._build_one(
                label="build-a",
                temp_root=temporary,
                tool_python=tool_python,
                frontend_dist=frontend_dist,
                rp2=rp2,
            )
            second = base._build_one(
                label="build-b",
                temp_root=temporary,
                tool_python=tool_python,
                frontend_dist=frontend_dist,
                rp2=rp2,
            )
            first_records = base._stage_records(first)
            second_records = base._stage_records(second)
            if first_records != second_records:
                raise base.CandidateError("BUILD_REPRODUCIBILITY_MISMATCH")
            tree_digest = base._tree_digest(first_records)
            _, inventory_digest = base._validate_archive(
                first.bundle / "PDUExamObserver.exe", viewer
            )
            first_frontend = base._tree_digest(base._frontend_records(first.bundle))
            second_frontend = base._tree_digest(base._frontend_records(second.bundle))
            if first_frontend != isolated_digest or second_frontend != isolated_digest:
                raise base.CandidateError("FRONTEND_INCLUSION_MISMATCH")
            readme_digest = base._validate_readme(first.bundle)
            base._validate_readme(second.bundle)
            stage = temporary / "candidate-stage"
            stage.mkdir()
            shutil.copytree(first.bundle, stage / "PDU-Exam-Observer")
            shutil.copy2(first.detached_manifest, stage / "RELEASE_MANIFEST.json")
            staged_records = base._tree_records(stage)
            if staged_records != first_records:
                raise base.CandidateError("BUILD_REPRODUCIBILITY_MISMATCH")
            if CANDIDATE_ROOT.exists():
                if _candidate_records() != staged_records:
                    raise base.CandidateError("CANDIDATE_EXISTS_MISMATCH")
            else:
                os.replace(stage, CANDIDATE_ROOT)
            receipt = _receipt(
                rp2=rp2,
                tree_digest=tree_digest,
                records=first_records,
                inventory_digest=inventory_digest,
                isolated_frontend_digest=isolated_digest,
                packaged_frontend_digest=first_frontend,
                readme_digest=readme_digest,
            )
            base._write_atomic(LOCAL_VALIDATION, base.canonical_json_bytes(receipt))
        except base.CandidateError:
            raise
        except OSError as exc:
            raise base.CandidateError("OUTPUT_WRITE_FAILED") from exc
        finally:
            try:
                shutil.rmtree(temporary)
            except OSError as exc:
                raise base.CandidateError("CLEANUP_FAILED") from exc
    return check_candidate()


def _failure(code: str) -> dict[str, object]:
    return {"failure_code": code, "result": "S3D_CANDIDATE_PACKAGE_NOT_VERIFIED", "status": None}


def _emit(document: dict[str, object], exit_code: int) -> NoReturn:
    sys.stdout.buffer.write(base.canonical_json_bytes(document))
    raise SystemExit(exit_code)


def main(argv: list[str] | None = None) -> NoReturn:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments not in ([], ["--check"], ["--build"]):
        _emit(_failure("REQUEST_INVALID"), 2)
    try:
        result = build_candidate() if arguments == ["--build"] else check_candidate()
    except base.CandidateError as exc:
        _emit(_failure(exc.code), 2)
    except Exception:
        _emit(_failure("UNEXPECTED_FAILURE"), 2)
    _emit(result, 0)


if __name__ == "__main__":
    main()
