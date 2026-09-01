# M2-S2C Synthetic Reviewer API/UI Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Status: `USER_APPROVED_FOR_IMPLEMENTATION_IMPLEMENTED_LOCALLY_VERIFIED`

**Goal:** Expose the fixed M2-S2A and M2-S2B synthetic cores through a
reviewer-authenticated, single-flight source-runtime API and an explicitly
non-authorizing monitor panel.

**Architecture:** A new `SyntheticReviewService` owns a temporary M1/M2
workspace for the application process, runs one fixed synthetic core at a time,
and retains at most 32 minimized job records. Monitor-only FastAPI routes expose
a closed one-field command and read-only receipt envelopes; a React panel polls
those routes and permanently labels every result as simulated and
device-unverified.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLite/M2 schema v2,
`ThreadPoolExecutor`, React, TypeScript, Vitest, Testing Library, Playwright,
Ruff, strict mypy, pytest, Windows 11 PowerShell.

**Spec:**
`docs/superpowers/specs/2026-08-31-m2-s2c-synthetic-reviewer-api-ui-design.md`

## Global Constraints

- This plan changes source runtime only; the release package is not rebuilt.
- Existing public M2-S2A and M2-S2B core interfaces remain unchanged.
- Existing M2 database schema version 2 and public API schema version 1 remain
  unchanged.
- The browser may submit only `run_kind=PREFLIGHT_60S|NOMINAL_20M` and an
  `Idempotency-Key` header.
- The service uses a private process-lifetime `pdu-m2-s2c-*` temporary root and
  never opens the configured M1/M1-R1 operational root.
- At most one synthetic run is active; there is no automatic retry or queue.
- No camera, audio, device enumeration, path, URL, participant, consent,
  `RECORDING`, export, deletion, deployment, M3, or external submission.
- Every response and rendered outcome preserves `SIMULATED`,
  `DEVICE_UNVERIFIED`, `d1_go=false`, and `AUTHORITY_NOT_ISSUED`.
- No test or runtime seam may weaken authentication, schema validation,
  persistence integrity, withdrawal checks, or authority controls.
- The current checkout is intentionally dirty and task-scoped. Do not reset,
  stash, commit, push, merge, package, deploy, or release without separate user
  authorization.

Every implementation task inherits this exact ceiling:

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

---

### Task 1: Freeze service and HTTP contracts with RED tests

**Files:**

- Create: `tests/backend/test_m2_synthetic_review_service.py`
- Create: `tests/backend/test_m2_synthetic_review_api.py`
- Modify: `tests/backend/test_launcher.py`
- Read: `src/pdu_exam_observer/m2_synthetic_integration.py`
- Read: `src/pdu_exam_observer/m2_persistence.py`
- Read: `src/pdu_exam_observer/api/factories.py`
- Read: `src/pdu_exam_observer/launcher.py`

**Interfaces:**

- Consumes: existing `M2SyntheticPreflightCore`, `M2SyntheticNominalCore`,
  `SyntheticIntegrationReceipt`, and `M2PersistenceStore`.
- Produces: test-enforced names and closed contracts used by Tasks 2 and 3.

