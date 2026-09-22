# Full system and Colab completion

Status: LOCAL_TECHNICAL_DELIVERY_VERIFIED. Completed 2026-09-08 within the
user-approved technical scope; external research/device acceptance remains separate.

## Outcome and authority

USER_STATED: complete the main repository system, review/export/model flows,
self-contained Colab training code and local delivery. Current-device technical
checks are authorized. No participant collection, actual research training,
commit, push, distribution or release is requested. A new-device test is deferred
by the user and remains UNVERIFIED; it does not block technical delivery.

SOURCE_VERIFIED: canonical proposal SHA-256 remains
2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5.

Ruling: preserve historical M0/M1/synthetic receipts and add a current research
runtime; historical milestone ceilings do not prohibit implementing the newly
approved code. Actual collection continues to require recorded institutional,
consent, retention and storage authority.

## RoutingReceipt

```json
{"schema_version":1,"profile":"research","default":{"model":"gpt-5.6-terra","effort":"high"},"research":{"model":"gpt-5.6-sol","effort":"xhigh"},"assignments":[{"task":"training","model":"gpt-5.6-sol","effort":"xhigh"},{"task":"runtime","model":"gpt-5.6-terra","effort":"high"}],"root":"session configured model; integration and final decision owner"}
```

## Work ledger

| Work | Acceptance | State |
|---|---|---|
| M2 capture, pose, focus, storage and recovery | Single owner; bounded capture process; technical failures fail closed; current-device receipt | LOCAL_CODE_VERIFIED; CURRENT_CAMERA_PROFILE_INSUFFICIENT |
| M3 review, labels, baseline and withdrawal | Sealed video review; manual/versioned decisions; temporal rules; owned-fixture withdrawal | LOCAL_SYNTHETIC_VERIFIED |
| M4/M5 preparation and export | Native authority gates; exact allowlist; provenance/cohort/participant split tests | LOCAL_CODE_VERIFIED; REAL_COLLECTION_NOT_PERFORMED |
| M6 training, ONNX and model import | Synthetic CPU training round trip; locked notebook dependencies; atomic verified activation | LOCAL_SYNTHETIC_VERIFIED |
| M7 evaluation implementation | Continuous-session denominator; maximum-cardinality same-class tIoU matching; three configurations | LOCAL_CODE_VERIFIED; REAL_EVALUATION_NOT_PERFORMED |
| Authenticated UI and integration | Actual exam/reviewer flow, saved answer, playable local video, annotation, lock/export/withdraw | LOCAL_BROWSER_VERIFIED |
| Packaging and GAP-06 | Current source manifest/hash, complete build metadata, EXE workflow and same-host relocation | LOCAL_SAME_HOST_VERIFIED |
| Independent review and final gates | Security/data and research review; backend/frontend/static/runtime evidence | LOCAL_VERIFIED; FINDINGS_CLOSED |
| New-device verification / GAP-08 | Requires another environment | USER_DEFERRED_UNVERIFIED |
| Institutional approval, real participants and research results | Requires external evidence | NOT_PERFORMED |

## Baseline

OBSERVED: work started on dirty main and moved to codex/complete-system-colab
without resetting user changes. Baseline status and patch are retained in local
output/completion-2026-09-08. Existing evidence is not treated as fresh test output.

## Falsifiable assumptions

The sibling demo supplies reusable training/preprocessing code, not authority
or current main-repository acceptance. Smallest refutation: cross-contract
export -> training -> ONNX -> runtime smoke. Its window-based false-alert-hour
denominator must be replaced by continuous-session time before research use.

## Verification

OBSERVED: frontend typecheck/lint and 82 tests pass. Ruff passes across the
repository; strict mypy passes for 62 source files. The final focused runtime
and workspace run passes 37 tests (25.06 seconds), including session lifecycle,
authority, integrity, temporal context and the authenticated HTTP workflow.
The wide nontraining run passes 1,018 tests (468.12 seconds), recorded in
`output/completion-2026-09-08/backend-clean-final.txt`. It precedes the final
privacy fixes, which are covered by the 37-test run, including five new
discriminating regression cases. The earlier run found seven historical
binding mismatches. Six came from a Vite asset removed by rebuilding; its exact
recorded bytes were restored from the preserved candidate. The current RP2
assertions now name the refreshed current binding while S3E receipt constants
remain unchanged. All 23 packaging and nine governance/RP2 targeted checks pass.

OBSERVED: the browser run in `output/completion-2026-09-08/ui-start.log` and
`ui-finish.log` exercised pairing, consent/preflight, recording, answer B saved,
seal, playable six-second local MP4 (readyState 4, no media error), manual
annotation, label lock, exact-envelope export, local report and withdrawal.
Representative images are `final-skeleton.png`, `final-exam.png`,
`final-video.png`, and `final-review.png` in the same output directory. They
were inspected for legibility/layout; this is not user aesthetic approval.

