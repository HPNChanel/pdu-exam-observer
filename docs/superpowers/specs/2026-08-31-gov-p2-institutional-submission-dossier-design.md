# GOV-P2 Advisor-First Institutional Submission Dossier Design

Date: `2026-08-31`

Status: `USER_APPROVED_FOR_IMPLEMENTATION`

## Outcome

GOV-P2 materializes a Vietnamese, advisor-first source dossier that binds the
existing GOV-P0 and GOV-P1 evidence without rewriting either historical pack.
The maximum claim is:

```text
GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW
```

The first audience is `FACULTY_ADVISOR_FIRST`. A structural pass is not a
submission receipt, advisor decision, institutional approval, invitation to a
participant, or collection authority.

## Authority ceiling

The dossier and every receipt retain:

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

No GOV-P2 path may run camera, participant, M2, B0.3, provisioning, A0/A1,
real deletion, network submission, email, upload, package rebuild, or create a
production key. No approval identifier, retention value, storage root, contact,
issuer, or decision date is invented.

## Historical/current correction

GOV-P1 is immutable historical evidence. Its manifest SHA-256 remains
`76fe01de697f44ba82208bd40ce1f14eb9f4df993076c3984ff15906620aa9b4` and
records the M1 source observed by the rehearsal. Current M1-R1 source has since
changed legitimately, so the live GOV-P1 builder reports `MANIFEST_MISMATCH`.
GOV-P2 must not rebuild GOV-P1 or weaken that checker. It pins the historical
manifest and reviewed annex sources by exact path and hash, and reports
`CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT` as a residual.

## Pack architecture

`research/institutional_submission/v1/` contains five reviewed sources, four
byte-identical generated annexes, a manifest, and a validation receipt. The
reviewed sources are the advisor cover, decision-request matrix, risk and
safeguard statement, retention/storage/withdrawal decision form, and source
index. Annexes snapshot the existing GOV-P1 dossier, GOV-P0 consent draft,
GOV-P0 participant-information draft, and GOV-P1 external-decision template.

The file set is flat and closed. JSON uses canonical UTF-8, sorted keys, no
NaN, exact fields, a single trailing LF, and body SHA-256 for source envelopes.
Generated annexes must be byte-identical to canonical upstream files.

## Decision contract

The matrix contains exact decisions `ADV-01`, `ADV-02`, and `EXT-01` through
`EXT-05`. All have `current_status=PENDING_EXTERNAL_DECISION` and
`current_value=null`. Review route is `FACULTY_ADVISOR_FIRST`, submission state
is `NOT_SUBMITTED`, authority effect is `NONE`, and readiness/collection remain
false. A real decision requires a separately authorized later version.

Human-readable sources state that identity, signatures, and submission-copy
metadata remain outside the repository. They distinguish observable posture
events from intent or misconduct, preserve human review, local-only raw video,
the pseudonymous export allowlist, pilot/confirmatory separation, withdrawal
blocking, and the synthetic-only limit of GOV-P1.

## Builder interface

`scripts/build_gov_p2_submission_dossier.py` exports:

```python
def write_pack(pack_root: Path = DEFAULT_PACK_ROOT) -> dict[str, object]: ...
def check_pack(pack_root: Path = DEFAULT_PACK_ROOT) -> dict[str, object]: ...
```

The CLI defaults to read-only `--check`. Explicit `--write` may replace only
the four fixed annexes, manifest, and validation receipt through fixed-name
temporary leaves plus atomic replace. Upstream paths are not CLI-configurable.
Success exits 0; rejection exits 2. Stdout is one canonical JSON line and
stderr is empty. Unexpected errors collapse to `UNEXPECTED_FAILURE` without
path or traceback disclosure.

## Acceptance

Acceptance requires ten focused tests, research and full-suite passes, Ruff,
strict mypy, canonical proposal and prior-pack hashes, GOV-P0 and RP2 checks,
exact historical GOV-P1 verification, unchanged release manifest/package, and
no PDU process/listener. The successful receipt still leaves advisor review,
institutional route, approval, retention, storage controls, participant work,
M2 physical evidence, and collection blocked.
