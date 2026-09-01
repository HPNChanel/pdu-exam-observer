# M2-S2C Synthetic Reviewer API/UI Wiring — Design Specification

Status: `USER_APPROVED_FOR_IMPLEMENTATION_IMPLEMENTED_LOCALLY_VERIFIED`

Date: `2026-08-31`

Maximum post-implementation status:

```text
M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY
```

## 1. Outcome

M2-S2C turns the already verified M2-S2A preflight and M2-S2B nominal cores
into a reviewer-visible source-runtime workflow:

```text
Authenticated monitor UI
  -> closed synthetic-run HTTP contract
  -> single-flight SyntheticReviewService
  -> fixed S2A or S2B core
  -> M2PersistenceStore in a service-owned temporary workspace
  -> minimized receipt returned to the monitor UI
```

The feature lets a reviewer exercise and inspect synthetic integration from the
application instead of invoking Python APIs or command-line scripts. It does
not add a camera flow, physical M2 evidence, `D1_GO`, model-performance
evidence, participant collection, research readiness, or release-package
inclusion.

## 2. Current evidence and design basis

`OBSERVED` on the current checkout:

- M2-S2A provides a fixed 977-frame `PREFLIGHT_60S` core.
- M2-S2B provides a fixed 18,077-frame `NOMINAL_20M` core.
- Both cores return `SyntheticIntegrationReceipt`, persist valid
  `BACKEND_CONTRACT_PASS` and `NO_GO` receipts, and fail closed when evidence or
  persistence is invalid.
- The monitor origin already requires a tab-scoped reviewer bearer.
- The React monitor already separates technical observations from claims about
  intent and already uses a fetch-based authenticated API client.
- Python collection is 904 tests and the current web suite is 58 tests.
- The historical release package does not contain M2-S2A or M2-S2B.

`DERIVED`: the smallest useful next vertical slice is a source-only synthetic
review service behind the existing monitor authentication boundary. Reopening
physical authority would add device and institutional dependencies without
improving the application workflow that can be verified now.

## 3. Explicit boundaries

### 3.1 Authority ceiling

Every API envelope, UI disclosure, current ledger, verification receipt, and
terminal core receipt must preserve:

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

### 3.2 Prohibited behavior

M2-S2C must not:

- enumerate or open a camera, microphone, audio device, display, or native
  capture handle;
- accept a filesystem path, URL, fixture bytes, device token, duration,
  profile, run ID, artifact ID, failure injection, golden digest, participant
  identifier, session identifier, or authority override from HTTP or browser
  input;
- create or mutate a real participant, consent receipt, research study,
  operational research session, exam session, or `RECORDING` state;
- run automatically on page load, retry a failed run automatically, queue an
  unbounded number of jobs, or allow concurrent synthetic jobs;
- expose a local path, username, native-device identifier, fixture/frame data,
  raw landmark, stack trace, exception text, bearer, idempotency key, or
  service-owned synthetic session identifier;
- write to the existing M1/M1-R1 operational storage root;
- change the M2 database schema, D1 schema, public S2A/S2B core interfaces, or
  release package;
- claim physical fault reproduction, model quality, ethics approval, research
  readiness, deployment, or release.

## 4. Chosen architecture

### 4.1 Considered approaches

1. **Chosen — process-lifetime synthetic workspace.** A dedicated service owns
   a temporary M1/M2 workspace, one DRAFT synthetic metadata session, a
   single-worker executor, and bounded in-memory job records. It closes the M2
   store and removes the workspace on application shutdown. This preserves
   real M2 persistence semantics without touching the application's real
   operational root.
2. **Rejected — persist S2C artifacts into the live M1/M1-R1 root.** This would
   couple a synthetic UI experiment to production-oriented storage ownership,
   withdrawal lineage, and live session state. The current CLI deliberately
   closes M1 before opening M2, so live-root integration is not a safe minimal
   step.
3. **Rejected — execute the existing CLI as a subprocess.** This would duplicate
   lifecycle and error parsing, weaken typed receipt binding, and introduce a
   shell/process boundary that the in-process cores do not need.

### 4.2 Runtime activation

The source launcher adds one fixed allowlisted mode:

```text
PDU_RUNTIME_MODE=m2synthetic
```

Existing modes `m0`, `m1`, and `m1r1` remain unchanged. In `m2synthetic` mode:

