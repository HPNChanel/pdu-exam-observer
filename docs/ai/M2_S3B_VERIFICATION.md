# M2-S3B Verification

Status:
`M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY`

## Evidence

- `OBSERVED`: build A and build B produced the same candidate tree SHA-256:
  `80364f89c49affcd15b74e53d07b9b3cd0545055d5c9c4780e869a5417dd7009`.
- `OBSERVED`: the candidate executable SHA-256 is
  `432b82534448d5e32c10ecd2099ee7267dc5e2f7d0079a3782c9d9db9861610d`.
- `OBSERVED`: recursive executable/PYZ inventory contains all 11 required
  current-source synthetic modules; inventory digest is
  `1a26de9f12adad66cfd72d73b3d17b52c2d7c0c7f6c1e5ce4c7aebca7774493e`.
- `OBSERVED`: isolated and packaged frontend tree digests are both
  `1e935e8dcdea79ab83ed769a21cafbdb55cb33f2fa8a7f97510bf7e75b988826`.
- `OBSERVED`: candidate and detached manifest SHA-256 is
  `5d796d341f20d449dc4ff469cc315e6a815506195d739166fe550a2ba8039749`.
- `SOURCE_VERIFIED`: candidate source identity is RP2 tuple
  `e1ab400a388df7c573a177494a46de9af07c85e62ca0f1c95c4a5c3c9211d626` /
  `d6c523d74f3188a43f060721073c3671ade0a6fa20e15fde583b6eeb84735d10` /
  `eb0a3df699c5a60a47e6419876fee64a7003ea7afa628ec746f01d180fe1a3c8`.

```text
package_integration_receipt_sha256=c3d67bd842cc56ae7f377350ced3be56b09fdca9ec1e161d3d4805407c0a36bf
static_bindings_digest=e1ab400a388df7c573a177494a46de9af07c85e62ca0f1c95c4a5c3c9211d626
candidate_exact_bytes_sha256=d6c523d74f3188a43f060721073c3671ade0a6fa20e15fde583b6eeb84735d10
binding_schema_exact_bytes_sha256=eb0a3df699c5a60a47e6419876fee64a7003ea7afa628ec746f01d180fe1a3c8
historical_package_unchanged=true
candidate_package_built=true
candidate_package_contains_integration=true
packaged_runtime_smoke_verified=false
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
```

GAP-01, GAP-02, and GAP-07 are `CLOSED_FOR_CURRENT_CANDIDATE`. GAP-03,
GAP-04, GAP-05, GAP-06, and GAP-08 remain `OPEN`.

## Verification closure

`OBSERVED` on `2026-09-01`:

- Two read-only candidate checks returned byte-identical canonical receipts
  with exit code `0`.
- Historical and candidate release manifests both returned
  `manifest verified`.
- S3B focused tests: `8 passed`.
- RP2 artifact tests: `6 passed`; governance consistency: `3 passed`;
  research suite: `69 passed`.
- Ruff and strict mypy passed.
- Collection was exactly `958 tests collected`; one full invocation returned
  `958 passed in 199.64s`.
- Proposal SHA-256 remained
  `2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5`.
- `S3B_TEMP_ROOT_COUNT=0`, `PDU_PROCESS_COUNT=0`, and
  `PDU_LISTENER_COUNT=0`.

`OBSERVED_IMPLEMENTATION_NOTE`: the first double-build comparison included a
PyInstaller intermediate executable outside the intended one-folder bundle,
creating a false reproducibility mismatch. The comparator was corrected to
the specified closed payload: candidate bundle plus detached manifest. A
provisional RP2 tuple was therefore superseded; only the final tuple recorded
above controls this candidate. No candidate bytes were promoted before the
corrected A/B comparison passed.

## Boundary

This is static same-host candidate evidence. The executable was not run.
Packaged runtime smoke, same-host portability, clean-machine portability,
S2D/S2E packaged round trips, distribution, signing, and release remain
unverified or unauthorized. Physical camera, participant collection,
research readiness, collection authority, and `D1_GO` remain closed.
