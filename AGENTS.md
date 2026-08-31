# PDU Exam Observer Agent Contract

## Authority

The current approved product and research specifications under docs/spec are authoritative. The canonical source proposal is docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx and must remain byte-identical to the SHA-256 recorded in docs/source/SOURCE_PROVENANCE.md.

## Evidence

Use explicit states for load-bearing claims: OBSERVED, USER_STATED, SOURCE_VERIFIED, DERIVED, PLAUSIBLE, UNVERIFIED, UNKNOWN, or REFUTED. Local tests do not prove camera behavior, two-monitor behavior, package portability, academic approval, research performance, distribution, or deployment.

Read docs/ai/CURRENT_TASK.md, docs/ai/TASK_CONTRACT.md, the relevant spec, and applicable tests before substantive work. Keep CURRENT_TASK accurate only at meaningful milestones.

## Safety and research integrity

- Preserve unrelated work. Never reset, rewrite history, force-push, deploy, publish, or delete data without explicit scoped authority.
- Never weaken validation, authorization, privacy controls, data-split gates, or tests to obtain a pass.
- Never collect a real participant before consent, a retention decision, an approved storage root, and the required institutional approval are recorded.
- Raw video remains local. Colab exports are allowlisted and may contain only the exact pseudonymous export envelope defined in docs/spec/PRODUCT_SPEC.md: export_id, manifest_sha256, schema_version, record_count, sample_id, participant_pseudonym, session_pseudonym, source_kind, parent_provenance_id, pose, label, quality, focus, and timing. Operator identity and operator audit records remain local-only.
- Every sample retains source_kind. AI-rendered or augmented data may not enter calibration or test.
- Do not infer intent, dishonesty, phone use, or identity from webcam behavior. Alerts are evidence for human review, never disciplinary decisions.
- Camera, pose, focus, model, encoder, disk, or schema failure must fail closed as TECHNICAL_INSUFFICIENT or FAILED.

## Engineering

- Target Windows 11 x64, standard-user, offline operation.
- Keep one camera owner and one active collection session.
- Keep exam and reviewer capabilities separated on different loopback origins.
- Add discriminating tests for material behavior. For user-visible flows, obtain actual runtime and visual evidence.
- No CDN, runtime download, telemetry, LAN listener, cloud sync, auto-update, arbitrary file path, arbitrary URL, or shell command from browser input.

## Completion

Before completion, inspect changed artifacts, run the smallest relevant gates, exercise the actual app flow, and report verified facts separately from residual risks. A portable ZIP is not accepted until it runs on the target Windows environment without installed Python, Node, administrator rights, or Internet.
