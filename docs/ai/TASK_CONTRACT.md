# Task Contract v13

## GOV-P5A current human-confirmation request boundary

`USER_STATED`: on `2026-08-31`, the user approved the advisor-first GOV-P5A
design and instructed implementation. This authorizes local request artifacts,
a deterministic builder, tests, and ledger reconciliation only.

Current status:
`GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED`.

`OBSERVED`: `HC-01` asks whether a dossier may be routed after the current-cycle
deadline; `HC-02` asks which ethics/human-subjects route applies to the
adult-volunteer webcam study. Audience is `FACULTY_ADVISOR_FIRST`.
`human_response_status=PENDING`, `external_transmission_authorized=false`, and
`submission_state=NOT_SUBMITTED`. Manifest SHA-256 is
`4c5443ae46972b5ec56d2229700580bd0a6e7c1be61ef79d019c055314962fa8`.

The response template remains unfilled. Blocking gates
`CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED` and
`HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED` remain open. Residual
`HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED` prevents the local pack from being
presented as a transmitted request or received response. GOV-P5B requires a
separate task and real minimized evidence.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

This contract authorizes no email, upload, external submission, response or
approval claim, consent issuance, participant contact, camera/M2/B0.3,
provisioning, real deletion, package rebuild, deployment, or release.

## GOV-P4 current institutional-route boundary

`USER_STATED`: on `2026-08-31`, the user instructed implementation of the next
task after GOV-P3. This authorizes official-source research, a repository-only
route pack, deterministic validation, tests, and ledger reconciliation. It does
not authorize contact, submission, approval, or collection.

Current status:
`GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_UNCONFIRMED_APPROVAL_NOT_ISSUED`.

`SOURCE_VERIFIED`: the public university regulation and current-cycle notice
establish Hội đồng khoa review, forms 1-6, faculty forwarding through the
research-management office, advice to the Rector, and a Rector-issued approval
decision before students begin. GOV-P4 therefore records
`adv_02_status=SATISFIED_BY_PUBLIC_PRIMARY_SOURCES` and
`institutional_route_status=SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED`.

Manifest SHA-256 is
`f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531`.
The checker validates recorded source metadata and hashes but does not refetch
the Internet. No external source file, personal identity, signature, or contact
record is added to the pack.

`human_subjects_review_requirement=UNKNOWN_PENDING_CONFIRMATION` because the
public student-research route does not settle a separate ethics review for
adult volunteers/webcam data. Late-cycle acceptance is also unconfirmed.
Residuals `HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED` and
`CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION` remain open.
`institutional_approval_status=NOT_ISSUED` and
`submission_state=NOT_SUBMITTED` remain binding.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

This contract authorizes no email, upload, institutional submission, consent
issuance, participant contact, camera/M2/B0.3, provisioning, real deletion,
package rebuild, deployment, or release.

## GOV-P3 current advisor-decision boundary

`USER_STATED`: on `2026-08-31`, the user reported a verbal approval from the
faculty advisor and instructed implementation of the next task. This authorizes
a repository-only versioned receipt, deterministic validation, tests, and
governance reconciliation.

Current status:
`GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_READY_FOR_INSTITUTIONAL_ROUTING`.

`OBSERVED`: GOV-P3 records only `ADV-01` as
`SATISFIED_BY_USER_REPORT_UNVERIFIED`, outcome
`READY_FOR_INSTITUTIONAL_ROUTING`, evidence mode
`VERBAL_CONFIRMATION_REPORTED_BY_USER`, and classification
`USER_STATED_UNVERIFIED`. Manifest SHA-256 is
`7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605`.

No identity, signature, written evidence, fabricated decision date, approval
ID, issuer, retention value, or storage root is recorded. `ADV-02` remains
`PENDING_EXTERNAL_DECISION`; `institutional_approval_status=NOT_ISSUED` and
`submission_state=NOT_SUBMITTED`. Residual
`ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY` remains explicit.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

This contract authorizes no external submission, participant contact,
institutional approval claim, official consent issuance, camera/M2/B0.3,
provisioning, real deletion, package rebuild, deployment, or release.

## GOV-P2 current advisor-first dossier boundary

`USER_STATED`: on `2026-08-31`, the user approved the GOV-P2 advisor-first
specification/plan and Correction A. Authorized work is local Markdown/JSON,
deterministic annex/manifest/receipt generation, tests, and governance
reconciliation only.

`OBSERVED`: status is
`GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW`, audience
is `FACULTY_ADVISOR_FIRST`, `submission_state=NOT_SUBMITTED`, and review is
`PENDING_EXTERNAL_REVIEW`. Manifest SHA-256 is
`1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e`.

Correction A preserves exact historical GOV-P1 bytes and records
`CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT`. It does not rebuild
GOV-P1 against current M1, suppress its live `MANIFEST_MISMATCH`, or convert
synthetic evidence into a production receipt.

```text
production_reconciler_implemented=false
production_reconciler_real_storage_verified=false
real_data_deletion_authorized=false
execution_authorized=false
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
participant_collection_authorized=false
research_ready=false
collection_authorized=false
authority_status=AUTHORITY_NOT_ISSUED
```

