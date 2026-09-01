# M2-S2E Strict Same-Revision Synthetic Evidence Reproduction Design

Status: `USER_APPROVED_DIRECTION_A_PLAN_READY_FOR_IMPLEMENTATION`

## Outcome

M2-S2E accepts one canonical M2-S2D evidence bundle, verifies the existing
S2D integrity contract, compares its environment binding with the current
source revision, and replays the corresponding built-in synthetic fixture in
an owned temporary workspace. Only a byte-identical bundle and exact nested
receipt/digest match may produce `EXACTLY_REPRODUCED`.

The maximum status is:

```text
M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY
```

This is synthetic reproducibility evidence. It is not physical M2, `D1_GO`,
model-performance evidence, research readiness, collection authority, package
inclusion, deployment, or release evidence.

## Interfaces

`m2_synthetic_evidence.py` exposes an immutable
`VerifiedSyntheticEvidenceSource` and
`load_verified_synthetic_evidence_bytes(payload: bytes)`. The loader returns
the verified bundle/run/artifact projection needed for replay and raises the
existing bounded `SyntheticEvidenceError` on invalid bytes. The existing
`verify_synthetic_evidence_bytes()` API and S2D CLI remain compatible.

`m2_synthetic_environment.py` owns the current canonical source inventory,
the fixed simulated encoder policy, `current_synthetic_environment_bindings()`
and `synthetic_environment_binding_digest()`. It accepts no caller path.

`m2_synthetic_reproduction.py` exposes:

```python
def reproduce_synthetic_evidence_bytes(
    payload: bytes,
) -> SyntheticReproductionReceipt: ...
```

The function has no public runner, fixture, path, duration, device, URL, or
expected-digest override.

The classifications are `EXACTLY_REPRODUCED`,
`SOURCE_REVISION_MISMATCH`, `SEMANTIC_RESULT_MISMATCH`, and
`REPRODUCTION_FAILED`. Operational failures use only the approved bounded
failure enum. Source- and semantic-mismatch classifications carry a null
failure code.

## Same-revision data flow

The source bundle must first pass the complete S2D validator. The current
environment binding is recomputed from canonical repository-relative files,
the historical release manifest, the bundled pose task, and the fixed
simulated encoder policy. A different binding returns
`SOURCE_REVISION_MISMATCH` without creating a replay workspace.

For a matching binding, M2-S2E creates synthetic M1 metadata with
encryption/ACL `UNVERIFIED`, never records consent, and never enters
`RECORDING`. It runs only the built-in 977-frame `PREFLIGHT_60S` or
18,077-frame `NOMINAL_20M` fixture. The replay uses the source artifact ID in
an isolated M2 store, then reads the artifact through the verified same-handle
reader and rebuilds a transient S2D bundle from the source run metadata.

Exact success requires equality of the whole bundle SHA-256, observation
count/digest, D1 outcome/failure/digest, artifact SHA-256, and integration
result digest. Mismatches are sorted and restricted to the closed comparison
field set. Authority mutation is an operational failure, never a semantic
mismatch. Stores and temporary roots are closed and removed before an exact
receipt is emitted.

## Receipt and CLI

The schema-v1 canonical receipt contains the classification, bounded failure,
run kind, source/reproduced digest pairs, closed mismatch fields, temporary
workspace state, the complete fail-closed authority ceiling, and a canonical
`result_digest`. Non-exact receipts use
`M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_NOT_VERIFIED`.

`scripts/reproduce_m2_s2e_synthetic_evidence.py <bundle.json>` accepts exactly
one regular non-link file up to 4,000,000 bytes. It detects a changed file
identity/size, writes one canonical JSON line to stdout, keeps stderr empty,
returns 0 only for exact reproduction, and never prints a path, username,
traceback, or exception text. It creates no output file or server archive.

## Migration and residual risk

There is no database, API, D1, manifest-v2, web, or package migration. Moving
the environment computation to a shared source changes the application
revision digest. Older S2D bundles remain valid integrity evidence but must
classify as `SOURCE_REVISION_MISMATCH`; they are never rewritten.

Exact replay proves determinism of the built-in synthetic pipeline at the
bound source revision. It does not reproduce a physical camera, encoder,
driver, disk, participant, or hostile production environment.

## Authority ceiling

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
