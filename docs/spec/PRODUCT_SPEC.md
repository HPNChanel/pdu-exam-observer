# Product Specification

Version: 1.0

Status: APPROVED FOR M0

## Product thesis

PDU Exam Observer is a research instrument, not a surveillance verdict system. It reduces the reviewer's search burden by marking time-bounded observable events and explaining which signals contributed. A camera can show posture, presence, and movement; it cannot establish intent, honesty, identity, or unobserved phone use.

The product must make this boundary visible in copy, schemas, exports, alerts, and failure behavior. A technically confident prediction with weak evidence is less acceptable than an explicit TECHNICAL_INSUFFICIENT result.

## Users

Research operator: configures the study, confirms consent, runs preflight, starts and seals sessions, views alerts, reviews events, imports approved models, and exports allowlisted research data.

Participant: completes a mock exam on the primary display. The participant sees recording disclosure and technical state, but never behavior labels, alerts, confidence, reviewer notes, or model details.

Research analyst: trains and evaluates models using pseudonymous exports. The analyst does not receive raw video, identity mappings, full window metadata, or browser history.

## Supported environment

Windows 11 x64, standard-user execution, one camera, one participant, one active Windows session, primary display for exam, secondary display for reviewer, Microsoft Edge or another supported Chromium browser, offline operation.

## Core journeys

### Researcher setup

The reviewer opens the monitor origin, authenticates with a local PIN, selects an approved storage root and retention record, creates a pseudonymous participant session, records a consent receipt, runs camera/display/disk preflight, and pairs the candidate exam surface with a one-time code.

### Mock exam

The candidate sees instructions, recording disclosure, timer, sample questions, answer-save state, connection state, and a neutral technical status. Answers are idempotently autosaved. Leaving the exam window becomes a focus enum without recording a window title or process name.

### Real-time review

The server creates a durable alert event before publishing it. The second monitor shows the event label in neutral observable language, duration, confidence, contributing signals, quality state, and health state. It does not show live raw video.

### Post-session review

After the session is sealed, an authorized reviewer may inspect locally stored clips, confirm or reject event boundaries, select UNCERTAIN when evidence is insufficient, and add a reason code. This workflow arrives after M0.

### Research export

The operator explicitly requests an export. The server constructs a new bundle from an allowlist and emits a manifest with schema version, record counts by source kind, hashes, and a local-only operator audit record. The Colab/research export contains no operator identity or audit record. No background upload occurs.

## Local authentication and origin contract

This current M0 contract is `OBSERVED` by the backend/frontend code gates; it is not browser, device, clean-machine, release, or production evidence. The exam origin uses host `127.0.0.1` and the monitor origin uses host `localhost`. The launcher binds the exam server to IPv4 loopback and the monitor server to localhost loopback.

The candidate is authenticated only by a host-only `HttpOnly` cookie plus CSRF protection at the exam origin. The reviewer is not cookie-authenticated: PIN login returns an opaque 256-bit bearer exactly once; only its digest is stored server-side; only one reviewer bearer is active; replacement, logout, and expiry revoke it; and the fixed TTL is two hours. The monitor stores the bearer only in versioned monitor-origin `sessionStorage`, attaches it at request time in `Authorization`, uses `credentials: omit`, validates it after reload, and clears it on `401`. It never appears in a URL, cookie, `localStorage`, DOM, or log. Reviewer event delivery uses authenticated POST fetch-stream SSE with bearer revalidation per event/heartbeat; native `EventSource` is not used.

## Functional requirements

FR-001: The application shall expose independent exam and monitor capabilities on separate loopback origins: exam host `127.0.0.1` and monitor host `localhost`.

FR-002: Reviewer access shall require a local PIN. Candidate access shall require a one-time pairing code.

FR-003: Candidate authentication shall use a host-only `HttpOnly` cookie plus CSRF at the exam origin. Reviewer authentication shall not use a cookie: login shall return one opaque 256-bit bearer, with only its server-side digest retained, one active bearer, fixed two-hour TTL, and revocation on replacement, logout, or expiry.

