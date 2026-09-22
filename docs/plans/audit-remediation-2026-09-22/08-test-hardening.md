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
