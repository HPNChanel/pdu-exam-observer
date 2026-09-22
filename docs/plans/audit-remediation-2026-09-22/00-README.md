# Audit Remediation Plan — 2026-09-22

**Status:** PLANNED. Not yet authorized for implementation.
**Source:** four-agent read-only audit of the full repository on 2026-09-22,
consolidated in `00-findings.md`. Baseline status at audit time:
`LOCAL_TECHNICAL_DELIVERY_VERIFIED` (docs/ai/COMPLETION_2026_09_08.md), branch
`codex/complete-system-colab`, working tree dirty (59 modified + 36 untracked
files), canonical proposal SHA-256
`2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5`.

## Goal

Close every code-level and documentation-level gap found by the audit so the
repository is internally consistent, reproducible in principle, and defensible
as a scientific research instrument — without claiming any authority,
verification, or evidence that does not exist.

## Non-goals (explicitly out of scope for every task)

- No commit, push, merge, branch, deploy, publish, sign, distribute, or release
  action. Commit authority is a separate user decision (see DG-1).
- No real participant collection, camera capture beyond the existing technical
  diagnostic, institutional submission, or research training/evaluation.
- No mutation of `packaging/candidates/completion-2026-09-08/candidate-06/`,
  `packaging/handoffs/m2-s3e-clean-environment/`, the historical
  `packaging/release/` payload bytes, `docs/source/DE_CUONG_*.docx`, or any
  historical receipt under `docs/ai/` or `packaging/**`.
- No weakening of validation, authorization, privacy controls, data-split
  gates, or tests to obtain a pass.

## Global constraints (apply to all tasks)

1. Evidence discipline per AGENTS.md: every load-bearing claim gets an explicit
   state (OBSERVED / USER_STATED / SOURCE_VERIFIED / DERIVED / PLAUSIBLE /
   UNVERIFIED / UNKNOWN / REFUTED).
2. TDD per repo convention: write a discriminating failing test first (RED),
   then implement (GREEN). Never edit a test to match broken behavior.
3. `test_m2_s3a_package_gap_audit.py` pins exact SHA-256 of
   `scripts/build_release.ps1`, `scripts/smoke_release.ps1`,
   `scripts/smoke_m1_release.ps1`, `packaging/PDU-Exam-Observer.spec`,
   `packaging/README.txt`, and the canonical proposal. Any edit to those files
   fails that audit until the pins are re-recorded in the same task (see
   Task 03 procedure).
4. Source changes alter the RP2 static binding tuple
   (`static_bindings_digest`, `candidate_exact_bytes_sha256`). Historical
   receipts stay untouched; new tuples are produced only in Task 10.
5. Source changes mean candidate-06 no longer matches current source. The plan
   treats candidate-06 as immutable evidence of the 2026-09-08 source state;
   Task 09 builds a NEW candidate lineage (candidate-07) — it never overwrites
   or "fixes" candidate-06 in place.
6. Fail-closed behavior is preserved: no failure path may downgrade from
   FAILED / TECHNICAL_INSUFFICIENT to a weaker state.
7. `docs/ai/CURRENT_TASK.md` is updated only at the Task 10 milestone.
8. Loopback-only, offline, no CDN, no telemetry, no arbitrary path/URL/device
   input from the browser — unchanged.

## Decision gates — require the user before or during execution

| ID | Question | Needed by | Recommendation |
|----|----------|-----------|----------------|
| DG-1 | Commit the current uncommitted delivery (H4) before remediation? | Before Task 01 | Recommended: request scoped commit authority for a single baseline commit, so remediation diffs are reviewable and the delivered state is recoverable. If denied, proceed in the dirty tree exactly as prior milestones did. |
| DG-2 | `focus.contaminated_by_operator`: implement a real trigger, or remove the field from the export envelope? | Task 07 | Implement a minimal operator-mark mechanism (spec keeps the field meaningful); removal requires a PRODUCT_SPEC envelope change and is not recommended. |
| DG-3 | Vendor `tools/ffmpeg.exe` into the repo, or record a hash-pinned fetch recipe? | Task 09 | Record provenance + recipe only (keeps repo source-only, matches current practice); vendoring adds LGPL binary to git. |
| DG-4 | Retire `scripts/build_release.ps1` entirely, or keep it as a labeled historical script? | Task 03 | Keep file, add HISTORICAL banner + fail-fast guard, add a current-source entry point — preserves the S3A pin story with a re-pin. |

