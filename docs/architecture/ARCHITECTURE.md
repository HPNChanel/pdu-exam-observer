# Architecture

## Current architecture (2026-09)

The launcher accepts five `PDU_RUNTIME_MODE` values (`launcher.py`): `m0`
(deterministic in-memory demo, default), `m1` and `m1r1` (native-configured
SQLite/WAL governance persistence), `m2synthetic` (reviewer synthetic
evidence service), and `m2research` (the research workspace path).

In `m2research` the launcher requires `PDU_WORKSPACE_ROOT` — an absolute,
non-UNC, symlink-free local directory validated by `validate_storage_root` —
and constructs four components under it:

- `WorkspaceBackend` (`root/exam`): SQLite persistence for exam-side state.
- `WorkspaceService` (`root/metadata`): the monitor-only workspace boundary —
  pairing, consent/preflight orchestration, session actions, review, export,
  withdrawal — exposed through `api/workspace.py` behind the reviewer bearer
  on the monitor origin only.
- `ResearchRuntimeService` (`root/research`): session lifecycle, REAL vs
  synthetic capture, per-frame MediaPipe pose, temporal rules, artifact
  persistence, allowlisted evidence export, and withdrawal. Capture runs in
  a spawned `NativeCapture` child (`research_runtime/camera_worker.py`) so
  the camera has exactly one owner process.
- `ModelRegistry` (`root/models`): hash-verified eight-file model bundles
  with atomic `active.json` activation; inference is abstaining and
  fail-closed.

REAL collection additionally requires a native authority record installed by
`authority_cli` into `<root>/.pdu_exam_observer/collection-authority.v1.json`
and referenced by the launcher environment via `PDU_COLLECTION_AUTHORITY_REF`;
every REAL frame, preview, and export revalidates it. `RootLease` takes a
non-blocking OS lock per storage root so two processes cannot own the same
workspace concurrently.

## Historical baseline (M0/M1)

The sections below describe the M0/M1 baseline. They remain accurate for
those modes and are retained as design history for the workspace path.

### Runtime modes

The application has two explicit modes. M0 is the default and uses the existing in-memory backend for the deterministic demo. M1 is selected only when `PDU_RUNTIME_MODE=m1`; startup then loads native configuration and constructs `M1Backend` over `M1Store`. M1 is metadata persistence and research governance, not collection.

Both modes run two FastAPI applications in one local process: exam on `127.0.0.1` and monitor on `localhost`. The launcher uses standard-user loopback binding and does not expose a LAN listener.

### Native configuration and storage

The native configuration command writes schema-versioned JSON to `%LOCALAPPDATA%\PDUExamObserver\config.v1.json` with `root`, `encryption_status`, and `acl_status`. The configured root must be an absolute local writable directory outside the bundle, static frontend tree, and archive; reparse points and UNC roots are rejected on Windows.

M1 creates `operational\pdu-exam-observer.sqlite3` and its WAL files below the configured root. The database, staging partials, quarantine, logs, exports, and future media are outside the replaceable application directory. No runtime data is written into the bundle.

`VERIFIED` encryption/ACL values are typed operator/test attestations stored in the root record. They do not prove that encryption or Windows ACL enforcement exists.

### Persistence and schema integrity

M1 schema version 1 has a `schema_migrations` ledger and canonical DDL checksum. Startup enables SQLite `WAL` and `foreign_keys`, creates the schema only when the ledger is absent, and rejects malformed, mismatched, incomplete, or newer schema state. Validation covers canonical SQL objects, columns, indexes, unique constraints, and foreign keys.

The operational tables are `schema_migrations`, `storage_roots`, `studies`, `participants`, `sessions`, `consent_receipts`, `retention_records`, `exam_attempts`, `answer_versions`, `session_events`, `idempotency_records`, `artifact_registry`, `artifact_dependencies`, `withdrawal_receipts`, `withdrawal_tasks`, `write_intents`, and `audit_events`.

### Transactions, events, and SSE

Every M1 mutation runs under a locked `BEGIN IMMEDIATE` transaction. The operation, event-sequence increment, session event row, idempotency response, and audit/lineage rows commit together or roll back together. The event row is committed before `_publish` places the event on in-process subscribers; SSE therefore never becomes the source of truth.

Idempotency is scoped by operation and key. The request payload is canonicalized and hashed. A matching prior hash returns the stored response; a mismatched reuse fails closed. This covers create, consent, answer/submit, withdrawal, and other retryable mutations.

### Authentication and trust boundaries

Reviewer login remains monitor-origin bearer authentication. The bearer is returned once, represented server-side by a digest/session contract, and held by the monitor only in versioned `sessionStorage` for request-time `Authorization`. PINs, bearer material, bearer digests, cookies, and authorization state are memory-only and never enter SQLite.

M1 research routes are reviewer-bearer-only. Candidate routes remain separate on the exam origin with host-only `HttpOnly` cookie plus CSRF. Candidate capabilities cannot access research metadata, reviewer events, artifacts, exports, or model routes.

### Research state and readiness

Research records use opaque study, participant, and session identifiers. A study starts as `APPROVAL_PENDING`; a research session starts `DRAFT`, then may record consent metadata and readiness state. `readiness` returns typed blocking codes. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` is unconditional in M1, so a research session cannot enter `RECORDING`; no camera, pose, model, or real participant data is accepted.

The demo session state machine remains available for M0 deterministic replay. It is not evidence that a research session captured media.

### Withdrawal, lineage, and recovery

Withdrawal resolves the participant from the initiating research session, then atomically marks the participant withdrawn, marks every related session `WITHDRAWN` and collection-blocked, recursively traverses artifact dependencies, marks reachable artifacts `INVALIDATED`, creates one canonical withdrawal receipt, creates one bounded task per affected artifact, and records audit/session events. Repeated withdrawal requests return the canonical receipt.

Write intents name only validated relative partial paths. On restart, pending intents are rechecked; partial artifacts are moved to the quarantine area and the session becomes `FAILED` unless it is already terminal `WITHDRAWN`. A withdrawn participant remains terminal and cannot acquire new intents.

### Acceptance boundary

M1 local evidence is `M1_LOCALLY_VERIFIED` as of 2026-08-25. It does not establish actual storage encryption/ACL controls, institutional approval, real participant data, M2+ capture, model performance, clean-machine portability, signing, deployment, physical two-monitor acceptance, user visual acceptance, release, or production.
