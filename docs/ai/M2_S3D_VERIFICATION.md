# M2-S3D Verification

Status:
`M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`

`OBSERVED`: the deterministic S3D candidate completed two independent
same-host synthetic round-trip cycles. Each cycle ran `PREFLIGHT_60S` and
`NOMINAL_20M`, exported both S2D bundles through the monitor-only endpoint,
terminated the server, and reproduced both bundles through the packaged
stdin-only `m2synthetic-reproduce` mode. All four reproductions were
`EXACTLY_REPRODUCED`; both minimized cycle projections had SHA-256
`6a452cbca40f5e96b4b191fd41e5f92161c0aefebb9e727fe281eaf26cc68abe`.

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

This receipt is same-host synthetic package evidence only. It does not
establish clean-machine portability, camera/device behavior, participant
collection, distribution readiness, signing, deployment, or release authority.

`OBSERVED`: S3D focused tests `10 passed`, RP2 artifact tests `6 passed`,
governance `3 passed`, research `69 passed`, Ruff PASS, strict mypy PASS,
collection `976 tests`, and one full-suite invocation returned
`976 passed in 226.47s`. Historical, S3B, and S3D manifests verified after the
runtime cycle.

`REVIEWED`: the original S3D/S3C cleanup-prefix defect was corrected and the
real S3D cleanup helper is exercised by a focused test. A low residual remains:
a malicious same-account junction substitution racing the check/delete window
is not excluded by handle-level file-identity locking. Random owned roots,
direct-parent containment, prefix checks, and reparse rejection reduce this
risk; it is not evidence of clean-machine or hostile-local-user resistance.
