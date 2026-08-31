# M2 Readiness Pack

Version: 0.4

Status: `D1_N1_NATIVE_PREFLIGHT_AUTHORIZED_IMPLEMENTATION_ACTIVE`

Current decision: `M2_S1_ACCEPTED`, `P1_ACCEPTED`, and `M2_D1_N1_NATIVE_PREFLIGHT_GO`

P1 implementation status: `P1_ACCEPTED`

## Authority and decision

User approval date: `2026-08-26`.

User decision `2026-08-26` accepts P1 and opens the separately revision-scoped D1 no-human device-validation boundary. The immutable proposal is `docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx`, SHA-256 `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`.

`SOURCE_VERIFIED`: the proposal and binding specifications require no audio, observable rather than intent-based labels, abstention, human review, provenance separation, and participant-disjoint evaluation. `OBSERVED`: M1 has SQLite governance and recovery but does not implement camera capture, pose processing, encoding, inference, or collection. `DERIVED` controls below are admission criteria, not research findings or participant authorization.

Authorization is non-transitive:

| Rung | Scope | Current state |
|---|---|---|
| R0 | Documentation and user review | `M2_R0_ACCEPTED` |
| S1 | Pure backend synthetic exercise | `M2_S1_ACCEPTED` |
| P1 | v1-to-v2 persistence migration and manifest design | `P1_ACCEPTED` |
| D1 | No-human device validation | `D1_N1_NATIVE_PREFLIGHT_AUTHORIZED_IMPLEMENTATION_ACTIVE` |
| Participant collection | Any real-person capture, storage, or processing | `NOT_AUTHORIZED` |
| M4 participant consideration | Pilot consideration after M2/M3 and external gates | `NOT_AUTHORIZED` |

Authorization vector for this revision:

```text
M2_S1_SYNTHETIC_PREPARATION_AUTHORIZED=true
M2_P1_PERSISTENCE_MIGRATION_AUTHORIZED=true
M2_D1_NO_HUMAN_DEVICE_VALIDATION_AUTHORIZED=true
M2_D1_N1_PHYSICAL_CAMERA_ACCESS_AUTHORIZED=true
M2_D1_N1_PRETRAINED_TECHNICAL_INFERENCE_AUTHORIZED=true
M2_PARTICIPANT_COLLECTION_AUTHORIZED=false
M2_MODEL_TRAINING_OR_EVALUATION_AUTHORIZED=false
```

These booleans are non-transitive and revision-scoped. D1-C1 remains injected-only evidence. The active D1-N1 slice permits exactly one server-owned video camera and one 60-second preflight after dependency/model/FFmpeg/privacy/owner gates. It requests no audio, retains no raw frame, and has no HTTP/UI, SQLite/M1/P1, seal/export, participant, or research model-evaluation surface. It may return at most `D1_N1_PREFLIGHT_PASS` with `device_gate_decision=UNVERIFIED`, never `D1_GO`.

Participant consideration is an M4 decision only after accepted M2 and M3 evidence plus institutional approval, documented consent, retention authority, storage authority, accepted no-human device evidence, frozen protocol controls, and explicit user authorization. A synthetic fixture, a green test, or a device run cannot transitively authorize a participant.

## Preserved M1 baseline

