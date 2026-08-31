# GOV-P5A Human Confirmation Request Pack Implementation Plan

> **For agentic workers:** execute inline with test-driven development because
> this workspace has no Git metadata and no subagent delegation was requested.

**Goal:** Build a deterministic advisor-first request pack for the two open
GOV-P4 human-confirmation blockers without recording a response or authority.

**Architecture:** Five reviewed sources define questions, evidence rules, a
blank response template, and upstream bindings. A Python builder validates the
closed pack and generates only manifest/validation leaves.

**Tech Stack:** Python 3, pytest, canonical JSON, SHA-256, Markdown governance
ledgers.

**Spec:** `docs/superpowers/specs/2026-08-31-gov-p5-human-confirmation-request-pack-design.md`

## Global constraints

- Maximum status is `GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`.
- Audience is `FACULTY_ADVISOR_FIRST`; submission remains `NOT_SUBMITTED`.
- GOV-P5A contains no response, identity, approval, retention, storage, or contact value.
- The existing authority ceiling remains byte-for-byte equivalent in meaning.
- No runtime, API, database, frontend, package, camera, participant, M2, or external operation changes.

## Tasks

1. Materialize the approved spec and five canonical reviewed-source artifacts.
2. Add exactly eight focused tests and observe RED because the builder module is absent.
3. Implement strict canonical parsing, upstream binding, source validation, deterministic generation, and bounded CLI behavior.
4. Run all specified adversarial mutations and keep both questions pending.
5. Reconcile current governance ledgers with G14, G10, and R-32.
6. Run focused, research, lint, strict typing, collection, full-suite, upstream, release-manifest, process, and listener gates.

The expected post-change baselines are 69 research tests and 880 total tests.
Historical GOV-P1 `MANIFEST_MISMATCH` remains disclosed and is not repaired.

