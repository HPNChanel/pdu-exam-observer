# M1-R1 Production Withdrawal Reconciler — Full Specification

Version: `1.0-approved-source-only`

Status: `APPROVED_FOR_SOURCE_ONLY_IMPLEMENTATION`

Implementation authorized: `true — source and runner-owned synthetic rehearsal only`

Real-data deletion authorized: `false`

Companion documents:

- `2026-08-30-m1-r1-production-withdrawal-reconciler-threat-model.md`
- `2026-08-30-m1-r1-production-withdrawal-reconciler-migration-design.md`

## 1. Decision and evidence ceiling

`USER_STATED`: after GOV-P1, the user requested a full specification, threat
model, and migration design for the production withdrawal reconciler.

`OBSERVED`: M1 schema v1 makes participant withdrawal terminal, invalidates
artifact lineage, and creates one `PENDING` `withdrawal_tasks` row per affected
artifact. It has no operation that deletes a bound artifact or changes a task
to `COMPLETED`.

`OBSERVED`: M2-P1 schema v2 adds manifest-owned technical-fixture paths and
hashes in a store intentionally separate from `M1Backend`. `M1Store` accepts
exactly ledger version 1 and therefore fails closed on a v2 or newer database.
The current v2 manifest accepts only deterministic or AI-rendered technical
fixtures; it is not a production participant-artifact manifest.

`OBSERVED`: GOV-P1 deleted four synthetic fixtures but deliberately left all
four M1 tasks `PENDING`. Its receipt records
`PRODUCTION_RECONCILER_UNIMPLEMENTED` and does not establish production
deletion, hostile same-account race resistance, storage controls, participant
authority, or collection readiness.

The maximum result of implementing the source-only slice described here is:

