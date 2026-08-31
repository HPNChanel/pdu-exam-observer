# D1-N2 B0.3 Custodian Ceremony Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> task-by-task. Steps use checkbox syntax for tracking. This checkout has no
> Git metadata; do not claim commits, branches, PRs, or merges.

**Goal:** Materialize the approved B0.3 contract and prepare a credential-free,
fail-closed PowerShell custodian kit outside the repository without creating or
using production authority.

**Architecture:** Repository changes are documentation/governance only. A
create-new external kit exposes a safe `ValidateOnly` mode and a dormant
`Execute` mode gated by an exact future authority. The current run ends after
static verification and independent review because no custodian exists.

**Tech Stack:** Windows PowerShell, embedded C# P/Invoke, NCrypt/BCrypt contract
source, canonical JSON, SHA-256, pytest 8.4.1.

**Spec:**
`docs/superpowers/specs/2026-08-29-d1-n2-b0-3-custodian-ceremony-design.md`

## Global constraints

- Do not modify any of the 27 RP2-bound artifacts or 21 policy preimages.
- Do not regenerate RP2; stale output is a stop condition.
- Do not create a key, bundle, signature, execution authority, provisioning
  receipt, or signed A0.
- Do not invoke `-Mode Execute`, the B0.4 installer, `prepare_d1_n2()`,
  `run_d1_n2_preflight()`, native discovery, FFmpeg, MediaPipe, or camera.
- Keep `AUTHORITY_NOT_ISSUED`, `physical_camera_access_authorized=false`,
  `device_gate_decision=UNVERIFIED`, and `d1_go=false`.
- External kit root is fixed at
  `D:\FOR_RESEARCH\SCIENTIFIC_RESEARCH\pdu-exam-observer-custodian-kit\b0-r2`.
- Resolve and prove the kit root is outside the checkout before writing; if the
  root exists, stop without overwrite or deletion.

---

### Task 1: Materialize approved documents and pre-kit governance

**Files:**
- Create: `docs/superpowers/specs/2026-08-29-d1-n2-b0-3-custodian-ceremony-design.md`
- Create: `docs/superpowers/plans/2026-08-29-d1-n2-b0-3-custodian-ceremony-plan.md`
- Modify: `docs/ai/CURRENT_TASK.md`
- Modify: `docs/ai/TASK_CONTRACT.md`
- Modify: `docs/spec/M2_D1_N2_READINESS_PACK.md`

- [x] Record the approved spec without placeholders or operational authority.
- [x] Record this plan with the exact external artifact boundary.
- [x] Change governance to
  `B0_3_SPEC_PLAN_APPROVED_INERT_KIT_PREPARATION_AUTHORIZED_CUSTODIAN_UNAVAILABLE_NO_EXECUTION_AUTHORITY`.
- [x] Run RP2 `--check`; stop rather than regenerate if it fails.

### Task 2: Build the inert external kit test-first

**Files outside repository:**
- Create: `b0_3_create_bootstrap.ps1`
- Create: `B0_3_CUSTODIAN_RUNBOOK.md`
- Create mechanically after source closure: `b0-3-kit-manifest.v1.json`
- Create mechanically after verification: `b0-3-kit-validation.v1.json`

**Interfaces:**
- `-Mode ValidateOnly` is the default and has no NCrypt or filesystem side
  effect other than stdout.
- `-Mode Execute` exists as dormant source but cannot pass without an exact
  future fixed-leaf `B0_3ExecutionAuthorityV1`.
- Stdout is one compact sanitized JSON object; success exit is `0`, rejected
  validation/execution is `2`.

- [x] Write safe-mode checks first and run them against the missing tool to
  establish RED.
- [x] Implement closed constants, canonical JSON, SHA-256, base64url, exact
  authority parsing, safe-mode self-tests, and sanitized output.
- [x] Run `ValidateOnly` and confirm it emits
  `KIT_VALIDATED`, `execution_attempted=false`, and
  `key_creation_attempted=false`.
- [x] Add embedded C# signatures for the design's fixed NCrypt/BCrypt and
  Win32 publication primitives without calling them from safe mode.
- [x] Add the dormant exact-once `Execute` state machine exactly as specified.
- [x] Write the runbook with the fixed future authority and stop conditions.
- [x] Compute the final script/runbook byte counts and SHA-256 values, then
  publish the closed canonical kit manifest with create-new semantics.

### Task 3: Static and safe-mode verification

- [x] Parse the script with the inbox PowerShell AST and require zero errors.
- [x] Run `ValidateOnly` under `powershell.exe -NoLogo -NoProfile -NonInteractive`.
- [x] Run pure negative cases for absent/false/malformed authority, alternate
  epoch/RP2/tool/manifest digest, retry, overwrite, private export, backup, and
  target-workstation flags. No negative case may reach NCrypt.
- [x] Scan source for forbidden delete/overwrite/machine-key/network,
  installer/prepare/native/camera paths. Allow a private blob identifier only
  inside the explicit negative export-denial probe.
- [x] Recompute every manifest path, size, and digest from exact bytes.
- [x] Scan repository and kit for private-key markers, production bundles,
  signatures, receipts, and execution-authority files; require zero.
- [x] Recompute proposal SHA-256 and the exact B0-R2 triple.
- [x] Run RP2 `--check` and
  `pytest tests/backend/test_m2_d1_n2_rp2_artifacts.py -q`.
- [x] Write a closed validation receipt only after all safe gates pass.

### Task 4: Independent trust-boundary review

- [x] Give the reviewer the exact spec, plan, kit manifest, script, runbook,
  validation receipt, RP2 triple, and command outputs.
- [x] Require Sol/xhigh review with no `Execute`, NCrypt creation, installer,
  native, or camera call.
- [x] Accept only `APPROVE_INERT_KIT_ONLY`; remediate any Critical/Important
  finding, regenerate tool/manifest digests, and re-review.

### Task 5: Governance closure

- [x] Record exact tool/manifest hashes and independent verdict.
- [x] Set final status to
  `B0_3_INERT_KIT_STATIC_VERIFIED_CUSTODIAN_UNAVAILABLE_NO_EXECUTION_AUTHORITY`.
- [x] Preserve `BOOTSTRAP_UNPROVISIONED` and `AUTHORITY_NOT_ISSUED`.
- [x] Inspect every changed repository artifact and every external kit file.

### Task 6: Deferred operational B0.3 — not authorized now

- [ ] Keep this task blocked until a dedicated non-target physical custodian
  exists and a fresh user authority names the exact tool hash, manifest hash,
  RP2 triple, epoch, provider, scope, one-shot/no-retry/no-overwrite, and all
  private/export/target denials.
- [ ] When separately authorized, transfer and verify the public kit, create
  the canonical authority file, invoke `-Mode Execute` exactly once, inspect
  the sanitized receipt, and stop before B0.4.
