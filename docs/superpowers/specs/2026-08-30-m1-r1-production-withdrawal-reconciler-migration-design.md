# M1-R1 Production Withdrawal Reconciler — Migration Design

Version: `1.0-approved-source-only`

Status: `APPROVED_FOR_SOURCE_ONLY_IMPLEMENTATION`

Migration execution authorized: `false`

## 1. Migration objective

Introduce exact schema version 3 for reconciliation without rebuilding or
weakening the accepted v1 tables. Migration must be explicit, pre-collection,
single-owner, atomic, fail-closed, and irreversible after commit.

This design creates no database backup or duplicate data tree. A root with any
research participant/session is ineligible; live-data migration requires a
separate institutional design and authority.

## 2. Observed compatibility problem

`OBSERVED`:

- `M1Store.schema_version == 1` and accepts exactly one migration row for v1.
- `M2PersistenceStore.schema_version == 2`, migrates exact v1 to exact v2, and
  is intentionally separate from `M1Backend`.
- v2 adds `artifact_manifests` and `m2_write_intents` but its manifest accepts
  only technical fixtures.
- opening v2/v3 through legacy `M1Store` fails closed as a newer schema.

Therefore v3 cannot be introduced merely by adding tables to the current M1
database. The runtime must gain one store owner that validates v1+v2+v3 and is
injected into the M1 governance backend. Two independent store objects must not
open the same operational database.

## 3. Compatibility policy

| On-disk ledger | Legacy `m1` mode | Future `m1r1` mode | Mutation |
|---|---|---|---|
| Empty/no ledger | Existing M1 may create v1 | Reject; explicit v1 bootstrap required | None |
| Exact `[1]` | Accept | Preflight then explicit `[1]->[1,2,3]` | One transaction |
| Exact `[1,2]` | Reject newer | Preflight then explicit `[1,2]->[1,2,3]` | One transaction |
| Exact `[1,2,3]` | Reject newer | Validate and open | None |
| Any other sequence/hash | Reject | Reject | None |

There is no downgrade path. After v3 commit, only the v3-capable runtime may
open that root.

## 4. Activation boundary

The new runtime mode is named `m1r1` during source-only development. Default
remains M0; explicit `m1` remains legacy v1. `m1r1` cannot be selected from the
browser.

Migration uses a native fixed operation, conceptually:

```text
pdu-exam-observer migrate-r1 --check
pdu-exam-observer migrate-r1 --apply --expected-readiness-digest <sha256>
```

Exact CLI naming is an implementation-plan decision, but the contract is
fixed:

- `--check` is read-only and emits a canonical `MigrationReadinessReceipt`;
- `--apply` requires the exact readiness digest from the same root/schema
  state;
- root comes only from the validated native configuration;
- browser input cannot invoke migration;
- a changed root, ledger, schema, process lease, or eligibility count invalidates
  the readiness digest; and
- neither mode accepts an arbitrary path.

## 5. Eligibility checks

All checks complete before `BEGIN IMMEDIATE`:

1. Windows 11 x64 standard-user process.
2. Existing configured local NTFS root; no UNC/network root.
3. Actual root/operational/database/sidecar handle validation.
4. Exclusive root lease acquired before SQLite open.
5. Exact v1 or v2 ledger checksum and canonical schema.
6. `PRAGMA foreign_key_check` returns no row.
7. `PRAGMA integrity_check` returns exactly `ok`.
8. Zero research participants.
9. Zero `RESEARCH` sessions.
10. Zero consent/retention/withdrawal receipts and tasks.
11. Zero artifact registry/dependency rows and active write intents.
12. Zero external export records or target rows if a future pre-v3 table exists.
13. No active application process, worker, listener, or incompatible owner.

Demo-only metadata may remain only if it has no artifact, participant, or
research foreign-key reachability. Any ambiguity is
`MIGRATION_REQUIRES_EMPTY_PRECOLLECTION_ROOT`.

## 6. Additive v3 schema

The implementation shall materialize semantically equivalent canonical DDL;
names and constraints below are binding unless a reviewed correction updates
this design before implementation.

