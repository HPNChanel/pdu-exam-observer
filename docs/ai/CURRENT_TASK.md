# Current Task

Milestone: `M2-S3D - packaged S2D export and S2E reproduction round-trip`

Status:
`M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`

Updated: `2026-09-02`

## Active M2-S3D outcome

`M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`

`OBSERVED`: a new deterministic S3D candidate completed two independent
same-host cycles. Each cycle ran preflight and nominal synthetic jobs, exported
two verified S2D bundles, and reproduced both through the same packaged
executable's closed stdin-only mode. All four reproductions were exact and the
two minimized projections were byte-identical.

```text
round_trip_receipt_sha256=4d8a862408aec0470d86b084f1abdc9baa323a3ee53cb57dfe780c3d6e2258ed
static_bindings_digest=034eb3e19f88377529f5ffc37c077938b42563a447d1d6e6a481c1b635cbf607
candidate_exact_bytes_sha256=ced85d39533de902da652c4a7f56ea85eaf4891a5d8b27946badf8aebcae5c79
binding_schema_exact_bytes_sha256=7125de572f5a78b986a768b484315b818e1c630d10ada48ea31bd0915c300058
source_tool_inventory_count=64
policy_preimage_count=55
candidate_build_validation_sha256=432c906b2a32d84d5d82509d27cfa3882500657ce97e544e7fb71513b0754b94
candidate_executable_sha256=9d9aabe6b6176fabb1db423924d8c27a8ee9478d302b421680dc8bfc989c66aa
candidate_manifest_sha256=8702963dddd8b9d2761120fce8875d9fd181177eb15f1576e72e7354ad3ae216
candidate_tree_sha256=64686518c09679f98b6f3c01805535ca9aad50413781424a08020c2460d017e1
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

This is same-host synthetic package evidence only. Clean-machine portability,
physical camera/device evidence, participant collection, distribution and
release authority remain unverified. The next package task is M2-S3E clean
environment portability; it is not opened by this receipt.

`OBSERVED`: S3D focused tests `10 passed`, RP2 artifact tests `6 passed`,
governance `3 passed`, research `69 passed`, collection `976 tests`, Ruff and
strict mypy PASS, and one full-suite invocation returned
`976 passed in 226.47s`.

---

Milestone: `M2-S3C - packaged synthetic runtime smoke`

Status:
`M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`

Updated: `2026-09-02`

## Active M2-S3C outcome

`M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`

`OBSERVED`: the corrected one-folder candidate ran in exactly two independent
process invocations on the build host. Each invocation completed built-in
`PREFLIGHT_60S` (977 observations) and `NOMINAL_20M` (18,077 observations)
with `BACKEND_CONTRACT_PASS`; the minimized projections were byte-identical.
Candidate bytes, manifests, processes, listeners, and owned temporary roots
were checked before closure.

```text
packaged_smoke_receipt_sha256=479aa2e364216a8f4560fbf98a31a6935829d847dfbace65f7c66fae8778bbb7
package_integration_receipt_sha256=bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd
candidate_source_static_bindings_digest=a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f
candidate_source_candidate_exact_bytes_sha256=a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639
candidate_source_binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca
static_bindings_digest=721783d4d89eb55a599a1505574741d9e631d66a5ceee7e443f4469058104a8a
candidate_exact_bytes_sha256=ca5e80e847e11f93f8a8da33ddc743b1f106a50af864a7eb339194a1ef86929a
binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca
source_tool_inventory_count=58
policy_preimage_count=50
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

This is same-host synthetic runtime evidence only. It does not establish
same-host portability, clean-machine portability, camera/device behavior,
participant collection, distribution readiness, signing, or release authority.
The next planned package task is M2-S3D packaged S2D export and S2E
reproduction round-trip; it remains unopened.

`OBSERVED`: S3B focused tests `8 passed`, S3C focused tests `8 passed`, RP2
artifact tests `6 passed`, governance `3 passed`, research `69 passed`, Ruff
PASS, strict mypy PASS, both historical and candidate manifests verified,
collection `966 tests`, and one clean full invocation returned
`966 passed in 170.26s`.

---

Milestone: `M2-S3B - deterministic current-source package integration`

Status:
`M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY`

Updated: `2026-09-01`

## Active M2-S3B outcome

`M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY`

`USER_STATED`: the user approved Direction A and authorized the S3B plan in
the existing task-scoped dirty checkout.

`OBSERVED`: two isolated builds from the same pinned source/toolchain produced
byte-identical candidate payload trees. Recursive executable/PYZ inspection
contains all 14 required application and S2A-S2E runtime modules, the packaged frontend equals the
isolated frontend build, and the candidate README preserves the synthetic and
no-authority boundary. This S3B receipt is static; runtime execution is
attested separately by S3C.

```text
package_integration_receipt_sha256=bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd
source_tool_inventory_count=58
policy_preimage_count=50
static_bindings_digest=a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f
candidate_exact_bytes_sha256=a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639
binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca
candidate_tree_sha256=29a0d7749e8069978f54d9c0087261fe709da3c016c73acca9cffb5034f8c37e
candidate_manifest_sha256=e0b279a1e667cc39e5c5f62d6aa169e6973c2c2f957f78118f86f9de972e620f
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

For this candidate only, GAP-01, GAP-02, and GAP-07 are
`CLOSED_FOR_CURRENT_CANDIDATE`. GAP-03, GAP-04, GAP-05, GAP-06, and GAP-08
remain `OPEN`. S3C is the next task and is the first task permitted to run the
candidate for packaged synthetic smoke. No signing, portability, distribution,
commit, push, deployment, or release authority is issued.

`OBSERVED`: final integrated gates returned S3B `8 passed`, S3C `8 passed`,
RP2 artifacts `6 passed`, governance `3 passed`, research `69 passed`, and one
full invocation `966 passed in 170.26s`. Both manifests verified; read-only
candidate checks were byte-identical; `S3B_TEMP_ROOT_COUNT=0`, `PDU_PROCESS_COUNT=0`,
and `PDU_LISTENER_COUNT=0`.

---

Milestone: `M2-S3A - current-source package gap audit`

Status:
`M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY`

Updated: `2026-09-01`

## Active M2-S3A outcome

`USER_STATED`: the user approved Direction A and authorized the audit-only
S3A plan in the existing task-scoped dirty checkout.

`OBSERVED`: the historical package remains manifest-valid but is classified
`HISTORICAL_NOT_CURRENT_SOURCE`. The canonical audit records eight open gaps
and preserves the historical executable, manifests, packaged frontend,
current observed frontend dist, build TOC, packaging scripts/spec, and README
bytes. No package rebuild was started.

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

Git metadata exists. The S2A task began from clean `main` at `7912bd9`; the
current checkout remains task-scoped and dirty. S3A does not authorize package
integration, physical M2, participant collection, M3, commit, push,
deployment, signing, distribution, or release.

---

Milestone: `M2-S2E - strict same-revision synthetic evidence reproduction`

Status:
`M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`

Updated: `2026-09-01`

## Retained M2-S2E outcome

`USER_STATED`: the user approved Direction A and instructed implementation of
the decision-complete M2-S2E plan in the existing task-scoped dirty checkout.

`OBSERVED`: fresh `PREFLIGHT_60S` and `NOMINAL_20M` S2D bundles passed strict
same-revision replay from new owned temporary roots with
`EXACTLY_REPRODUCED`. Whole-bundle, observation, D1, artifact, and integration
digests matched. A source-binding mismatch stops before replay; semantic and
operational failures cannot publish exact success. The one-file CLI is
canonical, bounded, path-sanitized, and creates no output archive.

Current RP2 tuple for 51 source/tool entries and 40 policy preimages:

```text
static_bindings_digest=38a17dcc4ea214a2d52ef2bb825e502bcf88d7dbf48ebc2f3758da93b6d2a585
candidate_exact_bytes_sha256=15f3bcc27411b1534e6214d8818af70cf46076776af4ae73551d508d0f0f7119
binding_schema_exact_bytes_sha256=abc494b96a3cc52eda57c43d677c83245736ab65ff923faa4e39524cf84f2dc5
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

