"""Regenerate THIRD_PARTY_NOTICES.txt deterministically.

The inventory covers exactly what the packaged bundle ships: the uv.lock
default dependency set (dev group and ``training`` extra excluded), the
frontend production dependencies bundled by Vite, and the native/vendored
components PyInstaller collects. License expressions were verified against
each wheel's installed dist-info metadata on 2026-09-22.

Output is deterministic: sorted sections, fixed text, no timestamps, so a
byte-identical regeneration is the integrity gate.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "THIRD_PARTY_NOTICES.txt"
UV_LOCK = ROOT / "uv.lock"
NPM_LOCK = ROOT / "apps/web/package-lock.json"

# Default (shipped) dependency set, derived from
#   uv export --format requirements-txt --no-dev --frozen --no-hashes
# on 2026-09-22. Dev group (pytest/mypy/ruff/httpx) and the ``training``
# extra (torch, scikit-learn, onnxscript, ...) do not ship in the bundle.
PYTHON_RUNTIME_DEPENDENCIES = (
    "absl-py",
    "annotated-types",
    "anyio",
    "certifi",
    "cffi",
    "click",
    "colorama",
    "contourpy",
    "cycler",
    "fastapi",
    "flatbuffers",
    "fonttools",
    "h11",
    "idna",
    "kiwisolver",
    "matplotlib",
    "mediapipe",
    "ml-dtypes",
    "numpy",
    "onnx",
    "onnxruntime",
    "opencv-contrib-python",
    "packaging",
    "pillow",
    "protobuf",
    "pycparser",
    "pydantic",
    "pydantic-core",
    "pyparsing",
    "python-dateutil",
    "six",
    "sounddevice",
    "sse-starlette",
    "starlette",
    "typing-extensions",
    "typing-inspection",
    "uvicorn",
)

# License expressions verified against installed dist-info metadata
# (License-Expression / License fields) on 2026-09-22. Entries annotated
# where a package ships additional bundled-component licenses.
PYTHON_LICENSES = {
    "absl-py": "Apache-2.0",
    "annotated-types": "MIT",
    "anyio": "MIT",
    "certifi": "MPL-2.0",
    "cffi": "MIT-0",
    "click": "BSD-3-Clause",
    "colorama": "BSD-3-Clause",
    "contourpy": "BSD-3-Clause",
    "cycler": "BSD-3-Clause",
    "fastapi": "MIT",
    "flatbuffers": "Apache-2.0",
    "fonttools": "MIT",
    "h11": "MIT",
    "idna": "BSD-3-Clause",
    "kiwisolver": "BSD-3-Clause",
    "matplotlib": (
        "PSF-style (see matplotlib/LICENSE; bundles STIX fonts OFL-1.1 "
        "and other listed components)"
    ),
    "mediapipe": (
        "Apache-2.0 (bundles third-party components; see mediapipe "
        "third-party notices)"
    ),
    "ml-dtypes": "Apache-2.0",
    "numpy": (
        "BSD-3-Clause (bundled components under 0BSD, MIT, Zlib, CC0-1.0; "
        "see numpy LICENSES_bundled.txt)"
    ),
    "onnx": "Apache-2.0",
    "onnxruntime": "MIT",
    "opencv-contrib-python": "Apache-2.0",
    "packaging": "Apache-2.0 OR BSD-2-Clause",
    "pillow": "MIT-CMU (HPND-style PIL license)",
    "protobuf": "BSD-3-Clause",
    "pycparser": "BSD-3-Clause",
    "pydantic": "MIT",
    "pydantic-core": "MIT",
    "pyparsing": "MIT",
    "python-dateutil": "Apache-2.0 OR BSD-3-Clause (dual license)",
    "six": "MIT",
    "sounddevice": "MIT",
    "sse-starlette": "BSD-3-Clause",
    "starlette": "BSD-3-Clause",
    "typing-extensions": "PSF-2.0",
    "typing-inspection": "MIT",
    "uvicorn": "BSD-3-Clause",
}

# Frontend packages whose code is bundled into apps/web/dist (the shipped
# artifact). Build-time packages (vite, plugin-react, eslint, typescript,
# vitest, testing-library, jsdom, ...) are devDependencies and do not ship.
NPM_SHIPPED_DEPENDENCIES = ("react", "react-dom")

NPM_LICENSES = {
    "react": "MIT",
    "react-dom": "MIT",
}

# Native, vendored, or runtime components collected into the bundle that do
# not come from a Python/npm package registry.
BUNDLED_COMPONENTS = (
    (
        "FFmpeg",
        "tools/ffmpeg.exe",
        "LGPL-2.1-or-later (GPL components; full license text in bundled "
        "FFMPEG_LICENSE.txt)",
    ),
    ("PortAudio", "_internal/_sounddevice_data (bundled by sounddevice)", "MIT"),
    ("Python", "python311.dll and standard library", "PSF-2.0"),
    ("OpenSSL", "libcrypto-3.dll, libssl-3.dll", "Apache-2.0"),
    ("SQLite", "sqlite3.dll", "public domain"),
    (
        "Microsoft Visual C++ Runtime",
        "msvcp140.dll, vcruntime140*.dll, ucrtbase.dll",
        "Microsoft redistributable license",
    ),
    ("libffi", "libffi-8.dll", "MIT"),
    (
        "MediaPipe pose/face models",
        "pdu_exam_observer/assets/models (pose_landmarker_lite.task, "
        "blaze_face_short_range.tflite)",
        "Apache-2.0 (MediaPipe model cards)",
    ),
    (
        "setuptools vendored wheels",
        "autocommand, backports.tarfile, importlib_metadata, "
        "jaraco.context/functools/text, more_itertools, platformdirs, "
        "tomli, wheel, zipp, packaging",
        "MIT",
    ),
)

# Build-time tooling that shapes the artifact but is not distributed in it.
BUILD_TOOLS = (
    ("PyInstaller", "6.10.0", "GPL-2.0-or-later with bootloader exception"),
    ("Vite", "bundles the frontend (vite.config.ts)", "MIT"),
    ("TypeScript", "compiles the frontend", "Apache-2.0"),
    ("hatchling", "builds the source wheel", "MIT"),
)


def _uv_lock_versions() -> dict[str, str]:
    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    versions: dict[str, str] = {}
    shipped = set(PYTHON_RUNTIME_DEPENDENCIES)
    for package in lock["package"]:
        name = package["name"]
        if name not in shipped:
            continue
        if name in versions and versions[name] != package["version"]:
            raise SystemExit(f"uv.lock resolves {name} to multiple versions")
        versions[name] = package["version"]
    return versions


def _npm_lock_versions() -> dict[str, str]:
    lock = json.loads(NPM_LOCK.read_text(encoding="utf-8"))
    return {
        name: lock["packages"][f"node_modules/{name}"]["version"]
        for name in NPM_SHIPPED_DEPENDENCIES
    }


def render() -> str:
    python_versions = _uv_lock_versions()
    npm_versions = _npm_lock_versions()
    missing = [
        name for name in PYTHON_RUNTIME_DEPENDENCIES if name not in python_versions
    ]
    if missing:
        raise SystemExit(f"uv.lock no longer resolves shipped deps: {missing}")

    lines = [
        "PDU Exam Observer — third-party dependency notices",
        "",
        "Generated by scripts/generate_third_party_notices.py from uv.lock,",
        "apps/web/package-lock.json, and the verified packaged-bundle contents.",
        "Do not edit by hand; regenerate instead. Development-only packages",
        "(pytest, mypy, ruff, httpx) and the `training` extra (torch,",
        "scikit-learn, onnxscript, ...) are excluded — they do not ship in",
        "the application bundle.",
        "",
        "== Python runtime dependencies (uv.lock default set) ==",
        "",
    ]
    for name in sorted(PYTHON_RUNTIME_DEPENDENCIES):
        lines.append(f"{name} {python_versions[name]} — {PYTHON_LICENSES[name]}")
    lines += [
        "",
        "== Frontend dependencies bundled into assets/web ==",
        "",
    ]
    for name in sorted(NPM_SHIPPED_DEPENDENCIES):
        lines.append(f"{name} {npm_versions[name]} — {NPM_LICENSES[name]}")
    lines += [
        "",
        "== Bundled native, vendored, and runtime components ==",
        "",
    ]
    for name, location, license_name in BUNDLED_COMPONENTS:
        lines.append(f"{name} ({location}) — {license_name}")
    lines += [
        "",
        "== Build-time tools (not distributed inside the bundle) ==",
        "",
    ]
    for name, detail, license_name in BUILD_TOOLS:
        lines.append(f"{name} {detail} — {license_name}")
    lines += [
        "",
        "This file is informational. It asserts the dependency inventory of the",
        "packaged artifact; it grants no additional rights and implies no",
        "release authorization, distribution readiness, or institutional",
        "approval.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    rendered = render()
    check = "--check" in sys.argv[1:]
    if check:
        current = OUTPUT.read_text(encoding="utf-8")
        if current != rendered:
            print("THIRD_PARTY_NOTICES.txt is stale; run scripts/generate_third_party_notices.py")
            return 1
        print("THIRD_PARTY_NOTICES.txt is up to date")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.name} ({len(rendered.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
