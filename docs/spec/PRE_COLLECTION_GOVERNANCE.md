# Pre-Collection Governance Specification

Version: `1.0`

Status: `GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`

## Purpose

This specification governs research preparation that can be completed without
an additional device, camera access, a participant, or institutional authority.
It does not authorize collection. It records a reproducible draft labelbook,
continuous-session/clip reconciliation, source traceability, ethics/data
templates, reporting structure, and future borrowed-custodian requirements.

## Evidence ceiling

`PACK_VALIDATED` means only that the versioned files are canonical, complete,
hash-bound, and internally consistent. It must coexist with:

```text
research_ready=false
collection_authorized=false
participant_collection_authorized=false
physical_camera_access_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
device_gate_decision=UNVERIFIED
d1_go=false
```

No document, template, source citation, test, hash, or manifest can change
those fields.

## GOV-P5A advisor-first human-confirmation request

GOV-P5A creates a local request pack for exactly two unresolved decisions:
`HC-01` current-cycle late-submission acceptance and `HC-02` the applicable
human-subjects/ethics review route. Audience is `FACULTY_ADVISOR_FIRST`.

Current status is
`GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`.
`human_response_status=PENDING`, `external_transmission_authorized=false`, and
`submission_state=NOT_SUBMITTED`. Manifest SHA-256 is
`4c5443ae46972b5ec56d2229700580bd0a6e7c1be61ef79d019c055314962fa8`.

The response template contains no answer or identity. Blocking gates
`CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED` and
`HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED` remain open. Residual
`HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED` prevents a structural PASS from
being presented as transmission, human response, ethics clearance, or
institutional approval. GOV-P5B remains unopened.

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

## GOV-P4 institutional route source verification

Immutable upstream status:
`GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_UNCONFIRMED_APPROVAL_NOT_ISSUED`.

GOV-P4 uses the canonical proposal and current public primary sources from
Trường Đại học Phạm Văn Đồng. The verified administrative route is:

1. Sinh viên chuẩn bị Mẫu 1-3.
2. Hội đồng khoa xét đề cương bằng Mẫu 4 và Mẫu 5.
3. Khoa lập danh mục bằng Mẫu 6 và chuyển bộ Mẫu 1-6 cho Phòng Quản lý Khoa học.
4. Phòng Quản lý Khoa học tham mưu cho Hiệu trưởng.
5. Hiệu trưởng ban hành quyết định phê duyệt; sinh viên chỉ bắt đầu sau quyết định.

This closes route discovery as
`adv_02_status=SATISFIED_BY_PUBLIC_PRIMARY_SOURCES` and
`institutional_route_status=SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED`.
Manifest SHA-256 is
`f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531`.

The general student-research route does not establish whether adult-volunteer
webcam research needs a separate ethics/human-subjects review. Therefore
`human_subjects_review_requirement=UNKNOWN_PENDING_CONFIRMATION`. The current
registration deadline passed on `2026-08-29`; late acceptance also requires
human confirmation. Residuals
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

## GOV-P3 advisor verbal decision receipt

Immutable upstream status:
`GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_READY_FOR_INSTITUTIONAL_ROUTING`.

GOV-P3 records the user's report that the faculty advisor verbally approved
the dossier. It closes only `ADV-01` for workflow progression as
`SATISFIED_BY_USER_REPORT_UNVERIFIED` with outcome
`READY_FOR_INSTITUTIONAL_ROUTING`. The evidence classification is
`USER_STATED_UNVERIFIED`; no written evidence, identity, signature, exact
advisor decision date, or independent corroboration is stored.

The GOV-P3 manifest SHA-256 is
`7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605`.
The receipt pins exact GOV-P2 decision-matrix, manifest, and validation bytes.
It does not overwrite GOV-P2 v1.

`ADV-02` remains `PENDING_EXTERNAL_DECISION`, so the official approving unit,
required template, and signature roles are still unknown.
`institutional_approval_status=NOT_ISSUED` and
`submission_state=NOT_SUBMITTED`. The residual
`ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY` prevents a verbal report from
being presented as source-verified or institutional evidence.

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

## GOV-P2 advisor-first review interface

Immutable upstream status:
`GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW`.

GOV-P2 assembles a deterministic Vietnamese source dossier for
`FACULTY_ADVISOR_FIRST`. It remains `submission_state=NOT_SUBMITTED` and
`PENDING_EXTERNAL_REVIEW`. A validation pass proves only exact file set,
canonical JSON, source bindings, annex equality, and fail-closed decision
content. It is not an advisor decision, institutional approval, participant
invitation, or collection authority.

Manifest SHA-256 is
`1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e`.
All decision values remain `PENDING_EXTERNAL_DECISION`; a real response needs
a separately authorized version and may not overwrite v1.