`OBSERVED`: M0 remains the default in-memory mode. Explicit `PDU_RUNTIME_MODE=m1` activates native configuration and SQLite/WAL metadata storage outside the bundle. M1 readiness is fail-closed: `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional, research sessions cannot enter `RECORDING`, and startup rejects persisted research `RECORDING` state. Withdrawal is participant-wide and terminal; restart recovery quarantines pending partial artifacts. P1 must preserve all of these M1 facts.

The exact M1 local evidence remains unchanged: 73 Python tests; Ruff; mypy for 14 files; frontend 9 files and 57 tests with typecheck/lint/build; M0/M1 smoke; 182 manifest entries and 0 forbidden items; 5/5 package match; executable SHA-256 `30C191FFBC8729736377B8800ADA80459187504772E30B77E7FD0DDCBFD97F27`; detached and bundled manifest SHA-256 `071849B5AB94C60D90F184282C66B6FBBC5FE133AB888304DAAD22DC6D5CFCAC`; packaged Chromium browser/runtime `PASS`; Sol visual advisory `ACCEPT`; user visual acceptance `PENDING`.

Those are local-only facts. They do not establish camera behavior, physical-device privacy, encoder or disk throughput, encryption/ACL enforcement, institutional approval, participant access, model performance, clean-machine portability, signing, deployment, release, or production.

## S1: authorized pure synthetic implementation boundary

S1 is authorized only as a pure backend/dependency-injected exercise in `src/pdu_exam_observer/m2_synthetic.py` and `tests/backend/test_m2_synthetic.py`, with optional repository-safe fixtures under `tests/fixtures/m2`. It receives a deterministic input provider, pose-result provider, monotonic clock, and a non-writing sink. The current implementation changed only those two code files and is locally verified pending explicit user gate review.

S1 must not import a camera/device library, enumerate OS devices, access a camera, expose HTTP, modify UI, open SQLite, write the research root, create or mutate an M1 session, accept a participant/session ID, use `REAL` provenance, emit `AlertEvent`, emit a research label, or emit confidence. M1 lifecycle and readiness behavior, including unconditional `RESEARCH_COLLECTION_NOT_IMPLEMENTED`, stay unchanged.

### S1 MICRO_PLAN

1. Add immutable, dependency-injected technical fixture and observation contracts in `m2_synthetic.py`, including allowlisted failure semantics and canonical fixture/result digests.
2. Add deterministic fixture cases and a non-writing sink in `test_m2_synthetic.py`; use `tests/fixtures/m2` only when a fixture file improves a hash/digest assertion.
3. Add discriminating and output-compatible mutant tests for malformed input, clock regression, invalid pose shape/mask, quality failure, pose-engine unavailability/exception, and unknown schema/failure values.
4. Add boundary tests proving no forbidden imports, device enumeration, HTTP/UI interfaces, SQLite/research-root writes, participant/session IDs, `REAL` provenance, `AlertEvent`, research label, confidence, or M1 lifecycle/readiness mutation.
5. Assess the resulting S1 evidence against the acceptance ledger before any separate P1 decision; do not infer P1, D1, participant, or model authority from an S1 pass.

### S1 acceptance evidence

S1 acceptance requires deterministic fixtures with fixture/input hashes; canonical expected-output and observed-result digests; explicit TechnicalObservation field and topology/mask validation; one result for every fixture input with reconciled delivered/processed/drop/failure accounting; exact allowlisted failure codes; direct fault tests and output-compatible mutants; proof that the non-writing sink observes no SQLite or research-root write; static/import-level proof of no camera/device libraries or OS enumeration; and interface-level proof of no HTTP/UI, participant/session IDs, `REAL` provenance, `AlertEvent`, research label, confidence, or M1 lifecycle/readiness changes.

A superficially output-shaped result that substitutes zero pose for an exception, silently clamps a clock regression, truncates landmarks, silently excludes quality-insufficient frames, accepts an unknown digest/schema, or emits a forbidden research-shaped field fails S1. Passing S1 proves only constrained pure-fixture behavior; it does not prove capture, pose quality on real imagery, persistence, device performance, privacy in a device environment, or research validity.

`OBSERVED` local S1 evidence: TDD initial missing-module RED; first GREEN (`17 passed`); verifier `NO-GO` because valid observations did not enforce supplied golden digest equality and scoped Ruff had 29 errors; targeted golden-mismatch RED; corrected focused pytest (`18 passed in 0.07s`), Ruff (`All checks passed`), mypy (`Success: no issues found in 1 source file`), and Luna/medium independent verifier `APPROVE`. The user accepted S1 on `2026-08-25`; this did not transitively accept P1, D1, participant collection, or model work.

For a valid deterministic result, the canonical observed digest excludes both `result_digest` and `golden_expected_output_digest`, avoiding circular self-hash semantics. It must equal the supplied golden before a valid success is emitted. A mismatch produces a deterministic `FAILED` observation with `MANIFEST_VALIDATION_FAILED`, absent `pose_count`, and a recomputable failure digest; the sink receives that failure observation, never a success.

The only S1 input categories are:

```text
TechnicalInputKind = DETERMINISTIC_FIXTURE | AI_RENDERED_FIXTURE | NO_HUMAN_DEVICE_SCENE
```

`TechnicalInputKind` is deliberately separate from `SampleProvenance.source_kind`. It is excluded from dataset export, calibration, test, training, research labels, and participant lineage. `NO_HUMAN_DEVICE_SCENE` is reserved for later D1; its frames are ephemeral by default. An incidental person, voice, identity-bearing reflection, or unapproved screen content is `PRIVACY_STOP`: stop, invalidate the run, do not seal, do not export, and retain only permitted non-sensitive audit evidence.

The synthetic empty-scene case is only an input/pose-count/quality exercise. It is not an assertion about a participant or a research event.

## Proposed TechnicalObservation contract

This proposed in-memory contract has `schema_version: 1` and is neither a persisted study record nor an API response.

| Field | Required rule |
|---|---|
| `technical_input_kind` | One of the three technical categories above |
| `fixture_id`, `fixture_version` | Opaque allowlisted identifiers, never paths or participant/session IDs |
| `run_id` | Opaque technical-run ID, never a research session ID |
| `frame_seq` | Non-negative and strictly increasing within a run |
| `captured_monotonic_ns` | Non-negative monotonic clock value |
| `processed_monotonic_ns` | Not earlier than capture when processing succeeds |
| `pose_engine_task_hash` | SHA-256 of the exact pose-engine and task/configuration contract used for this result |
| `preprocessing_id` | Immutable allowlisted preprocessing identifier |
| `landmark_topology_version` | Immutable topology/version identifier; rejects an unknown or mismatched topology |
| `landmarks` | At most 2 pose sets, each exactly 33 ordered landmark records `{x,y,z,visibility}`; no truncated, reordered, or extra set is valid |
| `landmark_missing_mask` | Explicit 2 x 33 boolean mask; every absent/unusable landmark is true and every present landmark is false |
| `pose_count` | Only `0`, `1`, or `2`; it must equal the number of complete, non-masked pose sets and is absent for an unprocessed failure |
| `quality_state` | `VALID`, `INSUFFICIENT`, or `FAILED` |
| `processing_state` | `PROCESSED`, `DROPPED_EXPLICIT`, or `FAILED` |
| `failure_code` | Null only for a valid processed result; otherwise allowlisted below |
| `latency_ms` | Measured non-negative capture-to-process latency; absent if processing did not begin |
| `fixture_input_hash` | SHA-256 of canonical fixture/input metadata, never a raw path or participant identifier |
| `golden_expected_output_digest` | Required deterministic expected-result digest for fixture runs; `NO_HUMAN_DEVICE_SCENE` records `N/A` with a stated non-determinism reason |
| `result_digest` | SHA-256 of the canonical TechnicalObservation result, compared to the golden digest when one is required |

Allowlisted failure codes are `INPUT_UNAVAILABLE`, `INPUT_MALFORMED`, `FRAME_STALLED`, `CLOCK_REGRESSION`, `POSE_ENGINE_UNAVAILABLE`, `POSE_ENGINE_EXCEPTION`, `POSE_OUTPUT_INVALID`, `QUALITY_INSUFFICIENT`, `ENCODER_UNAVAILABLE`, `ENCODER_WRITE_FAILED`, `ENCODER_FINALIZE_FAILED`, `DISK_UNAVAILABLE`, `DISK_SPACE_INSUFFICIENT`, `DISK_THROUGHPUT_INSUFFICIENT`, `DISK_FSYNC_FAILED`, `ATOMIC_RENAME_FAILED`, `MANIFEST_VALIDATION_FAILED`, `SCHEMA_INCOMPATIBLE`, `PRIVACY_STOP`, and `UNKNOWN_TECHNICAL_FAILURE`. An unknown code is `SCHEMA_INCOMPATIBLE`. Failure never becomes normal/success semantics, numeric confidence, `AlertEvent`, or a participant conclusion.

## P1 persistence and artifact lineage prerequisite

`OBSERVED`: current SQLite v1 validates canonical DDL, columns, indexes, unique constraints, foreign keys, migration checksum, and schema version; it rejects malformed or unknown newer state. Current `artifact_registry` only has artifact ID, session ID, validity status, and time. It lacks artifact type, technical input kind, provenance, hash, relative path, capture profile, timing origin, manifest version, and failure state.

P1 therefore requires a separately reviewed forward `v1 -> v2` migration and manifest design. It must validate v1, apply one migration-ledger entry, validate canonical v2 DDL, and reject malformed, partial, checksum-mismatched, or unknown newer state. In-place v1 edits are prohibited.

The v2 manifest design must allow only opaque artifact/parent IDs, technical input kind, permitted dataset source kind only when a real dataset artifact is later authorized, manifest schema version, manifest-owned relative path, byte size, SHA-256, capture profile version, monotonic timing origin, processing version, failure code/null, sealing time, and validity state. It must exclude names, contacts, consent images, raw browser paths, URLs, window titles, process names, tokens, cookies, PINs, audio, and identity mappings.

Future atomic write/recovery order is fixed:

```text
validate opaque intent and session mutability
-> derive allowlisted staging partial path
-> write partial
-> fsync file and parent directory where supported
-> verify byte count and SHA-256
-> atomic rename to validated final relative path
-> BEGIN IMMEDIATE: manifest + registry + dependencies + event + idempotency response
-> COMMIT
-> publish only after commit
```

Before commit, no completed manifest exists. A partial remains intent-tracked. Restart revalidates and quarantines incomplete data; its session becomes `FAILED` unless terminal `WITHDRAWN` already applies. Withdrawal wins over later write/export intents and invalidates reachable lineage.

## D1 native-device boundary

D1 is no-human device validation only. It requires a fresh authorization. Server-side enumeration may expose only opaque current-device selections; browser input may never provide a device ID, path, URL, command, model location, media path, or export destination. There is one camera owner and one active collection-capable process. Audio is never enumerated, requested, captured, encoded, stored, or exported. Raw frames are never logged, statically mounted, or resolved by arbitrary path.

## Derived technical thresholds

| Area | `DERIVED` gate |
|---|---|
| Profile | Exact target `1280x720@15fps`; record negotiated profile and reject unsupported profile. |
| Runs | 60-second no-human preflight and 20-minute no-human run. |
| Warmup | First 5 seconds excluded from fps/latency percentiles but all warmup faults remain counted. |
| Delivered fps | At least 13.5 fps after warmup: `delivered_frames / measured_post_warmup_seconds`; every drop is explicit. |
| Frame gaps | p95 inter-delivery gap at most 200 ms; any gap at least 1000 ms is `FRAME_STALLED`. |
| Pose latency | p95 capture-to-pose latency at most 200 ms; p99 at most 500 ms. |
| Backlog | At most 2 seconds: newest capture monotonic time minus newest completed processing monotonic time. |
| Free space | At least `max(2 GiB, 2 x measured_byte_rate x planned_duration_seconds)`. |
| Disk preflight | 60-second write p10 throughput at least 2 times the measured encoded byte rate. |
| Safety | Zero false seals and zero privacy violations. |

For the 20-minute no-human nominal run, record separate post-warmup denominators: `delivered_frames`; `inter_frame_gaps=max(delivered_frames-1,0)`; `processed`; `dropped_explicit`; `failed`; and `quality_insufficient`. The exact reconciliation is `processed + dropped_explicit + failed = delivered_frames`. `quality_insufficient` is a separately reported subset of processed results and is never silently excluded from any count or selected away as an easy frame.

Require processed coverage of at least 99%: `processed / delivered_frames >= 0.99` when delivered frames are nonzero. Require total explicit processing drop plus failure at most 1%: `(dropped_explicit + failed) / delivered_frames <= 0.01`. A zero-delivery run is `INPUT_UNAVAILABLE`, never a vacuous pass. Delivery FPS uses measured post-warmup duration; frame-gap percentiles use exactly `inter_frame_gaps`; latency percentiles use processed results only. A threshold breach is `QUALITY_INSUFFICIENT`, `FRAME_STALLED`, `POSE_ENGINE_UNAVAILABLE`, `POSE_ENGINE_EXCEPTION`, `DISK_THROUGHPUT_INSUFFICIENT`, or another exact applicable failure code and produces technical insufficiency, not selection of easier frames.

Use nearest-rank percentiles and one value per delivered frame where the denominator specifies delivered frames. Missing values, non-monotonic timestamps, clipped negative latencies, overwritten counters, denominator mismatch, or unaccounted drops are `SCHEMA_INCOMPATIBLE`, not favorable values.

## Failure-injection ledger

Each future gate needs both the direct fault and an output-compatible mutant.

| Fault or mutant | Required fail-closed result |
|---|---|
| Input unavailable | `INPUT_UNAVAILABLE`; no seal. Reject an empty result treated as valid zero pose. |
| Frozen capture timestamp with advancing sequence | `FRAME_STALLED`; reject falsely advancing counters. |
| Clock regression | `CLOCK_REGRESSION`; reject negative latency clamped to zero. |
| Pose engine absent or raises | `POSE_ENGINE_UNAVAILABLE` or `POSE_ENGINE_EXCEPTION`; reject exception translated to pose count zero. |
| Invalid count, topology, mask, or landmark shape | `POSE_OUTPUT_INVALID`; reject truncated, reordered, or extra landmarks accepted as usable. |
| Quality failure | `QUALITY_INSUFFICIENT`; reject low visibility interpreted as normal. |
| Encoder cannot open | `ENCODER_UNAVAILABLE`; reject a fabricated encoder-ready result. |
| Encoder write error | `ENCODER_WRITE_FAILED`; reject zero-byte success manifest. |
| Encoder flush/finalize error | `ENCODER_FINALIZE_FAILED`; reject a finalized/sealed state before completion. |
| Disk capacity failure | `DISK_SPACE_INSUFFICIENT`; reject a partial marked sealed. |
| Disk throughput below gate | `DISK_THROUGHPUT_INSUFFICIENT`; reject average throughput masking a failing p10. |
| Disk fsync error | `DISK_FSYNC_FAILED`; reject sealing before durability check. |
| Rename failure | `ATOMIC_RENAME_FAILED`; reject a registry row whose final file does not exist. |
| Manifest hash mismatch | `MANIFEST_VALIDATION_FAILED`; reject a substituted digest. |
| Manifest schema/version mismatch | `SCHEMA_INCOMPATIBLE`; reject a substituted version. |
| Withdrawal race | `PRIVACY_STOP`; no new write and terminal withdrawal preserved. |
| Incidental person/prohibited content | `PRIVACY_STOP`; invalidate, retain no frame/export. |

## Readiness receipts and gate ledgers

Receipts state facts, not inferred approval. Repository-safe material has no raw frames, device IDs, local usernames, paths, participants, secrets, or private-storage topology. Local-only material remains outside source control and exports.

| Receipt | Minimum content | Location |
|---|---|---|
| Authority/spec/source | Rung, decision owner, booleans, proposal hash, spec versions | Repository-safe |
| Ethics/institutional/consent/retention | Approval status/reference, opaque consent ID/version, retention authority | Local-only |
| Storage | Root-control attestation, free-space calculation, encryption/ACL status | Local-only; attestation is not proof |
| Fixture | Fixture/generator version, fixture/input hash, golden expected-output digest, observed result digest | Repository-safe |
| Environment | Exact OS/build, app executable/revision hash, release-manifest hash, camera/driver class without serial, pose engine/task hash, encoder version/hash, CPU/GPU class, locale/timezone, offline state | Local-only for device identity-adjacent facts; repository-safe only when redacted to non-identifying aggregate |
| Capture/pose/failure/privacy | Profile, accounting, quality/failure counts, no-human stop result | Local-only for D1; synthetic aggregate may be repository-safe |
| Withdrawal/reproduction/gate decision | Opaque task counts, deterministic expected digest, evidence references, explicit GO/NO-GO | Local-only withdrawal data; other fields repository-safe |

R0 and S1 are accepted as of `2026-08-25`; P1 is accepted and D1 no-human validation is authorized as of `2026-08-26`. D1-C1 may exercise every threshold, accounting rule, privacy receipt, ownership abstraction, no-audio interface invariant, and failure mutant with injected observations, but a pass retains `device_gate_decision=UNVERIFIED`. Physical D1 still requires the native profile, 60-second/20-minute no-human runs, OS-level one-camera-owner/no-audio proof, and exact environment/reproduction receipts. Participant collection and model training/evaluation remain `NOT_AUTHORIZED`.

An EnvironmentReceipt records exact OS/build; app executable/revision and release-manifest hashes; camera/driver class without serial; pose engine/task hash; encoder version/hash; CPU/GPU class; locale/timezone; and offline state. A ReproductionReceipt records one exact clean reproduction command, input/fixture hashes, deterministic settings/seeds or an explicit `N/A` reason, expected output manifest/digests, and observed output digests. The exact command must be executable from a clean declared environment without interactive substitution; a command omitted, parameterized by an unstated value, or producing a different observed digest is `SCHEMA_INCOMPATIBLE` for that receipt.

## Stop conditions and execution sequence

Immediately stop and record only permitted non-sensitive audit evidence for incidental person/prohibited content; an authority/control required by the active technical rung being absent, mismatched, or uncertain; unallowlisted path/device/source/schema/failure input; audio or multi-owner violation; incomplete measurement accounting; unsafe partial recovery; withdrawal/write race; or any failure translated to normal/success. Institutional approval, participant consent, and participant retention authority are required stop conditions only for M4/real-person activity; their absence does not block S1, P1, or D1 technical work unless a rung-specific authority/control is required. Participant collection remains false. The affected rung is `NO_GO` and restart does not resume it automatically.

Execute D1 only within its active plan and acceptance ledger. Keep injected backend evidence distinct from native-device evidence, and keep participant collection and model training/evaluation closed until their independent gates are accepted.

## RoutingReceipt

```json
{
  "schema_version": 1,
  "writer": {"model": "Terra", "reasoning_effort": "high", "role": "implementation_builder", "scope": "M2_D1_BACKEND_CONTRACT_EXERCISE"},
  "prior_p1_security_review": {"status": "APPROVE", "model": "Terra", "reasoning_effort": "max", "role": "security_reviewer"},
  "research_privacy_review": {"status": "APPROVE", "model": "Sol", "reasoning_effort": "xhigh", "role": "research_methodologist"},
  "decision_owner": "root",
  "implementation_authorized": true,
  "authorized_implementation_scope": "M2_D1_N1_NATIVE_VIDEO_ONLY_PREFLIGHT",
  "persistence_migration_authorized": true,
  "p1_accepted": true,
  "no_human_device_validation_authorized": true,
  "physical_camera_access_authorized_for_current_slice": true,
  "pretrained_technical_inference_authorized": true,
  "participant_collection_authorized": false,
  "model_training_or_evaluation_authorized": false
}
```

## D1-C1 implementation evidence and residuals

`OBSERVED` on `2026-08-26`: the injected-only D1 backend contract is limited to `src/pdu_exam_observer/m2_d1_contract.py` and `tests/backend/test_m2_d1_contract.py`. It accepts only `TEST_CHART` or `SYNTHETIC_VIDEO` with `SIMULATED` evidence; a success is only `BACKEND_CONTRACT_PASS` with `device_gate_decision=UNVERIFIED`. The interface has no native/device/audio/path/URL/browser, HTTP/UI, SQLite/M1/P1, persistence/seal/export, participant/session, `REAL`, label/confidence/alert, model, or `D1_GO` surface.

TDD and review evidence: initial missing-module RED; an observed `ENCODER_WRITE_FAILED` false pass; independent Sol/xhigh `NO-GO` rounds for semantic relabel/rehash, zero-byte success, timestamp/backlog errors, incomplete/unbound receipts, quality-failure success, privacy evidence after stop, provenance placeholders, and missing mutants; targeted remediation RED included `8 failed, 28 passed`. Final focused pytest emitted 45 passing markers; scoped Ruff reported `All checks passed!`; scoped mypy reported `Success: no issues found in 1 source file`; final independent Sol/xhigh review returned `APPROVE`. Root independently observed `uv.lock` SHA-256 `BAF657E935BD76C34E097C6D7F02EBED902758B965148E5585F1CC7CAD8B608C`, matching the bound constant.

The final contract fail-closes exact profile/run kinds, first-capture warmup, monotonic/end-bounded timestamps, accounting, nearest-rank thresholds, backlog, positive/reconciled encoder bytes, capacity/p10, stage states, exclusive injected ownership, privacy-first minimal stop receipts, strict authority/provenance/environment/reproduction binding, semantic rehash mutants, and the failure ledger. This is `D1_BACKEND_CONTRACT_LOCALLY_VERIFIED_PENDING_NATIVE_EVIDENCE`, not physical/native evidence.

`UNVERIFIED`: physical camera enumeration/access/ownership/profile; OS-level audio non-access; actual 60-second and 20-minute runs; native capture/pose/encoder/disk/fsync/rename/privacy behavior; packaged runtime; participant/institutional evidence; model performance; deployment; release; production; and `D1_GO`.

## Historical P1 implementation evidence and residuals

The P1 status statements below are historical receipts captured before the explicit `2026-08-26` user acceptance. They are retained as remediation evidence and do not override `P1_ACCEPTED` in the current decision vector.

`OBSERVED` local P1 evidence on `2026-08-25`: the additive backend seam is limited to `src/pdu_exam_observer/m2_persistence.py` and `tests/backend/test_m2_persistence.py`. It retains canonical v1 DDL, applies one v2 ledger entry with an additive manifest/intent schema, validates exact v2 objects, uses injected deterministic/AI-rendered byte sources, derives local contained paths, and inserts manifest/registry/dependencies/event/audit together only after verified rename. P1 has no route, UI, device, audio, participant-creation, model, or export interface.

Exact final local gates: `python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` reported `32 passed in 3.43s`; `python -m ruff check src\\pdu_exam_observer\\m2_persistence.py tests\\backend\\test_m2_persistence.py` reported `All checks passed!`; `python -m mypy src\\pdu_exam_observer\\m2_persistence.py` reported `Success: no issues found in 1 source file`. Historical receipt before the later approved security review. P1 is `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`, not `P1_ACCEPTED`; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

### Security NO-GO remediation

`OBSERVED`: security review identified false seal after rename, recovery path tamper, manual recovery/session-state gaps, duplicate manifest validity, private metadata acceptance, silent directory-fsync handling, TOCTOU, and concurrency/idempotency weaknesses. Targeted RED reproduced those boundaries. The final local receipt is `$env:PYTHONPATH='src'; python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`40 passed in 6.13s`), scoped Ruff (`All checks passed!`), and mypy (`Success: no issues found in 1 source file`). P1 now guards/revalidates final bytes and identity through commit, re-derives recovery paths from IDs, automatically quarantines/fails non-withdrawn sessions, consults canonical registry validity, uses explicit version allowlists, reports directory durability state, and serializes same-root calls in-process. This is local remediation evidence only: independent security review remains pending, `P1_ACCEPTED` remains false, and `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

### Second security NO-GO remediation

`OBSERVED`: second re-review found that process-local serialization and non-exclusive handles did not satisfy the P1 trust boundary. The corrected seam acquires a lifetime Windows OS lease before migration validation/recovery through internal `CreateFileW` share mode `0`. A rejected contender reports typed `STORE_OWNER_UNAVAILABLE` and does not run recovery. Windows final-object handles are raw share-zero `CreateFileW` handles with `FILE_FLAG_OPEN_REPARSE_POINT`; internal root/staging/partial/artifact/quarantine directories are raw `FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT` handles held without delete share. Outside Windows, P1 artifact sealing fails closed with `PLATFORM_UNSUPPORTED`; no POSIX-equivalence claim is made. All handles are closed in `finally` paths.

### Third security NO-GO remediation

`OBSERVED`: third review found that constructor errors after lease acquisition could retain the lease, that pathname prechecks did not certify the opened object, and that POSIX protection was overstated. The constructor now encloses every post-lease operation in an ownership-transfer cleanup boundary; all Windows lease/directory/final handles use `GetFileInformationByHandle` after open to reject a reparse attribute; and non-Windows persistence rejects before any artifact file write with typed `PLATFORM_UNSUPPORTED`. Focused RED covered malicious database reparse then second constructor acquisition, acquisition-window directory swap, and forced non-Windows refusal. Final local receipt: `$env:PYTHONPATH='src'; python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`46 passed in 6.16s`), scoped Ruff (`All checks passed!`), and mypy (`Success: no issues found in 1 source file`). `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW` remains current; `P1_ACCEPTED=false` and `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remain unconditional.

### Fourth security NO-GO remediation

`OBSERVED`: P1 was incorrectly able to bootstrap missing M1 storage and could open child lease/database paths before `operational` had a lifetime raw-handle guard. P1 now requires an existing exact M1 root, `operational` directory, and v1 database; missing components raise the explicit v1 precondition without creating a root, directory, lease, or database. On Windows, post-open-validated raw no-follow/no-delete-share root and `operational` handles are held before the lease, database connection, migration, and recovery. RED covered missing components and an `operational` swap between observation and handle open with no outside lease/database creation. Final local receipt: `$env:PYTHONPATH='src'; .\\.venv\\Scripts\\python.exe -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`50 passed in 6.82s`), scoped Ruff (`All checks passed!`), and scoped mypy (`Success: no issues found in 1 source file`). This is local remediation evidence only: `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW` remains current, `P1_ACCEPTED=false`, and `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

### Fifth security NO-GO remediation

`OBSERVED`: the v1 database leaf and SQLite sidecars could still be swapped after parent-directory validation. On Windows, P1 now opens the exact derived v1 database with `OPEN_EXISTING|FILE_FLAG_OPEN_REPARSE_POINT`, regular-file and exact-final-path checks, and read/write sharing without delete sharing before lease, SQLite connect, migration, or recovery. Existing `-wal`/`-shm` leaves are rejected if unsafe; after WAL mode they must be guardable before migration/recovery. Sidecar guards remain through the main application connection close; a trusted anchor prevents last-connection cleanup while they are held, then closes after guard release. RED swapped the validated database to a separate valid v1 database and proved its ledger remained `[1]` with no v2 table or sidecars; a symlinked WAL sidecar also failed before migration. Focused P1 evidence ran all 51 cases in bounded groups (`7+6+13+6+8+11`, necessitated by the local 30-second terminal wrapper), all passed; the one M1 migration regression passed (`1 passed in 0.47s`); scoped Ruff reported `All checks passed!`; scoped mypy reported `Success: no issues found in 1 source file`. `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW` remains current, `P1_ACCEPTED=false`, and `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remain unconditional.

