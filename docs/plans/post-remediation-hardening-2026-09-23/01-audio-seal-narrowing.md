# Task 01 — Narrow the audio-seal write surface

**Type:** code + test. **Depends on:** none.

## Objective

The Task-10 torch fix made `_DisabledMediaPipeAudio` allow **all** dunders
through `__setattr__` (and `__getattribute__`). Only reads needed relaxing —
`inspect.getmodule` reads `__file__`. A writable `__path__` would
(theoretically) let the disabled stub behave like a package. Restore the
minimal write surface.

## Current state

`src/pdu_exam_observer/m2_d1_native.py:139-155`:

- `__getattribute__` allows `_allowed` ∪ all dunder names — **keep**: reading
  module metadata (`__file__`, `__doc__`, `__name__`, …) is harmless and is
  exactly what `inspect`, `torch`, and import machinery need.
- `__setattr__` allows the same broad dunder set — **narrow**: only the five
  explicit names (`__name__`, `__package__`, `__loader__`, `__spec__`,
  `DISABLED`) may be written. Everything else raises `RuntimeError`, exactly
  as before the Task-10 widening.

Note: `_install_audio_import_seal` (`:158-172`) sets `__package__` and
`DISABLED` — both already in the explicit list, so the seal's own install
path is unaffected.

## Steps

1. Test first (`tests/backend/test_m2_d1_native.py` — extend the existing
   seal tests):
   - `disabled.__file__` (and e.g. `__doc__`) is **readable** without
     `RuntimeError` — guards the torch/`inspect.getmodule` regression.
   - `disabled.__path__ = [...]` raises `RuntimeError` — the new
     discriminating assertion for the narrowed write surface.
   - `disabled.anything = x` raises `RuntimeError` (non-dunder, unchanged).
   - `mediapipe.tasks.python.audio` attribute access for a real audio
     attribute (e.g. `AudioClassifier`) still raises `RuntimeError`.
   - `import sounddevice` still `ImportError`s via `_AudioImportDenyFinder`
     after seal install.
2. Implement: revert `__setattr__` to the explicit five-name allowlist.
3. Gates: `pytest tests/backend/test_m2_d1_native.py
   tests/training/test_training_round_trip.py` (the torch import path that
   motivated the original widening), ruff, mypy.

## Acceptance

- `__setattr__` is the five-name allowlist only; `__getattribute__` keeps
  dunder reads.
- New assertions above pass; the training round-trip (PyTorch `inspect`
  path) still passes.
- Execution note appended here; commit separately.

## Execution note — 2026-09-23

Implemented as planned. `__setattr__` restored to the explicit five-name
allowlist (`_allowed`); `__getattribute__` keeps dunder reads so
`inspect.getmodule`/PyTorch introspection still works.

New test `test_disabled_mediapipe_audio_surface_is_read_only_metadata`
asserts: `__file__`/metadata readable without RuntimeError; audio
attributes sealed on read; non-dunder AND non-allowlisted dunder writes
(`__path__`) sealed. RED→GREEN confirmed.

Gates: focused tests + full `test_m2_d1_native.py` (145 tests) PASS;
`test_training_round_trip` PASS (torch import path preserved); ruff PASS;
mypy PASS (64 files). RP2 regenerated once for this source change:
digest `ca9e6118…`, candidate `905fb054…` — test constants updated in
`test_m1_r1_governance_closure.py`.
