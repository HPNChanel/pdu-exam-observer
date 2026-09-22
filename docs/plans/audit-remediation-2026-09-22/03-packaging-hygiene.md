# Task 03 — Packaging hygiene and candidate marking

**Type:** repo hygiene (files + test re-pin; no runtime code change).
**Findings:** H1, M5, L7, L14. **Depends on:** Tasks 01–02, DG-4.

## Objective

Make it impossible to mistake a stale script, superseded candidate, or failed
handoff for the verified 2026-09-08 delivery.

## Steps

1. **Record candidate-06 integrity baseline first:** compute SHA-256 of
   `packaging/candidates/completion-2026-09-08/candidate-06/PDU-Workspace-local.zip`
   and `packaging/release/PDU-Exam-Observer/PDUExamObserver.exe`; store them
   in a scratch note. At task end, re-hash and require identical values —
   this task must not mutate either artifact.
2. **Stale release path (H1 + DG-4):**
   - Add a HISTORICAL banner comment block at the top of
     `packaging/PDU-Exam-Observer.spec` and `scripts/build_release.ps1`
     stating: produces the M1-style `PDUExamObserver.exe` bundle, is NOT the
     verified workspace delivery, and is retained for provenance only.
   - In `build_release.ps1`, add a fail-fast guard near the top:
     `Write-Error "...historical spec... use build_completion_delivery.py"; exit 2`
     — unless DG-4 chose a full rewrite to the workspace spec, in which case
     re-point it at `packaging/PDU-Workspace.spec` and update
     `tests/packaging/test_release_pipeline.py` expectations in the same
     change.
   - Update `packaging/README.txt` with the same HISTORICAL banner and a
     pointer to `scripts/build_completion_delivery.py` +
     `packaging/PDU-Workspace.spec` for the current build path.
3. **Superseded candidates (M5):** write `SUPERSEDED.txt` (one line:
   superseded by candidate-06, build timestamp, reason) into
   `packaging/candidates/completion-2026-09-08/candidate-04/` and
   `candidate-05/`. These dirs are gitignored — the markers protect human
   reviewers, not git.
4. **Failed/diagnostic handoffs (M5):** prepend a one-line banner inside each
   `packaging/handoffs/m2-s3e-failed-*/` and `m2-s3e-diagnostic-fourth/`
   `README_M2_S3E_HANDOFF.txt` copy: "DIAGNOSTIC/FAILED ATTEMPT — not the
   delivered handoff; see `m2-s3e-clean-environment/`".
5. **Historical release (M5):** add `HISTORICAL.txt` to
   `packaging/release/PDU-Exam-Observer/` (do not touch the exe or
   manifests — marker file only) and a banner line at the top of
   `packaging/README.txt` if not already done in step 2.
6. **`.gitignore` (L7):** add `packaging/manifest-metadata.json`.
7. **Re-pin the S3A audit test (global constraint 3):** run
   `pytest tests/packaging/test_m2_s3a_package_gap_audit.py -q`, read the
   failing SHA assertions, compute the new digests of the edited files
   (`Get-FileHash` / `hashlib.sha256`), update the pinned constants in
   `tests/packaging/test_m2_s3a_package_gap_audit.py`, and re-run until green.
   If the audit also binds RP2 inventory, defer the digest tuple update to
   Task 10 but keep this test green now.
8. **Optional (L14):** add one assertion in `test_release_pipeline.py` that
   the historical spec lacks `collect_submodules` — pinning the known-stale
   state so a silent "fix" is also caught. Skip if DG-4 rewrote the script.

## Acceptance

- `pytest tests/packaging -q` green, including the re-pinned S3A audit.
- Ruff + strict mypy clean (script/comment changes only — should be trivial).
- candidate-06 zip SHA-256 and historical exe SHA-256 identical to step 1.
- `git status` shows only intended file additions/edits; no artifacts deleted.