Git remains the task-scoped dirty `main` checkout rooted at `7912bd9`. No
camera, device enumeration, participant contact, remote transmission, real
deletion, package rebuild, deployment, commit, push, M3, or release is claimed.

---

Milestone: `M2-S2D - synthetic evidence export and offline verification`

Status:
`M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`

Updated: `2026-09-01`

## Active M2-S2D outcome

`USER_STATED`: the user approved Direction A and instructed implementation of
the full M2-S2D plan in the current task-scoped dirty checkout.

`OBSERVED`: terminal persisted `PREFLIGHT_60S` and `NOMINAL_20M` source runs
were exported as complete minimized canonical JSON bundles through the
authenticated monitor origin. Both downloaded files passed the one-file
offline verifier. The exam origin returned 404; browser console errors and
warnings were 0/0; shutdown left temp roots, PDU processes, and listeners at
0/0/0. Export is download-only and creates no server archive.

Current RP2 tuple for 47 source/tool entries and 36 policy preimages:

```text
static_bindings_digest=7204b1d53dbac8d5fd7f057c9b5a63e3fde10ec4c68111e4fa2b0ef9312880d3
candidate_exact_bytes_sha256=46221d85c38df2e44b62d688ff5a162519f215078462ef6f54bc47b65c75abd0
binding_schema_exact_bytes_sha256=23d742592c018343767ff8b670e1a253f7e2e2cbdf1a91c4829e8dc7bf30a9d3
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

`OBSERVED at task start`: Git metadata exists; the baseline was clean `main`
at `7912bd9`. Current uncommitted changes remain task-scoped. No camera, audio,
device enumeration, participant contact, export to a remote service, real
deletion, package rebuild, deployment, commit, push, or release is claimed.
The historical package does not contain M2-S2D.

---

Milestone: `M2-S2C - synthetic reviewer API/UI wiring`

Status:
`M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`

Updated: `2026-08-31`

## Active M2-S2C outcome

`USER_STATED`: the user approved Direction A and instructed implementation
of the full M2-S2C plan in the current dirty checkout.

`OBSERVED`: the authenticated monitor source runtime exposes exactly two
fixed synthetic actions, `PREFLIGHT_60S` and `NOMINAL_20M`, through a
single-flight service-owned temporary M2 workspace. Both runs reached
`BACKEND_CONTRACT_PASS` in headed Chromium. The exam origin returned 404 and
shutdown left `TEMP_ROOT_COUNT=0`, `PDU_PROCESS_COUNT=0`, and
`PDU_LISTENER_COUNT=0`.

Current RP2 tuple for 44 source/tool entries and 32 policy preimages:

```text
static_bindings_digest=d54ec5277d9713128e03a0eaae787c5ff6fd04ee6e48fee3654f87655d847248
candidate_exact_bytes_sha256=582bb50f0ca2118937f7d79d7dd8a0bff3d43d72a58ae540c27c41ccddcabd71
binding_schema_exact_bytes_sha256=9c460d3fb874faea444ab97a3c85bc70c37d25f6ea1ced5be4f2dbec20092387
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

No camera, audio, device enumeration, participant contact, consent creation,
export, real deletion, package rebuild, submission, deployment, or release was
performed. The package does not contain M2-S2C.

Milestone: `M2-S2B - synthetic nominal 20-minute run`

Status: `M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`

Updated: `2026-08-31`

## Active M2-S2B outcome

`USER_STATED`: the user approved the M2-S2B synthetic nominal design and
implementation plan. The authorized scope is repository code, deterministic
fixtures, temporary synthetic persistence, tests, RP2 source/static
reconciliation, and current-ledger updates only.

`OBSERVED`: the shared private integration engine preserves the public M2-S2A
contract and adds a caller-locked `run_kind=NOMINAL_20M` path. It processes
exactly 18,077 deterministic zero-pose frames with accelerated timestamps,
`requested_duration_seconds=1200`, and no physical wait. Valid
`BACKEND_CONTRACT_PASS` and exact technical `NO_GO` receipts are persisted for
audit; corrupt inputs, forged receipts, persistence faults, and withdrawal
races fail without a fabricated artifact claim. The evidence remains
`evidence_kind=SIMULATED` and `package_contains_integration=false`.

Current RP2 source/static tuple for the 31-entry source/tool inventory and 28
policy preimages:

```text
static_bindings_digest=6e84eb0699658c61efd335a175a2abb4470f37afeaff131d94cdce332640fa43
candidate_exact_bytes_sha256=99365851f4fbad6f78c9b94c30eaef362b281c1a901cc15b40f2c5707e9fd771
binding_schema_exact_bytes_sha256=1bec3a9e9747136f01e43dd76de62f5b622eb00540714ee4c1639ee470edcb2d
```

`OBSERVED at task start`: Git metadata exists; the baseline was clean `main`
at `7912bd9`. Current uncommitted changes are task-scoped. No commit, push,
package rebuild, deployment, or release is claimed.

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

No camera, audio, device enumeration, participant contact, export, real
deletion, external submission, provisioning, package rebuild, or deployment
was performed. A synthetic nominal PASS is not physical M2, `D1_GO`, model
performance evidence, research readiness, or collection authority.

---

## Retained M2-S2A outcome

Status:
`M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`.

`USER_STATED`: the user approved the M2-S2A synthetic-only design and
implementation plan. The authorized scope is repository code, deterministic
fixtures, a temporary local smoke store, tests, RP2 source/static
reconciliation, and current-ledger updates only.

`OBSERVED`: `SyntheticRunner -> D1 aggregate evaluator -> canonical synthetic
preflight receipt -> M2PersistenceStore` is locally exercised with 977
zero-pose fixture frames and accelerated monotonic timestamps. Both semantic
`BACKEND_CONTRACT_PASS` and `NO_GO` receipts can be persisted for audit while
artifact validity remains separate from D1 outcome. The no-argument smoke ran
twice with exit 0, empty stderr, byte-identical canonical stdout,
`device_gate_decision=UNVERIFIED`, `d1_go=false`, and temp-root cleanup.

Current RP2 source/static tuple:

```text
static_bindings_digest=84694c545120b69cebaa8d64fb40c3c1d574afcecd69126f1238d5e285a7a22f
candidate_exact_bytes_sha256=cd89fad5be9e804fcdf56b87f8edd517fe15be74de0e1c0dcd01d0e10bb16bec
binding_schema_exact_bytes_sha256=fcc3ae40caf53e2afd3f67b1f0739ce863e4a6780673e6de0afd904750571d94
```

`OBSERVED at task start`: Git metadata exists; the baseline was clean `main`
at `7912bd9`. Current uncommitted changes are task-scoped. No commit, push,
package rebuild, deployment, or release is claimed.

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

No camera, audio, device enumeration, participant contact, export, real
deletion, external submission, provisioning, package rebuild, or deployment
was performed. Physical M2 and participant collection remain unopened.

---

## Retained GOV-P5A outcome

Status:
`GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`.

`USER_STATED`: the user approved the GOV-P5A design and implementation plan.
Authorized work is repository-only request material, deterministic validation,
tests, and governance reconciliation. It does not authorize transmission or a
response claim.

