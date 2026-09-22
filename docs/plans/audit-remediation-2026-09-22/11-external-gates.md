# Task 11 — External gates tracker (non-codable)

**Type:** documentation-only tracker. **Findings:** H4 (commit authority),
H5 (all external acceptance). **Depends on:** none — can be written early,
but it is listed last because it tracks items code cannot close.

## Objective

One honest checklist of everything that remains open NOT because of code but
because it requires the physical world or the user's authority. This becomes
the "what's left before real research" page for the thesis/IRB narrative.

## Steps

1. Create `docs/plans/EXTERNAL_GATES.md` (or keep inside this folder as
   `11-external-gates-checklist.md`) with one row per gate:

   | Gate | Required evidence | Current state | Blocking |
   |------|-------------------|---------------|----------|
   | Clean-machine verification (GAP-08 / S3E-B) | Run `packaging/handoffs/m2-s3e-clean-environment/M2-S3E-CLEAN-ENVIRONMENT-HANDOFF.zip` + `VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1` on a genuinely separate Windows machine/VM without Python/Node/admin/Internet; import the filled `M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.template.json` | USER_DEFERRED_UNVERIFIED | Any portability claim |
   | Camera profile | A device/camera meeting 1280x720 @ ≥15 fps measured (current host: ~10.08 fps → fails closed) | UNVERIFIED | REAL collection |
   | Dual physical displays | `GetSystemMetrics(80) >= 2` on the collection machine (current: 1) | UNVERIFIED | REAL collection (reviewer surface on second monitor) |
   | Institutional approval | GOV-P3 verbal confirmation is USER_STATED only; P4 records deadline passed; P5 request NOT_SUBMITTED. External submission + recorded approval required | NOT_PERFORMED | Any real participant |
   | Consent + retention + storage | Real consent form signed, retention decision recorded, approved storage root with OBSERVED (not attested) encryption/ACL | NOT_PERFORMED | Any real participant |
   | Research performance | Pilot/confirmatory collection → real training → evaluation per MODEL_EVALUATION_SPEC (continuous-session denominators already implemented) | NOT_PERFORMED — synthetic smoke only | Any scientific claim about detection quality |
   | Commit/push of delivery (H4) | User grants scoped commit authority for the delivered working tree (recommend: baseline commit BEFORE remediation, milestone commit after Task 10) | AWAITING USER DECISION | Recoverability of delivered source |
   | Distribution/release | THIRD_PARTY_NOTICES regenerated (Task 04), signing decision, distribution authorization | NOT_AUTHORIZED | Any sharing beyond local |

2. For each gate record the *smallest sufficient evidence* — reuse the
   project's existing receipt machinery (e.g. S3E-B response JSON,
   `workspace-camera.json` fields, decision-record templates in
   `research/institutional_submission/v1/`).
3. Cross-link from `docs/ai/CURRENT_TASK.md` Task-10 update and from
   `docs/plans/ROADMAP.md` so a reader always reaches this page.

## Acceptance

- The tracker exists, every row cites its evidence artifact, and no row
  claims more than the evidence supports.
- No code changes; no authority ceiling moved.
