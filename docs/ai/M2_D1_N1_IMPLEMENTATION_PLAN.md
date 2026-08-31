# M2-D1-N1 Native No-Human Preflight Plan

Version: `1.0`

Date: `2026-08-26`

State: `D1_N1_NATIVE_PREFLIGHT_AUTHORIZED_IMPLEMENTATION_ACTIVE`

## Authority receipt

`USER_STATED`: the user confirmed a controlled no-human environment and explicitly opened the
D1-N1 native adapter plus 60-second preflight on `2026-08-26`.

```text
P1_ACCEPTED=true
M2_D1_NO_HUMAN_DEVICE_VALIDATION_AUTHORIZED=true
M2_D1_N1_PHYSICAL_CAMERA_ACCESS_AUTHORIZED=true
M2_D1_N1_PRETRAINED_TECHNICAL_INFERENCE_AUTHORIZED=true
M2_PARTICIPANT_COLLECTION_AUTHORIZED=false
M2_MODEL_TRAINING_OR_EVALUATION_AUTHORIZED=false
M1_RECORDING_TRANSITION_AUTHORIZED=false
PERSISTENCE_SEAL_OR_EXPORT_AUTHORIZED=false
RESEARCH_COLLECTION_NOT_IMPLEMENTED=true
```

This authority is non-transitive and revision-scoped. It permits only one local video camera for
one 60-second no-human technical preflight. It does not authorize a person, participant, research
session, audio, dataset, model evaluation, M1 lifecycle change, persistence, seal, export, HTTP/UI,
release, or production claim.

## Compact challenge contract

- Outcome: implement, independently review, and then run one video-only Windows preflight that
  produces either `D1_N1_PREFLIGHT_PASS` or an exact fail-closed code.
- Falsifiable assumption: a fixed hash-bound FFmpeg DirectShow transport plus locally bundled,
  locked MediaPipe face and pose tasks can process every delivered frame without audio or raw
  retention while satisfying the D1-N1 application-ingress thresholds.
- Smallest refutation: missing/mismatched dependency, executable, model, privacy guard, camera,
  profile, owner, frame, timestamp, accounting, or cleanup evidence; any audio/request/listing,
  runtime download, raw write, caller-controlled native input, privacy uncertainty, or capture-only
  result translated to pass.

## Current observed environment

`OBSERVED` before implementation:

- exactly one present Windows `Camera`-class device reports status `OK`;
- `uv` and FFmpeg are available;
- the project venv/lock does not yet contain MediaPipe, NumPy, OpenCV, WinRT, or WinSDK packages;
- current checkout therefore cannot execute a valid D1-N1 run yet.

These observations do not establish DirectShow access, exact profile negotiation, pose/privacy
execution, exclusive ownership, or audio non-access.

## Selected architecture

Use FFmpeg DirectShow as the video transport and MediaPipe Tasks in synchronous `VIDEO` mode.
OpenCV `VideoCapture` is excluded from the primary adapter. Capture-only operation is a typed
`NO_GO` and must fail before camera open when pose/privacy prerequisites are unavailable.

Primary current sources:

- FFmpeg DirectShow device contract: `https://ffmpeg.org/ffmpeg-devices.html#dshow`
- MediaPipe Python setup: `https://ai.google.dev/edge/mediapipe/solutions/setup_python`
- Pose Landmarker Python guide and model bundle:
  `https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python`
- Face Detector Python guide and model:
  `https://developers.google.com/edge/mediapipe/solutions/vision/face_detector/python`
- MediaPipe package provenance: `https://pypi.org/project/mediapipe/`

Official documentation states that DirectShow distinguishes `video=NAME` from `audio=NAME`, rejects
unsupported requested video options, and that MediaPipe `VIDEO` mode processes synchronously. These
are source contracts, not physical-runtime evidence.

## Authorized repository slice

The implementation writer owns only:

```text
pyproject.toml
uv.lock
src/pdu_exam_observer/m2_d1_native.py
src/pdu_exam_observer/assets/models/pose_landmarker_lite.task
src/pdu_exam_observer/assets/models/blaze_face_short_range.tflite
tests/backend/test_m2_d1_native.py
docs/source/M2_D1_NATIVE_ASSET_PROVENANCE.md
```

