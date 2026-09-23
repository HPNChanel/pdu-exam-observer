# Task 07 — Ledger note and close-out

**Type:** documentation + commit hygiene. **Depends on:** Tasks 01–06.

## Objective

Small-scope version of the remediation Task-10 reconciliation: keep the
ledgers honest after this batch without rewriting history.

## Steps

1. Refresh the **as-of annotation** date and counts in:
   - `docs/ai/QUALITY_GATES.md` (extend the 2026-09-22 note or add a dated
     line — do not rewrite per-milestone sections),
   - `docs/ai/CURRENT_TASK.md` milestone block (append the batch status
     token and any changed counts/digests),
   - `docs/plans/ACCEPTANCE_GATES.md` as-of note.
2. If Task 04 landed, update `docs/plans/RISK_REGISTER.md` M2b residual
   wording (the "delegated to authority issuance" line) — annotate, don't
   delete history.
3. If Task 05 rebuilt candidate-07, confirm `CANDIDATE_07_LINEAGE.md` is
   current (should already be done inside Task 05).
4. RP2 check: if any file in the static-binding inventory changed
   (`launcher.py` will, if Task 04 lands; `m2_d1_native.py` in Task 01),
   regenerate `scripts/build_m2_d1_n2_rp2.py --write` **once** for this
   batch and update the test-side constants
   (`tests/research/test_m1_r1_governance_closure.py`), then record the
   new tuple in the as-of annotations.
5. Append execution notes to every task file in this folder.
6. Immutability spot-check (cheap): proposal SHA, candidate-06 zip SHA,
   `git status` clean except intended files.
7. Final commit(s): prefer one commit per task as each lands; this file's
   changes go with the last commit.

## Acceptance

- All ledger annotations reflect the batch truthfully; no ceiling moved.
- RP2 tuple (if regenerated) recorded consistently in test constants +
  ledgers.
- Working tree clean at the end; batch fully committed.

## Execution note — 2026-09-23

Batch close-out performed without rewriting history:

- `QUALITY_GATES.md`, `CURRENT_TASK.md`, `ACCEPTANCE_GATES.md`: dated
  2026-09-23 as-of annotations added above the 2026-09-22 blocks —
  gate-runner PASS (`1125` Python tests, `85` frontend tests, ruff, mypy),
  current tuple `ae02b69f…`/`60e65b93…`/`302dc815…`, candidate-07 exe
  `e31a7f2e…` / zip `c3426f1c…`. Older notes kept as historical.
- `CURRENT_TASK.md` gap paragraph annotated: the stale-dist delivery risk
  is closed by the in-builder frontend stage (Task 05); storage labels
  now probed (Task 04). GAP-08 still `OPEN` in EXTERNAL_GATES.
- `RISK_REGISTER.md`: new `R-47` row records M2b mitigation (probe
  upgrades evidence honesty; readiness gates unchanged).
- `CANDIDATE_07_LINEAGE.md` already current from Task 05.
- RP2: `--check` PASS; no regeneration needed beyond the in-task regens
  (Task 01 `ca9e6118…` → superseded by Task 04 `ae02b69f…`, the current
  value). Test constants consistent
  (`test_m1_r1_governance_closure.py` 3/3 governance pinning tests pass).
- Immutability spot-check: proposal `2CD5F6FD…` unchanged; candidate-06
  zip `f5bd0add…` unchanged; working tree contains only intended files.
- Ceilings untouched: `authority_status=AUTHORITY_NOT_ISSUED`,
  `clean_machine_verified=false`, `d1_go=false`,
  `collection_authorized=false`, `release_authorized=false`.
