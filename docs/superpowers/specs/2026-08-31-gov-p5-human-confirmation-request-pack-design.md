# GOV-P5A Human Confirmation Request Pack Design

Date: `2026-08-31`

Status: `USER_APPROVED_FOR_IMPLEMENTATION`

## Outcome

GOV-P5A creates a deterministic, advisor-first request pack for two unresolved
human decisions: late-cycle submission acceptance after `2026-08-29`, and the
applicable ethics/human-subjects route for an adult-volunteer webcam study.
Its maximum claim is:

```text
GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED
```

A validated request pack is not a response, submission, ethics clearance,
institutional approval, or collection authority. A real response requires the
separate GOV-P5B task and a new versioned artifact.

## Pack contract

`research/institutional_submission/human_confirmation_request/v1/` is a flat,
closed pack with five reviewed sources plus a generated manifest and validation
receipt. The first audience is `FACULTY_ADVISOR_FIRST`; the advisor may route a
question to an authorized unit but cannot be inferred to hold institutional
approval authority.

`HC-01` asks whether the current-cycle dossier may be routed after the deadline.
`HC-02` asks whether a separate ethics/human-subjects review is required and,
if so, which review body and template apply. A response that says the general
student-research route is sufficient must include an authority or policy
reference. Silence, absence of a public rule, and verbal user reports do not
resolve either question.

The response template is deliberately unfilled. It contains no identity,
contact, signature, approval ID, decision date, storage root, retention value,
or asserted answer. Completed response evidence remains outside GOV-P5A.

## Evidence hierarchy

An official written document or official email may be evaluated by GOV-P5B if
the respondent role and authority are established. Written advisor guidance
may route a request but is not institutional approval. A verbal report remains
`USER_STATED_UNVERIFIED` and cannot close either blocker.

Raw external messages, names, email addresses, phone numbers, and signatures
are not stored in this repository. A later receipt may retain only minimized
role, date, evidence classification, authority reference, and a cryptographic
evidence reference under a separately approved contract.

## Builder and failure behavior

`scripts/build_gov_p5_confirmation_request_pack.py` exposes `write_pack()` and
`check_pack()`. The CLI defaults to read-only checking. `--write` may replace
only the fixed manifest and validation leaves using fixed-name temporary files
and atomic replace. JSON is canonical UTF-8 with sorted keys, duplicate-key
rejection, exact envelopes, body SHA-256, and one trailing LF.

The builder pins exact canonical proposal and GOV-P2/P3/P4 paths and hashes,
rejects shadow paths, extra files, links, reparse leaves, filled response data,
forged decisions, and every authority mutation. Success writes one canonical
JSON line to stdout and exits 0. Rejection writes one bounded JSON line, keeps
stderr empty, and exits 2.

## Authority ceiling

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

GOV-P5A performs no email, upload, external submission, camera, participant,
M2, B0.3, provisioning, signing, real deletion, package rebuild, deployment,
or release action.

