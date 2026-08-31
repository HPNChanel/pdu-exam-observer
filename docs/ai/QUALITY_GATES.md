# Quality Gates

Status: `CURRENT_EVIDENCE_LEDGER`

Updated: `2026-08-30`

This ledger separates local observations from user and external acceptance. Final local verifier status for the current M1-R1 governance revision is `OBSERVED`/`VERIFIED`; it is not a release or production receipt.

## G0 - Source and workspace

- Canonical source is `SOURCE_VERIFIED`; project copy and archive witness retain SHA-256 `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
- Archive disposition and the former root-input absence are `OBSERVED` and expected after the approved scoped move.
- G0 is `PASS`, not pending. The old M0 `PENDING` wording is superseded by the current ledger.

## G1 - Python and security contracts

- Python collection: `OBSERVED`, 846 tests. Current source evidence is
  `M1_R1_SOURCE_SUITE_846_OF_846_PASS`, with 846/846 passing in one fresh full
  invocation. Earlier two full invocations each had one distinct
  load-sensitive timeout; the packaging smoke and M2 blocked-reader tests later
  passed alone and in bounded repetition. Those observations remain historical
  and are not claimed fixed. The packaged acceptance revision predates three
  governance-only consistency tests and remains 843/843.
- Scoped Ruff: `OBSERVED`, passed. Repository-wide Ruff retains the documented
  pre-existing `UP038` finding in `tests/backend/test_m2_synthetic.py`.
- mypy: `OBSERVED`, strict pass for 37 source files.
- Auth, origin, role separation, fail-closed research boundaries, and no-camera/no-model claims remain enforced by the current contract. No approval, participant, intent, dishonesty, identity, or disciplinary claim is made.

## G2 - Frontend contracts

- Frontend: `OBSERVED`, 10 files and 58 tests.
- Typecheck, lint, and production build: `OBSERVED`, passed.
- Browser resume, mobile `390x844`, focus-visible controls, reduced-motion behavior, neutral candidate vocabulary, and monitor bearer handling are covered by the current frontend/runtime evidence.
- Node `24.11` versus jsdom `24.15` is an environment warning. The build passed; the warning is not release evidence.

## G3 - M0 artifact and browser regression (HISTORICAL)

This is the `HISTORICAL` M0 artifact receipt, retained without rewriting its
hashes or counts.

- Executable SHA-256: `30C191FFBC8729736377B8800ADA80459187504772E30B77E7FD0DDCBFD97F27`.
- Detached and bundled manifest SHA-256: `071849B5AB94C60D90F184282C66B6FBBC5FE133AB888304DAAD22DC6D5CFCAC` for both copies.
- Manifest: `OBSERVED`, 182 entries and 0 forbidden items.
- Dist/package receipt: `OBSERVED`, 5/5 byte/hash matched.
- M0 smoke: `OBSERVED`, health plus `/exam` and `/monitor` passed.
- Packaged Chromium flow: `OBSERVED`/`PASS` for authentication, pairing, consent, preflight, start/countdown, save/navigation/submit, replay `POST 200`, live SSE cards and resume, sealing, favicon, normal-path console, mobile layout, focus-visible controls, and cleanup.
- Exact-SHA browser/runtime assertion: `PASS`; remaining processes/listeners: zero.
- Sol visual advisory: `ACCEPT`; user visual acceptance: `PENDING`.

## G4 - M1 persistence and governance

- M1 smoke: `OBSERVED`, native configuration, loopback health, study/participant/session governance flow, fail-closed readiness, withdrawal, restart persistence, and cleanup passed.
- SQLite schema version 1 uses WAL, foreign keys, the migration checksum ledger, canonical schema validation, transactional commit/rollback, and explicit write-intent recovery.
- Restart preserves valid metadata and terminal withdrawal state. Duplicate mutations replay the stored response for the same request hash and reject key reuse with a different payload.
- Readiness is typed and `ready=false`; institutional approval, retention authority, storage-control attestations, and `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remain blocking.
- Participant-wide withdrawal is terminal, creates one receipt, invalidates artifact lineage, creates bounded tasks, and blocks new collection/write intents/export.
- Encryption/ACL `VERIFIED` values in this smoke are test attestations, not storage-control proof.

## G5 - M1-R1 current package and governance closure

