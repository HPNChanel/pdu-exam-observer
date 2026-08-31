# M1-R1 Production Withdrawal Reconciler — Threat Model

Version: `1.0-approved-source-only`

Status: `APPROVED_FOR_SOURCE_ONLY_IMPLEMENTATION`

Implementation authorized: `true — source and runner-owned synthetic rehearsal only`

Real-data deletion authorized: `false`

## 1. Security objective

Prevent the reconciler from deleting any object other than the exact
manifest-owned target selected by a current, authenticated, explicitly
confirmed participant-withdrawal plan. If identity, path, schema, authority,
state, or post-delete evidence is uncertain, the system must preserve the
withdrawal block and report an unresolved technical state.

Security success does not mean secure physical erasure. It means the exact
directory entry was removed from the approved local filesystem or an external
deletion was explicitly attested under an approved procedure.

## 2. Normative anchors

Project anchors:

- `docs/spec/DATA_GOVERNANCE.md`: exact paths under approved root,
  manifest-owned enumeration, hash verification, operator confirmation, no
  browser deletion path, and incident preservation.
- `docs/spec/SECURITY_PRIVACY.md`: standard-user/offline operation, opaque IDs,
  separate monitor/exam origins, no shell input, local-only raw media, bounded
  logs, and explicit technical failure.
- `docs/spec/M1_PERSISTENCE_SPEC.md`: participant-wide terminal withdrawal,
  canonical receipt, invalidated lineage, pending tasks, idempotency, and
  `BEGIN IMMEDIATE` mutations.

Platform anchors:

- Microsoft documents that `FILE_FLAG_OPEN_REPARSE_POINT` opens a link itself
  rather than following its target, and that handle sharing modes remain in
  effect until handle close.
- Microsoft documents that `SetFileInformationByHandle` with
  `FileDispositionInfo` requires a handle opened with `DELETE` access and marks
  that handle's file for deletion.
- Microsoft documents that volume serial plus file ID identifies whether two
  handles refer to the same file on one computer, with filesystem-specific
  limitations.
- SQLite documents that nontrivial constraint changes may require table
  reconstruction and that `BEGIN IMMEDIATE` may fail when another writer is
  active.

These anchors inform the design; implementation tests and runtime evidence
must still verify actual behavior on the target Windows revision.

## 3. Assets

| Asset | Required property |
|---|---|
| Participant withdrawal state | Terminal, participant-wide, immutable |
| Artifact lineage | Complete and provenance-preserving |
| Local artifact bytes | Deleted only when exactly bound and confirmed |
| Unrelated local files | Never opened for deletion |
| External-copy obligation | Visible until human attestation |
| Manifest/path/hash | Integrity and containment |
| Confirmation challenge | Fresh, single-use, plan-bound |
| Reconciliation receipt | Canonical, complete, redacted, replayable |
| Audit evidence | Local-only, append-only, non-sensitive |
| SQLite migration ledger | Exact, monotonic, fail-closed |
| Reviewer bearer | Memory/session-scoped, never logged or persisted in receipt |

## 4. Actors

- **Participant:** can request withdrawal through the approved research
  process; does not operate reviewer APIs.
- **Authorized reviewer/operator:** authenticates on monitor origin, reviews
  the plan, confirms local execution, and records external attestation.
- **Candidate browser capability:** untrusted for reconciliation and always
  denied.
- **Other website:** may attempt cross-site requests to loopback.
- **Local standard-user process:** may accidentally hold, rename, or modify a
  file. A deliberately malicious same-account process remains outside the MVP
  protection claim, although retained handles reduce races.
- **Application process:** owns root/store/worker and is not trusted to infer
  authority beyond persisted gates.
- **External institution/account:** outside the application; its deletion is
  attested, not machine-observed.
- **Administrator/kernel attacker:** out of scope.

## 5. Trust boundaries

