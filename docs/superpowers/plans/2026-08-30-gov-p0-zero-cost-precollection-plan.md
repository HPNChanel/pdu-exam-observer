# GOV-P0 Zero-Cost Pre-Collection Governance Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> task-by-task. Steps use checkbox syntax. This checkout has no Git metadata;
> do not claim commits, branches, PRs, or merges.

**Goal:** Defer B0.3 without blocking zero-cost research preparation, then
materialize a canonical fail-closed pre-collection governance pack.

**Architecture:** Keep the B0.3 kit inert and untouched. A versioned repository
pack separates source/method contracts, participant-facing drafts, external
gates, and deterministic structural validation. A structural pass never opens
M2, M3, pilot, confirmatory collection, or any authority path.

**Tech Stack:** Markdown, canonical JSON, Python 3.11 standard library, SHA-256,
pytest 8.4.1, Ruff 0.12.10, mypy 1.17.1.

**Spec:**
`docs/superpowers/specs/2026-08-30-gov-p0-zero-cost-precollection-design.md`

## Global constraints

- Do not modify the canonical proposal or any RP2-bound artifact/preimage.
- Do not regenerate RP2.
- Do not touch the external B0.3 kit.
- Do not create or invoke credentials, authority, native, camera, participant,
  installer, prepare, preflight, seal, or export paths.
- Keep all collection and physical authorization fields false/unissued.

### Task 1: Materialize governance and method contracts

- [x] Record the approved design and implementation plan.
- [x] Create the binding pre-collection governance specification.
- [x] Transition current governance to GOV-P0 with B0.3 explicitly deferred.
- [x] Create the source register and method/data templates.

### Task 2: Implement deterministic validation test-first

- [x] Write mutation tests and observe RED because the builder is missing.
- [x] Implement closed JSON envelopes and semantic validators.
- [x] Implement deterministic manifest and receipt write/check modes.
- [x] Make all focused tests, Ruff, and mypy pass.

### Task 3: Build and close the static pack

- [x] Generate the manifest and validation receipt.
- [x] Synchronize protocol, traceability, roadmap, gates, risk, and task state.
- [x] Verify proposal hash and unchanged RP2.
- [x] Run focused and full Python suites.
- [x] Inspect every artifact and record only the static governance ceiling.
