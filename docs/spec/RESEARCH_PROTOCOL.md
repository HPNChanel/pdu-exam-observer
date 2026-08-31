# Research Protocol

Version: 1.0

Status: DRAFT PRE-COLLECTION; NOT FROZEN; COLLECTION NOT AUTHORIZED

The machine-verifiable draft inputs are under `research/pre_collection/v1/`.
Their structural validation does not replace institutional approval, pilot
evidence, protocol freeze, or collection authority.

## Research question

Can temporal pose analysis with image-quality and exam-focus context reduce false alerts caused by benign confounders while preserving event detection, compared with a rule baseline and a camera-only model?

## Primary estimand

The primary estimand is the participant-level difference in false alerts per continuous exam hour between context-plus-abstention and camera-only configurations, with thresholds chosen exclusively from the corresponding training/calibration partition to target the same event recall.

The confirmatory report shall show the effect per outer fold and across pooled out-of-fold real sessions. It shall not redefine the metric, classes, exclusion rules, or matching procedure after viewing test results.

## Secondary outcomes

- Event precision, recall, and F1 by research label.
- Three-state operator confusion matrix.
- Detection latency measured from the first time an event becomes eligible under the locked duration policy.
- Brier score, negative log likelihood, and calibration error.
- Abstention rate and coverage.
- Frame-gap, pose-visibility, and technical-insufficient rates.
- Error analysis for writing, scratching, posture adjustment, no-person, and multiple-person cases.

## Participants and phases

Target twelve consenting adults.

Pilot phase: two participants. Each is planned for eight to ten precommitted
6,000-ms windows per supervised class across two continuous twenty-minute
sessions, for 96 to 120 pilot clips. Pilot data is used to test the apparatus,
instructions, visibility, benign confounders, focus contamination, storage
throughput, and labelability. Pilot samples are excluded from confirmatory
metrics.

Confirmatory phase: ten participants. Each completes two controlled twenty-minute mock-exam sessions under documented camera, lighting, seating, and scenario conditions.

## Event schedule

Each confirmatory participant is scheduled for nine to ten 6,000-ms,
non-overlapping windows per supervised class across the two continuous
sessions. This targets 540 to 600 confirmatory clips and 636 to 720 combined
pilot-plus-confirmatory planned clips while retaining the continuous timeline
required for false-alerts-per-hour and latency analysis. Actual usable,
uncertain, excluded, and technical counts are reported separately.

Scenario timestamps are prepared before a session and are not moved after
model output is observed. Labelers compare the timestamp plan with the local
recording. When observable evidence is insufficient, the event becomes
UNCERTAIN rather than being forced into a supervised class.

## Labels

NORMAL: ordinary exam behavior without a review-worthy event.

BENIGN_CONFOUNDER: writing notes, scratching, stretching, or posture adjustment that may resemble head or shoulder movement but should not trigger excessive review alerts.

PROLONGED_HEAD_DOWN: observable sustained downward head orientation, without inferring the object or intent.

PROLONGED_SIDE_LOOK: observable sustained lateral head orientation.

NO_PERSON: no usable person visible after the locked persistence and quality rules.

MULTIPLE_PEOPLE: more than one usable pose visible after the locked persistence and quality rules.

UNCERTAIN: insufficient visual evidence to assign a research label. It is excluded from supervised class training and retained for audit.

## Two-corpus policy

Demo corpus: may be AI-rendered majority. It exists to develop the UI, capture pipeline, replay behavior, packaging, and failure handling. It may not support research performance claims.

Confirmatory corpus: real participant sessions are the only calibration and test source. AI-rendered and augmented samples may be added only to training partitions. Every sample retains immutable source_kind and parent provenance.

Actual source counts are reported. A technical format that matches real data does not make an AI-rendered sample real.

## Experimental configurations

Rules: head angle, pose presence, pose count, event duration, distinct start/end thresholds, persistence, cooldown, and merge gap.

Camera-only: presence/quality logic plus ST-GCN motion scores, without focus context or final abstention fusion.

Context plus abstention: camera scores combined with quality and focus context, calibrated probabilities, and a locked abstention policy.

## Split and leakage control

Use five participant-disjoint outer folds with two confirmatory participants per test fold. No participant appears in both train/calibration and outer test.

Within each outer training partition, reserve real participant data for calibration. Synthetic or augmented samples may enter only the model-training subset.

Augmentations are fitted or parameterized without inspecting outer test outcomes. Temperature, fusion coefficients, thresholds, duration policy, and abstention policy are selected without outer test data.

Automated gates must prove:

- zero participant overlap;
- zero pilot samples in confirmatory metrics;
- zero AI-rendered or augmented samples in calibration/test;
- no child augmentation outside its parent's training fold;
- no test statistic used during threshold or model selection.

## Protocol freeze

Before freeze, class-aware one-to-one event matching reports the tIoU sweep
from 0.50 through 0.95 in 0.05 steps. The primary tIoU, angle/onset/offset,
duration, persistence, cooldown, and merge-gap values remain unset until chosen
from calibration or pilot method evidence without viewing an outer test result.

After the two-person pilot, freeze the labelbook, scenario schedule, capture settings, exclusion rules, split algorithm, primary estimand, metrics, and reporting templates. Engineering defects may be corrected after freeze, but every correction is versioned and its impact on already collected data is documented.

If the confirmatory hypothesis is not supported, report that result honestly. Do not relabel, hide source provenance, change the primary metric, or move samples between partitions to create a positive result.