- the normal loopback exam and monitor origins remain separate;
- the application backend remains non-collecting M0 state;
- the monitor receives an injected `SyntheticReviewService`;
- only the monitor origin registers synthetic-run routes;
- the service owns an internal temporary workspace and removes it at shutdown;
- the historical packaged executable remains unchanged and is not described as
  containing this mode.

No browser or HTTP field may select the runtime mode.

## 5. Service contract

Create:

```text
src/pdu_exam_observer/m2_synthetic_review.py
```

### 5.1 Public types

```python
class SyntheticReviewRunKind(StrEnum):
    PREFLIGHT_60S = "PREFLIGHT_60S"
    NOMINAL_20M = "NOMINAL_20M"


class SyntheticReviewJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    TERMINAL = "TERMINAL"


class SyntheticReviewServiceFailureCode(StrEnum):
    SERVICE_CLOSED = "SERVICE_CLOSED"
    RUN_ALREADY_ACTIVE = "RUN_ALREADY_ACTIVE"
    CAPACITY_EXHAUSTED = "CAPACITY_EXHAUSTED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


@dataclass(frozen=True, slots=True)
class SyntheticReviewRunRecord:
    schema_version: int
    request_id: str
    run_sequence: int
    run_kind: SyntheticReviewRunKind
    job_status: SyntheticReviewJobStatus
    service_failure_code: SyntheticReviewServiceFailureCode | None
    receipt: SyntheticIntegrationReceipt | None

    def as_dict(self) -> dict[str, object]: ...


class SyntheticReviewService:
    MAX_RECORDS = 32

    @classmethod
    def create_owned(cls) -> Self: ...

    def submit(
        self,
        run_kind: SyntheticReviewRunKind,
        *,
        idempotency_key: str,
    ) -> SyntheticReviewRunRecord: ...

    def get(self, request_id: str) -> SyntheticReviewRunRecord: ...
    def list(self) -> tuple[SyntheticReviewRunRecord, ...]: ...
    def close(self) -> None: ...
```

`create_owned()` is the only production constructor. It accepts no root, path,
executor, fixture, device, or digest input. Tests may use internal underscored
factories for injected cores, executors, and faults; those seams must not be
exported through HTTP or CLI.

### 5.2 Owned workspace lifecycle

`create_owned()` must:

1. Create one `TemporaryDirectory(prefix="pdu-m2-s2c-")`.
2. Initialize a synthetic M1 workspace with encryption and ACL both
   `UNVERIFIED`.
3. Create one internal synthetic study/participant/session metadata chain only
   to satisfy the existing immutable M2 foreign-key schema.
4. Leave that synthetic session in `DRAFT`; do not write consent and never enter
   `PREFLIGHT_READY` or `RECORDING`.
5. Close the M1 store before opening `M2PersistenceStore` on the temporary root.
6. Keep the M2 store open for the service lifetime so artifacts remain
   inspectable during that process.
7. On `close()`, reject new submissions, wait for the accelerated worker,
   close the store, shut down the executor, remove the temporary root, and make
   repeated close calls harmless.

The synthetic study, participant, and session IDs remain private and never
appear in a service record or API response. They are not representations of a
real person.

### 5.3 Submission, idempotency, and concurrency

- `Idempotency-Key` must match `[A-Za-z0-9._-]{16,128}`.
- `request_id` is `synrun-` plus the first 32 lowercase hexadecimal characters
  of SHA-256 over the idempotency key. The raw key is never stored in a response.
- The same key and same `run_kind` returns the same record and never starts a
  second run.
- The same key with another `run_kind` raises `IDEMPOTENCY_CONFLICT`.
- At most one record may be `QUEUED` or `RUNNING`. A different submission while
  active raises `RUN_ALREADY_ACTIVE`; there is no queue.
- The service keeps at most 32 records for its process lifetime and does not
  evict idempotency history. The 33rd distinct key raises
  `CAPACITY_EXHAUSTED`.
- Records are returned newest-first by `run_sequence`.
- No wall-clock timestamp is needed in the public record. Ordering uses the
  service-local monotonic integer sequence.

### 5.4 Job execution

A `ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdu-m2-synthetic")`
runs the fixed core. The job transitions:

```text
QUEUED -> RUNNING -> TERMINAL
```

