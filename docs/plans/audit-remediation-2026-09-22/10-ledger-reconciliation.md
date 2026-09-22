# Task 10 — Ledger reconciliation and final gates

**Type:** ledger + verification. **Findings:** L9, closes the loop on all
prior tasks. **Depends on:** Tasks 01–09.

## Objective

Produce one authoritative fresh evidence run and reconcile every ledger to
the post-remediation reality — per AGENTS.md, `CURRENT_TASK.md` is updated
only at this milestone.

## Steps

1. **Fresh full gates** (record all counts + durations as OBSERVED):
   - `uv run pytest` — full suite; record collected count and result.
   - `cd apps/web && npm run typecheck && npm run lint && npm test &&
      npm run build`.
   - `uv run ruff check .` and strict `uv run mypy` over
     `pdu_exam_observer`.
   - Save outputs under `output/audit-remediation-2026-09-22/`.
2. **RP2 regeneration:** run `scripts/build_m2_d1_n2_rp2.py --write` exactly
   once to rebind source inventory after the code changes; record the new
   `static_bindings_digest` / `candidate_exact_bytes_sha256` /
   `binding_schema_exact_bytes_sha256` / counts.
3. **Ledger updates:**
   - `docs/ai/QUALITY_GATES.md` — update stale counts (846→actual,
     frontend 58→82+new) with a dated "as of" note; don't rewrite history —
     annotate.
   - `docs/ai/CURRENT_TASK.md` — add the remediation milestone entry at the
     top following the existing format: status token, OBSERVED receipts
     (test counts, digests, candidate-07 sha), unchanged ceilings
     (`authority_status=AUTHORITY_NOT_ISSUED`, `clean_machine_verified=false`,
     `d1_go=false`, …), and the new gap state.
   - `docs/plans/ROADMAP.md` header — point "current implementation" at the
     remediation receipt.
   - `docs/plans/RISK_REGISTER.md` — flip R-44/R-45 to their post-fix status
     ONLY if Tasks 06/07 landed (else leave OPEN with a pointer).
   - `docs/plans/ACCEPTANCE_GATES.md` — annotate any gate whose evidence
     tuple changed.
4. **Remediation receipt:** write
   `docs/ai/AUDIT_REMEDIATION_2026_09_22.md` — for every finding ID in
   `00-findings.md`: disposition (FIXED / ACCEPTED-WITH-RISK-ENTRY /
   DEFERRED / EXTERNAL-BLOCKED), evidence ref, and residual risk. End with
   the unchanged authority ceiling and the explicit statement that no clean
   machine, physical camera, institutional approval, research performance,
   or release authority is claimed.
5. **Immutability sweep (final):**
   - proposal SHA-256 == `2cd5f6fd…` (recompute).
   - candidate-06 zip SHA-256 == `f5bd0add…` (recompute).
   - historical `docs/ai/M2_*` receipts unchanged (`git diff --name-only`
     scoped check).
   - No PDU processes / listeners / temp roots left (`Get-Process`,
     `Get-NetTCPConnection` loopback ports 8765/8766, temp glob).
6. **Report** verified facts separately from residual risks in the session
   summary (AGENTS.md completion rule).

## Acceptance

- Full suite green on final tree; counts recorded.
- New RP2 tuple recorded; old tuples untouched in history.
- `AUDIT_REMEDIATION_2026_09_22.md` covers 100% of finding IDs.
- Immutability sweep passes; no residual processes/listeners/temp roots.
