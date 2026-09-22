from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pdu_exam_observer.showcase.preprocessing import (
    PREPROCESSING_ID,
    preprocess_primary_pose_arrays,
    resample_pose_window,
)


def _pose(frames: int) -> tuple[np.ndarray, np.ndarray]:
    landmarks = np.zeros((frames, 33, 4), dtype=np.float32)
    landmarks[..., 3] = 0.9
    landmarks[:, 11, :3] = (0.4, 0.3, 0.0)
    landmarks[:, 12, :3] = (0.6, 0.3, 0.0)
    landmarks[:, 23, :3] = (0.45, 0.6, 0.0)
    landmarks[:, 24, :3] = (0.55, 0.6, 0.0)
    landmarks[:, 0, 0] = np.linspace(0.45, 0.55, frames)
    landmarks[:, 0, 1] = 0.2
    return landmarks, np.ones((frames, 33), dtype=bool)


def test_timestamp_resampling_is_deterministic_and_preserves_missing_mask() -> None:
    landmarks, present = _pose(46)
    present[20, 7] = False
    timestamps_ns = np.arange(46, dtype=np.int64) * 133_333_333

    window = resample_pose_window(timestamps_ns, landmarks, present)

    assert window.preprocessing_id == PREPROCESSING_ID
    assert window.landmarks.shape == (90, 33, 4)
    assert window.present_mask.shape == (90, 33)
    assert window.tensor.shape == (1, 5, 90, 33)
    assert window.tensor.dtype == np.float32
    assert np.isfinite(window.tensor).all()
    assert np.any(~window.present_mask[:, 7])
    assert np.all(window.tensor[0, :4, ~window.present_mask] == 0.0)


def test_preprocessing_fails_closed_when_body_anchors_are_missing() -> None:
    landmarks, present = _pose(90)
    present[8, 23] = False

    with pytest.raises(ValueError, match="anchor"):
        preprocess_primary_pose_arrays(landmarks[None], present[None])


def test_checked_in_golden_fixture_matches_shared_preprocessing_bytes() -> None:
    fixture = (
        Path(__file__).resolve().parents[2]
        / "research"
        / "training"
        / "fixtures"
        / "preprocessing_golden.npz"
    )
    with np.load(fixture, allow_pickle=False) as archive:
        actual = resample_pose_window(
            archive["timestamps_ns"],
            archive["landmarks"],
            archive["present_mask"],
        )
        np.testing.assert_array_equal(actual.timestamps_ns, archive["resampled_timestamps_ns"])
        np.testing.assert_allclose(actual.tensor, archive["pose_sequence"], rtol=0, atol=0)