This contract authorizes no participant/institution contact, submission,
official DOCX/PDF, camera/M2/B0.3/provisioning/A0/A1, real deletion, package
rebuild, or external operation.

## Authority and evidence

The approved documents under `docs/spec` are the binding product and research constraints. The canonical proposal remains `docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx` and its recorded SHA-256 is authoritative.

Load-bearing claims use `OBSERVED`, `SOURCE_VERIFIED`, or `UNVERIFIED`. Local tests and packaged browser observations do not prove institutional approval, camera behavior, participant access, model performance, clean-machine portability, deployment, or production readiness.

## Current authorized action

`USER_STATED`: on `2026-08-30`, the user approved bounded TM-17 monotonic
hardening for the existing reviewer bearer and M1-R1 confirmation challenge.
The slice is source, tests, and documentation only. No schema migration,
normal reconciliation execution, real deletion, external attestation,
participant/camera work, packaging, deployment, publishing, or release is
authorized.

`USER_STATED`: on `2026-08-30`, the user requested the next task and thereby
authorized one local rebuild of the generated PyInstaller bundle plus packaged
runtime and desktop/390x844 visual acceptance against a fresh synthetic-only
research root. This authority does not include signing, ZIP distribution,
publishing, deployment, real deletion, external attestation, participant data,
camera use, or collection.

`USER_STATED`: on `2026-08-30`, the user approved the corrected M1-R1 full
specification, threat model, migration design, detailed implementation plan,
and requested implementation. The authorized slice is source code, tests,
documentation, and one no-path `rehearse-r1` flow that creates and disposes its
own `%TEMP%\pdu-m1r1-rehearsal-*` synthetic root. The rehearsal may receive a
non-persisted one-target-set authority bound only to that process/root/plan.
Normal migration apply, real-root reconciliation, local deletion, external
attestation, participant collection, camera/device work, M2/M3, deployment,
publishing, and release remain unauthorized and must fail closed as
`AUTHORITY_NOT_ISSUED`.

`OBSERVED`: before implementation, the canonical proposal SHA-256 remains
`2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`,
Git metadata is absent, and the focused M1/P1 baseline passes 94 tests. This is
only a pre-change local regression baseline.

`OBSERVED`: M1-R1 source implementation still reaches only
`M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY`. The TM-17 follow-up keeps
wall time for audit, adds process-monotonic reviewer/challenge deadlines, and
expires every pre-existing issued challenge when confirmation service starts.
It also rejects non-finite clock evidence, rechecks reviewer/time state after
planning immediately before issue/consume, and durably revokes issued
challenges on logout/replacement through one active service callback. Fresh
evidence is 137 focused backend tests, the final 843-test Python suite, 58
frontend tests, typecheck, lint, production build, Ruff over current source and
the changed packaging test, and strict mypy over 37 source files.
Current-revision independent review returned `NO-GO`, all concrete Important
findings were reproduced and remediated, and scoped re-review returned
`APPROVE_SOURCE_ONLY` with no unresolved Critical or Important finding. The exact threat map and
residual ledger are `docs/ai/M1_R1_VERIFICATION.md`.

`OBSERVED`: the rebuilt local package passed its 8-test packaging gate,
manifest verification, M0 smoke, M1 persistence smoke, and the packaged M1-R1
monitor flow. The reviewer created a step-up challenge, received a fail-closed
`403 AUTHORITY_NOT_ISSUED` from the normal execution route, logged out, and
left two revoked challenges, zero execution/run records, two pending targets,
and the synthetic artifact unchanged by size and SHA-256. The PIN was cleared
from the DOM and reviewer session storage was empty after logout. Desktop and
390x844 screenshots were inspected. The sanitized receipt is
`output/runtime/m1-r1-tm17-packaged-acceptance/PACKAGED_RUNTIME_ACCEPTANCE.md`.
Clean-machine portability, real storage, external-account truth, and all
participant/collection gates remain unverified. The implementation claim is
`production_reconciler_source_implemented=true`; production/runtime and real-
storage claims remain false.

`USER_STATED`: on `2026-08-30`, the user approved GOV-P1 direction A and its
full specification/plan. The authorized slice is a synthetic-only rehearsal in
a runner-owned temporary directory, deterministic receipt/pack generation, and
draft institutional-review documentation. It authorizes no production M1
schema/API mutation, production task completion, real deletion, participant,
camera, native, export, network, B0.3, A0/A1, M2, or M3 action.

`OBSERVED`: GOV-P1 passed its isolated M1 rehearsal. Receipt body SHA-256 is
`539405cdb0c5fd3745740cbd5c6727af9afdcc6008ee63622d997c34e0f50b97`
and pack manifest SHA-256 is
`76fe01de697f44ba82208bd40ce1f14eb9f4df993076c3984ff15906620aa9b4`.
Four synthetic files were deleted while the out-of-manifest sentinel remained;
the temporary root was then disposed. Four M1 withdrawal tasks remain
`PENDING`, so `PRODUCTION_RECONCILER_UNIMPLEMENTED` is an explicit blocking
gate. `research_ready=false`, `collection_authorized=false`, and
`AUTHORITY_NOT_ISSUED` remain binding.

