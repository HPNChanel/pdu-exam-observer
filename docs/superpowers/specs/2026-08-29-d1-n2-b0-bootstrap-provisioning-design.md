# D1-N2 B0 Bootstrap Provisioning Design

Date: `2026-08-29`

Design revision: `B0-R1`

Design status: `USER_APPROVED`

Authority ceiling: `AUTHORITY_NOT_ISSUED`

## 1. Outcome

Implement a source-only, Windows 11 x64 bootstrap-provisioning boundary for
the D1-N2 signed-A0 lifecycle. The source will be ready to consume one
externally approved, one-shot-installed P-256 public verification key without
creating a production signing identity, installing a real bootstrap, issuing
A0, invoking preparation, opening A1, or performing native or physical work.

This design is the next task after independent I2 review returned
`APPROVE_STATIC_PACK_ONLY` for the remediated signed-A0 source. That exact RP2
triple is non-authorizing and will become historical when B0 changes its bound
source inventory.

The B0 implementation must first reconcile the stale I2/A0 rows in
`docs/spec/M2_D1_N2_READINESS_PACK.md` with the current static-pack approval.
It must then generate and independently review a new exact RP2 triple.

## 2. Compact challenge contract

- Outcome: make the governed production entrypoint capable of verifying a
  separately provisioned A0 public key while retaining a hard fail-closed
  unprovisioned state.
- Falsifiable assumption: repository source, tests, generated RP2 artifacts,
  or the application entrypoint cannot create, select, replace, sign with, or
  silently fall back to a production authority key.
- Smallest refutation: an absent, partial, malformed, mismatched, or ambiguous
  bootstrap causes an A0 source read, RP2/native call, PENDING write, fallback
  key selection, or generated signing material.

## 3. Authority and non-goals

### 3.1 Allowed source work

B0 may add:

1. closed bootstrap and provisioning-receipt schemas;
2. a Windows fixed-leaf bootstrap reader;
3. a minimal BCrypt P-256 public-key verifier;
4. a one-shot installer implementation and separately gated operator script;
5. discriminating tests using test-only keys and temporary roots;
6. production composition that remains constructor-inert and lazy;
7. RP2 inventory and policy bindings for the new source and tests;
8. governance documentation for the new non-authorizing state.

### 3.2 Forbidden operational work

B0 may not:

- generate, import, store, export, or use a production private key;
- create or install a production bootstrap bundle or provisioning receipt;
- generate, sign, install, or consume a production A0 envelope;
- invoke `prepare_d1_n2()` or `run_d1_n2_preflight()`;
- enumerate or open a camera, start FFmpeg or MediaPipe, or launch a worker;
- open A1, authorize retry, collect participant data, use audio or network, or
  retain raw video;
- accept a key, path, provider, algorithm, digest, URL, command, or environment
  override through the governed application entrypoint;
- delete, repair, overwrite, refresh, rotate, or recover a bootstrap epoch.

Source implementation is not authority to run the operator installer. Actual
key creation, bootstrap installation, A0 issuance, preparation, A1, and
physical execution remain separate gates.

## 4. Trust domains

### 4.1 Repository domain

The repository contains parsers, verifiers, fixed Windows I/O, installer
source, production composition, tests, schemas, and deterministic RP2
construction. It contains no production credential, key material, raw
approval identifier, signature, bootstrap bundle, or provisioning receipt.

Test keys and test signatures must be unmistakably test-only, unreachable from
production composition, and bound into RP2 test evidence as non-authorizing
artifacts.

### 4.2 External private domain

An offline custodian environment owns the production signing identity and
private key. The private key never enters the target application repository,
target workstation, `.env`, browser input, documentation, test fixture, log,
receipt, RP2 candidate, or memory artifact.

The public-only P-256 key blob may leave this domain only as the payload of an
exact bootstrap bundle whose digest and key identifier are separately approved
by the user before installation.

### 4.3 Provisioned local domain

The fixed Windows authority directory remains:

