# Proposal traceability matrix

Status: SOURCE_VERIFIED index; the canonical DOCX remains the authority.

Canonical artifact: `docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx`.

The proposal anchors below use the exact requirement names recorded by `SOURCE_PROVENANCE.md:23`. A future final report must add the canonical DOCX page/paragraph locator beside any changed value; a summary or implementation convenience must not be treated as a source change.

| ID | Canonical proposal requirement | Implementing document | Falsifiable acceptance evidence |
| --- | --- | --- | --- |
| P-01 | Research topic and ethical boundary | `docs/spec/PRODUCT_SPEC.md`, `docs/spec/RESEARCH_PROTOCOL.md`, `docs/spec/SECURITY_PRIVACY.md` | No intent, dishonesty, identity, or disciplinary verdict appears in product outputs; reviewer output remains observable evidence. |
| P-02 | Observable labels | `docs/spec/RESEARCH_PROTOCOL.md`, `docs/spec/DATASET_SCHEMA.md` | Label enum and labelbook hash match the frozen protocol; `UNCERTAIN` is retained rather than forced into a class. |
| P-03 | Population range | `docs/spec/RESEARCH_PROTOCOL.md` | Participant and phase counts in the protocol and final receipt match the proposal, or a disclosed deviation is recorded. |
| P-04 | Camera resolution and frame rate | `docs/spec/RESEARCH_PROTOCOL.md`, `docs/spec/PRODUCT_SPEC.md` | Capture configuration receipt matches the proposal before pilot/confirmatory collection. |
| P-05 | No-audio rule | `docs/ai/TASK_CONTRACT.md`, `docs/spec/PRODUCT_SPEC.md`, `docs/spec/SECURITY_PRIVACY.md` | Runtime/package scan and collection receipt show no audio device, audio stream, or audio export. |
| P-06 | MediaPipe landmark scope | `docs/architecture/ARCHITECTURE.md`, `docs/spec/DATASET_SCHEMA.md` | Landmark schema and capture receipt contain only the approved landmark scope. |
| P-07 | ST-GCN direction | `docs/spec/MODEL_EVALUATION_SPEC.md`, `docs/spec/RESEARCH_PROTOCOL.md` | Model manifest identifies the approved temporal model family and revision. |
| P-08 | Context fusion | `docs/spec/MODEL_EVALUATION_SPEC.md`, `docs/spec/RESEARCH_PROTOCOL.md` | Configuration receipt distinguishes rules, camera-only, and context-plus-abstention runs. |
| P-09 | Calibration and abstention | `docs/spec/MODEL_EVALUATION_SPEC.md`, `docs/spec/RESEARCH_PROTOCOL.md` | Split-provenance receipt proves calibration partition separation and records the locked abstention policy. |
| P-10 | Participant-disjoint evaluation | `docs/spec/RESEARCH_PROTOCOL.md`, `docs/plans/ACCEPTANCE_GATES.md` | `scripts/verify_split_provenance.py` receipt proves zero participant overlap and zero pilot samples in confirmatory metrics. |
| P-11 | Pre-collection method and source traceability | `docs/spec/PRE_COLLECTION_GOVERNANCE.md`, `research/pre_collection/v1/source-register.v1.json` | GOV-P0 builder verifies canonical source records, draft-only method fields, the proposal hash, and a fail-closed non-authorizing receipt. |

Any deviation from P-01 through P-10 requires the changed proposal or final report disclosure required by `SOURCE_PROVENANCE.md:25`; passing an implementation test is not a waiver.

## Spec → implementation