`OBSERVED`: GOV-P1 reviewed-source files are pinned by exact hashes; copied
live source paths are rejected even when byte-identical; generated leaves use
same-directory atomic replacement; deletion rechecks identity immediately
before unlink; and both CLIs sanitize unexpected exceptions. This does not
prove resistance to a hostile concurrent process under the same Windows
account. The receipt keeps
`concurrent_same_account_mutation_resistant=false` and no production/native
delete authority is introduced.

`OBSERVED`: independent post-remediation security review is `APPROVE` for the
synthetic GOV-P1 slice only. Fresh evidence is 22/22 focused GOV-P1 tests,
78/78 focused GOV-P1/GOV-P0/M1/RP2 tests, scoped Ruff and strict mypy, both
GOV-P1 check CLIs, unchanged proposal/GOV-P0/RP2 hashes, and 770/770 full-suite
tests. This is local governance/rehearsal evidence, not institutional approval,
participant evidence, or production deletion evidence.

`HISTORICAL`: earlier on `2026-08-30`, the user authorized design documentation
only for the M1-R1 candidate. That boundary was superseded by the later
approved source-only implementation plan, but the prohibition on normal schema
migration, root activation, real file deletion, external operation, M2/M3, and
collection remains unchanged.
The draft design preserves terminal participant withdrawal even when target
binding is missing; missing targets block reconciliation completion rather
than reject or roll back withdrawal.

`USER_STATED`: on `2026-08-30`, the user approved and requested implementation
of GOV-P0 direction 1. This authorizes repository-only research-governance
documents, deterministic validation, and static receipts. It does not authorize
contacting or recording a participant, opening M2 or M3, changing B0.3,
provisioning a credential, installing a bootstrap, issuing A0/A1, or invoking
native, camera, FFmpeg, MediaPipe, model, seal, or export paths.

`OBSERVED`: the GOV-P0 pack is structurally verified with manifest SHA-256
`c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025`.
The receipt deliberately records `research_ready=false` and
`collection_authorized=false`; all institutional, consent, retention, storage,
ACL/encryption, M2, protocol-freeze, and B0.3 execution gates remain blocking.
B0.3 is deferred because no suitable custodian device exists, not waived.

`USER_STATED`: on `2026-08-29`, the user approved the B0.3 custodian direction,
written specification/plan, and preparation of a credential-free inert
PowerShell/NCrypt kit outside the checkout. No custodian exists. The only
currently authorized mutation is documentation/governance plus static and
safe-mode kit preparation. `-Mode Execute`, production key creation, a bundle,
signature, execution-authority artifact, B0.4 installation, signed A0,
preparation, A1, native/camera work, and retry remain unauthorized.

Current B0.3 work status:
`B0_3_INERT_KIT_STATIC_VERIFIED_CUSTODIAN_UNAVAILABLE_NO_EXECUTION_AUTHORITY`.
The controlling design and plan are
`docs/superpowers/specs/2026-08-29-d1-n2-b0-3-custodian-ceremony-design.md`
and
`docs/superpowers/plans/2026-08-29-d1-n2-b0-3-custodian-ceremony-plan.md`.
The kit must be create-new outside the repository, contain no credential, and
default to `ValidateOnly`. Its review ceiling is `APPROVE_INERT_KIT_ONLY`.

`OBSERVED`: the final external packet is script
`ce02742fb57ea2d01d41bd60e9c63f528254f64977952e7e297108d8f7d848dc`,
runbook `a294b6eeb8123a96f79de5b96bb5d23a4eaa257718555ff72166d16580f4077b`,
manifest `d59c1c402ba5be3da41c03accca708740cc1cb93cf6249683716354a5e852df2`,
and safe validation
`8b8f1dfdec40e85d503c9730963245ca75f14194d730d69344173e5694b31474`.
Independent Sol/xhigh review returned `APPROVE_INERT_KIT_ONLY` with no Critical
or Important finding and explicitly invoked no operational path. This does not
verify native behavior or issue B0.3 execution authority, a credential,
bootstrap, A0, preparation, A1, or device/research evidence.

Controlling boundary for `2026-08-29`: the user approved the B0-R2 exact epoch-
binding correction SPEC, PLAN, and source-only implementation. The replacement
non-authorizing RP2 exact triple is
`M2_R0_STATIC_AUTHORITY_REENTRY_RECONCILED`,
`static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979`,
`binding_schema_canonical_sha256=07ebbffaa9e0f9c2fa5b44dc9d2fab24ac82e324a118618acea7c830c5dd15cb`,
`binding_schema_exact_bytes_sha256=1592ea390925a7bccfe0360babdb343942a30e0e6878e794e2b5808b545f02ca`,
and
`candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`.
Independent Sol/xhigh review recomputed the exact packet, matched 27/27 live
artifacts and 21/21 policy preimages, and returned
`APPROVE_STATIC_PACK_ONLY`. Bootstrap provisioning, production signing
identity, signed A0, preparation, A1, and physical execution have not started.
The packet is unsigned and supplies no authority.
The live ceiling remains `authority_status=AUTHORITY_NOT_ISSUED`.

`HISTORICAL`: A0 for the superseded digest
`f582e6a284d5f3afcbe51d37a74ee9bcdb982537e2c7da7c81ba14bb0ef7c5c9`
authorized one parameter-free prepare call. It returned
`AUTHORITY_NOT_ISSUED` with zero reported native side effects and is closed and
non-reusable. It authorizes nothing under the new RP2. The existing D1-N1
terminal remains immutable and non-reusable.