```text
M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY
production_reconciler_source_implemented=true
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

No document, passing test, migration fixture, synthetic deletion, reviewer
click, or local receipt may raise that ceiling.

## 2. Outcome

M1-R1 shall provide a durable, offline, Windows-only reconciliation subsystem
that can eventually satisfy participant withdrawal obligations without
accepting a path from browser input. It shall:

1. bind each affected artifact to one or more manifest-owned reconciliation
   targets before collection or export;
2. preserve the existing participant-wide terminal withdrawal receipt;
3. create a deterministic reconciliation plan over the current target set;
4. require fresh reviewer authentication and an explicit, short-lived,
   single-use operator confirmation bound to that plan;
5. execute each local deletion by a verified Windows file handle under the
   approved research root;
6. verify absence after deletion and preserve crash-recovery evidence;
7. represent external copies as human-attested obligations without network or
   cloud automation;
8. change legacy tasks to `COMPLETED` only after every target has an allowed,
   auditable terminal outcome; and
9. issue one canonical `ReconciliationReceipt` without identity, secrets,
   absolute paths, operator audit details, or raw media.

## 3. Scope

### 3.1 Included in the future implementation

- additive schema v3 and exact schema/ledger validation;
- explicit, non-automatic pre-collection migration from exact v1 or v2;
- one root owner and one reconciliation worker;
- local manifest-file targets beneath the configured research root;
- export-staging targets beneath a fixed server-derived export root;
- external-copy obligations identified only by `export_id` and manifest hash;
- participant-wide target planning from canonical artifact lineage;
- reviewer-only plan, challenge, execution, status, and attestation APIs;
- accessible Vietnamese monitor UI for explicit confirmation and status;
- bounded failure codes, append-only audit events, idempotency, leases, crash
  recovery, and canonical receipts;
- synthetic and mutation testing with runner-owned temporary roots.

### 3.2 Explicitly excluded

- any deletion during specification or implementation-plan work;
- automatic deletion at application startup;
- automatic retention-expiry deletion;
- deletion of identity-root records or signed consent;
- remote Google Drive, Colab, cloud, LAN, HTTP, or account automation;
- browser-supplied path, URL, command, executable, root, model, or destination;
- recursive directory deletion, directory cleanup, wildcard deletion, recycle
  bin semantics, secure overwrite, or claims about physical media erasure;
- modification or concealment of incident evidence;
- collection, camera, model, M2/M3 activation, institutional submission, or
  issuance of consent/retention/storage authority;
- protection against kernel compromise, administrator compromise, physical
  disk access outside approved encryption, or malware already controlling the
  same Windows account.

## 4. Selected architecture

Three approaches were considered:

1. **Delete inside the withdrawal request.** Rejected because filesystem work
   cannot commit atomically with SQLite, can exceed HTTP deadlines, and leaves
   ambiguous crash windows.
2. **Automatically resume a background deletion queue.** Rejected because a
   stale or replayed decision could delete after restart without fresh human
   confirmation.
3. **Durable plan, single-use confirmation, bounded worker, verified receipt.**
   Selected because it makes authority, crash state, and target evidence
   inspectable without weakening the offline architecture.

### 4.1 Components

`ResearchStoreV3`

- is the sole owner of a v3 operational SQLite database;
- composes the accepted v1 governance and v2 persistence invariants;
- holds the existing root, operational-directory, database, WAL/SHM, and
  lifetime lease guards before migration, recovery, or reconciliation;
- exposes a transaction seam to `M1Backend` rather than opening a second
  connection through legacy `M1Store`;
- refuses unknown ledger versions, schema drift, unsafe roots, a second owner,
  or unsupported filesystems.

`ReconciliationPlanner`

- starts only from the canonical participant withdrawal receipt;
- traverses participant sessions, invalidated artifacts, dependencies,
  withdrawal tasks, and registered targets inside one read transaction;
- rejects artifacts with zero targets, unregistered lineage, active write
  intents, mutable manifests, duplicate locator digests, or unexplained target
  state;
- emits a canonical plan body and SHA-256 digest; and
- returns only opaque IDs, pseudonyms, counts, target classes, and blockers to
  the browser—never a path.

`ConfirmationService`

- requires the monitor-origin reviewer bearer, current reviewer session, and a
  successful reviewer-PIN step-up performed no more than two minutes earlier;
- creates the challenge in the same server-side transaction as the step-up
  record, stores no PIN, and returns no reusable step-up credential to the
  browser;
- creates a random 256-bit challenge token, stores only its digest, and binds
  it to participant ID, withdrawal receipt ID, exact plan digest, current
  target-state version, reviewer session, step-up record, issue time, expiry,
  and one allowed action;
- binds an `ATTEST_EXTERNAL_DELETION` challenge to exactly one
  `EXTERNAL_COPY` target; an `EXECUTE_LOCAL_RECONCILIATION` challenge is bound
  to the complete current local-target plan and cannot attest any target;
- requires the operator to type the displayed phrase
  `DOI_SOAT <participant_pseudonym>`;
- treats the phrase as confirmation, not authentication or a secret;
- permits one successful consumption before the shared two-minute challenge
  and step-up expiry; records wall time for audit while enforcing elapsed-time
  expiry with a process-monotonic deadline; expires every still-issued
  challenge when the confirmation service starts again;
- rejects non-finite time evidence and revalidates reviewer session, wall time,
  and monotonic time under the root lock after planning and immediately before
  issue or consumption;
- transactionally revokes every issued challenge bound to a bearer on logout,
  replacement, or expiry, with one active confirmation-service callback per
  backend; and
- revokes the challenge when target state, reviewer session, plan digest, or
  participant state changes.

`ReconciliationCoordinator`

- has one in-process worker and one durable root lease;
- accepts only a consumed confirmation challenge;
- creates a durable run before starting any target;
- never resumes deletion automatically after restart;
- marks an interrupted run `RECOVERY_REQUIRED` and requires a new plan plus a
  new operator confirmation;
- processes targets in stable opaque-ID order, one at a time; and
- stops on the first unexplained or unsafe state.

`WindowsHandleDeletionPrimitive`

- is available only on Windows 11 x64 and a verified NTFS research root;
- derives every component from a server-owned manifest-relative path;
- opens root, ancestors, parent, and target with no-follow/reparse-aware Win32
  flags (`FILE_FLAG_OPEN_REPARSE_POINT`, plus
  `FILE_FLAG_BACKUP_SEMANTICS` for directories) and validates post-open
  identity and final location;
- retains parent and target handles across hash verification and disposition;
- rejects links, reparse points, multiple hard links, non-regular files,
  alternate path syntax, identity changes, and manifest mismatch;
- rechecks file identity, attributes, size, and link count through the retained
  handle immediately before setting disposition;
- requests `DELETE` access and uses `SetFileInformationByHandle` with
  `FileDispositionInfo`; and
- verifies the leaf is absent or detects a replacement before recording a
  successful target outcome.

`ExternalObligationService`

- never connects to an external account;
- represents an exported copy by opaque target ID, `export_id`, and bound
  manifest SHA-256 only;
- requires an explicit reviewer attestation against a persisted, current
  `APPROVED` institutional procedure-authority record; a free-form reference
  string is not authority;
- only reads procedure-authority records; creating, approving, revoking, or
  importing those records is a separate institution-authorized governance
  operation and has no browser route in this slice;
- stores operator identity/audit data locally and omits it from exports and the
  canonical participant receipt;
- labels the outcome `EXTERNAL_DELETION_ATTESTED`, never
  `MACHINE_DELETION_VERIFIED`.

## 5. Target registration contract

Every artifact that can contain participant-derived data must have at least one
target registered before its artifact registry state can become `VALID`.
Registration and artifact sealing commit atomically.

Target kinds:

| Kind | Locator source | Machine action | Terminal basis |
|---|---|---|---|
| `LOCAL_RESEARCH_FILE` | Server-derived relative path under research root | Handle-bound delete | `LOCAL_DELETION_VERIFIED` |
| `LOCAL_EXPORT_STAGING_FILE` | Server-derived relative path under fixed export staging | Handle-bound delete | `LOCAL_DELETION_VERIFIED` |
| `EXTERNAL_COPY` | `export_id` plus manifest SHA-256 | No network action | `EXTERNAL_DELETION_ATTESTED` |

Each target binds:

- opaque target and artifact IDs;
- target kind and root scope;
- canonical locator digest;
- manifest schema version and manifest SHA-256;
- expected byte size and SHA-256 for local files;
- server-derived normalized POSIX relative path for local files only;
- `export_id` for external copies only;
- creation time and immutable registration version.

Absolute paths, drive letters, UNC forms, colon/alternate-stream syntax,
backslashes, empty/dot/dot-dot components, non-NFC text, extra JSON fields, or
unbound targets fail closed. Windows reserved device names, trailing dots or
spaces, and case-fold collisions are also rejected before registration.

## 6. State model

The existing `withdrawal_tasks.status` remains exactly `PENDING|COMPLETED`.
Schema v3 adds detailed companion state instead of rebuilding the v1 table.

Target state:

```text
PENDING_CONFIRMATION
  -> IN_PROGRESS
       -> LOCAL_DELETION_VERIFIED      (local target kinds only)
       -> EXTERNAL_DELETION_ATTESTED   (`EXTERNAL_COPY` only)

