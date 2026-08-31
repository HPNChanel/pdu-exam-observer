# Acceptance Gates

Evidence labels: `OBSERVED`, `SOURCE_VERIFIED`, and `UNVERIFIED` are used for load-bearing claims. A local pass is not release, production, institutional, or research-performance acceptance.

## G0 - Source and workspace

- Canonical DOCX and archive witness match the recorded SHA-256 `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`: `SOURCE_VERIFIED`/`PASS`.
- Approved archive disposition and excluded legacy workspace: `OBSERVED`/`PASS`.

## G1 - M0 regression and packaging (HISTORICAL)

This is the `HISTORICAL` M0 package receipt; it is not the current artifact
tuple.

- Python tests 73, Ruff, mypy for 14 files: `OBSERVED`/`PASS`.
- Frontend 9 files/57 tests, typecheck, lint, build: `OBSERVED`/`PASS`.
- M0 smoke and browser/runtime flow: `OBSERVED`/`PASS`, including authenticated replay/SSE resume, sealing, mobile `390x844`, focus-visible controls, and zero normal-path console errors.
- Manifest: `OBSERVED`/`PASS`, 182 entries and 0 forbidden items.
- Dist/package: `OBSERVED`/`PASS`, 5/5 byte/hash matched.
- Executable SHA `30C191FFBC8729736377B8800ADA80459187504772E30B77E7FD0DDCBFD97F27`; detached and bundled manifest SHA `071849B5AB94C60D90F184282C66B6FBBC5FE133AB888304DAAD22DC6D5CFCAC`.

## G2 - M1 migrations, schema, and WAL

- Explicit `PDU_RUNTIME_MODE=m1` selects M1; default M0 remains in-memory: `OBSERVED`.
- Native config is validated at `%LOCALAPPDATA%\PDUExamObserver\config.v1.json`; research root is outside the bundle, static tree, and archive: `OBSERVED`.
- SQLite enables WAL and foreign keys; schema version 1 creates and validates the migration ledger, canonical DDL, required columns, indexes, unique constraints, foreign keys, and checksum: `OBSERVED`.
- Malformed, mismatched, or newer schema state fails closed: `OBSERVED` by schema-integrity tests.

## G3 - Restart, transaction, and idempotency

- Restart preserves studies, participants, sessions, consent/retention records, event sequence, and terminal withdrawal state: `OBSERVED` in M1 smoke/tests.
- Mutations commit metadata before any subscriber/SSE publication: `OBSERVED` by transaction design/tests.
- Same scope/key/request hash replays the stored response; same key with another request hash is rejected: `OBSERVED`.
- `BEGIN IMMEDIATE` serializes mutations; rollback leaves no partial mutation: `OBSERVED`.

## G4 - Authentication and route boundary

- M1 research routes are monitor-origin and reviewer-bearer-only; exact origin/host, content, role, ownership, and idempotency checks apply: `OBSERVED`.
- Bearer is returned once, represented server-side by a digest/session contract, kept in monitor-origin versioned `sessionStorage`, and never persisted in SQLite, cookies, URLs, DOM, localStorage, or logs: `OBSERVED`.
- Candidate cookie/CSRF routes remain exam-origin only; candidate cannot access monitor research routes/events: `OBSERVED`.

## G5 - Readiness and research safety

- Readiness response is typed with `schema_version`, `session_id`, `ready`, and `blocking_gates`: `OBSERVED`.
- `RESEARCH_COLLECTION_NOT_IMPLEMENTED` always blocks; institutional approval, retention authority, operator consent, retention decision, encryption, and ACL gates remain explicit: `OBSERVED`.
- Research sessions cannot enter `RECORDING`; M1 creates governance metadata only and cannot capture a participant: `OBSERVED`.

## G6 - Participant-wide withdrawal and lineage