```text
Participant request / institutional process
        |
        v
Reviewer human -> Monitor React origin -> Monitor FastAPI routes
                                      -> Confirmation service
                                      -> Reconciliation coordinator
                                      -> SQLite v3 + local audit
                                      -> Win32 handle boundary -> NTFS root
                                      -> External attestation boundary

Candidate origin -------- DENY --------^ 
Other websites -------- Host/Origin/auth/CSRF boundary
```

The filesystem, persisted database, browser storage, HTTP input, and external
attestations are untrusted until validated at their respective boundaries.

## 6. Assumptions and exclusions

Assumptions required for a future real execution:

- Windows 11 x64, standard-user process, offline, one application owner;
- local NTFS research root selected through native configuration;
- actual approved encryption and ACL state;
- no administrator/kernel compromise;
- all participant artifacts registered before they become valid;
- operator is acting under a valid institutional procedure.

Explicit exclusions:

- secure overwrite or forensic unrecoverability from SSD/HDD snapshots;
- deletion from Google/Colab by the application;
- malware already controlling the reviewer bearer or same Windows account;
- physical attacks outside encrypted-volume controls;
- determining legal priority between withdrawal and an incident/legal hold.

## 7. Threat register

### TM-01 — Arbitrary path injection

Severity: `CRITICAL`

Threat: browser/API input supplies an absolute, UNC, drive-relative, dot-dot,
alternate-stream, or otherwise aliased path and causes unrelated deletion.

Controls:

- browser never submits a path/root/URL;
- server resolves opaque target ID to immutable manifest-relative path;
- closed request models reject extra fields;
- normalized POSIX components and locator digest are verified;
- fixed root scopes only.

Acceptance probes: mutation corpus for absolute, UNC, drive, ADS colon,
backslash, empty/dot/dot-dot, Unicode normalization, reserved device names,
trailing-dot/space, and extra JSON fields.

### TM-02 — Reparse, junction, or symlink traversal

Severity: `CRITICAL`

Threat: root, ancestor, parent, or leaf redirects deletion outside the approved
root.

Controls:

- `FILE_FLAG_OPEN_REPARSE_POINT` on every opened component and
  `FILE_FLAG_BACKUP_SEMANTICS` when opening directories;
- post-open file-attribute and final-path validation;
- retained root/ancestor/parent handles without delete sharing;
- reject any reparse attribute rather than attempt to classify safe reparse
  types.

Acceptance probes: root junction, ancestor junction, leaf symlink, race during
open, and cleanup after rejection.

### TM-03 — Check/use substitution race

Severity: `CRITICAL`

Threat: a validated pathname is replaced before deletion.

Controls:

- hash and delete through the same retained target handle;
- compare volume serial and file ID from handles;
- retain parent handles across absence verification;
- no delete sharing on guarded parent/target;
- never reopen a replacement for deletion during recovery.

Residual: a same-account malicious process is outside the formal MVP threat
claim; runtime review must still test the available Windows sharing guarantees.

### TM-04 — Hard-link alias preserves or redirects data

Severity: `HIGH`

Threat: deleting one directory entry leaves the bytes accessible through
another hard link or targets an unexpected alias.

Controls: require regular file, expected file ID, and link count exactly one;
recheck link count through the retained handle immediately before disposition;
otherwise `HARD_LINK_DETECTED` and no deletion.

### TM-05 — Manifest or lineage tampering

Severity: `CRITICAL`

Threat: changed hashes, missing descendants, extra targets, or mutable
registry data produces incomplete or excessive deletion.

Controls:

- exact schema/ledger validation;
- canonical manifests with stored hashes;
- recursive lineage computed in SQLite;
- plan digest binds every task/target/version;
- zero-target and unregistered-lineage blockers;
- task/target mapping commits with withdrawal.

### TM-06 — Stale confirmation or replay

Severity: `HIGH`

Threat: a confirmation for an earlier plan is replayed after target state
changes.

Controls: 256-bit token, digest-only storage, five-minute expiry, reviewer
session binding, plan digest, state version, single allowed action, one-time
consumption, idempotency conflict on changed request hash.

