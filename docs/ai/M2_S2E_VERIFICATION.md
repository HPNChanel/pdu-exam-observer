# M2-S2E Strict Synthetic Reproduction Verification Receipt

Date: `2026-09-01`

Status:
`M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`

## Observed source behavior

`OBSERVED`: fresh same-revision `PREFLIGHT_60S` and `NOMINAL_20M` S2D
bundles returned `EXACTLY_REPRODUCED` from new owned temporary roots. The
whole-bundle SHA-256, observation count/digest, D1 outcome/failure/digest,
artifact SHA-256, and integration result digest matched. Cleanup completed
before receipt emission.

`OBSERVED`: a changed current binding returns `SOURCE_REVISION_MISMATCH`
without calling replay. Tampered, noncanonical, oversized, forged-authority,
platform, transient-evidence, and cleanup paths return bounded non-exact
receipts without a replay artifact claim. The CLI emits one canonical line,
empty stderr, and no path or exception text.

## RP2 tuple

```text
source_tool_inventory_count=51
policy_preimage_count=40
static_bindings_digest=38a17dcc4ea214a2d52ef2bb825e502bcf88d7dbf48ebc2f3758da93b6d2a585
candidate_exact_bytes_sha256=15f3bcc27411b1534e6214d8818af70cf46076776af4ae73551d508d0f0f7119
binding_schema_exact_bytes_sha256=abc494b96a3cc52eda57c43d677c83245736ab65ff923faa4e39524cf84f2dc5
classification=EXACTLY_REPRODUCED
legacy_classification=SOURCE_REVISION_MISMATCH
```

## Verification gates

```text
s2e_focused=10/10 PASS
s2d_evidence_service_api_regression=28/28 PASS
s2a_s2b_d1_persistence_regressions=PASS
ruff=PASS
strict_mypy=PASS
rp2_check=PASS
python_collection=945
python_full_suite=945/945 PASS
research_suite=69/69 PASS
governance_consistency=3/3 PASS
release_manifest=PASS
package_s2e_match_count=0
TEMP_ROOT_COUNT=0
PDU_PROCESS_COUNT=0
PDU_LISTENER_COUNT=0
```

## Authority ceiling

```text
evidence_kind=SIMULATED
package_contains_integration=false
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

This receipt proves local determinism of bound built-in synthetic inputs only.
It is not physical/device, participant, model-performance, package,
research-readiness, collection, M3, deployment, or release evidence.
