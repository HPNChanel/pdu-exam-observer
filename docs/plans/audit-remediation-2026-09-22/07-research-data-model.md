# Task 07 — Research data-model and governance gaps

**Type:** code + schema migration + tests. **Findings:** M10, M11, M2b, L5.
**Depends on:** Tasks 01–06, DG-2.
**Caution:** highest-risk task in the plan — touches the runtime schema and
the authority record contract. Additive, versioned changes only; never edit a
historical receipt, and keep `schema_version` semantics consistent with
existing migrations (read `service.py:266-312` and the M1 migration-ledger
pattern in `m1.py:501-578` first). Split into sub-commits if the diff grows.

## 07.1 Persist drop/gap accounting (M11, R-09)

- `camera_worker.py` already counts dropped frames (`:66-69`); today
  `service.py:597` discards the counter.
- Persist per-session `dropped_frames`, `gap_events`, and
  `max_gap_frames` into the runtime timeline/manifest (pick the store that
  already carries per-session technical metadata — read `service.py`
  `_write_frame_locked`/manifest writer first).
- Surface the counts in `workspace_service.detail()` output and the session
  report so a reviewer sees data-quality accounting, not silent absorption.
- RED test: inject a capture stub that drops N frames → persisted record
  shows N; >45-frame gap still fails `FRAME_GAP_EXCEEDED`.

## 07.2 `contaminated_by_operator` (M11, DG-2)

- If DG-2 = implement: add a monitor-only action (e.g.
  `POST /workspace/sessions/{id}/mark-contamination`, reviewer-bearer,
  RECORDING-only) that sets `contaminated_by_operator=True` on subsequent
  focus contexts; export then emits the real flag. Wire UI minimally
  (a labeled button on the monitor workspace panel) or leave UI out and
  document the API — decide by smallest honest surface.
- If DG-2 = remove: delete the field from the export focus object AND update
  `PRODUCT_SPEC.md` envelope + `DATASET_SCHEMA.md` in the same change; add a
  spec-changelog line. (Not recommended — the field is scientifically
  meaningful.)
- RED test for whichever path is chosen.

## 07.3 Consent receipt fields (M11)

- Add `consent_receipt_id` + `consent_version` to the authority record
  schema (`authority_cli.py` install args, `service.py:998-1027`
  `_validate_authority`, template in `template_main`). Decide required vs
  optional: required matches FR-005 mapping but breaks the current template
  — since no real authority exists yet, making them required is safe.
- Regenerate the template doc + `WORKSPACE_GUIDE_VI.md` flag list.
- RED test: authority record missing the fields → `COLLECTION_AUTHORITY_*`
  failure.

## 07.4 Operator attribution (M11, L5)

- Add `operator_pseudonym` (opaque, operator-chosen at install) to the
  authority record; stamp it onto `runtime_reviews` and `runtime_exports`
  rows, and into `detail()` output. Pseudonymous, never a real name — the
  identifier binds actions to an operator label, not an identity.
- Add `reviewer_audit` events: login/logout recorded into the local store
  (event kind + timestamp + session scope only — NEVER the PIN, token, or
  digest). Insertion points: `services/core.py` bearer issue/revoke
  (`:112-150`) → persist via the active backend hook.
- RED tests: review row carries the operator pseudonym from the installed
  authority; login emits an audit row with no secret material (assert
  absence of pin/token strings).

## 07.5 `protocol_version` on runtime_sessions (M11)

- Add the column via additive migration; populate from the authority record
  at session creation; surface in `detail()`.
- RED test: session row records the authority's protocol_version.

## 07.6 Withdrawal task rows (M10)

- Mirror the M1 `withdrawal_tasks` pattern: on `withdraw()` with existing
  exports, insert task rows (one per export record / derived artifact class)
  instead of only the `external_export_follow_up_required` flag — keep the
  flag too (it drives the UI banner).
- RED test: withdrawal after export produces task rows; second withdrawal
  is idempotent (no duplicate tasks).

## 07.7 Device-gate interlock field (M2a, R-44)

