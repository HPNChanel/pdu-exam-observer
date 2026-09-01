# M2-S3B Deterministic Current-Source Package Integration Design

```text
document_status=USER_APPROVED_DIRECTION_A_PLAN_READY_FOR_IMPLEMENTATION
approved_direction=A_SIDE_BY_SIDE_DOUBLE_BUILD
```

## Outcome

M2-S3B builds a local Windows candidate twice from the current S2A-S2E
source revision and accepts it only when the two complete package trees are
byte-identical. The historical package remains immutable and the candidate is
not executed, promoted, signed, distributed, or described as a release.

Maximum status:

```text
M2_S3B_CURRENT_SOURCE_PACKAGE_CANDIDATE_DETERMINISTICALLY_INTEGRATED_STATICALLY_VERIFIED_SMOKE_PENDING_NO_RELEASE_AUTHORITY
```

The candidate closes only S3A gaps 01, 02, and 07. Packaged runtime smoke,
S2D export, S2E reproduction, receipt aggregation, and clean-environment
portability remain open for S3C-S3F.

## Build contract

The builder exposes `build_candidate()` and `check_candidate()` and a closed
CLI with `--build` or the default read-only `--check`. It accepts no caller
path, URL, device, output root, or arbitrary command. Success is exit 0;
rejection is exit 2; stdout is one canonical JSON line and stderr is empty.

The same transient tool environment is used for both builds. The contract is
Windows 11 x64, Python 3.11.9, Node 24.11.0, npm 11.14.1, uv 0.10.10,
PyInstaller 6.10.0, `PYTHONHASHSEED=1`, `SOURCE_DATE_EPOCH=1788220800`, and
fixed manifest time `2026-09-01T00:00:00Z`. The frontend is built into an
owned temporary directory; `apps/web/dist` is not rewritten.

The new PyInstaller spec uses explicit current-source hidden imports for the
S2A-S2E integration modules. Recursive executable/PYZ inventory, not a build
TOC alone, must contain every required module. The packaged frontend tree
must be byte-identical to the isolated frontend build. A candidate-specific
README repeats the synthetic-only and no-authority boundary.

## Provenance and no-overwrite behavior

Before and after building, the builder verifies the canonical S3A audit,
historical package manifest, and immutable historical hashes. The final RP2
tuple is generated after the S3B builder, spec, README, and tests stabilize;
that tuple is then embedded as the source revision in both builds.

Build A and B are staged in different owned temporary roots. Their closed
records contain repository-relative path, byte size, and SHA-256 for every
bundle file plus the detached manifest. Any mismatch fails closed. An
existing canonical candidate is retained when identical and rejected when
different; no force overwrite exists.

## Evidence and authority

The canonical receipt is a closed, body-hashed JSON envelope. It records the
S3A audit binding, final RP2 tuple, toolchain contract, build A/B tree digests,
candidate manifest/executable hashes, archive inclusion result, frontend
tree equality, README boundary, candidate gap projection, and authority
ceiling.

`candidate_package_contains_integration=true` describes static candidate
bytes only. Packaged runtime smoke, same-host portability, clean-machine
portability, distribution readiness, release authorization, physical camera,
participant collection, research readiness, and collection authority remain
false, unverified, or unissued.

## Failure boundary

The bounded failure codes are `REQUEST_INVALID`, `PLATFORM_UNSUPPORTED`,
`SOURCE_INPUT_MISMATCH`, `HISTORICAL_PACKAGE_MISMATCH`, `RP2_INVALID`,
`TOOLCHAIN_UNAVAILABLE`, `TOOLCHAIN_MISMATCH`, `FRONTEND_BUILD_FAILED`,
`PYINSTALLER_BUILD_FAILED`, `ARCHIVE_INVENTORY_INVALID`,
`PYTHON_RUNTIME_INCLUSION_MISMATCH`, `FRONTEND_INCLUSION_MISMATCH`,
`BUILD_REPRODUCIBILITY_MISMATCH`, `CANDIDATE_README_INVALID`,
`CANDIDATE_EXISTS_MISMATCH`, `MANIFEST_MISMATCH`, `RECEIPT_MISMATCH`,
`OUTPUT_WRITE_FAILED`, `CLEANUP_FAILED`, and `UNEXPECTED_FAILURE`.

No failure may emit an absolute path, username, traceback, exception text,
false artifact hash, or authority escalation.
