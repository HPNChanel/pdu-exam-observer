# M2-S3B Verification

Status:
`M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY`

## Evidence

- `OBSERVED`: build A and build B produced the same candidate tree SHA-256:
  `29a0d7749e8069978f54d9c0087261fe709da3c016c73acca9cffb5034f8c37e`.
- `OBSERVED`: the candidate executable SHA-256 is
  `9a90abf58e7a0c36c5050c44213ec2f478070b5c8bfdd05570bed4bdc40efbec`.
- `OBSERVED`: recursive executable/PYZ inventory contains all 14 required
  application and synthetic runtime modules; inventory digest is
  `18a9a5b219304a7607696a4c1a1ea8ac73e364a50001afab0b85ea42d9d9e07a`.
- `OBSERVED`: isolated and packaged frontend tree digests are both
  `1e935e8dcdea79ab83ed769a21cafbdb55cb33f2fa8a7f97510bf7e75b988826`.
- `OBSERVED`: candidate and detached manifest SHA-256 is
  `e0b279a1e667cc39e5c5f62d6aa169e6973c2c2f957f78118f86f9de972e620f`.
- `SOURCE_VERIFIED`: candidate source identity is RP2 tuple
  `a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f` /
  `a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639` /
  `3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca`.

```text
package_integration_receipt_sha256=bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd
static_bindings_digest=a7b0505cb283fb6998b3bc27aea155c78039b1dc5b7c0d4a11811d919cf9e16f
candidate_exact_bytes_sha256=a6f209b7184fee723911cc2c9385fdd8df06f3313458e3b107859fcb3835e639
binding_schema_exact_bytes_sha256=3acb8578f3e1666bfd7ca83f59312875e5c1678f56037c0fbc38773e872b14ca
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
- Final integrated collection was exactly `966 tests collected`; one full
  invocation returned `966 passed in 170.26s`.
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

This receipt remains static candidate evidence. Later execution is attested
separately by M2-S3C and does not change `packaged_runtime_smoke_verified=false`
inside this historical S3B receipt. Same-host portability, clean-machine portability,
S2D/S2E packaged round trips, distribution, signing, and release remain
unverified or unauthorized. Physical camera, participant collection,
research readiness, collection authority, and `D1_GO` remain closed.
