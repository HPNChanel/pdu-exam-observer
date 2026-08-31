# M2-R0 Static Authority Re-entry Receipt

Date: `2026-08-30`

Status: `M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`

## Current source/static evidence

- Environment: `.venv\Scripts\python.exe`.
- RP2 static check: `PASS`.
- Canonical proposal SHA-256:
  `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
- `static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`
- `candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`
- `binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`
- Inventory: 24 source/test/script artifacts plus 3 lock/model artifacts,
  27 total, and 21 policy preimages.

The digests were recomputed directly from the current exact candidate and
schema bytes. The static bindings digest uses canonical compact, sorted-key,
UTF-8 JSON with non-finite numbers prohibited. The RP2 builder accepted the
current files with `--check`; it was not run with `--write`.

## Historical separation

The earlier A0 bound to
`f582e6a284d5f3afcbe51d37a74ee9bcdb982537e2c7da7c81ba14bb0ef7c5c9`
is `HISTORICAL_CONSUMED_TERMINAL_NON_AUTHORIZING`. It is closed, non-reusable,
and cannot transfer to B0-R2. Earlier RP2 tuples remain historical evidence
only and are not current controlling identities.

## Binding authority ceiling

```text
bootstrap_provisioning_status=UNPROVISIONED
fresh_a0_status=NOT_ISSUED
a1_status=NOT_OPENED
x0_status=BLOCKED
authority_status=AUTHORITY_NOT_ISSUED
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
```

M2 physical/native work remains unopened. No bootstrap bundle, signing
identity, provisioning receipt, PreparedAuthority, WorkerGrant, capability,
Job, camera/device evidence, FFmpeg/MediaPipe run, participant evidence, audio,
network, raw retention, retry, or collection authority was created or invoked.

## Receipt ceiling

This document is a source/static consistency receipt. It is not a signature,
A0, PreparedAuthority, WorkerGrant, capability, launch instruction, device
decision, M2 exit receipt, research approval, collection approval, package
receipt, or release claim. The runtime, public APIs, schemas, RP2 candidate,
package, and authority behavior are unchanged.
