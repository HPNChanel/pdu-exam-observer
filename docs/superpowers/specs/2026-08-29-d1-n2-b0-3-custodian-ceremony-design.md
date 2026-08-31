# D1-N2 B0.3 Custodian Ceremony Design

Date: `2026-08-29`

Design status: `USER_APPROVED`

Operational status: `CUSTODIAN_UNAVAILABLE_EXECUTION_AUTHORITY_NOT_ISSUED`

## 1. Outcome and ceiling

This design prepares a credential-free, fail-closed PowerShell ceremony kit
outside the repository. A future separately authorized custodian ceremony may
use the kit to create exactly one production ECDSA P-256 signing identity and
one public `BootstrapBundleV1`.

The current approved work may write this design, its implementation plan, an
inert kit, hashes, and static/safe-mode evidence. It may not create a key,
bundle, signature, execution-authority file, provisioning receipt, signed A0,
or invoke B0.4, A0-P, A1, X0, native discovery, FFmpeg, MediaPipe, or camera.

The live ceiling remains:

```text
authority_status=AUTHORITY_NOT_ISSUED
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
```

## 2. Exact frozen inputs

```text
authority_revision=d1-n2-authority-v1
bootstrap_epoch_digest=736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b
static_bindings_digest=5645963129cb0dcd70538a18c35ed0a569111ad907975333a17d664bc62d5979
binding_schema_canonical_sha256=07ebbffaa9e0f9c2fa5b44dc9d2fab24ac82e324a118618acea7c830c5dd15cb
candidate_exact_bytes_sha256=cd7d6c8b1ec688afaddab638d1a09cb1da41d733e604bbc7363ec714aad99acb
key_name=PDUExamObserver.D1N2.A0Signing.v1
key_storage_provider=Microsoft Software Key Storage Provider
key_storage_scope=CURRENT_USER
key_algorithm=ECDSA_P256
public_key_format=BCRYPT_ECCPUBLIC_BLOB_P256
signature_algorithm=ECDSA_P256_SHA256_IEEE_P1363
```

Changing any value requires a new design, a new exact kit, and a new review.

## 3. Trust domains and artifact topology

The repository contains only this design, its plan, governance, public parsers,
public verifiers, and the already approved RP2-bound implementation. It gains no
private-key operation, production credential, operational authority, bundle, or
signature.

The inert kit is created with create-new semantics outside the checkout at:

```text
D:\FOR_RESEARCH\SCIENTIFIC_RESEARCH\pdu-exam-observer-custodian-kit\b0-r2\
```

Before any write, the resolved kit root must be proven outside the resolved
checkout. A pre-existing kit root is a stop condition; no file is overwritten.

The kit contains only:

```text
b0_3_create_bootstrap.ps1
B0_3_CUSTODIAN_RUNBOOK.md
b0-3-kit-manifest.v1.json
b0-3-kit-validation.v1.json
```

The manifest binds the script and runbook by relative path, exact byte count,
and lowercase SHA-256. It does not bind itself. The validation receipt binds the
manifest digest and safe-mode results, and always states that no credential or
execution authority exists.

A future private domain must be a dedicated physical Windows 11 x64 machine
that is not the preflight workstation, uses a dedicated standard-user account,
is offline, and has no cloud sync or private-key backup. A VM, snapshot, clone,
same-machine account, exportable key, alternate provider, or alternate path
requires a revised design.

## 4. PowerShell interface

The kit uses the inbox `powershell.exe` and embedded C# P/Invoke. It has no
Python, PowerShell-module, .NET SDK, network, certificate-store, or compiler
dependency beyond `Add-Type` available to Windows PowerShell.

```powershell
b0_3_create_bootstrap.ps1 -Mode ValidateOnly
b0_3_create_bootstrap.ps1 -Mode Execute
```

`ValidateOnly` is the default. It performs only pure contract self-tests and
must not open a key-storage provider, call any NCrypt function, write an intent,
or create operational output.

`Execute` accepts no operator-selected key, provider, algorithm, path, digest,
URL, command, or output leaf. It reads a closed execution-authority artifact
from a fixed future custodian root under Known Folder LocalAppData. It must not
change or bypass the host execution policy.

## 5. `B0_3ExecutionAuthorityV1`

The future authority is closed canonical UTF-8 JSON with sorted keys, compact
separators, ASCII escaping, no BOM, duplicate keys, NaN, insignificant
whitespace, or trailing bytes. It has exactly these fields:

```text
schema_version
domain
authority_granted
ceremony_revision
authority_revision
bootstrap_epoch_digest
static_bindings_digest
binding_schema_canonical_sha256
candidate_exact_bytes_sha256
tool_sha256
kit_manifest_sha256
custodian_class
key_name
key_storage_provider
key_storage_scope
one_shot
retry
overwrite
private_key_export_authorized
private_key_backup_authorized
target_workstation
```

Required values are:

```text
schema_version=1
domain=D1N2/B0_3_EXECUTION_AUTHORITY/v1
authority_granted=true
ceremony_revision=d1-n2-b0-r2-custodian-v1
custodian_class=DEDICATED_NON_TARGET_WINDOWS_11_X64_STANDARD_USER_OFFLINE
key_storage_scope=CURRENT_USER
one_shot=true
retry=false
overwrite=false
private_key_export_authorized=false
private_key_backup_authorized=false
target_workstation=false
```