```text
%LOCALAPPDATA%\PDUExamObserver\d1-n2-authority-v1
```

The bootstrap and receipt leaves are fixed as:

```text
a0-bootstrap.v1.json
a0-bootstrap-provisioning-receipt.v1.json
```

Installation may additionally use the fixed fail-closed staging leaf:

```text
a0-bootstrap.v1.partial
```

No caller-controlled path, current working directory, `PATH` search, registry
fallback, URL, removable-drive discovery, or alternate filename is permitted
inside the governed application. The separately gated installer may receive
canonical public input through its closed operator contract, but it always
writes only these resolved fixed leaves.

## 5. Bootstrap artifact contract

### 5.1 `BootstrapBundleV1`

The bootstrap is a signed, closed envelope encoded as canonical UTF-8 JSON
with sorted keys, compact separators, ASCII escaping, and no duplicate keys,
NaN, Infinity, insignificant whitespace, or trailing bytes. Its root has
exactly these fields:

```text
schema_version
domain
body
key_id
signature_algorithm
signature_b64url
```

Fixed root values are:

```text
schema_version = 1
domain = D1N2/A0_BOOTSTRAP/v1
signature_algorithm = ECDSA_P256_SHA256_IEEE_P1363
```

The closed `body` has exactly these fields:

```text
authority_revision
public_key_format
public_key_b64url
bootstrap_epoch_digest
```

Fixed body values are:

```text
authority_revision = d1-n2-authority-v1
public_key_format = BCRYPT_ECCPUBLIC_BLOB_P256
```

`public_key_b64url` is unpadded base64url of one exact public-only
`BCRYPT_ECCPUBLIC_BLOB` for ECDSA P-256. The decoded blob must have the expected
public P-256 magic, coordinate length, and total length. Private-key magic,
private components, an alternate curve, an alternate blob type, padding,
empty coordinates, or extra bytes are invalid.

`key_id` is lowercase SHA-256 of the exact decoded public-key blob.
`bootstrap_epoch_digest` is lowercase SHA-256 of the canonical fixed epoch
preimage defined by the implementation and bound into RP2. The signed bytes are
canonical UTF-8 JSON of the exact `body`. `signature_b64url` is unpadded
base64url of exactly 64 IEEE-P1363 bytes `r || s` produced by the corresponding
offline private key.

The bootstrap signature proves possession of the corresponding private key and
detects body mutation. It does not bootstrap its own authority. Trust comes
from the user's separate out-of-band approval of the exact whole-envelope
digest and `key_id`, followed by one-shot installation. A self-consistent but
unapproved key, bundle, signature, or receipt remains non-authorizing.

There is exactly one key and one algorithm in this authority epoch. There is no
runtime rotation, expiry, certificate lookup, or algorithm negotiation.

The bundle does not contain an RP2 digest. The fresh signed A0 envelope later
binds this independently provisioned key to one exact RP2 triple.

### 5.2 External approval of the bundle

Before provisioning, the user must separately authorize the exact tuple:

```text
authority_revision
bootstrap_bundle_sha256
key_id
bootstrap_epoch_digest
one_shot = true
overwrite = false
```

That authority is external to the repository and non-transitive. B0 source
implementation does not create or infer it.

## 6. Provisioning receipt contract

`ProvisioningReceiptV1` is closed canonical JSON. It is sanitized evidence of
the installation ceremony and is a runtime integrity prerequisite, but it is
not A0 authority and cannot substitute for signature verification.

The fixed ceremony revision is `d1-n2-b0-r1-provisioning-v1`; receipts from the
superseded pre-R1 order are not valid under this design.

The receipt records only:

- schema, domain, ceremony revision, result code, and integer timestamp;
- exact bundle digest, key ID, and bootstrap epoch digest;
- boolean `CREATE_NEW`, no-reparse, share-zero, write-flush, parent-durability,
  atomic no-replace promotion, and exact-readback outcomes;
- digests of the receipt-object and parent handle identities;
- cleanup status for every fallible resource closed before terminal receipt
  publication.