- [ ] **Step 1: Confirm the pre-change baselines**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -o addopts="" --collect-only -q
Set-Location apps\web
npm test -- --reporter=verbose
Set-Location ..\..
```

Expected before new tests: `904 tests collected`; web `58 passed`.

- [ ] **Step 2: Create exactly eight service test functions**

Use these exact names, without parametrization:

- `test_owned_service_uses_private_draft_workspace_and_removes_it_on_close`
- `test_preflight_submission_is_fixed_persisted_and_idempotent`
- `test_nominal_submission_is_fixed_and_preserves_exact_receipt`
- `test_single_flight_and_payload_collision_fail_closed`
- `test_valid_no_go_is_terminal_but_not_service_failure`
- `test_not_persisted_and_pre_core_failure_never_claim_artifact`
- `test_capacity_close_and_platform_errors_are_bounded`
- `test_records_are_canonical_minimized_newest_first_and_shutdown_drains_worker`

The tests must assert private DRAFT synthetic metadata, no consent/recording,
fixed frame counts, exact authority fields, one active job, same-key replay,
different-payload collision, a bounded 32-record capacity, no forbidden output
keys, store closure, and root removal.

- [ ] **Step 3: Create exactly seven API test functions**

Use these exact names, without parametrization:

- `test_synthetic_routes_require_reviewer_bearer_and_are_monitor_only`
- `test_create_accepts_only_fixed_run_kind_and_required_idempotency_key`
- `test_list_and_item_return_closed_authority_envelopes`
- `test_active_and_idempotency_conflicts_map_to_exact_409_codes`
- `test_absent_closed_capacity_and_platform_states_are_sanitized`
- `test_forged_path_device_duration_fixture_digest_and_authority_fields_are_rejected`
- `test_auth_loss_blocks_reads_but_does_not_cancel_or_retry_the_worker`

Build `AppConfig` with an injected fake service so these tests do not open a
camera, real root, or worker. Verify no route appears on `create_exam_app()`.

- [ ] **Step 4: Add one launcher test**

Add exactly one function named
`test_launcher_m2synthetic_mode_injects_owned_service_and_closes_it`.

Patch only environment and service factory. Assert existing `m0`, `m1`, and
`m1r1` behavior remains unchanged, `m2synthetic` supplies the monitor service,
and monitor shutdown closes it.

- [ ] **Step 5: Run the new tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\backend\test_m2_synthetic_review_service.py `
  tests\backend\test_m2_synthetic_review_api.py `
  tests\backend\test_launcher.py -q
```

Expected: collection succeeds for the new test files and fails because
`pdu_exam_observer.m2_synthetic_review`, route registration, and
`m2synthetic` mode do not yet exist. Do not weaken assertions to obtain GREEN.

**Checkpoint:** 16 new Python tests exist; production code is still unchanged.

---

### Task 2: Implement the owned single-flight synthetic review service

**Files:**

- Create: `src/pdu_exam_observer/m2_synthetic_review.py`
- Test: `tests/backend/test_m2_synthetic_review_service.py`

**Interfaces:**

- Consumes:
  `M2SyntheticPreflightCore.execute(SyntheticPreflightRequest)`,
  `M2SyntheticNominalCore.execute(SyntheticNominalRequest)`, built-in fixture
  bundles, and `M2PersistenceStore`.
- Produces:
  `SyntheticReviewRunKind`, `SyntheticReviewJobStatus`,
  `SyntheticReviewServiceFailureCode`, `SyntheticReviewRunRecord`, and
  `SyntheticReviewService` exactly as defined in the spec.

- [ ] **Step 1: Add enums and the immutable record**

Start with the exact closed values:

```python
class SyntheticReviewRunKind(StrEnum):
    PREFLIGHT_60S = "PREFLIGHT_60S"
    NOMINAL_20M = "NOMINAL_20M"


class SyntheticReviewJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True, slots=True)
class SyntheticReviewRunRecord:
    schema_version: int
    request_id: str
    run_sequence: int
    run_kind: SyntheticReviewRunKind
    job_status: SyntheticReviewJobStatus
    service_failure_code: SyntheticReviewServiceFailureCode | None
    receipt: SyntheticIntegrationReceipt | None
```

`as_dict()` must serialize only these fields and `receipt.as_dict()`; it must
reject impossible terminal/nonterminal combinations in a private validator.

- [ ] **Step 2: Implement the production no-argument workspace factory**

Use an owned object that retains the `TemporaryDirectory` handle:

```python
@classmethod
def create_owned(cls) -> Self:
    owned = tempfile.TemporaryDirectory(prefix="pdu-m2-s2c-")
    root = Path(owned.name)
    backend = M1Backend(root, encryption_status="UNVERIFIED", acl_status="UNVERIFIED")
    # Create one private synthetic metadata chain; leave its session DRAFT.
    backend.store.close()
    store = M2PersistenceStore(root)
    return cls._from_owned_components(owned=owned, store=store, session_id=session_id)
```

The concrete implementation must close the M1 store on every exception path,
never return `root` or `session_id`, and keep internal test injection behind
underscored constructors.

- [ ] **Step 3: Implement request IDs and idempotency binding**

Use:

```python
_IDEMPOTENCY = re.compile(r"[A-Za-z0-9._-]{16,128}\Z")

def _request_id(key: str) -> str:
    return "synrun-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
```

Store only the digest-derived request ID and run kind. Under one lock, return
same-key/same-kind records, reject same-key/different-kind, reject a second
active request, and reject a distinct 33rd record.