FR-003a: The monitor shall store the reviewer bearer only in versioned monitor-origin `sessionStorage`, attach it at request time in `Authorization` with `credentials: omit`, validate it after reload, and clear it on `401`. The bearer shall not appear in a URL, cookie, `localStorage`, DOM, or log.

FR-003b: Reviewer event delivery shall use authenticated POST fetch-stream SSE with bearer revalidation on every event/heartbeat; native `EventSource` is prohibited.

FR-004: A session shall follow the server-owned lifecycle DRAFT, CONSENT_CONFIRMED, PREFLIGHT_READY, RECORDING, SEALED, FAILED, or WITHDRAWN.

FR-005: Capture shall not start without an explicit consent receipt, an approved retention record, a writable private storage root, and passing preflight.

FR-006: The exam surface shall support timer, navigation, idempotent answer save, submit, connection state, and technical state.

FR-007: The exam surface shall never render alert labels, confidence, contributing signals, reviewer controls, or raw server traces.

FR-008: The monitor shall receive persisted events in sequence and recover missed events after reconnect.

FR-009: Every event shall carry model, policy, schema, and source provenance.

FR-010: Camera, pose, focus, model, encoder, disk, and schema failures shall not produce NORMAL by default.

FR-011: Real-time alerts shall be visible only on the reviewer-facing second display.

FR-012: Live monitor mode shall show skeleton or abstract evidence only; raw video is restricted to preflight and authorized post-session review.

FR-013: Model import shall reject missing, incompatible, unapproved, or hash-mismatched bundles.

FR-014: Export shall include only approved pseudonymous fields and shall reject media and identity mappings.

FR-015: Demo mode shall be visually labeled and shall never imply that a real camera or trained model produced its events.

## AlertEvent confidence contract

`AlertEvent.confidence` is `number | null`. `AlertEvent.confidence_status` is the required enum `MODEL_UNAVAILABLE`, `INSUFFICIENT`, `CALIBRATED`, or `NOT_APPLICABLE`.

- `MODEL_UNAVAILABLE`: confidence is `null`; used by the M0 deterministic demo and any run without an approved model.
- `INSUFFICIENT`: confidence is `null`; evidence quality or required inputs did not support a calibrated score.
- `CALIBRATED`: confidence is a finite value in `[0, 1]` produced by the locked calibration path.
- `NOT_APPLICABLE`: confidence is `null`; the event type or technical state has no probability semantics.

The combinations `MODEL_UNAVAILABLE` with a numeric confidence, `INSUFFICIENT` with a numeric confidence, and `CALIBRATED` with a null confidence are schema failures. M0 must never emit placeholder probabilities.

## Export envelope

The Colab/research export may contain exactly these envelope and sample fields: `export_id` (pseudonymous random identifier), `manifest_sha256`, `schema_version`, `record_count`, `sample_id`, `participant_pseudonym`, `session_pseudonym`, `source_kind`, `parent_provenance_id`, `pose`, `label`, `quality`, `focus`, and `timing`. It must not contain operator identity, operator audit records, raw video, identity mappings, names, usernames, URLs, window titles, process names, or arbitrary paths. Operator audit records remain local to the operational store and are not part of the Colab bundle.

## Non-functional requirements

NFR-001: Bind literal 127.0.0.1 only; never bind 0.0.0.0, LAN addresses, or IPv6 wildcard.

NFR-002: Operate without Internet, remote fonts, CDNs, analytics, runtime downloads, or cloud credentials.

NFR-003: Package as a Windows x64 PyInstaller one-directory bundle, then ZIP it.

NFR-004: Run without installed Python, Node, administrator rights, Windows service installation, or installer.

NFR-005: Persist event creation before live delivery and use monotonic event sequence numbers.

NFR-006: Keep raw video and identity data outside the replaceable application directory.

NFR-007: Recover or quarantine incomplete session artifacts after interruption.

NFR-008: Use Vietnamese user-facing language and English code/schema names.

## Explicit non-goals

No production exam deployment, LAN dashboard, multiple candidate machines, remote proctoring, face identity, audio, keystroke collection, network monitoring, automatic discipline, fraud verdict, phone-use inference without visible evidence, auto-update, model marketplace, plugin system, or cloud database.
