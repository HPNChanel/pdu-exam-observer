# D1-N2 I2 Signed-A0 Remediation Design

Date: `2026-08-29`

Design status: `USER_APPROVED_OPTION_A`

Implementation status: `SOURCE_IMPLEMENTED_I2_STATIC_PACK_APPROVED_BOOTSTRAP_UNPROVISIONED`

Authority ceiling: `AUTHORITY_NOT_ISSUED`

## 1. Decision and outcome

The independent Sol/xhigh I2 review rejected the current D1-N2 source under
`static_bindings_digest=5c1606a0e20c571aa37f0ccb150c819457612ec96cc2aea1d621930de28757d0`.
The user approved remediation option A: a signed, offline `A0ApprovalV1`
envelope verified by a frozen trust bootstrap outside the RP2 mutation domain.

The remediation must close five review findings:

1. RP2 candidate/schema mutual consistency is not an independent trust root.
2. WorkerGrant does not bind the worker challenge and exact Job derivation.
3. TERMINAL cannot reconstructively verify receipt, failure-ledger, accounting,
   privacy, audio/network, watchdog, and cleanup semantics.
4. retained leases close after TERMINAL persistence, allowing cleanup ambiguity
   to appear restart-valid;
5. failures before bridge ownership transfer can leak retained preparation
   leases.

The result of implementation is source readiness for another independent I2
review. It does not create a signing key, provision a verifier bootstrap, issue
A0 or A1, invoke preparation, open a camera, or authorize execution.

## 2. Evidence and non-authority baseline

- `OBSERVED`: the rejected RP2 contains 13 bound artifacts and passed its
  self-consistency checker, focused tests, Ruff, and mypy.
- `OBSERVED`: an in-memory coordinated candidate/schema mutation could enable
  authority booleans while retaining self-consistent static/schema digests.
- `OBSERVED`: production `prepare_d1_n2()` and
  `run_d1_n2_preflight()` were not invoked by the I2 review.
- `USER_STATED`: option A was approved on `2026-08-29`.
- `UNVERIFIED`: no production signing identity, signed approval envelope,
  frozen verifier bootstrap, PreparedAuthority, WorkerGrant, receipt,
  failure ledger, TERMINAL, or native/device evidence exists.

The rejected digest and every historical A0 remain non-reusable. The binding
ceiling stays `authority_status=AUTHORITY_NOT_ISSUED`,
`execution_authorized=false`, `physical_camera_access_authorized=false`,
`device_gate_decision=UNVERIFIED`, and `d1_go=false`.

## 3. Threat model

The signed A0 design prevents RP2 regeneration, candidate/schema coordination,
or repository-file substitution from changing the exact triple approved by A0.
It assumes the externally frozen verifier bootstrap and its public verification
key are provisioned through a trust channel outside the mutable repository.

The design does not claim to prevent the local OS account from running an
unrelated camera program or replacing the entire application with arbitrary
code. Its boundary is the governed D1-N2 entrypoint and its authority records.
OS-enforced application control or network isolation would be a separate
security design and is not inferred from source tests.

No private signing key, credential, secret, or production signature may be
stored in the repository, `.env`, browser input, documentation, test fixture,
memory file, or RP2 candidate.

## 4. Frozen bootstrap and signed approval

### 4.1 Bootstrap boundary

The production authority path consumes a `FixedA0Verifier` port. The port has
no caller-supplied path, key, algorithm, digest, environment override, working
directory, PATH search, URL, network lookup, or fallback verifier.

The future production port is backed by one externally provisioned signed
bootstrap containing the A0 public verification key. That bootstrap is outside
the RP2 mutation domain and must be independently frozen and verified before
I2 can pass for native preparation. Its packaging, publisher identity, offline
signature verification, fixed location, and clean-machine behavior require a
separate provisioning receipt.

Until that receipt exists, the only production result is the typed status
`BOOTSTRAP_UNPROVISIONED`. Test ports may use test-only keys, but no test key or
fake verifier may be reachable from the production factory.

### 4.2 Signature profile

The approval signature profile is fixed as:

- algorithm: `ECDSA_P256_SHA256_IEEE_P1363`;
- signed bytes: UTF-8 canonical JSON of the exact `body` object, using sorted
  keys, compact separators, ASCII escaping, and no NaN/Infinity;
