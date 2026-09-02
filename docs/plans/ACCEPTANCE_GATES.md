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

## G15 - M2-S2A synthetic integration acceptance

- Status:
  `M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.
- `evidence_kind=SIMULATED`; 977 deterministic zero-pose frames bind the
  synthetic runner to D1 receipt semantics and M2 persistence.
- Both valid `BACKEND_CONTRACT_PASS` and `NO_GO` audit receipts are persisted;
  `integration_status=PERSISTED` does not imply device or research readiness.
- Current RP2 tuple:
  `static_bindings_digest=84694c545120b69cebaa8d64fb40c3c1d574afcecd69126f1238d5e285a7a22f`,
  `candidate_exact_bytes_sha256=cd89fad5be9e804fcdf56b87f8edd517fe15be74de0e1c0dcd01d0e10bb16bec`,
  `binding_schema_exact_bytes_sha256=fcc3ae40caf53e2afd3f67b1f0739ce863e4a6780673e6de0afd904750571d94`.
- At task start Git existed and the baseline was clean `main` at `7912bd9`.

```text
package_contains_integration=false
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

## G16 - M2-S2B synthetic nominal integration acceptance

Status:
`M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

- Exactly 18,077 deterministic zero-pose frames are evaluated under the fixed
  accelerated `run_kind=NOMINAL_20M` contract for 1,200 requested seconds.
- The public M2-S2A API remains intact; the nominal caller cannot select run
  kind, duration, profile, artifact kind, or status marker.
- D1 `BACKEND_CONTRACT_PASS` and exact valid technical `NO_GO` receipts remain
  distinct from `integration_status=PERSISTED`; corrupt or forged evidence and
  persistence/withdrawal failures do not claim an artifact.
- The synthetic fault matrix covers timing, accounting, latency, backlog,
  input, pose, quality, encoder, disk, durability, privacy, receipt integrity,
  idempotency, persistence, and withdrawal routing. This is synthetic routing
  evidence, not proof of a reproduced physical fault.
- RP2 verifies the current 31-entry inventory and 28 policy preimages:
  `static_bindings_digest=6e84eb0699658c61efd335a175a2abb4470f37afeaff131d94cdce332640fa43`,
  `candidate_exact_bytes_sha256=99365851f4fbad6f78c9b94c30eaef362b281c1a901cc15b40f2c5707e9fd771`,
  `binding_schema_exact_bytes_sha256=1bec3a9e9747136f01e43dd76de62f5b622eb00540714ee4c1639ee470edcb2d`.

```text
evidence_kind=SIMULATED
run_kind=NOMINAL_20M
package_contains_integration=false
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

G16 does not authorize camera/device access, participant contact, collection,
export, real deletion, package rebuild, deployment, or M3.

## G17 - M2-S2C synthetic reviewer API/UI acceptance

Status:
`M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

- Monitor routes require the reviewer bearer; exam origin returns 404.
- Request surface contains only `run_kind`, with `PREFLIGHT_60S` and
  `NOMINAL_20M`; no path, device, duration, fixture, digest, or authority input.
- One owned temporary workspace permits one active run, retains at most 32
  records, derives per-intent artifact IDs, and is removed on shutdown.
- Browser evidence shows the persistent synthetic/no-camera/no-collection
  banner and bounded terminal interpretation for both fixed runs.
- RP2 verifies 44 source/tool entries and 32 policy preimages:
  `static_bindings_digest=d54ec5277d9713128e03a0eaae787c5ff6fd04ee6e48fee3654f87655d847248`,
  `candidate_exact_bytes_sha256=582bb50f0ca2118937f7d79d7dd8a0bff3d43d72a58ae540c27c41ccddcabd71`,
  `binding_schema_exact_bytes_sha256=9c460d3fb874faea444ab97a3c85bc70c37d25f6ea1ced5be4f2dbec20092387`.

```text
evidence_kind=SIMULATED
package_contains_integration=false
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

