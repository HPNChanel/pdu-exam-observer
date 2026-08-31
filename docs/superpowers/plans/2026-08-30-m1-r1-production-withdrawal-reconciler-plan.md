# M1-R1 Production Withdrawal Reconciler Implementation Plan

**Goal:** Implement the approved production-shaped withdrawal reconciler as a
source-only, fail-closed slice, with a no-path synthetic rehearsal proving the
flow without authorizing a real migration, real deletion, external operation,
participant collection, M2, or M3.

**Specifications:**

- `docs/superpowers/specs/2026-08-30-m1-r1-production-withdrawal-reconciler-design.md`
- `docs/superpowers/specs/2026-08-30-m1-r1-production-withdrawal-reconciler-threat-model.md`
- `docs/superpowers/specs/2026-08-30-m1-r1-production-withdrawal-reconciler-migration-design.md`

## Authority and evidence ceiling

- Normal `m1r1` runtime is deny-all for migration apply, reconciliation
  execution, local deletion, and external attestation until a future scoped
  authority exists. The bounded result is `AUTHORITY_NOT_ISSUED`.
- `migrate-r1 --check` is read-only and derives its root only from validated
  native configuration. `migrate-r1 --apply` is implemented but cannot obtain
  authority in this slice.
- `rehearse-r1` accepts no root or path. It creates exactly one
  `%TEMP%\pdu-m1r1-rehearsal-*` root, fixed synthetic fixtures, and an
  in-memory authority bound to that one target set. There is no retry.
- Browser requests may contain only opaque IDs, bounded confirmation text,
  PIN step-up input, a challenge token, and closed attestation fields. They may
  never contain a path, URL, root, command, executable, or destination.
- No real participant, real storage root, network account, camera, device,
  collection, M2, M3, deployment, publishing, or release operation is in
  scope.
- The maximum completion claim is
  `M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY`.

## Challenge contract

**Outcome:** one owner and one connection compose the accepted v1/v2
invariants with v3 reconciliation, while every destructive transition remains
bound to a current plan, recent PIN step-up, single-use typed challenge, and
explicit authority.

**Falsifiable assumption:** the M1 transaction seam and extracted guarded
SQLite ownership can be introduced without changing the existing v1/v2
schema, migration, withdrawal, recovery, or lease behavior.

**Smallest refutation:** existing M1/P1 regression tests plus focused injected-
store and owner lifecycle tests. Any failure stops the extraction and requires
the plan to be revised before later tasks proceed.

## Task 1 — Shared guarded SQLite ownership and injected M1 store

- [x] Add focused RED tests for injected-store ownership, one connection, one
  transaction lock, cleanup, and legacy construction compatibility.
- [x] Extract or compose the accepted root/operational/database/WAL/SHM/lease
  guards into `src/pdu_exam_observer/storage_owner.py` without weakening P1.
- [x] Make `M1Backend` accept the sole injected store/transaction seam while
  retaining the legacy v1 constructor for existing M1.
- [x] Re-run the M1/P1 regression group, Ruff, and mypy.

Acceptance: no second SQLite connection; accepted legacy tests unchanged;
fault cleanup releases guards once; no real root is opened during tests.

## Task 2 — Exact v3 schema, migration, service, and store

- [x] Copy the reviewed canonical R1 DDL exactly into a v3 module and bind the
  cumulative checksum to ledger DDL + v1 + v2 + R1.
- [x] Add schema/foreign-key/mutation tests, including one-byte DDL drift.
- [x] Implement read-only readiness receipt and atomic v1/v2-to-v3 migration.
- [x] Reject non-empty research roots, unexpected ledgers, schema drift,
  changed readiness digests, unsupported roots, and missing authority.

Acceptance: reviewed DDL parses on exact v1/v2; mutation probes fail closed;
normal apply is denied; synthetic migration rolls back at every injected fault.

## Task 3 — Target registration and withdrawal mapping

- [x] Implement server-derived `LOCAL_ARTIFACT` and `EXTERNAL_COPY` target
  registration with closed locators and unique locator digests.
- [x] Require target coverage before an artifact can become valid in m1r1.
- [x] Bind participant withdrawal tasks to targets without changing terminal
  withdrawal semantics; missing targets create reconciliation blockers and
  never roll back withdrawal.
- [x] Test duplicate, unregistered, cross-participant, stale, and late-write
  cases.

Acceptance: no caller-supplied path survives; each task/target pairing is
kind-correct and participant-bound; existing M1 withdrawal receipts replay.

## Task 4 — Canonical planner and receipts

- [x] Build plans inside one read transaction from the canonical withdrawal
  receipt, invalidated lineage, dependencies, tasks, targets, and intents.
- [x] Canonicalize body bytes, stable opaque-ID order, counts, blockers,
  target-state version, and SHA-256.