`pyproject.toml` may be changed only to lock the exact MediaPipe dependency and ensure the two model
assets are packaged. No existing M0/M1/S1/P1/D1-C1 source, route, UI, config, schema, packaging entry
point, or research behavior may be modified.

## Dependency and asset gate

Before camera open:

1. Lock exact `mediapipe==1.0.1` and all transitive wheels/hashes in `uv.lock`; use its compatible
   locked NumPy dependency. Do not add OpenCV unless MediaPipe itself requires a locked transitive
   distribution.
2. Download the official Pose Landmarker lite bundle and BlazeFace short-range model during the
   repository preparation step only. Runtime networking is prohibited.
3. Record model filename, exact upstream URL/version, byte length, SHA-256, task type, model-card
   URL, license/source statement, and retrieval date in the asset provenance file.
4. Load each asset through fixed package resources into `BaseOptions.model_asset_buffer`; caller
   paths and runtime downloads are impossible.
5. Bind the exact local FFmpeg absolute artifact, SHA-256, version/configuration, and provenance in a
   local-only authority configuration. Mutable `PATH` resolution is not accepted at run time.
6. Create both MediaPipe task instances and complete a deterministic liveness probe before camera
   open. Failure is `POSE_ENGINE_UNAVAILABLE` or `PRIVACY_STOP`, never capture-only fallback.

The model tasks are used only for technical liveness and privacy-stop screening. This is not model
training, calibration, evaluation, accuracy validation, or research inference.

## Server-owned device configuration

The parameter-free `prepare` action:

- enumerates only the Windows `Camera` PnP class, never audio;
- requires exactly one present `OK` camera;
- records the DirectShow-friendly name only in fixed local-only configuration under
  `%LOCALAPPDATA%\PDUExamObserver`;
- exposes only a SHA-256-derived opaque selection token in receipts;
- records no serial, PnP instance ID, username, arbitrary path, URL, command, or browser value;
- records the hash-bound FFmpeg artifact and the current authority revision.

The preflight constructor accepts no device name, path, URL, command, duration, model location,
output destination, or browser input. It can only load the fixed local authority configuration.

## Native owner and FFmpeg command contract

Acquire a process-global Windows named mutex before launching FFmpeg. A contender returns
`SCHEMA_INCOMPATIBLE`/typed owner-unavailable evidence without opening the camera. Release the mutex
on every success, stop, exception, timeout, and child-start failure path.

Launch with `shell=False`, an exact hash-checked absolute executable, and this fixed argv topology:

```text
ffmpeg -hide_banner -nostdin -loglevel warning
  -f dshow -video_size 1280x720 -framerate 15
  -i video=<server-owned-approved-friendly-name>
  -map 0:v:0 -an -sn -dn
  -c:v rawvideo -pix_fmt rgb24 -f rawvideo pipe:1
```

Forbidden argv or behavior: `-list_devices`, `-list_options`, `audio=`, audio maps/codecs, wildcard
source, stdin control, shell, network protocol, file output, temp file, screenshot, raw checksum,
caller substitution, or automatic restart.

The source code may not log the friendly name or full argv. Receipts contain only the opaque device
token and FFmpeg digest/version.

## Frame, pose, and privacy pipeline

- Read exactly `1280 * 720 * 3` RGB bytes per frame with bounded blocking and at most two reusable
  byte buffers.
- Timestamp only after a complete adapter read using `perf_counter_ns`.
- Name the timestamp `application_ingress_monotonic_ns`; never call it sensor exposure/capture time.
- Convert the buffer to a NumPy view without file creation and then to immutable `mediapipe.Image`.
- Run Face Detector synchronously first. Any face result is terminal `PRIVACY_STOP` before pose.
- Run Pose Landmarker synchronously with strictly increasing video timestamps. Any pose result is
  terminal `PRIVACY_STOP`; an empty valid result is the expected no-human technical observation.
