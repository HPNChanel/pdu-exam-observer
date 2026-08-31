# M2-D1-N2 Readiness Pack

Date: 2026-08-26

Status: GOV_P0_STATIC_VERIFIED_EXTERNAL_GATES_PENDING_B0_3_DEFERRED_NO_COLLECTION_AUTHORITY

M2-R0 reconciliation status:
`M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`. This marker identifies the
current B0-R2 source/static tuple only; it does not open M2 or issue authority.
The current schema exact-bytes SHA-256 is
`1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`,
the candidate exact-bytes SHA-256 is
`cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`,
and the static bindings digest is
`5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`.

GOV-P0 update: on `2026-08-30`, the zero-cost pre-collection governance pack
was structurally verified under `research/pre_collection/v1/`, with manifest
SHA-256
`c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025`.
This work does not modify or supersede D1-N2. It keeps B0.3 deferred,
`AUTHORITY_NOT_ISSUED`, `device_gate_decision=UNVERIFIED`, and `d1_go=false`.
No camera, participant, native, installer, preparation, or preflight path was
invoked.

B0.3 planning update: on `2026-08-29`, the user approved a dedicated offline,
non-target Windows custodian design and a credential-free PowerShell/NCrypt kit
for static/safe-mode preparation outside the repository. The user stated that
no custodian exists. This grants no execution authority and does not permit a
production key, bundle, signature, B0.4 installation, A0, preparation, A1, or
physical work. The design and plan are under `docs/superpowers/`.

B0.3 closure update: the credential-free external kit passed AST/default/
`ValidateOnly`, exact-manifest, secret/artifact, proposal, and unchanged RP2
gates. Independent Sol/xhigh review returned `APPROVE_INERT_KIT_ONLY` for
script `ce02742fb57ea2d01d41bd60e9c63f528254f64977952e7e297108d8f7d848dc`,
runbook `a294b6eeb8123a96f79de5b96bb5d23a4eaa257718555ff72166d16580f4077b`,
manifest `d59c1c402ba5be3da41c03accca708740cc1cb93cf6249683716354a5e852df2`,
and validation receipt
`8b8f1dfdec40e85d503c9730963245ca75f14194d730d69344173e5694b31474`.
No operational path was invoked. `BOOTSTRAP_UNPROVISIONED` and
`AUTHORITY_NOT_ISSUED` remain unchanged; no custodian or B0.3 execution
authority exists.

Historical runtime update: on `2026-08-29`, exact A0 was granted for the
superseded digest `f582e6a284d5f3afcbe51d37a74ee9bcdb982537e2c7da7c81ba14bb0ef7c5c9`.
The old bound entrypoint returned `AUTHORITY_NOT_ISSUED` with zero reported
native side effects. That A0 is closed and non-reusable. The remediated source
has a new RP2 and has not been prepared or physically invoked. See
`docs/ai/M2_D1_N2_A0_PREPARE_RECEIPT.md` for the historical receipt.

## 1. Decision and ceiling

This pack freezes the source-derived inputs and future issuance protocol for one no-human, video-only, 60-second D1-N2 diagnostic attempt.

It is not execution authority. It authorizes no native discovery, camera access, FFmpeg launch, MediaPipe execution, retry, participant use, network, audio, or raw retention.

| Claim | State |
| --- | --- |
| authority_status | AUTHORITY_NOT_ISSUED |
| issuance_implementation_status | D1_N2_B0_R2_STATIC_PACK_APPROVED_BOOTSTRAP_UNPROVISIONED_AUTHORITY_NOT_ISSUED |
| grants_execution_authority | false |
| execution_authorized | false |
| physical_camera_access_authorized | false |
| valid_for_native_launch | false |
| device_gate_decision | UNVERIFIED |
| d1_go | false |
| D1-N1 terminal immutable | true |
| D1-N1 reopened or reusable | false |

