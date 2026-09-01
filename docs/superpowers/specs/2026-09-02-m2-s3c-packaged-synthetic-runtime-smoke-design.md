# M2-S3C Packaged Synthetic Runtime Smoke Design

```text
document_status=USER_APPROVED_DIRECTION_A_FULL_SPEC_AND_PLAN_READY_FOR_IMPLEMENTATION
approved_direction=A_EXTERNAL_NO_ARGUMENT_PACKAGED_SMOKE_HARNESS
```

## Outcome

Run the exact ignored S3B Windows candidate twice on the build host. Each
candidate process serves only the two canonical loopback origins, authenticates
the monitor API, and runs built-in `PREFLIGHT_60S` followed by `NOMINAL_20M`.
Both minimized projections must be byte-identical before publishing:

```text
M2_S3C_PACKAGED_SYNTHETIC_RUNTIME_SMOKE_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY
```

This closes only
`GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT` for the current candidate.
It is not camera/device evidence, clean-machine or same-host portability,
research readiness, distribution readiness, or release authority.

## Fixed inputs

```text
s3b_receipt_sha256=c3d67bd842cc56ae7f377350ced3be56b09fdca9ec1e161d3d4805407c0a36bf
candidate_executable_sha256=432b82534448d5e32c10ecd2099ee7267dc5e2f7d0079a3782c9d9db9861610d
candidate_manifest_sha256=5d796d341f20d449dc4ff469cc315e6a815506195d739166fe550a2ba8039749
candidate_tree_sha256=80364f89c49affcd15b74e53d07b9b3cd0545055d5c9c4780e869a5417dd7009
candidate_readme_sha256=653585fd4c0e25a81ebca9ed1107d791ac8494cfffdea26370d005a41bff7570
candidate_static_bindings_digest=e1ab400a388df7c573a177494a46de9af07c85e62ca0f1c95c4a5c3c9211d626
candidate_exact_bytes_sha256=d6c523d74f3188a43f060721073c3671ade0a6fa20e15fde583b6eeb84735d10
candidate_binding_schema_sha256=eb0a3df699c5a60a47e6419876fee64a7003ea7afa628ec746f01d180fe1a3c8
```

The candidate source revision remains the S3B tuple. A separate final S3C RP2
tuple identifies the external smoke harness and its tests; the harness must not
be represented as packaged code.

## Interface

`scripts/run_m2_s3c_packaged_smoke.py` exposes a parameterless
`run_packaged_smoke()` and a no-argument CLI. Any argument exits `2` with
`REQUEST_INVALID` before candidate execution. Success exits `0`; failure exits
`2`. Stdout is one canonical JSON line and stderr is empty. Output never
contains a bearer token, PIN, PID, port, username, local path, captured child
output, traceback, or exception text.

Failure codes are closed:

```text
REQUEST_INVALID
PLATFORM_UNSUPPORTED
S3B_RECEIPT_MISMATCH
CANDIDATE_INPUT_MISMATCH
MANIFEST_MISMATCH
PROCESS_START_FAILED
HEALTH_TIMEOUT
LOOPBACK_SCOPE_VIOLATION
AUTHENTICATION_FAILED
SYNTHETIC_RUN_REJECTED
SYNTHETIC_RUN_TIMEOUT
SYNTHETIC_RECEIPT_INVALID
RUN_REPRODUCIBILITY_MISMATCH
AUTHORITY_CEILING_VIOLATION
PROCESS_CLEANUP_FAILED
TEMP_CLEANUP_FAILED
UNEXPECTED_FAILURE
```

## Runtime contract

Each of exactly two process invocations uses an owned
`packaging/candidates/.pdu-m2-s3c-*` root and process-only environment:

```text
PDU_RUNTIME_MODE=m2synthetic
PDU_OPEN_BROWSER=0
PDU_REVIEWER_PIN=m2-s3c-smoke-process-only
PDU_EXAM_PORT=<owned distinct free loopback port>
PDU_MONITOR_PORT=<owned distinct free loopback port>
TEMP=<owned root>
TMP=<owned root>
```

The harness verifies exam and monitor health, inspects listeners for only
`127.0.0.1` or `::1`, authenticates the reviewer, then submits fixed
idempotency keys `m2-s3c-preflight-0001` and `m2-s3c-nominal-0001`. Preflight
must be sequence 1 with 977 observations; nominal must be sequence 2 with
18,077 observations. Both must be terminal, persisted,
`BACKEND_CONTRACT_PASS`, simulated, device-unverified, and non-authorizing.
No S2D evidence endpoint is called.

Child output is captured only in the owned root. The process tree is terminated
with fixed `taskkill.exe /PID ... /T /F`, so the receipt records forced
termination and `graceful_shutdown_verified=false`. The root is removed only
after validating it as a direct child of the candidate parent. Process,
listener, temp-root, and candidate pre/post hash checks must all pass.

## Receipt and authority

The canonical envelope contains `schema_version`, `artifact_kind`, `status`,
`body`, and `body_sha256`. The closed body contains the result/date, S3B
receipt, candidate source revision, smoke harness revision, candidate binding,
fixed smoke contract, both invocation projections, reproducibility, runtime
boundary, gap projection, and authority ceiling.

The API's conservative S2C-era `package_contains_integration=false` remains
unchanged and is classified as
`CONSERVATIVE_SOURCE_ERA_DISCLOSURE_NOT_CANDIDATE_ATTESTATION`. S3B static
archive/manifest evidence controls
`candidate_package_contains_integration=true`. The candidate README remains an
immutable conservative pre-smoke build snapshot.

```text
historical_package_unchanged=true
candidate_package_unchanged=true
candidate_package_contains_integration=true
smoke_execution_scope=LOCAL_SYNTHETIC_CANDIDATE_ONLY
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
```

## Stop conditions

Do not publish the S3C marker if a fixed input changes, a listener is not
loopback, health/auth/run/accounting fails, authority opens, the two projections
differ, candidate bytes change, cleanup is incomplete, output leaks protected
values, or any required RP2/test/manifest gate fails. The CLI has no automatic
retry. A failed real smoke requires new user direction before another run.