`OBSERVED`: the closed pack asks only `HC-01` current-cycle late-submission
acceptance and `HC-02` human-subjects/ethics review routing. Audience is
`FACULTY_ADVISOR_FIRST`; `human_response_status=PENDING`,
`external_transmission_authorized=false`, and `submission_state=NOT_SUBMITTED`.
Manifest SHA-256 is
`4c5443ae46972b5ec56d2229700580bd0a6e7c1be61ef79d019c055314962fa8`.

The pack contains an unfilled template, not evidence of a response. Blocking
gates `CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED` and
`HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED` remain open. Residual
`HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED` is binding; GOV-P5B has not opened.

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

No email, upload, external submission, participant contact, camera, M2/B0.3,
provisioning, signing, real deletion, package rebuild, deployment, or release
was performed.

Pack root:
`research/institutional_submission/human_confirmation_request/v1/`.

---

Milestone: `GOV-P4 - institutional route source verification`

Status: `GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_UNCONFIRMED_APPROVAL_NOT_ISSUED`

Updated: `2026-08-31`

## Active GOV-P4 outcome

`SOURCE_VERIFIED`: the canonical proposal identifies Trường Đại học Phạm Văn
Đồng and Khoa Công nghệ thông tin. Current public primary sources from the
university identify the student-research route: Hội đồng khoa reviews the
proposal; the faculty forwards forms 1-6 to the research-management office;
that office advises the Rector; and the Rector issues the approval decision.
Students begin only after that decision.

`OBSERVED`: GOV-P4 records
`adv_02_status=SATISFIED_BY_PUBLIC_PRIMARY_SOURCES` and
`institutional_route_status=SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED`.
Manifest SHA-256 is
`f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531`.
The source register pins exact downloaded bytes for the 2022 regulation,
2026-2027 notice, and 2026 student form set. GOV-P2 and GOV-P3 remain
byte-identical.

`UNVERIFIED`: the public sources do not determine whether this webcam study
requires a separate human-subjects/ethics review. The 2026-2027 registration
deadline ended on `2026-08-29`; late acceptance is not established.
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

Current residuals:
`ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY`,
`CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION`, and
`HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED`.

Pack root: `research/institutional_submission/route_discovery/v1/`.

---

Milestone: `GOV-P3 - advisor verbal decision receipt`

Status: `GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_READY_FOR_INSTITUTIONAL_ROUTING`

Updated: `2026-08-31`

## Active GOV-P3 outcome

`USER_STATED`: the user reports that the faculty advisor verbally approved the
GOV-P2 dossier. No written message, signature, independent witness, advisor
identity, or exact advisor decision date was supplied to the repository.

`OBSERVED`: the versioned GOV-P3 receipt records only `ADV-01` as
`SATISFIED_BY_USER_REPORT_UNVERIFIED`, with advisor outcome
`READY_FOR_INSTITUTIONAL_ROUTING`. Evidence mode is
`VERBAL_CONFIRMATION_REPORTED_BY_USER`; classification is
`USER_STATED_UNVERIFIED`. Manifest SHA-256 is
`7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605`.
GOV-P2 v1 remains byte-identical.

`UNVERIFIED`: `ADV-02` institutional route identification remains
`PENDING_EXTERNAL_DECISION`; `institutional_approval_status=NOT_ISSUED` and
`submission_state=NOT_SUBMITTED`. The user-stated verbal decision is not an
institutional approval and does not authorize participant contact, camera use,
collection, execution, or real deletion.

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

Current residual: `ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY`.

Receipt root:
`research/institutional_submission/advisor_decision/v1/`.

---

Milestone: `GOV-P2 - advisor-first institutional submission dossier`

Status: `GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW`

Updated: `2026-08-31`

## Active GOV-P2 outcome

`USER_STATED`: the user approved direction A, its full specification/plan, and
Correction A after baseline evidence showed that immutable GOV-P1 pins an older
M1 source than current M1-R1. GOV-P1 was not rebuilt or rewritten.

`OBSERVED`: the deterministic dossier at
`research/institutional_submission/v1/` is locally structure-validated for
`FACULTY_ADVISOR_FIRST`; `submission_state=NOT_SUBMITTED` and review remains
`PENDING_EXTERNAL_REVIEW`. Manifest SHA-256 is
`1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e`.
Four annexes are byte-identical GOV-P0/GOV-P1 snapshots. This is not an advisor
decision, institutional approval, invitation, or collection authority.

`OBSERVED`: historical GOV-P1 bytes remain intact. Residual
`CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT` records that the old
receipt pins M1 SHA-256
`1d28ed877573e99d928516bd8d76490e845a5a030ed23048d6f2931f38e5c67e`,
while current M1-R1 source differs. Its live checker therefore retains the
expected `MANIFEST_MISMATCH`; this is disclosed, not fixed or hidden.

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

No camera, participant, M2, B0.3, provisioning, A0/A1, signing, real deletion,
network submission, package rebuild, deployment, or release is authorized.

Controlling design:
`docs/superpowers/specs/2026-08-31-gov-p2-institutional-submission-dossier-design.md`.

Controlling plan:
`docs/superpowers/plans/2026-08-31-gov-p2-institutional-submission-dossier-plan.md`.

---

Milestone: `M1-R1 - production withdrawal reconciler, synthetic-only local verification`

Status: `M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY`

Updated: `2026-08-30`

## Active M1-R1 outcome

`USER_STATED`: on `2026-08-30`, the user approved the corrected M1-R1 full
specification, threat model, migration design, detailed plan, and requested
implementation.

`USER_STATED`: on `2026-08-30`, the user approved the bounded TM-17 design:
retain wall time for audit, enforce reviewer-bearer and challenge TTLs with
process-monotonic elapsed time, and expire issued challenges when the
confirmation service starts again. This approval authorizes source, tests, and
documentation only; it adds no migration, real deletion, participant, camera,
packaging, deployment, or release authority.

`USER_STATED`: on `2026-08-30`, the user then requested the next task, which
authorized a local generated-bundle rebuild and packaged runtime/visual
acceptance on a fresh synthetic-only root. It did not authorize signing, ZIP
publication, deployment, real deletion, external attestation, camera work, or
participant collection.

`OBSERVED`: the TM-17 follow-up is implemented from an unchanged canonical proposal hash
`2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`
and fresh latest-revision evidence is recorded in
`docs/ai/M1_R1_VERIFICATION.md`: 137 focused backend tests and the final
843-test Python suite pass; 58 frontend tests, typecheck, lint, and production
build pass; Ruff passes over current source and the changed packaging test;
strict mypy passes 37 source files. Current-revision independent review
first returned `NO-GO`, the concrete Important findings were reproduced and
remediated by TDD, and scoped re-review returned `APPROVE_SOURCE_ONLY` with no
unresolved Critical or Important finding. There is no Git metadata in this
workspace, so no Git/release claim is made.

`USER_STATED`: the only destructive-path exercise authorized by this plan is
one no-path `rehearse-r1` invocation over a runner-created
`%TEMP%\pdu-m1r1-rehearsal-*` synthetic root. The CLI regression verifies this
bounded path and cleanup. Normal migration apply,
real-root reconciliation/deletion, external attestation, participant/camera,
M2/M3, deployment, publishing, and release are not authorized.
`production_reconciler_source_implemented=true`, while
`production_reconciler_implemented=false`,
`production_reconciler_real_storage_verified=false`, and
`authority_status=AUTHORITY_NOT_ISSUED` remain binding.