### TM-07 — Candidate/cross-site unauthorized execution

Severity: `CRITICAL`

Threat: candidate origin or another website triggers deletion on loopback.

Controls: monitor-only route registration, reviewer bearer dependency, exact
Host/Origin, `credentials: omit`, no wildcard CORS, body/content limits,
resource ownership, security headers, and frontend controls treated only as UX.

### TM-08 — Crash creates false completion

Severity: `CRITICAL`

Threat: the file is deleted but database remains pending, or database says
completed while the file survives.

Controls: committed pre-delete snapshot, handle-bound delete, post-delete
absence verification, target completion transaction, final receipt transaction,
startup `RECOVERY_REQUIRED`, and mandatory reconfirmation.

A missing file without a matching committed snapshot is never success.

### TM-09 — Schema drift, downgrade, or partial migration

Severity: `CRITICAL`

Threat: older runtime opens v3 incorrectly, partial DDL is accepted, or a
tampered ledger is trusted.

Controls: exact cumulative checksums, canonical schema equality,
`foreign_key_check`, integrity check, single explicit transaction, old M1
fail-closed behavior, and no post-commit downgrade.

### TM-10 — Two owners or two workers

Severity: `HIGH`

Threat: concurrent processes execute the same target or race migration.

Controls: share-zero root lease before SQLite, one worker, `BEGIN IMMEDIATE`,
unique challenge/run/attempt/receipt constraints, target-state compare-and-set,
and `ROOT_OWNER_UNAVAILABLE` on contention.

### TM-11 — False external-deletion claim

Severity: `HIGH`

Threat: application labels an external copy machine-deleted without observing
the account.

Controls: no network capability, explicit `EXTERNAL_COPY` kind, persisted
approved procedure-authority record, two-minute reviewer-PIN step-up, local
operator audit, distinct `EXTERNAL_DELETION_ATTESTED` receipt basis, and
plain-language UI limitation. Composite database bindings require the same
participant, withdrawal receipt, plan, `ATTEST_EXTERNAL_DELETION` action,
external target kind/root scope, and current approved procedure authority.
One typed execution row makes local-run and external-attestation consumption
mutually exclusive.

Residual: truthfulness and adequacy of the external attestation require human
and institutional oversight.

### TM-12 — Sensitive path, identity, or token disclosure

Severity: `HIGH`

Threat: API, UI, logs, or portable receipts reveal paths, usernames, tokens,
operator identity, or external account details.

Controls: opaque browser models, bounded exception mapping, no response
models containing local fields, canonical receipt allowlist, local-only audit,
no raw payload logging, and mutation tests using private-looking fixtures.

### TM-13 — XSS or browser-state compromise

Severity: `HIGH`

Threat: injected content steals reviewer bearer or submits confirmation.

Controls: structured escaped React rendering, no raw HTML/DOM sinks, CSP,
no third-party assets, short confirmation expiry, session binding, typed phrase,
and server authorization. Same-origin XSS remains a material residual because
the reviewer bearer exists in monitor-origin `sessionStorage`.

### TM-14 — Resource exhaustion

Severity: `MEDIUM`

Threat: oversized requests, enormous target sets, very large files, or rapid
plan requests block the local app.

Controls: request-size limits, rate bounds, maximum targets per run, streaming
hash with fixed buffer, one target at a time, execution deadline, progress
heartbeats, and no parallel deletion workers.

No size/deadline threshold may be invented without source/runtime evidence;
the implementation spec must keep it unset until calibrated synthetically.

### TM-15 — Deletion conceals an incident

Severity: `HIGH`

Threat: deletion removes evidence subject to an approved incident/legal hold.

Controls: approved-hold blocker, no app-created or app-cleared authority,
collection/export stop, institutional escalation, and no completion receipt
while held.

### TM-16 — Unsupported filesystem or deletion semantics

Severity: `HIGH`

Threat: ReFS/FAT/network filesystem semantics invalidate identity or deletion
assumptions.

