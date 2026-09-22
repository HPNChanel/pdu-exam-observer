# M2-S3E-A Same-Host Portability and Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> task-by-task. Use TDD and preserve the S3D candidate.

**Goal:** Create and exercise a deterministic clean-environment handoff ZIP at
two isolated same-host paths without claiming clean-machine or release proof.

**Architecture:** A Python builder creates a closed deterministic ZIP around
the immutable S3D candidate. A no-argument Windows PowerShell 5.1 verifier runs
one full packaged synthetic evidence cycle. A Python harness executes that
verifier at two relocation paths and emits the canonical S3E-A receipt.

**Tech Stack:** Python 3.11, Windows PowerShell 5.1, ZIP/JSON/SHA-256,
PyInstaller one-folder candidate, pytest, Ruff, mypy.

**Spec:**
`docs/superpowers/specs/2026-09-02-m2-s3e-a-same-host-portability-clean-environment-handoff-design.md`

## Global constraints

- Do not rebuild or mutate the S3D candidate or historical package.
- No camera, audio, device, participant, arbitrary path/URL, Internet, signing,
  deployment, distribution, or release action.
- `clean_machine_verified=false`; GAP-06 and GAP-08 remain open.
- Run the same-host harness once only; it internally runs two relocations and
  never retries.
- Do not commit or push without separate lifecycle authorization.

## Task 1 - RED contracts

- Add exactly ten non-parametrized packaging tests covering builder CLI,
  deterministic ZIPs, closed member validation, PowerShell contract,
  isolation/network controls, full-cycle response validation, two relocations,
  cleanup/sanitization, canonical receipt, and immutable inputs.
- Run the focused file before the implementation modules exist and preserve the
  expected missing-contract failure.

## Task 2 - Deterministic handoff builder

- Implement `build_handoff_pack()` and `check_handoff_pack()` in
  `scripts/build_m2_s3e_handoff_pack.py`.
- Pin S3D hashes and validate the candidate/release manifest before building.
- Create two fixed-metadata ZIP streams, require byte identity, and materialize
  only a safe closed output. Default CLI mode is read-only `--check`.

## Task 3 - Windows PowerShell verifier

- Implement the no-argument Windows PowerShell 5.1 script and its canonical
  unfilled response template.
- Verify handoff/candidate manifests, non-elevated execution, isolated process
  environment, loopback scope, exact run accounting, two S2D exports, two exact
  stdin reproductions, candidate immutability, and cleanup.
- Emit only one bounded JSON line and a fixed response leaf.

## Task 4 - Same-host relocation harness

- Implement `SameHostPortabilityReceipt`, bounded failure codes,
  `run_same_host_portability()`, and the no-argument CLI.
- Extract the exact ZIP to a spaces path and a Unicode/spaces path; call
  `powershell.exe` and validate both responses.
- Require byte-identical minimized projections and zero residual process,
  listener, and temporary roots.

## Task 5 - RP2 and generated handoff

- Bind builder, harness, PowerShell verifier, README, response template, and
  tests. Raise inventory `64 -> 70` and policy count `55 -> 60`.
- Add policies for S3E-A status/gaps, deterministic ZIP, two relocations,
  external-response boundary, and authority ceiling.
- Run RP2 `--write` exactly once, then build the handoff ZIP exactly once and
  use only read-only checks.

## Task 6 - Runtime receipt and governance

- Run the same-host CLI exactly once. Stop on any failure; do not retry.
- Materialize exact successful stdout as
  `docs/ai/M2_S3E_A_SAME_HOST_PORTABILITY.json` and write the verification
  narrative.
- Reconcile CURRENT_TASK, TASK_CONTRACT v22, ROADMAP, G24, G20, R-42, and the
  three current governance tests without altering historical receipts.

## Task 7 - Verification

- Require 10 focused packaging tests, deterministic builder checks,
  PowerShell parser PASS, S3D/candidate manifest checks, Ruff, strict mypy,
  RP2/artifact/governance/research PASS, exactly 986 collected tests, and one
  986-test full-suite invocation.
- Finish with candidate/proposal/hash immutability and process/listener/temp
  checks. Report same-host proof separately from open clean-machine evidence.

