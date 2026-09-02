# Product and Research Roadmap

## M2-S3C - Packaged synthetic runtime smoke

Status:
`M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`
as of `2026-09-02`.

The exact S3B candidate completed two independent packaged invocations on the
build host. Both invocations produced byte-identical preflight and nominal
synthetic projections, used loopback-only listeners, and left candidate bytes
unchanged with no process, listener, or temporary root residue.

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

M2-S3D is the next package task: packaged S2D export and S2E reproduction
round-trip. S3C does not open portability, clean-machine, camera, participant,
distribution, or release gates.

## M2-S3B - Deterministic current-source package integration

Status:
`M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY`
as of `2026-09-01`.

Two isolated builds produced byte-identical current-source candidate trees.
The executable/PYZ inventory contains all 14 required application and S2A-S2E runtime modules, the
frontend is byte-identical to the isolated build, and the candidate README
states the synthetic-only/no-authority boundary. The historical package is
unchanged. Runtime execution is attested separately by M2-S3C.

```text
package_integration_receipt_sha256=bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd
source_tool_inventory_count=58
policy_preimage_count=50
static_bindings_digest=a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f
candidate_exact_bytes_sha256=a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639
binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca
candidate_tree_sha256=29a0d7749e8069978f54d9c0087261fe709da3c016c73acca9cffb5034f8c37e
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

GAP-01, GAP-02, and GAP-07 are `CLOSED_FOR_CURRENT_CANDIDATE`; GAP-03,
GAP-04, GAP-05, GAP-06, and GAP-08 remain `OPEN`. M2-S3C is next and may run
only packaged synthetic smoke under its own contract. S3B does not establish
portability, distribution readiness, physical M2, research readiness, or
release authority.

## M2-S3A - Current-source package gap audit

Status:
`M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY`
as of `2026-09-01`.

The canonical audit confirms that the historical package is
`MANIFEST_VERIFIED` and `HISTORICAL_NOT_CURRENT_SOURCE`. It pins eight open
gaps from Python/frontend inclusion through packaged synthetic smoke,
export/reproduction, manifest/README currency, and clean-environment evidence.
The build TOC remains `AUXILIARY_BUILD_TOC_ONLY`.

```text
audit_json_sha256=a63c0fefa7c7aba37685ccb65bec7fd605448e42873d5d8252975a82ea9269e5
source_tool_inventory_count=52
policy_preimage_count=42
static_bindings_digest=e11984ea6cd5146a862b9065a22063cf80d3eb8aa7ce92b6929450cafa7769d5
candidate_exact_bytes_sha256=d98a0013e4c4b3c219fcd0d53e66c5c99dcd3c4fcea6d823d54bf1e040e0c258
binding_schema_exact_bytes_sha256=17cb07cb672dfccc0c5fe0c3fffd91a82e63a392bbbc0660d09b047dce8ad5f1
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

M2-S3B is the next task. S3A does not rebuild the package or open physical M2,
participant collection, M3, distribution, deployment, or release.

## M2-S2E - Strict same-revision synthetic evidence reproduction

Status:
`M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`
as of `2026-09-01`.

M2-S2E verifies one S2D bundle, compares its environment binding with the
current source, and replays only the built-in preflight or nominal fixture in
an owned temporary root. Fresh same-revision preflight and nominal evidence
returned `EXACTLY_REPRODUCED`: whole bundle, observation, D1, artifact, and
integration digests matched after cleanup. Older valid S2D bundles classify
as `SOURCE_REVISION_MISMATCH` and do not enter replay.

Current RP2 tuple for 51 source/tool entries and 40 policy preimages:
`static_bindings_digest=38a17dcc4ea214a2d52ef2bb825e502bcf88d7dbf48ebc2f3758da93b6d2a585`,
`candidate_exact_bytes_sha256=15f3bcc27411b1534e6214d8818af70cf46076776af4ae73551d508d0f0f7119`,
`binding_schema_exact_bytes_sha256=abc494b96a3cc52eda57c43d677c83245736ab65ff923faa4e39524cf84f2dc5`.