- [ ] **Step 4: Implement the worker state machine**

Use a one-worker executor and immutable record replacement:

```python
self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdu-m2-synthetic")

def _run(self, request_id: str) -> None:
    self._replace_status(request_id, SyntheticReviewJobStatus.RUNNING)
    try:
        receipt = self._execute_fixed_core(request_id)
        self._replace_terminal(request_id, receipt=receipt)
    except Exception:
        self._replace_terminal(
            request_id,
            failure=SyntheticReviewServiceFailureCode.UNEXPECTED_FAILURE,
        )
```

Never put exception text in the record. `_execute_fixed_core()` derives fixed
run, intent, artifact, source, model, release-manifest, and encoder bindings.
It may dispatch only to the two built-in fixture factories.

- [ ] **Step 5: Implement deterministic reads and shutdown**

`get()` validates `synrun-[0-9a-f]{32}` and raises `KeyError` otherwise.
`list()` returns immutable records ordered by descending `run_sequence`.
`close()` must:

```python
with self._lock:
    self._closed = True
self._executor.shutdown(wait=True, cancel_futures=False)
try:
    self._store.close()
finally:
    self._owned.cleanup()
```

Make close idempotent and preserve cleanup attempts if store closure fails.

- [ ] **Step 6: Run focused service tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_m2_synthetic_review_service.py -q
```

Expected: `8 passed`.

- [ ] **Step 7: Run S2A/S2B regression immediately**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\backend\test_m2_synthetic_integration.py `
  tests\backend\test_m2_synthetic_nominal_integration.py `
  tests\backend\test_m2_synthetic_review_service.py -q
```

Expected: all 28 tests pass; S2A/S2B public APIs and digests remain unchanged.

**Checkpoint:** the service is independently testable without HTTP or React.

---

### Task 3: Add monitor-only API routes and the source runtime mode

**Files:**

- Create: `src/pdu_exam_observer/api/synthetic_review.py`
- Modify: `src/pdu_exam_observer/api/factories.py`
- Modify: `src/pdu_exam_observer/launcher.py`
- Test: `tests/backend/test_m2_synthetic_review_api.py`
- Test: `tests/backend/test_launcher.py`

**Interfaces:**

- Consumes: `SyntheticReviewService.submit/get/list/close`.
- Produces:
  `register_synthetic_review_routes(app, require_reviewer, service) -> None`,
  `AppConfig.synthetic_review_service`, and `PDU_RUNTIME_MODE=m2synthetic`.

- [ ] **Step 1: Define the closed request model and fixed authority envelope**

In `api/synthetic_review.py`:

```python
class SyntheticRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_kind: Literal["PREFLIGHT_60S", "NOMINAL_20M"]


def _authority_envelope() -> dict[str, object]:
    return {
        "schema_version": 1,
        "capability_status": "SYNTHETIC_REVIEW_ONLY",
        "evidence_kind": "SIMULATED",
        "package_contains_integration": False,
        "production_reconciler_implemented": False,
        "production_reconciler_real_storage_verified": False,
        "real_data_deletion_authorized": False,
        "execution_authorized": False,
        "physical_camera_access_authorized": False,
        "device_gate_decision": "UNVERIFIED",
        "d1_go": False,
        "participant_collection_authorized": False,
        "research_ready": False,
        "collection_authorized": False,
        "authority_status": "AUTHORITY_NOT_ISSUED",
    }
```

Do not accept a generic dictionary or copy unknown request fields into errors.

- [ ] **Step 2: Register the three authenticated monitor routes**

Use a dedicated registration function:

```python
def register_synthetic_review_routes(
    app: FastAPI,
    *,
    require_reviewer: Callable[[], str],
    service: SyntheticReviewService,
) -> None:
    @app.post("/api/v1/synthetic-runs", status_code=202)
    async def create_synthetic_run(
        payload: SyntheticRunCreateRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        _reviewer: Annotated[str, Depends(require_reviewer)],
    ) -> dict[str, object]:
        record = service.submit(
            SyntheticReviewRunKind(payload.run_kind),
            idempotency_key=idempotency_key,
        )
        return {**_authority_envelope(), "run": record.as_dict()}

    @app.get("/api/v1/synthetic-runs")
    async def list_synthetic_runs(
        _reviewer: Annotated[str, Depends(require_reviewer)],
    ) -> dict[str, object]:
        return {
            **_authority_envelope(),
            "runs": [record.as_dict() for record in service.list()],
        }

    @app.get("/api/v1/synthetic-runs/{request_id}")
    async def get_synthetic_run(
        request_id: str,
        _reviewer: Annotated[str, Depends(require_reviewer)],
    ) -> dict[str, object]:
        return {**_authority_envelope(), "run": service.get(request_id).as_dict()}
```

