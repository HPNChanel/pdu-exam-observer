# Task 06 — Runtime hardening

**Type:** code + tests (TDD: RED test first for every sub-item).
**Findings:** L1, L2, L3, L4, L6, L10, M3, M7, M8, M9.
**Depends on:** Tasks 01–05. **Note:** largest low-risk task; sub-items are
independent — land them in the written order so each diff stays small and
reviewable. Each sub-item = one RED test + one fix + focused test run.

## 06.1 Literal loopback binding (L1)

- `launcher.py:133` — change monitor bind `host="localhost"` →
  `host="127.0.0.1"` for symmetry with the exam server and the
  "literal loopback" claim.
- Keep `allowed_hosts=("127.0.0.1","localhost")` and
  `monitor_origin=f"http://localhost:{port}"` — the browser may still use
  `localhost` (Host header check accepts both); only the socket bind becomes
  literal. Verify `test_launcher.py` expectations and update the bind-order
  assertion if it encodes `"localhost"`.
- RED test: assert `uvicorn.Config` for both servers receives a literal
  IPv4 loopback string (parameterize over exam/monitor).

## 06.2 Bounded SSE queues and in-memory ceilings (M8)

- `services/core.py`: give the subscriber `asyncio.Queue` a `maxsize`
  (e.g. 512 — pick after checking the largest burst in
  `test_workspace_end_to_end`); on overflow do NOT silently drop — mark the
  subscriber stale/close its stream so the client reconnects and resyncs via
  `after_event_seq`. Add a per-session subscriber cap (e.g. 8) returning 429
  beyond it.
- `repositories/in_memory.py`: cap `SessionRecord.events` and `answers`
  (e.g. 10_000 / 1_000); overflow → explicit failure event, never silent
  eviction of research-shaped data. This is the M0/demo path — keep the cap
  generous enough that the demo fixture (4 events) and UI flows never hit it.
- RED tests: flood a subscriber queue → stream terminates and resync works;
  9th subscriber → 429; event cap → typed failure. Apply the same bound to
  the M1-inherited fan-out (`m1.py:684-685`) via the shared code path.

## 06.3 Bounded pose_timeline read (M7)

- `service.py:1634-1653`: replace the whole-file `handle.read()` with a
  size-capped read — stat the verified file first, refuse beyond a fixed
  ceiling (e.g. 256 MiB — check the largest expected artifact first:
  NOMINAL_20M = 18,077 observations) and/or stream-hash in 1 MiB chunks then
  parse line-by-line. Fail closed `ARTIFACT_*` on oversize, consistent with
  existing artifact failure codes.
- RED test: oversize pose_timeline → typed failure, not MemoryError.

## 06.4 FFmpeg provenance (M3)

- `service.py:1627-1632`: keep the bundled `tools/ffmpeg.exe` preference.
  For the non-frozen fallback, replace bare `shutil.which("ffmpeg")` with:
  explicit env `PDU_FFMPEG_PATH` (absolute, non-UNC) REQUIRED plus a SHA-256
  allowlist `PDU_FFMPEG_SHA256`; verify before use; otherwise fail
  `ENCODER_FFMPEG_UNAVAILABLE`. No PATH resolution.
- Update `docs/spec/SECURITY_PRIVACY.md` + `WORKSPACE_GUIDE_VI.md` if they
  describe the fallback.
- RED tests: PATH-only ffmpeg → unavailable; wrong-hash configured binary →
  rejected; correct pinned binary → accepted (use a tiny fixture binary).

## 06.5 SQL column allowlist (L2)

- `service.py:1771-1774`: add a module-level frozenset of permitted
  `runtime_sessions` column names; assert `changes` keys ⊆ allowlist before
  building the UPDATE — `AssertionError`/`RuntimeError` on violation (this is
  a defense-in-depth assert, not input validation).
- RED test: calling the internal update with a hostile key name → error, no
  SQL executed.

## 06.6 Request model tightening (L3)

- `contracts.py:204-207`: `AnswerRequest` gets `model_config =
  ConfigDict(extra="forbid")` matching sibling models. Check
  `apps/web/src/api.ts` sends only declared fields first.
- RED test: extra field → 422.

## 06.7 Monotonic PIN throttle (L4)

- `services/core.py:54-68`: base the failure-window bookkeeping on
  `time.monotonic()` (dual-clock validated elsewhere is for token expiry —
  the throttle just needs monotonic). Keep the 5/60 s policy and the
  effectively-global loopback bucket (it's protective).
- RED test: simulated wall-clock jump backward/forward must not reset the
  cooldown.

## 06.8 Authority template entry point (M9)

- `__main__.py`: add an `authority-template` route calling
  `authority_cli.template_main` (read `__main__.py` dispatch convention
  first). Update `WORKSPACE_GUIDE_VI.md:66` if the exposed name differs.
- RED test: `python -m pdu_exam_observer authority-template --out <dir>`
  writes the template; exit code contract matches sibling commands.

## 06.9 Preview cleanup (L6)

- `scripts/start_workspace_preview.py`: add a `--stop` mode that reads
  `output/completion-2026-09-08/preview-server.json`, kills the PID's process
  tree (`taskkill /T /F`), and removes the owned temp root only after
  path-containment + `.pdu-owned-verification` marker checks (same pattern
  as `smoke_m1_release.ps1:99-116`).

## 06.10 NaN guard (L10)

- In the canonical JSON writer used by `service.py` (and the analysis path
  around `:1057-1059`), reject non-finite floats — `math.isfinite` gate
  producing `TECHNICAL_INSUFFICIENT`/`POSE_SCHEMA_FAILED` consistent with
  existing failure codes, instead of emitting a `NaN` literal.
- RED test: feed a degenerate frame through `_analyze_frame` → typed failure,
  no `NaN` token in any emitted artifact.

## Acceptance (whole task)

- Every sub-item has its RED→GREEN pair recorded in the task receipt.
- Focused runs green: `pytest tests/backend tests/runtime -q`; Ruff; strict
  mypy. Frontend untouched except api.ts review in 06.6.
- No endpoint, schema, or export-envelope shape changes beyond what's listed
  (export fields unchanged; caps are internal).
- Fail-closed review: every new failure mode maps to an existing typed code.
