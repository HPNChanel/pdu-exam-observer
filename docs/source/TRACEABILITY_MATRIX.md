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