The fixed result enum is:

```text
INSTALLED
ALREADY_EXISTS
INVALID_INPUT
PLATFORM_UNSUPPORTED
WRITE_FAILED
DURABILITY_FAILED
READBACK_FAILED
CLEANUP_FAILED
```

The receipt contains no absolute path, username, machine name, raw public key,
private material, raw approval identifier, exception text, argv, unrestricted
metadata, device identity, or participant information.

Both the installed bundle and its matching receipt must pass fixed-leaf,
identity, canonical-byte, self-signature, and cross-digest checks before the
bootstrap can be used. A receipt alone grants nothing.

`leaf_identity_digest` binds the receipt object created under the fixed partial
leaf and later renamed to the fixed final receipt leaf. It does not bind the
bundle identity. The installer captures this identity before writing the
provisional receipt, and runtime compares it with the final receipt handle.

`cleanup_clean=true` is valid only after every fallible installer resource
except the terminal publisher has closed successfully. The terminal publisher
owns no handle and exposes no cleanup method, so receipt publication does not
self-attest cleanup that remains capable of failing.

## 7. Components and isolation

### 7.1 `m2_d1_n2_bootstrap.py`

This module owns closed value types, canonical parsing, bundle/receipt semantic
validation, digest calculation, state classification, and the production
bootstrap port. It contains no Windows path discovery, private-key operation,
installer entrypoint, or native preparation code. It treats a valid bootstrap
self-signature as integrity and proof-of-possession evidence only, never as
self-issued authority.

### 7.2 `m2_d1_n2_bootstrap_win32.py`

This module owns fixed known-folder resolution and Windows handle-backed reads
for the installed bundle, receipt, and A0 approval. It uses exact leaf names,
`OPEN_EXISTING`, `FILE_FLAG_OPEN_REPARSE_POINT`, share zero, post-open file
information, exact final-path comparison, disk-file and non-reparse checks,
stable file identity, bounded exact reads, and nested `finally` cleanup.

Every inspection open returns one tagged result: `OPENED`, `ABSENT`, or
`AMBIGUOUS`. Only the exact Windows not-found cases are `ABSENT`; sharing,
access, platform, or other open uncertainty is `AMBIGUOUS` and poisons the
bootstrap state. A bare nullable handle is not an allowed production boundary.
Every `CREATE_NEW` likewise returns `CREATED`, `EXISTS`, or `AMBIGUOUS`; only
the exact Windows conflict errors become `EXISTS`.

Unsupported platforms fail closed. No POSIX-equivalence claim is made.

### 7.3 `m2_d1_n2_cng.py`

This module exposes only P-256 public-key import and IEEE-P1363 signature
verification for bootstrap and A0 envelopes. It uses BCrypt with the exact
decoded public blob and closes all algorithm and key handles on every path. It
has no key-generation, signing, private-key import, persisted-key, certificate,
network, provider-selection, or fallback API.

The design uses a file-backed public bundle plus ephemeral BCrypt import.
Microsoft's CNG documentation states that public keys are not persisted by the
KSP public-key workflow; this avoids falsely relying on a persistent public-only
CNG container.

Primary references:

- <https://learn.microsoft.com/en-us/windows/win32/seccng/key-import-and-export>
- <https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptimportkeypair>
- <https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptverifysignature>

### 7.4 `m2_d1_n2_bootstrap_install.py`

This module owns the one-shot installation state machine. It validates the
canonical bundle, self-signature, and exact externally approved tuple before
any fixed-root write. Under the fixed authority mutex and retained parent it
requires bundle, receipt, and partial leaves all to be unambiguously absent. It
then:

1. creates the partial leaf with `CREATE_NEW`, writes/flushes/readbacks the
   exact bundle, closes it cleanly, and promotes it no-replace/write-through to
   the final bundle leaf;
2. reopens and verifies the final bundle, then recreates the now-free partial
   leaf with `CREATE_NEW` as the receipt candidate;
