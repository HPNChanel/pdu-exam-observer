# Task 08 — Test hardening

**Type:** tests (+ at most extraction refactors to create testable seams).
**Findings:** M6, M12. **Depends on:** Tasks 06–07 (tests target final
behavior).

## Objective

Close the discriminating-test gaps the audit found, and fix the one test
that masks drift instead of detecting it.

## Steps

1. **`test_notebook_contract.py` drift fix (M6):** change
   `build_preprocessing_fixture()`/`build_notebook()` calls to write into a
   `tmp_path` destination, then byte-compare against the checked-in
   `research/training/fixtures/preprocessing_golden.npz` (+manifest) and
   `research/training/showcase/v3/pdu_stgcn_training_colab.ipynb`. The test
   must FAIL if committed artifacts drift — today it regenerates them
   in-tree so it can't. Verify the checked-in artifacts match a fresh build
   once; if they don't, regenerate them deliberately and record the
   regeneration in the task receipt (that's a finding, not a silent fix).
2. **REAL `_native_preflight` tests (M12):** the path is hardware-bound
   (`service.py:975-996` — ctypes `GetSystemMetrics`, disk probe, camera
   diagnostics). Extract the pure evaluation into a testable function
   (e.g. `_evaluate_native_preflight(measured_fps, display_count,
   disk_ok) -> decision`) if one doesn't already exist, then unit-test every
   boundary: fps below/inside/above the 12–18 band, 1 vs ≥2 displays, disk
   probe failure. Do not mock the thing under test; mock only the hardware
   probes.
3. **Frozen-rules binding test (M12):** authority `protocol_version`
   mismatch vs `frozen-rules.v1.json` self-hash → REAL path fails with
   `RULE_POLICY_NOT_FROZEN`/`TECHNICAL_INSUFFICIENT` before capture starts.
   (`service.py:1113-1129`)
4. **Withdrawal quarantine branch (M12):** cover
   `QUARANTINE_RUNTIME_ARTIFACTS` (`service.py:881-882`) — currently only the
   DELETE branch is proven.
5. **Workspace negative-auth (M12):** `/api/v1/workspace/*` with missing,
   malformed, expired, and revoked bearer → 401; exam-origin request with
   valid reviewer bearer → still 404/403 (extend
   `test_workspace_api.py`, keep style).
6. **CLI coverage (M12):** `workspace_cli.py` happy path + PIN<6 rejection +
   env cleanup in `finally`; `__main__.py` `workspace` dispatch; the
   `authority-template` route added in 06.8; `research/training/showcase/v3/cli.py`
   REARCH gate (`RESEARCH requires --export and --protocol-freeze`, cli.py:26-27).
7. **Calibration sanity (M12, optional-but-recommended):** a small unit test
   that calibration math on a known fixture moves confidence in the expected
   direction (not a performance claim — a correctness check for
   `calibration.py`), plus `confidence_status` bounds.
8. **SSE/backpressure (M8 follow-up):** tests from 06.2 already cover bounds;
   add one stalled-consumer test asserting the stream closes rather than
   growing memory.

## Acceptance

- New tests are discriminating (they fail if the behavior is removed —
  assert negative space, not just happy paths).
- No existing test edited to weaken assertions; `test_notebook_contract`
  now fails on drift by construction.
- `pytest tests/training tests/runtime tests/backend/test_workspace* tests/backend/test_auth.py -q` green.
- Ruff + strict mypy clean on all touched files.

## Execution note (2026-09-22)

- **08.1 (M6):** `build_self_contained_notebook.py` and
  `scripts/build_training_delivery.py` now emit deterministic bytes (fixed
  ZIP metadata, deterministic NPZ writer). `build_preprocessing_fixture` and
  `build_synthetic_smoke_fixture` accept an optional `fixture_root`.
  `test_notebook_contract.py` builds into `tmp_path` and byte-compares the
  committed `preprocessing_golden.npz` + manifest + `.ipynb`, so committed
  drift fails by construction. The checked-in artifacts were **deliberately
  regenerated once** to remove accumulated timestamp drift — that
  regeneration is recorded here, not silent.
- **08.2 (M12):** pure helpers `_camera_profile_ready(height, width, fps)`
  and `_evaluate_native_preflight(camera_ready, display_count, disk_ok)`
  extracted in `research_runtime/service.py`; hardware probes unchanged.
  `tests/runtime/test_preflight_governance.py` covers fps below/at/above the
  12–18 band, NaN/inf, wrong dimensions, 0/1/2+ displays, disk failure.
- **08.3 (M12):** REAL-session test writes `frozen-rules.v1.json` with a
  mismatched `protocol_version` (valid self-hash) and asserts a
  `TECHNICAL_STATE` event with `reason=RULE_POLICY_NOT_FROZEN` and no
  `RULE_POLICY_BOUND`; a matching-protocol control asserts `RULE_POLICY_BOUND`.
- **08.4 (M12):** quarantine test asserts the owned artifact directory is
  renamed to `<dir>.withdrawn.quarantine`, the original path is gone, and
  the `WITHDRAWAL_RECORDED` receipt carries the decision + artifact inventory.
- **08.5 (M12):** `test_workspace_api.py` now covers malformed bearer
  (garbage token, `Basic` scheme, bare `Bearer`), expired bearer (clock
  advanced past `REVIEWER_BEARER_TTL_SECONDS`), and revoked bearer (post-
  logout). Missing-bearer and exam-origin-with-valid-token cases were
  already covered.
- **08.6 (M12):** new `tests/backend/test_cli_surfaces.py` — subprocess
  dispatch for `authority-template`/`authority`/`workspace --help`; in-process
  `workspace_cli` tests for relative-root rejection, PIN<6 rejection,
  launcher invocation with `PDU_RUNTIME_MODE=m2research`, and
  `PDU_REVIEWER_PIN` cleanup in `finally` on both success and launcher
  failure; subprocess gate that `RESEARCH` mode without `--export` /
  `--protocol-freeze` exits 2.
- **08.7 (M12):** new `tests/training/test_calibration_sanity.py` —
  softmax normalization/shift-invariance/overflow safety, temperature
  monotonicity + direction of `fit_temperature` on known fixtures, fusion
  shape/roundtrip checks, abstention minimum-coverage bound, and the
  `ConfidenceStatus` enum boundary. Correctness only; no performance claims.
- **08.8 (M8 follow-up):** `test_sse_stream_terminates_for_stalled_consumer`
  runs a slow consumer against a flooded bounded queue: the stream closes
  after the stale-marker heartbeat check and detaches the subscriber,
  instead of buffering without bound.
- **Test hygiene found during 08.6:** `workspace_cli.main()` writes
  `PDU_WORKSPACE_ROOT`/`PDU_RUNTIME_MODE`/`PDU_OPEN_BROWSER` into the real
  process environment, so in-process tests leaked `PDU_WORKSPACE_ROOT` into
  `test_launcher.py` and produced a `RUNTIME_ROOT_ALREADY_OWNED` collision.
  `test_cli_surfaces.py` now restores all `PDU_*` keys via a
  `preserve_process_env` fixture; the leak is fixed at the test seam, not in
  production code (the env mutation is the intended launcher contract).
- **Verification:** gate command green (113 tests); full `tests/backend`
  re-run green; `ruff` clean on all touched files; `mypy` (strict,
  `pdu_exam_observer` package) clean — 64 source files.
- **Residual:** NumPy degenerate-frame RuntimeWarnings persist (pre-existing,
  cosmetic — frames fail closed). These tests do not prove real-camera,
  two-monitor, deployment, portability, or research-performance behavior.
