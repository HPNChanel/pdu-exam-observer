# Product and Research Roadmap

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

## M2 - Capture and pose pipeline

Status: unopened. No current authorization for webcam enumeration, capture, pose processing, FFmpeg recording, or participant collection.

Source/static substatus: `M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`. The
current B0-R2 tuple is
`static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`,
`candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`,
and
`binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`.
This is source/static consistency evidence only. Bootstrap is unprovisioned,
fresh A0 is not issued, A1 is not opened, and X0 is blocked.

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
