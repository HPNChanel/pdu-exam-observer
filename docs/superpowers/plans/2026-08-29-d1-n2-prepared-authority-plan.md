# D1-N2 PreparedAuthority Implementation Plan

Date: 2026-08-29

Status: IMPLEMENTED_I2_REVIEW_NO_GO_SUPERSEDED_BY_SIGNED_A0_REMEDIATION

Authority ceiling: source remediation only. This plan does not issue A0, A1,
camera authority, execution authority, retry authority, participant authority,
or D1 GO.

## Outcome

Implement the approved retained-epoch design so one future fresh A0 can invoke
a parameter-free no-stream prepare, emit sanitized A1 evidence, and stop. Only
an explicit same-process run call after accepted A1 can consume authority and
invoke one supervised 60-second video-only worker attempt.

## Tasks and acceptance evidence

1. Add immutable typed PREPARED, WorkerGrant, and TERMINAL attestations.
   Acceptance: exact closed canonical records; raw names, paths, nonces,
   capabilities, and argv never persist.
2. Add fixed RP2 verification and retained artifact leases.
   Acceptance: fixed module-derived paths; canonical schema/manifest,
   size/hash/identity/reparse/alias checks; cleanup ambiguity is nonlaunchable.
3. Add the no-stream identity attestor.
   Acceptance: RP2, supervisor, Camera-class cardinality, FFmpeg, dependency,
   and model bindings are checked in fixed order without capture input.
4. Compose production preparation lazily.
   Acceptance: construction/import is inert and PENDING precedes attestation.
5. Add the D1-N2 native preparation port and dormant worker bridge.
   Acceptance: fixed D1-N2 mutex/Job/worker surfaces, exact grant/capability
   handoff, one attempt, no retry, and no D1-N1 authority-store access.
6. Add the retained same-process controller.
   Acceptance: `UNINITIALIZED -> PREPARING -> PREPARED_WAITING_A1 -> CONSUMED
   -> TERMINAL`; no reopen, reconstruction, automatic run, or second call.
7. Regenerate RP2 and synchronize governed documentation.
   Acceptance: new artifact inventory and digests accurately retain
   `AUTHORITY_NOT_ISSUED` and identify the historical A0 as spent.
8. Verify without production prepare or run.
   Acceptance: focused D1-N2 and D1-N1 regression tests, scoped Ruff, strict
   mypy, RP2 write/check, and canonical proposal hash all pass.

## Stop conditions

- Do not call production `prepare_d1_n2()` or `run_d1_n2_preflight()` during
  implementation or verification.
- Any source or RP2 change invalidates prior review and prior A0.
- Independent review and a fresh A0 must bind the exact new digest before any
  no-stream native preparation.
- A1 must accept the exact same-process PreparedAuthority before run.