Current state:
`B0_R2_STATIC_PACK_APPROVED_BOOTSTRAP_UNPROVISIONED_AUTHORITY_NOT_ISSUED`.
The user approved source-only B0 implementation: closed bootstrap/receipt
contracts, public-only BCrypt verification, fixed Windows readers, separately
gated installer source, production fail-closed composition, tests, RP2
regeneration, and independent static review. No production key, bootstrap,
receipt, signed A0, preparation, or physical action is authorized. The source
already contains the noncyclic signed-A0 boundary, challenge/Job
grant binding, semantic TERMINAL evidence, close-before-terminal ordering, and
idempotent pre-bridge abort. Independent B0-R2 review approved only the exact
static pack. Actual bootstrap provisioning and fresh signed A0 remain separate
gates. This source has not been physically invoked. A1 was not opened and X0
remains blocked.

`OBSERVED`: B0 contract, CNG, reader, and retained-lifecycle work is partially
implemented and passes 113 focused tests plus scoped Ruff and mypy. Independent
Sol/max architecture review found the approved final-receipt order cyclic:
`cleanup_clean=true` could be published before the receipt writer/verifier's
own cleanup outcome is known. Installer and production composition work are
therefore paused. The proposed B0-R1 boundary is a provisional receipt in the
fixed partial leaf, cleanup of every fallible resource, then one no-replace
write-through same-directory rename as the sole terminal publication action;
it also changes the identity digest to the receipt object and requires tagged
`OPENED`/`ABSENT`/`AMBIGUOUS` opens. At that checkpoint these material semantics
were not approved and no installer, operator CLI, production provisioning
artifact, RP2 refresh, or operational entrypoint invocation resulted from the
partial implementation. The following user decision superseded that pause.

`USER_STATED`: the user approved option A on `2026-08-29`. B0-R1 therefore
requires receipt-object identity, tagged inspection opens, closure of every
fallible resource before publication, and one final same-directory no-replace
write-through receipt rename with no authority-affecting work afterward. The
existing same-account whole-root replacement exclusion remains the accepted
threat-model boundary. This approval authorizes source implementation and tests
only; production key creation, installer execution, bootstrap/A0 provisioning,
preparation, A1, and physical work remain unauthorized.

`OBSERVED`: the approved B0-R1 source, tests, fixed operator CLI source, lazy
production composition, and deterministic RP2 regeneration are implemented.
Independent review rejected the first exact packet
`5305a2f8aff40a4f3f9babe3d7331bef5492e50104a0fb685d617a52c20a9c87`,
`da3b35674a922c830503ffece9e5e070c4ab02279fc51a4a9c24ee96a26fa558`,
and
`d8750b46c3f3a08c6887ba416656c598bdf744cdb4f2f896af9f2c61704ee98a`
for an unguarded post-ownership clock fault and an exact-once parent-close
violation. Those bytes are rejected. A second packet
`ddd5090b252af866bf3b626036a51018999d0884c2679b71f1b4cff47af6616c` /
`0c5340da49c63a0c6e043a8778f63844200f274cbd84095b5de4e536ba3bc04e`
was also rejected because receipt construction/canonicalization did not yet
guard every `BaseException` under ownership. All three findings are remediated
with focused ordinary-exception and `BaseException` regressions. The current
unsigned/non-authorizing exact triple is
`c439c12983fcd05675c5a13fba1db0199064a5df0632b94e7c7a61b42046bacc`,
`da3b35674a922c830503ffece9e5e070c4ab02279fc51a4a9c24ee96a26fa558`,
and
`13a995221dbbd327e5e9984967f8bcf2f74b8d3016ff523372dc8eb9735d0df7`.
Independent Sol/xhigh review returned `APPROVE_STATIC_PACK_ONLY` for exactly
this replacement packet after matching 26/26 artifacts and 20 policy preimages.
That verdict grants no operational or physical authority.
No production bundle, receipt, key, signature, A0, preparation, native call, or
camera action was created or run.

`USER_STATED`: the user approved the B0-R2 epoch-binding correction design,
SPEC, PLAN, and source-only implementation. `REFUTED`: B0-R1 did not enforce or
RP2-bind one exact epoch digest. B0-R2 now binds the immutable 626-byte policy
preimage under
`bootstrap_epoch_digest=736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b`
and rejects alternate well-formed values at bundle, installation-authority,
operator-parser, and receipt boundaries.

`OBSERVED`: the independently reviewed replacement packet is
`5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979` /
`07ebbffaa9e0f9c2fa5b44dc9d2fab24ac82e324a118618acea7c830c5dd15cb` /
`cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb`,
with 27 artifacts and 21 policy preimages. It is unsigned, non-authorizing,
and received Sol/xhigh `APPROVE_STATIC_PACK_ONLY` after exact recomputation and
four-layer alternate-digest rejection review. No B0.3 credential or operation
has started.

`HISTORICAL`: the prior RP2 decision was
`APPROVE_RP2_MACHINE_ARTIFACTS_FOR_DOC_SYNC` by Sol/xhigh. It applies only to
the superseded artifact bytes. The current RP2 later received independent I2
`NO-GO`; review itself issued no physical authority.