The highest present result is an independently approved deterministic B0-R2
static RP2 candidate plus locally verified source. B0-R2 corrects the missing
exact epoch binding found while
preparing B0.3. The approved B0-R1 26-artifact/20-policy packet is now
historical and non-reusable. The B0-R2 24-source/test/script plus 3-lock/model
and 21-policy packet received independent Sol/xhigh
`APPROVE_STATIC_PACK_ONLY` after exact recomputation. The production
verifier bootstrap remains deliberately unprovisioned and the replacement
triple is unsigned and supplies no authority. No
PreparedAuthority, WorkerGrant, host runtime evidence, camera/device attempt,
participant use, audio/network/raw retention, retry, or device result exists.

## 2. Fresh authority epoch

| Element | Required value |
| --- | --- |
| schema_version | 3 |
| authority_revision | d1-n2-authority-v1 |
| bootstrap_epoch_digest | 736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b |
| bootstrap epoch preimage | 15 closed fields; 626 canonical UTF-8 bytes |
| authority directory | %LOCALAPPDATA%\PDUExamObserver\d1-n2-authority-v1\ |
| prepared record | prepared.v3.json |
| terminal record | terminal.v3.json |
| worker grant | worker-grant.v2.json |
| authority mutex | Local\PDUExamObserver.D1N2.AuthorityV1 |
| video-only mutex | Local\PDUExamObserver.D1N2.VideoOnly |
| Job name prefix | Local\PDUExamObserver.D1N2.Capture.<challenge> |

The D1-N2 store must not enumerate, load, migrate, rename, replace, delete, validate, or reconcile any D1-N1 object. The consumed D1-N1 terminal remains historical, immutable, non-reopenable, and non-reusable.

## 3. Machine artifacts

| Artifact | Role | Digest |
| --- | --- | --- |
| docs/spec/M2_D1_N2_AUTHORITY_BINDING.schema.json | Closed RP2 schema for the non-authorizing candidate | canonical_sha256=07ebbffaa9e0f9c2fa5b44dc9d2fab24ac82e324a118618acea7c830c5dd15cb; exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca |
| docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json | Locally verified RP2 static candidate | static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979; exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb |

The static digest covers only the canonical static_bindings object. It is neither a signature nor a grant. The schema is closed recursively with additionalProperties=false. RP2 binds 24 source/test/script artifacts plus 3 lock/model artifacts and 21 explicit policy preimages; policy projections are source-bound static declarations, not runtime/native proof. Issuance-only fields carry only UNVERIFIED_AT_ISSUANCE in the static candidate.

## 4. Source-verified static bindings

### 4.1 Source, lock, dependency, and models

| Binding | Bytes | SHA-256 |
| --- | ---: | --- |
| RP2 fixed inventory | 27 artifacts | Candidate-bound sizes and SHA-256 values |
| Source/test/script inventory | 24 artifacts | B0-R2 and D1-N2 production sources, focused tests including the RP2 artifact test, RP2 builder, and fixed operator script |
| RP2 builder | 1 of the 24 source artifacts | Self-hash is noncyclic and candidate-bound |
| Lock and models | 3 artifacts | `uv.lock`, pose model, face model |

Dependency pin: mediapipe==1.0.1.

### 4.2 Worker and protocol bindings

| Binding | SHA-256 |
| --- | --- |
| worker argv | 2a9713396c70cb12d0a2e20245b7daac427cabec70943995ca556a64d0291668 |
| worker Job policy | f57846b541be8296510220f6e49536e0b442f8666eb7c2487f53fb7d1bec8461 |
| FFmpeg argv template | fcce8bb0442e5125a24ece5a516be96b3108d01df27f6704afbbcbe0af79acff |
| worker bootstrap | 1d85a5370f516240dcbb9a01a87d4ae641f784ecd3afa580c78cde707e6e84b4 |
| receipt schema | 3fbb5022ba163ba4368a6fbbb7f2c9eadc491f8e3d20193121cd0554f1a9bf56 |
| failure ledger | 4fb769a94964161a446f0089f1baa8050f39050e01bf9248268e940ee072b2a7 |