- signature: exactly 64 raw bytes `r || s`, base64url without padding;
- key identifier: lowercase SHA-256 of the canonical public-key blob;
- verification: offline only, one fixed key identifier, no certificate or
  algorithm agility inside an authority epoch.

An implementation may use Windows CNG or the frozen bootstrap internally. It
must not add an online certificate check or a mutable crypto provider.

### 4.3 Closed `A0ApprovalV1` envelope

The canonical envelope has exactly these root keys:

```text
schema_version
domain
body
key_id
signature_algorithm
signature_b64url
```

Required fixed root values are:

```text
schema_version = 1
domain = D1N2/A0_APPROVAL/v1
signature_algorithm = ECDSA_P256_SHA256_IEEE_P1363
```

The closed `body` has exactly these keys:

```text
authority_revision
static_bindings_digest
binding_schema_canonical_sha256
candidate_exact_bytes_sha256
approval_id_digest
issued_unix_ns
expires_unix_ns
no_human
video_only
duration_seconds
retry_authorized
audio_authorized
network_authorized
raw_retention_authorized
participant_collection_authorized
model_training_or_evaluation_authorized
```

The fixed scope is:

```text
authority_revision = d1-n2-authority-v1
no_human = true
video_only = true
duration_seconds = 60
retry_authorized = false
audio_authorized = false
network_authorized = false
raw_retention_authorized = false
participant_collection_authorized = false
model_training_or_evaluation_authorized = false
```

All three RP2 values and `approval_id_digest` are lowercase SHA-256 strings.
The envelope validity interval is exactly 900 seconds. A valid signature with
an expired, future-issued, overlong, malformed, duplicated-key, or extra-field
body is invalid authority.

### 4.4 Approval installation and consumption

The signed envelope is installed only by a separately authorized external A0
installer at the fixed D1-N2 leaf `a0-approval.v1.json`. Installation uses
`CREATE_NEW`, no-follow, share-zero, exact canonical bytes, parent durability,
and readback verification. The application cannot create, replace, refresh,
repair, or sign this file.

The parameter-free prepare path verifies the signature and fixed scope before
any PENDING write. Once the signature is valid, PENDING is created immediately
and binds `a0_approval_digest`, `approval_id_digest`, and the approved RP2
triple. That PENDING creation consumes the approval for launch purposes.

Static/RP2 or later no-stream failure leaves sticky PENDING and makes the A0
non-reusable. Invalid signature or an unprovisioned bootstrap creates no
authority record because no valid A0 existed. There is no reinstall, overwrite,
retry, or second PREPARED path.

The A0 handle is retained from verification through PREPARED and, after A1,
through the execution cleanup boundary. Only its canonical digest and approved
triple enter authority records; signature bytes, raw approval identifier, key
material, and path do not.

## 5. RP2 exact-triple verification

Introduce an immutable typed value:

```python
@dataclass(frozen=True, slots=True)
class ApprovedRP2Triple:
    static_bindings_digest: str
    binding_schema_canonical_sha256: str
    candidate_exact_bytes_sha256: str
    a0_approval_digest: str
    approval_id_digest: str
    issued_unix_ns: int
    expires_unix_ns: int
```

`FixedA0Verifier.verify()` returns this value plus a retained A0 lease only
after signature, schema, scope, time, file-identity, and durability checks.
`FixedRP2Verifier.verify(expected: ApprovedRP2Triple)` then requires exact
equality for:

1. SHA-256 of exact candidate bytes;
2. SHA-256 of canonical schema bytes;
3. SHA-256 of canonical `static_bindings`;
4. all fixed authority-denial booleans and issuance-only `UNVERIFIED` values;
5. every artifact size/hash and policy preimage/digest.

The candidate and schema may not supply their own accepted values. Coordinated
regeneration changes the triple and fails against the prior signed A0. Any RP2,
source, builder, lock, model, formatting, or schema change invalidates the old
approval.

## 6. Preparation ownership and abort

The preparation composition solely owns the A0, RP2, supervisor, Camera-class,
FFmpeg, dependency, and model leases until explicit transfer to the execution
bridge.

Add two internal operations:

```python
abort_pre_bridge() -> AbortReport
transfer_to_bridge() -> ExecutionOwnership
```

`AbortReport` is closed and contains only step enums and a final clean/uncertain
status. `abort_pre_bridge()` is idempotent, closes every retained lease exactly
once, clears private values, performs no grant/native launch, and returns the
same terminal report on repeated calls.

