# D1-N2 PreparedAuthority and Retained-Epoch Controller Design

Date: `2026-08-29`

Design status: `IMPLEMENTED_THEN_I2_REVIEW_NO_GO_SUPERSEDED`

Implementation status: `IMPLEMENTED_LOCAL_GATES_PASS_I2_REJECTED`

## 1. Outcome

Create a new source-bound D1-N2 revision that can perform one parameter-free,
no-stream preparation operation after a fresh A0, emit an A1-reviewable
`PreparedAuthority`, retain its one-time capability only in the originating
process, and contain a dormant parameter-free execution path that cannot be
invoked as part of preparation.

This source task ends before any production prepare call, camera stream,
FFmpeg capture, MediaPipe inference, WorkerGrant issuance, or physical
preflight. After implementation and verification, the project must create a
new RP2 digest, obtain independent source review, and obtain a fresh A0 before
calling the new prepare entrypoint.

The authority identifier remains `d1-n2-authority-v1` and the persisted record
schema remains v3. The failed A0 created no authority record or native state;
the newly generated `static_bindings_digest` is the revision-scoped separator
that makes the old A0 inapplicable. This task does not create a second authority
namespace or migrate an existing record.

## 2. Evidence baseline

- `OBSERVED`: the currently bound `prepare_d1_n2()` and
  `run_d1_n2_preflight()` return `AUTHORITY_NOT_ISSUED` and perform no native
  work.
- `OBSERVED`: `D1N2CanonicalProductionFactory` is parameterless and uses an
  attestor that always returns `ValidationStatus.ERROR`.
- `OBSERVED`: a PREPARED record loaded by a new process becomes
  `STALE_PREPARED_NONLAUNCHABLE`; only the process epoch that created it may
  consume it.
- `OBSERVED`: the A0 bound to
  `f582e6a284d5f3afcbe51d37a74ee9bcdb982537e2c7da7c81ba14bb0ef7c5c9`
  was consumed by one fail-closed prepare call and is not reusable.