Map every domain exception to the exact fixed HTTP/code table in the spec.
Errors use the existing structured
`detail={"code": "SYNTHETIC_RUN_ALREADY_ACTIVE", "message": "A synthetic run is already active"}`
shape and never include `str(exc)`.

- [ ] **Step 3: Inject the optional service into `AppConfig`**

Add:

```python
synthetic_review_service: SyntheticReviewService | None = None
```

Register routes in `create_monitor_app()` only when this value is non-null.
Never register them in `create_exam_app()`. Add one monitor shutdown handler
that calls `service.close()` exactly once.

- [ ] **Step 4: Add the fixed launcher mode**

Extend the allowlist to:

```python
{"m0", "m1", "m1r1", "m2synthetic"}
```

For `m2synthetic`, keep `M0Backend` and inject
`SyntheticReviewService.create_owned()`. If app construction fails after
service creation, close the service before re-raising. Existing modes must not
instantiate the service.

- [ ] **Step 5: Run API and launcher tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\backend\test_m2_synthetic_review_api.py `
  tests\backend\test_launcher.py -q
```

Expected: seven new API tests and the full launcher file pass.

- [ ] **Step 6: Run auth and origin regressions**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\backend\test_auth.py `
  tests\backend\test_integration_contract.py `
  tests\backend\test_m2_synthetic_review_api.py -q
```

Expected: all pass; exam origin has no synthetic route, monitor requests omit
cookies, and reviewer bearer behavior is unchanged.

**Checkpoint:** authenticated HTTP integration is complete without frontend
changes.

---

### Task 4: Add strict frontend API types and mappers

**Files:**

- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/api.test.ts`

**Interfaces:**

- Consumes: the exact HTTP envelopes from Task 3.
- Produces:
  `SyntheticReviewApi`, `SyntheticRunKind`, `SyntheticRunRecord`,
  `SyntheticIntegrationReceiptView`, and `isSyntheticReviewApi()`.

- [ ] **Step 1: Add five RED adapter tests**

Add five `it()` cases under a new `synthetic review API adapter` describe block:

- `uses reviewer bearer and one-field body with a stable idempotency key`
- `maps an exact queued running and terminal record`
- `rejects missing extra and authority-mutated envelope fields`
- `maps exact active collision unavailable and not-found failures`
- `never sends a path device duration fixture digest session or authority field`

Run:

```powershell
Set-Location apps\web
npm test -- --run src/api.test.ts
Set-Location ..\..
```

Expected: the five new cases fail because the API methods/types are absent.

- [ ] **Step 2: Add exact frontend types**

Define closed unions rather than `string`:

```typescript
export type SyntheticRunKind = 'PREFLIGHT_60S' | 'NOMINAL_20M';
export type SyntheticJobStatus = 'QUEUED' | 'RUNNING' | 'TERMINAL';
export type SyntheticReviewRunRecord = {
  schemaVersion: 1;
  requestId: string;
  runSequence: number;
  runKind: SyntheticRunKind;
  jobStatus: SyntheticJobStatus;
  serviceFailureCode: string | null;
  receipt: SyntheticIntegrationReceiptView | null;
};
```

The receipt type must include every current S2A/S2B field and literal authority
values. It must not include index signatures.

- [ ] **Step 3: Implement strict record and envelope mappers**

Reject unknown keys by comparing `Object.keys(value).sort()` with exact key
sets. Verify digest fields are lowercase 64-character hexadecimal strings,
artifact fields are all-null when `NOT_PERSISTED`, and authority literals are
unchanged. A mapper failure throws `Error('Synthetic review response is invalid')`
without echoing response content.

- [ ] **Step 4: Add the optional capability interface**