For `PREFLIGHT_60S`, the service builds the canonical preflight bundle and
calls `M2SyntheticPreflightCore`. For `NOMINAL_20M`, it builds the canonical
nominal bundle and calls `M2SyntheticNominalCore`. The service, not the caller,
derives run, intent, artifact, source-binding, pose-engine, release-manifest,
and encoder-policy digests.

A terminal record contains exactly one of:

- a canonical `SyntheticIntegrationReceipt`, including valid persisted
  `BACKEND_CONTRACT_PASS`, valid persisted `NO_GO`, or fail-closed
  `NOT_PERSISTED`; or
- a bounded `service_failure_code` when the service failed before a core receipt
  could be formed.

`PERSISTED` and `BACKEND_CONTRACT_PASS` remain separate facts. A valid `NO_GO`
is terminal and auditable; it is not a service failure. Authentication loss or
UI unmount does not cancel a running core and does not start a retry.

## 6. HTTP contract and trust boundary

Create:

```text
src/pdu_exam_observer/api/synthetic_review.py
```

Register routes only in `create_monitor_app()` and only when
`AppConfig.synthetic_review_service` is not `None`:

```text
POST /api/v1/synthetic-runs
GET  /api/v1/synthetic-runs
GET  /api/v1/synthetic-runs/{request_id}
```

All three routes require the existing reviewer bearer dependency. They are not
registered on the exam origin. Existing no-store, Host, Origin, CSP, bearer,
and credential-omission controls remain unchanged.

### 6.1 Create request

```json
{
  "run_kind": "PREFLIGHT_60S"
}
```

`run_kind` permits exactly `PREFLIGHT_60S` or `NOMINAL_20M`. The body is a
closed Pydantic model with `extra="forbid"`. `Idempotency-Key` is mandatory.
There are no query parameters.

Success returns HTTP 202 and a record envelope. The endpoint is asynchronous;
the returned job may be `QUEUED`, `RUNNING`, or already `TERMINAL`.

### 6.2 Read envelopes

List response:

```json
{
  "schema_version": 1,
  "capability_status": "SYNTHETIC_REVIEW_ONLY",
  "evidence_kind": "SIMULATED",
  "package_contains_integration": false,
  "production_reconciler_implemented": false,
  "production_reconciler_real_storage_verified": false,
  "real_data_deletion_authorized": false,
  "execution_authorized": false,
  "physical_camera_access_authorized": false,
  "device_gate_decision": "UNVERIFIED",
  "d1_go": false,
  "participant_collection_authorized": false,
  "research_ready": false,
  "collection_authorized": false,
  "authority_status": "AUTHORITY_NOT_ISSUED",
  "runs": []
}
```

Item and create responses use the same authority envelope plus one `run`.
`run.receipt`, when present, is the exact minimized receipt dictionary already
defined by M2-S2A/S2B. Unknown or extra response keys are not allowed by the
frontend mapper.

### 6.3 HTTP failure mapping

| Condition | HTTP | Code |
|---|---:|---|
| Missing/malformed key or closed request body | 422 | `REQUEST_INVALID` |
| Another run active | 409 | `SYNTHETIC_RUN_ALREADY_ACTIVE` |
| Key reused with another run kind | 409 | `IDEMPOTENCY_CONFLICT` |
| Record absent | 404 | `SYNTHETIC_RUN_NOT_FOUND` |
| Service closed/capacity/platform unsupported | 503 | exact bounded service code |
| Unexpected route/service failure | 500 | `UNEXPECTED_FAILURE` |

Errors contain only `code` and a fixed human-safe message. They must not expose
exception text, local paths, keys, IDs other than the already requested opaque
request ID, or tracebacks.

## 7. Frontend contract

Create:

```text
apps/web/src/SyntheticValidationPanel.tsx
```

Modify `apps/web/src/api.ts` to add exact runtime-validated types and an
optional `SyntheticReviewApi` capability. `HttpApiClient` implements it;
`DemoApiClient` does not fabricate S2C evidence. A type guard keeps existing
test fakes and non-S2C modes compatible.

### 7.1 Panel behavior

The panel appears only after reviewer authentication and only when the
synthetic list endpoint exists. An exact 404 hides the panel. A 401 returns the
monitor to the existing PIN wall. A 503 renders a scoped unavailable state and
does not affect ordinary monitor controls.

The panel must display this disclosure before any action:

