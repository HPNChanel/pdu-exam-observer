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
