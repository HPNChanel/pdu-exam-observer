# M2-S2E Strict Same-Revision Synthetic Evidence Reproduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` and `superpowers:test-driven-development`.
> Steps use checkbox syntax for tracking. Work inline in the approved
> task-scoped dirty checkout; do not commit, push, rebuild, deploy, or release.

**Goal:** Reproduce a verified M2-S2D synthetic bundle in a fresh owned
workspace and emit exact, source-mismatch, semantic-mismatch, or bounded
failure evidence without opening device or collection authority.

**Architecture:** A structured S2D loader feeds a current-source binding gate.
Matching evidence is replayed through the existing S2A/S2B core and verified
persistence path; a closed comparator produces a canonical S2E receipt only
after cleanup.

**Tech Stack:** Python 3.11, pytest, SQLite-backed M2 persistence, Ruff, mypy.

**Spec:**
`docs/superpowers/specs/2026-09-01-m2-s2e-synthetic-evidence-reproduction-design.md`

## Global constraints

- Input maximum: 4,000,000 bytes.
- Built-in `PREFLIGHT_60S` and `NOMINAL_20M` fixtures only.
- No public dependency injection, device/path/URL surface, API, UI, migration,
  package rebuild, commit, push, deployment, or release.
- Preserve every false/unissued authority field in the approved design.
- Baseline Python collection is 935; add exactly ten tests for 945.

---

### Task 1: Materialize contracts and establish RED

- [ ] Create the approved spec/plan and the ten-function S2E test module.
- [ ] Run the focused module before production modules exist; require import or
  missing-contract RED.

### Task 2: Structured S2D source and shared environment binding

- [ ] Add `VerifiedSyntheticEvidenceSource` and the strict loader without
  changing existing S2D verification output.
- [ ] Centralize the closed source inventory and current binding helper.
- [ ] Route the S2C/S2D review service through the shared helper.
- [ ] Run evidence, service, and API regressions to GREEN.

### Task 3: Exact replay and comparison

- [ ] Implement canonical S2E receipt/enums and fail-closed validation.
- [ ] Short-circuit source mismatch before workspace creation.
- [ ] Execute the locked fixture in synthetic M1/M2 temporary state, verify the
  persisted artifact, rebuild a transient S2D bundle, and compare all closed
  fields.
- [ ] Close and remove the workspace before exact success.

### Task 4: Failure paths and CLI

- [ ] Implement bounded operational failure receipts and semantic mismatch.
- [ ] Add the safe one-file CLI with exact exit/stdout/stderr behavior.
- [ ] Run adversarial mutants and focused S2A-S2E regressions.

### Task 5: RP2 and governance reconciliation

- [ ] Add four source/tool entries and four policy preimages to RP2.
- [ ] Run RP2 `--write` once after final source stabilization, then only
  `--check`.
- [ ] Update current task/contract/roadmap, G19, G15, R-37, governance
  consistency, and the S2E verification receipt with the final tuple.

### Task 6: Final verification

- [ ] Run the ten S2E tests, all S2A-S2E regressions, Ruff, strict mypy, RP2,
  governance, research, exact collection, and one full Python suite.
- [ ] Verify release manifest, proposal SHA, package exclusion, dirty-checkout
  scope, and zero temp/process/listener residue.

## Stop conditions

Do not publish the marker if an invalid S2D bundle enters replay, a source
mismatch creates a workspace, any comparison field is omitted, replay trusts
caller fixture/path/device input, authority mutation becomes semantic mismatch,
cleanup fails, a required gate fails, or package/authority state changes.