`OBSERVED`: the current revision was rebuilt as a local PyInstaller bundle and
the packaged monitor was exercised at desktop and 390x844 on deterministic
synthetic data. Step-up returned `201`; normal execution returned the binding
`403 AUTHORITY_NOT_ISSUED`; logout revoked both challenges, cleared the PIN and
reviewer session storage, and left the artifact hash, both pending targets, and
zero execution/run records unchanged. M0 and M1 packaged smokes, the 8-test
packaging gate, manifest verification, screenshots, and sanitized runtime logs
are recorded in
`output/runtime/m1-r1-tm17-packaged-acceptance/PACKAGED_RUNTIME_ACCEPTANCE.md`.

`OBSERVED`: M1-R1 governance closure reconciles the current roadmap,
acceptance, quality, risk, task, and verification ledgers without changing
runtime source or rebuilding the package. The immutable proposal SHA-256 is
`2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
The accepted 186-file package retains executable SHA-256
`EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF`
and identical bundled/detached manifest SHA-256
`9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256`.
Its receipt remains 843/843 Python tests, 58/58 frontend tests, and packaging
8/8. Three governance-only consistency tests make the current collection 846
tests; they pass 3/3. Current source evidence is
`M1_R1_SOURCE_SUITE_846_OF_846_PASS`: one fresh full invocation passed
846/846. Earlier two full invocations each produced one different
load-sensitive timeout; the affected tests later passed alone and in bounded
repetition. Those observations remain historical and are not claimed fixed.
The package was not rebuilt, and the later source evidence is not
retroactively assigned to it.

The current authority ceiling remains binding:

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

`UNVERIFIED`: multi-process callback behavior, hostile live NTFS race semantics,
clean-machine portability, real storage, external deletion, and
human-attestation truth remain unverified. Technical visual evidence is not
user aesthetic approval. This local packaged observation does not authorize
execution, signing, distribution, deployment, or release.

Controlling plan:
`docs/superpowers/plans/2026-08-30-m1-r1-production-withdrawal-reconciler-plan.md`.

Governance-closure plan:
`docs/superpowers/plans/2026-08-30-m1-r1-governance-closure-plan.md`.

Current determinism receipt:
`docs/ai/M1_R1_V1_DETERMINISM_RECEIPT.md`.

---

Milestone: `GOV-P1 - synthetic withdrawal and deletion rehearsal`

Status: `GOV_P1_SYNTHETIC_REHEARSAL_VERIFIED_PRODUCTION_RECONCILER_UNIMPLEMENTED_EXTERNAL_APPROVAL_PENDING_NO_COLLECTION_AUTHORITY`

Updated: `2026-08-30`

## Active outcome

`USER_STATED`: on `2026-08-30`, the user approved GOV-P1 direction A: an
isolated synthetic withdrawal/deletion rehearsal and institutional-review
dossier, with no production M1 schema/API change and no authority escalation.

`OBSERVED`: the runner exercised the existing M1 backend with one synthetic
participant, two retention-pending sessions, four manifest-owned synthetic
files, and two withdrawal requests. Both requests replayed one canonical
receipt; both sessions became terminal/collection-blocked; all four artifacts
became `INVALIDATED`; four production withdrawal tasks correctly remained
`PENDING`; late artifact/write creation was rejected; four owned files were
deleted; an out-of-manifest sentinel was preserved; and the runner-owned temp
root was disposed after SQLite closure. M1 has no export capability, so GOV-P1
records `NOT_IMPLEMENTED_IN_M1_NOT_EXERCISED` and makes no export-rejection
claim.

`OBSERVED`: the EthicsDataReceipt body SHA-256 is
`539405cdb0c5fd3745740cbd5c6727af9afdcc6008ee63622d997c34e0f50b97`;
the GOV-P1 manifest SHA-256 is
`76fe01de697f44ba82208bd40ce1f14eb9f4df993076c3984ff15906620aa9b4`.
This proves only the synthetic rehearsal contract. Production reconciliation,
institutional approval, consent issuance, retention/storage decisions, M2/M3,
B0.3, and all participant collection remain blocked. Every readiness,
collection, physical-camera, D1, and authority field remains false/unissued.

`OBSERVED`: independent security review first returned `NO-GO` for mutable
delete/output paths, self-sealing altered reviewed sources, and unexpected CLI
traceback disclosure. TDD remediation now rejects the original root and every
path reparse, rechecks file identity immediately before unlink, uses atomic
generated-leaf replacement, pins all three reviewed-source file hashes and the
canonical live-source paths, and collapses unexpected exceptions to bounded
`UNEXPECTED_FAILURE`. The receipt explicitly records
`concurrent_same_account_mutation_resistant=false`; retained native-handle
deletion remains outside this synthetic-only slice and is not claimed.

`OBSERVED`: the post-remediation independent security re-review is `APPROVE`
for the synthetic GOV-P1 slice only. Fresh verification passed 22 focused
GOV-P1 tests, 78 focused GOV-P1/GOV-P0/M1/RP2 tests, Ruff, strict mypy, both
GOV-P1 CLI checks, GOV-P0/RP2 checkers, and the full 770-test suite. This
approval does not change any external or collection gate.

## Historical M1-R1 design gate

`USER_STATED`: on `2026-08-30`, the user requested the full specification,
threat model, and migration design for the production withdrawal reconciler.

`HISTORICAL`: three documents were drafted under `docs/superpowers/specs/` with
status `DRAFT_FOR_USER_REVIEW` before approval: the full specification, its 20-item
threat register, and an explicit empty-precollection-only v1/v2-to-v3 additive
migration design. They select a durable plan/challenge/worker/receipt flow,
handle-bound Windows deletion, distinct external human attestation, exact
legacy fail-closed compatibility, and no automatic restart deletion.

`HISTORICAL`: an independent design security review initially returned
`NO_GO_DRAFT` for cross-kind completion, ambiguous schema-version naming, and
undefined fresh-authentication semantics. The current revision adds
kind-specific terminal constraints, composite participant/withdrawal/plan/
action/target binding, one typed challenge execution, persisted procedure
authority, a reviewer-PIN step-up of at most 120 seconds, and distinct
`receipt_schema_version=1` / `operational_ledger_version=3`. Exact R1 DDL parses
against current v1+v2, `foreign_key_check` is empty, discriminating mutation
probes reject the reviewed invalid pairings, and re-review returned
`APPROVE_DRAFT`. The user later approved the corrected source-only design and
implementation plan.

`HISTORICAL`: the documentation-only implementation prohibition was superseded
by source-only implementation authority. Normal migration execution and real-
data deletion remain unauthorized. All collection and M2/M3 physical/
participant boundaries remain unchanged.

`USER_STATED`: because no additional physical custodian device is available,
the user approved direction 1: defer operational B0.3 without weakening it and
complete every zero-cost pre-collection governance artifact that does not need
a camera, participant, institutional decision, or execution authority.

`OBSERVED`: GOV-P0 is implemented under `research/pre_collection/v1/` and
governed by `docs/spec/PRE_COLLECTION_GOVERNANCE.md`. The deterministic builder
and mutation suite validate the source register, draft labelbook, exact
6,000-ms window policy, scenario counts, external-gate template,
participant-facing drafts, reporting template, and non-authorizing borrowed-
custodian checklist. The generated manifest SHA-256 is
`c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025`.
This is static structure evidence only: `research_ready=false`,
`collection_authorized=false`, `participant_collection_authorized=false`,
`physical_camera_access_authorized=false`,
`authority_status=AUTHORITY_NOT_ISSUED`,
`device_gate_decision=UNVERIFIED`, and `d1_go=false` remain binding. B0.3 is
deferred for lack of a custodian; the inert kit remains unchanged.

`USER_STATED`: on `2026-08-29`, the user approved B0.3 direction A and the
detailed custodian-ceremony specification/plan. The approved current work may
materialize those documents and prepare a credential-free PowerShell/NCrypt
inert kit outside the checkout for static and safe-mode review. The user stated
that no custodian environment exists. This approval therefore does not permit
`-Mode Execute`, production key creation, bundle/signature creation, an
execution-authority artifact, bootstrap installation, signed A0, preparation,
A1, native/camera access, or retry.

`OBSERVED`: the B0.3 design and implementation plan are materialized at
`docs/superpowers/specs/2026-08-29-d1-n2-b0-3-custodian-ceremony-design.md`
and
`docs/superpowers/plans/2026-08-29-d1-n2-b0-3-custodian-ceremony-plan.md`.
The exact B0-R2 triple remains the non-authorizing baseline. The external inert
kit is now static/safe-mode verified and independent Sol/xhigh review returned
`APPROVE_INERT_KIT_ONLY`. Exact reviewed hashes are
`tool_sha256=ce02742fb57ea2d01d41bd60e9c63f528254f64977952e7e297108d8f7d848dc`,
`runbook_sha256=a294b6eeb8123a96f79de5b96bb5d23a4eaa257718555ff72166d16580f4077b`,
`kit_manifest_sha256=d59c1c402ba5be3da41c03accca708740cc1cb93cf6249683716354a5e852df2`,
and
`validation_sha256=8b8f1dfdec40e85d503c9730963245ca75f14194d730d69344173e5694b31474`.
No `Execute`, NCrypt/BCrypt, native, camera, FFmpeg, MediaPipe, installer,
preparation, or preflight path was invoked. No operational artifact exists.
Native CNG behavior, physical/dedicated/non-target custody, and concurrent
same-account reparse replacement remain `UNVERIFIED` or procedurally attested.

`USER_STATED`: on `2026-08-29`, the user approved the B0 source-only bootstrap
provisioning design and implementation plan. This permits closed bootstrap and
receipt contracts, fixed Windows readers, public-only BCrypt verification, a
separately gated one-shot installer source, production fail-closed wiring, tests,
RP2 regeneration, and independent static review. It does not authorize creating
or installing a production key/bootstrap/A0, invoking the operator installer or
production prepare/run wrappers, opening A1, or performing native/camera work.

`OBSERVED`: B0 implementation started with the production bootstrap still
`UNPROVISIONED`. The previously approved RP2 triple remains the current
non-authorizing baseline only until B0 changes its bound inventory; it cannot
authorize the B0 revision.

`OBSERVED`: the closed bootstrap/receipt contracts, public-only BCrypt P-256
verification, fixed bootstrap/A0 readers, retained bootstrap lifecycle, and A0
ordering/cleanup integration are implemented source-only. The focused B0 slice
passes 113 tests, scoped Ruff, and strict mypy for the five changed source
modules. No installer, operator CLI, production composition, RP2 regeneration,
or operational provisioning has been completed or invoked.

`OBSERVED`: an independent Sol/max architecture review returned `NO-GO` on the
approved receipt-finalization order before installer implementation. A final
receipt that asserts `cleanup_clean=true` cannot be written while its own
writer/verifier cleanup remains capable of failing; that is a cyclic
self-attestation and could expose runtime-acceptable final bytes after a close
failure. The smallest proposed B0-R1 correction stages the receipt in the fixed
partial leaf, closes every fallible resource first, then performs exactly one
same-directory no-replace write-through rename as the terminal publication
primitive. The receipt identity digest would bind the staged/final receipt
object, and open results would be explicitly tagged `OPENED`, `ABSENT`, or
`AMBIGUOUS`. Runtime would reject partial, asymmetric, ambiguous, or failed
states. At that checkpoint this material revision was `UNVERIFIED` and installer
work paused rather than implementing unapproved semantics; the following user
decision superseded that pause.

`USER_STATED`: on `2026-08-29`, the user approved option A and therefore the
material B0-R1 staged-receipt correction, including receipt-object identity,
tagged `OPENED`/`ABSENT`/`AMBIGUOUS` inspection results, clean closure of every
fallible resource before publication, and exactly one no-replace/write-through
terminal receipt rename. The existing threat-model exclusion for malicious
same-account whole-root replacement remains accepted. This reopens source-only
implementation; it grants no operator execution or provisioning authority.

`HISTORICAL OBSERVED`: independent trust-boundary review returned `NO-GO` for
the first B0-R1 packet
`5305a2f8aff40a4f3f9babe3d7331bef5492e50104a0fb685d617a52c20a9c87` /
`da3b35674a922c830503ffece9e5e070c4ab02279fc51a4a9c24ee96a26fa558` /
`d8750b46c3f3a08c6887ba416656c598bdf744cdb4f2f896af9f2c61704ee98a`.
Those bytes are rejected and non-reusable. Review found an unguarded clock
failure after installer ownership acquisition and an exact-once violation when
the bootstrap reader's clean-absence parent close raised.

`HISTORICAL OBSERVED`: review also rejected the next packet
`ddd5090b252af866bf3b626036a51018999d0884c2679b71f1b4cff47af6616c` /
`0c5340da49c63a0c6e043a8778f63844200f274cbd84095b5de4e536ba3bc04e`
because receipt construction/canonicalization did not yet catch every
`BaseException` while resources were owned. Those bytes are also rejected.

`OBSERVED`: all three cleanup findings now have discriminating
ordinary-exception and `BaseException` regressions and source remediation. The
regenerated unsigned, non-authorizing B0-R1 exact triple is
`static_bindings_digest=c439c12983fcd05675c5a13fba1db0199064a5df0632b94e7c7a61b42046bacc`,
`binding_schema_canonical_sha256=da3b35674a922c830503ffece9e5e070c4ab02279fc51a4a9c24ee96a26fa558`,
and
`candidate_exact_bytes_sha256=13a995221dbbd327e5e9984967f8bcf2f74b8d3016ff523372dc8eb9735d0df7`.
Independent Sol/xhigh trust-boundary review recomputed exactly these bytes,
matched all 26 bound artifacts and 20 policy preimages, closed all three cleanup
findings, and returned `APPROVE_STATIC_PACK_ONLY`. This is source/static approval
only and grants no installer, A0, preparation, native, or physical authority.

`USER_STATED`: on `2026-08-29`, while preparing B0.3 the user approved the
B0-R2 exact bootstrap-epoch-binding correction design, written specification,
implementation plan, and source-only implementation. This approval does not
authorize production signing-key creation, a bundle, installer execution, A0,
preparation, native execution, or camera access.

`REFUTED`: B0-R1 stated that `bootstrap_epoch_digest` was derived from a fixed
implementation preimage and bound into RP2, but its source accepted any
lowercase SHA-256-shaped digest and RP2 contained no exact epoch projection.
A read-only probe proved that two distinct well-formed epoch values both parsed.
The B0-R1 triple at lines above is therefore historical and non-reusable.

`OBSERVED`: B0-R2 now owns one immutable 15-field epoch-policy preimage, its
exact 626 canonical bytes, and
`bootstrap_epoch_digest=736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b`.
Bundle parsing, installation authority, operator authority parsing, and
provisioning receipts reject another well-formed digest. The RP2 builder derives
a dedicated epoch projection from the source constants, and the RP2 artifact
test itself is now bound into the fixed inventory.

`OBSERVED`: the unsigned, non-authorizing B0-R2 packet is
`static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`,
`binding_schema_canonical_sha256=07ebbffaa9e0f9c2fa5b44dc9d2fab24ac82e324a118618acea7c830c5dd15cb`,
`binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`,
and
`candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`.
It binds 27 artifacts and 21 explicit policy preimages. Independent Sol/xhigh
review recomputed this exact triple, matched all 27 live artifacts and all 21
policy preimages, verified the 15-field/626-byte epoch and all four alternate-
digest rejection boundaries, found no Critical or Important finding, and
returned `APPROVE_STATIC_PACK_ONLY`. No operational path was invoked.

`OBSERVED`: all 394 D1-N2 tests and the 152-test D1-N1 native regression pass on
the B0-R2 source. The first full-suite pass exposed two D1-N1 process/timing
failures under suite load; all three directly targeted parameterized cases then
passed, and one clean full-suite rerun passed all 738 tests without changing
native source or thresholds. Scoped Ruff passes, strict mypy passes all 32
source files, RP2 `--check` exits 0, the proposal hash remains exact, and scans
found zero private-key markers and zero operational authority-artifact leaves.

`OBSERVED`: on `2026-08-29`, independent Sol/xhigh I2 source/trust-boundary
review returned `NO-GO` for the current D1-N2 source. It found no independent
RP2 trust root, no challenge-to-WorkerGrant-to-Job binding, incomplete durable
TERMINAL semantics, retained-lease closure after TERMINAL persistence, and an
unclosed pre-bridge failure path. Production `prepare_d1_n2()` and
`run_d1_n2_preflight()` were not invoked by the review.

`USER_STATED`: on `2026-08-29`, the user approved remediation option A: a
signed offline `A0ApprovalV1` envelope verified by a frozen bootstrap outside
the RP2 mutation domain. The written design is
`docs/superpowers/specs/2026-08-29-d1-n2-i2-signed-a0-remediation-design.md`.
Source implementation and the replacement non-authorizing RP2 are complete.
Bootstrap provisioning, a production signing identity, signed A0, no-stream
preparation, A1, and physical execution have not started.

`OBSERVED`: the remediation adds closed signed-A0 parsing, an independently
approved exact RP2 triple, A0-before-PENDING binding, bridge-generated
challenge/Job grant binding, reconstructively verified integer-only receipt and
failure-ledger evidence, exclusive ownership transfer, idempotent pre-bridge
abort, and close-before-terminal ordering. Production remains hard-wired to
`BOOTSTRAP_UNPROVISIONED` and cannot create keys, signatures, or approvals.

`HISTORICAL OBSERVED`: the replacement RP2 bound 15 artifacts and 14 explicit policy
preimages under
`static_bindings_digest=49d877e2dbd85368e5ec0feb1a4207a0ca6926840bfa7ffaf6d39875aaf2a208`.
Its canonical schema digest is
`975388bff4ad6a3bfded6a043bd234c22897487a6ced9b797e7a21ccc1cfb081`
and its exact candidate-byte digest is
`5e907471495cbbd5e1405b284ace3a22c577511ae627635eed14a0881066bae7`.
This triple is not signed and supplies no authority. Independent Sol/xhigh I2
review returned `APPROVE_STATIC_PACK_ONLY` for exactly this triple.

`HISTORICAL OBSERVED`: the rejected non-authorizing RP2 bound 13 artifacts under
`static_bindings_digest=5c1606a0e20c571aa37f0ccb150c819457612ec96cc2aea1d621930de28757d0`.
Its canonical schema digest is
`56c099301398fe281506af6b34fe58a732a26882694fc6e618e039f4ae42a87f` and
the exact manifest-byte digest is
`a733fdf46b0068d9487f7ae7002e23a6235868c93ef36a37213944d6a4bbc145`.
These bytes are rejected I2 evidence and may not receive A0. They remain useful
only as the exact snapshot reviewed; they are not PreparedAuthority or
execution authority.

`HISTORICAL USER_STATED`: on `2026-08-29`, the user granted A0 for exactly
`d1-n2-authority-v1` and the superseded digest
`f582e6a284d5f3afcbe51d37a74ee9bcdb982537e2c7da7c81ba14bb0ef7c5c9`.
That authority was used once by the old inert entrypoint, closed fail-closed,
and is non-reusable. It does not transfer to the new digest.

`HISTORICAL OBSERVED`: the superseded entrypoint returned
`AUTHORITY_NOT_ISSUED` with zero reported native side effects. The source change
has invalidated that old binding exactly as required. A1 remains unopened.

The binding ceiling remains `authority_status=AUTHORITY_NOT_ISSUED`, `execution_authorized=false`, `physical_camera_access_authorized=false`, `device_gate_decision=UNVERIFIED`, and `d1_go=false`.

The single D1-N1 physical authority is now consumed and terminal. The authorized
parameter-free attempt returned `NO_GO` with
`UNKNOWN_TECHNICAL_FAILURE`, `device_gate_decision=UNVERIFIED`, and `d1_go=false`.
No retry occurred and no D1-N2 physical authority exists. The active slice is
offline/no-device diagnostic remediation only; the terminal D1-N1 authority may
not be reopened, replaced, or inferred to authorize another camera action.

### HISTORICAL_CONSUMED_TERMINAL_NON_AUTHORIZING: D1-N1

`HISTORICAL`: on `2026-08-26`, after accepting P1 and authorizing D1, the user confirmed a controlled no-human environment and opened the D1-N1 adapter for one 60-second preflight. That one-shot authority, including the then-recorded `M2_D1_N1_NATIVE_PREFLIGHT_GO`, was consumed and terminalized. It cannot authorize a second physical action or retry. M0 remains the default runtime mode; M1 remains locally verified and does not implement research collection or real participant activity.

`HISTORICAL`: the consumed D1-N1 vector recorded physical-camera and pretrained-technical-inference permissions as true for that one attempt only; participant and model permissions were false. It is not a live authorization vector.

`CURRENT`: authorization is non-transitive and revision-scoped. The live D1-N2 vector remains `physical_camera_access_authorized=false`; D1-N2 has no native-execution authorization. Audio, network, raw retention, participant collection, model training/evaluation, persistence/seal/export, retry, M3, and M4 remain `NOT_AUTHORIZED`.

## Active M2-R0 source/static authority re-entry boundary

Status: `M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`.

`OBSERVED`: the current B0-R2 controlling tuple is
`static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`,
`candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`,
and
`binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`.
It binds 24 source/test/script artifacts plus 3 lock/model artifacts and 21
policy preimages. RP2 `--check` passes without rewriting the candidate or
schema. Bootstrap remains `UNPROVISIONED`; fresh A0 is `NOT_ISSUED`; A1 is
`NOT_OPENED`; X0 is `BLOCKED`. M2 native/camera work remains unopened.

`docs/spec/M2_READINESS_PACK.md` Version 0.4 records the historical P1 acceptance and D1 decision context; it supplies no live D1-N2 or physical authority. `docs/ai/M2_D1_IMPLEMENTATION_PLAN.md` defines the implementation hypothesis; `docs/ai/M2_D1_METHOD_REVIEW.md` narrows the first slice to `D1_BACKEND_CONTRACT_EXERCISE`. A backend contract pass must retain `device_gate_decision=UNVERIFIED` and must be structurally unable to emit `D1_GO`. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional. Incidental person, voice, identity-bearing reflection, prohibited screen content, unknown privacy state, audio, or a second owner is a terminal `PRIVACY_STOP`/`NO_GO` condition with no seal or export.

## Current evidence

- `OBSERVED`: current B0-R2 RP2 `--check` exits 0 for the 24-source/test/script
  plus 3-lock/model inventory and 21 explicit policy preimages. No current
  `--write` invocation was used for M2-R0.
- `HISTORICAL OBSERVED`: before B0-R2, all 388 D1-N2 tests and all 152 tests in the D1-N1 native regression file passed; the then-current full repository suite passed `732/732`. B0-R2 supersedes those counts with the evidence above.
- `OBSERVED`: independent Sol/xhigh review recomputed the exact current packet,
  matched 27/27 artifacts and 21 policy preimages, found no remaining
  source/static blocker, and returned `APPROVE_STATIC_PACK_ONLY`. The prior
  `NO-GO` verdicts remain attached only to rejected historical packets.
- `OBSERVED`: the canonical proposal remains byte-identical at SHA-256 `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
- `HISTORICAL OBSERVED`: the spent A0 prepare receipt remains recorded in `docs/ai/M2_D1_N2_A0_PREPARE_RECEIPT.md`; it applies only to the superseded digest.
- `HISTORICAL OBSERVED`: an earlier independent Sol/xhigh I2 review returned
  `NO-GO` after 273
  D1-N2 tests with the public production-dispatch test deselected, 152 D1-N1
  regressions, RP2 `--check`, scoped Ruff, strict mypy, exact 13-artifact
  hash/size comparison, and a coordinated candidate/schema authority-flip
  probe. Those findings belong to the rejected earlier packet; the current
  B0-R2 source/static packet later received `APPROVE_STATIC_PACK_ONLY`.
