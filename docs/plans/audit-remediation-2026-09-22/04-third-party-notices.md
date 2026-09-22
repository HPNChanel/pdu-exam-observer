# Task 04 — Regenerate THIRD_PARTY_NOTICES.txt

**Type:** repo hygiene + one deterministic script. **Findings:** H2.
**Depends on:** Task 05 (so notices reflect final pinned versions).

## Objective

Replace the hand-written M0-era notices file with a generated inventory that
covers everything the packaged bundle actually contains — a hard prerequisite
for any future distribution.

## Steps

1. Create `scripts/generate_third_party_notices.py`:
   - Read `uv.lock` → all packages in the default dependency set (exclude
     `dev` group and `training` extra, since they don't ship); for each, emit
     name, exact version, license expression/source (from lock metadata or a
     small curated `LICENSE_MAP` dict in the script for cases where lock
     metadata is absent — mediapipe, onnxruntime, onnx, numpy,
     opencv-python, pydantic, pydantic-core, starlette, anyio,
     sse-starlette, click, h11, certifi, sounddevice, fastapi, uvicorn,
     pydantic stack extras).
   - Read `apps/web/package-lock.json` → production deps only (walk
     `packages."".dependencies`), name + version + license field.
   - Append a fixed VENDORED section listing: FFmpeg (`tools/ffmpeg.exe`,
     LGPL/GPL — see bundled `FFMPEG_LICENSE.txt`), PortAudio (inside
     sounddevice `_sounddevice_data`), Python 3.11 runtime (PSF license),
     setuptools vendored wheels (jaraco/platformdirs/zipp/wheel/packaging/
     tomli/more_itertools/backports.tarfile/importlib_metadata/autocommand —
     verify actual list against the last build's `COLLECT-00.toc` or a fresh
     `_internal` listing).
   - Deterministic output: sorted sections, canonical text, no timestamps.
     Header keeps the existing "informational" honesty wording but removes
     the "until generated inventory is attached" clause.
2. RED test `tests/packaging/test_third_party_notices.py`:
   - Assert every default dependency name from `uv.lock` appears in
     `THIRD_PARTY_NOTICES.txt`.
   - Assert the file contains the tokens: `mediapipe`, `onnxruntime`,
     `onnx`, `numpy`, `opencv`, `pydantic`, `starlette`, `sse-starlette`,
     `certifi`, `sounddevice`, `FFmpeg`, `PortAudio`, `Python` (PSF),
     `React`, `Vite`.
   - Assert regenerating the file produces byte-identical output
     (determinism guard).
3. Run the generator, write `THIRD_PARTY_NOTICES.txt`, GREEN the test.
4. Record the deviation honestly: candidate-06 shipped the old notices file.
   Add one line for Task 10's remediation receipt — do NOT rebuild or patch
   candidate-06.

## Acceptance

- `pytest tests/packaging/test_third_party_notices.py -q` green.
- Generator is idempotent: two runs → byte-identical output.
- Ruff + strict mypy clean on the new script.
- Spot-check 3 licenses against upstream (e.g. mediapipe Apache-2.0,
  onnxruntime MIT, certifi MPL-2.0) — record as OBSERVED in the task receipt.

## Execution note (2026-09-22)

- NEW `scripts/generate_third_party_notices.py`: deterministic renderer over
  `uv.lock` (tomllib) + `package-lock.json`; ships-set = the 37-package
  default dependency closure from `uv export --no-dev` (mediapipe transitively
  pulls matplotlib/opencv-contrib-python/sounddevice — they ship).
- License expressions verified against installed wheel dist-info METADATA
  (all 37 read; e.g. certifi MPL-2.0, cffi MIT-0, numpy BSD-3-Clause+bundled,
  pillow MIT-CMU, python-dateutil dual Apache-2.0/BSD-3-Clause).
- `vite`/`@vitejs/plugin-react` moved to `devDependencies` — they are
  build tools, not shipped code; `npm ci` still green, dist output
  byte-identical.
- Vendored section covers FFmpeg (LGPL, FFMPEG_LICENSE.txt), PortAudio,
  Python 3.11/PSF, OpenSSL 3, SQLite, MSVC runtime, libffi, MediaPipe model
  assets, setuptools vendored wheels, PyInstaller bootloader exception.
- NEW `tests/packaging/test_third_party_notices.py`: coverage (every shipped
  name+version), token gate, frontend prod-dep equality, byte-identical
  regeneration. `--check` mode gives CI a staleness gate.
- DEVIATION (recorded for Task 10 receipt): candidate-06 shipped the old
  15-line informational notices; this regeneration lands in the next
  candidate lineage — candidate-06 bytes untouched.