Every unsuccessful prepare result, malformed composition result,
driver-factory exception, bridge-construction exception, controller exception,
or `BaseException` before ownership transfer invokes this abort path. After
transfer, only the bridge may close the leases. No object may have ambiguous or
shared cleanup ownership.

## 7. Challenge, WorkerGrant, and Job composition

The execution bridge generates a 32-byte raw challenge before WorkerGrant
issuance. It derives:

```text
challenge_digest = sha256(domain || raw_challenge)
job_name_digest = sha256(domain || fixed_job_prefix || raw_challenge)
```

Only these two digests enter `WorkerGrantBindingAttestation`. The raw challenge,
capability, Job name, device name, executable path, and argv remain memory-only.

The driver receives the raw challenge through the private in-memory execution
request. It must not generate replacement entropy. Before worker continuation,
the driver derives the fixed Job name, proves its digest matches WorkerGrant,
creates the kill-on-close Job, launches suspended, assigns the worker, and
proves the worker's challenge maps to the persisted digest.

The issued and revoked WorkerGrant records retain the challenge and Job digests
through the entire grant chain. Any mismatch, replay, second handoff, missing
Job assignment, or unknown challenge suppresses worker continuation and pass.

## 8. Closed receipt, failure ledger, and TERMINAL

### 8.1 Receipt and ledger

The driver returns canonical bytes for a closed redacted receipt and a closed
bounded failure ledger. The receipt includes the existing profile/runtime
metrics plus all accounting operands required to recompute:

- ingress, delivered, processed, dropped, inference-failed, and privacy-checked
  frame counts;
- exact reconciliation equations;
- warmup and post-warmup duration;
- maximum stall gap, percentile gaps/latencies, FPS, backlog, and delivery
  failure count;
- watchdog phase results;
- worker, Job, pipe, media, FFmpeg, mutex, and buffer cleanup statuses;
- `audio_requested=false`, `network_authorized=false`,
  `network_transport_constructed=false`, and `raw_retained=false`;
- authority, grant, challenge, Job, policy, runtime, and model digests.

The failure ledger contains only a fixed stage enum, fixed failure-code enum,
bounded occurrence count, and precedence. It never contains exception text,
path, argv, device name, raw frame/image bytes, identity, or unrestricted
metadata.

### 8.2 Verified terminal evidence

The bridge accepts only a `VerifiedTerminalEvidence` constructed after closed
schema validation and semantic recomputation. It binds:

```text
receipt_bytes and receipt_digest
failure_ledger_bytes and failure_ledger_digest
consumed authority and revoked grant digests
challenge and Job digests
static/profile/watchdog/runtime/model digests
accounting/privacy/audio/network/raw-retention projections
worker/Job/native cleanup projection
retained preparation lease cleanup projection
```

TERMINAL persists the canonical redacted receipt and failure ledger, not only
opaque digests. Restart inspection recomputes their digests and semantic
projections before classifying TERMINAL. Extra fields, mismatched digests,
invalid accounting, unknown failures, privacy ambiguity, cleanup ambiguity, or
audio/network/raw-retention capability makes the record invalid and never a
pass.

## 9. Close-before-terminal ordering

Every post-consume path uses this order:

```text
stop/kill and drain worker descendants
close worker, Job, pipe, media, FFmpeg, mutex, and raw buffers
revoke capability and WorkerGrant
close and verify all retained A0/RP2/preparation leases
construct VerifiedTerminalEvidence with CLEAN retained-lease status
create, durably re-read, and semantically verify TERMINAL
release authority-store mutation guards
```

If retained preparation lease cleanup is uncertain, TERMINAL is not written.
Restart observes CONSUMED or REVOKED_TERMINAL_PENDING and is permanently
nonlaunchable. Metadata-only reconciliation cannot create a launchable or pass
TERMINAL.

Authority-store mutex/directory cleanup that occurs after terminal persistence
retains the existing durability reinspection rule. Any ambiguity is reported
as failure and cannot be interpreted as D1-N2 preflight pass.

## 10. Public controller boundary

The only operational calls remain parameter-free:

```python
prepare_d1_n2() -> D1N2EntrypointResult
run_d1_n2_preflight() -> D1N2EntrypointResult
```