```sql
CREATE TABLE reconciliation_targets(
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES artifact_registry(id),
    target_kind TEXT NOT NULL CHECK(target_kind IN (
        'LOCAL_RESEARCH_FILE',
        'LOCAL_EXPORT_STAGING_FILE',
        'EXTERNAL_COPY'
    )),
    root_scope TEXT NOT NULL CHECK(root_scope IN (
        'RESEARCH_ROOT',
        'EXPORT_STAGING',
        'EXTERNAL_ATTESTATION'
    )),
    locator_digest TEXT NOT NULL UNIQUE CHECK(length(locator_digest)=64),
    relative_path TEXT,
    export_id TEXT,
    expected_byte_size INTEGER,
    expected_sha256 TEXT,
    manifest_schema_version INTEGER NOT NULL CHECK(manifest_schema_version>=1),
    manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
    registration_version INTEGER NOT NULL CHECK(registration_version=1),
    created_at REAL NOT NULL,
    UNIQUE(id,target_kind,root_scope),
    UNIQUE(id,artifact_id,target_kind,root_scope),
    CHECK(
        (
            target_kind IN ('LOCAL_RESEARCH_FILE','LOCAL_EXPORT_STAGING_FILE')
            AND root_scope IN ('RESEARCH_ROOT','EXPORT_STAGING')
            AND relative_path IS NOT NULL
            AND export_id IS NULL
            AND expected_byte_size IS NOT NULL
            AND expected_byte_size >= 0
            AND expected_sha256 IS NOT NULL
            AND length(expected_sha256)=64
        )
        OR
        (
            target_kind='EXTERNAL_COPY'
            AND root_scope='EXTERNAL_ATTESTATION'
            AND relative_path IS NULL
            AND export_id IS NOT NULL
            AND expected_byte_size IS NULL
            AND expected_sha256 IS NULL
        )
    )
);

CREATE UNIQUE INDEX uq_sessions_participant_binding
    ON sessions(id,participant_id);
CREATE UNIQUE INDEX uq_artifacts_session_binding
    ON artifact_registry(id,session_id);
CREATE UNIQUE INDEX uq_withdrawal_receipt_participant_binding
    ON withdrawal_receipts(id,participant_id);
CREATE UNIQUE INDEX uq_withdrawal_task_subject_artifact_binding
    ON withdrawal_tasks(id,withdrawal_subject_session_id,artifact_id);

CREATE TABLE withdrawal_task_targets(
    withdrawal_task_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    withdrawal_receipt_id TEXT NOT NULL,
    withdrawal_subject_session_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    artifact_session_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    root_scope TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN (
        'PENDING_CONFIRMATION',
        'IN_PROGRESS',
        'LOCAL_DELETION_VERIFIED',
        'EXTERNAL_DELETION_ATTESTED',
        'RECOVERY_REQUIRED',
        'BLOCKED'
    )),
    state_version INTEGER NOT NULL DEFAULT 0 CHECK(state_version>=0),
    blocker_code TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY(withdrawal_task_id,target_id),
    UNIQUE(target_id),
    UNIQUE(withdrawal_task_id,target_id,target_kind,root_scope),
    UNIQUE(
        withdrawal_task_id,target_id,target_kind,root_scope,
        participant_id,withdrawal_receipt_id
    ),
    FOREIGN KEY(
        withdrawal_task_id,withdrawal_subject_session_id,artifact_id
    ) REFERENCES withdrawal_tasks(
        id,withdrawal_subject_session_id,artifact_id
    ),
    FOREIGN KEY(withdrawal_receipt_id,participant_id)
        REFERENCES withdrawal_receipts(id,participant_id),
    FOREIGN KEY(withdrawal_subject_session_id,participant_id)
        REFERENCES sessions(id,participant_id),
    FOREIGN KEY(artifact_id,artifact_session_id)
        REFERENCES artifact_registry(id,session_id),
    FOREIGN KEY(artifact_session_id,participant_id)
        REFERENCES sessions(id,participant_id),
    FOREIGN KEY(target_id,artifact_id,target_kind,root_scope)
        REFERENCES reconciliation_targets(
            id,artifact_id,target_kind,root_scope
        ),
    CHECK(
        (
            target_kind IN ('LOCAL_RESEARCH_FILE','LOCAL_EXPORT_STAGING_FILE')
            AND root_scope IN ('RESEARCH_ROOT','EXPORT_STAGING')
            AND state <> 'EXTERNAL_DELETION_ATTESTED'
        )
        OR
        (
            target_kind='EXTERNAL_COPY'
            AND root_scope='EXTERNAL_ATTESTATION'
            AND state <> 'LOCAL_DELETION_VERIFIED'
        )
    )
);

CREATE TABLE approved_procedure_authorities(
    id TEXT PRIMARY KEY,
    authority_reference TEXT NOT NULL UNIQUE CHECK(
        length(authority_reference) BETWEEN 1 AND 128
        AND authority_reference NOT GLOB '*[^A-Za-z0-9._-]*'
    ),
    procedure_kind TEXT NOT NULL CHECK(
        procedure_kind='EXTERNAL_DELETION'
    ),
    source_document_sha256 TEXT NOT NULL CHECK(
        length(source_document_sha256)=64
    ),
    status TEXT NOT NULL CHECK(status IN ('APPROVED','REVOKED')),
    approved_at REAL NOT NULL,
    expires_at REAL,
    revoked_at REAL,
    CHECK(expires_at IS NULL OR expires_at>approved_at),
    CHECK(
        (status='APPROVED' AND revoked_at IS NULL)
        OR (status='REVOKED' AND revoked_at IS NOT NULL)
    )
);

CREATE TABLE reconciliation_holds(
    id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(id),
    authority_reference TEXT NOT NULL CHECK(
        length(authority_reference) BETWEEN 1 AND 128
    ),
    status TEXT NOT NULL CHECK(status IN ('ACTIVE','RELEASED')),
    recorded_at REAL NOT NULL,
    released_at REAL,
    CHECK(
        (status='ACTIVE' AND released_at IS NULL)
        OR (status='RELEASED' AND released_at IS NOT NULL)
    )
);

CREATE TABLE reviewer_step_up_authentications(
    id TEXT PRIMARY KEY,
    reviewer_session_digest TEXT NOT NULL CHECK(length(reviewer_session_digest)=64),
    authentication_epoch INTEGER NOT NULL CHECK(authentication_epoch>=0),
    verified_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    consumed_at REAL,
    CHECK(expires_at>verified_at),
    CHECK(expires_at<=verified_at+120.0),
    CHECK(consumed_at IS NULL OR consumed_at<=expires_at),
    UNIQUE(id,reviewer_session_digest,verified_at,expires_at)
);

CREATE TABLE reconciliation_challenges(
    id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(id),
    withdrawal_receipt_id TEXT NOT NULL REFERENCES withdrawal_receipts(id),
    reviewer_session_digest TEXT NOT NULL CHECK(length(reviewer_session_digest)=64),
    token_digest TEXT NOT NULL UNIQUE CHECK(length(token_digest)=64),
    plan_sha256 TEXT NOT NULL CHECK(length(plan_sha256)=64),
    target_state_version INTEGER NOT NULL CHECK(target_state_version>=0),
    step_up_authentication_id TEXT NOT NULL UNIQUE,
    step_up_verified_at REAL NOT NULL,
    step_up_expires_at REAL NOT NULL,
    target_id TEXT,
    target_kind TEXT,
    root_scope TEXT,
    action TEXT NOT NULL CHECK(action IN (
        'EXECUTE_LOCAL_RECONCILIATION',
        'ATTEST_EXTERNAL_DELETION'
    )),
    status TEXT NOT NULL CHECK(status IN (
        'ISSUED','CONSUMED','EXPIRED','REVOKED'
    )),
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    consumed_at REAL,
    CHECK(expires_at>issued_at),
    CHECK(issued_at>=step_up_verified_at),
    CHECK(expires_at<=step_up_expires_at),
    CHECK(
        (
            action='EXECUTE_LOCAL_RECONCILIATION'
            AND target_id IS NULL
            AND target_kind IS NULL
            AND root_scope IS NULL
        )
        OR
        (
            action='ATTEST_EXTERNAL_DELETION'
            AND target_id IS NOT NULL
            AND target_kind='EXTERNAL_COPY'
            AND root_scope='EXTERNAL_ATTESTATION'
        )
    ),
    FOREIGN KEY(target_id,target_kind,root_scope)
        REFERENCES reconciliation_targets(id,target_kind,root_scope),
    FOREIGN KEY(
        step_up_authentication_id,reviewer_session_digest,
        step_up_verified_at,step_up_expires_at
    ) REFERENCES reviewer_step_up_authentications(
        id,reviewer_session_digest,verified_at,expires_at
    ),
    CHECK(
        (status IN ('ISSUED','EXPIRED','REVOKED') AND consumed_at IS NULL)
        OR (status='CONSUMED' AND consumed_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX idx_reconciliation_challenge_binding
    ON reconciliation_challenges(
        id,participant_id,withdrawal_receipt_id,plan_sha256,
        action,target_id,target_kind,root_scope
    );

CREATE TABLE reconciliation_executions(
    id TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES reconciliation_challenges(id),
    execution_kind TEXT NOT NULL CHECK(execution_kind IN (
        'LOCAL_RUN','EXTERNAL_ATTESTATION'
    )),
    created_at REAL NOT NULL,
    UNIQUE(id,challenge_id,execution_kind)
);

CREATE TABLE reconciliation_runs(
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    execution_kind TEXT NOT NULL DEFAULT 'LOCAL_RUN'
        CHECK(execution_kind='LOCAL_RUN'),
    participant_id TEXT NOT NULL REFERENCES participants(id),
    challenge_id TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL CHECK(length(plan_sha256)=64),
    state TEXT NOT NULL CHECK(state IN (
        'QUEUED','RUNNING','COMPLETED','BLOCKED',
        'RECOVERY_REQUIRED','FAILED_TECHNICAL'
    )),
    failure_code TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    terminal_at REAL,
    FOREIGN KEY(execution_id,challenge_id,execution_kind)
        REFERENCES reconciliation_executions(id,challenge_id,execution_kind)
);

CREATE TABLE reconciliation_attempts(
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES reconciliation_runs(id),
    withdrawal_task_id TEXT NOT NULL REFERENCES withdrawal_tasks(id),
    target_id TEXT NOT NULL REFERENCES reconciliation_targets(id),
    attempt_number INTEGER NOT NULL CHECK(attempt_number>=1),
    stage TEXT NOT NULL CHECK(stage IN (
        'PREDELETE_PENDING',
        'PREDELETE_VERIFIED',
        'DELETE_MARKED',
        'ABSENCE_VERIFIED',
        'RECOVERY_REQUIRED',
        'BLOCKED'
    )),
    observed_byte_size INTEGER,
    observed_sha256 TEXT,
    volume_identity_digest TEXT,
    file_identity_digest TEXT,
    failure_code TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(run_id,target_id),
    UNIQUE(withdrawal_task_id,target_id,attempt_number)
);

CREATE TABLE external_deletion_attestations(
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    execution_kind TEXT NOT NULL DEFAULT 'EXTERNAL_ATTESTATION'
        CHECK(execution_kind='EXTERNAL_ATTESTATION'),
    participant_id TEXT NOT NULL REFERENCES participants(id),
    withdrawal_receipt_id TEXT NOT NULL REFERENCES withdrawal_receipts(id),
    plan_sha256 TEXT NOT NULL CHECK(length(plan_sha256)=64),
    withdrawal_task_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_kind TEXT NOT NULL DEFAULT 'EXTERNAL_COPY'
        CHECK(target_kind='EXTERNAL_COPY'),
    root_scope TEXT NOT NULL DEFAULT 'EXTERNAL_ATTESTATION'
        CHECK(root_scope='EXTERNAL_ATTESTATION'),
    challenge_action TEXT NOT NULL DEFAULT 'ATTEST_EXTERNAL_DELETION'
        CHECK(challenge_action='ATTEST_EXTERNAL_DELETION'),
    challenge_id TEXT NOT NULL,
    procedure_authority_id TEXT NOT NULL
        REFERENCES approved_procedure_authorities(id),
    reviewer_session_digest TEXT NOT NULL CHECK(length(reviewer_session_digest)=64),
    attested_at REAL NOT NULL,
    UNIQUE(withdrawal_task_id,target_id),
    FOREIGN KEY(execution_id,challenge_id,execution_kind)
        REFERENCES reconciliation_executions(id,challenge_id,execution_kind),
    FOREIGN KEY(
        withdrawal_task_id,target_id,target_kind,root_scope,
        participant_id,withdrawal_receipt_id
    )
        REFERENCES withdrawal_task_targets(
            withdrawal_task_id,target_id,target_kind,root_scope,
            participant_id,withdrawal_receipt_id
        ),
    FOREIGN KEY(
        challenge_id,participant_id,withdrawal_receipt_id,plan_sha256,
        challenge_action,target_id,target_kind,root_scope
    ) REFERENCES reconciliation_challenges(
        id,participant_id,withdrawal_receipt_id,plan_sha256,
        action,target_id,target_kind,root_scope
    )
);

CREATE TABLE reconciliation_receipts(
    id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL UNIQUE REFERENCES participants(id),
    withdrawal_receipt_id TEXT NOT NULL UNIQUE REFERENCES withdrawal_receipts(id),
    body_json TEXT NOT NULL,
    body_sha256 TEXT NOT NULL CHECK(length(body_sha256)=64),
    created_at REAL NOT NULL
);

CREATE INDEX idx_reconciliation_targets_artifact
    ON reconciliation_targets(artifact_id);
CREATE INDEX idx_reconciliation_holds_participant
    ON reconciliation_holds(participant_id,status);
CREATE INDEX idx_withdrawal_task_targets_state
    ON withdrawal_task_targets(state);
CREATE INDEX idx_reconciliation_challenges_participant
    ON reconciliation_challenges(participant_id,status);
CREATE INDEX idx_reconciliation_runs_participant
    ON reconciliation_runs(participant_id,state);
CREATE INDEX idx_reconciliation_attempts_target
    ON reconciliation_attempts(target_id,attempt_number);
```