3. captures the receipt-candidate identity, writes provisional canonical
   `INSTALLED` bytes with `cleanup_clean=true`, and flushes/readbacks them;
4. closes the receipt writer/verifier, final-bundle verifier, BCrypt resources,
   durability handles, retained parent, and mutation mutex; every close must
   succeed;
5. only after clean closure, constructs a private `ClosedReceiptCandidate`
   token containing the fixed source, fixed destination, and bounded receipt;
6. only with that token, calls exactly one terminal
   `publish_fixed_receipt_no_replace_write_through()` operation that performs a
   same-directory partial-to-final-receipt rename without replace, copy,
   fallback, or retry.

The Windows terminal primitive is `MoveFileExW` with `MOVEFILE_WRITE_THROUGH`
and without `MOVEFILE_REPLACE_EXISTING` or `MOVEFILE_COPY_ALLOWED`. It owns no
handle and has no cleanup method. After it succeeds, the installer performs no
authority-affecting filesystem, cryptographic, durability, or lifecycle work;
it may only return its already-bounded in-memory result.

Any uncertainty leaves the epoch fail closed. A failure before terminal receipt
publication leaves the partial receipt candidate or an asymmetric state;
runtime rejects it. Failure results, including `CLEANUP_FAILED`, are in-memory
only and are never promoted as final receipts. The installer never deletes a
partial or final artifact and never retries, repairs, refreshes, overwrites, or
rotates.

### 7.5 Operator script

`scripts/provision_m2_d1_n2_bootstrap.py` is a separately gated operator
entrypoint. It is not imported by the application, not called by tests or RP2
verification, and not authorized to run merely because its source exists. Its
contract accepts only the closed bundle bytes and exact externally authorized
digest tuple; all destination paths remain fixed internally.

### 7.6 Production composition

`D1N2PreparedProductionFactory` remains parameterless, constructor-inert, and
lazy. On its one governed prepare invocation it constructs only the fixed
bootstrap reader, fixed A0 approval source, fixed RP2 verifier, and existing
preparation composition. No browser, caller, environment, configuration file,
or alternate entrypoint can inject a key, verifier, path, provider, or
algorithm.

The installer module and script are not reachable from this factory.

## 8. Installation state machine

The closed states are:

```text
ABSENT
INSTALLING
INSTALLED
POISONED
```

`ABSENT` requires bundle, receipt, and partial leaves all to be absent. Runtime
classification is `BOOTSTRAP_UNPROVISIONED` and must not open A0.

`INSTALLING` is observable only within the separately authorized one-shot
installer while it owns the fixed authority mutex and directory handles. A
crash or ambiguous failure leaves a partial or incomplete final state and is
classified as `POISONED` on the next inspection.

`INSTALLED` requires both final bundle and receipt to be present and mutually
consistent, canonical, stable, durable, non-reparse, and exact-path bound.

`POISONED` includes any partial leaf, missing pair member, existing conflict,
malformed artifact, cross-digest mismatch, identity drift, unsupported file
kind, tagged-open ambiguity, durability uncertainty, or cleanup uncertainty.

There is no state transition from `INSTALLED` or `POISONED` back to `ABSENT`.
An already existing artifact yields `ALREADY_EXISTS` even when its bytes match.
Recovery or epoch rotation requires a new design, review, and explicit
authority.

## 9. Runtime verification order

The production prepare path must execute in this order:

1. inspect bootstrap state without opening the A0 approval leaf;
2. return `BOOTSTRAP_UNPROVISIONED` only for a clean `ABSENT` state;
3. return `REJECTED` for `POISONED`, malformed, unsupported, or ambiguous state;
4. retain validated bundle and receipt leases;
5. import the exact public blob into BCrypt, recheck its key ID, and verify the
   bootstrap self-signature as integrity and proof-of-possession evidence;
6. open the fixed `a0-approval.v1.json` leaf with a retained share-zero lease;
7. validate the closed A0 envelope, exact 900-second interval, scope, time, and
   IEEE-P1363 signature;
