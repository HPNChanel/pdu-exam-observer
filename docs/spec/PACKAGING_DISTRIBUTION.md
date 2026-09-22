# Packaging and Distribution Specification

Version: 1.0

## Target

Windows 11 x64, standard user, offline, no installed Python or Node, no administrator privilege, no service, no installer, and no auto-update.

## Build shape

Build the React application first and copy immutable static assets into the Python package. Build Python with PyInstaller one-directory mode. One-file mode is intentionally excluded because native ML and media dependencies are easier to diagnose and verify in a visible bundle.

The verified workspace delivery (candidate-06, 2026-09-08) has this shape:

~~~text
PDU-Workspace/
  PDUWorkspace.exe
  _internal/
    assets/web/                        built frontend
    demo/                              deterministic demo fixture
    pdu_exam_observer/assets/models/   pose/face task models
    tools/ffmpeg.exe                   pinned encoder binary
  START.cmd                            workspace entry point
  HUONG_DAN.md                         Vietnamese operator guide
  SOURCE_MANIFEST.json                 source byte inventory
  DELIVERY_MANIFEST.json               bundle manifest
  RELEASE_MANIFEST.json
  THIRD_PARTY_NOTICES.txt
  FFMPEG_LICENSE.txt
~~~

`PDU-Workspace-local.zip` ships beside a detached
`RELEASE_MANIFEST.detached.json`; the historical M1 bundle
(`PDU-Exam-Observer/PDUExamObserver.exe`, built by the legacy
`packaging/PDU-Exam-Observer.spec` path) is retained for provenance and is
not the current-source delivery.

The exact pinned toolchain and FFmpeg acquisition recipe required to attempt
a rebuild are recorded in `docs/spec/BUILD_TOOLCHAIN.md`.

The historical portable release has this conceptual shape:

~~~text
PDU-Exam-Observer/
  PDUExamObserver.exe
  _internal/
  assets/
  demo/
  models/
  THIRD_PARTY_NOTICES.txt
  RELEASE_MANIFEST.json
  README.txt
~~~

Runtime data, identity mappings, exports, logs, imported models, and real media are outside this directory.

## Included assets

- Python runtime and pinned dependencies.
- Built frontend assets.
- Approved MediaPipe task model when M2 opens.
- ONNX Runtime CPU and approved model bundles when M6 opens.
- Pinned, license-reviewed FFmpeg binary when M2 opens.
- Deterministic non-personal demo fixtures.
- Licenses, third-party notices, release manifest, and checksums.

## Exclusion gate

Fail packaging if the assembly contains:

- _archive, data, runtime, exports, test output, cache, coverage, or source-control metadata;
- .env, token, cookie, credential, key, PIN, identity mapping, or consent document;
- MP4, participant image, real landmark export, database, log, partial file, or unapproved model;
- Node modules, development server, compiler cache, or raw source proposal unless explicitly listed as public documentation.

## Release manifest

Record product version, schema version, target OS/architecture, build time, source revision when Git is authorized, Python lock hash, frontend lock hash, every included file hash, model/task/FFmpeg versions, test receipt identifiers, and known limitations. The identical `RELEASE_MANIFEST.json` bytes are included inside the bundle and copied beside the ZIP as a detached manifest; publish the detached manifest SHA-256 beside the ZIP. Release acceptance compares the detached file byte-for-byte and by SHA-256 with the bundled file.

## Acceptance

Extract to a clean path containing spaces and Unicode. Launch as standard user with Internet disabled. Verify:

- only loopback listeners;
- separate exam and monitor origins;
- reviewer login and candidate pairing;
- deterministic demo replay;
- candidate cannot access alerts;
- restart and port collision recovery;
- no Python/Node prerequisite;
- no write into the application directory;
- no personal or restricted data in the ZIP.

M0 acceptance on the development machine is not evidence for another device. Distribution readiness requires a clean Windows 11 x64 machine or VM receipt.
