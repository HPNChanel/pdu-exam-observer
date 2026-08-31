# M1-R1 Verification Ledger

Updated: `2026-08-30`

Status: `M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY`

## Claim boundary

`OBSERVED`: the canonical proposal SHA-256 remains
`2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
This workspace has no Git metadata, so this ledger identifies the inspected
working tree by its files and fresh gates rather than a commit.

`OBSERVED`: source, strict contracts, synthetic Windows/NTFS fixtures, the
no-path rehearsal, API tests, frontend component/build tests, and the local
packaged monitor flow are verified on synthetic data. Normal migration apply,
normal local deletion, and normal external attestation still return
`AUTHORITY_NOT_ISSUED` before mutation.

`UNVERIFIED`: clean-machine portability, hostile live NTFS race behavior, real
storage deletion, real participant data, an external account, institutional
procedure, deployment, and release were not exercised.

## Fresh gates

| Gate | Result |
| --- | --- |
| Focused M1-R1, storage-owner, M2 persistence, and auth group | `137 passed` |
| Python collection/full-suite attempts | `M1_R1_SOURCE_SUITE_846_OF_846_PASS`; 846/846 passed in one fresh full invocation; earlier two invocations each had one distinct load-sensitive timeout, retained as historical evidence and not claimed fixed |
| Ruff, current Python source and changed packaging test | `PASS` |
| mypy `--strict`, `src/pdu_exam_observer` | `PASS`, 37 source files |
| Frontend Vitest | `PASS`, 10 files / 58 tests |
| Frontend typecheck | `PASS` |
| Frontend ESLint | `PASS` |
| Frontend production build | `PASS`, 21 modules |
| Packaging tests and manifest verification | `PASS`, 8 tests / 186 files |
| Packaged M0 smoke and M1 persistence smoke | `PASS` |
| Packaged M1-R1 desktop and 390x844 monitor flow | `PASS_LOCAL_SYNTHETIC`; normal execution `403 AUTHORITY_NOT_ISSUED` |
| No-path synthetic `rehearse-r1` | `PASS` through the CLI regression |
| Independent M1-R1 security review before TM-17 follow-up | `GO — APPROVE_SOURCE_ONLY`; superseded for latest-revision review claims |
| Independent review of the current TM-17 revision | `APPROVE_SOURCE_ONLY` after remediation; no unresolved Critical/Important findings |

## Threat-to-evidence map

| Threat | Current control and discriminating evidence | State |
| --- | --- | --- |
| TM-01 arbitrary path injection | Server-derived target locators in `m1_r1.py`; unknown/path fields rejected in `test_m1_r1_targets.py` and `test_m1_r1_confirmation.py`. | `OBSERVED` |
| TM-02 reparse traversal | No-follow parent/leaf checks in `reconciliation_execution.py`; reparse cases in `test_m1_r1_deletion.py`. | `OBSERVED_SYNTHETIC_WINDOWS` |
| TM-03 check/use substitution | Target and parent handles remain retained through disposition and absence; same-byte recovery replacement and parent-rename subprocess probes pass. | `OBSERVED_SYNTHETIC_WINDOWS` |
| TM-04 hard-link alias | Link-count-one requirement and multi-hard-link rejection test in `test_m1_r1_deletion.py`. | `OBSERVED_SYNTHETIC_WINDOWS` |
| TM-05 manifest/lineage tampering | Canonical manifest binding and planner blockers in `m1_r1.py`/`reconciliation.py`; target/planner mutation tests pass. | `OBSERVED` |
| TM-06 stale confirmation/replay | Session-bound PIN step-up, token digests, plan/state binding, one typed execution, replay/expiry tests in `test_m1_r1_confirmation.py`. | `OBSERVED` |
| TM-07 candidate/cross-site execution | Reconciliation routes exist only on the monitor app; Host/Origin/bearer/content-type tests pass. | `OBSERVED` |
| TM-08 crash false completion | Durable run/attempt stages, startup `RECOVERY_REQUIRED`, no auto-delete, recovery tests in `test_m1_r1_deletion.py`. | `OBSERVED_SYNTHETIC` |
| TM-09 schema drift/partial migration | Exact reviewed DDL/checksum, full v3 integrity/FK/schema validation, injected rollback and owner-race tests in `test_m1_r1_migration.py`. | `OBSERVED_SYNTHETIC` |
| TM-10 two owners/workers | Legacy-compatible migration-owner lease plus accepted P1 lease; preflight/apply race probes reject the loser. | `OBSERVED_SYNTHETIC_WINDOWS` |
| TM-11 false external deletion | Separate current procedure authority and one challenge-bound in-memory execution authority; normal route denies; attestation tests pass. | `OBSERVED_SYNTHETIC_ONLY` |
| TM-12 path/identity/token disclosure | Redacted plan/receipt/HTTP/CLI assertions and digest-only challenge storage tests pass. | `OBSERVED` |
| TM-13 browser/XSS compromise | Closed mappers, React text rendering, CSP/security headers, unknown-field rejection, no browser path/URL/command input. | `SOURCE_VERIFIED` |
| TM-14 resource exhaustion | Content length is required and transfer encoding is rejected; a 70,000-byte chunked request returns `413`. | `OBSERVED` |
| TM-15 deletion conceals incident | Approved holds remain planner blockers; no browser route can create/import authority. | `SOURCE_VERIFIED` |
| TM-16 unsupported filesystem | NTFS validation and fail-closed platform codes precede deletion. | `OBSERVED_LOCAL_WINDOWS`; other filesystems `UNVERIFIED` |
| TM-17 clock rollback/expiry | Wall time remains audit evidence; reviewer bearer and challenge lifetimes also use process-monotonic deadlines. Non-finite bounds fail closed; reviewer/time state is rechecked after planning and before challenge issue/consume; logout/replacement durably revokes issued challenges through the one-active-service callback; restart expires every pre-existing issued challenge. | `OBSERVED_SYNTHETIC`; independent `APPROVE_SOURCE_ONLY` |
| TM-18 active/partial write | Pending/failed/quarantined intents block; failed leaves are moved to quarantine; recovery includes failed intents; withdrawal/quarantine tests pass. | `OBSERVED_SYNTHETIC` |
| TM-19 receipt/count forgery | Replay recomputes current exact receipt and re-joins kind-specific evidence/current procedure authority; canonical rehash forgery and revocation tests reject. | `OBSERVED` |
| TM-20 migration duplicates data | Eligibility requires an exact empty precollection root; non-empty roots and changed readiness digests reject. | `OBSERVED_SYNTHETIC` |

## TM-17 follow-up evidence

`OBSERVED`: TDD began with four discriminating failures against the prior
revision: `M0Backend` rejected the requested monotonic source, the confirmation
service rejected its requested monotonic source, a replacement confirmation
service left a prior `ISSUED` challenge active, and a backwards monotonic clock
allowed challenge consumption. The corrected tests pass and assert terminal
database state plus absence of a reconciliation execution where applicable.

`OBSERVED`: current-revision independent review then returned `NO-GO` for
Important fail-closed seams: stale pre-lock expiry/session samples during
consumption, non-finite bearer/challenge time, logout/replacement leaving
durable `ISSUED` challenges, append-only stale revocation callbacks, raw HTTP
500 on a clock fault, and create-path post-plan session/time drift. Each
concrete repro was observed RED before remediation. The corrected revision
revalidates the bearer and both clocks under the root lock immediately before
issue/consume, returns bounded `TECHNICAL_INSUFFICIENT` for HTTP clock faults,
transactionally revokes matching issued challenges, and replaces the sole
active service callback on service replacement. Scoped re-review is
`APPROVE_SOURCE_ONLY` with no unresolved Critical or Important finding.

`OBSERVED`: the first full-suite invocation used the system Python rather than
the project environment and produced 49 M2 native failures, all rooted in
`POSE_ENGINE_UNAVAILABLE`. A read-only prerequisite probe showed the system
interpreter had no `mediapipe` distribution, while
`.venv\Scripts\python.exe` reports the required `mediapipe==1.0.1`. No M2
source or test was changed. Re-running the same full suite with the project
interpreter passed all 819 collected tests.

## Packaged runtime acceptance follow-up

`USER_STATED`: the next-task request authorized a local generated-bundle
rebuild and packaged runtime/visual acceptance on synthetic data only. It did
not authorize signing, distribution, deployment, real deletion, external
attestation, participant data, camera use, or collection.

`OBSERVED`: TDD first reproduced a packaging-harness defect: custom
`ExamPort`/`MonitorPort` arguments were probed by `smoke_release.ps1` but were
not forwarded to the packaged process. The new behavioral packaging test
failed by health timeout, then passed after the script set and restored
`PDU_EXAM_PORT` and `PDU_MONITOR_PORT`. The packaging gate is now `8/8`.

`OBSERVED`: the first actual logout observation exposed that a successfully
used reviewer PIN remained in React state and therefore in the password input
DOM after logout. A focused frontend regression failed with received value
`2468`, then passed after successful login, authentication loss, stream
authentication loss, and logout all clear PIN state. The rebuilt package
confirmed an empty PIN field and empty reviewer session storage after logout.

`OBSERVED`: the final local bundle executable SHA-256 is
`EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF`.
The identical bundled/detached manifest SHA-256 is
`9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256`
for 186 bundle files. Manifest verification, M0 smoke, and M1 persistence
smoke pass.

`OBSERVED`: the packaged M1-R1 monitor restored one withdrawn synthetic
session with one local and one external target. Challenge issue returned
`201`; the normal execution route returned `403 AUTHORITY_NOT_ISSUED`; logout
left both challenges `REVOKED`, zero execution/run records, both targets
`PENDING_CONFIRMATION`, and the synthetic local artifact unchanged by size and
SHA-256. Desktop and 390x844 frames were inspected and the only console error
was the intentional 403 resource failure. Final gates are 843/843 Python tests,
58/58 frontend tests, frontend typecheck/lint/build, scoped Ruff, strict mypy
over 37 source files, and an unchanged canonical proposal hash. The sanitized
receipt and image index are
`output/runtime/m1-r1-tm17-packaged-acceptance/PACKAGED_RUNTIME_ACCEPTANCE.md`.

## Governance closure follow-up

`OBSERVED`: three new governance consistency tests first failed against the
stale ledgers because M1-R1/G9/G5 were absent and historical M0/M1/GOV-P1
receipts were presented alongside current claims without explicit separation.
After reconciliation, all three pass. The current collection is 846 tests.
Current source evidence is `M1_R1_SOURCE_SUITE_846_OF_846_PASS`: one fresh full
invocation passed 846/846. Earlier two full invocations each exposed one
distinct load-sensitive timeout: the packaging smoke health deadline in the
first, and the M2 blocked-reader 3.24-second observation against a 3.0-second
bound in the second. Each failed test subsequently passed alone and in bounded
repetition. Those observations remain historical and are not claimed fixed.
No runtime or timeout implementation was changed. The package was not rebuilt;
the packaged acceptance event remains 843/843 Python tests, 58/58 frontend
tests, packaging 8/8, and 186 files. The current receipt is
`docs/ai/M1_R1_V1_DETERMINISM_RECEIPT.md`.

`OBSERVED`: the canonical proposal SHA-256 remains
`2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
The current package remains executable SHA-256
`EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF`
and identical bundled/detached manifest SHA-256
`9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256`.