```text
MÔ PHỎNG — KHÔNG CAMERA — KHÔNG CẤP QUYỀN THU DỮ LIỆU
```

It provides exactly two actions:

- `Chạy preflight mô phỏng 60 giây`;
- `Chạy nominal mô phỏng 20 phút (18.077 frame tăng tốc)`.

Both buttons are disabled while a job is `QUEUED` or `RUNNING`. Starting a run
creates one browser idempotency key and reuses it only for a retry of the same
unaccepted POST. Polling uses authenticated GET requests and never repeats the
POST. Polling stops on terminal state, authentication loss, component unmount,
or a bounded 30-second client wait; a client timeout offers only `Kiểm tra lại
trạng thái`.

### 7.2 Receipt presentation

The panel maps terminal outcomes without overclaiming:

- `PERSISTED + BACKEND_CONTRACT_PASS`:
  `Contract synthetic đạt; thiết bị vẫn chưa được xác minh.`
- `PERSISTED + NO_GO`:
  `NO_GO kỹ thuật đã được lưu để đối chiếu.`
- `NOT_PERSISTED` or service failure:
  `Không hình thành được receipt lưu trữ hợp lệ.`

Each history card shows run sequence, run kind, job status, D1 outcome,
technical failure code when present, observation count, and shortened display
forms of receipt/artifact digests while preserving the full digest in an
accessible `<code>` detail. It always shows:

```text
SIMULATED
DEVICE_UNVERIFIED
d1_go=false
AUTHORITY_NOT_ISSUED
```

No card uses `ready`, `approved`, `physical pass`, `camera pass`, `research
ready`, or disciplinary language. `NO_GO` styling is technical and neutral,
not a participant warning.

### 7.3 Accessibility and visual hierarchy

- The disclosure is a persistent status banner, not transient toast text.
- Run status uses `aria-live="polite"`; service errors use `role="alert"`.
- Buttons have unique accessible names and visible disabled state.
- History uses a heading and ordered list; digests use wrapping code styles.
- The panel must remain usable at 1280x720 and a 360px viewport without
  horizontal document overflow.
- No color is the sole carrier of PASS, `NO_GO`, or unavailable meaning.

## 8. State and data-flow invariants

1. The browser chooses only one of two fixed run kinds.
2. The API authenticates the reviewer before parsing a service action.
3. The service derives every opaque and cryptographic binding.
4. Only one core runs at a time.
5. The core validates D1 semantics before persistence.
6. The temporary M2 store persists the minimized artifact for the process
   lifetime.
7. The API returns only the minimized receipt and fixed authority envelope.
8. The UI labels the result as synthetic and never advances exam/research
   state.
9. Shutdown waits for the accelerated worker, closes all stores, and removes
   the owned root before the launcher exits.

## 9. Threat model

| Threat | Control | Residual |
|---|---|---|
| Synthetic PASS is presented as physical readiness | Persistent UI/API authority envelope; forbidden copy tests | A screenshot can still be misrepresented outside the app |
| Browser injects a path, fixture, duration, device, or failure | Closed one-field request; extra fields rejected; no query options | Source code can still be modified outside the validated revision |
| Concurrent button clicks create overlapping cores | Service lock, single active record, both buttons disabled, 409 mapping | A crashed process loses its ephemeral history |
| POST retry executes twice | Required idempotency key and exact payload binding | Records are process-local and reset after restart |
| Valid `NO_GO` is rendered as application failure | Separate job, integration, and D1 states | Reviewer must still understand technical failure codes |
| Auth loss exposes or cancels evidence incorrectly | Reviewer bearer on every read/write; job completes independently | Another authenticated reviewer in the same process can see synthetic history |
| Synthetic metadata contaminates real participant storage | Dedicated owned temporary root, private synthetic IDs, cleanup on shutdown | Temp bytes exist while the app process is alive |
| Shutdown leaves store/thread/root behind | Idempotent close, executor drain, store close, root deletion, orphan tests | Forced OS termination can interrupt cleanup |
| UI mapper accepts forged authority | Exact schema and enum validation; unknown fields rejected | Browser extension or local malware remains outside this research control |
| Source UI/API drifts outside RP2 | Bind all S2C service, route, launcher, UI, style, and tests in RP2 | RP2 remains static evidence, not runtime authority |

## 10. Database and migration design

There is no new database schema and no migration beyond the existing M2 schema
version 2. The owned workspace uses current M1 initialization followed by
`M2PersistenceStore`; the service never alters the user's operational root.

