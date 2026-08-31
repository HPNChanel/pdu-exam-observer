# Model and Evaluation Specification

Version: 1.0

## Runtime decomposition

The model is not responsible for every system state.

Presence and quality logic determines whether zero, one, or multiple usable poses are present and whether evidence quality is sufficient. This path produces NO_PERSON, MULTIPLE_PEOPLE, or TECHNICAL_INSUFFICIENT using locked persistence and quality policies.

When exactly one usable pose exists, ST-GCN predicts NORMAL, BENIGN_CONFOUNDER, PROLONGED_HEAD_DOWN, and PROLONGED_SIDE_LOOK from a temporal landmark window.

Late fusion combines learned camera scores with a fixed context vector. A regularized multinomial logistic regression is preferred over an MLP because the participant count is small and the context dimension is limited.

## Preprocessing contract

- MediaPipe topology: 33 pose landmarks.
- Stored landmark attributes: x, y, z, visibility.
- Person slots: maximum two; second slot supports presence logic.
- Motion-model input: exactly one usable pose.
- Position normalization: body-centered and scale-normalized using a versioned transform.
- Missing landmarks: explicit mask, never silent zeros without a mask.
- Timestamp resampling: versioned target rate and interpolation policy.
- Window and stride: stored in model manifest.
- Focus context: exam-focus fraction and signal age only.
- Quality context: pose visibility, blur, exposure, and frame-gap ratio.

Every training and runtime implementation uses the same preprocessing identifier and golden fixtures.

## Baseline rules

Rules use head orientation, pose presence, pose count, quality, duration, and distinct start/end thresholds. Hysteresis prevents chatter near a boundary. Persistence, cooldown, and merge gap are explicit policy values.

The rule baseline is a complete runnable configuration and remains available when no learned model is installed.

## ST-GCN training

Training occurs in a reproducible Colab notebook using exported landmarks, labels, context, and manifests. Raw video is not uploaded.

The notebook shall:

- validate schema and hashes;
- enforce participant and provenance split gates;
- fit only on the training partition;
- use calibration participants for early stopping, temperature, fusion, and policy selection;
- save exact environment and random seeds;
- report fold-specific data counts;
- export ONNX and a complete immutable model bundle.

## Calibration and abstention

Apply scalar temperature scaling to learned logits using calibration data only. Late-fusion probabilities are evaluated for calibration after fusion.

Abstain when quality is insufficient, signals are stale, the model is incompatible, outputs are non-finite, or calibrated confidence is below the locked policy. Abstention maps to TECHNICAL_INSUFFICIENT and is reported as coverage, not hidden as an error or normal sample.

## Model bundle

An importable bundle contains:

- model.onnx;
- manifest.json;
- calibration.json;
- policy.json;
- checksums.json;
- golden_inputs.npz;
- golden_outputs.npz;
- MODEL_CARD.md.

The manifest fixes class order, tensor dimensions, landmark topology, preprocessing version, FPS, window, stride, context order, dataset hash, runtime schema range, and model version.

Model import stages into a temporary directory, verifies the allowlist and hashes, runs golden tensors, confirms schema compatibility, and atomically activates the version. It never loads arbitrary Python, pickle, script, shared library, or user-supplied path.

## Evaluation

Use five outer participant-disjoint folds. Compute event matching from continuous real sessions using the frozen overlap and onset policy.

Before protocol freeze, matching is class-aware, one-to-one, and reported over
the tIoU sweep `0.50, 0.55, ..., 0.95`. A single primary tIoU and every numeric
event-policy threshold must be selected only from the applicable
training/calibration partition or pilot method evidence, then frozen before any
outer-test result is viewed. Until that selection, the GOV-P0 contract stores
the values as null rather than inventing operational defaults.

Report:

- per-class event precision, recall, and F1;
- macro and weighted summaries with participant-level uncertainty;
- false alerts per session hour;
- eligible-onset-to-alert latency;
- confusion matrices for six research labels and three operator outcomes;
- Brier score, negative log likelihood, and calibration error;
- coverage and abstention rate;
- technical-insufficient causes;
- results by participant, fold, lighting condition, and benign confounder;
- actual counts by source_kind and split.

No local unit test, demo replay, synthetic fixture, or successful ONNX conversion is evidence of research performance.