## 7. Constraint rationale

- Existing `withdrawal_tasks` is unchanged; detailed target state lives in a
  companion table.
- One artifact can have multiple local/external targets.
- A target can map to only one withdrawal task, preventing duplicate deletion
  through two tasks.
- `locator_digest` gives one immutable target identity without exposing a path
  in receipts.
- Local and external fields are mutually exclusive by table `CHECK`.
- Challenge tokens are digest-only and plan/session/action bound.
- A challenge creates exactly zero or one `reconciliation_executions` row;
  its typed composite foreign key permits that execution to become a local run
  or an external attestation, never both.
- Companion target-state checks prevent a local target from reaching
  `EXTERNAL_DELETION_ATTESTED` and an external target from reaching
  `LOCAL_DELETION_VERIFIED`.
- External attestation is composite-bound to the same participant, withdrawal
  receipt, plan, action, target kind, and root scope as its challenge and to a
  persisted procedure-authority record. The transaction additionally requires
  that authority to be currently `APPROVED`, unexpired, and not revoked.
- Attempts retain pre-delete object evidence without storing raw volume/file
  identifiers; only domain-separated digests are persisted.
- One participant gets one canonical final reconciliation receipt.
- Holds are participant-scoped, externally referenced, and cannot be inferred
  from application telemetry.

