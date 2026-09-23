# Task 03 — UI coverage for Task-07 workspace surface

**Type:** frontend tests only. **Depends on:** none.

## Objective

`apps/web/src/WorkspacePanel.test.tsx` has exactly one test. The Task-07
additions — the `mark-contamination` action and the drop/gap metrics — have
backend coverage (`tests/runtime/test_data_model_governance.py`) but zero UI
coverage. A disabled-state or wiring regression would ship silently.

Anchors (`apps/web/src/WorkspacePanel.tsx`):

- `:54` mark-contamination button: enabled iff
  `selected.state === 'RECORDING' && !selected.contaminated_by_operator`;
  `action('mark-contamination')` → `POST /sessions/{id}/mark-contamination`
  with `Idempotency-Key` header (`:37-40`).
- `:55` `role="alert"` notice when `contaminated_by_operator` is truthy.
- `:56` metrics row renders `dropped_frames`, `gap_events`, `max_gap_frames`.

## Steps

1. Extend `WorkspacePanel.test.tsx` (vitest + testing-library, existing
   mock-api pattern — `workspaceRequest` returns session objects keyed by
   path):
   - **Metrics render**: session with `dropped_frames: 12`,
     `gap_events: 3`, `max_gap_frames: 8` → assert the "Khung mất" cell
     shows `12` and "Đứt đoạn" shows `3 / 8 khung`; defaults render `0` when
     fields are absent.
   - **Button gating**: for each of `DRAFT`, `STOPPED`, `SEALED`,
     `RECORDING` states → button enabled only under `RECORDING`; also
     disabled when `contaminated_by_operator: true` even while `RECORDING`.
   - **Action wiring**: click under `RECORDING` →
     `api.workspaceRequest` called with
     `/sessions/<id>/mark-contamination`, `method: 'POST'`, and an
     `Idempotency-Key` header present; `open(id)` re-fetches after action
     (assert second call to `/sessions/<id>`).
   - **Contamination notice**: session with
     `contaminated_by_operator: true` renders the `role="alert"` notice
     text ("Đã đánh dấu nhiễm thao tác…").
   - Reuse the existing session fixture shape; the mock `workspaceRequest`
     must handle both `''` (summary) and `/sessions/<id>` paths as the
     current test does.
2. Gates: `cd apps/web && npm test -- --run WorkspacePanel` then the full
   `npm run typecheck && npm run lint && npm test && npm run build`.

## Acceptance

- The four behaviors above are asserted; test count in
  `WorkspacePanel.test.tsx` grows from 1 to ≥4.
- No component changes required — this is coverage, not behavior change. If
  a test exposes a real defect, stop and record it rather than editing the
  component silently.
- Execution note appended here; commit separately.

## Execution note — 2026-09-23

Implemented as planned — no component changes needed; all assertions pass
against the existing implementation.

`WorkspacePanel.test.tsx` grew from 1 → 4 tests, sharing a `makeApi`/
`openSession` helper:

- metrics render: `Khung mất`/`Đứt đoạn` cells show session values;
- button gating: enabled only under `RECORDING` and not already
  contaminated (`DRAFT`/`STOPPED`/`SEALED`/contaminated-RECORDING all
  disabled, per-state unmount loop);
- action wiring: POST `/sessions/s1/mark-contamination` carries
  `method: 'POST'` + `Idempotency-Key`, followed by a refetch;
- contamination notice: `role="alert"` renders when
  `contaminated_by_operator` is true.

Gates: `npm run typecheck` PASS, `npm run lint` PASS, `npm test` 85/85
PASS (82 + 3 new), `npm run build` PASS — dist bytes unchanged
(`index-Bl2iPLFx.js`) since only the test file changed.