- Any guard exception, invalid output, unavailable model, uncertainty, unexpected frame shape, or
  controlled-room authority mismatch is terminal and cannot resume.
- Clear reusable buffers, close tasks/pipes, terminate the child, and release the mutex on stop.

The user-confirmed controlled room plus face and pose screening is a bounded privacy guard for this
technical preflight. It does not prove detection of voices, screens, every reflection, partial body,
or all prohibited content. Real privacy sensitivity remains `UNVERIFIED`.

## Measurement contract

The run is exactly 60 measured seconds beginning with the first complete frame. The first 5 seconds
are warmup and excluded from FPS/gap/latency percentiles, while all warmup faults remain terminal.

- target/requested profile: exactly `1280x720@15fps`;
- delivered FPS after warmup: at least `13.5`;
- nearest-rank p95 application-ingress gap: at most `200 ms`;
- any gap at least `1000 ms`: `FRAME_STALLED`;
- nearest-rank p95 ingress-to-pose latency: at most `200 ms`;
- nearest-rank p99 ingress-to-pose latency: at most `500 ms`;
- application queue/backlog: at most `2000 ms` with no hidden overwrite;
- `processed + dropped_explicit + failed = delivered_frames`;
- processed coverage at least `0.99` and drop/failure rate at most `0.01`;
- zero delivery is `INPUT_UNAVAILABLE`, never a pass.

True sensor-to-application latency, driver buffering, and sensor timestamps remain `UNVERIFIED`.
Encoder, disk, fsync, rename, seal, and export stages are `NOT_ATTEMPTED` in N1.

## Receipt and outcomes

The local-only canonical receipt includes authority/spec/source/dependency/model/FFmpeg hashes,
opaque device token, exact fixed argv digest, requested profile, application-ingress accounting,
privacy counts, threshold metrics, cleanup states, audio policy, raw-retention policy, and result
digest. It excludes raw frames, friendly name, serial/instance ID, paths, usernames, participant or
research identifiers, labels, confidence, and arbitrary metadata.

The maximum success is:

```text
outcome=D1_N1_PREFLIGHT_PASS
device_gate_decision=UNVERIFIED
D1_GO=false
participant_collection_authorized=false
model_training_or_evaluation_authorized=false
raw_retained=false
audio_requested=false
```

Use exact readiness failure codes including `INPUT_UNAVAILABLE`, `FRAME_STALLED`,
`CLOCK_REGRESSION`, `POSE_ENGINE_UNAVAILABLE`, `POSE_ENGINE_EXCEPTION`, `POSE_OUTPUT_INVALID`,
`QUALITY_INSUFFICIENT`, `PRIVACY_STOP`, `SCHEMA_INCOMPATIBLE`, and
`UNKNOWN_TECHNICAL_FAILURE`. Unknown or contradictory state is `SCHEMA_INCOMPATIBLE`.

## TDD and security ledger

Focused tests must discriminate:

1. Exact dependency/model/FFmpeg/config hashes before camera open; mismatches open nothing.
2. Exact single-camera PnP preparation, local-only redaction, and opaque token stability.
3. Fixed argv equality; audio/listing/shell/path/output/network mutants are rejected.
4. Named mutex contention, acquisition failure, child failure, timeout, privacy stop, task exception,
   partial frame, EOF, and normal cleanup with no leaked owner/process/pipe/buffer.
5. Exact frame size, two-buffer maximum, no write/log/static-mount/raw-digest surface.
6. Strictly increasing application-ingress and MediaPipe timestamps; frozen/regression/stall mutants.
7. Face/pose result, guard uncertainty/exception/invalid output, and stop precedence with minimal
   privacy receipt and no later evidence.
8. Warmup, nearest-rank, FPS/gap/latency/backlog, reconciliation, coverage, threshold boundaries,
   and zero-delivery mutants.
9. Receipt semantic rehash mutants, forbidden fields, local-only redaction, exact cleanup states,
   `NOT_ATTEMPTED` persistence stages, and structural absence of `D1_GO=true`.
10. Static/import/interface proof of no audio library/enumeration, browser/HTTP/UI, M1/P1/SQLite,
    persistence/seal/export, participant/session, `REAL`, label/confidence/alert, training/evaluation,
    arbitrary shell, path, URL, or command surface.