- `USER_STATED`: signed-A0 remediation option A is approved for design; the
  production bootstrap remains `UNPROVISIONED` and no signing identity exists
  in this repository.
- `UNVERIFIED`: host runtime, executable/FFmpeg lease, camera/device, PreparedAuthority, WorkerGrant, capability, Job, watchdog runtime, terminal, and physical metrics.
- `BLOCKED`: no D1-N2 prepare, native discovery, camera access, consume, launch,
  retry, participant use, audio, network, or raw retention is authorized.
  Separately authorized bootstrap provisioning and a fresh signed A0 for the
  exact B0-R2 triple are required before no-stream prepare. A1/X0 remain
  unopened.

- D1-N1 terminal physical attempt: the official fixed entrypoint was invoked
  exactly once. It returned after about 22.1 seconds with `outcome=NO_GO`,
  `failure_code=UNKNOWN_TECHNICAL_FAILURE`, `authority_consumed=true`,
  `capture_worker_supervised=true`, `capture_deadline_enforced=true`,
  `capture_job_drained=true`, `capture_worker_lease_closed=true`,
  `audio_requested=false`, `raw_retained=false`,
  `device_gate_decision=UNVERIFIED`, and `d1_go=false`. Receipt digest:
  `ba7af1a2ffe4d0dfd62f530ef4f56ac5574322f10c755b1a55ac265b81099ea1`.
  This remains `OBSERVED` terminal evidence and cannot be relabeled by later
  offline work.

