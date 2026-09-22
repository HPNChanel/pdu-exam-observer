# Packaging lineage — read before building or picking an artifact

Status: OBSERVED map of what each packaging path produces, added during the
2026-09-22 audit remediation. The files listed as "pinned" are hash-bound by
the M2-S3A audit receipt (`docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.json`) or the RP2
source inventory; editing them would falsify historical receipts, so they are
intentionally left byte-identical and marked here instead.

## Current delivery lineage (use this)

- Builder: `scripts/build_completion_delivery.py` (requires `--build-python`
  and `--ffmpeg`; see `docs/spec/PACKAGING_DISTRIBUTION.md` for the bundle
  shape and toolchain).
- Spec: `packaging/PDU-Workspace.spec` (one-dir, includes frontend
  `apps/web/dist` → `assets/web`, `demo/`, `assets/models` →
  `pdu_exam_observer/assets/models`, mediapipe/onnxruntime/onnx data files,
  `tools/ffmpeg.exe`).
- Verified candidate:
  `packaging/candidates/completion-2026-09-08/candidate-06/`
  (`PDU-Workspace-local.zip`, SHA-256
  `f5bd0add40f246d476729d06988d1726297dc705c274194a440d6ad978d21bdc`).
- Verifier: `scripts/verify_completion_package.py`.

## Historical lineage (do not build or ship)

- `scripts/build_release.ps1` + `packaging/PDU-Exam-Observer.spec` build the
  M1-era `PDUExamObserver.exe` bundle. The spec has `hiddenimports=[]` and
  `datas` limited to `assets/web` + `demo`: a rebuild against current source
  produces a bundle missing `pdu_exam_observer/assets/models`,
  mediapipe/onnxruntime data files, and `tools/ffmpeg.exe`. Pinned by the
  S3A audit — retained for provenance only.
- `packaging/README.txt` describes that same M1 trial bundle. Pinned —
  retained for provenance.
- `packaging/release/PDU-Exam-Observer/` is the 2026-08-30 historical bundle
  (manifest-valid, `HISTORICAL_NOT_CURRENT_SOURCE`). Closed manifest file
  set — do not add or remove files inside it.
- `packaging/README_M2_S3B_CANDIDATE.txt`,
  `packaging/README_M2_S3D_CANDIDATE.txt`,
  `packaging/README_M2_S3E_HANDOFF.txt`,
  `packaging/M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.template.json`,
  `packaging/VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1`,
  `packaging/PDU-Exam-Observer.current-source.spec`, and
  `packaging/PDU-Exam-Observer.s3d.spec` are milestone-scoped artifacts bound
  into the RP2 source inventory — do not edit in place.
- `packaging/handoffs/m2-s3e-clean-environment/` is the delivered clean-
  environment handoff (ZIP SHA-256 `ab58430c…`); the sibling
  `m2-s3e-failed-*` and `m2-s3e-diagnostic-fourth` directories are failed or
  diagnostic attempts kept for audit — each carries a marker file.
- `packaging/candidates/completion-2026-09-08/candidate-04` and
  `candidate-05` are superseded same-day builds — see their `SUPERSEDED.txt`
  markers. Only candidate-06 is verified.
