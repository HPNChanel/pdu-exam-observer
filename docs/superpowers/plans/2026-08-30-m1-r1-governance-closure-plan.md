# M1-R1 Governance Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Reconcile the project roadmap, acceptance/quality gates, risk ledger,
and handoff state with the current M1-R1 synthetic-only packaged evidence.

**Architecture:** Treat `docs/ai/M1_R1_VERIFICATION.md`, the packaged runtime
acceptance receipt, and Task Contract v9 as current authority. Preserve M0, M1,
and GOV-P1 results as explicitly historical receipts, then add one current G9
boundary without changing product code, package bytes, or research authority.

**Tech Stack:** Markdown authority ledgers, pytest documentation-consistency
tests, Ruff, SHA-256/manifest verification.

**Spec:** Approved conversational design and
`docs/ai/M1_R1_VERIFICATION.md`.

## Global Constraints

- Canonical proposal SHA-256 remains
  `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
- Executable and manifest hashes remain `EC0D26A9...D7FF` and
  `9C4DDE09...C256`; do not rebuild the package.
- Preserve `AUTHORITY_NOT_ISSUED`, all collection/deletion false flags, and M2
  `unopened`.
- Do not edit proposal traceability, runtime source, schema, frontend, package,
  or generated acceptance evidence.
- This workspace has no Git metadata; do not make commit or branch claims.

---

### Task 1: Governance consistency RED

**Files:**

- Create: `tests/research/test_m1_r1_governance_closure.py`

- [x] Add three tests for the current evidence tuple, historical/current
  separation, and the binding authority ceiling.
- [x] Run the focused file and observe three expected failures against stale
  roadmap/gate wording.

### Task 2: Roadmap and gate reconciliation

**Files:**

- Modify: `docs/plans/ROADMAP.md`
- Modify: `docs/plans/ACCEPTANCE_GATES.md`
- Modify: `docs/ai/QUALITY_GATES.md`

- [x] Label M0/M1/GOV-P1 package evidence as historical.
- [x] Add the current M1-R1 milestone and G9 with exact hashes, counts,
  packaged 201/403 behavior, revocation/no-mutation evidence, and residuals.
- [x] Distinguish the packaged 843-test revision from the governance-only
  846-test collection, including the two load-sensitive full-run residuals.

### Task 3: Risk and handoff reconciliation

**Files:**

- Modify: `docs/plans/RISK_REGISTER.md`
- Modify: `docs/ai/CURRENT_TASK.md`
- Modify: `docs/ai/M1_R1_VERIFICATION.md`

- [x] Record PIN clearing, the superseded GOV-P1 risk, false-authority risk,
  and cross-ledger drift control.
- [x] Record governance closure without changing Task Contract v9 or the
  binding output ceiling.

### Task 4: Verification and closure

- [x] Run the three focused governance tests, research tests, Ruff, collect
  count, and the complete Python suite. Two complete invocations each exposed
  one distinct load-sensitive timeout; both affected tests pass alone, so no
  clean 846/846 receipt is claimed.
- [x] Verify the manifest and exact proposal/package hashes remain unchanged.
- [x] Confirm no sensitive evidence, PDU process, listener, M2 opening, or
  production/release claim was introduced.
