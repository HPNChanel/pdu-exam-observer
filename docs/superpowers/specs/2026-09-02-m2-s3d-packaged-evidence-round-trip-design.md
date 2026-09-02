# M2-S3D Packaged Evidence Round-Trip Design

document_status=USER_APPROVED_FOR_IMPLEMENTATION
approved_direction=A_SAME_EXECUTABLE_STDIN

## Outcome

M2-S3D creates a new deterministic current-source candidate and verifies, on
the build host only, that its authenticated monitor API exports canonical S2D
evidence and that the same packaged executable reproduces both fixed synthetic
runs exactly.

Maximum status:

```text
M2_S3D_PACKAGED_SYNTHETIC_EVIDENCE_ROUND_TRIP_LOCALLY_VERIFIED_SAME_HOST_ONLY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY
```

This closes GAP-04 and GAP-05 for the S3D candidate. GAP-06 and GAP-08 remain
open. S3B/S3C candidate bytes and receipts remain historical and immutable.

## Packaged protocol

`PDU_RUNTIME_MODE=m2synthetic-reproduce` dispatches before the loopback
launcher. It accepts no arguments, reads at most 4,000,001 bytes from stdin,
and emits exactly one canonical JSON line. Exit 0 is reserved for
`EXACTLY_REPRODUCED`; every other classification exits 2. The mode accepts no
path, URL, output directory, camera, audio, participant, or device input and
must not open a listener or browser.

The application revision binding covers the synthetic pipeline, reproduction
core, packaged protocol, and `__main__` dispatch. Legacy bundles can remain
integrity-valid but cannot be called same-revision evidence.

## Candidate and runtime flow

The ignored candidate root is `packaging/candidates/m2-s3d-round-trip`. Two
isolated PyInstaller builds must produce byte-identical trees. The manifest
uses the final pre-build RP2 tuple and retains `test_receipts=[]`.

The no-argument S3D harness runs two independent cycles. Each cycle starts one
loopback-only candidate server, runs preflight then nominal, downloads and
validates both evidence bundles, terminates the server tree, then starts the
same executable twice in reproduction mode via stdin. The two minimized cycle
projections must be byte-identical. The full harness therefore starts exactly
six candidate processes and performs no retry.

## Trust boundary

All bundles, logs, databases, and replay files live only under an owned
candidate-parent temporary root. Successful closure requires all processes,
listeners, and temporary roots to be gone and candidate bytes unchanged.
Receipts contain only hashes and minimized projections.

The authority ceiling remains fail-closed: camera/device and participant
authority are false, `device_gate_decision=UNVERIFIED`, `d1_go=false`,
`same_host_portable_verified=false`, `clean_machine_verified=false`,
`distribution_ready=false`, `release_authorized=false`, and
`authority_status=AUTHORITY_NOT_ISSUED`.
