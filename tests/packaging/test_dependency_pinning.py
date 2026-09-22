"""Pin guards for the frontend toolchain and the packaged-build toolchain.

H3 remediation: the frontend manifest previously used floating ``"latest"``
specs, so a plain ``npm install`` could silently upgrade the toolchain. These
tests fail closed if a non-exact spec or an unpinned PyInstaller returns.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "apps/web/package.json"
LOCK = ROOT / "apps/web/package-lock.json"
COMPLETION_BUILDER = ROOT / "scripts/build_completion_delivery.py"
HISTORICAL_RELEASE_SCRIPT = ROOT / "scripts/build_release.ps1"

EXACT_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _manifest_specs() -> dict[str, str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {
        **manifest.get("dependencies", {}),
        **manifest.get("devDependencies", {}),
    }


def test_frontend_manifest_uses_exact_versions_only() -> None:
    specs = _manifest_specs()
    assert specs, "frontend manifest has no dependency sections"

    floating = {
        name: spec for name, spec in specs.items() if not EXACT_SEMVER.match(spec)
    }
    assert floating == {}


def test_frontend_lockfile_resolves_exactly_the_manifest_specs() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    root = lock["packages"][""]
    specs = _manifest_specs()

    assert {**root.get("dependencies", {}), **root.get("devDependencies", {})} == specs
    for name, spec in specs.items():
        resolved = lock["packages"][f"node_modules/{name}"]["version"]
        assert resolved == spec, f"{name}: lock resolved {resolved}, manifest {spec}"


def test_completion_builder_pins_the_verified_pyinstaller_version() -> None:
    builder = COMPLETION_BUILDER.read_text(encoding="utf-8")
    release_script = HISTORICAL_RELEASE_SCRIPT.read_text(encoding="utf-8")

    match = re.search(r"pyinstaller==(\d+\.\d+\.\d+)", release_script)
    assert match is not None, "historical release script lost its PyInstaller pin"
    pinned = match.group(1)

    assert f'REQUIRED_PYINSTALLER_VERSION = "{pinned}"' in builder
    assert "PyInstaller.__version__" in builder