The implementation must validate exact columns, defaults, checks, foreign
keys, indexes, uniqueness, and full canonical SQL—not merely table presence.

## 8. Cumulative checksum

The schema ledger remains cumulative:

```text
V1_CHECKSUM = SHA256(LEDGER_DDL || V1_DDL)
V2_CHECKSUM = SHA256(LEDGER_DDL || V1_DDL || V2_DDL)
V3_CHECKSUM = SHA256(LEDGER_DDL || V1_DDL || V2_DDL || R1_DDL)
```

The exact canonical bytes, separator convention, and lowercase SHA-256 form
must match the existing v1/v2 builder convention. The final implementation
plan must add a test proving that one-byte DDL drift changes the v3 checksum and
causes fail-closed reopen.

## 9. Explicit migration algorithm

### 9.1 Readiness phase

1. Resolve native-configured root; reject path input.
2. Open and validate root/operational/database/sidecar handles.
3. Acquire the existing share-zero store lease.
4. Open SQLite, enable WAL and foreign keys.
5. validate exact ledger `[1]` or `[1,2]` and exact canonical schema.
6. run eligibility checks from section 5.
7. compute a canonical readiness body containing schema digests, ledger
   versions/checksums, zero-count evidence, proposal hash, executable/source
   binding, and non-authorizing fields.
