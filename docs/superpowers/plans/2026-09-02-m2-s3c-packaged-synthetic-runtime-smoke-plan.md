# M2-S3C Packaged Synthetic Runtime Smoke Implementation Plan

```text
document_status=USER_APPROVED_DIRECTION_A_FULL_SPEC_AND_PLAN_READY_FOR_IMPLEMENTATION
```

## Task 1 - RED contracts

Create exactly eight non-parametrized packaging tests for the closed CLI,
immutable bindings, two-invocation contract, loopback/auth behavior, exact run
projections, compatibility disclosure, bounded failures, cleanup, canonical
receipt, gaps, and authority ceiling. Run them before the harness exists;
collection must grow from 958 to 966 and fail for missing S3C behavior.

## Task 2 - Harness without candidate execution

Implement the canonical receipt/failure types, immutable S3B validation,
closed tree hashing, fixed environment, HTTP health/auth/run polling, listener
inspection, forced process-tree termination, direct-child temp cleanup, pre/post
candidate checks, and sanitized no-argument CLI. Use private dependency
injection only for tests. Bring source-level tests green using controlled fakes;
do not execute the candidate in this task.

## Task 3 - RP2 reconciliation

Bind `M2_S3C_PACKAGED_SMOKE_SCRIPT` and
`TEST_M2_S3C_PACKAGED_SMOKE_PY`, increasing source/tool inventory from 56 to
58. Add four policy preimages for status, fixed candidate binding, runtime
contract, and authority ceiling, increasing policy count from 46 to 50. Run
RP2 `--write` once after source stability and use only `--check` afterward. The
new tuple is the smoke harness revision, not the candidate source revision.

## Task 4 - One authorized smoke call

Run the no-argument CLI exactly once. It internally launches exactly two
candidate processes and runs preflight plus nominal in each. There is no retry.
On success, materialize exact canonical stdout with `apply_patch`; on failure,
clean up, withhold PASS artifacts, and stop for user direction.

## Task 5 - Governance

Create the canonical receipt and verification note. Advance current ledgers to
Task Contract v20, G22, G18, and R-40. Extend the three existing governance
tests without adding functions. Close only GAP-03 and preserve the full
authority ceiling. Do not modify candidate, historical package, S3A/S3B,
S2A-S2E, or GOV-P0-P5A receipts.

## Task 6 - Closure gates

Require eight focused tests, candidate and historical manifest checks, S3B
read-only check, Ruff, strict mypy, RP2 check/artifact tests, three governance
tests, 69 research tests, exactly 966 collected tests, and one 966-test full
suite. Recompute fixed hashes and confirm no S3C/S2C temp root, PDU process, or
listener remains. Do not run candidate again during verification.