- Add `device_gate_decision` to the authority record (allowed values:
  `UNVERIFIED` | recorded decision string). `start_real_collection` must
  reject when the field is absent — recording `UNVERIFIED` explicitly is
  acceptable at this stage (the rung ordering becomes technical, value
  honesty preserved); never accept a fabricated `GO`.
- Update `authority_cli` + template + guide.
- RED test: missing field → `COLLECTION_AUTHORITY_*` failure.

## Acceptance

- Additive migrations only; existing synthetic fixtures still pass
  (`pytest tests/runtime tests/backend/test_workspace* -q`).
- Export envelope fields unchanged except the now-real
  `contaminated_by_operator` value; update `test_export_contract.py` /
  `DATASET_SCHEMA.md` if the envelope semantics changed.
- No migration rewrites history; `runtime_sessions` rows created before this
  task still load (or a migration fills defaults).
- Update `TRACEABILITY_MATRIX.md` rows touched by this task (keeps Task 02's
  work accurate).

## Execution note (2026-09-22, DG-2 = implement)

All seven sub-items landed; `tests/runtime` + `tests/backend` green (incl. 10
new tests in `tests/runtime/test_data_model_governance.py`), Ruff + strict
mypy clean, frontend typecheck/lint/82 tests green.

- 07.1 `ingest_frame(..., dropped_frames=N)` validates (bool/negative/NaN →
  `CAPTURE_ACCOUNTING_INVALID`/`CAPTURE_TIMESTAMP_INVALID`), persists
  `dropped_frames`/`gap_events`/`max_gap_frames`; `_write_frame_locked`
  returns the fill count so write-side holes are accounted; >45-frame gaps
  fail `FRAME_GAP_EXCEEDED`; counters survive root reopen.
- 07.2 `mark_contamination` (RECORDING-only, first call wins) persists
  `contaminated_from_seq`/`contaminated_at`; `_export_records` emits the real
  flag for `frame_seq >= boundary`; wired as workspace action
  `mark-contamination` + monitor-panel button; `record_focus_context` events
  carry the flag.
- 07.3 `consent_receipt_id`/`consent_version` required by
  `authority_cli._validate_record` and `service._validate_authority`
  (`_is_reference` shape); template emits placeholders.
- 07.4 `operator_pseudonym` required in authority; stamped onto
  `runtime_reviews`/`runtime_exports` rows and `detail()` (never the export
  envelope). Reviewer login/logout emit audit via hook list: M1Backend →
  `audit_events`, WorkspaceService → runtime `reviewer_audit`; hooks receive
  the event kind only (no PIN/token/digest); closed-store write skipped
  narrowly (`sqlite3.ProgrammingError`).
- 07.5 `protocol_version` populated from authority at
  `start_real_collection`; surfaced in `detail()` and the report block.
- 07.6 `withdraw()` inserts one `runtime_withdrawal_tasks` row per existing
  export (`EXTERNAL_EXPORT_FOLLOW_UP`, PENDING); second withdraw is rejected
  by the terminal-state guard so no duplicates; receipt gains
  `follow_up_task_count`.
- 07.7 `device_gate_decision` required at install and collection; allowlist
  = UNVERIFIED/NO_GO/BACKEND_CONTRACT_PASS/D1_N1_PREFLIGHT_PASS/
  D1_N2_PREFLIGHT_PASS — no GO-equivalent accepted.

Additional fix surfaced by the suite: `service._analyze_frame` now installs
the D1 audio-import seal before importing mediapipe. Without it, the runtime
process pulled `sounddevice` into `sys.modules`, which permanently poisoned
`_runtime_prerequisites()` (`POSE_ENGINE_UNAVAILABLE`) for any later
native-preflight call in the same process — an order-dependent failure
latent since the runtime existed. The seal also makes the no-audio posture
real inside the runtime process.

Docs: `TRACEABILITY_MATRIX.md` gained the seven rows above;
`WORKSPACE_GUIDE_VI.md` documents the new required record fields, the
contamination marker, and the drop/gap counters. `DATASET_SCHEMA.md`
unchanged — the envelope already specified `contaminated_by_operator` as
"True during locked mask interval"; the implementation now honors it.