The fail-closed authority boundary is repeated here as binding evidence:

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

`OBSERVED`: final governance-scoped gates pass: the new consistency module is
3/3, the research suite is 35/35, scoped Ruff passes, and pytest collects 846
tests. Release-manifest verification passes; proposal, executable, detached
manifest, and bundled manifest hashes remain the exact values above. The final
read-only cleanup probe reports zero PDU processes and zero PDU listeners.

## Residuals and withheld acceptance

- The current-revision independent approval is source-only. Live ASGI
  scheduling, multi-process behavior, and any deployment architecture beyond
  one backend/one active confirmation service remain unverified.
- Repository-wide Ruff additionally reports pre-existing `UP038` at
  `tests/backend/test_m2_synthetic.py:404`; current source and the two changed
  backend tests pass Ruff without weakening or editing that unrelated test.
- Packaged monitor desktop/mobile screenshots and console inspection were
  obtained locally on deterministic synthetic data. This is technical visual
  evidence, not user aesthetic approval or clean-machine portability proof.
- The PyInstaller generated trees were rebuilt locally without signing,
  archiving, publishing, deployment, or release. The build toolchain reported
  an explicit Node/jsdom engine mismatch and the existing hidden-import
  warnings; exercised flows and all gates passed, but those warnings remain in
  the receipt.
- Live NTFS race behavior, clean-machine portability, real external deletion,
  and truth of a human attestation remain unverified.

## Binding output ceiling

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