```typescript
export interface SyntheticReviewApi {
  listSyntheticRuns(): Promise<SyntheticReviewRunRecord[]>;
  createSyntheticRun(runKind: SyntheticRunKind, idempotencyKey: string): Promise<SyntheticReviewRunRecord>;
  getSyntheticRun(requestId: string): Promise<SyntheticReviewRunRecord>;
}

export function isSyntheticReviewApi(value: ApiClient): value is ApiClient & SyntheticReviewApi {
  return typeof (value as Partial<SyntheticReviewApi>).listSyntheticRuns === 'function';
}
```

Implement all three methods on `HttpApiClient`. Do not add them to
`DemoApiClient`; demo mode cannot fabricate an S2C receipt.

- [ ] **Step 5: Run adapter tests, typecheck, and lint**

Run:

```powershell
Set-Location apps\web
npm test -- --run src/api.test.ts
npm run typecheck
npm run lint
Set-Location ..\..
```

Expected: adapter tests, typecheck, and lint pass.

**Checkpoint:** browser networking is typed and fail-closed; no UI action exists
yet.

---

### Task 5: Implement the synthetic validation panel

**Files:**

- Create: `apps/web/src/SyntheticValidationPanel.tsx`
- Create: `apps/web/src/SyntheticValidationPanel.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`

**Interfaces:**

- Consumes: `SyntheticReviewApi` from Task 4.
- Produces:
  `SyntheticValidationPanel({ api }: { api: SyntheticReviewApi })`.

- [ ] **Step 1: Create exactly eight RED component tests**

Use these eight cases:

- `hides the panel only for the exact absent-route 404`
- `renders the permanent simulated authority disclosure and exactly two run actions`
- `submits preflight once with one key and disables both buttons while active`
- `polls nominal with GET only and renders persisted backend-contract pass without readiness language`
- `renders persisted no-go as neutral technical audit evidence`
- `renders not-persisted and service errors without a false artifact claim or automatic repost`
- `handles active conflict by refreshing existing history and stops polling on auth loss or unmount`
- `keeps headings live regions digest details and narrow viewport layout accessible`

Run:

```powershell
Set-Location apps\web
npm test -- --run src/SyntheticValidationPanel.test.tsx
Set-Location ..\..
```

Expected: RED because the component does not exist.

- [ ] **Step 2: Implement capability discovery and empty state**

On mount, call `listSyntheticRuns()`. Return `null` only for exact route-absent
404. Render a scoped unavailable panel for 503 or malformed responses. Do not
start a run automatically.

- [ ] **Step 3: Implement the two fixed actions and stable POST retry**

Use component state that binds one idempotency key to one unaccepted POST:

```typescript
type PendingSubmission = { runKind: SyntheticRunKind; key: string };
```

Generate the key once with `newIdempotencyKey()`. Reuse it only when the user
explicitly retries that same failed POST. Once the POST is accepted, all later
refreshes use `getSyntheticRun(requestId)` and never POST again.

- [ ] **Step 4: Implement bounded polling**

Poll every 250 ms for at most 120 reads. Stop on `TERMINAL`, auth loss, or
unmount. A timeout displays `Kiểm tra lại trạng thái`; that action performs one
GET and may resume bounded polling, but never resubmits the run.

- [ ] **Step 5: Implement receipt cards and non-authorizing copy**

Render the exact persistent banner:

```text
MÔ PHỎNG — KHÔNG CAMERA — KHÔNG CẤP QUYỀN THU DỮ LIỆU
```

Map PASS, `NO_GO`, and `NOT_PERSISTED` to the exact Vietnamese statements in
the spec. Always render `SIMULATED`, `DEVICE_UNVERIFIED`, `d1_go=false`, and
`AUTHORITY_NOT_ISSUED`. Never render physical/readiness/approval claims.

- [ ] **Step 6: Integrate the panel into authenticated Monitor only**

In `App.tsx`, use `isSyntheticReviewApi(api)` after reviewer authentication and
render the panel as a separate section. Do not put it on the exam route, in demo
mode, or before the PIN wall.

- [ ] **Step 7: Add focused accessible styles**

Add `.syntheticValidationPanel`, `.syntheticAuthorityBanner`,
`.syntheticRunActions`, and `.syntheticReceiptList` styles. Use existing color
tokens, visible focus, wrapping `<code>`, and a 360px media rule. Do not hide
authority text visually or rely on color alone.

- [ ] **Step 8: Run the full web gate**

Run:

```powershell
Set-Location apps\web
npm run typecheck
npm run lint
npm test -- --reporter=verbose
npm run build
Set-Location ..\..
```

