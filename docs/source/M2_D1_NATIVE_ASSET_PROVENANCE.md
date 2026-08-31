# M2-D1-N1 Native Asset Provenance

Status: `SOURCE_VERIFIED` repository-preparation receipt only.

Retrieval date: `2026-08-26`.

Runtime networking is prohibited. `m2_d1_native.py` loads the packaged bytes only through
`BaseOptions.model_asset_buffer`; no model filename, URL, or download is accepted at runtime.
Before MediaPipe construction it verifies both packaged byte lengths and SHA-256 values plus the
installed `mediapipe==1.0.1` version. The adapter installs its lifetime Python outbound-connect
deny/audit guard before that initialization; loopback remains permitted and receipt evidence records
the guard state and attempt count. This is not a claim about native-OS or third-party native network
activity outside Python's socket audit boundary; that residual remains `UNVERIFIED`.

## Pose Landmarker Lite

- Packaged filename: `pose_landmarker_lite.task`
- Official upstream URL: `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task`
- Upstream channel/version: `pose_landmarker_lite`, `float16/latest`
- Observed immutable object generation: `1682624738331272`; ETag: `04a75ddf7c811ac7a1a4523266dd7d88`
- Byte length: `5777746`
- SHA-256: `59929E1D1EE95287735DDD833B19CF4AC46D29BC7AFDDBBF6753C459690D574A`
- Task type: MediaPipe Pose Landmarker synchronous `VIDEO` task
- Primary task/model documentation: `https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker`
- Model-artifact license: `UNKNOWN`; the MediaPipe source-code Apache-2.0 license at
  `https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE` is not asserted as an asset license.
- Training-data provenance and model limitations: `SOURCE_UNAVAILABLE` in this repository receipt;
  this technical liveness slice performs no model evaluation.

## BlazeFace Short Range

- Packaged filename: `blaze_face_short_range.tflite`
- Official upstream URL: `https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite`
- Upstream channel/version: `blaze_face_short_range`, `float16/latest`
- Observed immutable object generation: `1682480001393569`; ETag: `a3dd6ec31725290770b97cec0cbf94c9`
- Byte length: `229746`
- SHA-256: `B4578F35940BF5A1A655214A1CCE5CAB13EBA73C1297CD78E1A04C2380B0152F`
- Task type: MediaPipe Face Detector synchronous `VIDEO` task
- Primary task/model documentation: `https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector`
- Model-artifact license: `UNKNOWN`; the MediaPipe source-code Apache-2.0 license at
  `https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE` is not asserted as an asset license.
- Training-data provenance and model limitations: `SOURCE_UNAVAILABLE` in this repository receipt;
  this technical liveness slice performs no model evaluation.

## Dependency binding

- Python package: `mediapipe==1.0.1`
- Resolution artifact: `uv.lock`; the lock records the exact 45-package closure and wheel hashes.
- Observed liveness: `MEDIAPIPE_LIVENESS=True` after loading these exact packaged bytes, with no
  camera enumeration, FFmpeg launch, or audio action.
- `sounddevice==0.5.6` is a lock-resolved transitive package. It is `NOT_USED`, not absent: before
  any MediaPipe parent import the adapter installs a sealed disabled module only for
  `mediapipe.tasks.python.audio` and a lifetime deny finder for `sounddevice`, `_sounddevice`,
  `pyaudio`, `soundcard`, and `portaudio`. The fresh-process vision probe observed no such real
  module in `sys.modules`; explicit imports raised `ImportError`.
- Dataset splits, leakage analysis, seeds, baselines, and ablations are `N/A`: this is a fixed-model
  technical liveness/privacy screen, not training, calibration, or model evaluation.
- Offline reproduction: run `uv sync`, disconnect networking, then execute
  `.\\.venv\\Scripts\\python.exe -m pytest tests\\backend\\test_m2_d1_native.py -k vision_import_seal`.

This record does not claim model performance, model evaluation, participant authorization, camera
access, a native preflight result, production readiness, or `D1_GO`.


## Runtime binding amendment (2026-08-26)

D1-N1 validates both packaged model byte lengths and SHA-256 values, the installed
mediapipe==1.0.1 version, the sealed-disabled MediaPipe audio namespace, and the active outbound
Python network guard before camera launch. The fixed real FFmpeg image is bound by a Win32
deny-write/delete lease, handle-derived SHA-256 and sanitized file identity, and a bounded hashed
version output; no executable path or camera friendly name enters authority or receipt evidence.

OBSERVED no-camera capability evidence on the target host: the real non-reparse FFmpeg leaf denied
a conflicting write open while leased, version exited zero, output was 1,485 bytes, and the
executable SHA-256 remained stable before and after the probe. This is loader capability evidence,
not DirectShow, camera, audio-device, or 60-second evidence.

Residual UNKNOWN/UNVERIFIED: hostile same-user source mutation; native-library networking outside
the Python guard; power-loss directory-entry durability; model-artifact license and training-data
provenance; actual DirectShow device mapping, driver buffering, privacy sensitivity, and native
60-second cleanup behavior.



### Capability-probe evidence correction

The observed host probe was a separate PowerShell/.NET FileShare.Read capability probe, not an
execution of WindowsExecutableLease and not suspended-launch evidence. It observed:
- real FFmpeg executable SHA-256: 5af82a0d4fe2b9eae211b967332ea97edfc51c6b328ca35b827e73eac560dc0d
- version-output SHA-256: 7d2f91b616777606f2a778931bc96897fabfcf29c2101b49b30251ae7e3983c1
- output bytes: 1,485
- version exit: 0
- conflicting write open: denied
- leaf reparse: false
- executable hash before/after: stable

The exact production suspended-launch implementation remains UNVERIFIED until its separate
source-level no-camera capability probe is approved and executed. Python stdout is configured
unbuffered; only the two application bytearrays are zero-verified. OS pipe, driver, MediaPipe native,
and device-internal buffering remain UNVERIFIED and are not covered by raw_retained=false.

