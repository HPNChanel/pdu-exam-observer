"""Versioned MediaPipe-33 resampling and body-centred preprocessing.

This NumPy-only module is the single preprocessing implementation imported by
both the local runtime and the Colab training package.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

PREPROCESSING_ID = "mediapipe33-bodycenter-resample90-v1"
TARGET_FPS = 15
WINDOW_FRAMES = 90
LANDMARK_COUNT = 33
LANDMARK_ATTRIBUTES = 4
ANCHOR_INDICES = (11, 12, 23, 24)


@dataclass(frozen=True, slots=True)
class PreprocessedPoseWindow:
    preprocessing_id: str
    tensor: NDArray[np.float32]
    landmarks: NDArray[np.float32]
    present_mask: NDArray[np.bool_]
    timestamps_ns: NDArray[np.int64]


def preprocess_primary_pose_arrays(
    landmarks: NDArray[np.floating], present_mask: NDArray[np.bool_]
) -> NDArray[np.float32]:
    """Normalize finite ``[batch, 90, 33, 4]`` arrays into ``[batch, 5, 90, 33]``."""

    values = np.asarray(landmarks, dtype=np.float32)
    present = np.asarray(present_mask, dtype=bool)
    if values.ndim != 4 or values.shape[1:] != (
        WINDOW_FRAMES,
        LANDMARK_COUNT,
        LANDMARK_ATTRIBUTES,
    ):
        raise ValueError("landmarks must have shape [batch, 90, 33, 4]")
    if present.shape != values.shape[:-1]:
        raise ValueError("present_mask shape is incompatible")
    if not np.isfinite(values).all():
        raise ValueError("landmarks must be finite")
    if np.any((values[..., 3] < 0.0) | (values[..., 3] > 1.0)):
        raise ValueError("visibility must be within [0, 1]")
    if not np.all(present[..., ANCHOR_INDICES]):
        raise ValueError("body-center anchor landmark is missing")

    hips = (values[:, :, 23, :3] + values[:, :, 24, :3]) / 2.0
    shoulders = (values[:, :, 11, :3] + values[:, :, 12, :3]) / 2.0
    scale = np.linalg.norm(shoulders - hips, axis=-1)
    if not np.isfinite(scale).all() or np.any(scale <= 1e-6):
        raise ValueError("body-center anchor scale is invalid")

    normalized = (values[..., :3] - hips[:, :, None, :]) / scale[:, :, None, None]
    tensor = np.zeros((values.shape[0], 5, WINDOW_FRAMES, LANDMARK_COUNT), dtype=np.float32)
    tensor[:, :3] = np.moveaxis(np.where(present[..., None], normalized, 0.0), -1, 1)
    tensor[:, 3] = np.where(present, values[..., 3], 0.0)
    tensor[:, 4] = present.astype(np.float32)
    if not np.isfinite(tensor).all():
        raise ValueError("preprocessed tensor is non-finite")
    return tensor


def _validate_source(
    timestamps_ns: NDArray[np.integer],
    landmarks: NDArray[np.floating],
    present_mask: NDArray[np.bool_],
) -> tuple[NDArray[np.int64], NDArray[np.float32], NDArray[np.bool_]]:
    timestamps = np.asarray(timestamps_ns, dtype=np.int64)
    values = np.asarray(landmarks, dtype=np.float32)
    present = np.asarray(present_mask, dtype=bool)
    if timestamps.ndim != 1 or len(timestamps) < 2:
        raise ValueError("at least two source timestamps are required")
    if values.shape != (len(timestamps), LANDMARK_COUNT, LANDMARK_ATTRIBUTES):
        raise ValueError("source landmarks have incompatible shape")
    if present.shape != values.shape[:-1]:
        raise ValueError("source present mask has incompatible shape")
    if np.any(np.diff(timestamps) <= 0):
        raise ValueError("source timestamps must be strictly increasing")
    if not np.isfinite(values).all():
        raise ValueError("source landmarks must be finite")
    if np.any((values[..., 3] < 0.0) | (values[..., 3] > 1.0)):
        raise ValueError("source visibility must be within [0, 1]")
    return timestamps, values, present


def resample_pose_window(
    timestamps_ns: NDArray[np.integer],
    landmarks: NDArray[np.floating],
    present_mask: NDArray[np.bool_],
    *,
    target_fps: int = TARGET_FPS,
    window_frames: int = WINDOW_FRAMES,
) -> PreprocessedPoseWindow:
    """Linearly resample one primary pose without inventing missing landmarks."""

    if target_fps != TARGET_FPS or window_frames != WINDOW_FRAMES:
        raise ValueError("unsupported preprocessing window contract")
    timestamps, values, present = _validate_source(timestamps_ns, landmarks, present_mask)
    step_ns = 1_000_000_000 / target_fps
    target_float = timestamps[0] + np.arange(window_frames, dtype=np.float64) * step_ns
    if target_float[-1] > timestamps[-1]:
        raise ValueError("source timeline does not cover the full six-second window")
    target = np.rint(target_float).astype(np.int64)
    right = np.searchsorted(timestamps, target, side="left")
    right = np.clip(right, 1, len(timestamps) - 1)
    left = right - 1
    exact_right = timestamps[right] == target
    left = np.where(exact_right, right, left)
    denominator = timestamps[right] - timestamps[left]
    weight = np.divide(
        target - timestamps[left],
        denominator,
        out=np.zeros(window_frames, dtype=np.float64),
        where=denominator != 0,
    ).astype(np.float32)
    target_present = present[left] & present[right]
    interpolated = values[left] + (values[right] - values[left]) * weight[:, None, None]
    interpolated = np.where(target_present[..., None], interpolated, 0.0).astype(np.float32)
    tensor = preprocess_primary_pose_arrays(interpolated[None], target_present[None])
    return PreprocessedPoseWindow(
        preprocessing_id=PREPROCESSING_ID,
        tensor=tensor,
        landmarks=interpolated,
        present_mask=target_present,
        timestamps_ns=target,
    )
