# Candidate-07 lineage receipt (2026-09-22)

Evidence state: `OBSERVED` for all file digests and the packaged verification
result below; `UNVERIFIED` for clean-machine behavior as noted.

## Lineage

- **candidate-06** (`packaging/candidates/completion-2026-09-08/candidate-06`)
  remains the immutable evidence bundle for the 2026-09-08 source snapshot.
  Its zip SHA-256 was recomputed on 2026-09-22 and matches the recorded
  receipt (`f5bd0add40f246d476729d06988d1726297dc705c274194a440d6ad978d21bdc`)
  — bytes unchanged.
- **candidate-07** (`packaging/candidates/remediation-2026-09-22/candidate-07`)
  is the delivery candidate for the post-remediation source (Tasks 01–08).
  It supersedes candidate-06 for delivery purposes; candidate-06 is retained
  as historical evidence only.

candidate-06 still carries the pre-remediation `THIRD_PARTY_NOTICES.txt`
(partial inventory) and predates the Task 05–07 source changes. Those
deficiencies are documented in
`docs/plans/audit-remediation-2026-09-22/00-findings.md` (H2); the candidate
itself is intentionally not modified.

## candidate-07 build facts

- Build script: `scripts/build_completion_delivery.py --parent
  packaging/candidates/remediation-2026-09-22 --name candidate-07`
- Build env (recreated per `docs/spec/BUILD_TOOLCHAIN.md`):
  Python 3.11.9, PyInstaller 6.10.0, pyinstaller-hooks-contrib 2026.7,
  runtime deps from `uv export --locked` (uv.lock).
- FFmpeg input: `ffmpeg 8.0.1-essentials_build-www.gyan.dev`, SHA-256
  `5af82a0d4fe2b9eae211b967332ea97edfc51c6b328ca35b827e73eac560dc0d`
  (byte-identical to the candidate-06 bundled binary).
- `build-receipt.json`, `build.log`, `SOURCE_MANIFEST.json`,
  `RELEASE_MANIFEST.detached.json` are retained beside the bundle.
- One transient build failure occurred mid-build: the source manifest guard
  correctly detected documentation edited during the first attempt
  (`source changed during build`) and the run was discarded and rebuilt on a
  quiescent tree. The guard behaved as designed.
- Rebuilt once on 2026-09-22 after the S3A pin repair exposed that the first
  bundle had been packed from a stale `apps/web/dist` (pre-Task-07 frontend).
- Rebuilt once more on 2026-09-23 (post-remediation hardening Task 05):
  `build_completion_delivery.py` now runs `npm ci` + `npm run build` itself
  inside the build, so the packed frontend is a derived artifact of the
  pinned lockfile rather than trusted pre-existing `dist` bytes — the
  exact staleness failure mode above cannot recur silently. Same-name
  rebuild of the same source tree, not a new candidate.

### Current build (2026-09-23, hardening Task 05)

- `PDUWorkspace.exe` SHA-256:
  `e31a7f2e49acf3edde1be3d27b3b4b1dc046a3847656e1452376229c4141d48e`
- `PDU-Workspace-local.zip` SHA-256:
  `c3426f1c5e42711b3be812181a593c2a7af49e7d6292faf6ca5739ace8763eea`
- `DELIVERY_MANIFEST.json` SHA-256:
  `cf0af0ff8458e39d6a73b7557deffbd07fd92f4da91565be19221c29bd34486b`
- `build-receipt.json` now records `node_version: v24.11.0`,
  `npm_version: 11.14.1`, and `frontend_dist_manifest` (sha256 + bytes for
  all 5 dist files, `assets/index-Bl2iPLFx.js` included).

### Superseded 2026-09-22 build facts (historical)

- `PDUWorkspace.exe` SHA-256:
  `c418d82219a015e5e5df81fa4bdb09b52c872aa9c0a179f768b47b0ad98cb2da`
- `PDU-Workspace-local.zip` SHA-256:
  `738e6a8fa3ce4b6587965665c465502f61630a08e6018a7ac824bb67ce9257ad`
- `DELIVERY_MANIFEST.json` SHA-256:
  `d436aeb9a6f94059e9862c4ed59fd60c519f759e20d4618a9a311e9b01351cee`
- That bundle carried the current `index-Bl2iPLFx.js` frontend (rebuilt
  after the stale-dist discovery) but the dist bytes were still trusted
  rather than built in-band.

## Packaged verification (OBSERVED, same host)

`scripts/verify_completion_package.py` receipt:
`output/remediation-2026-09-22/package-verification.json` — `status: PASS`
(regenerated against the 2026-09-23 build;
`bundle_manifest_sha256: b0d32de150d2c021ca0a9e44349310e3df5c4b538e92697cd99790cb0b45f0fe`).

Both the original location and a relocated copy (`Relocated folder with
spaces`) passed the packaged synthetic workflow: manifest verified, reviewer
login, synthetic session (90 records, `source_kind=AI_RENDERED`), model
import with inference `READY`, allowlisted export, and withdrawal removing
owned artifacts. Child process PATH was `WINDOWS_SYSTEM32_ONLY` with no
Python/Node reachable; the external HTTP proxy was unreachable (loopback
only).

## Not claimed

- Clean-machine (new device) verification: `new_device_verified: false` —
  deferred to the external gate in Task 11.
- Release authorization, participant collection, institutional approval,
  model performance, or research-training claims.
- Bit-for-bit reproducibility of the bundle across rebuilds (PyInstaller
  embeds build timestamps/paths); the toolchain is documented and the binary
  inputs are hash-pinned, which is the supported reproducibility claim.
