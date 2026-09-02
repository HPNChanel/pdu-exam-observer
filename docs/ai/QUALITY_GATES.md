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

## G11 - M2-S2A synthetic vertical-slice integrity

- Status:
  `M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.
- Focused M2-S2A tests pass 12/12; scoped Ruff and strict mypy pass.
- Two no-argument smoke invocations returned exit 0, empty stderr, byte-identical
  canonical output, `BACKEND_CONTRACT_PASS`, `device_gate_decision=UNVERIFIED`,
  `d1_go=false`, and removed their temporary roots.
- RP2 binds 28 source/tool leaves and 25 policy preimages. Current tuple:
  `static_bindings_digest=84694c545120b69cebaa8d64fb40c3c1d574afcecd69126f1238d5e285a7a22f`,
  `candidate_exact_bytes_sha256=cd89fad5be9e804fcdf56b87f8edd517fe15be74de0e1c0dcd01d0e10bb16bec`,
  `binding_schema_exact_bytes_sha256=fcc3ae40caf53e2afd3f67b1f0739ce863e4a6780673e6de0afd904750571d94`.
- At task start Git existed and the baseline was clean `main` at `7912bd9`.

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

## G12 - M2-S2B synthetic nominal integrity

Status:
`M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

- Focused M2-S2B tests cover exactly 12 non-parametrized contracts, including
  18,077-frame shape/timing/golden bindings, S2A regression, exact D1 metrics,
  warmup denominators, synthetic fault routing, integrity rejection,
  idempotency/persistence races, artifact minimization, and no-argument CLI.
- Golden observation digests are independently calculated and literal boundary
  vectors are pinned; a mutated production digest implementation is rejected.
- Threshold failures are produced from mutated nominal observations for FPS,
  gap, latency, backlog, coverage/drop reconciliation, input, pose, quality,
  and manifest routes; exact valid `NO_GO` remains auditable without becoming a
  PASS or authority claim.
- RP2 current tuple is
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

G12 verifies deterministic local source behavior only. Physical device faults,
camera behavior, installed-package inclusion, research performance, and
collection readiness remain unverified.

## G13 - M2-S2C synthetic reviewer integrity

Status:
`M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

Focused Python tests cover single-flight, idempotency, capacity, owned-root
cleanup, monitor-only authentication, closed request schemas, error mapping,
and launcher shutdown. Web tests cover strict authority mapping, optional-route
handling, two fixed actions, GET-only bounded polling, terminal copy, and no
automatic retry. Headed Chromium verified both fixed runs and cleanup.

RP2 tuple:
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

G13 is local source/runtime integrity only. Physical, package, research,
collection, deployment, and release states remain unopened.

## G14 - M2-S2D synthetic evidence integrity

Status:
`M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

Focused Python tests cover verified descriptor reads, link/reparse and mutation
rejection, canonical bundle determinism, PASS and valid `NO_GO`, full semantic
cross-binding, offline CLI bounds, service eligibility, auth, origin
separation, and response headers. Web tests cover byte/hash/body verification,
closed authority mapping, one-shot download, no retry, download lifecycle, and
persistent disclosure. Source Chromium evidence verified both run kinds.

RP2 tuple:
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

G14 proves local source/download/offline-verification integrity only. Physical,
package, research, collection, deployment, and release states remain unopened.

## G15 - M2-S2E strict synthetic reproduction integrity

Status:
`M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

Exact success requires a verified S2D source, matching current environment
binding, deterministic built-in replay, verified persisted artifact, transient
S2D reconstruction, equality of the whole bundle plus every closed nested
digest, and removed temporary state. `SOURCE_REVISION_MISMATCH` stops before
replay. Authority mutation is a bounded failure, never a semantic mismatch.

RP2 tuple:
`static_bindings_digest=38a17dcc4ea214a2d52ef2bb825e502bcf88d7dbf48ebc2f3758da93b6d2a585`,
`candidate_exact_bytes_sha256=15f3bcc27411b1534e6214d8818af70cf46076776af4ae73551d508d0f0f7119`,
`binding_schema_exact_bytes_sha256=abc494b96a3cc52eda57c43d677c83245736ab65ff923faa4e39524cf84f2dc5`.

```text
classification=EXACTLY_REPRODUCED
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

