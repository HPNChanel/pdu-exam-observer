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