- Withdrawal is idempotent and terminal; one canonical receipt covers the participant, not only the initiating session: `OBSERVED`.
- All participant sessions become `WITHDRAWN`/collection-blocked; reachable artifact lineage becomes `INVALIDATED`; reconciliation tasks are bounded and queryable: `OBSERVED`.
- New write intents are rejected after withdrawal. Pending partials are quarantined on restart, with the withdrawn terminal state preserved: `OBSERVED`.
- The response contract includes `schema_version`, `withdrawal_receipt_id`, pseudonym, `terminal`, and `task_count`: `OBSERVED`.

## G7 - GOV-P0 static pre-collection pack

- Canonical proposal hash, closed JSON envelopes, body hashes, exact file set,
  method/count invariants, and deterministic manifest/receipt: `OBSERVED`/`PASS`.
- Manifest SHA-256:
  `c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025`.
- `research_ready=false`, `collection_authorized=false`, institutional/consent/
  retention/storage gates unresolved, B0.3 deferred, and M2/M3 unopened:
  `OBSERVED`/`BLOCKED_EXTERNAL`; this is the required fail-closed result.

## G8 - GOV-P1 synthetic withdrawal/deletion rehearsal (HISTORICAL)

This `HISTORICAL` synthetic rehearsal gate is superseded by M1-R1 for current
implementation and package claims.

- One synthetic participant, two sessions, two withdrawal requests, four
  invalidated artifacts, and four pending withdrawal tasks: `OBSERVED`/`PASS`.
- Exact deletion of four manifest-owned synthetic files, out-of-manifest
  sentinel preservation, SQLite close, and temp-root disposal:
  `OBSERVED`/`PASS`.
- EthicsDataReceipt body SHA-256:
  `539405cdb0c5fd3745740cbd5c6727af9afdcc6008ee63622d997c34e0f50b97`.
- GOV-P1 manifest SHA-256:
  `76fe01de697f44ba82208bd40ce1f14eb9f4df993076c3984ff15906620aa9b4`.
- Reviewed-source hash pins, live-source path binding, pre-unlink identity
  recheck, atomic generated outputs, and sanitized unexpected CLI failures:
  `OBSERVED`/`PASS`.
- Hostile concurrent same-account mutation resistance:
  `UNVERIFIED`/`OUT_OF_SCOPE`; the receipt records `false`.
- Production reconciler, export capability, external approval, storage
  controls, and collection authority: `UNVERIFIED`/`BLOCKED`.

## G9 - M1-R1 governance closure and current evidence