## Task index (execute strictly in order)

| # | File | Scope | Type | Findings |
|---|------|-------|------|----------|
| 01 | `01-risk-register.md` | RISK_REGISTER entries G-N1..N3 + stale-label annotations | docs-only | M1, M2, M3 |
| 02 | `02-docs-traceability.md` | TRACEABILITY_MATRIX spec→code layer; ARCHITECTURE/README/PACKAGING_DISTRIBUTION/demo/pyproject/guide refresh | docs-only | M4 |
| 03 | `03-packaging-hygiene.md` | stale build script disposition, SUPERSEDED/HISTORICAL markers, .gitignore, S3A re-pin | repo hygiene | H1, M5 |
| 04 | `04-third-party-notices.md` | generated THIRD_PARTY_NOTICES from lockfiles + vendored binaries | repo hygiene + script | H2 |
| 05 | `05-dependency-pinning.md` | package.json exact pins; pyinstaller pin in completion builder | repo hygiene | H3 |
| 06 | `06-runtime-hardening.md` | loopback literal bind, bounded queues/reads, ffmpeg pin, SQL allowlist, extra=forbid, monotonic throttle, authority-template, preview cleanup, NaN guard | code + tests | M7, M8, M9, M3, L-items |
| 07 | `07-research-data-model.md` | drop accounting, contaminated_by_operator, consent receipt fields, operator attribution, protocol_version, withdrawal task rows, device-gate interlock field, reviewer audit events | code + schema | M10, M11, M2 |
| 08 | `08-test-hardening.md` | notebook-contract verify-in-place; native preflight, frozen-rules binding, quarantine, negative-auth, CLI tests | tests | M6, M12 |
| 09 | `09-rebuild-reproducibility.md` | documented toolchain + candidate-07 rebuild attempt + lineage receipt | build evidence | V-items |
| 10 | `10-ledger-reconciliation.md` | fresh full gates, RP2 regeneration, CURRENT_TASK/QUALITY_GATES/ROADMAP update, remediation receipt | ledger | all |
| 11 | `11-external-gates.md` | non-codable tracker: clean-machine S3E-B, camera/display hardware, institutional approval, commit/distribution authority | docs-only | H4, H5 |

## Ordering rationale

Docs-only tasks (01–02) first: zero behavioral risk, produce the corrected
reference frame the later code tasks are judged against. Repo-hygiene tasks
(03–05) next: still no runtime behavior change, but they make packaging and
dependencies honest. Code changes (06–07) after that, smallest surface first.
Test hardening (08) then confirms the new behavior discriminates. Rebuild (09)
and ledger reconciliation (10) close the loop with fresh evidence. External
gates (11) are tracked, not "fixed" — they cannot be closed by code.

## Definition of done for the whole plan

- Every finding in `00-findings.md` carries a disposition:
  FIXED / ACCEPTED-WITH-RISK-ENTRY / DEFERRED-WITH-REASON /
  EXTERNAL-BLOCKED (each with evidence ref).
- All gates pass on the final tree: Ruff, strict mypy, full pytest suite,
  frontend typecheck + lint + vitest + build.
- `docs/ai/AUDIT_REMEDIATION_2026-09-22.md` exists and honestly records what
  changed, what was verified, and what remains open — including that no clean
  machine, physical camera, institutional approval, or release authority is
  claimed.
