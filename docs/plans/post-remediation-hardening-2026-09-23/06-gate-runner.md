# Task 06 — Canonical gate-runner

**Type:** tooling script. **Depends on:** DG-3 (Python assumed).

## Objective

The Task-10 reconciliation ran four gates by hand and redirected outputs
manually. Every future reconciliation, audit, or milestone needs the same
sequence — encode it once.

## Steps

1. New `scripts/run_all_gates.py` (stdlib only):
   - `--output DIR` (default `output/gates-<YYYYMMDD>`);
   - runs in order, each captured to its own file in the output dir:
     1. `python -m pytest tests -q` → `pytest-full.txt`
     2. `npm run typecheck`, `npm run lint`, `npm test -- --run`,
        `npm run build` in `apps/web` → `frontend-gates.txt`
     3. `python -m ruff check .` → `ruff.txt`
     4. `python -m mypy` → `mypy.txt`
   - fixed argv lists, `cwd` pinned, no shell; stream to both console and
     file (tee-style) so a hung gate is still observable;
   - stop-on-failure by default with `--keep-going` to run all anyway;
   - final machine-readable summary `gate-summary.json`:
     `{gate, command, exit_code, duration_s}` per step plus overall
     `status: PASS|FAIL`;
   - `--python` override defaulting to `sys.executable` (so the venv
     interpreter is used when invoked through it);
   - `--skip-frontend` / `--skip-pytest` flags for scoped runs.
2. Add the script to `docs/spec/BUILD_TOOLCHAIN.md` (or AGENTS-adjacent
   docs) as the canonical local gate command.
3. Self-test lightly in `tests/` only if there is a natural home for a
   script-surface test (pattern: `tests/backend/test_cli_surfaces.py`
   exists — a `--help`/dry-plan smoke test fits); do not run real gates in
   unit tests.
4. Gates: run the script once for real — it is its own verification —
   saving under `output/gates-2026-09-23/`.

## Acceptance

- One command reproduces the full Task-10 gate sequence with captured
  outputs and a JSON summary.
- No change to any gate semantics; the script only orchestrates.
- Execution note appended here; commit separately.

## Execution note — 2026-09-23

Implemented `scripts/run_all_gates.py` (stdlib only, DG-3 Python):

- Fixed argv tuples, pinned cwd, no shell; `subprocess.Popen` line-streamed
  tee to console + per-gate file (hung gate stays observable).
- Order: pytest → frontend (typecheck/lint/test/build, one shared
  `frontend-gates.txt`) → ruff → mypy. `--keep-going`, `--skip-frontend`,
  `--skip-pytest`, `--python`, `--npm`, `--output` supported.
- `gate-summary.json`: schema_version, status, per-step
  `{gate, command, cwd, exit_code, duration_s}`, skipped list,
  stop_on_failure flag. Exit code mirrors overall status.
- Encoding hardening learned on first real run: console cp1252 cannot
  encode vitest's U+2713 — `sys.stdout/stderr.reconfigure(errors="replace")`
  added so console glyphs degrade instead of crashing; per-gate files
  always get exact utf-8.
- npm resolved via `shutil.which` (same FRONTEND_TOOLCHAIN_UNAVAILABLE
  token as the delivery builder).

Docs: BUILD_TOOLCHAIN.md gained a "Canonical local gate runner" section.
Tests: `test_run_all_gates_help_is_bounded` +
`test_run_all_gates_step_surface_is_fixed_argv` in
`tests/backend/test_cli_surfaces.py` (no real gate runs).

Verified by running itself: `output/gates-2026-09-23/` — all 7 steps
exit 0 (pytest 361s, frontend ~136s, ruff, mypy), `status: PASS`.
