# M2-S3C Verification

Status:
`M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`

## Verified evidence

`OBSERVED` on `2026-09-02`: the exact S3B one-folder candidate was launched in
two independent processes. Each process exposed only the two owned loopback
listeners, authenticated the reviewer flow, and completed `PREFLIGHT_60S`
(977 observations) followed by `NOMINAL_20M` (18,077 observations). Both
minimized projections have SHA-256
`52a94fe74ab6fffea82c5d0c926b0ddf6c1ec95a53b72faf147956325f79f188`.

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

## Correction evidence

The first runtime attempt returned bounded `TEMP_CLEANUP_FAILED`. Inspection
showed that the candidate spec labeled itself one-folder while the `EXE`
still embedded binaries and data, producing a one-file `_MEI*` extraction
tree after forced termination. A regression test was established before the
spec was corrected with `exclude_binaries=True`. The corrected candidate was
then rebuilt twice, byte-compared, manifest-verified, and smoke-tested once.
The failed candidate is not represented by the PASS receipt.

## Verification closure

`OBSERVED` on `2026-09-02`:

- S3B focused tests: `8 passed`; S3C focused tests: `8 passed`.
- RP2 artifact tests: `6 passed`; governance consistency: `3 passed`;
  research suite: `69 passed`.
- Ruff and strict mypy passed.
- Historical and candidate release manifests both returned `manifest verified`.
- Collection was exactly `966 tests collected`; one full invocation returned
  `966 passed in 170.26s`.

## Boundary

This is same-host, loopback-only, synthetic runtime evidence. Forced
process-tree termination is recorded and graceful shutdown remains unverified.
No camera, audio, native device, participant, evidence export, real deletion,
signing, promotion, distribution, deployment, or release operation occurred.
Same-host portability and clean-machine portability remain unverified.
