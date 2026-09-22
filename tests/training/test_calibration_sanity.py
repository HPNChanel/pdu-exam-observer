"""Correctness checks for calibration math — not performance claims."""

from __future__ import annotations

import numpy as np
import pytest

from pdu_exam_observer.contracts import ConfidenceStatus
from research.training.showcase.v3.calibration import (
    apply_fusion,
    apply_temperature,
    fit_logistic_fusion,
    fit_temperature,
    select_abstention_threshold,
    stable_softmax,
)


def test_stable_softmax_is_normalized_shift_invariant_and_overflow_safe() -> None:
    logits = np.array([[1000.0, 999.0, 998.0, 997.0], [0.0, 0.0, 0.0, 0.0]])
    probabilities = stable_softmax(logits)
    assert np.isfinite(probabilities).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)
    np.testing.assert_allclose(
        probabilities[0],
        stable_softmax(logits - 500.0)[0],
        rtol=1e-12,
    )
    assert probabilities[1].tolist() == [0.25, 0.25, 0.25, 0.25]


def test_stable_softmax_rejects_bad_shape_and_non_finite() -> None:
    with pytest.raises(ValueError):
        stable_softmax(np.zeros((2, 3)))
    with pytest.raises(ValueError):
        stable_softmax(np.array([[0.0, np.nan, 0.0, 0.0]]))
    with pytest.raises(ValueError):
        stable_softmax(np.array([[0.0, np.inf, 0.0, 0.0]]))


def test_temperature_moves_confidence_in_expected_direction() -> None:
    logits = np.array([[4.0, 1.0, 0.0, -1.0]])
    hot = apply_temperature(logits, 4.0)
    cold = apply_temperature(logits, 0.5)
    assert hot[0, 0] < apply_temperature(logits, 1.0)[0, 0] < cold[0, 0]
    for invalid in (0.0, -1.0, np.nan, np.inf):
        with pytest.raises(ValueError):
            apply_temperature(logits, invalid)


def test_fit_temperature_direction_on_known_fixtures() -> None:
    # Under-confident but correct: sharpening (T < 1) must lower NLL.
    correct_low_margin = np.tile(np.array([0.4, 0.2, 0.2, 0.2]), (40, 1))
    labels_zero = np.zeros(40, dtype=np.int64)
    assert fit_temperature(correct_low_margin, labels_zero) < 1.0

    # Over-confident and wrong: softening (T > 1) must lower NLL.
    wrong_high_margin = np.tile(np.array([-8.0, 8.0, 0.0, 0.0]), (40, 1))
    assert fit_temperature(wrong_high_margin, labels_zero) > 1.0


def test_fit_temperature_rejects_incompatible_inputs() -> None:
    logits = np.zeros((4, 4))
    with pytest.raises(ValueError):
        fit_temperature(logits, np.zeros(3, dtype=np.int64))
    with pytest.raises(ValueError):
        fit_temperature(logits, np.array([0, 1, 2, 4], dtype=np.int64))
    with pytest.raises(ValueError):
        fit_temperature(np.zeros((0, 4)), np.zeros(0, dtype=np.int64))


def test_fusion_fit_and_apply_roundtrip() -> None:
    rng = np.random.default_rng(7)
    labels = np.tile(np.arange(4, dtype=np.int64), 10)
    logits = rng.normal(size=(40, 4))
    logits[np.arange(40), labels] += 3.0
    context = rng.normal(size=(40, 6))
    fit = fit_logistic_fusion(logits, context, labels, seed=13)
    assert fit.coefficients.shape == (4, 10)
    assert fit.intercepts.shape == (4,)
    probabilities = apply_fusion(
        logits, context, fit.coefficients, fit.intercepts, temperature=1.0
    )
    assert probabilities.shape == (40, 4)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)


def test_apply_fusion_rejects_incompatible_shapes() -> None:
    weights = np.zeros((4, 10))
    bias = np.zeros(4)
    with pytest.raises(ValueError):
        apply_fusion(np.zeros((2, 4)), np.zeros((2, 5)), weights, bias)
    with pytest.raises(ValueError):
        apply_fusion(np.zeros((2, 4)), np.zeros((2, 6)), np.zeros((4, 9)), bias)
    with pytest.raises(ValueError):
        apply_fusion(np.zeros((2, 4)), np.zeros((2, 6)), weights, np.zeros(3))


def test_abstention_threshold_respects_minimum_coverage() -> None:
    probabilities = np.array(
        [
            [0.9, 0.05, 0.03, 0.02],
            [0.8, 0.1, 0.05, 0.05],
            [0.4, 0.3, 0.2, 0.1],
            [0.3, 0.3, 0.25, 0.15],
        ]
    )
    labels = np.array([0, 0, 1, 0], dtype=np.int64)
    threshold = select_abstention_threshold(
        probabilities, labels, minimum_coverage=0.5
    )
    accepted = probabilities.max(axis=1) >= threshold
    assert accepted.mean() >= 0.5
    for invalid in (0.0, -0.5, 1.01):
        with pytest.raises(ValueError):
            select_abstention_threshold(probabilities, labels, minimum_coverage=invalid)
    with pytest.raises(ValueError):
        select_abstention_threshold(
            np.zeros((2, 3)), np.zeros(2, dtype=np.int64)
        )


def test_confidence_status_values_are_bounded() -> None:
    assert set(ConfidenceStatus) == {
        ConfidenceStatus.MODEL_UNAVAILABLE,
        ConfidenceStatus.INSUFFICIENT,
        ConfidenceStatus.CALIBRATED,
        ConfidenceStatus.NOT_APPLICABLE,
    }
    for member in ConfidenceStatus:
        assert member.value == member.name
