# Task 05 — Hermetic frontend build inside the delivery builder

**Type:** build/tooling + packaging test. **Depends on:** DG-1; run on a
quiet tree after Tasks 01–04 land.

## Objective

Root cause of the candidate-07 stale-frontend incident (fixed manually in
Task 10): `packaging/PDU-Workspace.spec:11` packs
`(root / "apps/web/dist")` — whatever bytes happen to be there — while
`source_manifest()` (`scripts/build_completion_delivery.py:26-56`) only
hash-binds `apps/web/src`, `public`, `package.json`, `package-lock.json`,
`vite.config.ts`, `tsconfig*`. `dist` is untracked and unverified. Nothing
prevents shipping a stale frontend again.

Under DG-1(a) the builder produces dist itself from pinned inputs:

- `npm ci` (lockfile-exact, `--ignore-scripts` if compatible with the
  vite/tsc toolchain — verify) then
- `npm run build` (`tsc -b && vite build`)
- inside `apps/web`, before the PyInstaller step (`:154-167`).

## Steps

1. In `build_completion_delivery.py`, insert a frontend stage between the
   `source_manifest()` snapshot and the PyInstaller run:
   - resolve `npm`/`node` executables explicitly (no shell, fixed argv,
     `cwd=apps/web`); fail closed `FRONTEND_TOOLCHAIN_UNAVAILABLE` if not
     found;
   - `npm ci` must be the lockfile path (`--no-audit --no-fund`; decide
     `--ignore-scripts` based on whether vite needs lifecycle scripts —
     verify on this repo);
   - `npm run build` overwrites `apps/web/dist`;
   - both commands' stdout/stderr go to `build.log` (same `with` block
     pattern as PyInstaller);
   - record `node --version` and `npm --version` in `build-receipt.json`
     alongside the existing toolchain fields;
   - record a **dist manifest** (relative path + sha256 for every file in
     the produced `dist/`) in `build-receipt.json` — the packed bytes are
     now a provable output of pinned inputs.
2. Keep `source_manifest()` source-only (dist is a derived output, not a
   source input — the manifest semantics stay honest).
3. Update `docs/spec/BUILD_TOOLCHAIN.md`: add Node/npm versions used
   (`node --version` at build time — currently Node 24.x, npm bundled),
   `npm ci` semantics, and one sentence that dist is a derived artifact
   produced in-build.
4. Tests (`tests/packaging/`):
   - unit-test the new stage seam: inject a fake runner, assert argv is
     fixed (`ci`, `run`, `build` — no shell string), cwd is `apps/web`,
     and failure → `FRONTEND_TOOLCHAIN_UNAVAILABLE`;
   - assert `build-receipt.json` schema gains `node_version`,
     `npm_version`, `frontend_dist_manifest` (extend the existing receipt
     test);
   - do not run a real npm in unit tests — the real build is exercised by
     rebuilding the candidate below.
5. Rebuild candidate-07 **once** under the new builder (same name, same
   tree — the rebuild is to prove the stage works, not to mint a new
   lineage entry). Re-run `verify_completion_package.py` original +
   relocated; update `docs/ai/CANDIDATE_07_LINEAGE.md` hashes and note the
   rebuild reason.
6. Gates: focused packaging tests, then `pytest tests/packaging
   tests/research` + ruff + mypy (scripts are not in the mypy package
   scope but keep them lint-clean).

## Acceptance

- A clean tree with **no** `apps/web/dist` still builds a complete bundle
  (the strongest freshness proof).
- `build-receipt.json` records node/npm versions and the dist manifest.
- Rebuilt candidate-07 verifies PASS original + relocated, same host.
- Lineage doc updated; execution note appended here; commit separately
  (docs + script + test; bundle stays gitignored).
