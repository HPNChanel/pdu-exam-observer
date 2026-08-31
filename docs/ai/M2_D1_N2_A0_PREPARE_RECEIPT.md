# M2-D1-N2 A0 Prepare Receipt

Date: `2026-08-29`

Status: `PREPARE_FAIL_CLOSED_AUTHORITY_NOT_ISSUED`

## Scope

- `USER_STATED`: A0 granted for `d1-n2-authority-v1` and `static_bindings_digest=f582e6a284d5f3afcbe51d37a74ee9bcdb982537e2c7da7c81ba14bb0ef7c5c9`.
- The scope was one no-human, video-only, 60-second preflight with no retry; physical execution remained conditional on A1 acceptance.
- Participant, audio, network, raw retention, model, seal, export, release, and D1 GO authority were not granted.

## Pre-invocation evidence

- `OBSERVED`: `scripts/build_m2_d1_n2_rp2.py --check` exited `0`.
- `OBSERVED`: the candidate and requested static digests matched exactly.
- `OBSERVED`: `src/pdu_exam_observer/m2_d1_n2_entrypoint.py` SHA-256 matched the RP2 inventory value `a91aa14c19db5cd8dd73ed19186865b1027a3bb421829b6ec1f47eef60e5df92`.

## Invocation outcome

- `OBSERVED`: the bound parameter-free `prepare_d1_n2()` entrypoint was invoked exactly once.
- `OBSERVED`: it returned `status=AUTHORITY_NOT_ISSUED`, `native_side_effects=false`, and `native_side_effect_count=0`.
- `SOURCE_VERIFIED`: the bound entrypoint is inert/unwired and cannot emit PreparedAuthority.
- `DERIVED`: no A1 reviewable record was produced by this invocation; A1 and X0 remain unopened.

## Decision

This A0 is closed as fail-closed and may not be reused for a second prepare or physical action. No camera, FFmpeg, MediaPipe, participant, audio, network, or raw-retention action is authorized.

The next permitted work is offline source remediation to create a genuinely issuable but still parameter-free prepare path. Any such source change invalidates the old static digest and requires a new RP2 artifact set, independent source review, and fresh revision-scoped A0 before another prepare call.