8. verify exact candidate bytes, canonical schema bytes, canonical static
   bindings, artifact inventory, policy preimages, and authority denials
   against the signed RP2 triple;
9. only then create the sticky A0-bound PENDING record;
10. retain bootstrap, receipt, A0, and RP2/preparation ownership through the
    existing explicit transfer and cleanup boundaries.

No bootstrap or receipt condition can be reclassified as clean unprovisioned
after any suspicious artifact is observed. There is no test-key, alternate
provider, alternate file, network, certificate, or user-input fallback.

Any retained bootstrap, receipt, BCrypt, or A0 cleanup failure suppresses
PREPARED and remains nonlaunchable. No TERMINAL or success receipt may hide a
prior bootstrap cleanup ambiguity.

## 10. Failure and crash behavior

- Missing bundle, receipt, and partial together: `BOOTSTRAP_UNPROVISIONED`.
- Any partial or asymmetric pair: `REJECTED`.
- Invalid canonical bytes, key blob, key ID, epoch digest, receipt, identity,
  final path, durability, or readback: `REJECTED`.
- Unsupported OS or unavailable BCrypt primitive: `REJECTED` with internal
  `PLATFORM_UNSUPPORTED` evidence.
- Valid bootstrap but missing or malformed A0: A0 `INVALID`.
- Future-issued or wrong-interval A0: A0 `INVALID`.
- Expired A0: A0 `EXPIRED`.
- Valid A0 but RP2 mismatch: sticky PENDING and permanent nonlaunchable failure,
  as already defined by the signed-A0 lifecycle.
- Any exception or `BaseException` after handle ownership begins: close each
  owned handle exactly once, preserve primary versus cleanup failure, and
  classify ambiguity fail closed.
- Any receipt-writer/verifier, bundle-verifier, BCrypt, parent, durability, or
  mutex cleanup failure: terminal publisher call count is zero, the final
  receipt remains absent, and the partial leaf remains as poison evidence.
- Terminal publisher failure: no retry or fallback; the partial leaf remains
  and runtime rejects the asymmetric/partial state.

The implementation may not automatically remove a failed staging leaf or an
incomplete receipt. Permanent fail-closed poisoning is preferable to a hidden
second provisioning attempt.

## 11. Verification strategy

### 11.1 Closed-schema tests

Tests reject missing, extra, duplicated, noncanonical, padded-base64url,
wrong-domain, wrong-algorithm, wrong-key-format, private-key, wrong-curve,
wrong-magic, wrong-length, key-ID-mismatch, malformed-signature, and
self-signature-mismatch inputs. They also prove that a self-consistent but
externally unapproved bootstrap tuple cannot be installed.

### 11.2 State and I/O tests

Tests distinguish clean absence from every partial/asymmetric/poisoned state.
They inject open, identity, read, write, flush, promotion, durability, readback,
and close faults. An existing identical bundle still rejects a second install.
Real Windows temporary-root tests prove no-follow/share-zero behavior where the
primitive can be observed without touching the production root.

### 11.3 BCrypt tests

On Windows, a real BCrypt test verifies test-only bootstrap and A0 P-256
vectors. Mutating either body, signature, public blob, or key ID fails.
Static/public-boundary tests prove the production CNG module exposes no
generation, signing, private import, persisted-key, certificate, or
provider-selection API.

### 11.4 Installer tests

Tests cover validation before write, `CREATE_NEW`, exact staging write and
flush, no-replace bundle promotion, final bundle readback, receipt-object
identity binding, tagged opens, pre-publication mutex/handle cleanup, the one
terminal receipt publication call, and crash/fault injection at every ownership
boundary. A writer-close failure must prove publisher call count zero, final
receipt absence, and retained partial poison. Tests do not call the production
operator script or write the production authority root.

### 11.5 Production-composition tests

