# GOV-P1 Synthetic Withdrawal and Deletion Rehearsal Design

Version: `1.0`

Status: `APPROVED_FOR_IMPLEMENTATION`

## Outcome

GOV-P1 shall exercise the existing M1 participant-wide withdrawal contract
with synthetic process data in a runner-owned temporary directory. It shall
delete only its four manifest-owned synthetic fixture files, prove that an
out-of-manifest sentinel was not deleted, dispose the temporary root, and emit
a deterministic EthicsDataReceipt plus an institutional-review dossier.

The successful ceiling is:

```text
GOV_P1_SYNTHETIC_REHEARSAL_VERIFIED
PRODUCTION_RECONCILER_UNIMPLEMENTED
EXTERNAL_APPROVAL_PENDING
research_ready=false
collection_authorized=false
participant_collection_authorized=false
physical_camera_access_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
device_gate_decision=UNVERIFIED
d1_go=false
```

The rehearsal is governance/process evidence only. It is not participant,
camera, native, storage-control, institutional, production reconciler, model,
export, M2, M3, or research-performance evidence.

## Immutable inputs and exclusions

- The canonical proposal SHA-256 remains
  `2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5`.
- The GOV-P0 manifest SHA-256 remains
  `c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025`.
- GOV-P0, RP2, the B0.3 kit, and production M1 schema/API are not modified.
- No real person, consent issuance, retention decision, approved storage
  claim, camera, native code, network, export, A0/A1, or collection path is
  permitted.
- M1 withdrawal tasks remain `PENDING`; GOV-P1 may not update the database to
  simulate production reconciliation.

## Rehearsal contract

The CLI accepts no work-root or artifact-path argument. It allocates its own
`TemporaryDirectory`, starts `M1Backend` with a fixed clock and `UNKNOWN`
encryption/ACL states, and creates one synthetic participant with two
retention-pending research sessions. It confirms no consent.

Four fixed manifest-owned fixture paths are created with create-new semantics:

```text
artifacts/session-a/raw-a.bin
artifacts/session-a/derived-a.json
artifacts/session-b/raw-b.bin
artifacts/session-b/derived-b.json
```

The M1 registry uses four fixed synthetic artifact identifiers and two
parent-child edges. A fixed out-of-manifest `sentinel.keep` proves bounded
deletion. Withdrawal is requested from both sessions with distinct idempotency
keys. Both responses must contain the same non-empty opaque receipt identifier.

The runner must prove two terminal/collection-blocked sessions, four
invalidated artifacts, four pending withdrawal tasks, refusal of late artifact
registration and late write-intent creation, and `start_research_session=false`.
M1 has no export capability; the receipt must record
`NOT_IMPLEMENTED_IN_M1_NOT_EXERCISED` rather than claim an export rejection.

## File deletion boundary

Only contract-listed relative paths beneath the runner-owned root may be
opened or unlinked. Absolute, drive-qualified, UNC, empty, dot, dot-dot,
backslash-alias, symlink, reparse, missing, non-file, size-mismatched, or
hash-mismatched targets fail closed. The original root is inspected before
resolution; every component is inspected; and the target file identity is
rechecked immediately before unlink. Empty fixture directories may be removed
only after all owned files are gone. Recursive deletion of a caller-selected
path is absent.

This is a deterministic synthetic rehearsal, not a hardened production delete
service. The receipt therefore records
`concurrent_same_account_mutation_resistant=false`: a hostile same-account
process could still race the final identity check and unlink because GOV-P1
does not use retained native directory/file handles. That production control
remains outside this no-schema/no-native slice.

The M1 SQLite store is closed before temporary-root disposal. No temp path,
opaque identifier, pseudonym, SQLite bytes, or fixture payload appears in the
receipt or bounded CLI output.

## GOV-P1 pack

`research/pre_collection/gov_p1/v1/` contains three reviewed sources and
three generated artifacts:

1. `rehearsal-contract.v1.json`
2. `external-decision-record.template.v1.json`
3. `submission-dossier.vi.draft.v1.md`
4. `synthetic-ethics-data-receipt.v1.json`
5. `gov-p1-pack.manifest.v1.json`
6. `gov-p1-pack.validation.v1.json`

All JSON is canonical UTF-8 with sorted keys, no NaN, exact closed fields,
one LF, and body SHA-256 where an envelope applies. The generated receipt
stores only deterministic counts, booleans, statuses, logical paths, source
hashes, and equality/non-empty assertions. Opaque runtime values are verified
but redacted.

The three reviewed sources are pinned by exact file SHA-256, not merely by
self-consistent body hashes:

```text
rehearsal-contract.v1.json = e7b7b17e4cd977a5b95d7d576d69d696f251e51109aa9552b1f9e0bc82a61087
external-decision-record.template.v1.json = 549212658ee2e4210a2a72396ead4a1a40afa0ac4bb91854f84bb5c87691f130
submission-dossier.vi.draft.v1.md = 45b29e79698ee39a0377243980d463bba1d718c3ee27b9f49ebb2c502f6c3afd
```

The live `m1.py` and runner arguments must resolve to their canonical checkout
paths; an identical copied source is rejected. Generated leaves are written to
create-new temporary files in the pack root, flushed, revalidated, and replaced
atomically. Existing link/reparse leaves and root substitutions fail closed.

The external decision template remains `DRAFT_BLOCKED`: approval/contact/
consent/retention/storage fields are null or unverified and collection is
false. The Vietnamese dossier remains `DRAFT_FOR_INSTITUTIONAL_REVIEW`; it is
not an invitation, submission receipt, or institutional decision.

The validator binds the proposal, GOV-P0 manifest, live runner, live `m1.py`,
and rehearsal contract. Its blocking gates are the fourteen GOV-P0 gates plus
`PRODUCTION_RECONCILER_UNIMPLEMENTED`.

## Interfaces and failure behavior

Both scripts default to read-only `--check`. `--write` replaces only their
fixed generated outputs after source validation. Success exits `0`; rejection
exits `2`. Stdout is exactly one canonical JSON line with bounded fields;
unexpected exceptions collapse to `UNEXPECTED_FAILURE` without traceback or
path disclosure.

The rehearsal exposes a Python `run_rehearsal()` function for tests and the
pack builder exposes `write_pack()` and `check_pack()`. Failure codes are
bounded and sanitized; they distinguish contract/path/link/fixture, M1 setup,
withdrawal/idempotency/state/task, late mutation, deletion/sentinel/disposal,
receipt, file-set, manifest, validation, and immutable-input failures.

## RoutingReceipt

```json
{"decision_owner":"root","execution_effort":"xhigh","execution_model_family":"Sol","participant_collection_authorized":false,"physical_camera_access_authorized":false,"routing_basis":"HPN_V6_RESEARCH_PROFILE","schema_version":1}
```

This receipt selects a research profile; it supplies no operational authority.