Expected if no unrelated test changes: 10 existing files plus one new file,
`71 passed`; typecheck, lint, and build pass.

**Checkpoint:** the source UI flow exists and has component/API evidence, but
has not yet received actual browser acceptance.

---

### Task 6: Exercise the actual local source application and inspect the UI

**Files:**

- Create at closure: `docs/ai/M2_S2C_VERIFICATION.md`
- Create runtime evidence directory:
  `docs/ai/evidence/m2-s2c/`
- Do not modify production source during this task.

**Interfaces:**

- Consumes: the `m2synthetic` launcher, monitor API, and built web bundle.
- Produces: current-revision runtime evidence, screenshot hashes, and a
  verification receipt; it does not produce authority.

- [ ] **Step 1: Start one local source runtime**

Build web first, then start the source launcher in a managed terminal session:

```powershell
$m2s2cRootsBefore = @(
  Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'pdu-m2-s2c-*' |
    ForEach-Object FullName
)
$env:PDU_RUNTIME_MODE = 'm2synthetic'
$env:PDU_REVIEWER_PIN = '48261057'
$env:PDU_OPEN_BROWSER = '0'
$env:PDU_EXAM_PORT = '8765'
$env:PDU_MONITOR_PORT = '8766'
.\.venv\Scripts\python.exe -m pdu_exam_observer
```

Expected: only loopback/localhost listeners on 8765 and 8766. No device or
camera enumeration appears in output.

- [ ] **Step 2: Run browser acceptance with Playwright**

Open `http://localhost:8766/monitor`, authenticate, and verify:

1. the panel is absent before authentication;
2. the permanent synthetic disclosure is visible after authentication;
3. the empty history has no automatic run;
4. preflight produces 977 observations and a persisted PASS receipt;
5. nominal produces 18,077 observations and a persisted PASS receipt;
6. both runs still display `DEVICE_UNVERIFIED` and `d1_go=false`;
7. the second button is disabled while one run is active;
8. logout returns to the PIN wall and blocks history reads.

Inspect the browser console and network log. Confirm POST bodies contain only
`run_kind`, GETs perform polling, credentials are omitted, and Authorization is
in the header rather than URL/cookie.

- [ ] **Step 3: Inspect representative layouts**

Capture authenticated terminal-history screenshots at 1280x720 and 360x800.
Check disclosure prominence, action hierarchy, digest wrapping, live status,
PASS/`NO_GO` wording from test fixtures, and absence of horizontal overflow.
Save screenshots under `docs/ai/evidence/m2-s2c/` and record SHA-256 values.

- [ ] **Step 4: Shut down and prove cleanup**

Stop the managed launcher normally. Verify:

```powershell
$m2s2cRootsAfter = @(
  Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'pdu-m2-s2c-*' |
    ForEach-Object FullName
)
Compare-Object $m2s2cRootsBefore $m2s2cRootsAfter
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 8765,8766
```

Expected: no new task-created `pdu-m2-s2c-*` directory and no listener. Confirm no
`pdu-m2-synthetic` worker remains in the process because the process is gone.

- [ ] **Step 5: Write the verification receipt**

Record exact commands, exit codes, browser states, screenshot paths/hashes,
console/network observations, authority ceiling, and residual limits in
`docs/ai/M2_S2C_VERIFICATION.md`. Do not use `research_ready`, `D1_GO`, package,
physical, deployment, or approval language except to state they remain false or
unverified.

**Checkpoint:** the changed user-visible flow has actual browser evidence, not
only test evidence.

---

### Task 7: Bind final source in RP2 and reconcile governance

**Files:**

- Modify: `scripts/build_m2_d1_n2_rp2.py`
- Modify: `tests/backend/test_m2_d1_n2_rp2_artifacts.py`
- Regenerate once: `docs/spec/M2_D1_N2_AUTHORITY_BINDING.schema.json`
- Regenerate once: `docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json`
- Modify: `tests/research/test_m1_r1_governance_closure.py`
- Modify: `docs/ai/CURRENT_TASK.md`
- Modify: `docs/ai/TASK_CONTRACT.md`
- Modify: `docs/plans/ROADMAP.md`
- Modify: `docs/plans/ACCEPTANCE_GATES.md`
- Modify: `docs/ai/QUALITY_GATES.md`
- Modify: `docs/plans/RISK_REGISTER.md`

