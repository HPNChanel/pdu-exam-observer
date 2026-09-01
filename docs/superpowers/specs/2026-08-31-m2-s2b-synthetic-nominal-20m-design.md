# M2-S2B Synthetic Nominal 20-Minute Run Design

Status: `USER_APPROVED_FOR_IMPLEMENTATION`

## Outcome

M2-S2B extends the synthetic-only M2-S2A vertical slice with an accelerated
`NOMINAL_20M` run.  It composes `SyntheticRunner`, the existing D1 aggregate
evaluator, a canonical minimized receipt, and `M2PersistenceStore`.  It never
waits twenty physical minutes or opens a camera, audio stream, participant
flow, browser route, export path, or device authority.

Maximum status:

```text
M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY
```

This is simulated system-integration evidence.  It is not `D1_GO`, physical
M2 evidence, model-performance evidence, research readiness, or collection
authority.

## Public and private contracts

The existing `SyntheticPreflightRequest` and `M2SyntheticPreflightCore` remain
public and retain their `PREFLIGHT_60S` behavior.  M2-S2B adds
`SyntheticNominalRequest` and `M2SyntheticNominalCore` with the same opaque
identifier, fixture, parent-lineage, persistence, privacy, and owner-lease
boundaries.

Both wrappers delegate to a private immutable `_SyntheticRunContract` and
private `_M2SyntheticRunEngine`.  A caller cannot select the run kind,
duration, profile, artifact kind, success marker, or failure marker.

The nominal contract is fixed:

```text
run_kind=NOMINAL_20M
requested_duration_seconds=1200
warmup_seconds=5
profile=1280x720@15fps
artifact_kind=M2_SYNTHETIC_NOMINAL_RECEIPT
database_artifact_kind=TECHNICAL_FIXTURE
success_status=M2_S2B_SYNTHETIC_NOMINAL_20M_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY
failure_status=M2_S2B_SYNTHETIC_NOMINAL_20M_NOT_PERSISTED
```

No D1 enum/schema, M2 database schema, or manifest version changes.

## Built-in nominal fixture

The built-in fixture contains exactly 18,077 zero-pose deterministic frames.
It uses origin `1800000000000ns`, interval `1000000000 // 15ns`, processing
latency `10000000ns`, run ID `m2-s2b-nominal-20m`, and fixture IDs
`nominal-frame-00000` through `nominal-frame-18076`.  The last processed time
is the run end and provides at least five seconds of warmup plus 1,200 seconds
of measured post-warmup time.

Every fixture binds its input digest and independently generated golden result
digest.  The built-in CLI supports only `DETERMINISTIC_FIXTURE`; the core
retains the existing deterministic and AI-rendered mappings.  There is no
filesystem, URL, device, arbitrary-path, or caller-provided golden interface.

## Evaluation, artifact, and failure semantics

The core recomputes observation, provenance, input, evaluation, reproduction,
and receipt digests.  D1 enforces exact warmup/post-warmup denominators,
accounting reconciliation, delivered FPS, gap, latency, backlog, processed
coverage, drop/failure ratio, disk, throughput, and encoder durability gates.

A canonical nominal artifact stores only observation result digests, their
aggregate digest, the canonical D1 receipt, environment binding digest,
evidence kind, package boundary, and authority ceiling.  It excludes raw
fixtures, landmarks, frames, paths, identities, native device identifiers,
usernames, and exception text.

A semantically valid `NO_GO` is persisted for audit and remains distinct from
artifact validity.  Malformed input, forged observations or receipts,
persistence failure, or withdrawal races return `NOT_PERSISTED` and cannot
claim an artifact ID or hash.  The synthetic fault matrix covers timing,
coverage, quality/pose, privacy, encoder/disk/durability, manifest/schema,
tamper, idempotency, and persistence failures.  It is not physical fault
evidence.

## CLI and authority ceiling

`scripts/run_m2_s2b_synthetic_nominal.py` accepts no arguments.  It uses an
owned temporary M1 root with encryption and ACL `UNVERIFIED`, never puts the
session into `RECORDING`, emits one sanitized canonical JSON line, closes all
stores, and proves temp-root removal before exit.  Success requires a persisted
`BACKEND_CONTRACT_PASS`; failure exits 2 without stderr or traceback.

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