G17 does not authorize physical execution, camera/device access, participant
contact, collection, package rebuild, deployment, or release.

## G18 - M2-S2D synthetic evidence export acceptance

Status:
`M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

- Only terminal persisted synthetic runs, including valid technical `NO_GO`,
  are exportable; corrupt input or forged receipt produces no bundle claim.
- The authenticated monitor route returns a canonical JSON attachment of at
  most 4,000,000 bytes; the exam origin exposes no evidence route.
- The bundle contains the complete minimized persisted artifact and cross-binds
  its SHA-256, D1 semantics, observations, source run, and authority ceiling.
- The offline CLI accepts exactly one regular non-link file and fails closed
  with a bounded canonical receipt; the server creates no export archive.
- Browser evidence downloaded and offline-verified both preflight and nominal
  bundles with console errors/warnings 0/0 and cleanup 0/0/0.
- RP2 verifies 47 source/tool entries and 36 policy preimages:
  `static_bindings_digest=7204b1d53dbac8d5fd7f057c9b5a63e3fde10ec4c68111e4fa2b0ef9312880d3`,
  `candidate_exact_bytes_sha256=46221d85c38df2e44b62d688ff5a162519f215078462ef6f54bc47b65c75abd0`,
  `binding_schema_exact_bytes_sha256=23d742592c018343767ff8b670e1a253f7e2e2cbdf1a91c4829e8dc7bf30a9d3`.

```text
evidence_kind=SIMULATED
package_contains_integration=false
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

G18 does not authorize physical execution, camera/device access, participant
contact, collection, remote transmission, package rebuild, deployment, or
release.

## G19 - M2-S2E strict synthetic reproduction acceptance

Status:
`M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

- Fresh preflight and nominal S2D bundles return `EXACTLY_REPRODUCED` only
  after whole-bundle and all nested comparison digests match.
- Valid older evidence returns `SOURCE_REVISION_MISMATCH` before temporary
  workspace creation; semantic and operational failures cannot emit exact.
- The replay uses only built-in fixtures, verified persistence reads, a
  transient S2D rebuild, and cleanup before success.
- The one-file CLI is bounded to 4,000,000 bytes, rejects links/reparse input,
  emits canonical sanitized output, and creates no output archive.
- RP2 verifies 51 source/tool entries and 40 policy preimages:
  `static_bindings_digest=38a17dcc4ea214a2d52ef2bb825e502bcf88d7dbf48ebc2f3758da93b6d2a585`,
  `candidate_exact_bytes_sha256=15f3bcc27411b1534e6214d8818af70cf46076776af4ae73551d508d0f0f7119`,
  `binding_schema_exact_bytes_sha256=abc494b96a3cc52eda57c43d677c83245736ab65ff923faa4e39524cf84f2dc5`.

```text
evidence_kind=SIMULATED
package_contains_integration=false
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

G19 does not authorize physical execution, device access, participant contact,
collection, M3, package rebuild, deployment, or release.

## G20 - M2-S3A current-source package gap audit acceptance

Status:
`M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY`.

- Canonical audit JSON SHA-256 is
  `a63c0fefa7c7aba37685ccb65bec7fd605448e42873d5d8252975a82ea9269e5`.
- The historical package is `MANIFEST_VERIFIED` and
  `HISTORICAL_NOT_CURRENT_SOURCE`; build-TOC evidence is auxiliary only.
- Exactly eight gaps remain `OPEN`; none has an authority effect.
- RP2 verifies 52 source/tool entries and 42 policy preimages:
  `static_bindings_digest=e11984ea6cd5146a862b9065a22063cf80d3eb8aa7ce92b6929450cafa7769d5`,
  `candidate_exact_bytes_sha256=d98a0013e4c4b3c219fcd0d53e66c5c99dcd3c4fcea6d823d54bf1e040e0c258`,
  `binding_schema_exact_bytes_sha256=17cb07cb672dfccc0c5fe0c3fffd91a82e63a392bbbc0660d09b047dce8ad5f1`.