- Status: `M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY`.
- Canonical proposal SHA-256:
  `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
- Current executable SHA-256:
  `EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF`.
- Identical bundled/detached manifest SHA-256:
  `9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256`;
  186 files; packaging gate 8/8.
- Packaged acceptance remains 843/843 Python tests and 58/58 frontend tests.
  Current source evidence is `M1_R1_SOURCE_SUITE_846_OF_846_PASS`, with three
  governance consistency tests and 846/846 passing in one fresh full
  invocation. Earlier two full invocations each exposed one distinct
  load-sensitive timeout; those observations remain historical and are not
  claimed fixed. The package was not rebuilt or altered. Packaging remains
  8/8 for 186 files.
- Desktop and 390x844 inspection is technical visual evidence only; user
  aesthetic approval and clean-machine portability remain unverified.
- Packaged synthetic challenge issue returned 201; normal execution returned
  403 `AUTHORITY_NOT_ISSUED`; logout revoked both challenges and left both
  targets pending, artifact bytes unchanged, and zero execution/run records.
- Binding authority ceiling:
  `production_reconciler_implemented=false`,
  `production_reconciler_real_storage_verified=false`,
  `real_data_deletion_authorized=false`,
  `participant_collection_authorized=false`, `research_ready=false`,
  `collection_authorized=false`, and
  `authority_status=AUTHORITY_NOT_ISSUED`.

## G6 - M2-R0 current source/static authority tuple

- Status: `M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`.
- RP2 `--check` accepts the current 24-source/test/script plus 3-lock/model,
  21-policy B0-R2 packet without rewriting it: `OBSERVED`/`PASS_STATIC_ONLY`.
- Controlling tuple:
  `static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`,
  `candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`,
  and
  `binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`.
- Bootstrap remains `UNPROVISIONED`; fresh A0 is `NOT_ISSUED`; A1 is
  `NOT_OPENED`; X0 is `BLOCKED`. This gate does not open M2, change package or
  runtime status, or authorize camera/participant/collection activity.

## G7 - GOV-P2 advisor-first dossier

- Status:
  `GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW`.
- `FACULTY_ADVISOR_FIRST`, `submission_state=NOT_SUBMITTED`, and
  `PENDING_EXTERNAL_REVIEW` remain binding.
- Deterministic manifest SHA-256:
  `1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e`.
- Exact annex, forged-decision, closed-file-set, canonical JSON, immutable
  upstream, bounded CLI, and authority-ceiling tests pass locally.
- Correction A records
  `CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT`; it does not rebuild
  historical GOV-P1 to match current M1-R1 source.

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

## G8 - GOV-P3 advisor verbal decision receipt

- Status:
  `GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_READY_FOR_INSTITUTIONAL_ROUTING`.
- The deterministic builder validates exact GOV-P2 upstream hashes, a closed
  canonical record, bounded CLI output, generated manifest/receipt bytes, and
  immutable prior governance artifacts.
- The record permits only `ADV-01=SATISFIED_BY_USER_REPORT_UNVERIFIED` and
  `READY_FOR_INSTITUTIONAL_ROUTING`; evidence remains
  `USER_STATED_UNVERIFIED` with residual
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

## G9 - GOV-P4 institutional route source verification

- Status:
  `GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_UNCONFIRMED_APPROVAL_NOT_ISSUED`.
- Exact downloaded SHA-256/size metadata for the 2022 regulation, current
  2026-2027 notice, and 2026 student form set are recorded in a closed source
  register; the checker is offline and does not refetch sources.
- `adv_02_status=SATISFIED_BY_PUBLIC_PRIMARY_SOURCES` and
  `institutional_route_status=SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED`.
- Manifest SHA-256:
  `f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531`.
- `human_subjects_review_requirement=UNKNOWN_PENDING_CONFIRMATION`,
  `institutional_approval_status=NOT_ISSUED`, and
  `submission_state=NOT_SUBMITTED`.
- Residuals `HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED` and
  `CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION` remain open.

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

## G10 - GOV-P5A human-confirmation request integrity

- Status:
  `GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`.
- Closed file set and canonical JSON validation cover `HC-01`, `HC-02`, the
  source index, evidence rules, and the unfilled response template.
- Audience is `FACULTY_ADVISOR_FIRST`; `human_response_status=PENDING`,
  `external_transmission_authorized=false`, and `submission_state=NOT_SUBMITTED`.
- Manifest SHA-256:
  `4c5443ae46972b5ec56d2229700580bd0a6e7c1be61ef79d019c055314962fa8`.
- Forged answers and authority mutations fail closed while
  `CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED`,
  `HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED`, and
  `HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED` remain open.

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

## External and residual gates

- `UNVERIFIED`: institutional approval, real participant data, M2 capture/pose/model work, clean-machine execution, signing, deployment, physical two-monitor behavior, other browsers, and user visual acceptance.
- PyInstaller tzdata/pkg_resources warnings remain environment notes; exact M1 smoke passed.
- Parked Minor `T-01`: code review, transactional CAS, and mutant duplicate-event evidence passed, but the concurrency test does not directly instrument `SELECT` ordering.
- One control-plane-blocked cleanup path left synthetic data under `%TEMP%\pdu-m1-smoke-6a73eff5299a48e89a6aca1fc43ce9fb`; no PDU process/listener remains. This does not establish release or production status.
