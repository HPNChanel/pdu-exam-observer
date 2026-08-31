# M2-D1 No-Human Device Validation Implementation Plan

Version: `1.0`

Date: `2026-08-26`

State: `D1_BACKEND_CONTRACT_LOCALLY_VERIFIED_PENDING_NATIVE_EVIDENCE`

## Authority receipt

`USER_STATED`: the user accepted P1 and opened D1 no-human device validation on
`2026-08-26`.

```text
P1_ACCEPTED=true
M2_D1_NO_HUMAN_DEVICE_VALIDATION_AUTHORIZED=true
M2_PARTICIPANT_COLLECTION_AUTHORIZED=false
M2_MODEL_TRAINING_OR_EVALUATION_AUTHORIZED=false
RESEARCH_COLLECTION_NOT_IMPLEMENTED=true
```

Authority is non-transitive and revision-scoped. D1 does not authorize a participant,
real-person scene, audio, research-session `RECORDING`, model training/evaluation, dataset
export, browser-provided device/path/URL/command, or a release/production claim.

## Compact challenge contract

- Outcome: implement and locally verify the fail-closed D1 validation core against injected
  no-human test-chart or AI-rendered video observations.
- Falsifiable assumption: the D1 accounting, threshold, privacy, ownership, and receipt contract
  can be discriminated without accessing a physical camera or retaining raw frames.
- Smallest refutation: any test showing a synthetic/injected run can be reported as physical
  device evidence, a privacy stop can seal/export, audio or arbitrary input can enter the
  interface, two owners can run, or missing accounting can pass.

## Current implementation slice

The current slice is `D1-C1`, a pure backend validation core. It may add only:

```text
src/pdu_exam_observer/m2_d1_contract.py
tests/backend/test_m2_d1_contract.py
```

The implementation may reuse value contracts from `m2_synthetic.py` but must not mutate M0/M1
runtime, routes, UI, storage schema, persistence behavior, packaging, or dependencies.

### Allowed inputs

- An injected no-human test-chart source.
- An injected AI-rendered no-human video source represented by observations, never a caller path.
- Server-owned opaque device-selection tokens in the interface contract; the token must not reveal
  a native device identifier, serial, path, URL, username, command, or driver-specific name.
- Synthetic monotonic timestamps and deterministic injected faults for focused tests.

`NATIVE_NO_HUMAN_DEVICE` is reserved for a later Windows adapter/run. D1-C1 must reject it rather
than fabricate physical-device evidence.

### Forbidden inputs and effects

- No camera or audio enumeration library and no OS device enumeration in D1-C1.
- No microphone/audio stream, codec, field, callback, receipt, or fallback.
- No participant/study/research-session identifier and no `REAL` sample provenance.
- No raw-frame log, static mount, filesystem path resolver, SQLite write, artifact seal, export, or
  network operation.
- No `AlertEvent`, research label, confidence, intent, dishonesty, phone-use, identity, or
  person-level verdict.
- No M1 readiness/lifecycle transition; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

## Core contracts

### Run configuration

The only accepted target profile is exactly `1280x720@15fps`. The production-duration gates are:

- preflight: at least `60.0` measured seconds;
- nominal: at least `1200.0` measured seconds;
- warmup: exactly the first `5.0` seconds excluded only from FPS/latency percentiles;
- planned duration and measured post-warmup duration are explicit and non-negative.

Accelerated tests may inject timestamps that represent these durations. Such tests prove evaluator
logic only and must carry `evidence_kind=SIMULATED`; they cannot produce `D1_RUNTIME_GO`.

### Observation accounting

The receipt records independent post-warmup values for `delivered_frames`,
`inter_frame_gaps`, `processed`, `dropped_explicit`, `failed`, and `quality_insufficient`.

Required invariants:

```text
inter_frame_gaps = max(delivered_frames - 1, 0)
processed + dropped_explicit + failed = delivered_frames
quality_insufficient <= processed
delivered_frames > 0
processed / delivered_frames >= 0.99
(dropped_explicit + failed) / delivered_frames <= 0.01
```

One delivery timestamp exists per delivered frame. One latency exists per processed result. Missing,
extra, non-finite, negative, non-monotonic, overwritten, clipped, or denominator-inconsistent values
are `SCHEMA_INCOMPATIBLE`.

### Threshold evaluator

- Delivered FPS is at least `13.5` after warmup.
- Nearest-rank p95 inter-delivery gap is at most `200 ms`.
- Any inter-delivery gap at least `1000 ms` is `FRAME_STALLED`.
- Nearest-rank pose latency p95 is at most `200 ms` and p99 at most `500 ms`.
- Backlog is at most `2000 ms`.
- Free space is at least `max(2 GiB, 2 * measured_byte_rate * planned_duration_seconds)`.
- Disk-preflight p10 throughput is at least twice the measured encoded byte rate.
- Unknown or multiple contradictory primary failures fail closed; no easier-frame selection is
  permitted.

