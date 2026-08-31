# GOV-P1 Synthetic Withdrawal and Deletion Rehearsal Implementation Plan

**Goal:** Implement the approved synthetic-only rehearsal and deterministic
institutional-review pack without changing production M1 or any authority
boundary.

**Spec:**
`docs/superpowers/specs/2026-08-30-gov-p1-synthetic-withdrawal-rehearsal-design.md`

## Global constraints

- Preserve the proposal, GOV-P0, RP2, B0.3 kit, and production M1 source.
- Do not invoke camera, native, participant, network, export, authority,
  installer, preparation, preflight, M2, or M3 paths.
- Delete only fixed synthetic files under a runner-owned temporary root.
- Never mark production withdrawal tasks complete.
- Keep readiness, collection, physical access, and authority false/unissued.

## Task 1 - Contracts and TDD RED

- [x] Materialize the approved design and plan.
- [x] Create the GOV-P1 contract and dossier source artifacts.
- [x] Write focused mutation and runtime tests before implementation.
- [x] Observe RED because the runner/builder modules are absent.

## Task 2 - Synthetic rehearsal runner

- [x] Implement closed contract parsing and owned-path validation.
- [x] Implement the two-session M1 rehearsal and deterministic redaction.
- [x] Implement exact fixture deletion, sentinel proof, cleanup, and CLI modes.
- [x] Make runner-focused tests, Ruff, and mypy pass.

## Task 3 - Deterministic pack builder

- [x] Implement source/receipt semantics and immutable-input binding.
- [x] Implement deterministic manifest/validation write and check modes.
- [x] Generate the rehearsal receipt and GOV-P1 pack.
- [x] Make all GOV-P1 mutation tests pass.

## Task 4 - Governance synchronization and closure

- [x] Update current task, task contract, governance, roadmap, gates, risks,
  and README with the precise GOV-P1 evidence ceiling.
- [x] Verify GOV-P0, RP2, and proposal hashes remain unchanged.
- [x] Run focused M1 regressions, scoped Ruff/mypy, both CLIs, and full pytest.
- [x] Inspect every artifact and record residual external/reconciler blockers.
