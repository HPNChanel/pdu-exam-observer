# Task 02 — Documentation and traceability refresh

**Type:** docs-only. **Findings:** M4. **Depends on:** Task 01.

## Objective

Bring the reference docs back into agreement with the code that actually
ships, and add the missing spec→implementation traceability layer. This is the
cheapest task and the highest value for a defensible research artifact.

## Steps

1. `docs/source/TRACEABILITY_MATRIX.md` — append a second section
   "Spec → implementation" (keep the existing proposal→spec table untouched).
   For each row in PRODUCT_SPEC FR-001…FR-015, the NFR list, and the
   DATA_GOVERNANCE capture/withdrawal/export gates, record: implementing
   module(s) and discriminating test(s). Seed rows from the audit's verified
   matrix — e.g. FR-003 → `services/core.py:112-143` + `test_auth.py`;
   FR-013 → `showcase/model_import.py` + `test_model_import_contract.py`;
   FR-014 → `service.py:61-76,1634-1743` + `test_workspace_end_to_end.py`;
   data-split gates → `research/training/showcase/v3/splits.py` +
   `test_split_augmentation_contract.py`. Mark requirements whose only
   evidence is code review (no runtime evidence) as `CODE_VERIFIED`, not
   `VERIFIED`.
2. `docs/architecture/ARCHITECTURE.md` — add a "Current architecture
   (2026-09)" section above the historical M0/M1 text: five launcher modes
   (`launcher.py:43`), `WorkspaceBackend`/`WorkspaceService`, monitor-only
   workspace router (`api/workspace.py`), `ResearchRuntimeService`,
   `RootLease`, `NativeCapture` spawn child, `ModelRegistry`/`ModelRuntime`,
   the authority record + `authority_cli`, `PDU_WORKSPACE_ROOT` /
   `PDU_COLLECTION_AUTHORITY_REF` env contract, packaged layout (`_internal`).
   Keep the M0/M1 section labeled historical.
3. `README.md` — update "Current milestone" to reflect M2–M7 technical
   delivery with the honest ceilings (no collection authority, camera fails
   closed at ~10 fps, no research-performance claim); fix the repo map
   (`research/` now holds `pre_collection/`, `institutional_submission/`,
   `training/`; `tests/` now includes `runtime/`, `training/`); add one line
   pointing to `docs/WORKSPACE_GUIDE_VI.md`.
4. `docs/spec/PACKAGING_DISTRIBUTION.md` — add the current workspace bundle
   shape (`PDU-Workspace/PDUWorkspace.exe`, `_internal/assets/web`,
   `_internal/demo`, `_internal/pdu_exam_observer/assets/models`,
   `tools/ffmpeg.exe`, `START.cmd`, `HUONG_DAN.md`, `SOURCE_MANIFEST.json`,
   `DELIVERY_MANIFEST.json`, `FFMPEG_LICENSE.txt`) and label the existing
   `PDU-Exam-Observer` section HISTORICAL.
5. `demo/README.md` — correct the adapter claim: `demo/events.jsonl` IS wired
   into `replay_demo_alerts` via `POST /api/v1/demo/replay`
   (`services/core.py:389-404`, `factories.py:365-373`) and ships in the
   bundle; keep the "synthetic demo, not research data" boundary.
6. `pyproject.toml` — update `description` to reflect the current system
   (e.g. "Local research-only PDU examination observer — M0–M7 technical
   delivery; collection gated by recorded authority").
7. `docs/WORKSPACE_GUIDE_VI.md` — verify every command/path against code
   (`__main__.py` routes, `authority_cli.py:274-284` flags, `workspace_cli.py`
   PIN rule, `service.py:1116` frozen-rules path). Correct the
   `authority-template` reference only if Task 06 wires the entry point;
   otherwise mark it "source tree only" until then. Re-check the exe name
   `PDUWorkspace.exe` against `__main__.py` / `PDU-Workspace.spec`.
8. Remove or annotate the stale `_archive/` entry in
   `configuration.py`'s forbidden-root set (L13) — code change allowed here
   because it is comment/constant-only and defensive; if edited, run
   `pytest tests/backend/test_launcher.py tests/backend/test_m1_backend.py -q`.

## Acceptance

- Every edited claim is verified against the current code line-by-line before
  writing (no claim copied from memory).
- `git diff` limited to the listed docs + at most the one constant in
  `configuration.py` + `pyproject.toml` description.
- Docs gates: `pytest tests/packaging -q` (S3A hash pins cover
  `packaging/README.txt`, not these docs — confirm no pin breakage),
  `pytest tests/research -q`.
- No new `VERIFIED` wording without a matching evidence artifact.
