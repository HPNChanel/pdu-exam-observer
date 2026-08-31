# M1-R1-V1 Minimal Determinism Receipt

Date: `2026-08-30`

Status: `M1_R1_SOURCE_SUITE_846_OF_846_PASS`

## Scope

This receipt records current-revision verification only. It changes no runtime
source, public API, schema, frontend, package, M2 state, or execution authority.
The package was not rebuilt.

## Environment and observations

- Project interpreter: `.venv\Scripts\python.exe`, Python `3.11.9`.
- Test runner: pytest `8.4.1`.
- Permanently blocked-reader focused repetition: `10/10 PASS`.
- Packaged custom-port smoke repetition: `5/5 PASS`.
- Current source suite: `846/846 PASS` in one clean invocation.
- Observed full-suite durations for the two formerly failing tests:
  blocked-reader `2.05s`; packaged smoke `3.15s`.
- Final local cleanup probe: `PDU_PROCESS_COUNT=0` and
  `PDU_LISTENER_COUNT=0`.

Earlier two full invocations each exposed one distinct load-sensitive timeout:
the packaged health deadline once and the blocked-reader `3.24s` observation
against its `3.0s` bound once. Those observations remain historical evidence.
The later passing evidence does not prove that scheduling variability has been
permanently eliminated, and no timeout or runtime implementation was changed.

## Immutable tuple

- Canonical proposal SHA-256:
  `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.
- Executable SHA-256:
  `EC0D26A9F63AE3EC56EF1A2AC75235DF5E419884697D86C1DB37100604DFD7FF`.
- Detached and bundled manifest SHA-256:
  `9C4DDE09BCE5833CEAAC4EB863171BA0B524368C329D6254E4C360D10D77C256`.
- Package receipt remains `843/843` Python tests, `58/58` frontend tests,
  packaging `8/8`, and 186 files. The current `846/846` source-suite evidence
  is not retroactively assigned to the package.

## Binding authority ceiling

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

M2 remains unopened. This receipt authorizes no camera, participant, real
deletion, signing, distribution, deployment, or release action.
