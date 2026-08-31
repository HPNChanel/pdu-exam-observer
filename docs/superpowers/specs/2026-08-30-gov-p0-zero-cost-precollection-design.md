# GOV-P0 Zero-Cost Pre-Collection Governance Design

Date: `2026-08-30`

Status: `USER_APPROVED_FOR_IMPLEMENTATION`

## Outcome

Defer operational B0.3 because no dedicated custodian device is available, but
preserve its inert kit and every authority boundary. Replace hardware work with
a versioned, machine-verifiable pre-collection governance pack that costs no
participant, camera, key, cloud, or additional device activity.

The final ceiling is:

```text
GOV_P0_STATIC_VERIFIED_EXTERNAL_GATES_PENDING_B0_3_DEFERRED_NO_COLLECTION_AUTHORITY
```

Structural validity is not research readiness. The pack must always retain
`research_ready=false`, `collection_authorized=false`,
`AUTHORITY_NOT_ISSUED`, `physical_camera_access_authorized=false`,
`device_gate_decision=UNVERIFIED`, and `d1_go=false`.

## Boundaries

- Preserve the external B0.3 kit byte-for-byte. Do not run `-Mode Execute`.
- Do not create a production key, bootstrap, signature, A0, PreparedAuthority,
  WorkerGrant, operational receipt, or physical evidence.
- Do not invoke native discovery, FFmpeg, MediaPipe, camera, participant,
  installer, prepare, preflight, seal, or export paths.
- Do not regenerate RP2. A stale RP2 check is a stop condition.
- Keep the canonical proposal byte-identical to SHA-256
  `2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5`.
- M3 remains unopened. Draft labels and methods are planning artifacts only.

## Pack architecture

`research/pre_collection/v1` contains five closed JSON contracts, five
human-readable draft artifacts, an exact-byte manifest, and a validation
receipt. JSON contracts use an envelope containing `schema_version`,
`artifact_kind`, `status`, `body`, and `body_sha256`; the digest covers
canonical JSON of `body` only.

`scripts/build_pre_collection_pack.py` defaults to read-only `--check`.
Explicit `--write` may create only the deterministic manifest and validation
receipt. A valid pack returns exit `0` with `PACK_VALIDATED`; malformed,
noncanonical, incomplete, or semantically unsafe material returns exit `2`
with a bounded failure code. No raw exception or arbitrary path is emitted.

## Research method

The six supervised classes are `NORMAL`, `BENIGN_CONFOUNDER`,
`PROLONGED_HEAD_DOWN`, `PROLONGED_SIDE_LOOK`, `NO_PERSON`, and
`MULTIPLE_PEOPLE`. `UNCERTAIN` is retained for audit and excluded from
supervised targets. `TECHNICAL_INSUFFICIENT` is an operational outcome, not a
behavior class.

Each participant has two continuous 20-minute sessions. Scenario windows are
fixed before a session, last exactly 6,000 ms, and do not overlap. Two pilot
participants contribute 96-120 planned clips; ten confirmatory participants
contribute 540-600; the combined 636-720 target remains inside the proposal's
500-720 range. Pilot samples never enter confirmatory metrics.

Matching is class-aware, one-to-one temporal intersection over union. Reports
show the `0.50` through `0.95` sweep. Primary tIoU, angles, durations,
hysteresis, cooldown, and merge gaps remain null until selected only from
training/calibration or pilot evidence and frozen before confirmatory testing.

## Ethics and data

Participant-facing drafts are Vietnamese and carry
`DRAFT_FOR_INSTITUTIONAL_REVIEW`. They cannot be issued while institutional
approval, responsible contact, retention decision, storage approval, or
template fields are unresolved. Raw video remains local; exports retain the
existing allowlist. The custodian request is a non-authorizing checklist only.

## Acceptance

Acceptance requires deterministic build/check, mutation tests, Ruff, mypy,
proposal-hash verification, unchanged RP2, the focused RP2 artifact test, the
full Python suite, and exact inspection of every pack entry. Passing proves
interface completeness only; institutional approval, consent adequacy,
retention authority, storage controls, method performance, camera behavior,
pilot readiness, and participant collection remain unverified or blocked.