- D1-N2 source seam: the offline store, fixed verifier/leases, canonical lifecycle,
  retained entrypoint, dormant worker bridge, dedicated authority-free capture
  loop, and closed receipt/terminal semantic verifiers are locally verified only.
  PREPARED/grant/terminal records persist only versioned sanitized state, sizes,
  digests, and bindings; raw process epoch, capability, nonce, path, friendly
  name, and argv are never persisted. This does not prove host behavior or
  authorize creation of any such record.

All statements below are `OBSERVED` local evidence unless another label is shown.

- D1-C1 injected backend contract: `src/pdu_exam_observer/m2_d1_contract.py` and `tests/backend/test_m2_d1_contract.py` only. TDD began with a missing-module RED, then independent Sol/xhigh review drove fail-closed remediation for semantic receipt forgery, zero-byte success, timestamp/backlog mutants, unbound receipts, quality failure, privacy evidence after stop, provenance allowlists, and missing threshold mutants. The final builder gate emitted 45 passing pytest markers; scoped Ruff reported `All checks passed!`; scoped mypy reported `Success: no issues found in 1 source file`. Independent final Sol/xhigh research/privacy review is `APPROVE`. Root independently observed `uv.lock` SHA-256 `BAF657E935BD76C34E097C6D7F02EBED902758B965148E5585F1CC7CAD8B608C`, matching the bound lowercase constant. This proves only the injected contract revision, not a native device run.