```text
classification=EXACTLY_REPRODUCED
legacy_classification=SOURCE_REVISION_MISMATCH
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

This milestone is exact built-in synthetic determinism evidence only. It does
not open physical M2, camera/device access, participant collection, M3,
package inclusion, deployment, or release.

## M2-S2D - Synthetic evidence export and offline verification

Status:
`M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`
as of `2026-09-01`.

Terminal persisted synthetic runs can be downloaded from the authenticated
monitor origin as bounded, complete minimized canonical JSON bundles. The
bundle cross-binds the run receipt, full persisted artifact, D1 receipt,
observation digest, and closed authority ceiling. A separate one-file CLI
verifies the bundle offline. The server keeps no export archive.

Source-runtime evidence covered both `PREFLIGHT_60S` and `NOMINAL_20M` bundle
downloads and offline verification. The exam origin returned 404, the browser
console was clean, and shutdown removed the owned root and listeners.

Current RP2 tuple for 47 source/tool entries and 36 policy preimages:
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

M2-S2D is not physical/device evidence, `D1_GO`, model-performance evidence,
research readiness, collection authority, package inclusion, deployment, or
release.

## M2-S2C - Synthetic reviewer API/UI wiring

Status:
`M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`
as of `2026-08-31`.

The authenticated monitor origin exposes two fixed source-only synthetic
actions through a single-flight service with an owned temporary workspace.
Headed Chromium verified both `PREFLIGHT_60S` and `NOMINAL_20M` as
`BACKEND_CONTRACT_PASS`; the exam origin returned 404 and shutdown removed the
temporary root and listeners. This evidence is `SIMULATED`.

Current RP2 tuple:
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

M2-S2C is not physical M2, device evidence, model-performance evidence,
research readiness, package inclusion, collection authority, deployment, or
release.

## M0 - Foundation and deterministic demo (HISTORICAL)

Status: `M0_LOCALLY_VERIFIED`.

This is a `HISTORICAL` M0 receipt. Source provenance, separate exam/monitor loopback origins, reviewer authentication, candidate pairing, session lifecycle, persisted deterministic demo replay, focused tests, frontend contracts, and packaging foundation were locally verified. Its evidence tuple includes executable SHA `30C191FFBC8729736377B8800ADA80459187504772E30B77E7FD0DDCBFD97F27`, identical detached/bundled manifest SHA `071849B5AB94C60D90F184282C66B6FBBC5FE133AB888304DAAD22DC6D5CFCAC`, 182 manifest entries with 0 forbidden items, and 5/5 dist/package match. M0 smoke and packaged Chromium browser/runtime checks passed; G0 and manifest verification were `PASS`, not pending. Sol visual advisory was `ACCEPT`; user visual acceptance remained `PENDING`.

M0 remains local evidence only. Clean-machine execution, signing, deployment, production, physical two-display/device behavior, other browsers, and external acceptance are `UNVERIFIED`.

## M1 - Session and exam persistence (HISTORICAL)

Status: `M1_LOCALLY_VERIFIED` as of `2026-08-25`.

This is a `HISTORICAL` M1 receipt. M1 added explicit SQLite WAL persistence, migration/schema integrity, native storage-root configuration, consent and retention receipts, restart recovery, idempotency, typed readiness gates, and participant-wide withdrawal/lineage governance. M0 remains the default in-memory runtime; M1 requires explicit `PDU_RUNTIME_MODE=m1` and native config under `%LOCALAPPDATA%\PDUExamObserver\config.v1.json`.

M1 exit evidence is `OBSERVED`: 73 Python tests; Ruff; mypy for 14 files; frontend 9 files/57 tests plus typecheck, lint, and build; M0 and M1 smoke; 182 manifest entries/0 forbidden; 5/5 dist/package match; exact executable and both-manifest hashes above; packaged browser/runtime `PASS`; Sol visual advisory `ACCEPT`; and zero remaining processes/listeners. Readiness remains fail-closed and research cannot enter `RECORDING`.

M1 does not claim encryption, ACL enforcement, institutional approval, real participant data, camera capture, model performance, release, or production. Encryption/ACL `VERIFIED` values are smoke test attestations only.

## GOV-P0 - Zero-cost pre-collection governance

Status:
`GOV_P0_STATIC_VERIFIED_EXTERNAL_GATES_PENDING_B0_3_DEFERRED_NO_COLLECTION_AUTHORITY`
as of `2026-08-30`.

The source register, draft labelbook and segment policy, precommitted scenario
schedule, external-gate template, Vietnamese participant drafts, withdrawal
rehearsal, reporting template, and borrowed-custodian checklist are
deterministically hash-bound. This milestone is documentation/static evidence
only. It does not open M2/M3, authorize collection, or waive B0.3; operational
B0.3 waits for a suitable borrowed custodian plus fresh exact authority.

## GOV-P1 - Synthetic withdrawal and deletion rehearsal (HISTORICAL)

Status:
`GOV_P1_SYNTHETIC_REHEARSAL_VERIFIED_PRODUCTION_RECONCILER_UNIMPLEMENTED_EXTERNAL_APPROVAL_PENDING_NO_COLLECTION_AUTHORITY`
as of `2026-08-30`.

This `HISTORICAL` receipt is superseded by M1-R1 for current implementation
and package claims. The existing M1 participant-wide withdrawal contract was exercised with one
synthetic participant, two sessions, and four synthetic artifacts in a
runner-owned temporary root. Exact manifest-owned deletion and sentinel
preservation passed, but the four M1 tasks remain `PENDING`: production
reconciliation is deliberately unimplemented. The accompanying Vietnamese
dossier is draft-only and no external decision or collection authority exists.
Reviewed-source pinning, live-source path binding, atomic generated outputs,
pre-unlink identity recheck, and sanitized CLI failure behavior are locally
verified. Hostile same-account race resistance remains explicitly false and is
not a GOV-P1 exit claim.

## GOV-P5A - Advisor-first human-confirmation request pack

Status:
`GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`
as of `2026-08-31`.

The deterministic pack asks only `HC-01` current-cycle late-submission
acceptance and `HC-02` the applicable human-subjects/ethics review route.
Audience is `FACULTY_ADVISOR_FIRST`; `human_response_status=PENDING`,
`external_transmission_authorized=false`, and `submission_state=NOT_SUBMITTED`.
Manifest SHA-256 is
`4c5443ae46972b5ec56d2229700580bd0a6e7c1be61ef79d019c055314962fa8`.

The blank response template is not response evidence. Blocking gates
`CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED` and
`HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED` remain open. Residual
`HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED` remains binding; GOV-P5B is a
separate future task.

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

GOV-P5A opens no email, upload, submission, response, participant, camera,
collection, M2, B0.3, real-deletion, deployment, or release gate.

## GOV-P4 - Institutional route source verification

Status:
`GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_UNCONFIRMED_APPROVAL_NOT_ISSUED`
as of `2026-08-31`.

Public primary sources from Trường Đại học Phạm Văn Đồng establish the route
from Hội đồng khoa, through forms 1-6 and the research-management office, to a
Rector-issued approval decision. GOV-P4 records
`adv_02_status=SATISFIED_BY_PUBLIC_PRIMARY_SOURCES` and
`institutional_route_status=SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED`.
Manifest SHA-256 is
`f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531`.

The public route does not resolve separate human-subjects/ethics review for
webcam data, and the current-cycle registration deadline has passed. Residuals
`HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED` and
`CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION` remain open.
`institutional_approval_status=NOT_ISSUED` and
`submission_state=NOT_SUBMITTED` remain binding.

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

GOV-P4 opens no external submission, participant, camera, collection, M2,
B0.3, real-deletion, deployment, or release gate.

## GOV-P3 - Advisor verbal decision receipt

Status:
`GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_READY_FOR_INSTITUTIONAL_ROUTING`
as of `2026-08-31`.

The user reports verbal faculty-advisor approval. GOV-P3 records only `ADV-01`
as `SATISFIED_BY_USER_REPORT_UNVERIFIED`, with outcome
`READY_FOR_INSTITUTIONAL_ROUTING`; it does not represent the report as written
or independently verified evidence. Manifest SHA-256 is
`7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605`.

`ADV-02` remains `PENDING_EXTERNAL_DECISION`. The next governance action is to
identify the approving unit, official template, and required signature roles.
`institutional_approval_status=NOT_ISSUED`,
`submission_state=NOT_SUBMITTED`, and residual
`ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY` remain binding.

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

GOV-P3 opens no participant, camera, collection, M2, B0.3, institutional
approval, real-deletion, deployment, or release gate.

## GOV-P2 - Advisor-first institutional submission dossier

Status:
`GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW`
as of `2026-08-31`.

The deterministic Vietnamese source dossier is locally complete for
`FACULTY_ADVISOR_FIRST`. Manifest SHA-256 is
`1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e`.
Four annexes exactly snapshot reviewed GOV-P0/GOV-P1 drafts. It remains
`submission_state=NOT_SUBMITTED` and `PENDING_EXTERNAL_REVIEW`; no advisor or
institutional decision exists.

Correction A retains GOV-P1 byte-identically as historical evidence and records
`CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT`. Its live checker
mismatch against later M1-R1 source is disclosed, not regenerated away.

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

GOV-P2 opens no participant, camera, M2, B0.3, approval, submission, signing,
deployment, release, or real-deletion gate.

## M1-R1 - Production withdrawal reconciler

Status: `M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY` as of
`2026-08-30`.

`OBSERVED`: the current local package contains 186 files, passes the 8/8
packaging gate, and has executable SHA-256
`EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF`
with identical bundled/detached manifest SHA-256
`9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256`.
The packaged acceptance receipt remains 843/843 Python tests and 58/58
frontend tests. The later governance-only closure adds three documentation
consistency tests, making the current source-suite collection 846 tests without
a package rebuild. Current source evidence is
`M1_R1_SOURCE_SUITE_846_OF_846_PASS`: one fresh full invocation passed
846/846. Earlier two full invocations each exposed one distinct load-sensitive
timeout, and both affected tests subsequently passed alone and in bounded
repetition. Those earlier observations remain historical and are not claimed
fixed. The package was not rebuilt.

`OBSERVED`: the source reconciler, fail-closed normal route, synthetic-only
rehearsal, challenge revocation, and desktop/390x844 technical runtime evidence
are locally verified. Technical visual evidence is not user aesthetic
approval, clean-machine portability, or permission to operate on real data.
In the packaged synthetic flow, challenge issue returned 201, normal execution
returned 403 `AUTHORITY_NOT_ISSUED`, logout revoked both challenges, both
targets remained pending, the artifact bytes were unchanged, and no execution
or run record was created.

The binding authority ceiling is:

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

M1-R1 does not open M2. Real deletion, external attestation, participant data,
camera use, signing, distribution, deployment, release, and institutional
approval remain unauthorized or unverified.

## M2-S2B - Synthetic nominal 20-minute integration

Status:
`M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