Imports and constructors perform no I/O. Clean bootstrap absence opens no A0,
RP2, preparation, or native resource and creates no PENDING. Invalid bootstrap
or A0 also reaches none of those resources. Test-only injected valid artifacts
may prove the order through the no-stream boundary, but production
`prepare_d1_n2()` and `run_d1_n2_preflight()` remain uncalled.

### 11.6 Final gates

The exact implementation revision requires:

1. focused bootstrap, CNG, installer, and production-composition tests;
2. all D1-N2 tests;
3. the D1-N1 native regression suite;
4. scoped Ruff and strict mypy;
5. deterministic RP2 `--write` and `--check`;
6. canonical proposal SHA-256 preservation;
7. repository scan for production private keys, credentials, signatures, and
   accidentally generated bootstrap/A0 artifacts;
8. fresh independent trust-boundary review of the exact new RP2 triple.

No verification command may invoke either production operational wrapper or
the production operator installer.

## 12. Governance and RP2 impact

The B0 implementation updates the RP2 inventory for every new source and
discriminating test artifact and adds explicit immutable policy preimages for:

- bootstrap bundle canonicalization and key-ID derivation;
- provisioning receipt projection;
- Windows fixed-leaf/read/identity/durability behavior;
- one-shot installation and poisoned-state semantics;
- BCrypt public-only verification;
- production composition and no-fallback behavior.

Any B0 source, test, schema, policy, lock, or formatting change creates a new
RP2 triple. The current triple cannot authorize the B0 revision. The new triple
remains unsigned and non-authorizing until independent review and fresh A0.

`docs/spec/M2_D1_N2_READINESS_PACK.md`, `docs/ai/CURRENT_TASK.md`, and
`docs/ai/TASK_CONTRACT.md` must distinguish historical rejected snapshots,
the current static-pack approval, B0 source evidence, actual bootstrap
provisioning, A0 issuance, preparation, A1, and physical execution.

## 13. Acceptance and subsequent gates

The maximum claim immediately after source implementation and local gates is:

```text
B0_SOURCE_IMPLEMENTED_LOCALLY_VERIFIED
BOOTSTRAP_UNPROVISIONED
AUTHORITY_NOT_ISSUED
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
```

If fresh independent review accepts the exact new static pack, the maximum
claim becomes `APPROVE_STATIC_PACK_ONLY`; it still supplies no bootstrap or A0
authority.

Subsequent gates are separate and non-transitive:

```text
B0.1  Source implementation and local verification
B0.2  Independent review and freeze of the exact new RP2 triple
B0.3  Authority to create the production signing identity and bundle
B0.4  Authority to install one exact bundle digest and key ID once
B0.5  Authority to issue one fresh signed A0 for the exact new RP2 triple
A0-P  Parameter-free no-stream preparation
A1    Independent PreparedAuthority review
X0    One physical preflight only after A1
```

## 14. Residual risks

- Source tests do not prove clean-machine BCrypt or installer behavior.
- This governed workflow does not prevent the same Windows account from
  replacing the entire application or authority root outside the application.
- Closing the parent lease and mutation mutex before the pathname-based terminal
  rename leaves a narrow same-account path-substitution risk. B0-R1 accepts this
  within the existing exclusion of malicious same-account whole-root
  replacement; strengthening it requires a separately reviewed external
  finalizer boundary.
- There is no bootstrap recovery or rotation in this epoch; loss or poisoning
  requires a new reviewed design and authority.
- A green static review does not prove signer custody, provisioning, A0,
  PreparedAuthority, camera, FFmpeg, MediaPipe, two-monitor behavior, device
  acceptance, participant access, model performance, or research validity.
- The operator script is sensitive local tooling. Its existence in source is
  not permission to run it and its output must remain local and sanitized.

## 15. Routing receipt

```text
schema_version = 1
work = D1-N2-B0 bootstrap provisioning design
route = Sol
effort = xhigh
decision_owner = root
result = B0_R1_USER_APPROVED
```

No route or design approval grants provisioning, A0, preparation, native, or
physical authority.