## Implementation and runtime sequence

1. Terra/high builder implements only the authorized repository slice and runs focused pytest, Ruff,
   mypy, dependency-lock, model-hash, and asset-package checks.
2. Sol/xhigh research/privacy review must return `APPROVE` before any camera access.
3. Root runs the parameter-free server-owned preparation action and records only local redacted
   authority evidence.
4. Root runs one parameter-free 60-second preflight. Incidental person/prohibited content or privacy
   uncertainty stops immediately.
5. Record a local-only receipt and update current task state. Do not run the 20-minute rung without a
   separate decision after reviewing N1 evidence.

## RoutingReceipt

```json
{
  "schema_version": 1,
  "decision_owner": "root",
  "user_decision_date": "2026-08-26",
  "implementation_scope": "M2_D1_N1_NATIVE_VIDEO_ONLY_PREFLIGHT",
  "writer": {"model": "Terra", "reasoning_effort": "high", "role": "implementation_builder"},
  "research_privacy_review": {"model": "Sol", "reasoning_effort": "xhigh", "role": "research_methodologist", "status": "CONDITIONAL_GO_PREIMPLEMENTATION"},
  "physical_camera_access_authorized": true,
  "pretrained_technical_inference_authorized": true,
  "participant_collection_authorized": false,
  "model_training_or_evaluation_authorized": false,
  "m1_recording_transition_authorized": false,
  "persistence_seal_or_export_authorized": false
}
```

## Residual evidence boundary

Even a passing N1 receipt leaves `UNVERIFIED`: OS-internal audio enumeration/non-access beyond the
fixed video-only argv; sensor timestamps and sensor-to-pose latency; driver buffering; comprehensive
privacy sensitivity; 20-minute stability; encoder/disk/durability; packaged clean-machine behavior;
participant/institutional/research validity; model performance; deployment; release; production;
and `D1_GO`.


## Revision 1.1 trust-boundary amendment (2026-08-26)

This section supersedes any earlier wording that preparation stores a camera friendly name or an
executable path.

- Prepared authority schema v2 stores only an opaque device token, a CSPRNG authorization nonce,
  the fixed profile, FFmpeg byte hash, version-output hash, byte size, and a sanitized file-identity
  digest. It stores no camera friendly name, executable path, device instance ID, URL, or command.
- The current Camera-class friendly name exists only in memory after fresh enumeration, must pass
  the strict DirectShow grammar, and is never written to a receipt or authority file.
- The fixed real FFmpeg binary is not the Chocolatey shim. A Win32 deny-write/delete lease is held
  across handle-derived hashing, bounded version evidence, suspended process-image verification,
  capture, child reaping, and pipe cleanup. There is no PATH, shim, or ordinary reopen fallback.
- A consumed run is committed once to a strict local terminal record. Receipt authority uses
  ReceiptCore digest, terminal-record digest, and final result digest in that order; verification
  after process restart reads the fixed terminal record and current source, lock, model, dependency,
  and profile bindings. The process-local issued-digest registry is not authority.
- Python audio imports and outbound non-loopback connections remain denied before MediaPipe vision
  initialization. Ingress timestamps are captured before queue handoff and backlog includes queue
  delay.
- Any lease, identity, terminal-finalization, cleanup, raw-zeroing, seal, binding, or verification
  failure is typed NO_GO. The maximum success remains D1_N1_PREFLIGHT_PASS with
  device_gate_decision=UNVERIFIED and D1_GO=false.



### Revision 1.2 correction

Revision 1.1 used shorthand that prepared authority stores the fixed profile. Source truth is
narrower: the prepared record stores only the random correlation token, authorization nonce, and
sanitized FFmpeg bindings. Profile constants remain immutable source/receipt expectations and are
not duplicated in the prepared record. The token is random and is not derived from the camera
friendly name. Terminal presence, valid or invalid, blocks consume before enumeration or launch.
Terminal creation is serialized by a fixed cross-process authority mutex and a non-replacing
same-volume move.

