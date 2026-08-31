# D1-N2 B0 Bootstrap Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans` and
> implement every behavioral change test-first.

**Goal:** Add a source-only, one-shot Windows bootstrap provisioning boundary
for signed D1-N2 A0 verification without creating or installing production
authority.

**Architecture:** A closed self-signed public-key bootstrap envelope and a
sanitized provisioning receipt are installed to fixed LocalAppData leaves by a
separately gated operator tool. Production lazily opens the pair with retained
share-zero/no-follow leases, imports the public key ephemerally through BCrypt,
and verifies A0 before any RP2, PENDING, native, or camera work.

**Tech stack:** Python 3.11, ctypes Win32/BCrypt, pytest, Ruff, strict mypy.

**Spec:** `docs/superpowers/specs/2026-08-29-d1-n2-b0-bootstrap-provisioning-design.md`

## Global constraints

- Target Windows 11 x64, standard user, offline.
- No new Python dependency.
- No production private key, bootstrap, receipt, signature, or A0 in the repo.
- Do not invoke the operator installer, `prepare_d1_n2()`,
  `run_d1_n2_preflight()`, native discovery, or camera.
- Preserve `AUTHORITY_NOT_ISSUED`, `physical_camera_access_authorized=false`,
  `device_gate_decision=UNVERIFIED`, and `d1_go=false`.
- The checkout has no Git metadata; do not claim commit, merge, PR, or Git
  closure.

## Execution checkpoint: B0-R1 approved

`OBSERVED` on `2026-08-29`: Task 1, Task 2, the fixed-reader portion of Task 3,
and the retained A0 lifecycle portion of Task 5 reached focused source
verification (113 tests, Ruff, and mypy pass).
Before Task 4, independent architecture review rejected the original
final-receipt order because `cleanup_clean=true` would self-attest cleanup that
can still fail after the final bytes exist. `USER_STATED` on `2026-08-29`: the
user approved option A, B0-R1 staged-receipt semantics. Implementation resumes
test-first. Operational provisioning remains unauthorized.

---

### Task 1: Governance baseline

- Reconcile stale I2/A0 rows in the readiness pack with the approved exact
  static pack.
- Mark the B0 design user-approved and record B0 implementation as active,
  bootstrap unprovisioned, with no operational authority.
- Verify exact statuses and the canonical proposal hash.

### Task 2: Closed bootstrap contracts and BCrypt verifier

- RED: closed canonical envelope/receipt parsing, public P-256 blob, key ID,
  epoch digest, self-signature, and external approval tuple tests.
- GREEN: add `m2_d1_n2_bootstrap.py` and public-only
  `m2_d1_n2_cng.py`; no signing/private/persisted-key production API.
- Verify with focused pytest, Ruff, and mypy.

### Task 3: Fixed Win32 readers

- RED: clean absence versus partial/asymmetric/poisoned state, share-zero,
  reparse, identity, durability, and cleanup tests.
- GREEN: add fixed-leaf bootstrap/receipt/A0 readers, retained leases, and
  no-replace promotion primitive in `m2_d1_n2_bootstrap_win32.py`.
- Tests use fake ops or temporary roots only, never production LocalAppData.

### Task 4: One-shot installer

- RED: invalid external tuple, tagged-open ambiguity, existing artifacts,
  write/flush/readback/bundle-promotion/durability/receipt/cleanup fault matrix;
  every pre-publication cleanup failure proves zero terminal-publisher calls,
  no final receipt, and retained partial poison.
- GREEN: add `m2_d1_n2_bootstrap_install.py` plus the separately gated
  `scripts/provision_m2_d1_n2_bootstrap.py` CLI.
- Stage the receipt in the fixed partial leaf, bind its object identity, close
  every fallible resource, then use one no-replace/write-through terminal rename
  with no subsequent authority-affecting work. Any post-create uncertainty
  leaves a fail-closed poison marker; never delete, repair, retry, refresh,
  rotate, or overwrite.

### Task 5: A0 lifecycle and production composition

- RED: bootstrap inspection must precede A0 open; absent or rejected bootstrap
  must reach no A0, RP2, native, or PENDING work; retained cleanup drift blocks
  PREPARED.
- GREEN: extend `A0BootstrapPort` with inspect/validate/close, retain bootstrap
  and A0 leases through ownership transfer, and lazily wire fixed production
  sources in `D1N2PreparedProductionFactory`.
- Installer and test keys remain unreachable from the application factory.

### Task 6: RP2 and governance closure

- Bind every new source/test/script and immutable bootstrap policy preimage.
- Run RP2 stale RED, regenerate with `--write`, then verify with `--check`.
- Record the exact new triple and keep it unsigned/non-authorizing.

### Task 7: Final verification and independent review

- Run focused and complete D1-N2 suites, D1-N1 regression, Ruff, mypy, RP2
  check, proposal hash, and repository secret/artifact scan.
- Obtain fresh independent Sol/xhigh trust-boundary review of the exact new
  triple. Only `APPROVE_STATIC_PACK_ONLY` may close B0 source work; any NO-GO
  requires remediation and a new triple.

No step provisions B0.3-B0.5, prepares A0-P, opens A1, or performs X0.
