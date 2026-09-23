# Audit remediation receipt — 2026-09-22

Status:
`AUDIT_REMEDIATION_2026_09_22_TASKS_01_10_COMPLETED_LOCAL_GATES_GREEN_NO_NEW_AUTHORITY`

Plan: `docs/plans/audit-remediation-2026-09-22/` (00-README, 00-findings,
tasks 01–11). Tasks 01–10 are implemented and committed; Task 11 tracks
external gates that cannot be closed by code.

## Scope

This receipt reconciles the repository ledgers to the post-remediation tree.
It covers local technical evidence only. It does not authorize or claim
clean-machine portability, physical-camera behavior, institutional approval,
research performance, distribution, deployment, or release.

## Gate outputs (fresh, this reconciliation)

Retained under `output/audit-remediation-2026-09-22/`:

- `pytest-full.txt` — full source suite, `1110` collected, all PASS
  (`pytest-collect.txt` records the collection count).
- `frontend-gates.txt` — `npm run typecheck && npm run lint && npm test &&
  npm run build`: PASS, `82` tests / `12` files.
- `ruff.txt` — repository-wide `ruff check .`: PASS (0 findings; the
  historical `UP038` note in QUALITY_GATES G1 is resolved).
- `mypy.txt` — strict mypy over `pdu_exam_observer`: PASS, 64 source files.

## Current RP2 tuple

Regenerated exactly once for this reconciliation via
`scripts/build_m2_d1_n2_rp2.py --write`:

```text
static_bindings_digest=c7d87f4a8bd6f058faac11124dd5b70476b5cb076ab8fc1f6120126cb5dc8456
candidate_exact_bytes_sha256=c6b3992519222ae33e85f6cb33c073b561631c95b98534e23ea565d76c0dcd9c
binding_schema_exact_bytes_sha256=302dc8156c0da4bee47b39f0c42d2cc91b09ea0bb3eeb49853413d52bff30003
source_tool_inventory_count=70
policy_preimage_count=60
```

## Candidate lineage

- candidate-06 (`packaging/candidates/completion-2026-09-08/candidate-06`)
  remains byte-identical; zip SHA-256 recomputed this reconciliation still
  matches `f5bd0add40f246d476729d06988d1726297dc705c274194a440d6ad978d21bdc`.
- candidate-07 (`packaging/candidates/remediation-2026-09-22/candidate-07`)
  is the post-remediation delivery candidate:
  `PDUWorkspace.exe` `c418d82219a015e5e5df81fa4bdb09b52c872aa9c0a179f768b47b0ad98cb2da`,
  zip `738e6a8fa3ce4b6587965665c465502f61630a08e6018a7ac824bb67ce9257ad`.
  It was rebuilt once during Task 10 after the S3A pin repair exposed that
  the first build had packed a stale `apps/web/dist`. Packaged synthetic
  verification PASS for original and relocated same-host runs
  (`output/remediation-2026-09-22/package-verification.json`). Lineage:
  `docs/ai/CANDIDATE_07_LINEAGE.md`.

## Corrections made during this reconciliation

Three defects surfaced only when the full suite ran against the
post-remediation tree; all fixed without weakening any check:

1. `current_observed_frontend_dist` pin — the S3A audit pins
   `apps/web/dist/assets/index-DB9w6fTP.js`, an untracked build artifact whose
   name changed when the frontend was rebuilt after Task 07. The audited
   bytes are preserved byte-identical inside the immutable candidate-06
   bundle; `tests/packaging/test_m2_s3a_package_gap_audit.py` and
   `scripts/build_m2_s3b_candidate.py::_s3a_immutable_inputs` now resolve that
   one pin to its preserved location while still requiring the exact audited
   SHA-256. The audit JSON itself is unchanged.
2. `_DisabledMediaPipeAudio` raised `RuntimeError` on `__file__`, breaking
   `inspect.getmodule` during PyTorch import. Dunder module metadata is now
   readable; non-dunder audio namespace attributes remain sealed for D1-N1.
3. `test_queue_pressure_reports_explicit_drops` had a producer/consumer race.
   The producer now fills the bounded queue before signalling READY, making
   the drop deterministic; the assertion is unchanged.

## Finding dispositions

All 31 findings in `00-findings.md` are covered below. Residual risks are
recorded in `docs/plans/RISK_REGISTER.md` where noted.

### HIGH

| ID | Disposition | Evidence | Residual |
|----|-------------|----------|----------|
| H1 | FIXED | Task 03: `build_release.ps1` and `packaging/PDU-Exam-Observer.spec` carry HISTORICAL markers; supersession is documented (commit `6ebbc7b`) | None new; behavioral test remains static-only (see L14) |
| H2 | FIXED | Task 04: `THIRD_PARTY_NOTICES.txt` regenerated deterministically covering all bundled components (commit `d23b285`) | None |
| H3 | FIXED | Task 05: `apps/web/package.json` exact-pinned; build tools moved to devDependencies (commit `6460c05`) | Lockfile discipline still required for transitive deps |
| H4 | FIXED | All remediation work committed (`4e52921`..`5d8853b` + Task 10 commit); source no longer lives only in a dirty checkout | None |
| H5 | EXTERNAL-BLOCKED | Ceilings unchanged by design; tracked in Task 11 | Clean-machine, camera ≥15 fps, ≥2 displays, institutional approval remain UNVERIFIED |

### MEDIUM

