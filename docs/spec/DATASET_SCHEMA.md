# Dataset and Label Schema

Version: 1

All persisted, API, model, and export artifacts carry schema_version. Unknown newer versions fail closed.

## Identifier rules

Identifiers are opaque UUIDs or generated pseudonymous codes. Client input never controls a filesystem path. Participant codes have no embedded name, class, birth date, phone, or institution identifier.

## Core records

StudyManifest:

| Field | Type | Rule |
|---|---|---|
| schema_version | integer | Must equal supported version |
| study_id | UUID | Opaque |
| protocol_version | string | Frozen protocol identifier |
| created_at | UTC timestamp | Server generated |
| retention_policy_ref | string | Required before real capture |

Participant:

| Field | Type | Rule |
|---|---|---|
| participant_id | UUID | Dataset identifier |
| participant_code | string | Pseudonymous and unique |
| cohort | enum | PILOT or CONFIRMATORY |
| consent_receipt_id | string | No name or document image |
| consent_version | string | Required |
| consent_confirmed_at | UTC timestamp | Required before preflight ready |
| withdrawn_at | UTC timestamp or null | Blocks export when set |

ExamSession:

| Field | Type | Rule |
|---|---|---|
| session_id | UUID | Opaque |
| participant_id | UUID | Foreign key |
| state | SessionState | Server-owned transitions |
| source_kind | SourceKind | REAL for participant collection |
| started_at, sealed_at | UTC timestamp or null | Server generated |
| monotonic_origin_ns | integer | Timing reference |
| capture_profile | string | Versioned 1280x720@15fps profile |
| protocol_version | string | Immutable after start |
| failure_code | enum or null | Required when FAILED |

PoseObservation:

| Field | Type | Rule |
|---|---|---|
| session_id | UUID | Parent session |
| frame_seq | integer | Strictly increasing captured-frame sequence |
| captured_ns | integer | Monotonic capture time |
| processed_ns | integer or null | Pose completion time |
| pose_count | integer | 0, 1, or 2 |
| landmarks | array | Up to two sets of 33 x, y, z, visibility values |
| quality | object | Blur, exposure, visibility, frame-gap measures |
| processing_status | enum | PROCESSED, DROPPED_EXPLICIT, FAILED |

FocusContext:

| Field | Type | Rule |
|---|---|---|
| session_id | UUID | Parent session |
| observed_ns | integer | Monotonic |
| state | enum | EXAM_FOCUSED, EXAM_NOT_FOCUSED, FOCUS_UNKNOWN |
| signal_age_ms | integer | Non-negative |
| contaminated_by_operator | boolean | True during locked mask interval |

EventSegment:

| Field | Type | Rule |
|---|---|---|
| event_id | UUID | Immutable |
| event_seq | integer | Monotonic within session |
| research_label | ResearchLabel | Observable label |
| operator_outcome | OperatorOutcome | Three-state result |
| start_ns, end_ns | integer | End not before start |
| confidence | number or null | Calibrated when model-generated |
| source_signals | string array | Approved signal identifiers |
| model_version, policy_version | string | Required for predictions |
| review_status | enum | UNREVIEWED, CONFIRMED, REJECTED, UNCERTAIN |

SampleProvenance:

| Field | Type | Rule |
|---|---|---|
| sample_id | UUID | Immutable |
| source_kind | SourceKind | REAL, AI_RENDERED, or AUGMENTED |
| parent_sample_id | UUID or null | Required for AUGMENTED |
| generator_name, generator_version | string or null | Required for AI_RENDERED |
| transform_manifest | object or null | Required for AUGMENTED |
| participant_id | UUID or null | Required for REAL |
| split | enum | TRAIN, CALIBRATION, TEST, DEMO |

## File layout

Structured operational metadata uses SQLite with WAL during runtime. High-rate landmarks use compressed columnar or array artifacts with a versioned manifest. Raw video uses per-session or per-clip media files. Media and high-rate arrays do not live as SQLite blobs.

Writes use a partial name, validation, fsync where supported, atomic rename, and then the manifest transaction. On restart, incomplete artifacts are quarantined and the session cannot appear SEALED.

## Label integrity

Labels describe only observable events. BENIGN_CONFOUNDER includes ordinary actions that intentionally challenge false-alert behavior. UNCERTAIN is retained for audit and excluded from supervised class targets.

