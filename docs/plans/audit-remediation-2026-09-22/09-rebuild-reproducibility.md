# Task 09 — Rebuild reproducibility record

**Type:** build evidence + docs. **Findings:** L11, residual of H1.
**Depends on:** Tasks 03–08 (builds on final source), DG-3.

## Objective

Make the verified-candidate build reproducible *in principle*: a documented,
pinned toolchain plus one honest rebuild attempt that establishes the lineage
between candidate-06 (2026-09-08 source) and the post-remediation source.

## Steps

1. **Toolchain doc** — extend `docs/spec/PACKAGING_DISTRIBUTION.md` (or a new
   `docs/spec/BUILD_TOOLCHAIN.md` linked from it) recording everything
   `build_completion_delivery.py` needs: Python 3.11.x exact patch version,
   Node/npm versions, `uv` version, PyInstaller `==6.10.0`, the
   `--build-python`/`--ffmpeg` inputs, env-isolation requirements
   (sanitized PATH), and the `package-env` creation steps that no longer
   exist in-tree.
2. **FFmpeg provenance (DG-3):**
   - If "recipe": extend `docs/source/M2_D1_NATIVE_ASSET_PROVENANCE.md` with
     the acquisition recipe (source URL, version, sha256 `5af82a0d…`,
     verification command) — enough for a third party to obtain the
     identical binary.
   - If "vendor": place `tools/ffmpeg.exe` + license in-repo, update
     `.gitignore` accordingly, and record the binary SHA-256 in the spec.
3. **New candidate build (candidate-07):** run
   `scripts/build_completion_delivery.py` against current source into
   `packaging/candidates/remediation-2026-09-22/candidate-07/` (new
   directory — never inside `completion-2026-09-08/`). Keep its
   `SOURCE_MANIFEST.json`, `build-receipt.json`, `build.log`.
4. **Verify candidate-07:** run
   `scripts/verify_completion_package.py --bundle … --model … --output …`
   (the self-contained packaged workflow: import model, pair, record
   synthetic session, export, withdraw). Record results; any failure is a
   finding, not a retry loop — stop and report.
5. **Lineage receipt:** write
   `docs/ai/CANDIDATE_07_LINEAGE.md` stating precisely: candidate-06 =
   evidence for 2026-09-08 source (immutable); candidate-07 = evidence for
   post-remediation source; which audit findings 06 still carries (e.g. old
   THIRD_PARTY_NOTICES) and that it is superseded for delivery purposes but
   retained as historical evidence.
6. **Optional same-host relocation:** if time permits, reuse the S3E-A
   harness pattern for one relocated run of candidate-07; otherwise mark
   UNVERIFIED.

## Acceptance

- `candidate-07` build receipt + verification JSON exist and pass; exe SHA
  recorded.
- Toolchain doc sufficient that a second operator could attempt the build
  without asking questions.
- candidate-06 bytes + receipts byte-identical before/after (immutability
  check — recompute the zip SHA).
- All gates green on the final tree.
- No claim of clean-machine verification — that's Task 11's external item.
