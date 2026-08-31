# M2 D1-N2 Diagnostic Recovery Contract

Status: `SOURCE_VERIFIED_NO_DEVICE_AUTHORITY`

Date: `2026-08-26`

## 1. Outcome and evidence boundary

D1-N2 repairs the diagnostic and watchdog ambiguity exposed by the terminal
D1-N1 attempt. It does not rerun, reinterpret, or replace that attempt.

`OBSERVED`: the one authorized D1-N1 physical run returned after about 22.1
seconds with `NO_GO`, `UNKNOWN_TECHNICAL_FAILURE`, consumed authority, supervised
worker/deadline/Job/lease cleanup evidence, no audio request, no retained raw
frame, `device_gate_decision=UNVERIFIED`, and `d1_go=false`.

`SOURCE_VERIFIED`: the old worker protocol collapsed several distinguishable
reader, capture, cleanup, and protocol failures into one generic code and used a
single startup deadline across privacy-engine initialization, device setup, and
first-frame delivery.

`UNVERIFIED`: the original physical failure cannot be retroactively assigned to
one of the new diagnostic categories. Camera behavior, DirectShow/FFmpeg behavior,
MediaPipe cold-start behavior in a future device run, physical privacy-stop, and
terminal runtime behavior of this revision have not been observed.

## 2. Offline forensic evidence

- Ordinary isolated MediaPipe liveness completed in 5.565 seconds and bounded
  close completed in 0.450 seconds.
- The exact minimal worker environment completed MediaPipe liveness in 17.903
  seconds, bounded close in 0.683 seconds, and the whole subprocess in 20.674
  seconds.
- Real MediaPipe with fake in-memory camera/FFmpeg/authority returned the typed
  `INPUT_UNAVAILABLE` result in 6.370 seconds with all cleanup flags true.
- A former 10-second fresh-process test was refuted. The bounded integration test
  now uses the exact authorization plus privacy-ready outer budget of 40 seconds.

These observations motivated separate phase deadlines; they do not identify the
terminal D1-N1 root cause.

## 3. Parent-observed lifecycle

The only valid positive lifecycle is:

```text
AUTHORIZED
PRIVACY_READY
CAPTURE_STARTING
FIRST_FRAME
CAPTURE_CLOSED
RECEIPT
```

- `AUTHORIZED` follows Job, durable WorkerGrant, and inherited capability checks.
- `PRIVACY_READY` has no payload and occurs only after exact dependency/model
  binding, audio/network guards, and successful MediaPipe liveness. It occurs
  before camera enumeration, FFmpeg authority work, mutex acquisition, or stream
  launch.
- `CAPTURE_STARTING` carries only an allowlisted worker monotonic timestamp. Fixed
  argv and its digest already exist; launch follows immediately.
- `FIRST_FRAME` carries the actual `_FrameReader` ingress timestamp.
- `CAPTURE_CLOSED` carries a worker monotonic timestamp. It may occur without a
  first frame only for a typed no-frame failure and can never authorize PASS.
- `RECEIPT` is accepted only under strict ordering, challenge, field, phase,
  failure-origin, cleanup, and graceful Job-drain rules.

Duplicate, missing, reordered, payload-bearing, future, regressing, wrong-challenge,
or output-compatible forged events fail closed.

## 4. Fixed deadlines

```text
authorization: 10 seconds
privacy ready: 30 seconds after AUTHORIZED
device setup: 25 seconds after PRIVACY_READY
first frame: 10 seconds after CAPTURE_STARTING timestamp
capture: exactly 60 seconds after FIRST_FRAME ingress
report: 5 seconds after CAPTURE_CLOSED
```

Delayed IPC cannot extend a phase deadline. The 60-second evidence interval remains
anchored exactly to the first complete application-ingress frame.

## 5. Typed failure and precedence contract

New privacy-safe codes are enum-only:

- `FRAME_READER_EXCEPTION`
- `CAPTURE_RUNTIME_EXCEPTION`
- `CLEANUP_INCOMPLETE`
- `WORKER_PROTOCOL_FAILURE`
- `CAPTURE_STARTUP_TIMEOUT`

No diagnostic includes exception text/type, traceback, path, device identifier,
frame content, credential, token, nonce, or authority state.

Parent-observed timeout and protocol codes cannot be self-reported by the worker.
Worker-originated NO_GO codes must match an explicit compatible lifecycle. In
particular, `PRIVACY_STOP` requires `FIRST_FRAME`; `INPUT_UNAVAILABLE` may close
cleanly without a first frame; and `UNKNOWN_TECHNICAL_FAILURE` is parent-only.

Timeout/decision precedence is:

1. Valid privacy detection or uncertainty: `PRIVACY_STOP`.
2. Privacy-engine or post-first-frame watchdog: `PRIVACY_GUARD_TIMEOUT`.
3. Device setup or first-frame startup watchdog: `CAPTURE_STARTUP_TIMEOUT`.
4. Invalid lifecycle/IPC/nonzero exit: `WORKER_PROTOCOL_FAILURE`.
5. Proven cleanup failure without an earlier privacy/timeout result:
   `CLEANUP_INCOMPLETE`.
6. `UNKNOWN_TECHNICAL_FAILURE` only when parent evidence cannot support a narrower
   code.

## 6. Cleanup evidence

The worker sends one bounded `worker_cleanup_complete` boolean derived from all
local cleanup invariants and raw-memory disposition. The parent never promotes
false or malformed evidence to true. Parent Job/pipe/reader/image-lease facts
remain independently reconstructed.

PASS requires complete worker cleanup, all phases, a zero worker exit, graceful Job
drain, stopped reader, closed pipe, closed worker lease, and valid semantics.
`CLEANUP_INCOMPLETE` remains valid when the worker assertion is false even if
process death lets the parent reclaim OS resources. `PRIVACY_STOP` retains
precedence after a cleanup failure, but its cleanup assertion remains false and it
cannot become PASS.

## 7. Verification evidence

TDD RED evidence covered missing phase constants/order, production serializer
contradiction, phase-timeout attribution, parent-only failure forgery, cleanup
reconstruction, privacy/cleanup compatibility, and invalid candidate wiring.

Final no-device evidence on the accepted source revision:

```text
targeted D1-N2 pytest: 50 passed
full native pytest file: 152 passed
Ruff: All checks passed
mypy: Success: no issues found in 1 source file
Sol/xhigh scoped review: APPROVE
```

The tests use fake/in-memory platforms, bounded child processes, Job surrogates,
and bundled model liveness only. They do not open a camera or consume authority.

## 8. Decision and next gate

The maximum result of this task is
`D1_N2_DIAGNOSTIC_REMEDIATION_SOURCE_VERIFIED_NO_DEVICE_AUTHORITY`.

It is not `D1_N1_PREFLIGHT_PASS`, device acceptance, `D1_GO`, research collection,
release, or production readiness. The terminal D1-N1 authority remains closed.
Any future device action requires a new current-revision source/lock/model/worker
binding, explicit one-attempt authority, and independent pre-execution approval.
