# Implementation Plan

## Global constraints

Target Python 3.11 and Node 24 for development, Windows 11 x64 for runtime, literal loopback only, standard-user execution, offline assets, schema version 1, strict source provenance, and no personal data in source or release artifacts.

## Completed foundation

Tasks 1-8 established provenance, domain contracts, secure local API, frontend surfaces, deterministic demo replay, launcher/configuration, packaging, and focused verification. Their current local regression receipt is 73 Python tests, Ruff, mypy for 14 files, frontend 9 files/57 tests with typecheck/lint/build, M0 smoke, 182 manifest entries with 0 forbidden, 5/5 dist/package match, exact executable/manifest hashes recorded in `docs/ai/CURRENT_TASK.md`, packaged browser/runtime `PASS`, Sol advisory `ACCEPT`, and zero remaining processes/listeners.

## M1 - Persistence and governance: locally verified

M1 implementation is complete locally and governed by `docs/spec/M1_PERSISTENCE_SPEC.md`.

- Select explicit `PDU_RUNTIME_MODE=m1`; retain M0 in-memory default.
- Configure an absolute research root through `%LOCALAPPDATA%\PDUExamObserver\config.v1.json`; keep the database outside the bundle.
- Open SQLite with WAL and foreign keys; validate schema version 1, migration checksum, canonical objects, columns, indexes, unique constraints, and foreign keys.
- Persist studies, opaque participants, research sessions, consent/retention receipts, exam/answer metadata, event sequence, idempotency responses, artifact lineage, withdrawal receipts/tasks, write intents, and audit events.
- Commit mutations and event rows before subscriber/SSE publication. Reuse responses for matching idempotency keys and reject mismatched reuse.
- Keep reviewer credentials memory-only and expose research routes only through the monitor bearer boundary.
- Return typed fail-closed readiness. Institutional approval, retention authority, storage-control attestations, and collection-not-implemented remain blockers; research cannot enter `RECORDING`.
- Make withdrawal participant-wide, terminal, idempotent, lineage-invalidating, and export/collection blocking; quarantine pending partials on restart.

M1 smoke and the current Python/frontend/package/browser receipts are `OBSERVED` local evidence. `VERIFIED` encryption/ACL values in smoke are test attestations only.

## Unopened later tasks

M2 through M7 follow the roadmap and their governing specs only after explicit authorization and new evidence. M2 webcam/capture/pose work is not authorized by M1 persistence routes. M3 labels/rules, M4 pilot, M5 confirmatory/demo corpora, M6 training/model import, and M7 evaluation/trial release remain unopened.

No implementation task waives consent, retention, institutional approval, participant-disjoint evaluation, human review, or the prohibition on automatic person-level verdicts.
