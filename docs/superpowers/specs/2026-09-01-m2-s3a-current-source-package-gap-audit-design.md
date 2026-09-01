# M2-S3A Current-Source Package Gap Audit Design

```text
document_status=USER_APPROVED_FOR_IMPLEMENTATION
approved_direction=A_AUDIT_ONLY
```

## Outcome

M2-S3A records deterministic evidence that the historical Windows package is
integrity-valid but does not represent the current M2-S2A through M2-S2E
source revision. The maximum status is:

```text
M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY
```

The audit is read-only with respect to runtime, frontend build outputs,
PyInstaller outputs, release manifests, and package bytes. It does not create
package acceptance, clean-machine evidence, distribution readiness, release
authority, physical-device authority, or collection authority.

## Immutable inputs

The audit pins the S2E RP2 tuple, canonical proposal, current observed frontend
dist, historical executable and manifests, packaged frontend bundle, historical
PYZ build inventory, PyInstaller spec, release/smoke scripts, and package README.
All paths are repository-relative. Git `main@7912bd9` is recorded only as the
baseline of the task-scoped dirty checkout; the S2E RP2 tuple remains the
controlling source/static identity.

The historical package remains classified:

```text
integrity_status=MANIFEST_VERIFIED
source_currency=HISTORICAL_NOT_CURRENT_SOURCE
python_inclusion_evidence=AUXILIARY_BUILD_TOC_ONLY
package_rebuilt=false
```

The build TOC is auxiliary evidence and is not represented as independent
inspection of the executable archive.

## Artifacts and contract

The machine source of truth is
`docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.json`. It is canonical UTF-8 JSON with sorted
keys, compact separators, and one trailing LF. Its closed envelope contains:

```text
artifact_kind=M2_S3A_PACKAGE_GAP_AUDIT
schema_version=1
status=M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY
body
body_sha256
```

`body_sha256` is SHA-256 over canonical JSON bytes for `body`. The body contains
only `audit_result`, `authority_ceiling`, `gap_matrix`, `historical_package`,
`next_task`, `observed_on`, `prohibited_claims`, and `source_revision`.

`docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.md` is the human-readable projection. It must
repeat the status, immutable identities, exact eight-gap matrix, evidence
labels, authority ceiling, and non-authorizing interpretation.

## Closed gap matrix

The matrix contains exactly these ordered open gaps:

1. `GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED` -> `M2-S3B`
2. `GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED` -> `M2-S3B`
3. `GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT` -> `M2-S3C`
4. `GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT` -> `M2-S3D`
5. `GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT` -> `M2-S3D`
6. `GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT` -> `M2-S3F`
7. `GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE` -> `M2-S3B`
8. `GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT` -> `M2-S3E_OR_EXTERNAL_CLEAN_ENVIRONMENT`

Every gap has `status=OPEN`, `authority_effect=NONE`, an allowed evidence
classification, and its exact closure task. No gap is closed during S3A.

## Authority ceiling

The audit fixes `package_contains_integration=false`,
`package_rebuild_started=false`, `release_authorized=false`,
`distribution_ready=false`, `clean_machine_verified=false`, and
`same_host_portable_verified=false`. Production reconciliation, real-storage
verification, real deletion, execution, physical camera, participant
collection, research readiness, and collection remain false. Device decision
remains `UNVERIFIED`, `d1_go=false`, and authority remains
`AUTHORITY_NOT_ISSUED`.

## Threat model and stop conditions

- Manifest integrity is kept separate from source currency.
- The dirty Git HEAD is not used as the current source digest.
- Build TOC evidence is explicitly auxiliary.
- Frontend marker comparison is bound to exact source/package asset hashes.
- The audit status cannot be shortened into package, distribution, or release
  readiness.
- Clean-path evidence cannot become clean-machine evidence.

Do not publish the S3A marker if any immutable input changes, the manifest no
longer verifies, the gap set changes without a new design, an authority flag
opens, RP2/governance/research/full-suite verification fails, or any package
byte is rewritten.

