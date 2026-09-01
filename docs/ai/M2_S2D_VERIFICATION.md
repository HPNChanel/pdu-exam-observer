# M2-S2D Source Runtime Verification Receipt

Date: `2026-09-01`

Status:
`M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`

## Scope and observed source runtime

`OBSERVED`: the source launcher ran in `PDU_RUNTIME_MODE=m2synthetic` on two
task-local loopback origins. The authenticated monitor origin exported one
terminal persisted preflight bundle and one terminal persisted nominal bundle.
The exam-origin evidence path returned HTTP 404.

The preflight download was 70,342 bytes with SHA-256
`63c06c0abed1f0ab7a3fbaa2ce2918ee85240313def6076de5b8dba161f7a80b`.
The nominal download was 1,216,043 bytes with SHA-256
`a3a3131a8e29145f072c4eea4d98d632849b3cf1b8a076c8ddbfe78f03c355f8`.
Both one-file CLI invocations returned `EVIDENCE_VERIFIED` with
`device_gate_decision=UNVERIFIED`, `d1_go=false`, and
`authority_status=AUTHORITY_NOT_ISSUED`.

Headed Chromium showed the persistent disclosure
`Bằng chứng mô phỏng — không phải xác minh thiết bị, D1_GO hay quyền thu dữ liệu.`
Console errors/warnings were 0/0. At 360 CSS pixels,
`scrollWidth=345` and horizontal overflow was false. Screenshot:
`output/playwright/m2-s2d-monitor.png`, SHA-256
`f06485122195f581a0420a35e8b21ed4c036a3d6d4e91ab3d3f02753f04b1707`.

## RP2 and cleanup

```text
source_tool_inventory_count=47
policy_preimage_count=36
static_bindings_digest=7204b1d53dbac8d5fd7f057c9b5a63e3fde10ec4c68111e4fa2b0ef9312880d3
candidate_exact_bytes_sha256=46221d85c38df2e44b62d688ff5a162519f215078462ef6f54bc47b65c75abd0
binding_schema_exact_bytes_sha256=23d742592c018343767ff8b670e1a253f7e2e2cbdf1a91c4829e8dc7bf30a9d3
TEMP_ROOT_COUNT=0
PDU_PROCESS_COUNT=0
PDU_LISTENER_COUNT=0
```

## Verification gates

```text
focused_s2a_through_s2d_regressions=PASS
web_tests=81/81 PASS
web_typecheck_lint_build=PASS
research_suite=69/69 PASS
python_collection=935
python_full_suite=935/935 PASS
ruff=PASS
strict_mypy=PASS
rp2_check=PASS
governance_consistency=3/3 PASS
release_manifest=PASS
package_s2d_match_count=0
```

An earlier full invocation crossed the local/UTC calendar boundary at
midnight and produced `934/935`: the request validator used the host-local
date while the M1 backend used UTC for the same retention decision. The
backend now uses the host-local calendar consistently; the focused regression
and the subsequent full `935/935` invocation passed. This correction does not
change S2D authority or RP2 bindings.

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

This receipt is source-runtime evidence only. It is not physical/device,
participant, model-performance, package, research-readiness, collection,
deployment, external-submission, or release evidence.