Historical decision: `M2_R0_ACCEPTED`, `M2_S1_ACCEPTED`, `P1_ACCEPTED`, and one
revision-scoped `M2_D1_N1_NATIVE_PREFLIGHT_GO`. That physical authority has been
consumed and terminalized. The attempt returned `NO_GO` with
`UNKNOWN_TECHNICAL_FAILURE`; `device_gate_decision=UNVERIFIED` and `d1_go=false`
remain binding. No retry or D1-N2 physical execution is authorized.

The current D1-N2 action is offline/no-device source remediation and verification
only. It may use fake or surrogate processes, bundled model liveness inside an
independently killable subprocess, and local unit/static gates. It may not read,
rewrite, reprepare, replace, or reopen the terminal authority; enumerate or open a
camera; launch the private worker entrypoint; or infer device acceptance from
source/tests. Any later physical attempt requires a new explicit revision-scoped
authority after independent review.

`HISTORICAL_CONSUMED_TERMINAL_NON_AUTHORIZING`: on `2026-08-26`, P1 was accepted and one D1-N1 native-adapter/60-second-preflight attempt was opened in a controlled no-human environment. The historical one-shot recorded physical-camera and pretrained-technical-inference permission for that attempt, with participant, model, recording, seal, and export permissions false. It was consumed and terminalized; it is not a live authorization vector, cannot authorize another physical action, and cannot authorize retry.

User accepted R0 on `2026-08-25`. S1 authorizes only pure backend/dependency-injected synthetic implementation in `src/pdu_exam_observer/m2_synthetic.py`, `tests/backend/test_m2_synthetic.py`, and optional `tests/fixtures/m2`. S1 forbids camera/device libraries and OS enumeration, HTTP/UI, SQLite/research-root writes, participant/session IDs, `REAL` provenance, `AlertEvent`, research labels/confidence, and M1 lifecycle/readiness changes. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

`OBSERVED`: the two S1 code files above have focused local verification. TDD evidence is initial missing-module RED, first GREEN (`17 passed`), verifier `NO-GO` for missing golden comparison plus 29 Ruff errors, targeted golden-mismatch RED, then corrected focused pytest (`18 passed in 0.07s`), Ruff (`All checks passed`), mypy (`Success: no issues found in 1 source file`), and Luna/medium independent verifier `APPROVE`. `M2_S1_ACCEPTED` is retained; the user separately accepted P1 and authorized D1 on `2026-08-26`.

Authorization remains non-transitive and revision-scoped. The first D1 slice is `D1_BACKEND_CONTRACT_EXERCISE`: injected test-chart/synthetic-video observations, exact threshold/accounting evaluation, privacy-stop precedence, exclusive injected ownership, and bounded receipts. It has no physical camera/device enumeration, audio, HTTP/UI/routes, SQLite/P1 sealing, model work, dataset export, or M1 lifecycle/readiness transition. Its only successful result is `BACKEND_CONTRACT_PASS` with `device_gate_decision=UNVERIFIED`; it cannot emit `D1_GO`. Participant collection, model training/evaluation, M3, and M4 participant consideration remain closed.

### D1-C1 acceptance boundary

The only D1-C1 implementation files are `src/pdu_exam_observer/m2_d1_contract.py` and `tests/backend/test_m2_d1_contract.py`, plus optional immutable repository-safe fixtures. Inputs are injected `TEST_CHART` or `SYNTHETIC_VIDEO` observations only. `NATIVE_NO_HUMAN_DEVICE`, native device identifiers, local paths, URLs, commands, browser fields, participant/session identifiers, `REAL` provenance, labels, confidence, alerts, arbitrary metadata, persistence, sealing, and export are rejected.

Required authority receipts state `P1_ACCEPTED=true`, D1 authorized, physical camera access false for this slice, participant/model/M1 recording/persistence-export authority false, and the exact proposal/readiness revisions. Run receipts retain separate warmup/post-warmup accounting; exact reconciliation; nearest-rank metrics; exact `1280x720@15fps`, 60-second/20-minute plan semantics; capacity/throughput gates; per-failure counts; `seal_attempted=false`; `export_attempted=false`; and `device_gate_decision=UNVERIFIED`. Any privacy uncertainty or privacy-guard failure is terminal `PRIVACY_STOP` before pose/encoder/durability handling.

`HISTORICAL D1-C1 EVIDENCE, NOT CURRENT STATE`: focused pytest, Ruff, mypy, and independent Sol/xhigh research/privacy review established `D1_BACKEND_CONTRACT_LOCALLY_VERIFIED_PENDING_NATIVE_EVIDENCE`. Actual camera enumeration/ownership/profile, 60-second and 20-minute physical runs, driver/audio behavior, physical timing/disk/privacy evidence, and `D1_GO` remained `UNVERIFIED`.

`HISTORICAL D1-C1 EVIDENCE, NOT CURRENT STATE`: on `2026-08-26`, D1-C1 was implemented only in `src/pdu_exam_observer/m2_d1_contract.py` and `tests/backend/test_m2_d1_contract.py`. The final focused pytest run emitted 45 passing markers; scoped Ruff reported `All checks passed!`; scoped mypy reported `Success: no issues found in 1 source file`; independent Sol/xhigh research/privacy review returned `APPROVE`. Root independently verified the bound `uv.lock` SHA-256 as `BAF657E935BD76C34E097C6D7F02EBED902758B965148E5585F1CC7CAD8B608C`. Its historical status was `D1_BACKEND_CONTRACT_LOCALLY_VERIFIED_PENDING_NATIVE_EVIDENCE`, never `D1_GO` or `D1_ACCEPTED`.

