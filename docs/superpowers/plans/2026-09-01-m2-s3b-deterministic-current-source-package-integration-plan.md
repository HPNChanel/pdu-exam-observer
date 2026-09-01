# M2-S3B Deterministic Current-Source Package Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans`. Do not commit, push, promote, sign,
> distribute, release, or run the candidate.

**Goal:** Build a side-by-side current-source Windows candidate twice and
publish static inclusion evidence only when both package trees are
byte-identical.

**Architecture:** A Python orchestrator owns the temporary frontend and two
PyInstaller builds, validates archive/frontend/README contracts, and emits a
canonical local receipt. RP2 binds the stable source inputs before package
creation; governance records candidate-static evidence without runtime or
release claims.

**Tech stack:** Python 3.11.9, Node 24.11.0, npm 11.14.1, uv 0.10.10,
PyInstaller 6.10.0, canonical JSON, SHA-256, pytest.

**Spec:**
`docs/superpowers/specs/2026-09-01-m2-s3b-deterministic-current-source-package-integration-design.md`

## Global constraints

- Preserve historical package and S3A audit bytes.
- Build only under owned temporary roots and the ignored canonical candidate.
- Require bit identity; do not normalize away a package mismatch.
- Do not execute the candidate or open camera, participant, distribution, or
  release authority.

## Task 1 - Contract and RED tests

- Materialize the approved design and this plan.
- Add exactly eight non-parametrized packaging tests for CLI closure, build
  contract, provenance, receipt, reproducibility, archive inclusion,
  frontend/README equality, and authority/immutability.
- Run the focused file before production artifacts exist and record RED.

## Task 2 - Deterministic candidate builder

- Add the candidate PyInstaller spec and candidate-only README.
- Implement canonical tree hashing, strict source/RP2/historical validation,
  bounded CLI failures, frontend build isolation, two PyInstaller builds,
  recursive archive inspection, no-overwrite promotion, and cleanup.
- Keep the existing release builder/spec/README unchanged.

## Task 3 - RP2 source reconciliation

- Bind the builder, candidate spec, candidate README, and packaging test.
- Add four S3B policy preimages for status, reproducibility, inclusion, and
  authority ceiling.
- Run RP2 `--write` once after sources stabilize and use the resulting tuple
  as both package builds' source revision.

## Task 4 - Build and receipt

- Reverify S3A and historical package inputs.
- Run the double build once, require exact equality, and materialize the
  candidate validation receipt.
- Run read-only check twice and materialize canonical AI verification
  artifacts from the validated result.

## Task 5 - Governance and adversarial verification

- Reject toolchain, source, archive, frontend, README, manifest,
  reproducibility, no-overwrite, and authority mutants.
- Update current task/contract v19, roadmap, G21, G17, and R-39.
- Extend the existing three governance consistency tests without adding test
  functions.

## Task 6 - Closure

- Run focused, manifest, RP2, research, Ruff, strict mypy, collection, and
  full-suite gates.
- Reverify all historical hashes and proposal bytes.
- Confirm no candidate execution, process/listener, temporary root, signing,
  distribution, commit, push, or release.
