# M2-D1-N2 Authority Contract

Date: 2026-08-30

Contract status: `M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`

## 1. Purpose and non-authority statement

This contract defines the only acceptable future authority lifecycle for one D1-N2 no-human, video-only, 60-second diagnostic preflight. It separates source-verified static bindings from issuance-time native evidence.

It is not an authority record, PreparedAuthority, WorkerGrant, capability, launch instruction, retry grant, or device decision.

## 2. Controlling identities

| Identity | Required value |
| --- | --- |
| schema_version | 3 |
| authority_revision | d1-n2-authority-v1 |
| static candidate | docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json |
| static schema | docs/spec/M2_D1_N2_AUTHORITY_BINDING.schema.json |
| static_bindings_digest | 5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979 |
| binding_schema_canonical_sha256 | 07ebbffaa9e0f9c2fa5b44dc9d2fab24ac82e324a118618acea7c830c5dd15cb |
| binding_schema_exact_bytes_sha256 | 1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca |
| candidate_exact_bytes_sha256 | cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb |

The static digest is a canonical inventory, not signed or consumable authority.
RP2 binds 24 source/test/script artifacts plus 3 lock/model artifacts and 21
explicit policy preimages. Those
projections are source-bound static declarations, not mechanically extracted
source slices and not runtime/native proof. The prior bytes were rejected by
independent I2 review. This replacement triple is unsigned and received
`APPROVE_STATIC_PACK_ONLY`; it is snapshot evidence only and cannot launch.

### HISTORICAL_SUPERSEDED_NON_AUTHORIZING

The previously controlling source-remediation packet used
`static_bindings_digest=49d877e2dbd85368e5ec0feb1a4207a0ca6926840bfa7ffaf6d39875aaf2a208`,
`binding_schema_canonical_sha256=975388bff4ad6a3bfded6a043bd234c22897487a6ced9b797e7a21ccc1cfb081`,
and
`candidate_exact_bytes_sha256=5e907471495cbbd5e1405b284ace3a22c577511ae627635eed14a0881066bae7`.
It bound 15 artifacts and 14 policy preimages. Those bytes are historical,
superseded, unsigned, non-authorizing, and cannot receive a new A0.

## 3. Namespace isolation

D1-N2 owns only:

- %LOCALAPPDATA%\PDUExamObserver\d1-n2-authority-v1\
- prepared.v3.json
- terminal.v3.json
- worker-grant.v2.json
- Local\PDUExamObserver.D1N2.AuthorityV1
- Local\PDUExamObserver.D1N2.VideoOnly
- Local\PDUExamObserver.D1N2.Capture.<challenge>

D1-N2 must not enumerate, load, migrate, rename, replace, delete, validate, reconcile, or inspect D1-N1 authority objects. The D1-N1 terminal is immutable historical evidence and cannot be reopened, resumed, copied forward, or used as D1-N2 authority.

## 4. State machine

The only progression is:

ABSENT -> PENDING -> PREPARED -> CONSUMED -> TERMINAL

There is no backward transition, migration, in-place upgrade, reopen, resume, second PREPARED record, or reuse after CONSUMED. Physical access cannot occur from ABSENT, PENDING, or PREPARED; no grant exists before CONSUMED; no pass exists before a durable, self-consistent TERMINAL.

A crash-observed PENDING or CONSUMED state is permanently nonlaunchable. A separately reviewed metadata-only reconciliation may record an explanation but cannot create launch authority.

## 5. Static freeze

The exact source, lock, model, dependency, worker argv, Job policy, FFmpeg argv template, worker bootstrap, receipt schema, failure ledger, watchdog, capture, and privacy bindings are in the static candidate.

An implementation may recompute them. It may not regenerate expected values, accept alternate files, use search-path fallback, weaken exact comparison, or downgrade a mismatch.

The observed interpreter hash is a candidate only. It is not the authorized supervisor image until issuance validates its exact path, bytes, live file identity, and worker equality.

## 6. PreparedAuthority v3

A future parameter-free prepare operation must bind:

- revision and schema version
- canonical static_bindings_digest and every frozen component digest
- opaque single-device token for one video-only device
- authorization nonce and one-time challenge
- exact supervisor executable path, size, SHA-256, and live file identity
- exact FFmpeg path, version, size, SHA-256, and live file identity
- issuance time and strict expiry
- canonical PreparedAuthority digest

