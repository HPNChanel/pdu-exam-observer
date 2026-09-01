# M2-S2A Synthetic System Integration Core Design

Status: `USER_APPROVED_FOR_IMPLEMENTATION`

## Outcome

M2-S2A composes the existing pure synthetic runner, the D1 aggregate
evaluator, a canonical minimized receipt, and the M2 v2 persistence seam.  It
executes only an accelerated, injected `PREFLIGHT_60S`; it never waits on or
opens a camera, participant, audio stream, browser route, export path, or
physical-device authority.

Maximum milestone status:

```text
M2_S2A_SYNTHETIC_PREFLIGHT_VERTICAL_SLICE_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY
```

`BACKEND_CONTRACT_PASS` is an evaluator result.  It is never `D1_GO`, physical
M2 evidence, model-performance evidence, research readiness, or collection
authority.

## Integration contract

The internal API is implemented by `M2SyntheticPreflightCore`.  A request
contains only opaque run/session/intent/artifact identifiers, an allowlisted
fixture sequence, and optional opaque parent artifact identifiers.  Environment
bindings contain only SHA-256 values and bounded injected failure codes.

The core:

1. validates one run ID, one supported synthetic input kind, increasing frame
   sequence, exact observation digests, and no reserved device scene;
2. maps `TechnicalObservation` into D1 aggregate observations;
3. rebuilds all provenance, input, evaluation, and reproduction digests;
4. evaluates and semantically verifies the D1 receipt;
5. persists a canonical minimized receipt through `M2PersistenceStore`;
6. returns a bounded integration receipt that distinguishes persistence
   success from D1 pass/no-go.

Both semantic `BACKEND_CONTRACT_PASS` and semantic `NO_GO` receipts are
persisted.  Artifact validity proves only byte, manifest, and lineage validity.
Persistence failure, withdrawal, malformed input, or semantic-receipt failure
must return `NOT_PERSISTED` with no artifact ID/hash claim.

## Built-in preflight

The smoke fixture contains exactly 977 zero-pose deterministic frames.  It uses
origin `900000000000ns`, interval `1000000000 // 15ns`, processing latency
`10000000ns`, `1280x720@15fps`, five-second warmup, and a 60-second requested
duration.  Every frame has a unique opaque fixture ID and a separately bound
golden digest.

The core supports `DETERMINISTIC_FIXTURE -> TEST_CHART` and
`AI_RENDERED_FIXTURE -> SYNTHETIC_VIDEO`.  The no-argument smoke CLI uses only
the deterministic zero-pose bundle in an owned temporary M1 root with
encryption and ACL status `UNVERIFIED`.

## Persistence and minimized artifact

The M2 database remains schema version 2; no DDL or migration is added.  The
registry kind remains `TECHNICAL_FIXTURE`, while the canonical payload declares
`M2_SYNTHETIC_PREFLIGHT_RECEIPT`.  It stores observation result digests, their
aggregate digest, canonical D1 aggregates, environment/source-binding digest,
and the closed authority ceiling.  It excludes landmarks, frames, paths,
session/participant IDs, native identifiers, usernames, and exception text.

The existing persistence failure allowlist is widened to every current D1
failure code so a persisted `NO_GO` manifest records the exact aggregate
failure without changing schema.

## CLI contract

`scripts/run_m2_s2a_synthetic_integration.py` accepts no arguments.  It emits
one canonical JSON line and empty stderr.  Success exits 0 only for a safely
persisted semantic `BACKEND_CONTRACT_PASS`; bounded failure exits 2.  It closes
all stores, removes its temporary root, emits no absolute path, and always
retains `SIMULATED`, `UNVERIFIED`, `d1_go=false`, and
`package_contains_integration=false`.

## Authority ceiling and non-goals

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

Nominal 20-minute synthetic runs, API/UI wiring, M3 rules, participant data,
camera/audio/device enumeration, actual performance claims, package rebuild,
release, deployment, submission, and real deletion are out of scope.

## Acceptance

- Twelve non-parametrized integration tests cover pass, persisted no-go,
  mapping, tamper, idempotency, persistence faults, withdrawal, minimization,
  CLI behavior, and forbidden surfaces.
- RP2 binds every new source/test/script plus policy preimages and remains
  static-only.
- Full source collection increases from 880 to exactly 892 tests.
- Release-package bytes remain historical and unchanged.