Every exact binding in section 2 and the newly computed tool/manifest digests
must match. The file may be materialized only after a fresh user authorization
names the complete tuple. Its parser is a mechanical interlock, not proof that
the user granted authority.

No execution-authority file exists during inert-kit preparation.

## 6. Future exact-once ceremony

`Execute` is permitted only after a future authority gate and performs this
fixed order:

1. Verify Windows 11 x64, non-elevated process, standard-user attestation,
   non-target custodian attestation, fixed non-reparse root, and zero `Up`
   non-loopback adapters.
2. Verify the script self-hash, kit manifest, exact authority, RP2 triple, epoch,
   provider, scope, and denials.
3. Reject any existing intent, partial, bundle, receipt, or exact named key.
4. Write and flush `b0-3-attempt-intent.v1.json` with create-new semantics.
   Reaching this publication consumes the one-shot authority.
5. Open Microsoft Software KSP and call `NCryptCreatePersistedKey` with
   `ECDSA_P256`, the fixed key name, legacy spec `0`, and flags `0`.
6. Set persisted `NCRYPT_EXPORT_POLICY_PROPERTY=0`, finalize the key, and read
   the policy back as exactly zero.
7. Attempt one private ECC blob export as a negative probe. Continue only when
   it is denied and returns no private bytes.
8. Export the public ECC blob and require 72 bytes, public P-256 magic,
   coordinate size 32, and `key_id=sha256(public_blob)`.
9. Construct the exact existing canonical bootstrap body, hash it with SHA-256,
   and sign with `NCryptSignHash`; require exactly 64 IEEE-P1363 bytes.
10. Import the public blob through a new BCrypt public handle and verify the
    signature independently.
11. Close every key/provider/public handle before publishing output.
12. Write, flush, read back, and close fixed bundle/receipt partial leaves;
    publish the bundle and then the receipt through no-replace/write-through
    renames. No authority-affecting work occurs after receipt publication.
13. Emit one sanitized JSON result and stop before B0.4.

The tool must never call `NCryptDeleteKey`, use
`NCRYPT_OVERWRITE_KEY_FLAG`/`NCRYPT_MACHINE_KEY_FLAG`, or expose a private blob.

## 7. Failure contract

Allowed failure codes are:

```text
AUTHORITY_ABSENT
AUTHORITY_REJECTED
HOST_REJECTED
PREEXISTING_STATE
INTENT_WRITE_FAILED
KEY_CREATE_FAILED
KEY_POLICY_FAILED
PRIVATE_EXPORT_NOT_DENIED
PUBLIC_EXPORT_FAILED
SIGN_FAILED
PUBLIC_VERIFY_FAILED
BUNDLE_WRITE_FAILED
RECEIPT_WRITE_FAILED
CLEANUP_FAILED
UNEXPECTED_FAILURE
```

Failure after intent or key creation preserves all evidence, does not delete or
repair anything, and cannot retry. A partial ceremony requires a new reviewed
epoch/design. Stdout, receipts, and review artifacts may contain no exception
text, username, SID, key-container path, adapter identity, private material,
operator identity, or unrestricted machine state.

`UNEXPECTED_FAILURE` is the only sanitized fallback for an unclassified local
fault. It must not downgrade an already accepted or consumed B0.3 execution
authority to `REJECTED`; `CLEANUP_FAILED` still takes precedence when cleanup
itself is not proven clean.

## 8. Receipt and B0.4 handoff

The success receipt is closed canonical JSON and binds the intent, execution
authority, tool and manifest digests, exact fixed policy, key ID, bundle digest
and byte count, public-only validation, export-policy check, private-export
denial, create-new/no-overwrite behavior, zero-network observation, clean
closure, and these negative claims:

```text
a0_issued=false
bootstrap_installed=false
physical_camera_access_authorized=false
```

Only the public bundle, sanitized receipt, `key_id`, bundle SHA-256, and epoch
digest may leave the custodian domain. B0.3 stops for a separate B0.4 authority
naming exactly:

```text
authority_revision
bootstrap_bundle_sha256
key_id
bootstrap_epoch_digest
one_shot=true
overwrite=false
```

## 9. Acceptance

The current implementation may claim at most:

```text
B0_3_INERT_KIT_STATIC_VERIFIED
CUSTODIAN_UNAVAILABLE
EXECUTION_AUTHORITY_NOT_ISSUED
BOOTSTRAP_UNPROVISIONED
```

Acceptance requires PowerShell AST parsing, safe-mode self-tests, authority
negative cases, forbidden-primitive scanning, exact manifest recomputation,
secret/artifact scanning, proposal-hash verification, unchanged RP2 `--check`,
the focused RP2 artifact test, and independent Sol/xhigh trust-boundary review.

The review verdict ceiling is `APPROVE_INERT_KIT_ONLY`. It proves no custodian,
key custody, operational ceremony, bootstrap installation, A0, preparation,
camera, participant, model, research, release, or deployment behavior.
