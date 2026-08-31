# D1-N2 I2 Signed-A0 Remediation Implementation Plan

Date: `2026-08-29`

Plan status: `IMPLEMENTED_AND_INDEPENDENT_I2_STATIC_PACK_APPROVED`

Authority ceiling: `AUTHORITY_NOT_ISSUED`

## Outcome

Implement the user-approved option A design in
`docs/superpowers/specs/2026-08-29-d1-n2-i2-signed-a0-remediation-design.md`.
The source must fail closed with an unprovisioned production bootstrap and be
approved by a fresh independent I2 source review. This work does not provision a
key, create or install A0, invoke preparation, open a camera, or perform the
physical preflight.

## Compact challenge contract

- Outcome: close all five I2 findings without widening operational authority.
- Falsifiable assumption: production construction cannot reach a test verifier,
  signing key, signature generator, or native preparation before signed A0 is
  independently verified.
- Smallest refutation: an injected/bootstrap-unprovisioned test that observes a
  PENDING write, RP2/native call, or generated signing material.

## Task 1 - Signed A0 and independent RP2 triple

Files: `m2_d1_n2_a0.py`, `m2_d1_n2_prepare.py`, focused tests.

1. Add closed canonical parsing for `A0ApprovalV1`, strict scope/time checks,
   typed bootstrap statuses, retained lease result, and `ApprovedRP2Triple`.
2. Keep production bootstrap explicitly `UNPROVISIONED`; permit injected fake
   bootstrap/lease ports only in tests.
3. Change `FixedRP2Verifier.verify` to require an approved triple and compare
   exact candidate bytes, canonical schema bytes, and canonical static bindings.

Acceptance: malformed/extra/duplicate/future/expired/wrong-scope envelopes fail;
unprovisioned production performs no RP2/native work; coordinated RP2 mutations
fail against a prior signed triple.

## Task 2 - A0-bound lifecycle and challenge-bound grant

Files: `m2_d1_n2_canonical.py`, `m2_d1_n2_adapter.py`, lifecycle tests.

1. Verify A0 before creating PENDING; bind A0 approval/triple fields into PENDING
   and carry them into PREPARED.
2. Add `challenge_digest` and `job_name_digest` to WorkerGrant and retain them
   through issued/revoked verification.
3. Reject any mismatched or incomplete binding during canonical reinspection.

Acceptance: no valid A0 means no PENDING; one valid approval creates one sticky
A0-bound PENDING; grant challenge/job mutants cannot authorize a worker.

## Task 3 - Closed terminal evidence

Files: `m2_d1_n2_evidence.py`, `m2_d1_n2_canonical.py`, `m2_d1_n2_native.py`,
focused tests.

1. Define closed receipt, bounded fixed failure ledger, integer-only accounting,
   privacy/audio/network/raw-retention projections, and cleanup projections.
2. Recompute reconciliation equations and thresholds before constructing
   `VerifiedTerminalEvidence`.
3. Persist canonical receipt and ledger bytes plus their digests; revalidate all
   semantics during restart classification.

Acceptance: every accounting, threshold, privacy, cleanup, receipt/ledger,
challenge/job, or unknown-code mutation invalidates terminal acceptance.

## Task 4 - Exclusive ownership and close-before-terminal

Files: `m2_d1_n2_adapter.py`, `m2_d1_n2_entrypoint.py`, bridge tests.

1. Add idempotent `abort_pre_bridge` and exclusive `transfer_to_bridge`.
2. Catch `BaseException` across the pre-transfer boundary, close all retained
   leases exactly once, and preserve the primary exception with cleanup evidence.
3. After transfer, let only the bridge close retained leases. Revoke grant and
   require clean retained cleanup before terminal persistence.

Acceptance: construction/factory/controller failures leak no lease; retained
close failure writes no TERMINAL and restart stays nonlaunchable.

## Task 5 - Fixed production composition and public boundary

Files: `m2_d1_n2_adapter.py`, `m2_d1_n2_entrypoint.py`, public-boundary tests.

Keep public functions parameter-free and imports/construction inert. Production
uses only `UnprovisionedA0Bootstrap`. Rewrite wrapper tests so verification never
invokes either production operational wrapper.

## Task 6 - RP2 and governance

Files: `scripts/build_m2_d1_n2_rp2.py`, generated RP2 candidate/schema,
`docs/ai/*`, `docs/spec/*`.

Add new source/test artifacts and policy preimages, regenerate deterministically,
record the new exact triple, and keep the authority ceiling explicit.

## Verification order

1. Focused A0/RP2 tests.
2. Canonical lifecycle and evidence tests.
3. Adapter/native/entrypoint tests using fakes only.
4. All D1-N2 tests, D1-N1 regression tests, Ruff, and mypy.
5. RP2 write/check determinism and proposal SHA-256 check.
6. Fresh independent Sol/xhigh I2 read-only review of the exact new digest.

No verification step may call production `prepare_d1_n2()` or
`run_d1_n2_preflight()`.
