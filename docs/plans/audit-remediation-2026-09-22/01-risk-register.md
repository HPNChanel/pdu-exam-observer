# Task 01 — Risk register and governance annotations

**Type:** docs-only. **Findings:** M1, M2, M3, L8, L12.
**Depends on:** DG-1 decision recorded (commit or proceed dirty).

## Objective

Make `docs/plans/RISK_REGISTER.md` name the three structural limits the audit
confirmed, so a reviewer can see the project knows them, and fix two stale
labels that can mislead a thesis/IRB reader.

## Steps

1. Read `docs/plans/RISK_REGISTER.md` fully first — match its existing entry
   format (R-xx id, statement, evidence gate, status) and its rule at
   `RISK_REGISTER.md:48` that no risk closes by prose.
2. Add **R-43 — self-attested collection authority** (finding M1):
   - Statement: `collection-authority.v1.json` binds document *existence*
     (SHA-256 of operator-supplied files), not institutional *approval*; an
     operator or same-account process can author a well-formed record and
     collect (`authority_cli.py:147-218`, `service.py:998-1027`).
   - Mitigations today: record is never shipped or installed by default
     (`AUTHORITY_NOT_ISSUED` everywhere); install is compare-and-swap bound to
     the resolved root (`authority_cli.py:199-208`); every REAL frame
     re-validates (`service.py:471-476`); the guide normatively forbids
     self-editing (`WORKSPACE_GUIDE_VI.md:58-62`).
   - Status: ACCEPTED-WITHIN-THREAT-MODEL; residual = procedural trust in the
     operator. Explicitly note `chmod 0o700` (`authority_cli.py:196`) is a
     no-op on Windows ACLs and is not a control.
   - Evidence gate: a future signed/notarized authority record or external
     custodian flow would downgrade this risk.
3. Add **R-44 — no technical interlock between collection authority and the
   D1 device-gate** (finding M2a): `start_real_collection` does not require a
   recorded `device_gate_decision`; the rung ordering in
   `M2_READINESS_PACK.md` is procedural. Status: OPEN until Task 07 adds the
   `device_gate_decision` field to the authority record.
4. Add **R-45 — PATH-resolved FFmpeg provenance** (finding M3):
   `shutil.which("ffmpeg")` fallback (`service.py:1627-1632`) trusts PATH under
   the same account. Status: OPEN until Task 06 removes or hash-pins the
   fallback.
5. Add **R-46 — network guard scope limit** (finding L8): the socket guard is
   Python-process-local (`m2_d1_native.py:124-194`); native DLL egress is not
   observable. Status: ACCEPTED — the real boundary is that no code path
   performs egress; add one sentence to `docs/spec/SECURITY_PRIVACY.md`
   stating this limit explicitly.
6. Fix stale labels:
   - `m1.py:1105` `RESEARCH_COLLECTION_NOT_IMPLEMENTED`: add one line to
     `docs/spec/M1_PERSISTENCE_SPEC.md` (or the M1 section it lives in)
     scoping the code to "M1 research-session store" — do NOT rename the code
     constant (receipts reference it).
   - `M2_READINESS_PACK.md:39`: add a clarifying line that
     `M2_MODEL_TRAINING_OR_EVALUATION_AUTHORIZED=false` refers to
     *research* training; synthetic training delivered 2026-09-08 is a
     separate, user-approved scope (`COMPLETION_2026_09_08.md:17-20`).
   - `physical_camera_access_authorized=false` vs the authorized camera
     diagnostic: add one disambiguating line where the ceiling table first
     appears in `docs/ai/CURRENT_TASK.md` historical record — diagnostic
     authorization ≠ collection authorization.

## Acceptance

- `git diff` touches only: `docs/plans/RISK_REGISTER.md`,
  `docs/spec/SECURITY_PRIVACY.md`, `docs/spec/M1_PERSISTENCE_SPEC.md`,
  `docs/spec/M2_READINESS_PACK.md`, `docs/ai/CURRENT_TASK.md` (annotation
  lines only — do not restructure the ledger).
- No status field anywhere flips to a stronger claim; ceilings remain
  `authority_status=AUTHORITY_NOT_ISSUED`, `d1_go=false`, etc.
- No code files changed; no test changes needed; run
  `pytest tests/research tests/backend/test_m2_d1_n2_rp2_artifacts.py -q` to
  confirm nothing references the edited text by hash.
