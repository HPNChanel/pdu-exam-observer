# M2-S3D Packaged Evidence Round-Trip Implementation Plan

document_status=USER_APPROVED_FOR_IMPLEMENTATION

1. Establish ten RED packaging tests for stdin-only dispatch, complete source
   binding, candidate lineage, deterministic build contract, two-cycle runtime
   projection, canonical receipt, gap state, and authority ceiling.
2. Implement the packaged reproduction protocol and bind its load-bearing
   sources. Preserve the existing HTTP API and all S2D/S2E semantics.
3. Add the new spec, README, and deterministic S3D candidate builder. Reconcile
   RP2 once after tracked build inputs stabilize, then build A/B once and use
   read-only checks thereafter.
4. Implement and run the no-argument two-cycle harness exactly once. Materialize
   its canonical stdout only after both cycles export and reproduce preflight
   and nominal exactly with complete cleanup.
5. Update the v21 governance ledgers, G23/G19/R-41, run focused/static/RP2/
   governance/research/full-suite and manifest gates, inspect the diff, commit,
   and push main. Do not tag, sign, deploy, distribute, or release.

Stop without publishing the S3D marker on any build mismatch, invalid bundle,
non-exact reproduction, cycle drift, listener/path disclosure, cleanup failure,
historical evidence mutation, gate failure, or authority escalation.