- M2-P1 persistence/lineage seam: `src/pdu_exam_observer/m2_persistence.py` and `tests/backend/test_m2_persistence.py` only. TDD RED observed missing module, then missing stage-fault hook. Final focused evidence: `python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`32 passed in 3.43s`); scoped Ruff (`All checks passed!`); mypy on the new source (`Success: no issues found in 1 source file`). Coverage includes additive v1-to-v2 migration/reopen/rollback, ledger and schema tamper, contained derived paths, hash persistence, idempotency, parent/session/cycle validation, injected write/fsync/hash/rename/commit faults, recovery quarantine, withdrawal races, canonical lineage invalidation, and receipt/interface allowlists.

- Security remediation: review `NO-GO` was reproduced with focused RED for missing post-rename guard, mutable recovery-path traversal, stale manifest validity, missing explicit metadata allowlists/durability state, and unscoped concurrency. Corrected evidence uses `$env:PYTHONPATH='src'; python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`40 passed in 6.13s`), scoped Ruff (`All checks passed!`), and mypy (`Success: no issues found in 1 source file`). The final object is guarded/revalidated through commit; automatic recovery re-derives paths from IDs, does not touch tampered references, and records bounded session/audit evidence; registry validity governs manifest/replay reads; and same-root operations serialize in process.

- Second security remediation: a second `NO-GO` found non-exclusive final/directory guards and process-local-only ownership. The P1 store now acquires a raw Windows `CreateFileW` share-zero lifetime lease before validation/recovery and holds share-zero final handles and no-delete-share internal directory handles through persistence/recovery. Outside Windows, artifact sealing fails closed with `PLATFORM_UNSUPPORTED`; no POSIX-equivalence claim is made. Targeted RED included a real subprocess contender, post-verification mutation, directory-symlink swap, and handle cleanup.

- Third security remediation: a third `NO-GO` found constructor lease cleanup, pre-open-only reparse checking, and an overbroad POSIX claim. The constructor releases the lease exactly once on any post-lease failure; every Windows lease/directory/final raw handle is checked with `GetFileInformationByHandle` after open; and non-Windows sealing refuses before write. RED covered a malicious database reparse followed by successful second acquisition, an acquisition-window directory swap, and forced non-Windows capability. Corrected gates: `$env:PYTHONPATH='src'; python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`46 passed in 6.16s`), Ruff (`All checks passed!`), and mypy (`Success: no issues found in 1 source file`). Status remains `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`, never `P1_ACCEPTED`.
- Fourth security remediation: P1 is now an existing-v1-root migration only: missing root, `operational`, or v1 database is rejected without bootstrap writes. Before lease/database child I/O, Windows accepts and retains post-open-validated raw no-follow/no-delete-share handles for root and `operational` through store lifetime. RED covered missing components and a pre-open `operational` replacement with no outside lease/database creation. Corrected gates: `$env:PYTHONPATH='src'; .\\.venv\\Scripts\\python.exe -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`50 passed in 6.82s`), Ruff (`All checks passed!`), and mypy (`Success: no issues found in 1 source file`). Status remains `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`, never `P1_ACCEPTED`; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

