# Build Toolchain — `PDU-Workspace` candidates

Version: 1.0 (2026-09-22)

This document records the exact toolchain required to reproduce a
`PDU-Workspace` delivery candidate via `scripts/build_completion_delivery.py`.
It exists because the candidate-06 build environment
(`output/completion-2026-09-08/package-env`) was not retained, which made the
verified bundle non-rebuildable in principle. Evidence state for every entry:
`OBSERVED` from candidate-06 `build.log` unless noted otherwise.

## Required toolchain

| Component | Version | Source |
|---|---|---|
| Windows | 11 x64 (build host observed: Windows 10.0.26200) | target platform |
| Python | **3.11.9** | `python.org` CPython, used only to *create* the build env |
| uv | any (observed 0.10.10) | env creation + locked install |
| Node.js | 24.x (observed v24.11.0) | frontend build only |
| npm | 11.x (observed 11.14.1) | frontend build only |
| PyInstaller | **6.10.0** (hard gate in `build_completion_delivery.py`) | PyPI |
| pyinstaller-hooks-contrib | **2026.7** (observed in candidate-06 build.log) | PyPI |
| FFmpeg | 8.0.1 essentials build (gyan.dev), GPL — see provenance recipe below | pinned binary input |
| Python runtime deps | exactly `uv.lock` (`uv export --locked`) | in-repo lockfile |
| Frontend deps | exactly `apps/web/package-lock.json` (`npm ci`) | in-repo lockfile |

`PYTHONHASHSEED=1` is forced by the build script. Git is required only to stamp
`source_revision` in the release metadata.

## Build procedure

~~~powershell
# 1. Frontend assets (spec packs apps/web/dist)
cd apps/web
npm ci
npm run build
cd ../..

# 2. Build environment (do NOT reuse the dev .venv)
uv venv output/<build-date>/package-env --python 3.11.9 --seed
uv export --format requirements-txt --locked --no-dev --no-emit-project `
    -o output/<build-date>/requirements.txt
uv pip install --python output/<build-date>/package-env/Scripts/python.exe `
    -r output/<build-date>/requirements.txt
uv pip install --python output/<build-date>/package-env/Scripts/python.exe `
    pyinstaller==6.10.0 pyinstaller-hooks-contrib==2026.7

# 3. FFmpeg input: place the pinned binary at
#    output/<build-date>/tools/ffmpeg.exe and its GPL license text at
#    output/<build-date>/LICENSE (the builder requires LICENSE beside the
#    tools directory). Verify SHA-256 first — see provenance recipe.

# 4. Build
.venv/Scripts/python.exe scripts/build_completion_delivery.py `
    --build-python output/<build-date>/package-env/Scripts/python.exe `
    --ffmpeg output/<build-date>/tools/ffmpeg.exe `
    --name <candidate-name> --parent packaging/candidates/<lineage-date>
~~~

The build script refuses to overwrite an existing candidate directory,
snapshots the source manifest before and after PyInstaller, and fails if the
source tree changed during the build.

## FFmpeg acquisition recipe (DG-3 — recipe, not vendored)

- Upstream: `ffmpeg version 8.0.1-essentials_build-www.gyan.dev`
  (`--enable-gpl --enable-version3 --enable-static`, built by MSYS2, gcc 15.2.0).
- The binary is **not vendored** in the repository. The provenance-verified
  copy is recoverable from
  `packaging/candidates/completion-2026-09-08/candidate-06/PDU-Workspace/_internal/tools/ffmpeg.exe`
  or re-downloaded from the upstream essentials channel.
- Required SHA-256 (also recorded in
  `docs/source/M2_D1_NATIVE_ASSET_PROVENANCE.md`):
  `5af82a0d4fe2b9eae211b967332ea97edfc51c6b328ca35b827e73eac560dc0d`
- Verify before use:
  `certutil -hashfile <path>\ffmpeg.exe SHA256` must equal the value above.
- License: GPL build — ship `FFMPEG_LICENSE.txt` (GPL-3.0 text) in the bundle
  root; the build script copies `LICENSE` from beside the binary.

## Non-goals

This record does not claim bit-for-bit reproducibility (PyInstaller embeds
timestamps and build paths), clean-machine verification, or release
authorization. It documents a repeatable toolchain and a verifiable binary
input, nothing more.
