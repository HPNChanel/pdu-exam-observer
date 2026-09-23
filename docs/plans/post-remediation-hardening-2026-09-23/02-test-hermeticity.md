# Task 02 — Test hermeticity for process-global native state

**Type:** test infrastructure. **Depends on:** none.

## Objective

`m2_d1_native._OUTBOUND_NETWORK_ATTEMPTS` is a module-global counter. Any
test that trips the network guard leaves it `!= 0`, and every subsequent
`_runtime_prerequisites()`/`prepare()` in the same process fails
`POSE_ENGINE_UNAVAILABLE` — the exact order-dependency that broke the suite
during Task 07. Tests currently reset it manually in scattered places
(`tests/backend/test_m2_d1_native.py:673,678`; `:761` asserts `== 1` without
a reset afterward). Make the suite hermetic.

## Steps

1. In `tests/conftest.py` add an **autouse** function-scoped fixture that
   snapshots and restores `m2_d1_native._OUTBOUND_NETWORK_ATTEMPTS` around
   each test:

   ```python
   @pytest.fixture(autouse=True)
   def _reset_outbound_network_attempts():
       import pdu_exam_observer.m2_d1_native as native
       previous = native._OUTBOUND_NETWORK_ATTEMPTS
       native._OUTBOUND_NETWORK_ATTEMPTS = 0
       yield
       native._OUTBOUND_NETWORK_ATTEMPTS = previous
   ```

   Resetting **to zero before** each test is the hermetic part; restoring the
   snapshot afterward preserves any deliberate cross-test accounting (none
   known, but cheap insurance). Do **not** touch `_NETWORK_GUARD_ACTIVE` —
   the guard is intentionally process-wide.

   Scope check: the fixture lives in `tests/conftest.py` so it applies to
   all suites; it must import the module lazily inside the fixture (not at
   conftest import time) so collection order is unaffected.

2. Remove now-redundant manual resets where they exist only to undo a
   previous test's leak (keep any reset that is part of a test's own
   arrange/act, e.g. the `monkeypatch.setattr` at `:533` — leave that one).

3. Cosmetic cleanup in the same commit (cheap, same file class):
   `tests/backend/test_runtime_hardening.py::test_degenerate_frame_fails_closed_without_nan`
   emits `RuntimeWarning` noise from `np.var`/`np.mean` on the degenerate
   frame — wrap the production call under test in `np.errstate(all='ignore')`
   **in the test** (not production code), or filterwarnings-mark it, so the
   suite output stays clean without touching runtime behavior.

4. Gates: run `pytest tests/runtime tests/backend` first in one process
   (the historical pollution order), then the full suite; confirm zero
   order-dependence.

## Acceptance

- `tests/conftest.py` owns the counter lifecycle; no test fails because a
  sibling tripped the guard.
- `test_m2_d1_native.py::...` counter assertions still pass (they set the
  value inside the test itself).
- NaN test no longer emits RuntimeWarnings.
- Execution note appended here; commit separately.

## Execution note — 2026-09-23

Implemented as planned, with two clarifications:

- The autouse fixture in `tests/conftest.py` zeroes
  `_OUTBOUND_NETWORK_ATTEMPTS` before each test and restores the previous
  value afterward; it imports `m2_d1_native` lazily inside the fixture.
- Redundant manual resets removed from
  `test_outbound_python_network_guard_denies_without_native_connection`
  (both were leak-undo; the subprocess script at :755+ keeps its own —
  it runs in a separate interpreter outside conftest scope).
- NaN test: `np.errstate` cannot catch the `Mean of empty slice`
  RuntimeWarning (it is `warnings.warn`, not a float flag) — used
  `@pytest.mark.filterwarnings("ignore::RuntimeWarning")` instead.
  Production code untouched.

Gates: `tests/runtime` + `tests/backend` in one process PASS (the
historical pollution order); full suite PASS; ruff PASS.
