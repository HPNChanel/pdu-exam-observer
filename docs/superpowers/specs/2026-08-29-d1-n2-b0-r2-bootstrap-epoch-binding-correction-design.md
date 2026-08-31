# D1-N2 B0-R2 Bootstrap Epoch Binding Correction Design

Date: `2026-08-29`

Status: `SPEC_APPROVED_IMPLEMENTED_STATIC_PACK_APPROVED`

Authority ceiling: `AUTHORITY_NOT_ISSUED`

Base design:
`docs/superpowers/specs/2026-08-29-d1-n2-b0-bootstrap-provisioning-design.md`

## 1. Decision and scope

`USER_STATED`: the user approved correction direction A and the detailed
correction design on `2026-08-29`.

This document corrects one trust-boundary mismatch discovered while preparing
the B0.3 production-signing-identity specification. The base B0-R1 design says
that `bootstrap_epoch_digest` is the SHA-256 of a fixed canonical epoch
preimage defined by implementation and bound into RP2. The current source only
requires a lowercase SHA-256-shaped value and compares the externally supplied
installation tuple with the bundle. It does not require one exact epoch value,
and the current RP2 has no explicit exact epoch preimage binding.

The correction introduces one immutable epoch-policy preimage, derives one
exact digest from its canonical bytes, enforces that digest at every closed
bootstrap boundary, binds the preimage and digest into RP2, and obtains a fresh
independent static review before B0.3 resumes.

This is a source-only correction. It does not authorize or perform key
generation, private-key access, bundle signing, bootstrap installation, A0
issuance, preparation, native work, camera work, retry, or participant
collection.

## 2. Falsifiable challenge contract

Outcome: every bootstrap bundle, installation authority, and provisioning
receipt accepted by production must carry the one implementation-defined epoch
digest that is explicitly represented in the reviewed RP2.

Key falsifiable assumption: all acceptance paths for
`bootstrap_epoch_digest` converge on the same immutable constant rather than
accepting any syntactically valid digest.

Smallest refuting check: substitute a different lowercase 64-hex digest into an
otherwise valid object at each of the bundle parser, installation-authority,
and provisioning-receipt boundaries. Acceptance at any boundary refutes the
correction.

## 3. Root cause and evidence state

`OBSERVED`: `parse_bootstrap_bundle()` currently validates
`bootstrap_epoch_digest` with `_is_digest()` only.

`OBSERVED`: `BootstrapInstallAuthority.valid_for()` currently requires the
authority tuple and parsed bundle to agree with each other but does not require
either value to equal an implementation constant.

`OBSERVED`: `ProvisioningReceiptV1.valid()` currently requires a syntactically
valid digest but not the exact epoch digest.

`OBSERVED`: a read-only probe constructed two canonical bundles that differed
only by the lowercase SHA-256-shaped epoch value; the parser accepted both.

`OBSERVED`: the current RP2 bootstrap policy projection describes algorithm,
authority revision, key-ID derivation, and prohibition of a private-key API,
but it contains no canonical epoch preimage or exact epoch digest.

`REFUTED`: the pre-correction implementation does not satisfy the base design's
claim that the epoch preimage is implementation-defined and RP2-bound.

Root cause: the epoch value was modeled as an externally supplied opaque digest
through the bundle, approval tuple, and receipt contracts. Shape validation and
cross-object equality were implemented, but the immutable source of the epoch
value was omitted.

## 4. Exact epoch-policy preimage

### 4.1 Canonicalization

The epoch-policy preimage is canonical UTF-8 JSON using the same repository
canonicalization profile as the bootstrap contract:

- keys sorted lexicographically;
- compact separators `,` and `:`;
- ASCII escaping enabled;
- NaN and Infinity prohibited;
- no byte-order mark, whitespace, newline, or trailing byte.

### 4.2 Closed fields and values

The preimage contains exactly these 15 fields and values:

```json
{
  "authority_revision": "d1-n2-authority-v1",
  "bootstrap_bundle_creation": "ONE_SHOT_CREATE_NEW",
  "custody_profile": "WINDOWS_CNG_USER_NONEXPORTABLE_OFFLINE_V1",
  "domain": "D1N2/A0_BOOTSTRAP_EPOCH/v1",
  "key_algorithm": "ECDSA_P256",
  "key_creation": "CREATE_ONLY",
  "key_export_policy": "NONE",
  "key_name": "PDUExamObserver.D1N2.A0Signing.v1",
  "key_storage_provider": "Microsoft Software Key Storage Provider",
  "key_storage_scope": "CURRENT_USER",
  "private_key_backup": "PROHIBITED",
  "public_key_format": "BCRYPT_ECCPUBLIC_BLOB_P256",
  "schema_version": 1,
  "signature_algorithm": "ECDSA_P256_SHA256_IEEE_P1363",
  "target_workstation_private_key": "PROHIBITED"
}
```

The exact 626 canonical bytes are:

```text
{"authority_revision":"d1-n2-authority-v1","bootstrap_bundle_creation":"ONE_SHOT_CREATE_NEW","custody_profile":"WINDOWS_CNG_USER_NONEXPORTABLE_OFFLINE_V1","domain":"D1N2/A0_BOOTSTRAP_EPOCH/v1","key_algorithm":"ECDSA_P256","key_creation":"CREATE_ONLY","key_export_policy":"NONE","key_name":"PDUExamObserver.D1N2.A0Signing.v1","key_storage_provider":"Microsoft Software Key Storage Provider","key_storage_scope":"CURRENT_USER","private_key_backup":"PROHIBITED","public_key_format":"BCRYPT_ECCPUBLIC_BLOB_P256","schema_version":1,"signature_algorithm":"ECDSA_P256_SHA256_IEEE_P1363","target_workstation_private_key":"PROHIBITED"}
```

The SHA-256 of those exact bytes is:

```text
736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b
```

### 4.3 Meaning and limits

The epoch-policy digest binds the reviewed custody and signature policy to the
bootstrap artifact contract. It is not proof that the external custodian
actually used the named provider, kept the machine offline, prevented export,
or avoided a backup. Those claims require separate B0.3 ceremony evidence and
remain `UNVERIFIED` until that ceremony occurs.

The preimage deliberately contains neither a production `key_id` nor an RP2
digest. The key does not exist during source freeze, and the same frozen signing
identity must later be able to sign one separately approved A0 envelope for the
then-current exact RP2 triple. Omitting both values prevents a construction
cycle and does not grant authority to an arbitrary key or RP2.

## 5. Source enforcement

### 5.1 Bootstrap contract

`src/pdu_exam_observer/m2_d1_n2_bootstrap.py` will expose immutable public
constants for:

- the closed epoch-policy preimage;
- its exact canonical bytes;
- `BOOTSTRAP_EPOCH_DIGEST`.

The structured preimage must be represented by immutable data, such as a
closed tuple of key/value pairs, or reconstructed from the canonical bytes. A
mutable dictionary must not be exported as the authority source.

Import-time construction must remain deterministic, side-effect free, and free
of filesystem, CNG, network, clock, or environment access. A source assertion
or equivalent deterministic invariant must prove that hashing the canonical
preimage produces the declared digest.

`parse_bootstrap_bundle()` must reject a body unless
`bootstrap_epoch_digest == BOOTSTRAP_EPOCH_DIGEST`. Shape validation alone is
insufficient.

### 5.2 Installation authority

`BootstrapInstallAuthority.valid_for()` must require both:

```text
self.bootstrap_epoch_digest == BOOTSTRAP_EPOCH_DIGEST
bundle.bootstrap_epoch_digest == BOOTSTRAP_EPOCH_DIGEST
```

The existing equality between the authority tuple and bundle remains. The
operator parser must reject a well-formed alternate digest before creating a
valid installation authority object.

### 5.3 Provisioning receipt

`ProvisioningReceiptV1.valid()` must require
`bootstrap_epoch_digest == BOOTSTRAP_EPOCH_DIGEST`. A canonical receipt with a
different 64-hex digest is invalid even if its bundle digest and key ID are
well-formed.

The installer continues to copy the digest from the already validated parsed
bundle; it receives no new caller-controlled epoch source.

### 5.4 Runtime and public-only CNG boundary

The fixed Windows reader continues reconstructing its internal authority from
the receipt and re-verifying the bundle. Exact epoch enforcement therefore
applies before a bootstrap can become runtime-acceptable.

`src/pdu_exam_observer/m2_d1_n2_cng.py` remains verification-only. The
correction must not add generation, signing, persisted-key, private import,
certificate, provider selection, alternate algorithm, or fallback APIs to the
production module.

## 6. Discriminating tests

Tests must be written red before source remediation and must cover at least:

1. the preimage canonical bytes are exactly 626 bytes and hash to the declared
   digest;
2. a canonical bundle carrying `BOOTSTRAP_EPOCH_DIGEST` parses successfully;
3. an otherwise valid canonical bundle carrying another lowercase 64-hex
   digest is rejected;
4. a matching bundle and installation-authority tuple that share the same
   alternate digest are rejected;
5. `parse_operator_authority()` rejects the alternate digest;
6. a canonical provisioning receipt carrying the alternate digest is rejected;
7. receipt creation from a valid exact bundle retains the exact digest;
8. production CNG static/public-boundary tests continue proving that no private
   or signing capability is exposed;
9. production constructors and imports remain I/O-free and do not invoke the
   operator installer or either operational wrapper.

Tests may use test-only public/private vectors already isolated from production
composition. They may not generate or store a production key, write the
production authority root, invoke `scripts/provision_m2_d1_n2_bootstrap.py`,
call `prepare_d1_n2()`, or call `run_d1_n2_preflight()`.

## 7. RP2 correction

`scripts/build_m2_d1_n2_rp2.py` must add a closed policy projection dedicated
to the epoch binding. The projection includes:

```text
projection = d1-n2.b0-r2-bootstrap-epoch
source_id = SRC_M2_D1_N2_BOOTSTRAP_PY
canonicalization = json-v1-sort-keys-compact-utf8
epoch_preimage = exact closed object from section 4.2
bootstrap_epoch_digest = 736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b
version = 1
```

The builder must derive the policy projection from immutable source constants,
not duplicate an independently editable digest string. Deterministic `--write`
and `--check` must agree.

Every changed source, test, builder, schema, policy, or formatting byte produces
a new RP2 triple. The currently approved B0-R1 triple:

```text
static_bindings_digest = c439c12983fcd05675c5a13fba1db0199064a5df0632b94e7c7a61b42046bacc
binding_schema_canonical_sha256 = da3b35674a922c830503ffece9e5e070c4ab02279fc51a4a9c24ee96a26fa558
candidate_exact_bytes_sha256 = 13a995221dbbd327e5e9984967f8bcf2f74b8d3016ff523372dc8eb9735d0df7
```

becomes historical and non-reusable after the first correction byte changes.
The replacement triple remains unsigned and non-authorizing until a fresh
independent trust-boundary review returns `APPROVE_STATIC_PACK_ONLY` for those
exact bytes.

## 8. Verification gates

The correction requires:

1. focused bootstrap, installer, CNG, and production-composition tests;
2. all D1-N2 tests;
3. the D1-N1 native regression suite;
4. scoped Ruff and strict mypy;
5. deterministic RP2 `--write` followed by `--check`;
6. exact source-proposal SHA-256 preservation:
   `2CD5F6FDB17D70FD5593E50B8387BC38DABF70430DFFFECDBE64439DC884AFD5`;
7. repository scan for production private keys, credentials, signatures,
   generated production bootstrap/A0 artifacts, and accidental operator
   execution evidence;
8. fresh independent review that recomputes the exact RP2 triple and explicitly
   checks the epoch preimage/digest relationship.

No verification command may invoke the production bootstrap installer,
`prepare_d1_n2()`, `run_d1_n2_preflight()`, camera discovery, FFmpeg,
MediaPipe, a worker, or a native physical operation.

## 9. Governance updates

At implementation start, the B0-R1 triple is historical and status must state
that B0-R2 correction is source-only and under review. At local verification,
the maximum claim is:

```text
B0_R2_EPOCH_BINDING_SOURCE_IMPLEMENTED_LOCALLY_VERIFIED
BOOTSTRAP_UNPROVISIONED
AUTHORITY_NOT_ISSUED
physical_camera_access_authorized=false
device_gate_decision=UNVERIFIED
d1_go=false
```

Only after exact-packet independent review may the maximum claim become:

```text
B0_R2_STATIC_PACK_APPROVED
BOOTSTRAP_UNPROVISIONED
AUTHORITY_NOT_ISSUED
```

`docs/ai/CURRENT_TASK.md`, `docs/ai/TASK_CONTRACT.md`, and
`docs/spec/M2_D1_N2_READINESS_PACK.md` must distinguish the historical B0-R1
triple, the B0-R2 replacement triple, and the still-unstarted B0.3 ceremony.

## 10. Stop boundary and subsequent gates

Completion of this correction stops after fresh B0.2 static-pack approval. It
does not inherit the earlier approval to create the B0.3 specification or any
operational authority.

The subsequent order remains:

```text
B0-R2 source correction and local verification
B0.2  independent review and freeze of the exact replacement RP2
B0.3  written production-signing-identity and bundle specification
B0.3  separately authorized offline custody ceremony
B0.4  separate approval and one-shot installation of the exact bundle tuple
B0.5  separate authority to issue one signed A0 for the exact RP2 triple
A0-P  parameter-free no-stream preparation
A1    independent PreparedAuthority review
X0    one physical preflight only after A1
```

## 11. Residual risks

- Source equality and RP2 binding do not prove that an external machine is
  offline or that a production key is non-exportable.
- The policy preimage describes the only acceptable ceremony profile; actual
  B0.3 evidence must still establish the provider, scope, create-only result,
  export policy, and clean handle closure without revealing private material.
- Static tests do not prove clean-machine CNG, installer, camera, FFmpeg,
  MediaPipe, two-monitor behavior, participant access, research performance,
  academic approval, distribution, or deployment.
- There is no recovery or rotation path. A lost, replaced, exported, or
  ambiguous production key requires a new reviewed epoch design.
- The historical D1-N1 authority remains consumed and terminal. No B0-R2
  artifact reopens it or authorizes retry.

## 12. Routing receipt

```text
schema_version = 1
work = D1-N2 B0-R2 bootstrap epoch binding correction design
route = Sol
effort = xhigh
decision_owner = root
result = SPEC_APPROVED_IMPLEMENTED_STATIC_PACK_APPROVED
```

No routing or design approval grants bootstrap provisioning, A0, preparation,
native execution, camera access, or participant collection.