Receipt field count: 60. Fixed failure-code count: 12.

### 4.3 Policy digests

| Policy | SHA-256 |
| --- | --- |
| bootstrap epoch | 8df0a2dbed4c839c8e071c665eb3138221aca9304b32c2dbdcae050f77fc83e1 |
| watchdog | b54e97e25f5428af7bc39cfc02fc7377bdd633f9b3834140cc13a22b844c2f78 |
| capture | 553f25eb67f50d8fcb0285498a065ff77b5c0cedd7dcc8019ab3ac20a6b8042b |
| privacy | edee0ee9bc49d5eb149feaf7b237d33cf075823e4a4a5d898378c7563b0f9ce9 |

Watchdog phase deadlines are 10, 30, 25, 10, 60, and 5 seconds for the source-defined phases. They are not a retry budget.

### 4.4 Executable candidate only

The observed base interpreter is 103192 bytes with SHA-256 5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec. Its classification is SUPERVISOR_EXECUTABLE_CANDIDATE and CANDIDATE_ONLY_UNVERIFIED.

It is not an authority binding. Exact path, file identity, live handle identity, applicable signer policy, and child-image equality remain issuance-time checks.

## 5. Fixed diagnostic profile

| Property | Value |
| --- | --- |
| input | DirectShow video only |
| width | 1280 |
| height | 720 |
| frame rate | 15 fps |
| pixel format | rgb24 |
| frame bytes | width * height * 3 |
| measured duration | 60 seconds |
| warmup | 5 seconds |
| post-warmup minimum | 55 seconds |
| audio | prohibited |
| network | prohibited |
| raw frame retention | prohibited |
| participant use | prohibited |
| retry | prohibited |

## 6. Acceptance contract for a future authorized attempt

All checks are conjunctive:

| Metric | Required result |
| --- | --- |
| total measured time | at least 60 seconds |
| post-warmup measured time | at least 55 seconds |
| processed frames | nonzero |
| ingress gaps and inference latencies | nonempty |
| post-success frame rate | at least 13.5 fps |
| p95 ingress gap | at most 200 ms |
| p95 pose latency | at most 200 ms |
| p99 pose latency | at most 500 ms |
| maximum backlog | at most 2000 ms |
| maximum stall gap | strictly less than 1 second |
| post success ratio | at least 99 percent |
| dropped-short plus inference-failure ratio | at most 1 percent |
| delivery failures | zero |
| privacy counters | all zero |
| privacy_checked | exactly equal to processed |

Exact accounting:

- received = warmup + post_attempted
- post_attempted = post_successful + dropped_short + inference_failure + privacy_terminal + delivery_failure
- delivered = received
- processed = warmup + post_successful
- dropped_explicit = dropped_short
- failed = inference_failure + privacy_terminal + delivery_failure
- processed + dropped_explicit + failed = delivered

Any absent or non-finite metric, accounting mismatch, privacy mismatch, ambiguous terminal state, or threshold failure suppresses a pass.

## 7. Issuance-time bindings remain unverified

The following must not be invented or inferred from the static candidate:

- opaque device token and exact video-only device identity
- authorization nonce and one-time challenge
- exact supervisor executable path, size, SHA-256, and live file identity
- exact worker image and equality with the supervisor image
- exact FFmpeg path, version, size, SHA-256, and live file identity
- prepared and consumed authority canonical digests
- WorkerGrant, capability, issuance time, and expiry
- Job creation, assignment, limits, and kill-on-close observation
- native watchdog observations
- terminal record and receipt digests

Every item remains UNVERIFIED until fresh user authorization explicitly names this D1-N2 revision and a final pre-execution review accepts the prepared evidence.

## 8. Gate ledger