Controls: Windows-only, verified local NTFS volume, server-owned root, no LAN
path, and `UNSUPPORTED_PLATFORM|NON_NTFS_ROOT` before target mutation.

### TM-17 — Clock rollback or expiry ambiguity

Severity: `MEDIUM`

Threat: wall-clock changes revive a challenge or lease.

Controls: store wall time for audit but enforce challenge/worker deadlines with
process-monotonic time where live; on restart all issued challenges expire and
all running leases require recovery.

### TM-18 — Active partial/write intent

Severity: `HIGH`

Threat: writer recreates bytes after deletion or a partial is omitted.

Controls: participant withdrawal blocks writes, planner rejects any active
intent, writer and reconciler share the root lease, pending partials are
quarantined, and target registration is required before valid sealing.

### TM-19 — Receipt/count forgery

Severity: `HIGH`

Threat: receipt says complete despite blocked or missing targets.

Controls: closed canonical body, SHA-256 self-hash, exact count reconciliation,
kind-specific terminal-state checks, completion-time re-join of all authority
and ownership bindings, receipt inserted with legacy task completion in one
transaction, unique participant/withdrawal receipt, and byte-identical replay.

### TM-20 — Migration duplicates sensitive data

Severity: `HIGH`

Threat: automatic database backups create ungoverned participant copies.

Controls: v3 migration is pre-collection-empty-root only and creates no backup
copy; any nonempty research root requires a separate institution-approved
live-data migration design.

## 8. Abuse cases that must stay impossible

- Candidate calls a reconciliation endpoint.
- Reviewer sends `C:\...`, `../...`, a UNC path, or a URL.
- Browser changes a target from external to local.
- Local target is completed through an external attestation or vice versa.
- One challenge is consumed by both a local run and an external attestation.
- A stale or revoked procedure authority closes an external target.
- A standing two-hour bearer substitutes for the two-minute reviewer-PIN
  step-up.
- A plan omits one descendant and still produces `complete=true`.
- App restarts and resumes delete without a new confirmation.
- A missing unattempted file becomes completed.
- A hard-linked file is deleted.
- External attestation is labeled machine verified.
- Old M1 opens v3 and silently ignores new tables.
- Migration runs against a root containing any research participant/session.
- An active legal/incident hold is bypassed by a UI click.

## 9. Security acceptance gates

1. Threat-to-test traceability for every `TM-*` item.
2. Independent architecture review before implementation plan approval.
3. TDD mutation suite for input/schema/state/receipt invariants.
   It must directly reject every cross-kind, cross-participant,
   cross-withdrawal, cross-plan, cross-action, stale-authority, stale-step-up,
   and dual-consumption pairing.
4. Windows subprocess tests for share modes, reparse points, file identity,
   hard links, replacement, and crash windows.
5. FastAPI route census proving monitor-only reviewer dependencies.
6. React sink/network/storage audit for the changed flow.
7. Actual packaged synthetic runtime flow with console, network, persistence,
   restart, and no-leftover-process evidence.
8. Independent security re-review of the exact revision.
9. Separate user approval before any real-storage validation.
10. Receipt consumers fail closed on unsupported `receipt_schema_version`, and
    legacy `m1` fails closed on `operational_ledger_version=3`.

## 10. Residual risk statement

Even after the source-only slice passes, the following remain `UNVERIFIED`:

- real NTFS/encryption/ACL behavior on the authorized storage environment;
- resistance to malware under the same Windows account;
- external-account deletion truth;
- legal adequacy of hold/withdrawal decisions;
- physical-media erasure and backups outside the registered targets; and
- participant collection, research performance, release, and deployment.

These residuals must appear in the final source-only acceptance receipt.

## 11. Primary technical references

- [Microsoft: CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
- [Microsoft: SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)
- [Microsoft: BY_HANDLE_FILE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information)
- [SQLite: ALTER TABLE](https://www.sqlite.org/lang_altertable.html)
- [SQLite: transactions](https://www.sqlite.org/lang_transaction.html)