### D1-N1 native preflight boundary

`HISTORICAL_CONSUMED_TERMINAL_NON_AUTHORIZING`: the no-human environment was confirmed for the one D1-N1 attempt. Its contract allowed exactly one server-owned Windows video camera for one 60-second run only after exact dependency/model/FFmpeg hashes, offline state, face/pose privacy-engine liveness, and a process-global owner mutex pass. The adapter accepted no caller device, path, URL, command, model, duration, output, or browser value; it requested no audio and retained no raw frame. The attempt is consumed and terminalized, so none of this permits present or future access.

`HISTORICAL`: the selected transport was fixed-argv FFmpeg DirectShow video-only with synchronous MediaPipe Face Detector followed by Pose Landmarker in `VIDEO` mode. Face/pose results, privacy uncertainty/exception, invalid model output, partial frames, timestamp/accounting mismatch, a second owner, an unsupported profile, or a missing prerequisite were terminal. Capture-only operation could not pass. N1 recorded application-ingress timestamps, not sensor timestamps, and its output ceiling was `D1_N1_PREFLIGHT_PASS` with `device_gate_decision=UNVERIFIED` and `D1_GO=false`; the actual single attempt terminalized `NO_GO`.

Repository scope and execution gates are binding in `docs/ai/M2_D1_N1_IMPLEMENTATION_PLAN.md`. Terra/high implemented; Sol/xhigh approval was required and obtained before the single consumed D1-N1 attempt. That approval is terminal, non-reusable, and authorizes no further camera or native access. The 20-minute run, OS-level audio proof, comprehensive privacy sensitivity, encoder/disk/durability, participant, model evaluation, release, and production remain closed or `UNVERIFIED`.

M1 persistence and governance remain locally verified but do not authorize collection. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional and research sessions cannot enter `RECORDING`.

## M1 contract

- M0 remains the default in-memory runtime. M1 is selected explicitly with `PDU_RUNTIME_MODE=m1` after native configuration.
- Native config is stored at `%LOCALAPPDATA%\PDUExamObserver\config.v1.json`; the SQLite operational database is under the configured research root, never in the application bundle.
- Reviewer credentials are memory-only. The SQLite store contains no PIN, bearer, bearer digest, cookie, or authorization state.
- Metadata writes use schema version 1, SQLite WAL, foreign keys, a migration checksum ledger, `BEGIN IMMEDIATE`, and commit/rollback boundaries.
- Every mutating M1 HTTP route is reviewer-bearer-only, exact-origin/host checked, content constrained, and idempotency-keyed where retries are plausible.
- Readiness is typed and fail-closed. Research collection is always blocked by `RESEARCH_COLLECTION_NOT_IMPLEMENTED`; research sessions cannot transition to `RECORDING`.
- Withdrawal applies to every session for the participant, creates one canonical receipt, invalidates reachable artifact lineage, and blocks future write intents and export.

## Constraints

- Local-first, offline, Windows 11 x64, standard user, loopback-only.
- One camera owner, one active collection session, and no audio, face identification, keylogging, network monitoring, cloud sync, or automatic discipline.
- Raw video and high-rate artifacts remain outside the replaceable application directory.
- Observable alerts are review evidence only; they never assert intent, dishonesty, identity, or misconduct.
- Do not collect a real participant before consent, retention, approved storage controls, and institutional approval are recorded.

## R0 review artifact

`docs/spec/M2_READINESS_PACK.md` Version 0.4 records accepted R0/S1/P1 evidence and the authorized D1 boundary, including the injected-only D1-C1 contract, native-device evidence gap, receipt topology, failure-injection ledger, measurement accounting, and stop conditions. The pack does not alter M1 behavior or collection acceptance claims.

## S1 completion boundary

S1 focused verification is accepted by the user for this revision. It does not authorize a camera, device, participant, model, dataset export, or study; the separate P1 authorization remains non-transitive.

## P1 local implementation evidence

`OBSERVED` on `2026-08-25`: the authorized P1 files are `src/pdu_exam_observer/m2_persistence.py` and `tests/backend/test_m2_persistence.py`. The seam validates v1, adds only v2 tables/indexes and a second checksum-ledger entry in one `BEGIN IMMEDIATE` migration, validates exact v2 schema objects, and never edits v1 DDL or M1 runtime/lifecycle code. It accepts dependency-injected deterministic or AI-rendered bytes only, derives contained paths, atomically seals only after manifest/registry/dependency/event/audit commit, and uses canonical `artifact_dependencies` so M1 withdrawal invalidates P1 descendants.

