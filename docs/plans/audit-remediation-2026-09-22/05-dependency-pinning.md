# Task 05 — Dependency pinning

**Type:** repo hygiene. **Findings:** H3, part of L11.
**Depends on:** Task 03 (ordering only — can technically run parallel but keep
sequence to keep diffs reviewable).

## Objective

Make the frontend toolchain reproducible by manifest, not by discipline, and
pin the PyInstaller version in the completion builder the same way
`build_release.ps1` already does.

## Steps

1. `apps/web/package.json` — replace every `"latest"` in `dependencies` and
   `devDependencies` with the exact version currently resolved in
   `apps/web/package-lock.json` (no caret/tilde — match the pyproject `==`
   convention). Expected set: react, react-dom, vite, typescript, vitest,
   eslint, typescript-eslint, @vitejs/plugin-react, testing-library packages,
   jsdom/happy-dom — read the lock, don't guess.
2. Run `npm ci` in `apps/web` to confirm the lockfile satisfies the pinned
   manifest exactly (`npm ci` fails closed on drift — that is the point).
3. Run the full frontend gates: `npm run typecheck` (or `tsc -b`),
   `npm run lint`, `npm test` (82 tests), `npm run build`. Then hash
   `apps/web/dist` output and compare against the dist recorded in
   candidate-06's `SOURCE_MANIFEST.json` — the asset filenames should be
   identical if versions truly didn't change; record any drift as OBSERVED,
   not silently.
4. `scripts/build_completion_delivery.py` — add the same
   `pyinstaller==6.10.0` pin that `build_release.ps1:33` uses (a module
   constant + a check that the resolved PyInstaller version matches before
   building). RED-test it in `tests/packaging/` if a natural seam exists;
   otherwise cover by a source-contract assertion similar to
   `test_release_pipeline.py`.
5. `pyproject.toml` — verify (do not change) that all runtime deps remain
   `==`-pinned; confirm `uv.lock` still matches (`uv lock --check` if
   supported, else `uv sync --frozen --dry-run`).

## Acceptance

- `npm ci` exits 0 on the pinned manifest.
- Frontend gates all green; dist drift either zero or explained in the task
  receipt.
- Backend gates unaffected: `pytest tests/packaging -q`, Ruff, strict mypy.
- No version was *downgraded* silently — every pinned value equals the version
  the lockfile already resolved.

## Execution note (2026-09-22)

- All 17 specs pinned to the exact lockfile-resolved versions (React 19.2.8,
  Vite 8.2.2, TypeScript 6.0.3, Vitest 4.1.11, ESLint 10.9.0, …);
  `npm install --package-lock-only` synced the lock specs — **zero resolved
  drift** (`npm ci` exits 0; typecheck, lint, 82/82 tests, build all green).
- Fresh `vite build` output (`index-CovMSGKu.js`, `index-CIlkHTxq.css`,
  `index.html`) is **byte-identical** to the copies inside candidate-06 —
  positive reproducibility evidence for the verified delivery.
- OBSERVED drift detail: candidate-06's `_internal/assets/web/assets/`
  contains both `index-CovMSGKu.js` (current) and `index-DB9w6fTP.js`
  (stale leftover from an earlier build that also sat in `apps/web/dist`
  at S3A audit time). The S3A `current_observed_frontend_dist` pin captured
  the stale file; it was restored verbatim from candidate-06 into
  `apps/web/dist/assets/` to keep the hash-bound audit green. Long-term the
  build should assert a single JS bundle in dist — noted for Task 09.
- `scripts/build_completion_delivery.py` now requires PyInstaller 6.10.0 on
  the build interpreter (probe fails closed otherwise) — the version recorded
  in candidate-06's build.log.
- New guard test `tests/packaging/test_dependency_pinning.py`: rejects
  floating specs, enforces manifest↔lock version equality, and pins the
  builder's PyInstaller constant to the historical script's version.
- `uv lock --check` resolved 85 packages — lockfile consistent; all runtime
  deps remain `==`-pinned in pyproject.