Correction A preserves historical GOV-P1. Because later M1-R1 source differs
from the M1 source pinned by that rehearsal, GOV-P2 records
`CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT` instead of rebuilding
or weakening the old receipt/checker.

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

## GOV-P1 synthetic rehearsal

GOV-P1 executes the approved withdrawal/deletion procedure only with synthetic
process data inside a runner-owned temporary root. The deterministic receipt
records one synthetic participant, two sessions, four invalidated artifacts,
four pending M1 withdrawal tasks, exact deletion of four manifest-owned fixture
files, preservation of one out-of-manifest sentinel, and final temp-root
disposal after closing SQLite.

The rehearsal does not implement or attest a production deletion reconciler.
It does not mark any M1 task complete and does not exercise export because M1
has no export capability. Its institutional dossier and external-decision
record remain draft/blocked. A valid GOV-P1 receipt therefore adds
`PRODUCTION_RECONCILER_UNIMPLEMENTED` to, rather than removes, the blocking
gate list.

The three reviewed GOV-P1 sources are exact-file-hash pinned. The runner also
binds the canonical checkout paths for itself and `m1.py`, atomically replaces
only fixed generated leaves, rejects link/reparse roots or leaves, and rechecks
fixture identity immediately before unlink. These controls do not establish a
native retained-handle deletion primitive or resistance to a hostile
same-account race; the receipt must keep that capability false.

## Population and observation units

The planned population remains twelve consenting adults: two pilot and ten
confirmatory participants. Each participant has two controlled 20-minute mock
exam sessions. Continuous time is the denominator for false alerts per hour and
latency. The derived clip is the supervised observation unit.

Every planned clip is exactly 6,000 ms and fixed in the scenario schedule
before the session. Planned windows do not overlap. Each pilot participant has
8-10 windows for each of six supervised classes; each confirmatory participant
has 9-10. This yields 96-120 pilot clips, 540-600 confirmatory clips, and
636-720 total planned real clips. Actual, uncertain, excluded, and technical
counts must be reported separately.

Pilot samples are apparatus/method evidence only and are prohibited from
confirmatory metrics. A scheduled window is never moved after seeing a model
output. Insufficient observable evidence becomes `UNCERTAIN`.

## Taxonomy

The six supervised classes are:

1. `NORMAL`
2. `BENIGN_CONFOUNDER`
3. `PROLONGED_HEAD_DOWN`
4. `PROLONGED_SIDE_LOOK`
5. `NO_PERSON`
6. `MULTIPLE_PEOPLE`

`UNCERTAIN` is an audit-retained research label/disposition and cannot enter a
supervised class target. `TECHNICAL_INSUFFICIENT` is a system outcome for weak
or failed evidence and is never relabeled as behavior.

## Method locking

Event matching is class-aware and one-to-one using temporal intersection over
union. The confirmatory report must expose the tIoU sweep from `0.50` to `0.95`
inclusive in `0.05` steps. The single primary tIoU is selected using only the
applicable training/calibration partition or pilot method evidence, then frozen
before any confirmatory outer-test result is viewed.

Head-angle onset/offset thresholds, minimum duration, persistence, cooldown,
and merge gap follow the same rule. Source literature may justify the feature,
metric, or selection method; it cannot be misrepresented as a validated PDU
threshold. Until selected, each field remains null with status
`UNSET_PENDING_M2_CALIBRATION_OR_PILOT`.

False alerts are unmatched predicted events. The denominator is valid
continuous exam time under the frozen technical-exclusion policy. Wrong-class
matches remain errors. Detection latency begins when an event first becomes
eligible under the frozen duration policy.

## Institutional and data gates

The participant information sheet and consent form remain
`DRAFT_FOR_INSTITUTIONAL_REVIEW`. They cannot become issued artifacts until an
institutional approval identifier, approved responsible contact, consent
version, retention decision, and approved storage controls are recorded.

The project does not invent a legal retention period. The approved record must
contain either a retention end date or a policy reference, never both. The
research root, encryption, and ACL state remain unverified until observed on
the actual authorized storage environment.

No real participant may be approached or recorded from this pack. Raw video
remains local. Identity mappings and signed consent remain outside the dataset
tree. Export remains limited to the existing product allowlist.

## B0.3 deferral

The inert B0.3 kit remains preserved outside the checkout. Resource constraint
defers, but does not weaken or bypass, the custodian contract. A future borrowed
custodian requires a physical non-target Windows 11 x64 standard-user offline
environment plus fresh exact execution authority. The checklist does not
request, create, or imply that authority.

## Static validation

The builder validates fixed paths, closed schemas, body hashes, taxonomy,
counts, duration, matching-selection boundaries, unresolved institutional
gates, non-authorizing claims, proposal SHA-256, and exact manifest bytes. It
rejects duplicate/noncanonical JSON, missing/extra files, tampering, unsafe
relative paths, issued drafts with unresolved tokens, test-informed threshold
selection, and any false transition to readiness or collection authority.
