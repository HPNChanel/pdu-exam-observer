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
- `PDUWorkspace.exe` SHA-256:
  `02dc32b1eea1a2bcd51ca101409981f998c3f06900cfc856ecc810bd3e435eca`
- `PDU-Workspace-local.zip` SHA-256:
  `b1e1e11f2b06d35a795577138378660b24437c2d9ee9aca40c877bf93b83830c`
- `DELIVERY_MANIFEST.json` SHA-256:
  `8332d84b175f7b81888abd2d0769f79971adc6150030a028e21480841167fd51`
- `build-receipt.json`, `build.log`, `SOURCE_MANIFEST.json`,
  `RELEASE_MANIFEST.detached.json` are retained beside the bundle.
- One transient build failure occurred mid-build: the source manifest guard
  correctly detected documentation edited during the first attempt
  (`source changed during build`) and the run was discarded and rebuilt on a
  quiescent tree. The guard behaved as designed.

## Packaged verification (OBSERVED, same host)

`scripts/verify_completion_package.py` receipt:
`output/remediation-2026-09-22/package-verification.json` — `status: PASS`.

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
