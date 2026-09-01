# M2-S2B Synthetic Nominal 20-Minute Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> task-by-task.  Preserve the existing dirty M2-S2A checkout; do not reset,
> stash, commit, push, rebuild the package, or perform physical/device work.

**Goal:** Add an accelerated, deterministic 20-minute synthetic M2 run with
canonical D1 evaluation, minimized persistence, fail-closed faults, and no
device or collection authority.

**Architecture:** Preserve the public M2-S2A preflight wrapper and add a
nominal wrapper.  Both delegate to a fixed private run-contract engine; the
existing D1 evaluator and M2 schema v2 remain unchanged.

**Tech Stack:** Python 3.12, dataclasses, pytest, Ruff, strict mypy, SQLite M2
persistence, canonical JSON and SHA-256.

**Spec:**
`docs/superpowers/specs/2026-08-31-m2-s2b-synthetic-nominal-20m-design.md`

## Global constraints

- Evidence remains `SIMULATED`; camera, audio, device enumeration, participant
  contact, export, real deletion, external submission, deployment and release
  are prohibited.
- The nominal run is fixed at 18,077 frames, 1,200 measured seconds, five
  warmup seconds, and `1280x720@15fps` using accelerated timestamps.
- Authority remains `AUTHORITY_NOT_ISSUED`, `device_gate_decision=UNVERIFIED`,
  `d1_go=false`, and every readiness/collection flag false.
- No D1 schema, M2 DDL, package, GOV-P0-P5A, Git history, commit, or push change.

## Task 1: Approved artifacts and RED tests

- Materialize this plan and the approved design.
- Add exactly 12 non-parametrized tests in
  `tests/backend/test_m2_synthetic_nominal_integration.py` covering fixture,
  wrappers, pass metrics, accounting, timing, thresholds, technical no-go,
  disk/encoder failures, privacy/tamper, replay/persistence, minimized artifact,
  and CLI behavior.
- Confirm baseline 892 before the new tests and a missing nominal API/module RED.

## Task 2: Shared engine and nominal PASS

- Refactor `m2_synthetic_integration.py` behind `_SyntheticRunContract` and
  `_M2SyntheticRunEngine` while preserving all S2A public behavior.
- Add `SyntheticNominalRequest` and `M2SyntheticNominalCore` with fixed
  `NOMINAL_20M` behavior.
- Add `m2_synthetic_nominal_fixture.py` with exact deterministic frame and
  golden bindings.
- Persist canonical `M2_SYNTHETIC_NOMINAL_RECEIPT` artifacts through schema v2.

## Task 3: Fault matrix and CLI

- Exercise runner timing/input/pose/quality failures, D1 threshold and injected
  encoder/disk/durability failures, privacy, semantic tamper, idempotency,
  persistence faults, and withdrawal races.
- Add the no-argument nominal CLI with owned temporary-root cleanup and bounded
  canonical output.
- Require S2A regression, nominal focused, Ruff and strict mypy gates.

## Task 4: RP2 and governance reconciliation

- Bind the nominal fixture, test, and CLI; update fixed status/run/fault policy
  preimages and regenerate RP2 once after source stability.
- Record the resulting tuple in current task/contract/roadmap, G16, G12 and
  R-34; extend the existing three governance consistency tests only.
- Run RP2, research, exact 904-test collection/full suite, release manifest,
  immutable-input, no-process/listener and dirty-scope checks.

## Stop conditions

Stop without publishing the M2-S2B marker if S2A regresses, a caller can choose
run authority, physical waiting/device access appears, raw or identifying data
is persisted, forged/corrupt state produces false success, RP2 or any required
gate fails, authority opens, or a PDU process/listener remains.

