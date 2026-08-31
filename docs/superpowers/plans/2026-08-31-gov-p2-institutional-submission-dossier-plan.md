# GOV-P2 Advisor-First Institutional Submission Dossier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` task-by-task. This workspace has no Git
> metadata; do not claim commits, branches, PRs, or merges.

**Goal:** Build a deterministic advisor-first dossier that packages reviewed
GOV-P0/GOV-P1 evidence without issuing approval or collection authority.

**Architecture:** Five reviewed source contracts feed a fail-closed Python
builder. The builder validates exact historical inputs, creates four exact-byte
annex snapshots, and emits a canonical manifest plus non-authorizing receipt.

**Tech Stack:** Markdown, canonical JSON, Python 3.11 standard library,
SHA-256, pytest 8.4.1, Ruff 0.12.10, mypy 1.17.1.

**Spec:** `docs/superpowers/specs/2026-08-31-gov-p2-institutional-submission-dossier-design.md`

## Global constraints

- Preserve the proposal, GOV-P0, GOV-P1, RP2, package, and authority ceiling.
- Treat GOV-P1 as historical evidence; do not rebuild it against current M1.
- Do not invoke camera, participant, provisioning, B0.3, A0/A1, M2, network,
  submission, signing, or real deletion paths.
- Add exactly ten focused tests and no new governance test function.

### Task 1: Materialize reviewed sources and establish RED

- [ ] Create the five reviewed source artifacts and exact body hashes.
- [ ] Add ten behavior-focused tests for the desired builder contract.
- [ ] Run the focused file and observe failure because the builder is absent.

### Task 2: Implement deterministic validation and generation

- [ ] Implement strict JSON, envelope, path/hash, source, decision, Markdown,
  file-set, authority, and historical-drift validation.
- [ ] Implement exact annex generation, manifest, receipt, atomic replacement,
  and bounded CLI failures.
- [ ] Run the ten tests to green, then run adversarial mutations.

### Task 3: Generate and reconcile

- [ ] Run canonical `--write` once and use only `--check` afterwards.
- [ ] Update PRE_COLLECTION_GOVERNANCE and the six current ledgers.
- [ ] Extend the existing three governance tests without increasing their
  collected count.

### Task 4: Verify and close

- [ ] Require 10 focused, 45 research, and 856 total tests.
- [ ] Require Ruff, strict mypy, GOV-P0, RP2, release-manifest, immutable-hash,
  package-hash, and zero PDU process/listener gates.
- [ ] Record GOV-P1 historical bytes as intact and its live checker drift as an
  explicit residual, not a fix or regenerated receipt.