| Gate | Decision | Boundary |
| --- | --- | --- |
| RP0 static inventory | SOURCE_VERIFIED | Checkout and canonical static digest only |
| RP2 machine artifacts | APPROVE_STATIC_PACK_ONLY | Exact 27-artifact/21-policy B0-R2 triple is unsigned and non-authorizing |
| I0 schema-v3 authority store | SOURCE_IMPLEMENTED_FOCUSED_VERIFIED_OFFLINE | No native runtime exercised |
| I1 parameter-free D1-N2 entrypoint | SOURCE_IMPLEMENTED_LOCAL_VERIFIED_NOT_INVOKED | Prepare and same-process run boundaries are source-only |
| I2 implementation verification | APPROVE_STATIC_PACK_ONLY | B0-R2 source/trust-boundary approval applies only to the exact replacement bytes |
| signed A0 bootstrap | UNPROVISIONED | No signing identity, frozen verifier, or provisioning receipt exists |
| B0 source-only bootstrap work | SOURCE_IMPLEMENTED_STATIC_PACK_APPROVED | B0-R2 source and tests only; installer execution remains unauthorized |
| A0 fresh user authorization | NOT_ISSUED | Historical A0 is spent; the current B0-R2 triple is unsigned and separately gated provisioning remains required before any new A0 |
| A1 prepared authority review | NOT_OPENED | No PreparedAuthority was emitted |
| X0 physical attempt | BLOCKED | Camera/native authority absent |
| device gate | UNVERIFIED | No physical evidence |
| D1 GO | false | Diagnostic-only ceiling |

## 9. Future one-attempt protocol

If and only if I0 through I2 and a fresh A0 pass, perform the preparation stage:

1. Invoke the parameter-free prepare entrypoint exactly once.
2. Create PENDING before any native check.
3. During prepare, permit only fixed no-stream enumeration and executable attestation.
4. Write PREPARED only after every binding matches.

Stop for independent A1 acceptance of that exact PreparedAuthority and checkout. If and only if A1 later passes, perform the execution stage:

5. Consume authority before opening a camera stream or starting FFmpeg or MediaPipe.
6. Issue WorkerGrant only from consumed authority.
7. Execute one 60-second, no-human, video-only attempt with no retry.
8. Revoke the grant before terminalization.
9. Terminalize every post-consume outcome.
10. Treat terminal ambiguity as failure.

The maximum successful output is D1_N2_PREFLIGHT_PASS with device_gate_decision=UNVERIFIED and d1_go=false. It is not a device gate pass.

## 10. Fail-closed stops

Stop without physical access for stale or absent authorization; any static mismatch; contact with D1-N1; an invalid state transition; crash-recovered PENDING or CONSUMED; an unexpected parameter, environment override, retry path, or alternate entrypoint; device ambiguity; executable or FFmpeg identity mismatch; audio, network, raw-retention, participant, or model capability; or any grant, Job, watchdog, receipt, cleanup, privacy, or terminal mismatch.

PENDING and CONSUMED are permanently nonlaunchable after a crash. No reopen, resume, backward transition, or migration is permitted. Metadata-only reconciliation requires a separate reviewed task and cannot create launch authority.

## 11. RoutingReceipt

schema_version: 1

| Work | Route | Effort | Result |
| --- | --- | --- | --- |
| static inventory and authoring | Terra | high | SOURCE_VERIFIED |
| authority-epoch and method review | Sol | xhigh | APPROVE_STATIC_PACK_ONLY_HISTORICAL_BYTES |
| I2 signed-A0 source and trust-boundary review | Sol | xhigh | APPROVE_STATIC_PACK_ONLY |
| B0 bootstrap provisioning design | Sol | xhigh | USER_APPROVED_SOURCE_ONLY |
| B0-R1 source and exact static pack review | Sol | xhigh | APPROVE_STATIC_PACK_ONLY |
| B0-R2 epoch binding and exact static pack review | Sol | xhigh | APPROVE_STATIC_PACK_ONLY |

No route in this receipt grants native authority.