### Privacy and ownership

- The privacy guard returns an explicit no-human-clear result for every delivered frame.
- Incidental person, voice, identity-bearing reflection, unapproved screen content, unknown privacy
  result, or privacy-guard failure is `PRIVACY_STOP`.
- `PRIVACY_STOP` invalidates the run and permits no raw retention, seal, replay, or export.
- Exactly one owner lease must cover a run. A second or missing owner fails closed before processing.
- D1-C1 tests an injected exclusive lease. Cross-process Windows/native ownership remains runtime
  evidence for the later adapter and must not be inferred from the injected proof.

### Receipts and evidence kinds

The output is a bounded, canonical, hashable receipt with explicit schema version. It contains only
allowlisted aggregate facts and digests. It must exclude raw frames, local paths, native device IDs,
serials, usernames, private storage topology, participant identifiers, and arbitrary metadata.

Evidence kinds are:

```text
SIMULATED
NATIVE_NO_HUMAN_DEVICE
```

Only a native run may ever be evaluated for `D1_RUNTIME_GO`. D1-C1 accepts `SIMULATED` only and may
return `IMPLEMENTATION_VALID` or `NO_GO`. A simulated receipt presented as native is
`SCHEMA_INCOMPATIBLE`.

## TDD and mutant ledger

RED must first show the D1 module is absent or the required contract is missing. Focused tests then
cover:

1. Exact profile, duration, warmup, nearest-rank percentile, FPS, backlog, capacity, and throughput.
2. Exact accounting and zero-delivery failure.
3. Missing/extra/non-finite/non-monotonic timestamps and denominator mismatches.
4. Frozen timestamp, clock regression, pose absent/exception/invalid output, and quality failure.
5. Encoder open/write/finalize, disk space/throughput/fsync, rename, manifest digest/schema, and
   withdrawal/privacy fault codes as injected fail-closed results without performing those effects.
6. Incidental person/reflection/screen/unknown privacy result and privacy-guard exception.
7. Competing/missing owner, owner release on every exception path, and no resumed success after stop.
8. Receipt field allowlist, canonical digest, unknown schema/failure code rejection, and mutation
   detection.
9. Static/import/interface proof of no camera/audio enumeration, HTTP/UI, path/URL/command,
   SQLite/research-root, participant/session, `REAL`, model, alert, label, confidence, or M1 state.
10. Output-compatible mutants: empty run as zero-pose success, frozen time with advancing counters,
    negative latency clamped to zero, exception translated to zero pose, p10 replaced by average,
    low-quality frame omitted, privacy stop translated to normal, false native evidence, or a
    partial/failure reported sealed.

## Acceptance evidence for D1-C1

Required local evidence after the implementation revision:

```text
python -m pytest tests\backend\test_m2_d1_contract.py
python -m ruff check src\pdu_exam_observer\m2_d1_contract.py tests\backend\test_m2_d1_contract.py
python -m mypy src\pdu_exam_observer\m2_d1_contract.py
```

An independent research/privacy review must return `APPROVE` after inspecting the final contract and
tests. Passing these gates permits only `D1_CORE_LOCALLY_VERIFIED_PENDING_NATIVE_RUN`.

## Evidence that remains required after D1-C1

The following remains `UNVERIFIED` and cannot be closed by synthetic timestamps or unit tests:

- actual Windows server-side device enumeration and opaque selection mapping;
- cross-process single-camera ownership against the native capture stack;
- negotiated `1280x720@15fps` on a physical camera;
- 60-second no-human preflight and 20-minute no-human run in a controlled empty scene;
- physical capture gaps/FPS, pose latency/backlog, encoder rate, disk p10 throughput, free space, and
  privacy-stop behavior;
- exact environment/reproduction receipts for the native run;
- clean shutdown/recovery with the real driver and encoder;
- participant, research-validity, production, release, deployment, or institutional evidence.

## Stop conditions

Stop D1 and record only permitted non-sensitive aggregate audit evidence when a person, voice,
identity-bearing reflection, prohibited screen content, audio interface, second owner, unallowlisted
input, missing authority/control, incomplete accounting, privacy uncertainty, or failure-to-success
translation is observed. A stopped run is `NO_GO` and restart never resumes it automatically.

## RoutingReceipt

```json
{
  "schema_version": 1,
  "decision_owner": "root",
  "user_decision_date": "2026-08-26",
  "p1_accepted": true,
  "no_human_device_validation_authorized": true,
  "participant_collection_authorized": false,
  "model_training_or_evaluation_authorized": false,
  "implementation_scope": "M2_D1_C1_PURE_VALIDATION_CORE",
  "writer": {
    "model": "Terra",
    "reasoning_effort": "high",
    "role": "implementation_builder"
  },
  "research_privacy_review": {
    "model": "Sol",
    "reasoning_effort": "xhigh",
    "role": "research_methodologist",
    "status": "APPROVE"
  }
}
```