```text
package_contains_integration=false
package_rebuild_started=false
release_authorized=false
distribution_ready=false
clean_machine_verified=false
same_host_portable_verified=false
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

G20 proves package-gap traceability only. It is not package integration,
portable execution, distribution readiness, physical evidence, or release
authority.

## G21 - M2-S3B deterministic current-source candidate acceptance

Status marker:
`M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY`.

Pass only if:

- The canonical integration receipt SHA-256 is
  `bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd`.
- RP2 checks the final tuple
  `static_bindings_digest=a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f`,
  `candidate_exact_bytes_sha256=a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639`,
  and `binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca`.
- Build A and B have the same tree digest
  `29a0d7749e8069978f54d9c0087261fe709da3c016c73acca9cffb5034f8c37e`
  with no mismatch paths.
- Recursive archive inventory contains all 14 required modules; the packaged
  frontend equals the isolated build; the candidate README retains every
  synthetic/no-authority marker; both candidate manifests verify.
- GAP-01, GAP-02, and GAP-07 are `CLOSED_FOR_CURRENT_CANDIDATE`; GAP-03,
  GAP-04, GAP-05, GAP-06, and GAP-08 remain `OPEN`.
- The historical package remains byte-identical and manifest-valid.
- The following ceiling remains exact:

```text
historical_package_unchanged=true
candidate_package_built=true
candidate_package_contains_integration=true
packaged_runtime_smoke_verified=false
same_host_portable_verified=false
clean_machine_verified=false
release_authorized=false
distribution_ready=false
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

G21 is static same-host build evidence only. The candidate was not run and is
not portability, distribution, physical-device, research, collection, or
release evidence.

## G22 - M2-S3C packaged synthetic runtime smoke acceptance

PASS requires
`M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`
and the following exact current evidence:

```text
packaged_smoke_receipt_sha256=479aa2e364216a8f4560fbf98a31a6935829d847dfbace65f7c66fae8778bbb7
package_integration_receipt_sha256=bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd
candidate_source_static_bindings_digest=a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f
candidate_source_candidate_exact_bytes_sha256=a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639
candidate_source_binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca
static_bindings_digest=721783d4d89eb55a599a1505574741d9e631d66a5ceee7e443f4469058104a8a
candidate_exact_bytes_sha256=ca5e80e847e11f93f8a8da33ddc743b1f106a50af864a7eb339194a1ef86929a
binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca
historical_package_unchanged=true
candidate_package_unchanged=true
candidate_package_contains_integration=true
packaged_runtime_smoke_verified=true
same_host_portable_verified=false
clean_machine_verified=false
release_authorized=false
distribution_ready=false
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
GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE
GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT=OPEN
GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT=OPEN
GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT=OPEN
GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT=OPEN
```

G22 requires exactly two candidate processes, fixed preflight and nominal runs,
byte-identical projections, loopback-only listeners, candidate immutability,
and cleanup. It does not establish portability, camera/device, participant,
distribution, signing, or release evidence.

## Residual and external gates

- `UNVERIFIED`: institutional approval, real participant data, M2+ capture/model work, actual encryption/ACL controls, clean-machine execution, signing, deployment, physical two-monitor behavior, other browsers, and user visual acceptance.
- Node `24.11` versus jsdom `24.15`, and PyInstaller tzdata/pkg_resources warnings, remain environment notes; exact smoke passed.
- Minor `T-01` remains parked: concurrency/CAS and mutant duplicate-event evidence passed, but the test does not directly instrument `SELECT` ordering.
- A control-plane-blocked old `%TEMP%\pdu-m1-smoke-6a73eff5299a48e89a6aca1fc43ce9fb` cleanup contains synthetic smoke only; no process/listener remains.
