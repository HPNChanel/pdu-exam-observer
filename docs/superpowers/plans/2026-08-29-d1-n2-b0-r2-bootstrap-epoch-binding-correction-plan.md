# B0-R2 Bootstrap Epoch Binding Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` task-by-task. This checkout has no Git metadata;
> do not claim commits, branches, PRs, or merges.

**Goal:** Enforce one exact implementation-defined bootstrap epoch digest at
every acceptance boundary, bind its canonical preimage into RP2, and obtain a
fresh static-only review without creating operational authority.

**Architecture:** The bootstrap module owns one immutable 15-field epoch-policy
preimage, its exact 626 canonical bytes, and its fixed SHA-256. Bundle parsing,
installation authority, operator parsing, and provisioning receipts converge
on that constant. The RP2 builder imports the constants and adds one dedicated
policy projection before deterministic regeneration and review.

**Tech stack:** Python 3.11, pytest 8.4.1, Ruff 0.12.10, mypy 1.17.1,
Windows 11 x64.

**Spec:**
`docs/superpowers/specs/2026-08-29-d1-n2-b0-r2-bootstrap-epoch-binding-correction-design.md`

## Global constraints

- Exact epoch digest:
  `736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b`.
- No new dependency and no production private/signing API.
- Do not generate a key, bundle, receipt, signature, or A0.
- Do not invoke the bootstrap installer, `prepare_d1_n2()`,
  `run_d1_n2_preflight()`, native discovery, FFmpeg, MediaPipe, or camera.
- Preserve `BOOTSTRAP_UNPROVISIONED`, `AUTHORITY_NOT_ISSUED`,
  `physical_camera_access_authorized=false`, `device_gate_decision=UNVERIFIED`,
  and `d1_go=false`.
- Preserve unrelated workspace changes and the canonical proposal SHA-256.

---

### Task 1: Exact bootstrap epoch contract

**Files:**
- Modify: `tests/backend/test_m2_d1_n2_bootstrap.py`
- Modify: `src/pdu_exam_observer/m2_d1_n2_bootstrap.py`

**Interfaces:**
- Produce `BOOTSTRAP_EPOCH_PREIMAGE: tuple[tuple[str, object], ...]`.
- Produce `BOOTSTRAP_EPOCH_CANONICAL_BYTES: bytes`.
- Produce `BOOTSTRAP_EPOCH_DIGEST: str`.

- [x] Add RED tests for the exact 626-byte preimage/digest, alternate bundle
  rejection, matching alternate authority rejection, and alternate receipt
  rejection.
- [x] Run the focused test and confirm failure because the exact interface or
  enforcement is absent.
- [x] Add the immutable preimage and derived canonical bytes/digest, with a
  literal digest assertion.
- [x] Enforce the exact digest in bundle parsing, authority validation, and
  receipt validation; export the three constants.
- [x] Replace valid test fixtures with the exact constant and rerun green.

### Task 2: Operator and downstream paths

**Files:**
- Modify: `tests/backend/test_m2_d1_n2_bootstrap_install.py`
- Modify: `tests/backend/test_m2_d1_n2_bootstrap_win32.py`
- Modify: `src/pdu_exam_observer/m2_d1_n2_bootstrap_install.py`

- [x] Add a RED test proving `parse_operator_authority()` rejects another
  lowercase 64-hex epoch digest.
- [x] Run the exact test and confirm it fails by returning an authority object.
- [x] Reject any non-exact digest before constructing the authority.
- [x] Update installer and Win32 fixtures to import the exact constant.
- [x] Run bootstrap, installer, Win32 reader, and CNG tests green.

### Task 3: RP2 epoch policy

**Files:**
- Modify: `tests/backend/test_m2_d1_n2_rp2_artifacts.py`
- Modify: `scripts/build_m2_d1_n2_rp2.py`
- Regenerate: `docs/spec/M2_D1_N2_AUTHORITY_BINDING.schema.json`
- Regenerate: `docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json`

- [x] Add a RED test requiring `bootstrap_epoch_policy_digest`, the exact
  source-derived preimage, and exact digest.
- [x] Import the immutable bootstrap constants into the builder and construct
  the closed `d1-n2.b0-r2-bootstrap-epoch` policy projection.
- [x] Run RP2 artifact tests green.
- [x] Prove `--check` is stale before regeneration.
- [x] Run one `--write`, then `--check`, and record the exact replacement triple.

### Task 4: Governance and verification

**Files:**
- Modify: `docs/ai/CURRENT_TASK.md`
- Modify: `docs/ai/TASK_CONTRACT.md`
- Modify: `docs/spec/M2_D1_N2_READINESS_PACK.md`

- [x] Record the approved B0-R2 spec/plan, historical B0-R1 triple, exact epoch
  digest, replacement triple, and fail-closed status.
- [x] Run focused bootstrap/composition tests, all D1-N2 tests, the 152-test
  D1-N1 native regression, and the full repository suite.
- [x] Run scoped Ruff, strict mypy, deterministic RP2 check, proposal hash, and
  credential/operational-artifact scans.
- [x] Obtain one independent Sol/xhigh review that recomputes the exact packet,
  21 policy preimages, and epoch digest without invoking operational wrappers.
- [x] Only after `APPROVE_STATIC_PACK_ONLY`, set
  `B0_R2_STATIC_PACK_APPROVED_BOOTSTRAP_UNPROVISIONED_AUTHORITY_NOT_ISSUED`.

No task opens B0.3, B0.4, B0.5, A0-P, A1, or X0.
