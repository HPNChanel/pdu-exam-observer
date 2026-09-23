# Task 04 — Launcher storage probe (M2b residual)

**Type:** code + test. **Depends on:** DG-2.

## Objective

`src/pdu_exam_observer/launcher.py:81-82` hardcodes
`encryption_status="UNVERIFIED"`, `acl_status="UNVERIFIED"` into
`WorkspaceBackend` at `m2research` start. Storage-control assurance is
delegated entirely to authority-issuance time — procedural, not technical.
Same class of gap the `device_gate_decision` field closed in remediation
Task 07: make the launcher **attempt** an honest probe at startup.

## Design bounds (DG-2(a))

- Probe only what a **standard user** can observe, offline, no admin APIs:
  - ACL: effective access control on the storage root — e.g. read the
    directory security descriptor via `GetSecurityInfo`/`win32security` if
    `pywin32` is already a dependency (check `uv.lock` first — if not
    vendored, use the stdlib-only path: `os.access` checks + owner SID via
    `GetNamedSecurityInfo` through `ctypes`, or accept ACL=UNVERIFIED).
  - Encryption: best-effort volume signal. `Get-BitLockerVolume` /
    `manage-bde` require elevation — do **not** depend on them. An
    acceptable standard-user signal is `fsutil volume query` parsing or
    `None` → `UNVERIFIED`.
- Fail-open on evidence, fail-closed on claims: any probe error, timeout,
  or ambiguous result records `UNVERIFIED` — never `OBSERVED`.
- These fields are **evidence labels** consumed by the backend (check where
  `encryption_status`/`acl_status` flow — `workspace_service` detail/readiness
  output), not gates. The probe upgrades honesty; it must not introduce a
  new blocking condition.
- Probe runs **once** at launcher startup; bounded (<2s); result recorded in
  the same fields so downstream output reflects observed-vs-unverified.

## Steps

1. Check `uv.lock`/`pyproject.toml` for `pywin32`. Read
   `workspace_service.py` to see how `encryption_status`/`acl_status` are
   consumed (readiness/detail paths) before choosing probe semantics.
2. New helper (co-locate near `validate_storage_root` in
   `research_runtime/` or a small `storage_probe.py`):
   `probe_storage_controls(root) -> {"encryption_status": str, "acl_status": str}`
   returning `OBSERVED_*`/`UNVERIFIED` vocabulary already used in the
   codebase.
3. Wire `launcher.py:81-82` to call the probe instead of hardcoding.
4. Tests (`tests/backend/` or `tests/runtime/`):
   - probe on a real temp dir returns a value in the allowed vocabulary and
     never raises;
   - probe failure path (monkeypatch probe internals) → `UNVERIFIED`;
   - launcher passes probed values through to the backend;
   - a discriminating test: fake probe result `OBSERVED_ACL_RESTRICTED`
     appears in workspace detail/readiness output if the surface exposes it.
5. Docs: update the launcher's behavior note in
   `docs/WORKSPACE_GUIDE_VI.md` / ARCHITECTURE only where they describe the
   hardcoded values.
6. Gates: focused tests + `pytest tests/backend tests/runtime`, ruff,
   mypy.

## Acceptance

- No hardcoded `UNVERIFIED` literals at `launcher.py:81-82`; values come
  from the probe and are honestly `UNVERIFIED` when undeterminable.
- Probe is standard-user-safe, offline, bounded; no new dependency unless
  `pywin32` is already locked.
- Execution note appended here; commit separately.

## Execution note — 2026-09-23

Implemented per DG-2(a). `probe_storage_controls(root)` added to
`configuration.py` (same module family as `validate_storage_root` /
`_check_ntfs`), stdlib `ctypes` only — no new dependency:

- `acl_status`: `GetNamedSecurityInfoW` DACL enumeration;
  `VERIFIED` iff no ACCESS_ALLOWED ACE grants any rights to broad
  local-user SIDs (Everyone, Authenticated Users, Builtin Users/Guests,
  Anonymous, Network/Interactive/Batch). NULL/unreadable DACL or broad
  grant → `UNKNOWN`. Verified on real ACLs via icacls (owner-only →
  VERIFIED; Everyone:R → UNKNOWN).
- `encryption_status`: `VERIFIED` iff `FILE_ATTRIBUTE_ENCRYPTED`
  observed on the root (EFS — inherited by children). BitLocker is not
  determinable as a standard user → `UNKNOWN` when the flag is absent
  (EFS unsupported on this host confirmed — honest UNKNOWN).
- Never raises; non-Windows or any error → both `UNKNOWN`.

`launcher.py` now passes probed values to `WorkspaceBackend` instead of
hardcoded `UNVERIFIED`. Readiness gates (`STORAGE_*_UNVERIFIED` when
!= VERIFIED) are unchanged — the probe only upgrades honesty of the
stored evidence label; on this host the observed result is UNKNOWN, so
the gates still block exactly as before.

Tests: `tests/backend/test_storage_probe.py` (6 tests — vocabulary,
failure-degradation, real icacls ACL states, EFS flag, launcher wiring
spy, workspace-shaped tree). Gates: backend+runtime+research PASS; ruff
PASS; mypy PASS. RP2 regenerated: digest `ae02b69f…`, candidate
`60e65b93…`.