Public API schema version remains 1. The new synthetic envelope has its own
closed `schema_version=1`. Existing M0/M1/M1-R1 endpoints and frontend response
mappers remain backward compatible.

## 11. RP2 and governance reconciliation

After source and tests stabilize, RP2 adds thirteen source/tool bindings:

```text
SRC_M2_SYNTHETIC_REVIEW_PY
SRC_M2_SYNTHETIC_REVIEW_API_PY
SRC_API_FACTORIES_PY
SRC_LAUNCHER_PY
WEB_API_TS
WEB_APP_TSX
WEB_SYNTHETIC_VALIDATION_PANEL_TSX
WEB_STYLES_CSS
TEST_M2_SYNTHETIC_REVIEW_SERVICE_PY
TEST_M2_SYNTHETIC_REVIEW_API_PY
TEST_LAUNCHER_PY
TEST_WEB_API_TS
TEST_WEB_SYNTHETIC_VALIDATION_PANEL_TSX
```

The source/tool inventory therefore grows from 31 to 44 if no other RP2 input
changes. Add four policy preimages, growing 28 to 32:

```text
synthetic_review_request_surface_policy_digest
synthetic_review_single_flight_policy_digest
synthetic_review_owned_workspace_policy_digest
synthetic_review_ui_disclosure_policy_digest
```

Run RP2 `--write` once only after the final bound source revision, then use
`--check` exclusively.

Current ledgers gain:

- roadmap milestone `M2-S2C`;
- acceptance gate `G17`;
- quality gate `G13`;
- risk `R-35`: reviewer-visible synthetic PASS mistaken for physical or
  research readiness;
- a current M2-S2C verification receipt.

Governance consistency remains outside the RP2-bound test inventory so ledger
text may be reconciled after the final static tuple without invalidating it.

## 12. Verification and acceptance

Implementation acceptance requires all of the following on one final revision:

- eight service tests, seven API tests, and one launcher test added without
  parametrization; Python collection grows from 904 to 920 if no other tests
  change;
- five new `api.test.ts` cases and eight panel cases; the web suite grows from
  58 to 71 if no other tests change;
- existing S2A and S2B focused tests remain green;
- Ruff and strict mypy pass for all changed Python;
- web lint, typecheck, test, and build pass;
- a real local `m2synthetic` monitor flow is exercised in a browser for:
  unavailable/empty, preflight PASS, nominal PASS, valid technical `NO_GO` via
  test injection only, active-run conflict, and authentication loss;
- the browser console has no uncaught error and the inspected requests contain
  no path/device/duration/fixture fields;
- shutdown leaves no `pdu-m2-s2c-*` owned root, PDU process, worker thread, or
  listener;
- RP2, governance, research suite, exact Python collection, full Python suite,
  release-manifest verification, proposal hash, and package exclusion all pass;
- an independent trust-boundary review finds no route on the exam origin, no
  bearer leak, no authority escalation, and no real-root mutation.

Runtime/browser evidence proves only the source-mode synthetic workflow that
was exercised. It does not prove the historical package, a clean machine,
physical camera behavior, model performance, deployment, or collection
readiness.

## 13. Stop conditions

Do not publish the M2-S2C marker if any of these occurs:

- an HTTP/browser value controls a path, fixture, duration, run ID, artifact ID,
  device, failure code, digest, or authority field;
- a route is reachable from the exam origin or without reviewer authentication;
- two cores overlap, idempotency can execute twice, or the record bound is not
  enforced;
- synthetic metadata touches the current M1/M1-R1 operational root;
- a run enters consent, preflight-ready, recording, participant, or collection
  state;
- a response or UI omits the synthetic/authority disclosure or calls a result
  physical/ready/approved;
- shutdown leaves the worker, store, temporary root, process, or listener;
- S2A/S2B, RP2, web, research, full suite, proposal, or release-manifest gates
  fail;
- the release package is rebuilt or advertised as containing S2C;
- any authority ceiling field changes to an open/issued value.

## 14. Post-M2-S2C boundary

After M2-S2C closes, the next decision is separate:

1. add synthetic API/UI history export only if a research need justifies a new
   governed local artifact; or
2. prepare a new physical M2 authority re-entry with its own A0/A1 and device
   evidence.

Neither path is authorized by this specification.
