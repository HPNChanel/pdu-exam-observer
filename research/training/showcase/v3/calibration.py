"""Calibration-only temperature, late-fusion, and abstention fitting."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .stgcn_mediapipe33 import CLASS_ORDER

CONTEXT_ORDER = (
    "visibility_mean",
    "blur_score",
    "exposure_score",
    "frame_gap_ratio",
    "focus_fraction",
    "scaled_focus_signal_age",
)
FUSION_FEATURE_ORDER = (
    *(f"camera_logit_{label}" for label in CLASS_ORDER),
    *CONTEXT_ORDER,
)


@dataclass(frozen=True, slots=True)
class FusionFit:
    coefficients: NDArray[np.float64]
    intercepts: NDArray[np.float64]
    probabilities: NDArray[np.float64]


def stable_softmax(logits: NDArray[np.floating]) -> NDArray[np.float64]:
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(CLASS_ORDER) or not np.isfinite(values).all():
        raise ValueError("logits must be finite [batch, 4]")
    shifted = values - values.max(axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / exponentials.sum(axis=1, keepdims=True)


def apply_temperature(logits: NDArray[np.floating], temperature: float) -> NDArray[np.float64]:
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    return stable_softmax(np.asarray(logits, dtype=np.float64) / temperature)


def fit_temperature(logits: NDArray[np.floating], labels: NDArray[np.integer]) -> float:
    """Fit one scalar on calibration rows only using deterministic log-space refinement."""

    values = np.asarray(logits, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    if values.shape != (len(targets), len(CLASS_ORDER)) or len(targets) == 0:
        raise ValueError("calibration logits and labels are incompatible")
    if np.any(targets < 0) or np.any(targets >= len(CLASS_ORDER)):
        raise ValueError("calibration label is invalid")
    lower, upper = -4.0, 4.0
    selected = 1.0
    for _ in range(5):
        candidates = np.exp(np.linspace(lower, upper, 81))
        losses = np.asarray(
            [
                -np.log(
                    np.clip(
                        apply_temperature(values, float(item))[np.arange(len(targets)), targets],
                        1e-12,
                        1.0,
                    )
                ).mean()
                for item in candidates
            ]
        )
        index = int(np.argmin(losses))
        selected = float(candidates[index])
        log_selected = math.log(selected)
        span = (upper - lower) / 10
        lower, upper = log_selected - span, log_selected + span
    return selected


def fit_logistic_fusion(
    camera_logits: NDArray[np.floating],
    context: NDArray[np.floating],
    labels: NDArray[np.integer],
    *,
    seed: int,
) -> FusionFit:
    """Fit the regularized multinomial fusion only on calibration participants."""

    from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

    logits = np.asarray(camera_logits, dtype=np.float64)
    context_values = np.asarray(context, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    if logits.shape != (len(targets), 4) or context_values.shape != (len(targets), 6):
        raise ValueError("fusion calibration shapes are incompatible")
    if set(targets.tolist()) != set(range(4)):
        raise ValueError("fusion calibration requires every learned class")
    features = np.concatenate((logits, context_values), axis=1)
    if not np.isfinite(features).all():
        raise ValueError("fusion features must be finite")
    estimator = LogisticRegression(
        C=1.0,
        solver="lbfgs",
        max_iter=500,
        random_state=seed,
    )
    estimator.fit(features, targets)
    if tuple(estimator.classes_) != tuple(range(4)):
        raise ValueError("fusion class order is incompatible")
    return FusionFit(
        coefficients=np.asarray(estimator.coef_, dtype=np.float64),
        intercepts=np.asarray(estimator.intercept_, dtype=np.float64),
        probabilities=np.asarray(estimator.predict_proba(features), dtype=np.float64),
    )


def apply_fusion(
    camera_logits: NDArray[np.floating],
    context: NDArray[np.floating],
    coefficients: NDArray[np.floating],
    intercepts: NDArray[np.floating],
    *,
    temperature: float = 1.0,
) -> NDArray[np.float64]:
    logits = np.asarray(camera_logits, dtype=np.float64)
    contexts = np.asarray(context, dtype=np.float64)
    weights = np.asarray(coefficients, dtype=np.float64)
    bias = np.asarray(intercepts, dtype=np.float64)
    if logits.ndim != 2 or logits.shape[1] != 4 or contexts.shape != (len(logits), 6):
        raise ValueError("fusion input shape is incompatible")
    if weights.shape != (4, 10) or bias.shape != (4,):
        raise ValueError("fusion parameter shape is incompatible")
    fused_logits = np.concatenate((logits, contexts), axis=1) @ weights.T + bias
    return apply_temperature(fused_logits, temperature)


def select_abstention_threshold(
    probabilities: NDArray[np.floating],
    labels: NDArray[np.integer],
    *,
    minimum_coverage: float = 0.75,
) -> float:
    values = np.asarray(probabilities, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    if values.shape != (len(targets), 4) or not 0 < minimum_coverage <= 1:
        raise ValueError("abstention calibration input is incompatible")
    confidence = values.max(axis=1)
    selected: tuple[float, float, float] | None = None
    for threshold in np.unique(np.concatenate(([0.0], confidence))):
        accepted = confidence >= threshold
        coverage = float(accepted.mean())
        if coverage < minimum_coverage:
            continue
        accuracy = float((values[accepted].argmax(axis=1) == targets[accepted]).mean())
        candidate = (accuracy, coverage, float(threshold))
        if selected is None or candidate > selected:
            selected = candidate
    if selected is None:
        raise ValueError("no abstention threshold satisfies coverage")
    return selected[2]
