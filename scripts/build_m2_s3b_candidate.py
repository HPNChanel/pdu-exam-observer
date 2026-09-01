"""Build and verify the deterministic M2-S3B current-source package candidate."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
PACKAGING_ROOT = ROOT / "packaging"
CANDIDATE_PARENT = PACKAGING_ROOT / "candidates"
CANDIDATE_ROOT = CANDIDATE_PARENT / "m2-s3b-current-source"
BUNDLE_ROOT = CANDIDATE_ROOT / "PDU-Exam-Observer"
DETACHED_MANIFEST = CANDIDATE_ROOT / "RELEASE_MANIFEST.json"
LOCAL_VALIDATION = CANDIDATE_ROOT / "M2_S3B_BUILD_VALIDATION.json"
AI_RECEIPT = ROOT / "docs" / "ai" / "M2_S3B_PACKAGE_INTEGRATION.json"
S3A_AUDIT = ROOT / "docs" / "ai" / "M2_S3A_PACKAGE_GAP_AUDIT.json"
RP2_CANDIDATE = ROOT / "docs" / "spec" / "M2_D1_N2_STATIC_BINDING_CANDIDATE.json"
RP2_SCHEMA = ROOT / "docs" / "spec" / "M2_D1_N2_AUTHORITY_BINDING.schema.json"
CANDIDATE_SPEC = PACKAGING_ROOT / "PDU-Exam-Observer.current-source.spec"
CANDIDATE_README = PACKAGING_ROOT / "README_M2_S3B_CANDIDATE.txt"
ENTRY_SCRIPT = ROOT / "src" / "pdu_exam_observer" / "__main__.py"
DEMO_DIR = ROOT / "demo"
WEB_ROOT = ROOT / "apps" / "web"
RELEASE_MANIFEST_SCRIPT = ROOT / "scripts" / "release_manifest.py"

STATUS = (
    "M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_"
    "STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY"
)
S3A_AUDIT_SHA256 = "a63c0fefa7c7aba37685ccb65bec7fd605448e42873d5d8252975a82ea9269e5"
CANDIDATE_SOURCE_REVISION: dict[str, str] = {
    "binding_schema_exact_bytes_sha256": (
        "eb0a3df699c5a60a47e6419876fee64a7003ea7afa628ec746f01d180fe1a3c8"
    ),
    "candidate_exact_bytes_sha256": (
        "d6c523d74f3188a43f060721073c3671ade0a6fa20e15fde583b6eeb84735d10"
    ),
    "static_bindings_digest": (
        "e1ab400a388df7c573a177494a46de9af07c85e62ca0f1c95c4a5c3c9211d626"
    ),
}
CONTRACT: dict[str, str] = {
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
REQUIRED_MODULES: tuple[str, ...] = (
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
)
README_MARKERS: tuple[str, ...] = (
    "CURRENT-SOURCE LOCAL CANDIDATE — NOT A RELEASE",
    "SYNTHETIC M2 ONLY",
    "NO CAMERA OR DEVICE VERIFICATION",
    "NO D1_GO",
    "NO PARTICIPANT COLLECTION AUTHORITY",
    "PACKAGED RUNTIME SMOKE NOT YET RUN",
    "CLEAN-MACHINE PORTABILITY UNVERIFIED",
    "UNSIGNED",
)
FAILURE_CODES = frozenset(
    {
        "REQUEST_INVALID",
        "PLATFORM_UNSUPPORTED",
        "SOURCE_INPUT_MISMATCH",
        "HISTORICAL_PACKAGE_MISMATCH",
        "RP2_INVALID",
        "TOOLCHAIN_UNAVAILABLE",
        "TOOLCHAIN_MISMATCH",
        "FRONTEND_BUILD_FAILED",
        "PYINSTALLER_BUILD_FAILED",
        "ARCHIVE_INVENTORY_INVALID",
        "PYTHON_RUNTIME_INCLUSION_MISMATCH",
        "FRONTEND_INCLUSION_MISMATCH",
        "BUILD_REPRODUCIBILITY_MISMATCH",
        "CANDIDATE_README_INVALID",
        "CANDIDATE_EXISTS_MISMATCH",
        "MANIFEST_MISMATCH",
        "RECEIPT_MISMATCH",
        "OUTPUT_WRITE_FAILED",
        "CLEANUP_FAILED",
        "UNEXPECTED_FAILURE",
    }
)


class CandidateError(RuntimeError):
    """Bounded S3B failure."""

    def __init__(self, code: str) -> None:
        if code not in FAILURE_CODES:
            code = "UNEXPECTED_FAILURE"
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class BuildTree:
    root: Path
    bundle: Path
    detached_manifest: Path


def canonical_json_bytes(document: object) -> bytes:
    return (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise CandidateError("SOURCE_INPUT_MISMATCH") from exc
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _safe_relative(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise CandidateError("SOURCE_INPUT_MISMATCH")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise CandidateError("SOURCE_INPUT_MISMATCH")
    if parsed.as_posix() != value:
        raise CandidateError("SOURCE_INPUT_MISMATCH")
    return value


def _strict_json(
    path: Path, failure_code: str, *, canonical_required: bool = True
) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise CandidateError(failure_code)
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateError(failure_code) from exc
    if not isinstance(value, dict) or (canonical_required and raw != canonical_json_bytes(value)):
        raise CandidateError(failure_code)
    return value


def _tree_records(root: Path, *, exclude: frozenset[str] = frozenset()) -> list[dict[str, object]]:
    if not root.is_dir() or _is_link_or_reparse(root):
        raise CandidateError("SOURCE_INPUT_MISMATCH")
    records: list[dict[str, object]] = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in dirs:
            if _is_link_or_reparse(current_path / name):
                raise CandidateError("SOURCE_INPUT_MISMATCH")
        for name in files:
            path = current_path / name
            if _is_link_or_reparse(path):
                raise CandidateError("SOURCE_INPUT_MISMATCH")
            relative = _safe_relative(path.relative_to(root).as_posix())
            if relative in exclude:
                continue
            records.append(
                {"path": relative, "sha256": _sha256_file(path), "size": path.stat().st_size}
            )
    records.sort(key=lambda item: str(item["path"]))
    return records


def _tree_digest(records: list[dict[str, object]]) -> str:
    return _sha256_bytes(canonical_json_bytes(records))


def contract_snapshot() -> dict[str, str]:
    return dict(CONTRACT)


def required_modules() -> tuple[str, ...]:
    return REQUIRED_MODULES


def required_readme_markers() -> tuple[str, ...]:
    return README_MARKERS


def _load_rp2() -> dict[str, str]:
    candidate = _strict_json(RP2_CANDIDATE, "RP2_INVALID", canonical_required=False)
    static_digest = candidate.get("static_bindings_digest")
    if not isinstance(static_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", static_digest):
        raise CandidateError("RP2_INVALID")
    return {
        "binding_schema_exact_bytes_sha256": _sha256_file(RP2_SCHEMA),
        "candidate_exact_bytes_sha256": _sha256_file(RP2_CANDIDATE),
        "static_bindings_digest": static_digest,
    }


def _s3a_immutable_inputs() -> dict[str, dict[str, str]]:
    if _sha256_file(S3A_AUDIT) != S3A_AUDIT_SHA256:
        raise CandidateError("SOURCE_INPUT_MISMATCH")
    audit = _strict_json(S3A_AUDIT, "SOURCE_INPUT_MISMATCH")
    try:
        inputs = audit["body"]["source_revision"]["immutable_inputs"]
    except (KeyError, TypeError) as exc:
        raise CandidateError("SOURCE_INPUT_MISMATCH") from exc
    if not isinstance(inputs, dict):
        raise CandidateError("SOURCE_INPUT_MISMATCH")
    result: dict[str, dict[str, str]] = {}
    for name, entry in inputs.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise CandidateError("SOURCE_INPUT_MISMATCH")
        if set(entry) != {"path", "sha256"}:
            raise CandidateError("SOURCE_INPUT_MISMATCH")
        relative = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise CandidateError("SOURCE_INPUT_MISMATCH")
        relative = _safe_relative(relative)
        path = ROOT / Path(relative)
        if not path.is_file() or _is_link_or_reparse(path) or _sha256_file(path) != expected:
            raise CandidateError("HISTORICAL_PACKAGE_MISMATCH")
        result[name] = {"path": relative, "sha256": expected}
    return result


def source_binding_snapshot() -> dict[str, object]:
    _s3a_immutable_inputs()
    return {
        "historical_inputs_verified": True,
        "rp2": _load_rp2(),
        "s3a_audit_sha256": S3A_AUDIT_SHA256,
    }


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None, code: str) -> bytes:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            check=False,
            timeout=1800,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CandidateError(code) from exc
    if result.returncode != 0:
        raise CandidateError(code)
    return result.stdout


def _tool(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is None:
        raise CandidateError("TOOLCHAIN_UNAVAILABLE")
    return resolved


def _tool_version(command: list[str], *, cwd: Path = ROOT) -> str:
    output = _run(command, cwd=cwd, env=None, code="TOOLCHAIN_UNAVAILABLE")
    return output.decode("utf-8", errors="strict").strip()


def _verify_toolchain() -> dict[str, str]:
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise CandidateError("PLATFORM_UNSUPPORTED")
    observed = {
        "node": _tool_version([_tool("node.exe"), "--version"]).removeprefix("v"),
        "npm": _tool_version([_tool("npm.cmd"), "--version"]),
        "python": platform.python_version(),
        "uv": _tool_version([_tool("uv.exe"), "--version"]).split()[1],
    }
    for name, value in observed.items():
        if value != CONTRACT[name]:
            raise CandidateError("TOOLCHAIN_MISMATCH")
    return observed


def _release_manifest_command(
    action: str, tree: BuildTree, metadata: Path | None = None
) -> list[str]:
    command = [
        sys.executable,
        str(RELEASE_MANIFEST_SCRIPT),
        action,
        "--bundle-root",
        str(tree.bundle),
    ]
    if action == "build":
        if metadata is None:
            raise CandidateError("MANIFEST_MISMATCH")
        command.extend(
            ["--metadata-json", str(metadata), "--detached", str(tree.detached_manifest)]
        )
    else:
        command.extend(
            [
                "--bundled",
                str(tree.bundle / "RELEASE_MANIFEST.json"),
                "--detached",
                str(tree.detached_manifest),
            ]
        )
    return command


def _verify_historical_manifest() -> None:
    historical = BuildTree(
        root=PACKAGING_ROOT / "release",
        bundle=PACKAGING_ROOT / "release" / "PDU-Exam-Observer",
        detached_manifest=PACKAGING_ROOT / "RELEASE_MANIFEST.json",
    )
    _run(
        _release_manifest_command("verify", historical),
        cwd=ROOT,
        env=None,
        code="HISTORICAL_PACKAGE_MISMATCH",
    )


def _source_revision(rp2: dict[str, str]) -> str:
    return "RP2:" + ":".join(
        [
            rp2["static_bindings_digest"],
            rp2["candidate_exact_bytes_sha256"],
            rp2["binding_schema_exact_bytes_sha256"],
        ]
    )


def _manifest_metadata(rp2: dict[str, str]) -> dict[str, object]:
    return {
        "build_time_utc": CONTRACT["build_time_utc"],
        "frontend_lock_sha256": _sha256_file(WEB_ROOT / "package-lock.json"),
        "known_limitations": [
            "Unsigned current-source candidate; not a release.",
            "Contains synthetic M2 integration only; no camera or participant collection.",
            "Packaged runtime smoke, export/reproduction round-trip, clean-machine "
            "portability, distribution, and release authority are UNVERIFIED.",
        ],
        "product_version": CONTRACT["product_version"],
        "python_lock_sha256": _sha256_file(ROOT / "uv.lock"),
        "schema_version": CONTRACT["schema_version"],
        "source_revision": _source_revision(rp2),
        "target_architecture": CONTRACT["target_architecture"],
        "target_os": CONTRACT["target_os"],
        "test_receipts": [],
    }


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise CandidateError("OUTPUT_WRITE_FAILED") from exc


def _prepare_tool_environment(root: Path) -> tuple[Path, Path]:
    uv = _tool("uv.exe")
    tool_root = root / "tool-environment"
    _run(
        [uv, "venv", str(tool_root), "--python", sys.executable],
        cwd=ROOT,
        env=None,
        code="TOOLCHAIN_UNAVAILABLE",
    )
    python = tool_root / "Scripts" / "python.exe"
    viewer = tool_root / "Scripts" / "pyi-archive_viewer.exe"
    _run(
        [uv, "pip", "install", "--python", str(python), "pyinstaller==6.10.0"],
        cwd=ROOT,
        env=None,
        code="TOOLCHAIN_UNAVAILABLE",
    )
    version = _tool_version([str(python), "-m", "PyInstaller", "--version"])
    if version != CONTRACT["pyinstaller"] or not viewer.is_file():
        raise CandidateError("TOOLCHAIN_MISMATCH")
    return python, viewer


def _build_frontend(frontend_dist: Path) -> None:
    npm = _tool("npm.cmd")
    _run([npm, "ci"], cwd=WEB_ROOT, env=None, code="FRONTEND_BUILD_FAILED")
    _run(
        [npm, "run", "build", "--", "--outDir", str(frontend_dist), "--emptyOutDir"],
        cwd=WEB_ROOT,
        env=None,
        code="FRONTEND_BUILD_FAILED",
    )
    if not frontend_dist.is_dir():
        raise CandidateError("FRONTEND_BUILD_FAILED")


def _build_one(
    *,
    label: str,
    temp_root: Path,
    tool_python: Path,
    frontend_dist: Path,
    rp2: dict[str, str],
) -> BuildTree:
    build_root = temp_root / label
    dist_root = build_root
    work_root = temp_root / f"{label}-work"
    env = dict(os.environ)
    env.update(
        {
            "PDU_DEMO_DIR": str(DEMO_DIR.resolve(strict=True)),
            "PDU_ENTRY_SCRIPT": str(ENTRY_SCRIPT.resolve(strict=True)),
            "PDU_PROJECT_ROOT": str(ROOT.resolve(strict=True)),
            "PDU_WEB_DIST": str(frontend_dist.resolve(strict=True)),
            "PYTHONHASHSEED": CONTRACT["python_hash_seed"],
            "SOURCE_DATE_EPOCH": CONTRACT["source_date_epoch"],
        }
    )
    _run(
        [
            str(tool_python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(dist_root),
            "--workpath",
            str(work_root),
            str(CANDIDATE_SPEC),
        ],
        cwd=ROOT,
        env=env,
        code="PYINSTALLER_BUILD_FAILED",
    )
    bundle = dist_root / "PDU-Exam-Observer"
    if not bundle.is_dir():
        raise CandidateError("PYINSTALLER_BUILD_FAILED")
    shutil.copy2(CANDIDATE_README, bundle / "README.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.txt", bundle / "THIRD_PARTY_NOTICES.txt")
    detached = build_root / "RELEASE_MANIFEST.json"
    metadata = build_root / "manifest-metadata.json"
    _write_atomic(metadata, canonical_json_bytes(_manifest_metadata(rp2)))
    tree = BuildTree(root=build_root, bundle=bundle, detached_manifest=detached)
    _run(
        _release_manifest_command("build", tree, metadata),
        cwd=ROOT,
        env=None,
        code="MANIFEST_MISMATCH",
    )
    metadata.unlink(missing_ok=True)
    _run(
        _release_manifest_command("verify", tree),
        cwd=ROOT,
        env=None,
        code="MANIFEST_MISMATCH",
    )
    return tree


def _archive_inventory(executable: Path, viewer: Path | None = None) -> list[str]:
    if viewer is None:
        uv = _tool("uv.exe")
        command = [
            uv,
            "run",
            "--with",
            "pyinstaller==6.10.0",
            "pyi-archive_viewer",
            "-r",
            "-b",
            str(executable),
        ]
    else:
        command = [str(viewer), "-r", "-b", str(executable)]
    raw = _run(command, cwd=ROOT, env=None, code="ARCHIVE_INVENTORY_INVALID")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise CandidateError("ARCHIVE_INVENTORY_INVALID") from exc
    inventory = sorted(
        {
            line.strip()
            for line in lines
            if line.startswith(" ") and line.strip() and not line.lstrip().startswith("pyi-")
        }
    )
    if not inventory:
        raise CandidateError("ARCHIVE_INVENTORY_INVALID")
    return inventory


def _validate_archive(executable: Path, viewer: Path | None = None) -> tuple[list[str], str]:
    inventory = _archive_inventory(executable, viewer)
    if not set(REQUIRED_MODULES).issubset(inventory):
        raise CandidateError("PYTHON_RUNTIME_INCLUSION_MISMATCH")
    return inventory, _sha256_bytes(canonical_json_bytes(inventory))


def _frontend_records(bundle: Path) -> list[dict[str, object]]:
    frontend = bundle / "_internal" / "assets" / "web"
    return _tree_records(frontend)


def _validate_readme(bundle: Path) -> str:
    try:
        source = CANDIDATE_README.read_bytes()
        packaged = (bundle / "README.txt").read_bytes()
        text = packaged.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CandidateError("CANDIDATE_README_INVALID") from exc
    if packaged != source or any(marker not in text for marker in README_MARKERS):
        raise CandidateError("CANDIDATE_README_INVALID")
    return _sha256_bytes(packaged)


def _stage_records(tree: BuildTree) -> list[dict[str, object]]:
    # PyInstaller also leaves an intermediate EXE beside the one-folder
    # bundle. It is not promoted into the candidate; the candidate projection
    # is exactly the bundle plus detached manifest.
    return _tree_records(tree.root, exclude=frozenset({"PDUExamObserver.exe"}))


def _authority_ceiling() -> dict[str, object]:
    return {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "candidate_package_built": True,
        "candidate_package_contains_integration": True,
        "clean_machine_verified": False,
        "collection_authorized": False,
        "d1_go": False,
        "device_gate_decision": "UNVERIFIED",
        "distribution_ready": False,
        "execution_authorized": False,
        "historical_package_unchanged": True,
        "packaged_runtime_smoke_verified": False,
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
    closed = {
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
        "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED",
        "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE",
    }
    ids = [
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
        "GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED",
        "GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT",
        "GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT",
        "GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT",
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT",
        "GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE",
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT",
    ]
    return [
        {
            "authority_effect": "NONE",
            "gap_id": gap_id,
            "status": "CLOSED_FOR_CURRENT_CANDIDATE" if gap_id in closed else "OPEN",
        }
        for gap_id in ids
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
        "build_contract": contract_snapshot(),
        "candidate_package": {
            "executable_sha256": _sha256_file(BUNDLE_ROOT / "PDUExamObserver.exe"),
            "file_count": len(records),
            "manifest_sha256": _sha256_file(DETACHED_MANIFEST),
            "root_role": "LOCAL_IGNORED_CURRENT_SOURCE_CANDIDATE",
            "tree_sha256": tree_digest,
        },
        "frontend_inclusion": {
            "byte_identical": True,
            "isolated_tree_sha256": isolated_frontend_digest,
            "packaged_tree_sha256": packaged_frontend_digest,
        },
        "gap_projection": _gap_projection(),
        "observed_on": "2026-09-01",
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
        "result": "CANDIDATE_PACKAGE_INTEGRATED",
        "s3a_audit_sha256": S3A_AUDIT_SHA256,
        "source_revision": rp2,
    }
    return {
        "artifact_kind": "M2_S3B_PACKAGE_INTEGRATION_RECEIPT",
        "body": body,
        "body_sha256": _sha256_bytes(canonical_json_bytes(body)),
        "schema_version": 1,
        "status": STATUS,
    }


def _candidate_tree() -> BuildTree:
    return BuildTree(root=CANDIDATE_ROOT, bundle=BUNDLE_ROOT, detached_manifest=DETACHED_MANIFEST)


def verify_candidate_manifest() -> bool:
    _run(
        _release_manifest_command("verify", _candidate_tree()),
        cwd=ROOT,
        env=None,
        code="MANIFEST_MISMATCH",
    )
    return True


def read_candidate_archive_inventory() -> list[str]:
    return _archive_inventory(BUNDLE_ROOT / "PDUExamObserver.exe")


def verify_candidate_frontend() -> bool:
    validation = _strict_json(LOCAL_VALIDATION, "RECEIPT_MISMATCH")
    expected = validation.get("body", {}).get("frontend_inclusion", {})
    if not isinstance(expected, dict):
        raise CandidateError("RECEIPT_MISMATCH")
    observed = _tree_digest(_frontend_records(BUNDLE_ROOT))
    if observed != expected.get("packaged_tree_sha256"):
        raise CandidateError("FRONTEND_INCLUSION_MISMATCH")
    return True


def _validate_receipt_envelope(document: dict[str, Any]) -> None:
    if set(document) != {"artifact_kind", "body", "body_sha256", "schema_version", "status"}:
        raise CandidateError("RECEIPT_MISMATCH")
    body = document.get("body")
    if (
        document.get("artifact_kind") != "M2_S3B_PACKAGE_INTEGRATION_RECEIPT"
        or document.get("schema_version") != 1
        or document.get("status") != STATUS
        or not isinstance(body, dict)
        or document.get("body_sha256") != _sha256_bytes(canonical_json_bytes(body))
    ):
        raise CandidateError("RECEIPT_MISMATCH")


def check_candidate() -> dict[str, object]:
    _verify_historical_manifest()
    verify_candidate_manifest()
    validation = _strict_json(LOCAL_VALIDATION, "RECEIPT_MISMATCH")
    _validate_receipt_envelope(validation)
    body = validation["body"]
    if body.get("source_revision") != CANDIDATE_SOURCE_REVISION:
        raise CandidateError("RP2_INVALID")
    records = _tree_records(CANDIDATE_ROOT, exclude=frozenset({"M2_S3B_BUILD_VALIDATION.json"}))
    digest = _tree_digest(records)
    reproducibility = body.get("reproducibility")
    if not isinstance(reproducibility, dict) or any(
        reproducibility.get(key) != digest for key in ("build_a_tree_sha256", "build_b_tree_sha256")
    ):
        raise CandidateError("BUILD_REPRODUCIBILITY_MISMATCH")
    inventory, inventory_digest = _validate_archive(BUNDLE_ROOT / "PDUExamObserver.exe")
    inclusion = body.get("python_runtime_inclusion")
    if not isinstance(inclusion, dict) or inclusion.get("inventory_sha256") != inventory_digest:
        raise CandidateError("ARCHIVE_INVENTORY_INVALID")
    del inventory
    packaged_frontend_digest = _tree_digest(_frontend_records(BUNDLE_ROOT))
    frontend = body.get("frontend_inclusion")
    if (
        not isinstance(frontend, dict)
        or frontend.get("packaged_tree_sha256") != packaged_frontend_digest
        or frontend.get("isolated_tree_sha256") != packaged_frontend_digest
    ):
        raise CandidateError("FRONTEND_INCLUSION_MISMATCH")
    _validate_readme(BUNDLE_ROOT)
    if AI_RECEIPT.is_file() and AI_RECEIPT.read_bytes() != LOCAL_VALIDATION.read_bytes():
        raise CandidateError("RECEIPT_MISMATCH")
    _s3a_immutable_inputs()
    return {
        "failure_code": None,
        "result": "CANDIDATE_PACKAGE_INTEGRATED",
        "status": STATUS,
    }


def build_candidate() -> dict[str, object]:
    source = source_binding_snapshot()
    _verify_historical_manifest()
    _verify_toolchain()
    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".pdu-m2-s3b-", dir=CANDIDATE_PARENT))
    try:
        frontend_dist = temporary / "frontend-dist"
        _build_frontend(frontend_dist)
        isolated_frontend_records = _tree_records(frontend_dist)
        isolated_frontend_digest = _tree_digest(isolated_frontend_records)
        tool_python, viewer = _prepare_tool_environment(temporary)
        rp2 = source["rp2"]
        if not isinstance(rp2, dict) or not all(isinstance(value, str) for value in rp2.values()):
            raise CandidateError("RP2_INVALID")
        typed_rp2 = {str(key): str(value) for key, value in rp2.items()}
        first = _build_one(
            label="build-a",
            temp_root=temporary,
            tool_python=tool_python,
            frontend_dist=frontend_dist,
            rp2=typed_rp2,
        )
        second = _build_one(
            label="build-b",
            temp_root=temporary,
            tool_python=tool_python,
            frontend_dist=frontend_dist,
            rp2=typed_rp2,
        )
        first_records = _stage_records(first)
        second_records = _stage_records(second)
        if first_records != second_records:
            raise CandidateError("BUILD_REPRODUCIBILITY_MISMATCH")
        tree_digest = _tree_digest(first_records)
        inventory, inventory_digest = _validate_archive(
            first.bundle / "PDUExamObserver.exe", viewer
        )
        del inventory
        first_frontend = _tree_digest(_frontend_records(first.bundle))
        second_frontend = _tree_digest(_frontend_records(second.bundle))
        if (
            first_frontend != isolated_frontend_digest
            or second_frontend != isolated_frontend_digest
        ):
            raise CandidateError("FRONTEND_INCLUSION_MISMATCH")
        readme_digest = _validate_readme(first.bundle)
        _validate_readme(second.bundle)

        stage = temporary / "candidate-stage"
        stage.mkdir()
        shutil.copytree(first.bundle, stage / "PDU-Exam-Observer")
        shutil.copy2(first.detached_manifest, stage / "RELEASE_MANIFEST.json")
        staged_records = _tree_records(stage)
        if staged_records != first_records:
            raise CandidateError("BUILD_REPRODUCIBILITY_MISMATCH")
        if CANDIDATE_ROOT.exists():
            existing_records = _tree_records(
                CANDIDATE_ROOT, exclude=frozenset({"M2_S3B_BUILD_VALIDATION.json"})
            )
            if existing_records != staged_records:
                raise CandidateError("CANDIDATE_EXISTS_MISMATCH")
        else:
            os.replace(stage, CANDIDATE_ROOT)

        receipt = _receipt(
            rp2=typed_rp2,
            tree_digest=tree_digest,
            records=first_records,
            inventory_digest=inventory_digest,
            isolated_frontend_digest=isolated_frontend_digest,
            packaged_frontend_digest=first_frontend,
            readme_digest=readme_digest,
        )
        _write_atomic(LOCAL_VALIDATION, canonical_json_bytes(receipt))
        result = check_candidate()
        _s3a_immutable_inputs()
        return result
    except CandidateError:
        raise
    except OSError as exc:
        raise CandidateError("OUTPUT_WRITE_FAILED") from exc
    finally:
        try:
            shutil.rmtree(temporary)
        except OSError as exc:
            raise CandidateError("CLEANUP_FAILED") from exc


def _failure(code: str) -> dict[str, object]:
    return {"failure_code": code, "result": "CANDIDATE_PACKAGE_NOT_VERIFIED", "status": None}


def _emit(document: dict[str, object], exit_code: int) -> NoReturn:
    sys.stdout.buffer.write(canonical_json_bytes(document))
    raise SystemExit(exit_code)


def main(argv: list[str] | None = None) -> NoReturn:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments not in ([], ["--check"], ["--build"]):
        _emit(_failure("REQUEST_INVALID"), 2)
    try:
        result = build_candidate() if arguments == ["--build"] else check_candidate()
    except CandidateError as exc:
        _emit(_failure(exc.code), 2)
    except Exception:
        _emit(_failure("UNEXPECTED_FAILURE"), 2)
    _emit(result, 0)


if __name__ == "__main__":
    main()