The shared private engine preserves the M2-S2A public API and adds a fixed
`run_kind=NOMINAL_20M` wrapper. The synthetic run processes exactly 18,077
deterministic zero-pose frames using accelerated timestamps for a requested
1,200 seconds; it does not wait 20 physical minutes or access a device. Valid
PASS and exact technical `NO_GO` receipts may be persisted for audit, while
corrupt inputs, forged receipts, persistence faults, and withdrawal races must
remain `NOT_PERSISTED` without fabricated artifact fields.

Current RP2 tuple:

```text
static_bindings_digest=6e84eb0699658c61efd335a175a2abb4470f37afeaff131d94cdce332640fa43
candidate_exact_bytes_sha256=99365851f4fbad6f78c9b94c30eaef362b281c1a901cc15b40f2c5707e9fd771
binding_schema_exact_bytes_sha256=1bec3a9e9747136f01e43dd76de62f5b622eb00540714ee4c1639ee470edcb2d
```

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

This milestone is synthetic failure-routing evidence only. It is not physical
M2, `D1_GO`, model-performance evidence, research readiness, or collection
authority. The release package was not rebuilt and does not contain M2-S2B.

## M2-S2A - Synthetic system integration core

Status:
`M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`
as of `2026-08-31`.

The synthetic-only vertical slice binds `SyntheticRunner`, the D1 aggregate
evaluator, a canonical receipt, and `M2PersistenceStore`. It processes 977
deterministic zero-pose frames using accelerated timestamps; it does not wait
60 physical seconds. Valid `BACKEND_CONTRACT_PASS` and `NO_GO` receipts are
persisted for audit, with artifact validity separated from D1 outcome.

