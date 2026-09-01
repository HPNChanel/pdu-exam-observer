# M2-S2C Source Runtime Verification Receipt

Date: `2026-08-31`

Status:
`M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY`

## Scope

`OBSERVED`: the source launcher ran with `PDU_RUNTIME_MODE=m2synthetic` on the
two canonical loopback origins. The authenticated monitor origin exposed the
optional synthetic-run API and panel. The exam origin returned HTTP `404` for
`/api/v1/synthetic-runs`.

This receipt covers source runtime only. It is not package, physical-device,
model-performance, participant, research-readiness, collection, deployment, or
release evidence.

## Browser evidence

The production web build was served by the source launcher. A Chromium
session completed these interactions:

1. opened the task-local monitor loopback origin on port `18766`;
2. authenticated with the task-local reviewer PIN;
3. observed the exact banner
   `MÔ PHỎNG — KHÔNG CAMERA — KHÔNG CẤP QUYỀN THU DỮ LIỆU`;
4. ran `PREFLIGHT_60S` to terminal `BACKEND_CONTRACT_PASS`;
5. ran `NOMINAL_20M` to terminal `BACKEND_CONTRACT_PASS`;
6. observed the bounded interpretation
   `Contract synthetic đạt; thiết bị vẫn chưa được xác minh.`

Screenshot:
`output/playwright/m2-s2c-monitor.png`

```text
sha256=a780bca5ab512d430c03e51aa24856a50ce33c5b3d1b576cf3255a1fd34fcc8a
```

`OBSERVED`: browser console contained zero errors and zero warnings. Network
evidence showed one authenticated list GET, one POST per user-selected run, and
GET-only polling until terminal. No automatic POST retry was observed. The
document had no horizontal overflow at either 1280px or 360px viewport width.

## Runtime and cleanup evidence

```text
monitor synthetic route=200 after reviewer authentication
exam synthetic route=404
TEMP_ROOT_COUNT after shutdown=0
PDU_LISTENER_COUNT after shutdown=0
PDU_PROCESS_COUNT after shutdown=0
```

The temporary root existed only while the source runtime was active and was
removed during service shutdown. The runtime did not use a configured M1/M1-R1
storage root.

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

No camera, audio, device enumeration, participant contact, consent creation,
export, real deletion, package rebuild, external submission, deployment, or
release occurred.