There is no public key, envelope, path, digest, environment, retry, profile, or
device parameter. The production controller constructs only the fixed
unprovisioned bootstrap port until a separate provisioning task is accepted.

The controller state progression remains forward-only:

```text
UNINITIALIZED -> PREPARING -> PREPARED_WAITING_A1
              -> CONSUMED -> TERMINAL
```

Any abort, expiry, restart, malformed evidence, cleanup uncertainty, or state
drift becomes permanently nonlaunchable. Preparation never automatically calls
run. A1 remains an external review of the exact same-process PreparedAuthority.

## 11. Expected source and artifact surfaces

- `m2_d1_n2_prepare.py`: closed signed-envelope parsing port, approved triple,
  exact RP2 comparison, and retained A0/RP2 leases.
- `m2_d1_n2_canonical.py`: A0-bound PENDING/PREPARED, challenge-bound grant,
  expanded semantic TERMINAL, and restart verification.
- `m2_d1_n2_adapter.py`: single lease owner, transfer, idempotent abort, and
  close-before-terminal.
- `m2_d1_n2_native.py`: bridge-generated challenge, exact Job binding, closed
  receipt/failure ledger, and verified terminal evidence.
- `m2_d1_n2_entrypoint.py`: exception-safe ownership transfer, abort, and
  truthful fail-closed result verification.
- `m2_d1_n2_win32.py` / `m2_d1_n2_win32_store.py`: fixed A0 leaf and exact
  no-follow/create-new/lease operations only if existing primitives are
  insufficient.
- RP2 builder/candidate/schema and focused D1-N2 tests.
- governed authority/readiness/current-task documentation.

No implementation may modify the canonical proposal DOCX or access the D1-N1
authority store.

## 12. Discriminating acceptance evidence

Implementation must begin with tests that fail for the reviewed defects and
then pass only after the corresponding production change:

1. coordinated candidate+schema authority flips fail against a signed prior
   triple;
2. wrong key, signature, algorithm, key ID, scope, time, duplicate key, extra
   field, reparse/alias, replacement, or unprovisioned bootstrap fails before
   PENDING/native checks;
3. valid signed A0 creates exactly one A0-bound PENDING and cannot be reused;
4. raw protected values are absent from every persisted/returned record;
5. challenge entropy occurs before grant issuance and challenge/Job mutants
   fail before worker continuation;
6. every accounting, threshold, privacy, audio, network, raw-retention,
   watchdog, cleanup, receipt, ledger, grant, challenge, and Job mutant prevents
   TERMINAL acceptance;
7. retained-lease close failure writes no TERMINAL and restart remains
   nonlaunchable;
8. every pre-transfer `Exception` and `BaseException` closes all leases exactly
   once; repeated abort performs no retry;
9. public signatures remain parameter-free, imports/construction remain inert,
   prepare remains no-stream, and one-attempt/no-retry remains structural;
10. D1-N1 regressions remain unchanged;
11. RP2 write/check is deterministic and the proposal hash remains exact.

Production `prepare_d1_n2()` and `run_d1_n2_preflight()` must not be called by
implementation or verification. Fake/injected lifecycle and worker flows are
permitted only when they cannot enumerate or open a device.

## 13. Provisioning gate and residual limits

This design deliberately leaves production bootstrap state
`BOOTSTRAP_UNPROVISIONED`. A later separately authorized provisioning task must
select the real signing custodian, generate or import the offline private key,
freeze the public-key bootstrap, produce a signed bootstrap/package receipt,
and prove fixed-path offline verification on the target Windows environment.

That task may not expose the private key to this repository or agent context.
Until it completes and the remediated source passes a new independent I2
review, no fresh A0 envelope may be installed and no preparation may occur.

Source verification cannot prove OS-level network denial, physical camera
behavior, FFmpeg/MediaPipe behavior, participant safety, research validity,
portable packaging, deployment, release, or D1 GO.

## 14. Acceptance claim ceiling

After source implementation, fake-only tests, RP2 regeneration, and independent
review, the strongest possible claim before bootstrap provisioning is:

`D1_N2_SIGNED_A0_SOURCE_REMEDIATED_BOOTSTRAP_UNPROVISIONED_AUTHORITY_NOT_ISSUED`

Only a later provisioning receipt and fresh signed A0 for the exact new triple
can open the one parameter-free no-stream preparation call. A1 and physical
execution remain separate later gates.