- `SOURCE_VERIFIED`: the canonical proposal SHA-256 remains
  `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.

## 3. Non-negotiable boundaries

The implementation must preserve all of the following:

1. Both public operational entrypoints remain parameter-free.
2. A fresh A0 is an external procedural prerequisite for calling prepare.
3. PENDING is durably created before static, device, executable, FFmpeg, model,
   or dependency attestation begins.
4. Preparation performs fixed video-device enumeration only. It never opens a
   camera stream or requests a frame.
5. Preparation does not launch FFmpeg capture, initialize MediaPipe inference,
   issue a WorkerGrant, consume authority, or call the execution driver.
6. Audio, network, raw retention, participant use, retry, alternate device,
   alternate profile, arbitrary path, arbitrary URL, browser command, PATH
   search, and environment override remain prohibited.
7. The historical D1-N1 terminal and authority directory are never read,
   written, migrated, replaced, reopened, or used as D1-N2 authority.
8. Any error after PENDING leaves a sticky, permanently nonlaunchable record.
9. A process restart makes PREPARED stale and nonlaunchable.
10. A1 is an external human-review decision. Source code must not claim it can
    authenticate a conversation or infer approval from a passing test.
11. No physical action occurs during implementation or source verification.
12. `device_gate_decision=UNVERIFIED` and `d1_go=false` remain unconditional.

## 4. Chosen architecture

Use one retained process epoch across A0 preparation and the later A1 decision.
The process owns an in-memory controller containing the canonical lifecycle,
raw nonce, selected safe device name, and live read leases. Only sanitized
digests and bounded metadata are persisted or returned for A1 review.

The public call/no-call boundary is the procedural authority boundary:

- after fresh A0, the operator calls `prepare_d1_n2()` exactly once;
- the process returns the sanitized PREPARED evidence and waits without
  opening a stream;
- after explicit acceptance of that exact evidence at A1, the operator may
  call `run_d1_n2_preflight()` in the same process;
- if A1 is rejected, expires, or the process exits, run remains impossible.

The code cannot independently prove that a human issued A1. It can enforce
same-process state, exact bindings, expiry, one-time consumption, and the
absence of any automatic prepare-to-run transition. Operational evidence must
record the external A1 decision before the run call.

## 5. Components

### 5.1 Canonical prepared-attestation model

Extend the canonical authority layer with an immutable typed attestation result
returned only after PENDING exists. It contains sanitized values needed to
build PREPARED; it does not contain a path, friendly name, raw nonce, argv, or
capability.

The PREPARED canonical record must bind:

- authority revision and schema version;
- canonical `static_bindings_digest` and binding-schema digest;
- digest of the exact runtime RP2 manifest bytes;
- camera cardinality and status;
- opaque single-device token;
- supervisor canonical-path digest, byte size, SHA-256, and live identity
  digest;
- FFmpeg canonical-path digest, byte size, SHA-256, version-output digest, and
  live identity digest;
- installed dependency observation digest;
- pose-model and face-model size/hash bindings;
- authorization-nonce digest, process-epoch digest, and PENDING digest;
- issuance time and expiration time;
- state `PREPARED` and domain `D1N2/PREPARED/v1`.

The canonical SHA-256 of the exact PREPARED bytes is the
`prepared_authority_digest`. It does not need a self-referential field inside
the record.

Preparation lifetime is fixed at 15 minutes. An expired PREPARED remains
persisted for audit but is nonlaunchable and cannot be re-prepared or retried.

### 5.2 Fixed RP2 verifier

The verifier reads only
`docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json` from a path derived from the
installed module location. It does not use the working directory, environment,
PATH, a caller argument, or a search operation.

It must:

1. validate the closed schema;
2. recompute `static_bindings_digest` from canonical JSON of
   `static_bindings`;
3. validate every artifact size and SHA-256 in the fixed inventory;
4. validate every policy preimage and derived digest;
5. reject extra fields, missing files, aliases, reparse-point substitution,
   identity drift, and noncanonical bytes;
6. retain read leases that permit other readers but deny replacement or
   mutation of every bound artifact until terminalization or fail-closed
   cleanup.

The manifest describes but does not include its own hash in its artifact
inventory, avoiding a self-reference cycle. Its exact byte digest is recorded
separately in PREPARED and is compared again before consumption.

### 5.3 No-stream identity attestor

Create a D1-N2-specific preparation adapter rather than constructing or
consulting the D1-N1 authority store.

It performs, in order:

1. RP2 and source/static verification;
2. supervisor executable canonical-path, byte, hash, and same-handle identity
   verification;
3. fixed Windows Camera-class enumeration through a canonical, live-verified
   system executable with a minimal fixed environment;
4. exact-one-present-and-OK video-device validation;
5. opaque token derivation while retaining the raw safe DirectShow name only
   in process memory;
6. FFmpeg canonical-path, version, byte, hash, and same-handle identity
   verification without opening a capture input;
7. installed dependency and bundled model verification;
8. construction of the sanitized attestation result.

All executable and artifact handles transfer into a `PreparedLeaseBundle` on
success. A cleanup failure suppresses PREPARED launchability. Friendly names,
raw nonces, raw paths, handles, and capabilities are never serialized.

### 5.4 Retained-epoch controller

`m2_d1_n2_entrypoint.py` owns one private process-global controller protected by
an in-process lock. Construction is inert; native work begins only inside the
single `prepare_d1_n2()` call.

The controller has these states:

`UNINITIALIZED -> PREPARING -> PREPARED_WAITING_A1 -> CONSUMED -> TERMINAL`

Any ambiguous state becomes `FAILED_NONLAUNCHABLE`. There is no backward edge,
second controller, second prepare, retry, resume, or reconstruction from
persisted PREPARED.

`prepare_d1_n2()` returns a bounded result containing status, canonical
PREPARED bytes or their sanitized JSON projection, the
`prepared_authority_digest`, issuance/expiry times, and reported native action
counters. It must never expose raw device name, path, nonce, handle, capability,
or argv.

`run_d1_n2_preflight()` checks the retained controller, epoch, expiry, record
digest, live leases, current static manifest, and exact no-stream camera
identity before consuming. A call without a live exact PREPARED controller
returns a fail-closed status with zero camera-stream side effects.

### 5.5 Dormant D1-N2 execution bridge

The new revision must contain the execution bridge before RP2 is frozen. Adding
it after A1 would change the source inventory and invalidate the reviewed
PreparedAuthority.

Extract or wrap the existing capture engine behind a private
revision-specific interface so D1-N2 can supply a consumed canonical authority
without reading or writing any D1-N1 authority record. Mode-specific mutex,
Job, worker bootstrap, challenge, authority names, and record paths are fixed
inside the D1-N2 production composition and are not caller inputs.

The bridge may run only after all of these succeed:

1. same-process PREPARED validation;
2. explicit invocation of the run entrypoint after the external A1 record;
3. immediate fixed no-stream identity revalidation;
4. atomic PREPARED-to-CONSUMED transition;
5. creation of a bounded WorkerGrant from the consumed authority;
6. worker executable equality and Job assignment checks.

Preparation imports or constructs no capture worker, MediaPipe runtime, pipe,
Job, or stream owner. Tests must discriminate this boundary.

The existing D1-N1 public behavior and terminal storage remain untouched. A
shared capture core is acceptable only if it contains no authority revision,
path, mutable configuration, or cross-revision fallback. Otherwise D1-N2 uses
a separate bridge.

## 6. Data flow

### Prepare after fresh A0

1. Parameter-free entrypoint verifies there is no controller and creates one.
2. Canonical lifecycle requires ABSENT and durably writes PENDING.
3. The fixed attestor validates RP2, source, runtime, one camera identity,
   supervisor, FFmpeg, dependency, and models without a stream.
4. The canonical layer writes exact PREPARED bytes by compare-and-swap.
5. Durability and every transferred lease are verified.
6. The controller retains secrets and handles in memory.
7. The entrypoint returns sanitized A1 evidence and performs no execution.

### Run only after A1

1. The operator records A1 acceptance of the exact revision, RP2 digest,
   PREPARED digest, checkout, scope, and expiry.
2. The operator invokes the parameter-free run entrypoint in the retained
   process.
3. The controller rejects expiry, state drift, artifact drift, lease drift,
   device drift, or record mismatch before stream access.
4. The lifecycle atomically consumes PREPARED.
5. The controller creates and hands off one bounded WorkerGrant.
6. The fixed D1-N2 driver performs at most one 60-second, video-only,
   no-human attempt with no retry.
7. Grant revocation and terminalization occur on every post-consume path.

No implementation or verification step in the source-remediation task performs
the second flow.

## 7. Failure behavior

- Failure before PENDING: return a typed failure with no authority write.
- Failure after PENDING: retain sticky PENDING; never delete, replace, or retry.
- PREPARED write/readback/durability/cleanup ambiguity: mark nonlaunchable and
  suppress all execution.
- Process exit or restart: classify PREPARED as
  `STALE_PREPARED_NONLAUNCHABLE`.
- Expiry before A1: suppress consume; no extension or reprepare.
- Run called without retained PREPARED: zero WorkerGrant and zero stream side
  effects.
- Device/static/executable/FFmpeg drift before consume: suppress consume and
  preserve nonlaunchable evidence.
- Any failure after consume: revoke any grant and write a bounded terminal
  failure; terminal ambiguity is failure.
- Cleanup failure: report a bounded code without exception text, path, device
  name, frame data, or secret material.

## 8. Expected source surfaces

The implementation plan may refine filenames but not responsibilities:

- `m2_d1_n2_canonical.py`: typed prepared attestation and exact lifecycle
  transitions.
- `m2_d1_n2_prepare.py`: fixed RP2 verifier, no-stream identity attestor, and
  retained leases.
- `m2_d1_n2_adapter.py`: production composition using the real attestor.
- `m2_d1_n2_entrypoint.py`: retained-epoch controller and parameter-free public
  results.
- `m2_d1_n2_native.py` or a strictly neutral extracted capture core: dormant
  D1-N2 execution bridge with no D1-N1 authority contact.
- focused backend tests for canonical, adapter, preparation, entrypoint, native
  bridge, and RP2 artifacts.
- RP2 builder, candidate, schema, readiness, authority, and AI task documents.

The canonical proposal document is never modified.

## 9. Test strategy

Implementation follows test-driven development. Production native prepare or
run is never invoked by the test suite.

Required discriminating tests include:

1. public operational signatures remain parameter-free;
2. constructor/import is inert;
3. PENDING precedes every attestor call;
4. attestation success produces exact sanitized PREPARED bytes;
5. attestation failure leaves only sticky PENDING;
6. prepare never calls the execution driver, opens a stream, initializes
   MediaPipe, issues a grant, or consumes authority;
7. cwd, `LOCALAPPDATA`, PATH, and related environment mutations cannot redirect
   bindings;
8. manifest, artifact, schema, policy-preimage, reparse, size, hash, identity,
   device-cardinality, dependency, model, supervisor, and FFmpeg mutants fail
   closed;
9. raw path, friendly name, nonce, capability, argv, and exception text are
   absent from persisted and returned evidence;
10. a second prepare and every restart/reopen path are nonlaunchable;
11. run without retained exact PREPARED has zero native side effects;
12. expiry, epoch drift, record drift, device drift, executable drift, and
    cleanup ambiguity suppress consume;
13. fake A1/run flow consumes before grant and revokes before terminalization;
14. D1-N2 never resolves or touches D1-N1 authority names or files;
15. existing D1-N1 focused behavior remains unchanged;
16. RP2 generation and check are deterministic for the new inventory.

## 10. Verification and evidence ceiling

Before the source revision can be offered for a fresh A0:

- focused pytest for all affected authority/native/RP2 tests must pass;
- scoped Ruff and mypy must pass;
- RP2 `--write` followed by `--check` must pass;
- the canonical proposal hash must remain exact;
- changed artifacts and sanitized schemas must be inspected;
- an independent source/trust-boundary review must accept the exact revision;
- no production `prepare_d1_n2()` or `run_d1_n2_preflight()` call may occur.

Passing these checks establishes only source readiness for a fresh A0. It does
not establish camera behavior, device identity, A1 acceptance, physical
preflight success, participant authority, research validity, release, or D1
GO.

## 11. Operational gate sequence

The only permitted sequence after source completion is:

`new RP2 -> independent source review -> fresh A0 -> one prepare -> stop -> A1 review -> same-process run call -> one attempt -> terminal`

Every revision or digest change returns to `new RP2`. Every failed or expired
one-shot authority is terminal for launch purposes. There is no retry path.

## 12. Acceptance criteria for this design

The design is implemented only when all source and fake-only checks above pass,
the RP2 digest is regenerated, the run path remains uninvoked, and live project
documents accurately report `AUTHORITY_NOT_ISSUED` pending a fresh A0.

The maximum claim at source-task completion is:

`D1_N2_REVISED_SOURCE_LOCALLY_VERIFIED_PENDING_INDEPENDENT_REVIEW_AND_FRESH_A0`

No stronger runtime or research claim is permitted.