- Status: `M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY`.
- Canonical proposal SHA-256:
  `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
- Current package: executable SHA-256
  `EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF`;
  identical bundled/detached manifest SHA-256
  `9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256`;
  186 files; packaging gate 8/8: `OBSERVED`/`PASS`.
- Packaged acceptance revision: 843/843 Python tests and 58/58 frontend
  tests. Current source revision:
  `M1_R1_SOURCE_SUITE_846_OF_846_PASS`, with 846/846 passing in one fresh full
  invocation. Earlier two full invocations each had one distinct
  load-sensitive timeout; the affected tests later passed alone and in bounded
  repetition. The earlier observations remain historical and are not claimed
  fixed. The package was not rebuilt and no runtime changed.
- Desktop and 390x844 packaged frames are local technical evidence, not user
  aesthetic approval or clean-machine portability proof.
- Packaged synthetic flow: challenge issue 201; normal execution 403
  `AUTHORITY_NOT_ISSUED`; logout revoked both challenges; target state,
  artifact bytes, and zero execution/run records remained unchanged:
  `OBSERVED`/`PASS_LOCAL_SYNTHETIC`.
- Binding authority ceiling:
  `production_reconciler_implemented=false`,
  `production_reconciler_real_storage_verified=false`,
  `real_data_deletion_authorized=false`,
  `participant_collection_authorized=false`, `research_ready=false`,
  `collection_authorized=false`, and
  `authority_status=AUTHORITY_NOT_ISSUED`.

## G10 - M2-R0 source/static authority re-entry

- Status: `M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`.
- Current B0-R2 tuple:
  `static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`,
  `candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`,
  and
  `binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`.
- RP2 static check and 24 source/test/script plus 3 lock/model artifact and 21
  policy-preimage reconciliation: `OBSERVED`/`PASS_STATIC_ONLY`.
- Bootstrap provisioning, fresh A0, A1, X0, native/camera execution, M2 exit,
  participant collection, and research authority remain
  `UNVERIFIED`/`BLOCKED`.
- Binding ceiling remains `authority_status=AUTHORITY_NOT_ISSUED`,
  `physical_camera_access_authorized=false`,
  `device_gate_decision=UNVERIFIED`, and `d1_go=false`.

## G11 - GOV-P2 advisor-first submission dossier

- Status:
  `GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW`.
- Audience `FACULTY_ADVISOR_FIRST`; `submission_state=NOT_SUBMITTED`; review
  state `PENDING_EXTERNAL_REVIEW`.
- Manifest SHA-256:
  `1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e`.
- Four annexes are exact upstream bytes; source index pins proposal, GOV-P0,
  and historical GOV-P1 by canonical path and hash.
- Correction A residual:
  `CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT`. The old GOV-P1
  receipt remains immutable and its live checker mismatch is not rewritten.
- Structural validation is not advisor review, institutional approval,
  participant invitation, or collection authority.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

## G12 - GOV-P3 advisor verbal decision receipt

- Status:
  `GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_READY_FOR_INSTITUTIONAL_ROUTING`.
- `ADV-01=SATISFIED_BY_USER_REPORT_UNVERIFIED`; advisor outcome is
  `READY_FOR_INSTITUTIONAL_ROUTING`.
- Evidence mode is `VERBAL_CONFIRMATION_REPORTED_BY_USER`; classification is
  `USER_STATED_UNVERIFIED` and residual is
  `ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY`.
- Manifest SHA-256:
  `7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605`.
- `ADV-02=PENDING_EXTERNAL_DECISION`,
  `institutional_approval_status=NOT_ISSUED`, and
  `submission_state=NOT_SUBMITTED`.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

## G13 - GOV-P4 institutional route source verification

- Status:
  `GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_UNCONFIRMED_APPROVAL_NOT_ISSUED`.
- `adv_02_status=SATISFIED_BY_PUBLIC_PRIMARY_SOURCES` and
  `institutional_route_status=SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED`.
- Verified route: Hội đồng khoa -> forms 1-6 -> research-management office ->
  Rector approval decision -> student begins only after approval.
- Manifest SHA-256:
  `f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531`.
- `human_subjects_review_requirement=UNKNOWN_PENDING_CONFIRMATION` and
  `HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED` remain binding;
  `CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION` remain open.
- `institutional_approval_status=NOT_ISSUED` and
  `submission_state=NOT_SUBMITTED`.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

## G14 - GOV-P5A advisor-first human-confirmation request pack

- Status:
  `GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`.
- Exact questions are `HC-01` late-submission acceptance and `HC-02`
  human-subjects/ethics review routing; audience is `FACULTY_ADVISOR_FIRST`.
- `human_response_status=PENDING`, `external_transmission_authorized=false`,
  and `submission_state=NOT_SUBMITTED`.
- Manifest SHA-256:
  `4c5443ae46972b5ec56d2229700580bd0a6e7c1be61ef79d019c055314962fa8`.
- `CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED` and
  `HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED` remain blocking.
- `HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED` remains a current residual;
  the blank response template is not evidence.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

## Residual and external gates

- `UNVERIFIED`: institutional approval, real participant data, M2+ capture/model work, actual encryption/ACL controls, clean-machine execution, signing, deployment, physical two-monitor behavior, other browsers, and user visual acceptance.
- Node `24.11` versus jsdom `24.15`, and PyInstaller tzdata/pkg_resources warnings, remain environment notes; exact smoke passed.
- Minor `T-01` remains parked: concurrency/CAS and mutant duplicate-event evidence passed, but the test does not directly instrument `SELECT` ordering.
- A control-plane-blocked old `%TEMP%\pdu-m1-smoke-6a73eff5299a48e89a6aca1fc43ce9fb` cleanup contains synthetic smoke only; no process/listener remains.
