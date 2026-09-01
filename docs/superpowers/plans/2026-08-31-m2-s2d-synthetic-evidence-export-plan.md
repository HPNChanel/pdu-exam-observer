# M2-S2D Synthetic Evidence Export & Offline Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and `superpowers:test-driven-development` to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Export and independently verify a complete minimized synthetic M2
artifact without opening a device, collection authority, or server archive.

**Architecture:** A verified same-handle read feeds a strict canonical bundle
builder. The existing reviewer service exposes a monitor-authenticated
download, while a pure byte verifier and one-file CLI independently validate
the complete digest and authority chain.

**Tech Stack:** Python 3.11, FastAPI, SQLite-backed M2 store, React/TypeScript,
Vitest, pytest, Ruff, mypy, Playwright.

**Spec:**
`docs/superpowers/specs/2026-08-31-m2-s2d-synthetic-evidence-export-design.md`

## Global constraints

- Status is
  `M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.
- Maximum bundle size is exactly 4,000,000 bytes.
- Only terminal persisted synthetic runs are exportable; valid `NO_GO` is
  exportable and `NOT_PERSISTED` is not.
- Export is download-only; no server archive, database row, migration, camera,
  participant, package rebuild, commit, push, deployment, or release.
- Preserve the complete fail-closed authority ceiling in the spec.
- Work inline in the current task-scoped dirty checkout.

---

### Task 1: Materialize contracts and establish RED

**Files:** create `tests/backend/test_m2_synthetic_evidence.py`; modify existing
persistence, service, API, web adapter, and panel tests.

- [ ] Add exactly eight evidence tests, two persistence tests, two service
  tests, three API tests, five web adapter tests, and five panel tests.
- [ ] Confirm focused tests fail for missing module/method/route/interface.
- [ ] Confirm Python collection grows from 920 to 935 only after all tests are
  present; web target is 81 tests.

### Task 2: Implement verified read and evidence core

**Interfaces:** produce `read_verified_artifact()`,
`build_synthetic_evidence_bundle()`, and `verify_synthetic_evidence_bytes()` as
specified in the design.

- [ ] Implement same-handle read with derived-path, validity, size, identity,
  and SHA checks.
- [ ] Implement strict canonical JSON, closed decoders, receipt reconstruction,
  D1 semantic verification, cross-bindings, authority checks, and forbidden
  content rejection.
- [ ] Run evidence and persistence tests to GREEN, then scoped Ruff/mypy.

### Task 3: Wire service, API, and CLI

- [ ] Inject the artifact reader and implement deterministic service export.
- [ ] Add the authenticated monitor route, exact headers, and bounded errors;
  retain exam-origin 404.
- [ ] Add the no-traceback one-file verifier CLI.
- [ ] Run service/API/CLI tests and all S2A-S2C backend regressions.

### Task 4: Implement strict web download flow

- [ ] Share the reviewer auth/error fetch boundary between JSON and binary
  calls; add `downloadSyntheticEvidence()`.
- [ ] Validate response headers, size, Web Crypto digest, closed envelope,
  request ID, and authority ceiling.
- [ ] Add terminal-only download, safe filename, object-URL cleanup, digest
  display, and non-authorizing copy without retry/import.
- [ ] Run web tests, typecheck, lint, and build.

### Task 5: Adversarial and runtime acceptance

- [ ] Reject duplicate/noncanonical/oversized JSON, nested digest mutations,
  observation mutations, forged authority, forbidden path/identity/raw fields,
  tampered storage, and non-exportable run states.
- [ ] Exercise preflight and nominal downloads in headed Chromium, verify both
  files with the CLI, inspect requests/console/responsive layout, and confirm
  exam-origin 404.
- [ ] Stop the runtime and confirm no task temp root, process, or listener.

### Task 6: RP2 and governance reconciliation

- [ ] Bind the evidence module, verifier CLI, and evidence test; inventory grows
  44 to 47. Add four policies; preimages grow 32 to 36.
- [ ] Run RP2 `--write` once on final bound source, then only `--check`.
- [ ] Update current task/contract/roadmap, G18, G14, R-36, governance
  consistency, and `docs/ai/M2_S2D_VERIFICATION.md` with exact final hashes.

### Task 7: Final verification

- [ ] Run focused backend, S2A-S2D regression, Ruff, strict mypy, web gates,
  RP2, governance, research, exact collection, and one full Python suite.
- [ ] Verify release manifest and canonical proposal SHA-256; package scan must
  have zero S2D matches.
- [ ] Run `git diff --check`, inspect task-scoped changes, and confirm cleanup.
  Keep the dirty checkout; do not commit or push.

## Stop conditions

Do not publish the marker if a path is trusted from the database/caller, an
unpersisted run exports, a nested mutation passes, the exam origin exposes the
route, an authority flag opens, raw/sensitive data appears, a required gate
fails, package bytes change, or any task process/listener/temp root remains.

