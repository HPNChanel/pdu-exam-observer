# M2-S3E-A Verification

Status:
`M2_S3E_A_SAME_HOST_ISOLATED_PORTABILITY_LOCALLY_VERIFIED_CLEAN_ENVIRONMENT_HANDOFF_READY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY`

`OBSERVED`: the deterministic S3E handoff ZIP was extracted and executed in
exactly two owned same-host relocation profiles: one path containing spaces and
one path containing Unicode plus spaces. Each relocation ran preflight,
nominal, two S2D exports, and two stdin-only S2E reproductions through the
packaged S3D executable. Both minimized projections were byte-identical.

```text
same_host_portability_receipt_sha256=e952c3364be3513dc2decd7d2ff55d9328d91b1e6a629b51b30d55419ce73b85
static_bindings_digest=ca925c67903757b776fceff0f785eb46fe2a74f8a1fd18681da4a6ff7dea212b
candidate_exact_bytes_sha256=dfbea5e5cb6bfa93fc33e3ed7225b25b43ba92091729f026dc116b7fbd8d2f83
binding_schema_exact_bytes_sha256=302dc8156c0da4bee47b39f0c42d2cc91b09ea0bb3eeb49853413d52bff30003
source_tool_inventory_count=70
policy_preimage_count=60
handoff_build_validation_sha256=eccb9e46eb5a86c98199a609d6321ab3b97529c607bd24341211f325f86d43a3
handoff_manifest_sha256=7735cd6d2aba8f8ac2425c3560344e8d0bcb2a558f59cf0191c25b0fd1659ff9
handoff_zip_sha256=ab58430c9af119553b222c29f972ab956387dc73a6fb76597a45ed97fdd49210
historical_package_unchanged=true
candidate_package_unchanged=true
candidate_package_contains_integration=true
packaged_runtime_smoke_verified=true
packaged_evidence_round_trip_verified=true
same_host_portable_verified=true
clean_environment_handoff_ready=true
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

Runtime evidence:

- relocation count: 2;
- candidate process count: 6;
- preflight observations per relocation: 977;
- nominal observations per relocation: 18,077;
- reproduction results: 4 exact reproductions;
- network scope: `LOOPBACK_ONLY_OBSERVED`;
- child PATH sanitized: true;
- external runtime dependency supplied: false;
- temporary workspaces removed: true;
- candidate bytes unchanged: true.

The run establishes same-host relocated portability and readiness of the
clean-environment handoff pack only. It does not establish a clean-machine or
VM result, air-gap, physical camera/device behavior, participant collection,
distribution readiness, signing, deployment, or release authority. GAP-06 and
GAP-08 remain open.

Final verification:

- S3E-A focused tests: `10 passed`;
- RP2 artifact tests: `6 passed`;
- governance consistency: `3 passed`;
- research suite: `69 passed`;
- collection: `986 tests`;
- full suite: `986 passed in 220.66s`;
- Ruff and strict mypy: PASS;
- S3D candidate and historical release manifests: verified.
