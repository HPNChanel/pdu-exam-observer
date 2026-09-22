"""MediaPipe-33 ST-GCN adapted from a pinned Hugging Face architecture reference.

The upstream reference uses a 22-node graph. This module defines a new
MediaPipe-33 graph and initializes all weights from scratch. PyTorch is imported
only inside ``build_stgcn_mediapipe33`` for Colab use.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
from numpy.typing import NDArray

CLASS_ORDER = (
    "NORMAL",
    "BENIGN_CONFOUNDER",
    "PROLONGED_HEAD_DOWN",
    "PROLONGED_SIDE_LOOK",
)

MEDIAPIPE_33_EDGES = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (0, 9),
    (0, 10),
    (0, 11),
    (0, 12),
    (9, 10),
    (11, 12),
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (24, 26),
    (25, 27),
    (26, 28),
    (27, 29),
    (28, 30),
    (29, 31),
    (30, 32),
    (27, 31),
    (28, 32),
)


def _hip_distance() -> tuple[int, ...]:
    neighbors: list[list[int]] = [[] for _ in range(33)]
    for left, right in MEDIAPIPE_33_EDGES:
        neighbors[left].append(right)
        neighbors[right].append(left)
    distances = [10_000] * 33
    queue: deque[int] = deque((23, 24))
    distances[23] = 0
    distances[24] = 0
    while queue:
        node = queue.popleft()
        for neighbor in neighbors[node]:
            if distances[neighbor] > distances[node] + 1:
                distances[neighbor] = distances[node] + 1
                queue.append(neighbor)
    if any(value == 10_000 for value in distances):
        raise RuntimeError("MediaPipe graph contains a disconnected node")
    return tuple(distances)


def _column_normalize(adjacency: NDArray[np.float64]) -> NDArray[np.float64]:
    degree = adjacency.sum(axis=0)
    output = adjacency.copy()
    nonzero = degree > 0
    output[:, nonzero] /= degree[nonzero]
    return output


def mediapipe33_spatial_partitions() -> NDArray[np.float32]:
    """Return root, centripetal, and centrifugal adjacency partitions."""

    distances = _hip_distance()
    root = np.eye(33, dtype=np.float64)
    centripetal = np.zeros((33, 33), dtype=np.float64)
    centrifugal = np.zeros((33, 33), dtype=np.float64)
    for left, right in MEDIAPIPE_33_EDGES:
        if distances[left] == distances[right]:
            root[left, right] = 1.0
            root[right, left] = 1.0
        elif distances[left] < distances[right]:
            centripetal[left, right] = 1.0
            centrifugal[right, left] = 1.0
        else:
            centripetal[right, left] = 1.0
            centrifugal[left, right] = 1.0
    partitions = np.stack(
        tuple(_column_normalize(value) for value in (root, centripetal, centrifugal))
    )
    return partitions.astype(np.float32)


def build_stgcn_mediapipe33(*, widths: tuple[int, int, int] = (32, 64, 64)) -> Any:
    """Build the Colab-only 5→32→64→64 ST-GCN with three graph partitions."""

    import torch
    from torch import nn

    class SpatialGraphConvolution(nn.Module):
        def __init__(self, input_channels: int, output_channels: int) -> None:
            super().__init__()
            self.partitions = 3
            self.output_channels = output_channels
            self.projection = nn.Conv2d(
                input_channels,
                output_channels * self.partitions,
                kernel_size=1,
                bias=False,
            )

        def forward(self, inputs: Any, adjacency: Any) -> Any:
            projected = self.projection(inputs)
            batch, _, time, nodes = projected.shape
            projected = projected.view(batch, self.partitions, self.output_channels, time, nodes)
            return torch.einsum("nkctv,kvw->nctw", projected, adjacency)

    class StgcnBlock(nn.Module):
        def __init__(self, input_channels: int, output_channels: int) -> None:
            super().__init__()
            self.spatial = SpatialGraphConvolution(input_channels, output_channels)
            self.temporal = nn.Sequential(
                nn.BatchNorm2d(output_channels),
                nn.ReLU(inplace=False),
                nn.Conv2d(
                    output_channels,
                    output_channels,
                    kernel_size=(9, 1),
                    padding=(4, 0),
                    bias=False,
                ),
                nn.BatchNorm2d(output_channels),
            )
            self.residual = (
                nn.Identity()
                if input_channels == output_channels
                else nn.Conv2d(input_channels, output_channels, kernel_size=1, bias=False)
            )
            self.activation = nn.ReLU(inplace=False)

        def forward(self, inputs: Any, adjacency: Any) -> Any:
            features = self.temporal(self.spatial(inputs, adjacency))
            return self.activation(features + self.residual(inputs))

    class MediaPipe33Stgcn(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.register_buffer(
                "adjacency",
                torch.from_numpy(mediapipe33_spatial_partitions()),
                persistent=True,
            )
            first, second, third = widths
            self.block1 = StgcnBlock(5, first)
            self.block2 = StgcnBlock(first, second)
            self.block3 = StgcnBlock(second, third)
            self.classifier = nn.Linear(third, len(CLASS_ORDER))

        def forward(self, inputs: Any) -> Any:
            features = self.block1(inputs, self.adjacency)
            features = self.block2(features, self.adjacency)
            features = self.block3(features, self.adjacency)
            return self.classifier(features.mean(dim=(2, 3)))

    return MediaPipe33Stgcn()