- [x] Implement closed `ReconciliationReceipt` schema v1 and replay checks.
- [x] Test ordering, drift, missing target, mutable manifest, active intent,
  duplicate locator, and receipt/count forgery.

Acceptance: the browser receives no path or local operator identity; identical
state produces identical digest; any state change invalidates the plan.

## Task 5 — PIN step-up, typed challenges, and external attestation

- [x] Extend reviewer authentication with a server-side PIN step-up record of
  at most 120 seconds, bound to the current reviewer session.
- [x] Create random 256-bit challenges, persist token digests only, and bind
  exact participant/receipt/plan/action/target/root-scope tuples.
- [x] Permit exactly one execution kind per challenge and consume it
  transactionally before work begins.
- [x] Require a current persisted approved institutional procedure-authority
  record for external attestation; expose no browser approval route.
- [x] Test expiry, replay, wrong action/kind/target/session/plan, clock rollback,
  state drift, cooldown, and absent/revoked procedure authority.

Acceptance: no reusable step-up credential or raw challenge token is stored;
local challenges cannot attest external copies and vice versa.

## Task 6 — Retained-handle deletion, coordinator, and recovery

- [x] Implement the Windows-only retained-handle primitive using server-owned
  manifest-relative components and post-open identity validation.
- [x] Hold parent and target handles across hash verification and disposition;
  reject reparse points, links, alternate syntax, multiple hard links,
  replacement, and unsupported filesystems.
- [x] Create durable runs/attempts before target work, serialize one worker,
  stop on first unsafe state, and never auto-resume after restart.
- [x] Mark interrupted work `RECOVERY_REQUIRED`; require a new plan, step-up,
  challenge, and authority to continue.
- [x] Fault-inject every persistence and deletion boundary using only synthetic
  temp roots; preserve sentinels and disclose bounded failure codes.

Acceptance: exactly registered fixture leaves are removed; out-of-manifest
files survive; a crash cannot create false completion or startup deletion.

## Task 7 — Monitor-only reconciliation API

- [x] Add reviewer-only plan, step-up/challenge, execution, status, receipt,
  and external-attestation routes only to the monitor origin.
- [x] Preserve exact host/origin/bearer/content-type/body-size rules and reject
  unknown fields.
- [x] Return bounded codes and opaque values; sanitize unexpected exceptions.
- [x] Prove candidate-origin absence and monitor authorization/idempotency/
  replay behavior.

Acceptance: no destructive route exists on the candidate app; request/response
schemas contain no path/URL/command field; no network operation is introduced.

## Task 8 — Reviewer UI and visual/runtime acceptance

- [x] Extend the Vietnamese research-preparation screen with withdrawal status,
  blockers, plan digest summary, PIN step-up, exact confirmation phrase,
  local-run status, recovery-required state, and external-attestation status.
- [x] Clear PIN/challenge state on reload, 401, expiry, plan drift, and logout.
- [x] Preserve keyboard operation, focus visibility, live status, error
  association, responsive layout, and redacted rendering.
- [x] Test API mappers/components, then exercise the actual packaged monitor
  flow at desktop and 390x844; inspect representative screenshots.

Acceptance: no destructive action is implied complete until receipt closure;
technical runtime proof is reported separately from user visual acceptance.

## Task 9 — No-path rehearsal CLI and packaging

- [x] Add `migrate-r1 --check`, deny-all `--apply`, and `rehearse-r1` dispatch.
- [x] Make rehearsal construct its own synthetic v1 root, migrate it, register
  fixed targets, withdraw, plan, step up, challenge, delete/attest, recover as
  applicable, verify receipts/sentinel, close SQLite, and dispose the root.
- [x] Inject one in-memory authority bound to the rehearsal root, readiness
  digest, plan digest, target IDs, process, and single execution.
- [x] Add no-path/extra-argument, no-retry, cleanup, redaction, and deterministic
  receipt tests; include the command in packaging without running real apply.

Acceptance: rehearsal cannot name or touch an existing root; authority is not
serializable or reusable; packaged source contains no new network dependency.

## Task 10 — Verification, threat matrix, ledger, and handoff

- [x] Run focused backend/frontend gates after each task, then full Python and
  frontend regression, Ruff, mypy, typecheck, lint, build, synthetic CLI, and
  packaging/static checks.
- [x] Map TM-01 through TM-20 to source and discriminating evidence.
- [x] Run independent security review against the same revision and remediate
  material findings through RED/GREEN cycles.
- [x] Update current task, task contract, roadmap/gates only with observed
  evidence; preserve every external, participant, physical, M2/M3, and
  collection blocker.

Acceptance output ceiling:

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

## Stop conditions

Stop before continuing if an existing M1/P1 invariant regresses, reviewed DDL
must change, a path/URL/command crosses the browser boundary, a test would need
a non-runner-owned root, authority becomes serializable, the rehearsal can
retry or accept a path, or any requested action would touch a real participant,
device, external service, deployment, or release boundary.