Exact focused evidence: initial RED was `python -m pytest tests\\backend\\test_m2_persistence.py` with `ModuleNotFoundError: pdu_exam_observer.m2_persistence`; stage-fault RED was the missing `fault_hook` constructor argument. Final commands were `python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`32 passed in 3.43s`), `python -m ruff check src\\pdu_exam_observer\\m2_persistence.py tests\\backend\\test_m2_persistence.py` (`All checks passed!`), and `python -m mypy src\\pdu_exam_observer\\m2_persistence.py` (`Success: no issues found in 1 source file`).

This paragraph records the historical P1 preacceptance state. The user accepted P1 on `2026-08-26`. `UNVERIFIED`: physical device/camera behavior, real-person collection, encryption/ACL enforcement, model behavior, dataset export, browser/runtime acceptance, deployment, release, and production. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

## Security NO-GO remediation evidence

`OBSERVED`: the security review was `NO-GO` for post-rename substitution, mutable recovery paths, manual recovery/session-state gaps, non-canonical manifest validity, denylist metadata validation, silent parent-directory durability state, path TOCTOU, and cross-instance concurrency. The P1 seam now guards and revalidates the final object through commit; re-derives recovery paths only from opaque artifact IDs; auto-quarantines and fails non-withdrawn sessions with bounded event/audit evidence; reads manifest/replay validity from canonical `artifact_registry`; uses small explicit metadata allowlists; reports `CONFIRMED` or `PLATFORM_UNSUPPORTED` parent-sync state; and serializes same-root operations in process. This is corrected local evidence, not a security acceptance.

Exact current commands use explicit source resolution: `$env:PYTHONPATH='src'; python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`40 passed in 6.13s`); `$env:PYTHONPATH='src'; python -m ruff check src\\pdu_exam_observer\\m2_persistence.py tests\\backend\\test_m2_persistence.py` (`All checks passed!`); `$env:PYTHONPATH='src'; python -m mypy src\\pdu_exam_observer\\m2_persistence.py` (`Success: no issues found in 1 source file`).

## Second security NO-GO remediation evidence

`OBSERVED`: second review found that the final guard was not Windows-exclusive, directories were not handle-guarded, and ownership was only in-process. P1 now opens the Windows lifetime lease file with raw `CreateFileW` share mode `0` before migration/recovery; a contender receives typed `STORE_OWNER_UNAVAILABLE` and cannot recover or mutate. Windows final files use raw `CreateFileW` with share mode `0` plus `FILE_FLAG_OPEN_REPARSE_POINT`; root, staging, partial, artifact, and quarantine directories are held with `FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT`, no delete share, and handle-path containment checks. Outside Windows, P1 artifact sealing fails closed with `PLATFORM_UNSUPPORTED`; no POSIX-equivalence claim is made. All final, directory, and lease handles are closed through `finally` paths.

Exact local evidence: `$env:PYTHONPATH='src'; python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`43 passed in 7.15s`); scoped Ruff (`All checks passed!`); scoped mypy (`Success: no issues found in 1 source file`). Adversarial coverage includes raw Windows sharing denial after final verification, directory-symlink swap denial, real subprocess lease rejection with a live pending intent, and failure-path cleanup before local-root deletion. `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW` remains the only status; `P1_ACCEPTED=false`.

## Third security NO-GO remediation evidence

`OBSERVED`: third review found a constructor lease-cleanup gap, pre-open-only reparse checks, and an overbroad POSIX sealing claim. Immediately after acquiring the Windows lease, every remaining constructor step is now inside one ownership-transfer `try/except`: unsafe database-child/reparse validation, connection, migration, and automatic recovery all release the native lease exactly once on failure. Every Windows lease/directory/final `CreateFileW` handle is inspected with `GetFileInformationByHandle` after open and rejects reparse attributes before acceptance. Artifact persistence is Windows-only; non-Windows capability tests receive typed `PLATFORM_UNSUPPORTED` before any artifact write.

Exact evidence: `$env:PYTHONPATH='src'; python -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`46 passed in 6.16s`); scoped Ruff (`All checks passed!`); scoped mypy (`Success: no issues found in 1 source file`). RED covered malicious reparse database rejection followed by second constructor acquisition, acquisition-window directory swap, and forced non-Windows capability. Status remains `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`; `P1_ACCEPTED=false`.

## Fourth security NO-GO remediation evidence

`OBSERVED`: P1 is a v1-to-v2 migration only. It now rejects a missing root, `operational` directory, or v1 database before any bootstrap creation. Windows constructor ordering holds post-open-validated raw no-follow/no-delete-share root and `operational` handles for the full store lifetime before creating/opening `p1-store.lock`, SQLite, migration, or recovery; failure releases accepted parent handles and any lease exactly once. RED included an `operational` swap between precheck and handle open and proved that no lease/database was created outside the approved root, plus missing-component no-bootstrap probes. Exact evidence: `$env:PYTHONPATH='src'; .\\.venv\\Scripts\\python.exe -m pytest tests\\backend\\test_m2_persistence.py tests\\backend\\test_m1_backend.py::test_m1_migrations_reopen_and_fail_closed_on_newer_or_tampered_ledger` (`50 passed in 6.82s`); scoped Ruff (`All checks passed!`); scoped mypy (`Success: no issues found in 1 source file`). Status remains `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`; `P1_ACCEPTED=false`; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

## Fifth security NO-GO remediation evidence