**Interfaces:**

- Consumes: final stable S2C service/API/launcher/frontend/tests.
- Produces: one current RP2 tuple and consistent `M2-S2C`, `G17`, `G13`, and
  `R-35` ledger entries.

- [ ] **Step 1: Extend RP2 inventory tests first**

Require the thirteen exact identifiers listed in the spec. Update expected
source/tool inventory from 31 to 44 and policy-preimage count from 28 to 32.
Add exact preimage assertions:

```python
"synthetic_review_request_surface_policy_digest"
"synthetic_review_single_flight_policy_digest"
"synthetic_review_owned_workspace_policy_digest"
"synthetic_review_ui_disclosure_policy_digest"
```

Run the RP2 artifact test and verify RED because the builder does not yet bind
the new sources.

- [ ] **Step 2: Extend the RP2 builder**

Bind service, route, factories, launcher, API, App, panel, style, two backend
test files, launcher test, API TypeScript test, and panel test. Policy fields
must state:

```text
request_fields=run_kind_only
run_kinds=PREFLIGHT_60S,NOMINAL_20M
max_active_runs=1
max_records=32
automatic_retry=false
caller_path=false
caller_device=false
owned_temp_root=true
cleanup_on_shutdown=true
evidence_kind=SIMULATED
device_gate_decision=UNVERIFIED
d1_go=false
authority_status=AUTHORITY_NOT_ISSUED
```

Run RP2 artifact tests until they pass before writing generated artifacts.

- [ ] **Step 3: Regenerate RP2 exactly once on the final bound revision**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\build_m2_d1_n2_rp2.py --write
.\.venv\Scripts\python.exe scripts\build_m2_d1_n2_rp2.py --check
```

Expected: both exit 0. Record the new static-binding, candidate exact-bytes,
and schema exact-bytes SHA-256 values. Do not run `--write` again unless a bound
source file changes.

- [ ] **Step 4: Extend governance consistency before ledger edits**

Within the existing three test functions, require:

```text
M2_S2C_SYNTHETIC_REVIEWER_API_UI_LOCALLY_VERIFIED_DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY
G17
G13
R-35
new RP2 tuple
evidence_kind=SIMULATED
package_contains_integration=false
device_gate_decision=UNVERIFIED
d1_go=false
authority_status=AUTHORITY_NOT_ISSUED
```

Also forbid claims that the panel proves a camera, device, model, participant,
research-ready, packaged, or approved state. Run the governance test and verify
RED against the old ledgers.

- [ ] **Step 5: Reconcile current ledgers**

Update only current sections. Add M2-S2C, G17, G13, and R-35, the final RP2
tuple, source-mode/browser evidence, package exclusion, and the complete closed
authority ceiling. Retain M2-S2A/S2B and earlier governance receipts as
historical/current evidence without rewriting their original tuples.

- [ ] **Step 6: Run governance and RP2 checks**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\build_m2_d1_n2_rp2.py --check
.\.venv\Scripts\python.exe -m pytest tests\backend\test_m2_d1_n2_rp2_artifacts.py -q
.\.venv\Scripts\python.exe -m pytest tests\research\test_m1_r1_governance_closure.py -q
```

Expected: RP2 check passes, RP2 artifact tests pass, governance remains exactly
three passing test functions.

**Checkpoint:** final source identity and current governance agree without
rewriting the historical release package.

---

### Task 8: Independent review and final verification

**Files:**

- Inspect all changed source, tests, generated RP2 artifacts, verification
  evidence, and ledgers.
- Do not edit during the first review pass; record findings by severity.

**Interfaces:**

- Consumes: all earlier task outputs.
- Produces: one verified source revision or a concrete reopened task when a
  gate fails.

- [ ] **Step 1: Perform a trust-boundary review**

Review these specific hypotheses:

1. synthetic routes cannot appear on exam origin;
2. every route requires the existing reviewer bearer and omits credentials;
3. body/query/path surfaces cannot carry local paths, devices, fixtures,
   durations, IDs, digests, failure injection, or authority overrides;
4. the service never opens the configured M1/M1-R1 root;
5. authentication loss cannot duplicate or cancel a worker;
6. shutdown cannot publish success before store/root cleanup;
7. UI schema validation cannot accept a forged authority field;
8. no rendered copy implies physical, research, approval, or collection state.

