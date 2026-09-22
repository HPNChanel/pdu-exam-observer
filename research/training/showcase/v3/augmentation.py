"""Deterministic train-only pose augmentation plans with parent provenance."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass

from .splits import OuterFold

CLASS_ORDER = (
    "NORMAL",
    "BENIGN_CONFOUNDER",
    "PROLONGED_HEAD_DOWN",
    "PROLONGED_SIDE_LOOK",
)


@dataclass(frozen=True, slots=True)
class AugmentationRecord:
    sample_id: str
    parent_provenance_id: str
    participant_pseudonym: str
    label: str
    source_kind: str
    transform_manifest: Mapping[str, object]


def build_augmentation_plan(
    parents: tuple[Mapping[str, object], ...], *, fold: OuterFold, seed: int
) -> tuple[AugmentationRecord, ...]:
    """Create one deterministic child per eligible real parent in this fold's train set."""

    if seed < 0:
        raise ValueError("seed must be non-negative")
    seen: set[str] = set()
    output: list[AugmentationRecord] = []
    for ordinal, parent in enumerate(sorted(parents, key=lambda row: str(row.get("sample_id")))):
        parent_id = parent.get("sample_id")
        participant = parent.get("participant_pseudonym")
        label = parent.get("label")
        if (
            not isinstance(parent_id, str)
            or not parent_id
            or parent_id in seen
            or participant not in fold.train
            or parent.get("cohort") != "CONFIRMATORY"
            or parent.get("source_kind") != "REAL"
            or parent.get("parent_provenance_id") is not None
            or label not in CLASS_ORDER
        ):
            raise ValueError(
                "augmentation parents must be unique REAL samples in training partition"
            )
        seen.add(parent_id)
        digest = hashlib.sha256(f"augmentation-v3:{seed}:{parent_id}".encode()).hexdigest()
        output.append(
            AugmentationRecord(
                sample_id=f"aug-{digest[:32]}",
                parent_provenance_id=parent_id,
                participant_pseudonym=str(participant),
                label=str(label),
                source_kind="AUGMENTED",
                transform_manifest={
                    "schema_version": 1,
                    "transform_id": "pose-jitter-shift-dropout-v1",
                    "seed": seed,
                    "ordinal": ordinal,
                    "coordinate_jitter_std": 0.005,
                    "scale_range": [0.97, 1.03],
                    "translation_range": [-0.015, 0.015],
                    "temporal_shift_frames": [-2, 2],
                    "landmark_dropout_max_fraction": 0.03,
                },
            )
        )
    return tuple(output)
