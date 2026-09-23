# M1 Persistence Specification

Status: binding actual interface/spec for locally verified M1. Updated `2026-08-25`.

Evidence terms: implementation/runtime facts are `OBSERVED`; proposal constraints are `SOURCE_VERIFIED`; future or external claims are `UNVERIFIED`.

## 1. Scope and modes

M1 persists research metadata and enforces governance preconditions. It does not capture a webcam, process pose, write media, run a model, or collect a real participant. M0 remains the default in-memory deterministic demo.

Select M1 explicitly with `PDU_RUNTIME_MODE=m1`. Startup must load a valid native config and construct the SQLite-backed backend. Any other value fails closed; absent mode means M0.

## 2. Native configuration

The native command is `PDUExamObserver.exe configure --root <absolute-local-root> [--encryption-status UNKNOWN|VERIFIED] [--acl-status UNKNOWN|VERIFIED]`.

The config file is `%LOCALAPPDATA%\PDUExamObserver\config.v1.json` and contains exactly the schema version, research `root`, `encryption_status`, and `acl_status` needed by the native loader. The root must be absolute, writable, local, outside the bundle/static/archive roots, and free of reparse-point traversal. The database is created at `<root>\operational\pdu-exam-observer.sqlite3`; the bundle is never the data root.

`VERIFIED` statuses are operator/test attestations only. They do not certify encryption or ACL enforcement.

## 3. Storage schema and migration integrity

SQLite is opened with `check_same_thread=false`, `PRAGMA journal_mode=WAL`, and `PRAGMA foreign_keys=ON`. Schema version 1 contains:

- `schema_migrations(version, applied_at_utc, checksum)`;
- `storage_roots(id, encryption_status, acl_status, configured_at)`;
- `studies`, `participants`, and `sessions` for opaque research metadata and state;
- `consent_receipts`, `retention_records`, `exam_attempts`, and `answer_versions`;
- `session_events` with `(session_id,event_seq)` primary key;
- `idempotency_records` with `(scope,idempotency_key)` primary key;
- `artifact_registry` and `artifact_dependencies` for validity and lineage;
- `withdrawal_receipts` and `withdrawal_tasks` for participant-wide recovery;
- `write_intents` for validated partial-artifact intent; and
- `audit_events` for local operator/research governance records.

The first migration records one checksum over the migration ledger and canonical DDL. Startup rejects a missing/malformed ledger, an unexpected version, a checksum mismatch, missing/extra schema objects, incorrect column shapes, indexes, unique constraints, or foreign keys. Unknown newer schema versions fail closed.

## 4. Monitor bearer-only interface

`GET /api/v1/health` is a loopback health check. Reviewer login/session/logout use the existing monitor-origin bearer contract. M1 research mutation and read routes are monitor-origin, exact-origin/host checked, and require `Authorization: Bearer <token>`:

- `POST /api/v1/research/studies` body `{study_code}` creates a study with `APPROVAL_PENDING` status.
- `POST /api/v1/research/participants` body `{study_id}` creates an opaque participant pseudonym.
- `POST /api/v1/research/sessions` body `{study_id, participant_id, retention_policy_reference?, retention_end_date?}` creates a `RESEARCH` session in `DRAFT`. A retention end date cannot be in the past.
- `POST /api/v1/research/sessions/{session_id}/consent-confirmation` body `{consent_receipt_id, consent_version}` records operator consent metadata.
- `GET /api/v1/research/sessions/{session_id}/readiness` returns typed blocking gates and is always `ready: false` in M1.
- `POST /api/v1/research/sessions/{session_id}/withdrawal` creates or replays the canonical participant-wide receipt.
- `GET /api/v1/research/sessions/{session_id}/withdrawal-status` returns the canonical receipt or current task count.
- `GET /api/v1/research/sessions/{session_id}/recovery` returns recovery state and collection-blocked status.

All mutating research requests use `Idempotency-Key`. Candidate exam routes remain on the separate exam origin and cannot call these routes. Existing monitor event/replay routes remain bearer-only and are M0 deterministic demo routes.