Resolve Critical/Important findings and rerun only the evidence invalidated by
the fix.

- [ ] **Step 2: Run focused Python integration**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\backend\test_m2_synthetic.py `
  tests\backend\test_m2_d1_contract.py `
  tests\backend\test_m2_persistence.py `
  tests\backend\test_m2_synthetic_integration.py `
  tests\backend\test_m2_synthetic_nominal_integration.py `
  tests\backend\test_m2_synthetic_review_service.py `
  tests\backend\test_m2_synthetic_review_api.py `
  tests\backend\test_launcher.py -q
```

Expected: all pass with no overlapping pytest process.

- [ ] **Step 3: Run static Python gates**

Run:

```powershell
.\.venv\Scripts\ruff.exe check `
  src\pdu_exam_observer\m2_synthetic_review.py `
  src\pdu_exam_observer\api\synthetic_review.py `
  src\pdu_exam_observer\api\factories.py `
  src\pdu_exam_observer\launcher.py `
  scripts\build_m2_d1_n2_rp2.py `
  tests\backend\test_m2_synthetic_review_service.py `
  tests\backend\test_m2_synthetic_review_api.py `
  tests\backend\test_launcher.py `
  tests\backend\test_m2_d1_n2_rp2_artifacts.py `
  tests\research\test_m1_r1_governance_closure.py

.\.venv\Scripts\python.exe -m mypy --strict `
  src\pdu_exam_observer\m2_synthetic_review.py `
  src\pdu_exam_observer\api\synthetic_review.py `
  src\pdu_exam_observer\api\factories.py `
  src\pdu_exam_observer\launcher.py
```

Expected: Ruff and strict mypy pass.

- [ ] **Step 4: Run final web gates once on the final source revision**

Run:

```powershell
Set-Location apps\web
npm run typecheck
npm run lint
npm test -- --reporter=verbose
npm run build
Set-Location ..\..
```

Expected if no unrelated changes: `71 passed`; typecheck, lint, and build pass.

- [ ] **Step 5: Run RP2, governance, research, collection, and full suite**

Run sequentially:

```powershell
.\.venv\Scripts\python.exe scripts\build_m2_d1_n2_rp2.py --check
.\.venv\Scripts\python.exe -m pytest tests\research\test_m1_r1_governance_closure.py -q
.\.venv\Scripts\python.exe -m pytest tests\research -q
.\.venv\Scripts\python.exe -m pytest -o addopts="" --collect-only -q
.\.venv\Scripts\python.exe -m pytest -o addopts="" -q --durations=20
```

Expected if no unrelated changes: governance `3 passed`, research `69 passed`,
`920 tests collected`, and `920 passed` in one full invocation.

- [ ] **Step 6: Verify immutable package and proposal boundaries**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\release_manifest.py verify `
  --bundle-root packaging\release\PDU-Exam-Observer `
  --bundled packaging\release\PDU-Exam-Observer\RELEASE_MANIFEST.json `
  --detached packaging\RELEASE_MANIFEST.json

(Get-FileHash -Algorithm SHA256 `
  docs\source\DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx).Hash.ToLowerInvariant()

rg -n -i "M2_S2C|m2_synthetic_review|SyntheticValidationPanel" `
  packaging\release\PDU-Exam-Observer
```

Expected: manifest verified; proposal hash remains
`2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5`;
package scan has zero matches.

- [ ] **Step 7: Verify final cleanup and diff integrity**

Run:

```powershell
git diff --check
git status --short
Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'pdu-m2-s2c-*'
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 8765,8766
```

Expected: no whitespace error, only task-scoped changed paths, no task-owned
temporary root, and no PDU listener/process. Keep the dirty checkout in place;
do not commit, push, package, deploy, or release.

## Stop conditions

Stop implementation and do not publish the M2-S2C marker when any required
focused, static, browser, RP2, governance, research, full-suite, proposal, or
package gate fails; when a path/device/authority surface is accepted; when the
exam origin exposes S2C; when synthetic work touches the real root; when two
jobs overlap; when cleanup is incomplete; or when any authority flag opens.

## Execution handoff

This document is a plan, not execution authority. After user approval, execute
inline with `superpowers:executing-plans` unless the user explicitly requests
subagents. Preserve the current dirty checkout and review after each checkpoint.