`OBSERVED`: after validated parent handles, P1 now holds a raw Windows guard for the exact derived existing v1 database leaf before lease creation, SQLite connect, migration, or recovery. `OPEN_EXISTING|FILE_FLAG_OPEN_REPARSE_POINT`, actual regular-file/reparse checks, exact canonical final-path matching, and omitted delete sharing are required. Existing unsafe WAL/SHM sidecars reject before use; sidecars created by WAL setup must be guarded before migration/recovery. Guards remain through the main application connection close; a trusted anchor prevents incompatible last-close cleanup until the sidecar guards release. RED proved a database-leaf symlink swap cannot migrate an outside valid v1 database (`schema_migrations=[1]`, no v2 table/sidecars) and a WAL sidecar symlink fails before migration. Focused P1 ran in bounded groups because of the local 30-second wrapper (`7+6+13+6+8+11 = 51 passed`); the M1 migration regression passed (`1 passed in 0.47s`); scoped Ruff and mypy passed. Status remains `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`; `P1_ACCEPTED=false`; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

## Sixth security review remediation evidence

`OBSERVED`: absent SQLite sidecars were previously created after SQLite began using their names, leaving a race, and guarded close repeatedly waited about 1.47 seconds. P1 now reserves exact derived WAL and SHM names with raw `CREATE_NEW|FILE_FLAG_OPEN_REPARSE_POINT` before any SQLite connection, validates any raced-existing object with a regular/non-reparse exact-path handle, and holds the guards through migration/recovery. Normal close checkpoints under guard, switches the only store connection to `query_only`, then releases sidecar guards before SQLite’s cleanup close while database/root/operational guards and the lifetime lease remain. RED covered an absent-WAL symlink plant and two close/reopen cycles; corrected timing probe passed in `0.36s`. The requested monolithic command was attempted with `yield_time_ms=120000`, but the local wrapper returned partial output at its fixed 30-second ceiling. Equivalent bounded P1 groups covered all 53 cases (`7+6+13+6+8+13`), all passed; the M1 migration regression passed (`1 passed in 0.63s`); scoped Ruff and mypy passed. Status remains `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`; `P1_ACCEPTED=false`; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

## Seventh security review remediation evidence

`OBSERVED`: normal close and constructor-failure cleanup diverged, leaving a repeatable fault-path stall. Both now use one failure-safe routine: rollback an open transaction, checkpoint/truncate, establish `query_only`, release sidecar guards only after that no-write state, close SQLite, then release database/directory/lease guards through nested `finally` cleanup. If a SQLite cleanup prerequisite fails, sidecar guards remain through close and `_cleanup_limitation=SQLITE_CLEANUP_GUARDED_CLOSE` records the retained-guard path. RED measured migration-fault cleanup at `2.915371s`; corrected fault/retry, absent-sidecar, and normal-close probes passed (`3 passed in 0.36s`). M1 migration regression passed (`1 passed in 0.55s`); scoped Ruff and mypy passed. The fixed terminal wrapper prevents the requested monolithic P1 result; status remains `P1_LOCALLY_VERIFIED_PENDING_USER_GATE_REVIEW`, `P1_ACCEPTED=false`, and `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.

## Acceptance claims allowed now

M1 may claim only the current local evidence ledger: 73 Python tests; Ruff; mypy for 14 files; frontend 9 files/57 tests plus typecheck, lint, and build; M0/M1 smoke; 182 manifest entries with 0 forbidden; 5/5 dist/package match; exact executable and manifest hashes; packaged Chromium browser/runtime `PASS`; Sol visual advisory `ACCEPT`; and zero remaining processes/listeners after cleanup.

These are local verification claims, not release, deployment, production, institutional approval, participant, camera, model, or research-success claims. S1 verification is focused-only: no full suite, M1 smoke/regression, browser, device, persistence, packaging, runtime, research collection, performance, or research-validity evidence was run. User visual acceptance remains `PENDING`.

## Seventh remediation and final independent review receipt (2026-08-26)

`OBSERVED`: all prior P1 security `NO-GO` rounds are resolved remediation evidence, not erased. Unified normal/constructor-failure cleanup returned from migration fault in `0.012s`; immediate retry produced ledger `[1,2]` and allowed deletion/cleanup. The no-replacement hook blocked WAL/SHM replacement with `WinError 32`; external bytes were unchanged. Independent final evidence: focused monolithic P1 plus one M1 migration regression `55 passed in 7.60s` (elapsed `8.371s`); Ruff `All checks passed!`; mypy `Success: no issues found in 1 source file`; Terra/max security reviewer `APPROVE` source. Residuals: `m2_persistence.py:340` SQLite-error fallback was source-reviewed fail closed but not independently fault-injected in the final pass; Windows-only sealing; parent-directory durability `PLATFORM_UNSUPPORTED`; no full suite/runtime/device/encryption/ACL/participant/research-validity evidence.

`HISTORICAL D1-C1 EVIDENCE, NOT CURRENT STATE`: this routing receipt predates the current H3 D1-N2 state. It recorded D1-C1 builder `Terra/high`, research/privacy reviewer `Sol/xhigh APPROVE`, root decision owner, `P1_ACCEPTED=true`, historical D1 no-human validation authorization, participant/model flags false, and `D1_BACKEND_CONTRACT_LOCALLY_VERIFIED_PENDING_NATIVE_EVIDENCE`. `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains unconditional.