8. emit body SHA-256; close without mutation.

The receipt omits root path, username, database bytes, tokens, and handles.

### 9.2 Apply phase

1. Repeat every readiness check under the exclusive lease.
2. Recompute and compare the expected readiness digest.
3. Execute `BEGIN IMMEDIATE`; fail `STORE_BUSY` if another writer exists.
4. If source is v1, execute exact v2 DDL and insert ledger row 2.
5. Execute exact R1 DDL and insert ledger row 3.
6. Run `PRAGMA foreign_key_check`; any row aborts.
7. Compare the in-transaction schema object map to canonical v3.
8. Commit once.
9. Checkpoint WAL, close, reopen under retained root ownership, and validate
   exact `[1,2,3]`, canonical schema, foreign keys, and integrity.
10. emit a canonical `MigrationReceipt` with pre/post schema digests and
    `migration_committed=true`.

No application/research route is served while migration is in progress.

## 10. Fault and restart behavior

Injected failure points:

- before `BEGIN IMMEDIATE`;
- after each v2 statement;
- after ledger row 2;
- after each v3 statement;
- after ledger row 3;
- before foreign-key/schema validation;
- before commit;
- after commit before WAL checkpoint;
- after checkpoint before receipt write;
- during receipt atomic replacement.

Required outcomes:

- before commit: reopen is exact original v1 or v2, with no v3 object or row;
- after commit: reopen is exact v3 even if receipt generation failed;
- a missing receipt never rolls back or repeats the schema migration; a
  read-only recovery command regenerates it only from exact committed v3 state
  and the original readiness digest;
- partial/extra schema objects, ledger gaps, or mismatched checksums reject;
- no migration path edits `sqlite_schema` through `writable_schema`;
- no migration failure falls back to legacy app startup.

## 11. Runtime integration design

`ResearchStoreV3` owns the connection and accepted Windows handles.
`M1Backend` gains a narrow injected-store protocol for transaction, connection,
lock, root, and close. Existing default construction continues to use
`M1Store` only in legacy `m1` mode.

`m1r1` startup:

1. requires exact v3;
2. constructs one `ResearchStoreV3`;
3. injects it into the M1 governance backend;
4. constructs planner/coordinator against the same store and root lease;
5. marks interrupted runs `RECOVERY_REQUIRED` without deleting;
6. registers monitor routes only after validation/recovery; and
7. preserves `RESEARCH_COLLECTION_NOT_IMPLEMENTED` until a later collection
   milestone explicitly removes it.

The implementation must not open `M1Store` and `ResearchStoreV3` together.

## 12. Data registration after migration

M1-R1 cannot reconcile an artifact without a target. Future artifact sealing
must insert `artifact_registry`, manifest, dependencies, and
`reconciliation_targets` in the same transaction.

Export sealing must insert an `EXTERNAL_COPY` target before the export is
reported transferable. If transfer fails, no external target is claimed. If
transfer succeeds, the target binds only `export_id` and manifest SHA-256; no
account, URL, path, or operator identity enters exportable data.

## 13. Migration receipts

`MigrationReadinessReceipt` body:

```text
receipt_schema_version
operational_ledger_version
source_ledger_versions
source_schema_sha256
target_ledger_versions
target_schema_sha256
eligibility_counts
proposal_sha256
source_binding_sha256
root_identity_bound
precollection_empty
migration_authorized
real_data_present
research_ready
collection_authorized
```

`MigrationReceipt` adds:

```text
readiness_body_sha256
migration_committed
post_reopen_validated
foreign_keys_valid
integrity_valid
legacy_runtime_compatible
```

Both receipt types use `receipt_schema_version=1`; readiness targets
`operational_ledger_version=3`, while the recorded source ledger remains in
`source_ledger_versions`. Consumers reject unsupported receipt versions, and
the legacy `m1` runtime must reject operational ledger v3.

For a successful v3 migration:

```text
migration_committed=true
post_reopen_validated=true
legacy_runtime_compatible=false
real_data_present=false
research_ready=false
collection_authorized=false
```

## 14. Migration test matrix

Required fixtures:

- exact empty v1;
- exact empty v2;
- exact v3 reopen;
- no ledger;
- bad v1/v2/v3 checksum;
- version gap, duplicate, reordered, and future version;
- extra/missing/altered table, index, column, check, FK, or unique constraint;
- participant, research session, consent, retention, withdrawal, artifact,
  dependency, write-intent, or export data present;
- second owner and active writer;
- root/database/WAL/SHM reparse and replacement;
- non-NTFS, non-Windows, UNC, missing operational component;
- every injected fault from section 10;
- exact receipts and redaction;
- unsupported receipt schema rejected by every consumer;
- direct mutation attempts pairing a local target with external terminal state,
  an external target with local terminal state, the wrong participant,
  withdrawal receipt, plan, action, root scope, target, stale/revoked procedure
  authority, expired step-up, or reused challenge;
- one challenge cannot create both a local run and an external attestation;
- legacy M1 fail-closed open after v3;
- `m1r1` successful reopen without duplicate migration.

## 15. Rollout and stop conditions

The migration may not be applied until:

- this design and its companion documents are approved;
- an implementation plan is approved;
- implementation plus migration mutation tests pass;
- independent security review approves the exact revision;
- the root is proven empty of research data; and
- fresh user authority explicitly permits one migration attempt.

Immediate stops:

- any nonzero eligibility count;
- any schema/hash/foreign-key/integrity mismatch;
- any second owner or live listener;
- any unsafe/reparse/unsupported root component;
- readiness digest drift;
- unexpected exception or receipt redaction failure.

The migration attempt does not authorize real deletion, M2, M3, camera, or
participant collection.