## 5. Typed state and readiness gates

Supported session states are `DRAFT`, `CONSENT_CONFIRMED`, `PREFLIGHT_READY`, `RECORDING`, `SEALED`, `FAILED`, and `WITHDRAWN`. M1 research sessions may be created and governed but cannot transition to `RECORDING`; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` is unconditional. This gate is scoped to the M1 research-session store: the separately governed workspace runtime (`runtime_sessions`) implements its own collection path under a distinct authority record and remains closed pending the same external approvals.

Readiness has this shape:

```json
{"schema_version":1,"session_id":"opaque-id","ready":false,"blocking_gates":["RESEARCH_COLLECTION_NOT_IMPLEMENTED"]}
```

The typed gate set is `INSTITUTIONAL_APPROVAL_REQUIRED`, `OPERATOR_CONSENT_REQUIRED`, `RETENTION_DECISION_REQUIRED`, `RETENTION_AUTHORITY_UNVERIFIED`, `STORAGE_ENCRYPTION_UNVERIFIED`, `STORAGE_ACL_UNVERIFIED`, and `RESEARCH_COLLECTION_NOT_IMPLEMENTED`. A browser-supplied approval boolean cannot clear an authority gate.

## 6. Transaction and idempotency rules

Every mutation uses `BEGIN IMMEDIATE`. The operation and its event/audit/idempotency rows commit atomically; exceptions roll back. Events are inserted and sequence numbers advanced before in-process subscriber publication or SSE delivery.

For `(scope, idempotency_key)`, the canonical request hash and serialized response are stored. Repeating the same request returns the stored response. Reusing the key with a different request hash returns a conflict and performs no mutation. This rule applies across restart.

## 7. Withdrawal and recovery

Withdrawal is terminal and participant-wide. The initiating session identifies the participant; all participant sessions become `WITHDRAWN` and `collection_blocked`. A single `withdrawal_receipts` record is canonical. All reachable children in `artifact_dependencies` are invalidated in `artifact_registry`, one pending `withdrawal_task` is created per affected artifact, and local audit/session events are recorded. Repeated requests from any related session return the same receipt.

`write_intents` accepts only validated relative partial paths under the configured staging area. A pending partial on restart is quarantined and its intent becomes `QUARANTINED`; the session becomes `FAILED` unless it was already `WITHDRAWN`. Withdrawal rejects new intents and blocks collection/export.

The withdrawal response is:

```json
{"schema_version":1,"withdrawal_receipt_id":"opaque-id","participant_pseudonym":"opaque-code","terminal":true,"task_count":0}
```

## 8. UI flow

The monitor authenticates with the PIN, creates a study/participant/session, records consent metadata, displays the blocking readiness gates, and exposes recovery and participant withdrawal controls. Withdrawal requires an explicit confirmation and states that it applies to all related sessions and artifacts and is not reversible in M1. The candidate surface remains separate and does not display reviewer alert vocabulary. The monitor displays governance and technical status, not camera/video evidence.

## 9. Acceptance and claim boundaries

M1 local exit evidence is `OBSERVED`: 73 Python tests; Ruff; mypy for 14 files; frontend 9 files/57 tests with typecheck/lint/build; M0 and M1 smoke; 182 manifest entries with 0 forbidden; 5/5 package match; exact executable SHA `30C191FFBC8729736377B8800ADA80459187504772E30B77E7FD0DDCBFD97F27`; identical manifest SHA `071849B5AB94C60D90F184282C66B6FBBC5FE133AB888304DAAD22DC6D5CFCAC`; browser/runtime `PASS`; Sol visual advisory `ACCEPT`; and zero remaining processes/listeners.

This receipt does not claim institutional approval, real participant data, camera/pose capture, model training or performance, actual encryption/ACL enforcement, clean-machine portability, signing, deployment, physical two-monitor behavior, other-browser acceptance, user visual acceptance, release, or production. M2 collection/capture remains unauthorized and unopened.
