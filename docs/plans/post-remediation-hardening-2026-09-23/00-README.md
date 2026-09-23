# Post-remediation hardening — 2026-09-23

Follow-up batch after `audit-remediation-2026-09-22` (all 11 tasks
complete). These items are improvements found during remediation, not new
findings — each was verified in code before being listed here.

## Objective

Close the remaining code-level weaknesses that do not require the physical
world or external authority:

- make the delivery build prove its packed frontend instead of trusting a
  volatile `apps/web/dist`,
- tighten the D1-N1 audio seal to the minimum permission it actually needs,
- remove a class of test-pollution (global network-attempt counter),
- cover the Task-07 UI surface (mark-contamination, drop/gap metrics),
- replace the launcher's hardcoded `UNVERIFIED` storage attestations with a
  best-effort honest probe,
- and give the project one canonical gate-runner so every future
  reconciliation runs the same commands.

## Non-goals

- No external gates (see `docs/plans/EXTERNAL_GATES.md`): clean machine,
  camera/displays, institutional approval, consent/retention, research
  performance, push, distribution.
- No re-opening of historical receipts (S3A/S3B/S3C/S3D, candidate-06,
  `docs/ai/M2_*`).
- No weakening of any validation, seal, authorization, or test to obtain a
  pass.
- Cosmetic-only cleanups deferred in remediation (L12, L13) stay deferred.

## Global constraints

- `AGENTS.md` is authoritative; raw video stays local; fail-closed on
  technical insufficiency; no claims beyond evidence.
- Frontend dist remains an **untracked derived artifact**. The build may
  produce it; no ledger may treat its bytes as source.
- Every task commits separately with its own execution note.
- npm/node is a **build-time** dependency only; the packaged product
  remains Python-runtime-only on the target.

## Decision gates

| ID | Question | Options | Recommendation |
|----|----------|---------|----------------|
| DG-1 | How should the delivery build obtain `apps/web/dist`? | (a) builder runs `npm ci` + `npm run build` itself from pinned inputs (dist becomes a provable derived artifact); (b) verify-only: compare dist bytes against a fresh build into temp, fail on drift | (a) — simplest honest model; Node is already a documented build dep; `npm ci` uses the lockfile so inputs stay pinned |
| DG-2 | Storage probe scope for the launcher (M2b)? | (a) ACL inspection on the storage root + best-effort volume-encryption signal, `UNVERIFIED` on any failure; (b) ACL only, encryption stays issuance-attested; (c) skip — keep hardcoded `UNVERIFIED` | (a) — matches the device-gate precedent: probe what is probe-able as standard user, record `OBSERVED`/`UNVERIFIED` honestly, never block on admin-only APIs |
| DG-3 | Gate-runner language? | (a) Python script (same interpreter as every other gate); (b) PowerShell | (a) |

## Task index

| # | File | Scope | Depends on |
|---|------|-------|------------|
| 01 | `01-audio-seal-narrowing.md` | `src/pdu_exam_observer/m2_d1_native.py` + test | — |
| 02 | `02-test-hermeticity.md` | `tests/conftest.py` + NaN-warning cleanup | — |
| 03 | `03-workspace-ui-coverage.md` | `apps/web/src/WorkspacePanel.test.tsx` | — |
| 04 | `04-launcher-storage-probe.md` | `launcher.py` + probe helper + tests | DG-2 |
| 05 | `05-frontend-build-freshness.md` | `scripts/build_completion_delivery.py`, spec, toolchain doc, packaging test | DG-1, after 01–04 (tree quiet) |
| 06 | `06-gate-runner.md` | `scripts/run_all_gates.py` + docs | DG-3 |
| 07 | `07-ledger-note.md` | as-of annotations, RISK_REGISTER pointer, execution notes, commit | all above |

Ordering rationale: 01–03 are small, independent, and each lands one clean
commit. 04 changes launcher evidence semantics (small but real). 05 is the
only behavioral change to the release path and must run on a quiet tree —
it re-runs a candidate build, so it goes last among code tasks. 06–07 are
tooling + ledgers.

## Definition of done

- Full suite green (`pytest`, frontend typecheck/lint/test/build, ruff,
  strict mypy) after every task, or a recorded reason for any scoped run.
- No historical artifact, receipt, or pinned hash is rewritten.
- Each task file carries an execution note; every task is one commit.
- Ledger annotations updated at the end (07) — no ceiling moves.