- M2-S1 pure synthetic seam: `src/pdu_exam_observer/m2_synthetic.py` and `tests/backend/test_m2_synthetic.py` only. TDD recorded the initial missing-module RED, first GREEN (`17 passed`), verifier `NO-GO` for absent golden comparison and 29 Ruff errors, then a targeted golden-mismatch RED. Corrected independent evidence is focused pytest (`18 passed in 0.07s`), Ruff (`All checks passed`), mypy (`Success: no issues found in 1 source file`), and Luna/medium independent verifier `APPROVE`.

- Python test suite: 73 passed; Ruff passed; mypy passed for 14 files.
- Frontend: 9 files and 57 tests; typecheck, lint, and production build passed.
- Release manifest: 182 entries and 0 forbidden items; dist/package receipt is 5/5 byte/hash matched.
- M0 smoke and M1 smoke passed. M1 smoke covered native configuration, loopback health, governance flow, fail-closed readiness, withdrawal, and restart persistence.
- Packaged executable SHA-256: `30C191FFBC8729736377B8800ADA80459187504772E30B77E7FD0DDCBFD97F27`.
- Detached and bundled manifest SHA-256: `071849B5AB94C60D90F184282C66B6FBBC5FE133AB888304DAAD22DC6D5CFCAC` for each copy.
- Exact-SHA browser/runtime acceptance: `PASS`; login, pairing, consent, preflight, deterministic replay, SSE resume, sealing, responsive `390x844`, focus-visible controls, and normal-path console checks passed in packaged Chromium.
- Process/listener cleanup: `OBSERVED`, zero remaining PDU processes and loopback listeners after smoke/browser cleanup.
- Sol visual advisory: `ACCEPT`; user visual acceptance remains `PENDING`.
- M0 source and archive disposition: `SOURCE_VERIFIED`/`PASS` under the existing provenance ledger.

## M1 persistence and governance

- `M0` uses the in-memory backend by default. Explicit `PDU_RUNTIME_MODE=m1` loads the native configuration and SQLite WAL store outside the bundle.
- Schema version 1 is migration-ledgered and validated by canonical DDL, columns, indexes, unique constraints, foreign keys, and checksum.
- Credentials remain memory-only: the reviewer bearer is represented by an in-memory digest/session contract and the reviewer PIN is supplied by the launcher environment; neither is persisted in SQLite.
- Research readiness is fail-closed. Institutional approval, retention authority, storage-control attestations, and collection implementation remain blocking gates; research sessions cannot enter `RECORDING`.
- Participant withdrawal is terminal and participant-wide. It creates one canonical receipt, blocks collection/export, invalidates artifact lineage, and creates bounded reconciliation tasks.

## HISTORICAL_CONSUMED_TERMINAL_NON_AUTHORIZING: D1-N1 boundary

`HISTORICAL`: the D1-N1 native video-only adapter and one 60-second no-human preflight were the one allowed M2 physical boundary. That boundary is consumed and terminalized; it authorizes no further physical action or retry. The 20-minute native run, encoder/disk/persistence integration, participant collection, M3 annotation/rule baseline, M4 pilot/participant consideration, M5 confirmatory collection, M6 training/model import, and M7 confirmatory evaluation/trial release remain unopened.

## Residuals and boundaries

- `UNVERIFIED`: institutional approval, real participant data, and all M2+ work other than the focused S1 pure synthetic seam, including device, capture, dataset, and model work.
- Encryption and ACL values marked `VERIFIED` in the smoke are test attestations supplied to the local configuration, not proof of actual storage encryption or access-control enforcement.
- `UNVERIFIED`: clean-machine execution, signing, deployment, physical two-monitor behavior, other browsers, and user visual acceptance.
- Environment notes: Node `24.11` versus jsdom `24.15` warning; PyInstaller tzdata/pkg_resources warnings. Exact smoke still passed; these warnings are not release evidence.
- Parked Minor `T-01`: concurrency evidence passed code review, transactional CAS, and mutant duplicate-event probes, but the test does not directly instrument `SELECT` ordering.
- One old `%TEMP%\pdu-m1-smoke-6a73eff5299a48e89a6aca1fc43ce9fb` cleanup was control-plane blocked. It contains synthetic smoke data only; no PDU process or listener remains. This is not a release artifact.

### Fifth security remediation

- P1 now holds an exact derived Windows database-leaf handle before lease/SQLite/migration/recovery and validates/guards WAL/SHM sidecars before migration/recovery writes. RED covered swapping the database leaf to a separate valid v1 database (outside ledger remained `[1]`, no v2 table/sidecars) and a symlinked WAL sidecar. Main-connection close retains sidecar guards; a trusted anchor is then closed after guard release to preserve SQLite WAL cleanup. Focused P1 evidence was bounded by the local 30-second terminal wrapper: `7+6+13+6+8+11 = 51 passed`; the M1 migration regression passed (`1 passed in 0.47s`); scoped Ruff and mypy passed. This remains local evidence only.

### Sixth security remediation

- P1 now reserves and raw-validates the exact WAL/SHM names before any SQLite operation, rejecting raced symlinks. Normal close checkpoints under guard, switches the single store connection to `query_only`, then releases sidecar guards for SQLite cleanup while database/root/operational guards and the root lease remain. RED covered an absent-sidecar plant and two clean close/reopen cycles; the corrected timing probe passed in `0.36s`. The explicit >120-second monolithic pytest request was terminal-wrapper-limited at 30 seconds, so all 53 P1 cases were run in bounded groups (`7+6+13+6+8+13`), all passing; M1 migration, Ruff, and mypy passed. This is local evidence only.

### Seventh security remediation

- Normal close and constructor-failure cleanup now share rollback/checkpoint/query-only/guard-release sequencing. Fault-path RED was `2.915371s`; corrected fault/retry plus close/race probes passed in `0.36s`. M1 migration, Ruff, and mypy passed. The terminal wrapper still blocks a monolithic P1 result, so this is local builder evidence only.

This paragraph records the pre-decision P1 state. The user explicitly accepted P1 on `2026-08-26`. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional. Nothing here claims camera/device readiness, capture, participant authorization, production, deployment, release, institutional approval, research performance, demand, or participant access.

## Seventh remediation and final independent review receipt (2026-08-26)

`OBSERVED`: all prior P1 security `NO-GO` rounds are resolved remediation evidence, not erased. Unified normal/constructor-failure cleanup returned from migration fault in `0.012s`; immediate retry produced ledger `[1,2]` and allowed deletion/cleanup. The no-replacement hook blocked WAL/SHM replacement with `WinError 32`; external bytes were unchanged. Independent final evidence: focused monolithic P1 plus one M1 migration regression `55 passed in 7.60s` (elapsed `8.371s`); Ruff `All checks passed!`; mypy `Success: no issues found in 1 source file`; Terra/max security reviewer `APPROVE` source. Residuals: `m2_persistence.py:340` SQLite-error fallback was source-reviewed fail closed but not independently fault-injected in the final pass; Windows-only sealing; parent-directory durability `PLATFORM_UNSUPPORTED`; no full suite/runtime/device/encryption/ACL/participant/research-validity evidence.

`HISTORICAL D1-C1 EVIDENCE, NOT CURRENT STATE`: RoutingReceipt schema v1 recorded prior P1 builder `Terra/high`; prior P1 security reviewer `Terra/max APPROVE`; D1-C1 writer `Terra/high`; D1 research/privacy reviewer `Sol/xhigh APPROVE`; root decision owner; `P1_ACCEPTED=true`; D1 no-human validation authorized; participant and model flags false. `M2_S1_ACCEPTED` remains retained; authority is non-transitive and revision-scoped. Historical D1-C1 status was `D1_BACKEND_CONTRACT_LOCALLY_VERIFIED_PENDING_NATIVE_EVIDENCE`; a backend pass cannot become physical-device evidence or `D1_GO`. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.
