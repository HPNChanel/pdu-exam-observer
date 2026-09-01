# M2-S2D Synthetic Evidence Export & Offline Verification Design

Status: `USER_APPROVED_FOR_IMPLEMENTATION`

## Outcome

M2-S2D exports the complete minimized artifact of an already-terminal synthetic
M2-S2A/S2B run as canonical JSON and verifies it offline. Export is available
only for `job_status=TERMINAL` and `integration_status=PERSISTED`, including a
valid technical `NO_GO`. It never reruns a core, opens a device, or creates a
server-side archive.

Maximum status:

```text
M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY
```

## Authority and scope

Every bundle, API response, verifier receipt, UI disclosure, and current ledger
retains:

```text
evidence_kind=SIMULATED
package_contains_integration=false
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

HTTP accepts only an opaque `request_id`; it cannot accept a path, URL,
artifact ID, filename, fixture, duration, device, or authority override. The
bundle cannot contain session/participant identity, local paths, raw frames,
images, landmarks, audio, usernames, or native-device identifiers. M2-S2D
does not change M2 DDL/schema, package contents, physical authority, research
readiness, or collection authority.

## Evidence bundle

`src/pdu_exam_observer/m2_synthetic_evidence.py` provides:

```python
MAX_EVIDENCE_BYTES = 4_000_000

def build_synthetic_evidence_bundle(
    run_record: Mapping[str, object],
    artifact_bytes: bytes,
) -> SyntheticEvidenceExport: ...

def verify_synthetic_evidence_bytes(
    payload: bytes,
) -> SyntheticEvidenceVerificationReceipt: ...
```

The closed envelope is canonical UTF-8 JSON with sorted keys, compact
separators, ASCII escaping, and one LF:

```json
{
  "artifact_kind": "M2_SYNTHETIC_EVIDENCE_BUNDLE",
  "body": {
    "authority_ceiling": {},
    "export_authority_effect": "NONE",
    "export_mode": "DOWNLOAD_ONLY_NO_SERVER_ARCHIVE",
    "source_artifact": {},
    "source_artifact_byte_size": 0,
    "source_artifact_sha256": "",
    "source_run": {}
  },
  "body_sha256": "",
  "schema_version": 1,
  "status": "M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
}
```

`body_sha256` hashes canonical body bytes without a trailing LF. Whole-bundle
SHA-256 is returned out-of-band in the HTTP header and verifier receipt. The
source artifact contains its canonical D1 receipt, 977 or 18,077 observation
result digests, aggregate observation digest, environment binding digest, and
synthetic authority ceiling. RP2 is deliberately not embedded, avoiding a
circular source/RP2 dependency.

The strict reader rejects duplicate keys, NaN, noncanonical bytes, unknown or
missing fields, payloads over 4,000,000 bytes, non-lowercase digests, and
forbidden content. It reconstructs `SyntheticIntegrationReceipt` and
`D1Receipt`, recomputes both receipt digests, calls
`verify_receipt_semantics()`, binds run kind/outcome/failure across all layers,
recomputes artifact SHA/size, checks the observation count and aggregate, and
requires the complete fail-closed authority ceiling.

Bounded failure codes are:

```text
INPUT_INVALID
INPUT_TOO_LARGE
INVALID_JSON
DUPLICATE_JSON_KEY
NONCANONICAL_JSON
ENVELOPE_INVALID
BODY_HASH_MISMATCH
RUN_RECORD_INVALID
RECEIPT_INVALID
ARTIFACT_INVALID
ARTIFACT_HASH_MISMATCH
D1_RECEIPT_INVALID
OBSERVATION_DIGEST_MISMATCH
AUTHORITY_CEILING_VIOLATION
FORBIDDEN_CONTENT
UNEXPECTED_FAILURE
```

## Verified artifact read and service

`M2PersistenceStore.read_verified_artifact(artifact_id, *, maximum_bytes)`
derives the final path from the opaque ID, requires the manifest path to match,
requires `VALID`, enforces the size cap, opens the existing same-handle guard,
reads from that descriptor, and rechecks identity/size/hash. It is read-only and
creates no audit event.

`SyntheticReviewService.export_evidence(request_id)` holds service lifecycle
ownership through the bounded read and returns deterministic
`SyntheticEvidenceExport`. Repeated export is byte-identical. It adds bounded
`EVIDENCE_NOT_EXPORTABLE` and `EVIDENCE_INTEGRITY_FAILED` service failures.

## API, CLI, and UI

The authenticated monitor-only endpoint is:

```http
GET /api/v1/synthetic-runs/{request_id}/evidence
```

It returns raw canonical bytes with `Content-Type: application/json`,
`Content-Disposition: attachment; filename="m2-s2d-<request_id>.json"`,
`Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and
`X-PDU-Evidence-SHA256`. Exact errors are `REQUEST_INVALID` (422),
`SYNTHETIC_RUN_NOT_FOUND` (404), `SYNTHETIC_EVIDENCE_NOT_EXPORTABLE` (409),
`SYNTHETIC_EVIDENCE_INTEGRITY_FAILED` (500), bounded service unavailable (503),
and sanitized `UNEXPECTED_FAILURE` (500). The exam origin has no route.

`scripts/verify_m2_s2d_synthetic_evidence.py <bundle.json>` accepts exactly one
regular, non-link local file no larger than 4 MB. It emits one canonical JSON
line, empty stderr, exit 0 for `EVIDENCE_VERIFIED`, and exit 2 with a bounded
failure code for `EVIDENCE_REJECTED`. It never prints a path or traceback.

The TypeScript `SyntheticReviewApi` gains
`downloadSyntheticEvidence(requestId)`. The client shares the current reviewer
auth/error boundary, requires safe headers and size, recomputes whole-body SHA
with Web Crypto, and validates the closed envelope before deriving the local
filename. The panel shows `Tải bằng chứng synthetic JSON` only for terminal
persisted records, performs one GET without retry, revokes the object URL, and
shows the full SHA-256 with permanent non-authorizing copy. There is no upload
or import UI.

## Threat and migration boundary

- Same-handle read and nested digest verification reject storage or bundle
  tamper; they prove bytes at export time, not physical behavior.
- Response-only download prevents a new server archive; the downloaded file is
  managed by the operator outside the server.
- The 4 MB cap bounds memory use. A larger future format requires a new version.
- Canonical schemas and recursive forbidden-content checks prevent silent data
  widening.
- No database migration, package rebuild, deployment, camera use, participant
  contact, export of real data, or authority issuance is part of M2-S2D.