G15 proves current-source built-in synthetic determinism only. Physical,
package, research, collection, M3, deployment, and release states remain
unopened.

## G16 - M2-S3A package-gap audit integrity

Status:
`M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY`.

Canonical audit verification binds exact historical package/build/frontend
inputs, S2E upstream identity, a closed eight-gap matrix, canonical body hash,
and a human-readable projection. Audit JSON SHA-256 is
`a63c0fefa7c7aba37685ccb65bec7fd605448e42873d5d8252975a82ea9269e5`.

RP2 tuple for 52 source/tool entries and 42 policy preimages:
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

G16 is audit/static evidence only. The historical package was not rebuilt and
no packaged S2A-S2E, portability, camera, participant, M3, deployment, or
release claim is opened.

## G17 - M2-S3B deterministic package integration integrity

Require
`M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY`
and receipt SHA
`bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd`.

The gate recomputes or checks:

- RP2 tuple
  `static_bindings_digest=a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f`,
  `candidate_exact_bytes_sha256=a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639`,
  and `binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca`;
- byte-identical build A/B tree digest
  `29a0d7749e8069978f54d9c0087261fe709da3c016c73acca9cffb5034f8c37e`;
- recursive executable/PYZ inclusion, isolated frontend equality, README
  boundary, candidate manifest integrity, and historical package immutability;
- GAP-01/GAP-02/GAP-07 `CLOSED_FOR_CURRENT_CANDIDATE` with GAP-03/GAP-04/
  GAP-05/GAP-06/GAP-08 `OPEN`;
- exact authority ceiling:

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

G17 does not run the candidate and does not establish packaged smoke,
portability, clean-machine evidence, distribution readiness, or release
authority.

## G18 - M2-S3C packaged synthetic runtime smoke integrity

Required marker:
`M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`.

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

Quality evidence requires two fixed packaged invocations, four terminal
synthetic runs, byte-identical projections, loopback inspection, forced tree
termination, candidate immutability, and owned-root cleanup. Same-host and
clean-machine portability remain false.

## External and residual gates

- `UNVERIFIED`: institutional approval, real participant data, M2 capture/pose/model work, clean-machine execution, signing, deployment, physical two-monitor behavior, other browsers, and user visual acceptance.
- PyInstaller tzdata/pkg_resources warnings remain environment notes; exact M1 smoke passed.
- Parked Minor `T-01`: code review, transactional CAS, and mutant duplicate-event evidence passed, but the concurrency test does not directly instrument `SELECT` ordering.
- One control-plane-blocked cleanup path left synthetic data under `%TEMP%\pdu-m1-smoke-6a73eff5299a48e89a6aca1fc43ce9fb`; no PDU process/listener remains. This does not establish release or production status.

## G19 - M2-S3D packaged evidence round-trip integrity

Required marker:
`M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`.

```text
round_trip_receipt_sha256=4d8a862408aec0470d86b084f1abdc9baa323a3ee53cb57dfe780c3d6e2258ed
static_bindings_digest=034eb3e19f88377529f5ffc37c077938b42563a447d1d6e6a481c1b635cbf607
candidate_exact_bytes_sha256=ced85d39533de902da652c4a7f56ea85eaf4891a5d8b27946badf8aebcae5c79
binding_schema_exact_bytes_sha256=7125de572f5a78b986a768b484315b818e1c630d10ada48ea31bd0915c300058
source_tool_inventory_count=64
policy_preimage_count=55
historical_package_unchanged=true
candidate_package_unchanged=true
candidate_package_contains_integration=true
packaged_runtime_smoke_verified=true
packaged_evidence_round_trip_verified=true
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
GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED=CLOSED_FOR_CURRENT_CANDIDATE
GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED=CLOSED_FOR_CURRENT_CANDIDATE
GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE
GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE
GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT=CLOSED_FOR_CURRENT_CANDIDATE
GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT=OPEN
GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE=CLOSED_FOR_CURRENT_CANDIDATE
GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT=OPEN
```

Quality evidence requires structured S2D verification, strict same-revision
reproduction through the packaged stdin-only mode, closed digest comparison,
two byte-identical projections, and process/listener/temp cleanup. Same-host
and clean-machine portability remain false.
