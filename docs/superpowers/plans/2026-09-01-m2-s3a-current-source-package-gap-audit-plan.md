# M2-S3A Current-Source Package Gap Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans`. Do not dispatch subagents, commit, push,
> rebuild, or release without separate user authority.

**Goal:** Produce a canonical source/package gap receipt and a human-readable
audit without changing package, runtime, frontend, or authority state.

**Architecture:** Five packaging tests bind the canonical JSON, Markdown
projection, immutable package inputs, eight-gap matrix, and authority ceiling.
RP2 binds the test and two policy preimages; governance ledgers record the
result and final RP2 tuple.

**Tech stack:** Python 3.12, pytest, canonical JSON, SHA-256, RP2 builder,
Markdown governance ledgers.

**Spec:**
`docs/superpowers/specs/2026-09-01-m2-s3a-current-source-package-gap-audit-design.md`

## Global constraints

- Preserve the task-scoped dirty `main@7912bd9` checkout.
- Do not execute the release builder, npm build, PyInstaller, signing,
  deployment, commit, push, physical capture, participant flow, or M3.
- Keep the historical package, both release manifests, frontend dist, build
  TOC, packaging scripts/spec, and README byte-identical.
- Keep every readiness, collection, camera, execution, and authority flag
  false, unverified, or unissued as specified.

## Task 1 - Contract and RED tests

- Create the approved spec/plan documents.
- Add `tests/packaging/test_m2_s3a_package_gap_audit.py` with exactly five
  non-parametrized tests for canonical JSON, immutable hashes, closed gaps,
  Markdown projection, and authority/immutability.
- Run the focused file and record the expected missing-artifact RED.

## Task 2 - Canonical audit artifacts

- Create `docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.json` using `apply_patch`.
- Compute the canonical body digest with a read-only Python command and patch
  the literal digest into the envelope.
- Create `docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.md` with explicit evidence labels
  and the complete non-authorizing boundary.
- Run the focused tests to obtain `5 passed`.

## Task 3 - RP2 reconciliation

- Add `TEST_M2_S3A_PACKAGE_GAP_AUDIT_PY` to the RP2 inventory, increasing it
  from 51 to 52.
- Add `package_gap_audit_status_policy_digest` and
  `package_gap_audit_authority_ceiling_policy_digest`, increasing policy
  preimages from 40 to 42.
- Update RP2 artifact tests without embedding a future digest in a bound test.
- Run RP2 `--write` exactly once after the source and tests stabilize, then use
  only `--check`.

## Task 4 - Governance reconciliation

- Update current task, task contract v18, roadmap, acceptance G20, quality G16,
  and risk R-38.
- Extend the existing three governance consistency tests without adding a test
  function. Require the S3A marker, audit JSON hash, final RP2 tuple, eight open
  gaps, and the closed ceiling.
- Preserve all historical receipts and GOV-P0 through GOV-P5A.

## Task 5 - Verification

- Run focused packaging tests, manifest verification, RP2 checker/artifact
  tests, governance and research suites, Ruff, strict mypy, exact collection,
  and the full suite.
- Expected final collection is 950 and the full suite must pass 950/950.
- Recompute every immutable input hash, verify proposal bytes, and confirm zero
  PDU processes/listeners before publishing the S3A marker.