PREPARED can be written only after exact match. No camera frame may be requested during prepare. Any later-authorized enumeration must be fixed, no-stream, and video-only.

PREPARED, WorkerGrant, and TERMINAL records persist only versioned sanitized state, sizes, digests, and bindings. Raw process epoch, capability, nonce, path, friendly name, and argv are never persisted.

## 7. WorkerGrant v2

WorkerGrant can be issued only after atomic consumption of matching PREPARED authority. It binds the challenge and capability; consumed-authority digest; supervisor/worker exact images and equality; all static bindings; FFmpeg; issuance and expiry; and its canonical digest.

The worker accepts no authority through command-line parameters, mutable environment overrides, working-directory or PATH search, or inherited writeable configuration.

## 8. Prerequisites

Before issuance can be invoked:

1. I0 source is implemented and focused verified offline; I1 remains inert/unwired source verified; I2 Sol source review is approved.
2. Obtain fresh user authorization naming d1-n2-authority-v1, the exact RP2 static digest, one no-human video-only 60-second attempt, and no retry.
3. Produce PREPARED without stream access only after that authority.
4. Obtain final independent pre-execution acceptance of that exact record and checkout.

This document satisfies none of these prerequisites by itself.

## 9. Fixed single-use sequence

1. Acquire the D1-N2 authority mutex.
2. Require ABSENT.
3. Verify the fixed signed A0 envelope and approved exact RP2 triple.
4. Persist an A0-bound PENDING before native checks.
5. Attest source and static bindings against the approved triple.
6. Perform only authorized no-stream identity checks.
7. Persist PREPARED.
8. Stop for final review.
9. On separate confirmation, atomically persist CONSUMED.
10. Generate the worker challenge and bind its challenge/Job digests in WorkerGrant.
11. Create and assign the kill-on-close Job before worker continuation.
12. Start one fixed video-only stream.
13. Run the phased watchdog and 60-second measurement.
14. Revoke capability and grant.
15. Close and verify retained A0/RP2/preparation leases.
16. Reconstructively verify and persist the redacted receipt and failure ledger in TERMINAL.

There is no retry branch. Failure skips launch where possible, kills bounded descendants when applicable, revokes grants, and terminalizes fail-closed.

## 10. Privacy and capability ceiling

A future separately authorized attempt may have one fixed video-only stream, bounded in-memory processing, aggregate timings and counters, redacted failure codes, and canonical digests.

Audio, network, raw frames, images, thumbnails, participant data, identifiers, model evaluation or tuning, dataset creation, alternate devices or profiles, alternate entrypoints, and retry are prohibited.

## 11. Terminalization

Every post-consume exit produces TERMINAL or a fail-closed ambiguity that cannot be interpreted as pass. TERMINAL binds authority/grant digests, static bindings, runtime identities, device token, profile, watchdog, accounting, privacy, cleanup, audio/network posture, and receipt/failure-ledger digests.

Revoke the grant before terminalization. Any mismatch, missing record, write ambiguity, orphan, cleanup uncertainty, or privacy uncertainty suppresses D1_N2_PREFLIGHT_PASS.

## 12. Result ceiling and blockers

The maximum future result is D1_N2_PREFLIGHT_PASS with device_gate_decision=UNVERIFIED and d1_go=false. It proves no general device gate, participant safety, scientific validity, release readiness, or later-gate authority.

Current blockers:

- the B0-R2 source/static packet received independent
  `APPROVE_STATIC_PACK_ONLY`, but that verdict grants no execution authority
- the external signing identity and frozen verifier bootstrap are unprovisioned
- no PreparedAuthority, WorkerGrant, or host runtime evidence exists
- public parameter-free entrypoints remain authority-gated and production bootstrap is `UNPROVISIONED`
- executable, FFmpeg, camera, grant, capability, Job, watchdog, receipt, and terminal evidence unverified
- the exact A0 granted on `2026-08-29` closed fail-closed after the single bound prepare entrypoint returned `AUTHORITY_NOT_ISSUED` with zero reported native side effects; it is not reusable for revised source or another prepare
- final pre-execution review is not performed; bootstrap provisioning and fresh signed A0 remain absent

Therefore authority_status is AUTHORITY_NOT_ISSUED, physical_camera_access_authorized is false, device_gate_decision is UNVERIFIED, and d1_go is false.
