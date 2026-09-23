# External gates tracker — what remains before real research

Status: `EXTERNAL_GATES_TRACKER_OPEN_ITEMS_NON_CODE`

Updated: 2026-09-22 (audit remediation Task 11)

This page is the single honest checklist of everything that remains open
**not because of code** but because it requires the physical world or the
user's/institution's authority. It is the "what's left before real research"
page for the thesis/IRB narrative.

Nothing on this page is authorized or verified. Each row names the smallest
sufficient evidence artifact; a gate closes only when that evidence exists
and is imported into the ledger.

## Gate matrix

| Gate | Required evidence (smallest sufficient artifact) | Current state | Blocks |
|------|--------------------------------------------------|---------------|--------|
| Clean-machine verification (GAP-08 / S3E-B) | Run `packaging/handoffs/m2-s3e-clean-environment/M2-S3E-CLEAN-ENVIRONMENT-HANDOFF.zip` on a genuinely separate Windows machine/VM — extract, run `VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1` without Python/Node/admin/Internet, fill `M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.template.json`, import the response into the repo | `USER_DEFERRED_UNVERIFIED` | Any portability claim beyond same-host |
| Camera profile | A camera on the collection machine meeting `capture.v1.1280x720@15fps.no-audio` — measured `measured_fps >= 15` in `workspace-camera.json`-style diagnostic output (current host observed `10.076` fps over 16 frames → REAL capture fails closed) | `UNVERIFIED` (current device insufficient) | REAL collection |
| Dual physical displays | `physical_display_count >= 2` (`GetSystemMetrics(80)`) in the native preflight on the collection machine (current host: `1`) | `UNVERIFIED` | REAL collection (reviewer surface on second monitor) |
| Institutional approval | External submission of the GOV-P5 request pack (`research/institutional_submission/v1/` templates) plus a recorded institutional decision; GOV-P3 verbal confirmation is `USER_STATED` only, GOV-P4 recorded the cycle deadline passed, GOV-P5 request is `NOT_SUBMITTED` | `NOT_PERFORMED` | Any real participant |
| Consent + retention + storage | Signed real consent form (annex-b draft in `research/institutional_submission/v1/`), recorded retention decision (`retention-storage-withdrawal-decision.vi.v1.md` executed, not drafted), approved storage root with OBSERVED encryption/ACL evidence (not attested) | `NOT_PERFORMED` | Any real participant |
| Research performance | Pilot/confirmatory collection → real training → evaluation per `docs/spec/` model-evaluation requirements; continuous-session denominators already implemented | `NOT_PERFORMED` — `SYNTHETIC_SMOKE` evidence only | Any scientific claim about detection quality |
| Commit/push of delivery (H4 residue) | Commit authority was granted and exercised: baseline + Tasks 01–10 are committed (`4e52921`..`3b9a9ad` on `codex/complete-system-colab`). Remaining: scoped push authorization if an off-host backup is wanted | `COMMITTED_LOCALLY` / `PUSH_NOT_AUTHORIZED` | Off-host recoverability of delivered source |
| Distribution / release | THIRD_PARTY_NOTICES regenerated (done, Task 04) + signing decision + explicit distribution authorization | `NOT_AUTHORIZED` | Any sharing beyond the local machine |

## Notes and honest caveats

- The clean-environment handoff zip currently packs the **historical
  S3D-candidate executable** (`PDUExamObserver.exe`, pre-remediation
  lineage), not candidate-07. Running it on a clean machine verifies
  *that* build. If the gate is attempted for the post-remediation source,
  a current-source handoff pack must be built first — same receipt
  machinery, new bundle.
- The current camera reading (~10.08 fps) and display count (1) are
  OBSERVED insufficiencies on *this* host — the runtime fails closed on
  them by design. A different machine may satisfy both; nothing is
  inferred about machines not measured.
- GOV-P3's advisor verbal confirmation remains `USER_STATED_UNVERIFIED`
  evidence; it does not substitute for the institutional decision record.
- No row on this page may be described as "in progress" or "nearly done"
  in any ledger until the cited artifact exists.

## Cross-references

- Remediation receipt: `docs/ai/AUDIT_REMEDIATION_2026_09_22.md`
- Current ceilings: `docs/ai/CURRENT_TASK.md` (Task-10 milestone block)
- Roadmap header: `docs/plans/ROADMAP.md`
- Findings: `docs/plans/audit-remediation-2026-09-22/00-findings.md`
  (H5, and the push/distribution residue of H4)