| ID | Disposition | Evidence | Residual |
|----|-------------|----------|----------|
| M1 | ACCEPTED-WITH-RISK-ENTRY | R-43 records document-hash authority limit; `chmod 0o700` not presented as a Windows ACL control (commit `4e52921`) | Signed/custodian-issued authority flow is future work |
| M2 | FIXED (a) / ACCEPTED-WITH-RISK-ENTRY (b) | Task 07: `device_gate_decision` required+allowlisted in authority records, validated at install and on `start_real_collection` (commit `500c3a1`) | M2b: storage re-verification still delegated to authority issuance time; documented in RISK_REGISTER |
| M3 | FIXED | Task 06: encoder requires `PDU_FFMPEG_PATH`+`PDU_FFMPEG_SHA256` or bundled `tools/ffmpeg.exe`; PATH fallback removed (commit `ddd1d60`) | None |
| M4 | FIXED | Task 02: ARCHITECTURE, PACKAGING_DISTRIBUTION, README, demo README, pyproject refreshed; TRACEABILITY_MATRIX gained spec→code layer (commit `2a9ea14`) | None |
| M5 | FIXED | Task 03: SUPERSEDED/HISTORICAL markers on candidates 04/05, handoffs, `packaging/release/` (commit `6ebbc7b`) | None |
| M6 | FIXED | Task 08: notebook/fixture tests byte-compare committed artifacts against fresh tmp builds (commit `ac0c031`) | None |
| M7 | FIXED | Task 06: bounded read on `pose_timeline.jsonl` (commit `ddd1d60`) | None |
| M8 | FIXED | Task 06: bounded SSE subscriber queues with stale-consumer reconnection; bounded events/answers caps (commit `ddd1d60`) | None |
| M9 | FIXED | Task 06: `authority-template` routed in `__main__.py`; CLI test added in Task 08 | None |
| M10 | FIXED | Task 07: `runtime_withdrawal_tasks` rows on export follow-up (commit `500c3a1`) | None |
| M11 | FIXED | Task 07: schema v2 — consent receipt fields, operator attribution, `protocol_version`, drop accounting (`dropped_frames`/`gap_events`/`max_gap_frames`), real `contaminated_by_operator` boundary (commit `500c3a1`) | None |
| M12 | FIXED | Task 08: native-preflight boundaries, frozen-rules mismatch, quarantine branch, workspace negative-auth, CLI surfaces, calibration math, SSE stalled consumer (commit `ac0c031`) | None |

### LOW

| ID | Disposition | Evidence | Residual |
|----|-------------|----------|----------|
| L1 | FIXED | Task 06: literal `127.0.0.1` binding for monitor + exam origins (commit `ddd1d60`) | None |
| L2 | FIXED | Task 06: session-update columns constrained to a literal allowlist (commit `ddd1d60`) | None |
| L3 | FIXED | Task 06: `extra="forbid"` on flat request models (commit `ddd1d60`) | None |
| L4 | FIXED | Task 06: PIN throttle uses monotonic clock (commit `ddd1d60`) | Per-loopback bucket is still de-facto global — accepted within the single-host threat model |
| L5 | FIXED | Task 07: `reviewer_audit` rows + `audit_events` hook on login/logout/lifecycle (commit `500c3a1`) | None |
| L6 | FIXED | Task 06: `start_workspace_preview.py --stop` terminates the recorded process tree and removes the owned root | None |
| L7 | FIXED | `packaging/manifest-metadata.json` gitignored | None |
| L8 | ACCEPTED-WITH-RISK-ENTRY | R-46 documents that the Python-level socket guard cannot observe native DLL egress | Binary-level egress verification is external evidence |
| L9 | FIXED | This reconciliation: QUALITY_GATES/CURRENT_TASK/ACCEPTANCE_GATES carry dated as-of annotations with observed counts (1110 backend, 82 frontend) | None |
| L10 | FIXED | Task 06: degenerate-frame NaN guard + discriminating test (commit `ddd1d60`) | None |
| L11 | FIXED | Task 09: `docs/spec/BUILD_TOOLCHAIN.md` pins the toolchain; FFmpeg provenance recipe+hash recorded; candidate-07 rebuilt under it (commit `5d8853b`) | Bit-for-bit bundle reproducibility not claimed (PyInstaller timestamps) |
| L12 | ACCEPTED-WITH-RISK-ENTRY | `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains accurate for the M1 store scope it guards; renaming would churn hash-bound receipts for cosmetic gain | Product-level wording stays as-is; documented here |
| L13 | ACCEPTED-WITH-RISK-ENTRY | `_archive/` remains in the forbidden-root set as harmless defense-in-depth after the archive moved | None |
| L14 | ACCEPTED-WITH-RISK-ENTRY | Static source-text assertions are the intended coverage for the historical script; the behavioral path requires a built exe + PowerShell on Windows | Script regressions are caught statically only — acceptable while the script is marked HISTORICAL |

## Final ceilings (unchanged)

```text
authority_status=AUTHORITY_NOT_ISSUED
clean_machine_verified=false
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
distribution_ready=false
release_authorized=false
real_data_deletion_authorized=false
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
```

No claim is made for clean-machine verification, physical-camera behavior,
institutional approval, research performance, distribution readiness, or
release authority. Those remain external gates tracked by Task 11.

## Immutability sweep

- Canonical proposal SHA-256 recomputed: matches
  `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`
  (SOURCE_PROVENANCE unchanged).
- candidate-06 zip SHA-256 recomputed: matches
  `f5bd0add40f246d476729d06988d1726297dc705c274194a440d6ad978d21bdc`.
- Historical `docs/ai/M2_*` receipts and per-milestone tuples in
  QUALITY_GATES/ACCEPTANCE_GATES are untouched (verified via git diff).
- Residual PDU processes/listeners/temp roots: `PDU_PROCESS_COUNT=0`,
  `PDU_LISTENER_COUNT=0` (loopback 8765/8766), `PDU_TEMP_ROOT_COUNT=0`
  (OBSERVED 2026-09-22).
