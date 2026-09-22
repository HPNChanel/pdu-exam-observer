"""Build a local-only workspace candidate and bind it to current source bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / "packaging/candidates/completion-2026-09-08"


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_manifest() -> dict[str, object]:
    files = []
    for relative in (
        "src",
        "apps/web/src",
        "apps/web/public",
        "docs/spec",
        "tests",
        "scripts",
        "research/training",
    ):
        files.extend(
            path
            for path in (ROOT / relative).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".zip"}
        )
    files.extend(
        ROOT / relative
        for relative in (
            "pyproject.toml",
            "uv.lock",
            "apps/web/package.json",
            "apps/web/package-lock.json",
            "packaging/PDU-Workspace.spec",
            "docs/WORKSPACE_GUIDE_VI.md",
            "apps/web/vite.config.ts",
            "apps/web/tsconfig.json",
            "apps/web/tsconfig.app.json",
            "docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        )
    )
    records = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(set(files))
    ]
    return {
        "schema_version": 1,
        "scope": "current source snapshot, including uncommitted changes",
        "files": records,
    }


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inventory(bundle: Path) -> dict[str, object]:
    forbidden_suffixes = {".db", ".sqlite3", ".mp4", ".avi", ".partial", ".log", ".pem"}
    files = []
    for path in sorted(bundle.rglob("*")):
        if not path.is_file() or path.name in {"DELIVERY_MANIFEST.json", "RELEASE_MANIFEST.json"}:
            continue
        relative = path.relative_to(bundle)
        public_ca = relative.as_posix() == "_internal/certifi/cacert.pem"
        if public_ca:
            pem = path.read_bytes()
            if b"-----BEGIN CERTIFICATE-----" not in pem or b"PRIVATE KEY" in pem:
                raise RuntimeError("invalid public CA certificate payload")
        if (
            path.is_symlink()
            or (path.suffix.lower() in forbidden_suffixes and not public_ca)
            or any(
                part in {".git", ".env", "runtime-artifacts", "__pycache__", "training"}
                for part in relative.parts
            )
        ):
            raise RuntimeError("forbidden runtime/private payload in candidate")
        files.append(
            {"path": relative.as_posix(), "sha256": digest(path), "bytes": path.stat().st_size}
        )
    return {
        "schema_version": 1,
        "scope": "LOCAL_TECHNICAL_CANDIDATE",
        "new_device_verified": False,
        "release_authorized": False,
        "files": files,
        "source_manifest_sha256": digest(bundle / "SOURCE_MANIFEST.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-python", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--name", default="candidate-01")
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum():
        parser.error("name must contain only letters, digits and hyphens")
    target = DEFAULT_PARENT / args.name
    if target.exists():
        parser.error("candidate already exists; choose a fresh name to preserve prior bytes")
    target.mkdir(parents=True)
    before = source_manifest()
    env = {
        **os.environ,
        "PDU_PROJECT_ROOT": str(ROOT),
        "PDU_FFMPEG_BINARY": str(args.ffmpeg.resolve()),
        "PYTHONHASHSEED": "1",
    }
    with (target / "build.log").open("w", encoding="utf-8") as log:
        subprocess.run(
            [
                str(args.build_python.resolve()),
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--clean",
                "--distpath",
                str(target),
                "--workpath",
                str(target / "build"),
                str(ROOT / "packaging/PDU-Workspace.spec"),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    if before != source_manifest():
        raise RuntimeError("source changed during build; candidate is not current-source verified")
    bundle = target / "PDU-Workspace"
    write_json(bundle / "SOURCE_MANIFEST.json", before)
    shutil.copy2(ROOT / "docs/WORKSPACE_GUIDE_VI.md", bundle / "HUONG_DAN.md")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.txt", bundle / "THIRD_PARTY_NOTICES.txt")
    license_path = args.ffmpeg.resolve().parent.parent / "LICENSE"
    if not license_path.is_file():
        raise RuntimeError("FFmpeg license must be supplied alongside the binary")
    shutil.copy2(license_path, bundle / "FFMPEG_LICENSE.txt")
    (bundle / "START.cmd").write_text(
        '@echo off\n"%~dp0PDUWorkspace.exe" workspace\n', encoding="ascii"
    )
    write_json(bundle / "DELIVERY_MANIFEST.json", inventory(bundle))
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    metadata = {
        "product_version": "0.2.0-workspace-local",
        "schema_version": 1,
        "target_os": "Windows 11",
        "target_architecture": "x64",
        "build_time_utc": datetime.now(UTC).isoformat(),
        "source_revision": revision + "+working-tree:" + digest(bundle / "SOURCE_MANIFEST.json"),
        "python_lock_sha256": digest(ROOT / "uv.lock"),
        "frontend_lock_sha256": digest(ROOT / "apps/web/package-lock.json"),
        "known_limitations": [
            "LOCAL_TECHNICAL_CANDIDATE",
            "NEW_DEVICE_UNVERIFIED_USER_DEFERRED",
            "NO_PARTICIPANT_COLLECTION",
            "NO_REAL_RESEARCH_TRAINING",
            "NO_RELEASE_AUTHORITY",
        ],
    }
    sys.path.insert(0, str(ROOT))
    from scripts.release_manifest import build_manifest

    build_manifest(bundle, metadata, target / "RELEASE_MANIFEST.detached.json")
    archive_path = target / "PDU-Workspace-local.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                archive.write(path, (Path("PDU-Workspace") / path.relative_to(bundle)).as_posix())
    receipt = {
        "schema_version": 1,
        "bundle": str(bundle),
        "zip": str(archive_path),
        "zip_sha256": digest(archive_path),
        "manifest_sha256": digest(bundle / "DELIVERY_MANIFEST.json"),
        "status": "BUILT_RUNTIME_VERIFICATION_PENDING",
        "clean_machine_verified": False,
    }
    write_json(target / "build-receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