### Sixth security review remediation

`OBSERVED`: absent SQLite WAL/SHM names were previously created only after SQLite started, and guarded close repeatedly took about 1.47 seconds. P1 now reserves both exact derived sidecar leaves with raw `CREATE_NEW|FILE_FLAG_OPEN_REPARSE_POINT` before any SQLite connection, validates a raced-existing leaf as regular/non-reparse at its actual exact path, and holds the guards through migration/recovery. Normal close checkpoints under guard, sets the sole store connection `query_only`, then releases sidecar guards for SQLite cleanup while database/root/operational guards and the root lease remain. RED covered an absent-WAL symlink plant and two clean close/reopen cycles; corrected timing passed in `0.36s`. The requested monolithic command was attempted with a >120-second yield, but this terminal wrapper returned partial output at its fixed 30-second ceiling. Equivalent bounded focused P1 groups covered all 53 cases (`7+6+13+6+8+13`), all passed; the M1 migration regression passed (`1 passed in 0.63s`); scoped Ruff and mypy passed. This remains local builder evidence only: `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW` remains current, `P1_ACCEPTED=false`, and `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remain unconditional.

### Seventh remediation and final independent review receipt (2026-08-26)

`OBSERVED`: all prior P1 security `NO-GO` rounds are resolved remediation evidence, not erased. Normal and constructor-failure cleanup use one failure-safe sequence. Migration-fault cleanup returned in `0.012s`; immediate retry produced exact ledger `[1,2]`, released all handles, and allowed local-root deletion. The no-replacement hook blocked WAL/SHM replacement with `WinError 32`; the external target bytes were unchanged. Independent final evidence: focused monolithic P1 plus the one M1 migration regression reported `55 passed in 7.60s` (measured elapsed `8.371s`); Ruff reported `All checks passed!`; mypy reported `Success: no issues found in 1 source file`; Terra/max security reviewer `APPROVE` source. Residuals: the SQLite-error fallback at `m2_persistence.py:340` was source-reviewed fail closed but not independently fault-injected in the final pass; sealing is Windows-only; parent-directory durability is `PLATFORM_UNSUPPORTED`; no full suite, runtime/device, encryption/ACL, participant, or research-validity evidence exists.

RoutingReceipt schema v1: D1-N1 builder `Terra/high`; research/privacy reviewer `Sol/xhigh CONDITIONAL_GO_PREIMPLEMENTATION`; prior P1 security reviewer `Terra/max APPROVE`; decision owner `root`; `P1_ACCEPTED=true`; D1-N1 physical video access and pretrained technical inference authorized; participant/model-evaluation flags false. `M2_S1_ACCEPTED` and D1-C1 local verification are retained. Authority remains non-transitive and revision-scoped. Current status is `D1_N1_NATIVE_PREFLIGHT_AUTHORIZED_IMPLEMENTATION_ACTIVE`; no camera access occurs before final source review, and an N1 pass cannot become `D1_GO`. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.