Current RP2 source/static tuple is
`static_bindings_digest=84694c545120b69cebaa8d64fb40c3c1d574afcecd69126f1238d5e285a7a22f`,
`candidate_exact_bytes_sha256=cd89fad5be9e804fcdf56b87f8edd517fe15be74de0e1c0dcd01d0e10bb16bec`,
and
`binding_schema_exact_bytes_sha256=fcc3ae40caf53e2afd3f67b1f0739ce863e4a6780673e6de0afd904750571d94`.
At task start, Git existed and the baseline was clean `main` at `7912bd9`.

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

This milestone is local source/runtime evidence only. It does not open physical
M2, camera/device access, participant collection, M3, package rebuild,
deployment, or release.

## M2 - Capture and pose pipeline

Status: unopened. No current authorization for webcam enumeration, capture, pose processing, FFmpeg recording, or participant collection.

The earlier `M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED` tuple is retained as
historical static authority evidence:
`static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`,
`candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`,
and
`binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`.
M2-S2A supersedes its current source inventory with the tuple recorded above
but issues no authority. Bootstrap is unprovisioned, fresh A0 is not issued,
A1 is not opened, and X0 is blocked.

Exit requires an actual reference-machine run and induced camera, encoder, disk, and inference failures.

## M3 - Labels, review, and rule baseline

Status: unopened. Add only after M2 evidence and authorization.

## M4 - Pilot and protocol freeze

Status: unopened. Requires consenting adult pilot participants, approved protocol/storage/retention, and human review.

## M5 - Confirmatory and demo corpora

Status: unopened. Requires participant-disjoint, consented confirmatory data and separate synthetic demo provenance.

## M6 - Training and model import

Status: unopened. Requires approved data splits, calibration/abstention gates, reproducible training, and model provenance.

## M7 - Confirmatory evaluation and trial release

Status: unopened. Requires frozen evaluation, physical two-monitor acceptance, clean Windows verification, signing/release gates, and external research decisions.

No milestone automatically permits a production, disciplinary, or generalization claim.
