# M2-S3E-A Same-Host Isolated Portability and Clean-Environment Handoff Design

```text
document_status=USER_APPROVED_FOR_IMPLEMENTATION
approved_direction=A_SAME_HOST_ISOLATED_PORTABILITY_AND_CLEAN_ENVIRONMENT_HANDOFF
```

## Purpose

M2-S3E-A preserves the deterministic M2-S3D candidate and packages it with a
closed, deterministic Windows PowerShell 5.1 verification protocol. The exact
handoff ZIP is exercised at two same-host relocation paths, one containing
spaces and one containing Unicode plus spaces. Each relocation executes one
complete synthetic preflight/nominal/export/reproduction cycle.

The maximum status is:

```text
M2_S3E_A_SAME_HOST_ISOLATED_PORTABILITY_LOCALLY_VERIFIED_CLEAN_ENVIRONMENT_HANDOFF_READY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY
```

This establishes only `same_host_portable_verified=true` and
`clean_environment_handoff_ready=true`. It does not establish a clean-machine
receipt, air-gapped execution, distribution readiness, physical-device
evidence, research readiness, or release authority.

## Immutable source candidate

The handoff binds the existing M2-S3D candidate without rebuilding it:

```text
s3d_round_trip_receipt_sha256=4d8a862408aec0470d86b084f1abdc9baa323a3ee53cb57dfe780c3d6e2258ed
s3d_build_validation_sha256=432c906b2a32d84d5d82509d27cfa3882500657ce97e544e7fb71513b0754b94
s3d_executable_sha256=9d9aabe6b6176fabb1db423924d8c27a8ee9478d302b421680dc8bfc989c66aa
s3d_manifest_sha256=8702963dddd8b9d2761120fce8875d9fd181177eb15f1576e72e7354ad3ae216
s3d_candidate_tree_sha256=64686518c09679f98b6f3c01805535ca9aad50413781424a08020c2460d017e1
static_bindings_digest=034eb3e19f88377529f5ffc37c077938b42563a447d1d6e6a481c1b635cbf607
candidate_exact_bytes_sha256=ced85d39533de902da652c4a7f56ea85eaf4891a5d8b27946badf8aebcae5c79
binding_schema_exact_bytes_sha256=7125de572f5a78b986a768b484315b818e1c630d10ada48ea31bd0915c300058
```

The historical package, S3B/S3C/S3D receipts, S3D candidate, manifests, and
canonical proposal remain byte-identical.

## Handoff artifact

The generated ignored artifact is
`packaging/handoffs/m2-s3e-clean-environment/M2-S3E-CLEAN-ENVIRONMENT-HANDOFF.zip`.
It contains the S3D bundle, detached release manifest, a canonical handoff
manifest, exact S3D build/round-trip receipts, a non-authorizing README, a
Windows PowerShell 5.1 verifier, and an unfilled response template.

The ZIP uses sorted members, fixed `2026-09-02T00:00:00Z` metadata, normalized
file modes, UTF-8 names, and fixed DEFLATE settings. Two independently built
ZIP byte streams must match before materialization. Absolute paths, drive
prefixes, `..`, duplicate members, symlinks, junctions, and reparse leaves are
rejected. Existing different output is never overwritten.

## Clean-environment verifier

`VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1` is no-argument and resolves every input
relative to its own directory. It requires Windows x64, Windows PowerShell
Desktop 5.1 or newer, and a non-elevated process. The candidate process receives
a system-only `PATH` and owned `TEMP`, `TMP`, `APPDATA`, and `LOCALAPPDATA`.

The verifier does not require Python, Node, npm, Git, administrator rights, or
Internet. It does not change firewall, registry, machine/user PATH, or user
profile. It starts one synthetic server, executes `PREFLIGHT_60S` and
`NOMINAL_20M`, downloads two S2D bundles, terminates the server, and invokes the
same executable twice in `m2synthetic-reproduce` mode through stdin. Both
reproductions must be `EXACTLY_REPRODUCED`.

Only loopback listeners/connections are accepted. The evidence label is
`LOOPBACK_ONLY_OBSERVED`; the verifier always keeps
`air_gapped_machine_verified=false` and `clean_machine_verified=false`.

The response is one bounded canonical JSON line, also written to the fixed
leaf `M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.json`. It excludes raw bundles, paths,
user/host identity, tokens, PINs, PIDs, ports, tracebacks, and exception text.
Its external classification remains `UNVERIFIED_PENDING_SOURCE_IMPORT`; only a
future M2-S3E-B task may validate a response returned from a different Windows
environment.

## Same-host portability harness

The Python harness extracts the exact handoff ZIP into two owned roots:

```text
relocation_a=path with spaces
relocation_b=Unicode path with spaces
```

It calls `powershell.exe`, never `pwsh.exe` or source Python, and validates the
closed response schema and digest projection. Both projections must be
byte-identical. Each root must be removed after process-tree/listener checks,
and the S3D candidate tree must remain unchanged.

The S3E-A receipt records two relocations, two full cycles, six candidate
processes, standard-user observation, child-PATH isolation, loopback-only
network observation, deterministic handoff binding, cleanup evidence, and the
unchanged authority ceiling.

## Authority and gaps

```text
same_host_portable_verified=true
clean_environment_handoff_ready=true
clean_machine_verified=false
distribution_ready=false
release_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT=OPEN
GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT=OPEN
```

M2-S3E-A does not rebuild or promote a candidate, close GAP-06/GAP-08, contact
a participant, transmit evidence, sign, deploy, tag, or release.

## Threat controls

- ZIP traversal and ambiguous members: closed normalized inventory and
  duplicate/reparse rejection.
- Installed-runtime dependency mistaken for portability: system-only child
  `PATH` and packaged executable-only execution.
- Same-host proof mistaken for clean-machine proof: separate flags and an
  external response classification that remains pending import.
- LAN or Internet use: fixed loopback hosts and process-tree connection
  inspection; no firewall mutation or air-gap claim.
- Candidate mutation: pre/post tree and manifest verification.
- Secret/path disclosure: bounded receipts with a closed field set.
- Unsafe cleanup: direct-child owned roots, marker validation, resolve checks,
  and reparse rejection before recursive removal.