Added 2026-09-22 (audit remediation). Requirement IDs refer to
`docs/spec/PRODUCT_SPEC.md` and `docs/spec/DATA_GOVERNANCE.md`. Evidence
states follow AGENTS.md: `TESTED` means a discriminating test exists and
passed; `CODE_VERIFIED` means the code was source-inspected but has no
runtime or hardware evidence.

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| FR-001 separate loopback origins | `launcher.py` dual uvicorn apps; `api/factories.py` Host/Origin middleware | TESTED — `test_launcher.py`, `test_auth.py` |
| FR-002 reviewer PIN, candidate pairing code | `services/core.py` scrypt PIN, single-use `token_urlsafe(12)` pairing | TESTED — `test_auth.py` |
| FR-003 reviewer bearer (digest-only, one active, 2h TTL, revocation) + FR-003a/b | `services/core.py:112-190`; `apps/web/src/api.ts` sessionStorage + POST SSE | TESTED — `test_auth.py`, `api.test.ts` |
| FR-004 session lifecycle DRAFT→…→WITHDRAWN | `domain/state.py`; `research_runtime/service.py` `_require_state` | TESTED — `test_research_runtime.py` |
| FR-005 capture gates (consent, retention, approved root, preflight) | `service.py` `_validate_authority` + `_native_preflight`; `authority_cli.py` install | TESTED (injected diagnostics) — `test_privacy_lifecycle.py`; REAL hardware preflight CODE_VERIFIED |
| FR-006 exam surface (timer, answers, submit) | `services/core.py` exam routes | TESTED — `test_workspace_end_to_end.py` |
| FR-007 candidate isolation | workspace routes exist only on monitor app | TESTED — `test_workspace_end_to_end.py` (exam origin 404) |
| FR-008 persisted, reconnectable events | `runtime_events` UNIQUE(session_id,event_seq); `events_after` | TESTED — `test_research_runtime.py` |
| FR-009 per-event provenance | `source_kind`/`schema_version`/`policy_version`/`source_signals` on every event | TESTED — `test_research_runtime.py` |
| FR-010 failures never become NORMAL | `service.py` `_fail_locked` → FAILED/TECHNICAL_INSUFFICIENT across camera/pose/model/encoder/disk/clock/schema | TESTED — `test_runtime_integrity.py`, `test_privacy_lifecycle.py` |
| FR-011 alerts only on reviewer display | REAL preflight requires ≥2 physical displays (`GetSystemMetrics(80)`) | CODE_VERIFIED — hardware evidence UNVERIFIED |
| FR-012 live monitor skeleton-only; video post-seal | `live_observation` landmarks only; `preview_path` requires SEALED + revalidated authority | TESTED — `test_privacy_lifecycle.py` |
| FR-013 model import rejects bad bundles | `showcase/model_import.py` exact 8-file allowlist, caps, compression-ratio, checksums, atomic activation | TESTED — `test_model_import_contract.py` |
| FR-014 export = pseudonymous 14-field allowlist | `service.py` `EXPORT_FIELDS`, `build_research_export` | TESTED — `test_export_contract.py`, `test_workspace_end_to_end.py` (no media/db in ZIP) |
| FR-015 demo labeled, never implies real | `CreateRequest` defaults `AI_RENDERED`; `synthetic:true` events | TESTED — workspace/research tests |
| Governance: real-capture authority record | `authority_cli.install_authority` (root-bound digests, compare-and-swap) + `service.py` revalidation | TESTED — `test_authority_cli.py`, `test_privacy_lifecycle.py`; authenticity of referenced documents is out of scope by design (R-43) |
| Governance: withdrawal deletes owned inventory only | `service.py` `withdraw` + `_withdrawal_artifact_inventory_locked` (untracked files rejected) | TESTED — `test_privacy_lifecycle.py` |
| Protocol freeze before outer-test | `research/training/showcase/v3/protocol.py` self-hash `status=FROZEN` | TESTED — `test_protocol_freeze.py` |
| Participant-disjoint splits; pilot excluded; synthetic never in cal/test | `research/training/showcase/v3/splits.py` | TESTED — `test_split_augmentation_contract.py` |
| Evaluation (tIoU sweep, class-aware matching, continuous denominators) | `research/training/showcase/v3/evaluation.py` | TESTED — `test_continuous_event_evaluation.py` |
| Shared preprocessing (runtime = training) | `showcase/preprocessing.py` single implementation, golden-byte fixture | TESTED — `test_preprocessing_contract.py` |
| Model bundle contract (8 files, no pickle) | `showcase/model_import.py`, `showcase/model_runtime.py` | TESTED — `test_model_import_contract.py`, `test_training_round_trip.py` (synthetic smoke only — no performance claim) |
| Packaging: deterministic bundle + manifest verification | `scripts/build_completion_delivery.py`, `packaging/PDU-Workspace.spec`, `scripts/release_manifest.py` | TESTED same-host — `tests/packaging/*`; clean-machine UNVERIFIED (GAP-08) |

P-04 (camera profile) is checkable against `service.py` capture profile and
`scripts/check_workspace_camera.py` output; current host measures ~10.08 fps
at 1280x720 and fails closed below the 15 fps requirement — recorded in
`output/completion-2026-09-08/workspace-camera.json`.
