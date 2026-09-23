"""Coverage and determinism gates for THIRD_PARTY_NOTICES.txt (H2)."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import generate_third_party_notices as gen  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NOTICES = (ROOT / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")

REQUIRED_TOKENS = (
    "mediapipe",
    "onnxruntime",
    "onnx",
    "numpy",
    "opencv",
    "pydantic",
    "starlette",
    "sse-starlette",
    "certifi",
    "sounddevice",
    "FFmpeg",
    "PortAudio",
    "Python",
    "PSF",
    "react",
    "Vite",
)


def _lock_versions() -> dict[str, str]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    return {p["name"]: p["version"] for p in lock["package"]}


def test_notices_cover_every_shipped_python_dependency() -> None:
    versions = _lock_versions()
    for name in gen.PYTHON_RUNTIME_DEPENDENCIES:
        assert name in versions, f"{name} missing from uv.lock"
        assert f"{name} {versions[name]}" in NOTICES


def test_notices_cover_required_tokens_and_bundled_components() -> None:
    missing = [token for token in REQUIRED_TOKENS if token not in NOTICES]
    assert missing == []


def test_notices_cover_frontend_production_dependencies() -> None:
    lock = json.loads((ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    production = lock["packages"][""].get("dependencies", {})
    assert set(production) == set(gen.NPM_SHIPPED_DEPENDENCIES)
    for name, spec in production.items():
        resolved = lock["packages"][f"node_modules/{name}"]["version"]
        assert f"{name} {resolved}" in NOTICES
        assert resolved == spec


def test_notices_regeneration_is_deterministic() -> None:
    assert gen.render() == NOTICES
