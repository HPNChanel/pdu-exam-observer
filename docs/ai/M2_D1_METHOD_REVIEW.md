# M2-D1 Research and Privacy Method Review

Date: `2026-08-26`

Reviewer route: `Sol/xhigh`, role `research_methodologist`

Initial decision: `CONDITIONAL_GO`

Final decision after implementation remediation: `APPROVE`

## Accepted scope

An injected test-chart/synthetic-video backend may exercise D1 accounting, thresholds, receipt
validation, stop precedence, exclusive-owner abstraction, and output-compatible mutants. The only
successful result is `BACKEND_CONTRACT_PASS` and it must retain
`device_gate_decision=UNVERIFIED`.

## Refuted claim

Injected evidence cannot prove negotiated camera profile, native/cross-process camera ownership,
OS-level no-audio behavior, physical encoder/disk performance, real-environment privacy behavior,
the 60-second preflight, the 20-minute run, or `D1_GO`. Those require separately observed native
runtime evidence.

## Binding safeguards

- Do not weaken S1 to accept `NO_HUMAN_DEVICE_SCENE`.
- Do not extend P1 artifact kinds or use its research `session_id`/seal path for D1.
- Do not import, instantiate, or mutate M1; `RESEARCH_COLLECTION_NOT_IMPLEMENTED` remains true.
- Accept only injected `TEST_CHART` or `SYNTHETIC_VIDEO`; reject native/real provenance, paths,
  URLs, device/browser fields, participant/session identifiers, labels, confidence, and alerts.
- Screen privacy before pose/encoder/durability processing. `UNSAFE`, `UNKNOWN`, unavailable, or
  exception is terminal `PRIVACY_STOP`; no seal/export and no automatic resume.
- Exact accounting, nearest-rank thresholds, warmup fault retention, canonical receipts, and the
  complete direct-fault/output-compatible-mutant ledger are required.

## Evidence left unverified

Physical device enumeration/access/ownership/profile, audio non-access at OS level, native timing,
encoder/disk/durability behavior, real privacy detection, packaged runtime, participant/research
validity, production, release, deployment, and institutional evidence remain `UNVERIFIED`.

## Final review receipt

`SOURCE_VERIFIED`: all prior source-level `NO-GO` findings are closed. Privacy stop produces a
minimal receipt with no post-stop encoder/disk/provenance/reproduction/evaluation claim; semantic
receipt verification re-applies the pass thresholds and rejects rehash mutants; every capture kind
is run-end bounded; authority/provenance/reproduction are strict and revision-scoped; the real
`uv.lock` SHA-256 is bound; quality/failure/drop counts reconcile; and focused tests discriminate
privacy, ownership, stages, warmup, timing, thresholds, capacity, and dynamic-access mutants.

Final reviewer route: `Sol/xhigh`, role `research_methodologist`, decision `APPROVE`. This approval
is for `D1_BACKEND_CONTRACT_LOCALLY_VERIFIED_PENDING_NATIVE_EVIDENCE` only and does not establish
physical/native device evidence or `D1_GO`.