IN_PROGRESS -> RECOVERY_REQUIRED
IN_PROGRESS -> BLOCKED
PENDING_CONFIRMATION -> BLOCKED
RECOVERY_REQUIRED -> IN_PROGRESS only after a new confirmation
```

`LOCAL_DELETION_VERIFIED` and `EXTERNAL_DELETION_ATTESTED` are terminal and
immutable. They are not interchangeable.

Run state:

```text
QUEUED -> RUNNING -> COMPLETED
                  -> BLOCKED
                  -> RECOVERY_REQUIRED
                  -> FAILED_TECHNICAL
```

`FAILED_TECHNICAL` never implies that a target is absent. `BLOCKED` requires
operator or institutional resolution. A run may be retried only through a new
plan and challenge; the original run remains immutable evidence.

The legacy task becomes `COMPLETED` only when every mapped target has the
terminal basis required by its immutable kind: local kinds require
`LOCAL_DELETION_VERIFIED`; `EXTERNAL_COPY` requires
`EXTERNAL_DELETION_ATTESTED`. Completion is one transaction that re-joins each
task, target kind/root scope, challenge action, execution type, plan,
participant, withdrawal receipt, and current procedure authority. Any missing,
cross-kind, stale, or mismatched row fails closed. A participant reconciliation
receipt becomes complete only when every participant task passes that query and
is `COMPLETED`.

## 7. End-to-end flow

### 7.1 Withdrawal

1. Existing M1 withdrawal marks the participant and every session terminal,
   blocks collection/export, invalidates lineage, and creates legacy tasks.
2. In the same transaction, v3 maps every task to every registered target.
3. A missing target binding never rejects or rolls back the participant's
   withdrawal. The withdrawal stays terminal, but the unmatched task remains
   `PENDING`, the planner reports `TARGET_BINDING_MISSING`, and no completed
   reconciliation receipt can be issued.
4. The canonical withdrawal receipt remains idempotent and participant-wide.

### 7.2 Plan and confirmation

1. Reviewer opens the monitor origin and re-enters the reviewer PIN; the server
   verifies it and creates a session-bound step-up record valid for at most two
   minutes.
2. `GET reconciliation` returns summary and blockers without paths.
3. `POST challenges` creates a single-use challenge bound to the current plan.
4. UI displays participant pseudonym, local/external counts, consequences,
   unresolved holds, and the exact confirmation phrase.
5. Operator types the phrase and submits `POST executions` with challenge token
   and idempotency key.
6. Server validates reviewer session, origin, host, content type, request size,
   challenge digest, challenge and step-up expiry, plan digest, state version,
   phrase, action/target kind, and ownership.

### 7.3 Local target deletion

1. Commit an attempt row with `PREDELETE_PENDING`.
2. Acquire root/parent/target handles; validate NTFS, containment, final path,
   object identity, regular-file type, link count, byte size, and SHA-256.
3. Commit the verified pre-delete snapshot including volume serial and file ID.
4. Recheck identity, attributes, byte size, and link count through the same
   retained handle; mark that exact handle for deletion and close it.
5. Reinspect the exact parent/leaf. If absent, commit
   `LOCAL_DELETION_VERIFIED`; if replaced or ambiguous, commit `BLOCKED`.
6. Never remove directories or any unlisted leaf.

### 7.4 External target attestation

1. External target remains blocking after all local deletion succeeds.
2. Operator completes deletion using the institution-approved external
   procedure outside the application.
3. Reviewer selects the server-returned current approved procedure-authority
   record and submits target ID, export ID, and a new single-use confirmation.
   The browser cannot create or edit procedure authority.
4. Server verifies the target/manifest binding and records a local-only audit
   entry plus `EXTERNAL_DELETION_ATTESTED`.
5. The application makes no claim that it observed the external account.

Procedure and hold references are opaque institutional identifiers restricted
to 1–128 ASCII alphanumeric, dot, underscore, or hyphen characters. They may
not be a URL, path, contact value, or free-text narrative.

### 7.5 Completion

Within one `BEGIN IMMEDIATE` transaction, the service:

- rechecks every target terminal basis;
- updates each eligible legacy task to `COMPLETED`;
- inserts one canonical final receipt;
- inserts bounded session and audit events; and
- commits the receipt and completed statuses atomically.

The final receipt is replayed byte-for-byte for every participant session.

## 8. Crash and recovery semantics

| Crash point | Durable observation | Required behavior |
|---|---|---|
| Before pre-delete snapshot commit | No delete authority consumed | Leave target pending |
| After snapshot, before handle disposition | Verified object identity exists | Mark run `RECOVERY_REQUIRED`; reconfirm |
| After disposition, before close | OS may complete deletion on process exit | Reinspect after restart; reconfirm |
| After file absence, before DB completion | Snapshot proves which object was selected | Reinspect exact leaf; distinguish absence from replacement; reconfirm |
| After target completion, before final receipt | Target outcome is durable | Recompute plan; finish only remaining targets |
| During final DB transaction | SQLite rollback or full commit | Exact receipt/status consistency on reopen |

A missing target without a prior committed matching pre-delete snapshot is
`TARGET_MISSING_UNEXPLAINED`, not success. A replacement at the same leaf is
never deleted by recovery.

## 9. API contract

All routes exist only on the monitor origin, use reviewer bearer auth with
`credentials: omit`, reject extra fields, enforce exact Host/Origin/content
type/body size, and apply object ownership and idempotency checks.

```text
GET  /api/v1/research/sessions/{session_id}/reconciliation
POST /api/v1/research/sessions/{session_id}/reconciliation/challenges
POST /api/v1/research/sessions/{session_id}/reconciliation/executions
GET  /api/v1/research/sessions/{session_id}/reconciliation/runs/{run_id}
POST /api/v1/research/sessions/{session_id}/reconciliation/external-attestations
```

The browser may submit only opaque IDs, the challenge token, confirmation
phrase, approved procedure reference, and idempotency key. It may not submit a
path, URL, root, command, external account identifier, hash override, target
kind, or completion status.

Bounded response fields include schema version, participant pseudonym, opaque
run/receipt IDs, plan digest, state, typed counts, terminal bases, blocker
codes, and `complete`. Paths and file identities are local-only.

## 10. UI contract

The existing irreversible-withdrawal dialog remains the first decision. A new
reconciliation panel appears only after terminal withdrawal.

The panel must:

- distinguish “withdrawal recorded” from “files reconciled”;
- display local-machine deletion and external attestation separately;
- show unresolved task counts and bounded blockers;
- never display an absolute path, username, token, raw ID mapping, or external
  account location;
- require typed confirmation and never preselect or auto-submit it;
- trap focus, support Escape cancellation, restore trigger focus, expose live
  status accessibly, and remain usable at `390x844`;
- clear confirmation/challenge state on `401`, reload, expiry, plan change, or
  terminal completion; and
- render all server text as escaped structured data, never raw HTML.

Frontend authorization is UX only; the server owns every decision.

## 11. Canonical ReconciliationReceipt

The receipt is canonical UTF-8 JSON with sorted keys, no NaN, one LF, a closed
schema, and SHA-256 over canonical body bytes without the trailing LF.

Required body fields:

```text
receipt_schema_version
operational_ledger_version
withdrawal_receipt_id
participant_pseudonym
plan_sha256
task_total
task_completed
local_target_total
local_deletion_verified_total
external_target_total
external_deletion_attested_total
blocked_target_total
recovery_required_total
completion_basis
complete
human_review_required
collection_authorized
research_ready
real_data_deletion_authorized_for_this_run
```

For this design, `receipt_schema_version=1` and
`operational_ledger_version=3`. The former versions the closed receipt/API
body; the latter reports the validated local operational ledger. They are never
represented by one ambiguous `schema_version` field. Clients fail closed on an
unsupported receipt schema, and legacy `m1` fails closed on ledger v3.

`complete=true` requires exact count reconciliation and zero blocked/recovery
targets. `completion_basis` is a sorted list containing only
`LOCAL_DELETION_VERIFIED` and/or `EXTERNAL_DELETION_ATTESTED`.

The receipt omits operator identity, reviewer token/session, absolute/relative
paths, file IDs, volume IDs, usernames, machine names, external account names,
contact data, consent images, raw media, and audit payloads.

## 12. Holds and conflicting obligations

An approved incident or legal hold blocks deletion. The application may record
only an externally issued hold reference and status; it cannot invent or clear
the authority. While held:

- collection and export remain blocked;
- the withdrawal remains terminal;
- targets remain `BLOCKED` with `APPROVED_HOLD_ACTIVE`;
- no completion receipt is issued; and
- the responsible researcher follows institutional procedure.

The application must not silently delete evidence to conceal an incident or
silently override a participant withdrawal request.

## 13. Failure taxonomy

Allowlisted failures:

```text
AUTHORITY_NOT_ISSUED
APPROVED_HOLD_ACTIVE
CHALLENGE_EXPIRED
CHALLENGE_REPLAYED
CONFIRMATION_MISMATCH
EXTERNAL_ATTESTATION_REQUIRED
HASH_MISMATCH
HARD_LINK_DETECTED
LINEAGE_INCOMPLETE
MANIFEST_MISMATCH
NON_NTFS_ROOT
OBJECT_IDENTITY_CHANGED
PATH_CONTAINMENT_FAILED
REPARSE_POINT_DETECTED
ROOT_OWNER_UNAVAILABLE
RUN_RECOVERY_REQUIRED
SCHEMA_INCOMPATIBLE
TARGET_BINDING_MISSING
TARGET_MISSING_UNEXPLAINED
TARGET_REPLACED_AFTER_DELETE
UNSUPPORTED_PLATFORM
WRITE_INTENT_ACTIVE
UNKNOWN_TECHNICAL_FAILURE
```

Unexpected exceptions map to `UNKNOWN_TECHNICAL_FAILURE` at API/CLI boundaries
without tracebacks, paths, request bodies, or secrets in client output.

## 14. Authority gates

### 14.1 Source-only implementation gate

May be separately authorized after this design, threat model, and migration
design receive explicit user approval. It permits code and synthetic temporary
roots only.

### 14.2 Real-storage validation gate

Requires a separate exact authority naming the accepted source revision, a
dedicated non-participant test root, actual NTFS/encryption/ACL evidence, a
bounded fixture manifest, one run, stop conditions, and no real data.

### 14.3 Real-data execution gate

Requires all of:

- institutional approval and approved responsible contact;
- issued consent/participant information versions;
- authorized retention decision;
- approved storage root with actual encryption and ACL evidence;
- accepted M2/M3/protocol prerequisites for any collected artifact;
- complete target registration and lineage proof;
- accepted independent security review and runtime evidence;
- explicit operator confirmation for the exact plan; and
- fresh user authority for real-data reconciliation.

No earlier gate implies a later one.

## 15. Acceptance criteria for the source-only slice

- Exact v1/v2/v3 ledger and schema mutation tests.
- Old M1 runtime rejects v3 without modifying it.
- Migration is explicit, atomic, empty-precollection-only, and deterministic.
- Plan mutation tests reject missing/extra/changed lineage and targets.
- API mutation tests cover reviewer auth, candidate denial, Host/Origin,
  content type, size, extra fields, idempotency, challenge replay/expiry, stale
  plan, and object ownership.
- Windows tests cover root/ancestor/leaf reparse, hard links, alternate streams,
  path aliases, object replacement, manifest hash/size mismatch, open-handle
  conflicts, and unsupported filesystem/platform.
- Crash tests cover every table in section 8 and prove no replacement is
  deleted during recovery.
- External attestation remains explicitly human evidence.
- Receipt tests prove canonical replay, field closure, redaction, count
  reconciliation, and non-authorizing fields.
- UI tests cover typed confirmation, expiry, auth loss, keyboard/focus,
  responsive layout, retry without duplicate execution, and distinction
  between withdrawal and reconciliation.
- Focused pytest, Ruff, strict mypy, frontend tests/typecheck/lint/build, actual
  packaged monitor flow, and independent security review pass for the same
  revision.

Passing these criteria proves only the source-only synthetic slice until the
later authority gates produce their own evidence.
