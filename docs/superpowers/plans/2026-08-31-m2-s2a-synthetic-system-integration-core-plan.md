# M2-S2A Synthetic System Integration Core Implementation Plan

> **For agentic workers:** execute inline with test-driven development in the
> shared checkout.  Do not create a branch, commit, push, rebuild the release
> package, or perform a physical/device/participant operation.

**Goal:** Compose the synthetic runner, D1 evaluator, canonical minimized
receipt, and M2 persistence seam for one accelerated 60-second preflight.

**Architecture:** A focused integration core validates and maps synthetic
observations, rebuilds D1 bindings, verifies the aggregate receipt, and persists
both pass and no-go evidence.  A separate built-in fixture module supplies a
deterministic zero-pose smoke bundle; a no-argument CLI exercises it in an owned
temporary root.

**Tech stack:** Python 3.12, dataclasses/enums, SQLite-backed existing M1/M2
stores, pytest, Ruff, strict mypy.

**Spec:**
`docs/superpowers/specs/2026-08-31-m2-s2a-synthetic-system-integration-core-design.md`

## Global constraints

- Evidence kind is always `SIMULATED`; run kind is only `PREFLIGHT_60S`.
- Persist both semantic pass and semantic no-go receipts.
- No raw landmarks, frames, local paths, identity, participant data, camera,
  audio, API/UI, export, real deletion, or package mutation.
- `device_gate_decision=UNVERIFIED`, `d1_go=false`, and
  `authority_status=AUTHORITY_NOT_ISSUED` are invariant.
- No database migration; RP2 static bindings are rebuilt after source settles.

## Tasks

1. Materialize this spec/plan, add exactly 12 non-parametrized tests, and
   observe missing-module RED.
2. Add the public fixture-input digest helper, canonical integration contracts,
   exhaustive adapter, and fail-closed receipt behavior.
3. Add the exact 60-second D1 binding, semantic verification, minimized
   canonical artifact, pass/no-go persistence, and expanded failure allowlist.
4. Add the deterministic 977-frame zero-pose fixture and no-argument sanitized
   temporary-root CLI.
5. Bind new artifacts/policy preimages into RP2, regenerate RP2 once, update
   current ledgers and three existing governance tests without adding functions.
6. Run focused tests, CLI determinism, Ruff, strict mypy, research/RP2 gates,
   exact 892-test collection/full suite, release-manifest verification, and
   zero-process/listener checks.

## Stop conditions

Stop without publishing the M2-S2A marker if any invalid D1 receipt persists,
any artifact contains forbidden data, a failure claims an artifact, the CLI
accepts external input or leaks a path, RP2 omits new source, the package
changes, or an authority/device/participant flag opens.

