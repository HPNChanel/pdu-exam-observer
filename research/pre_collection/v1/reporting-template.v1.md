# Confirmatory reporting template v1

Status: `DRAFT_NOT_FROZEN`

## Required provenance

Report protocol, labelbook, scenario, capture, preprocessing, split, model,
calibration, abstention, matching, and manifest versions. Report actual counts
by participant, cohort, class, source kind, uncertainty, exclusion, and
technical-insufficient status.

## Primary result

Report the participant-level difference in false alerts per valid continuous
exam hour between context-plus-abstention and camera-only configurations at the
pre-frozen primary tIoU and matched recall target. Show every outer fold and
pooled out-of-fold real sessions.

## Required secondary results

- Class-wise precision, recall, F1, latency, and class-aware tIoU sweep
  `0.50` through `0.95`.
- Three-state operator confusion matrix.
- Brier score, negative log likelihood, calibration error, abstention rate,
  coverage, and risk-coverage curve.
- Frame-gap, pose-visibility, exclusion, technical-insufficient, and missing-data
  rates.
- Error analysis for writing, scratching, posture adjustment, no-person, and
  multiple-people cases.

## Integrity statements

State explicitly that pilot samples are excluded from confirmatory metrics,
participants are disjoint across outer folds, synthetic/augmented samples do
not enter calibration/test, and thresholds were selected without outer-test
outcomes. Report null or negative findings without relabeling or metric changes.