OBSERVED: `workspace-camera.json` records 1280x720 at 10.07599 measured fps,
16 frames and one physical display. The required 15fps profile is unavailable;
capture remains blocked. No video or audio was saved. Camera nominal collection,
two physical monitors and a new device are not verified by synthetic tests.

SOURCE_VERIFIED: training and runtime share preprocessing, per-window context
aggregation, orientation proxy and temporal rule engine. Independent method
review found and corrected denominator loss for unlabeled sessions, mixed-fold
augmentation provenance, greedy event matching and missing REAL inference
context. Final training fixtures exercise these counterexamples. Shared policy
parsing also rejects fractional milliseconds. The training suite passed 33 tests
before that final parser correction; all nine affected protocol/rule tests
passed afterward. The final model/report ZIPs were then rebuilt. A detached
`python -I` import proves the notebook restores all project modules from its
embedded archive without a developer checkout; no external Colab execution is
claimed.

SOURCE_VERIFIED: independent security/data review found four issues, then
confirmed their fixes: REAL preview revalidates current authority; each REAL
frame revalidates before writing; stop/withdraw retain ownership when a worker
is alive; withdrawal rejects untracked files, verifies available manifest
hashes and deletes only an enumerated inventory. The five new tests reproduce
revocation, authority rebinding, a blocked camera thread, and untracked-file
preservation. No additional material bypass was found within the inspected
API/service paths. This is a scoped review, not a universal security claim.

OBSERVED: the final candidate passed both original-location and relocated EXE
workflows. Each run authenticated, imported the eight-file smoke model, paired
the exam, recorded/sealed a synthetic session, saved an answer, reviewed and
locked labels, read the local MP4, exported 90 records and withdrew the owned
artifacts. Model inference was invoked and returned READY in both runs.
The child PATH contained only Windows System32; Python and Node were absent
from that PATH, and external HTTP proxies were unreachable. The host network
interface was not disabled: this is bounded same-host dependency/loopback
evidence, not a new-machine or physically disconnected-network certification.

OBSERVED: the same final EXE also passed the actual browser workflow, including
video playback (6 seconds; readyState 4; no media error), manual annotation,
label lock, export/report, withdrawal and model upload through the UI.
Its browser console contained only native password-form advisories, with no
application error. The representative packaged screenshots were inspected.

SOURCE_VERIFIED: current source matches the bundle's SOURCE_MANIFEST byte
inventory; the bundled and detached release manifests verify before and after
runtime/relocation checks. All four delivery ZIPs pass CRC inspection. GAP-06
metadata is complete for this candidate. This does not rewrite old package
receipts or grant distribution/release authority.

## Deliverables and receipts

- [Application ZIP](../../packaging/candidates/completion-2026-09-08/candidate-06/PDU-Workspace-local.zip)
  — 159,884,706 bytes; SHA-256
  `f5bd0add40f246d476729d06988d1726297dc705c274194a440d6ad978d21bdc`.
- [Colab ZIP](../../output/completion-2026-09-08/training-delivery/pdu-stgcn-colab-delivery.zip)
  — notebook, pinned dependencies/configuration, protocol template, synthetic
  input, golden fixtures and training/restore guide; SHA-256
  `279da1662fc453e4d779c4beba991a4674e017887a6b75b99095c96272de8ed3`.
- [Demo model ZIP](../../output/completion-2026-09-08/training-delivery/pdu-stgcn-demo-model.zip)
  and [smoke reports](../../output/completion-2026-09-08/training-delivery/pdu-stgcn-demo-reports.zip).
- [Vietnamese operating guide](../WORKSPACE_GUIDE_VI.md).
- [Final machine-readable verification](../../output/completion-2026-09-08/delivery-verification.json)
  binds artifacts, source, packaged runtime, browser flow and screenshot hashes.
- [Packaged runtime/relocation receipt](../../output/completion-2026-09-08/package-verification.json)
  and [detached notebook import receipt](../../output/completion-2026-09-08/training-delivery/self-contained-import-evidence.json).
- [Packaged review screen](../../output/completion-2026-09-08/packaged-review.png)
  and [model import screen](../../output/completion-2026-09-08/packaged-model-import.png).

## Residual boundaries

UNVERIFIED: nominal collection on a camera meeting 1280x720@15fps, two physical
displays, a new Windows machine without installed development tools, physical
network disconnection, and external Colab execution. Current camera diagnostics
fail closed at about 10.08fps and one display. USER_STATED: new-device acceptance
is deferred and does not block this technical delivery.

NOT_PERFORMED: institutional approval, real participant collection,
pilot/confirmatory data collection, real research training/performance,
commit/push, deployment, publication and release. The proposal remains unchanged.
