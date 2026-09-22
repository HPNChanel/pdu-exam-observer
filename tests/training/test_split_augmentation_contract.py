from __future__ import annotations

import numpy as np
import pytest

from research.training.showcase.v3.augmentation import build_augmentation_plan
from research.training.showcase.v3.pipeline import Corpus, _assert_research_fold_sources
from research.training.showcase.v3.splits import (
    OuterFold,
    build_outer_folds,
    validate_fold_samples,
)


def test_five_folds_are_participant_disjoint_and_exclude_pilot() -> None:
    folds = build_outer_folds(tuple(f"P{i:02d}" for i in range(1, 13)), protocol_version="pdu-v1")

    assert len(folds) == 5
    for fold in folds:
        assert len(fold.train) == 6
        assert len(fold.calibration) == 2
        assert len(fold.test) == 2
        assert not (set(fold.train) & set(fold.calibration))
        assert not (set(fold.train) & set(fold.test))
        assert not (set(fold.calibration) & set(fold.test))
        assert "P01" not in fold.train + fold.calibration + fold.test
        assert "P02" not in fold.train + fold.calibration + fold.test


def test_split_gate_rejects_non_real_calibration_and_test_samples() -> None:
    fold = build_outer_folds(tuple(f"P{i:02d}" for i in range(1, 13)), protocol_version="pdu-v1")[0]
    samples = [
        {
            "sample_id": "aug-test",
            "participant_pseudonym": fold.test[0],
            "cohort": "CONFIRMATORY",
            "source_kind": "AUGMENTED",
            "parent_provenance_id": "parent",
        }
    ]

    with pytest.raises(ValueError, match="REAL"):
        validate_fold_samples(samples, fold)


def test_augmentation_is_train_only_and_parent_bound() -> None:
    fold = build_outer_folds(tuple(f"P{i:02d}" for i in range(1, 13)), protocol_version="pdu-v1")[0]
    parents = tuple(
        {
            "sample_id": f"{participant}-{label}-{index}",
            "participant_pseudonym": participant,
            "cohort": "CONFIRMATORY",
            "source_kind": "REAL",
            "parent_provenance_id": None,
            "label": label,
        }
        for participant in fold.train
        for label in (
            "NORMAL",
            "BENIGN_CONFOUNDER",
            "PROLONGED_HEAD_DOWN",
            "PROLONGED_SIDE_LOOK",
        )
        for index in range(2)
    )

    children = build_augmentation_plan(parents, fold=fold, seed=20260908)

    parent_ids = {str(parent["sample_id"]) for parent in parents}
    assert len(children) == len(parents)
    assert {child.source_kind for child in children} == {"AUGMENTED"}
    assert {child.parent_provenance_id for child in children} == parent_ids
    assert {child.participant_pseudonym for child in children} <= set(fold.train)
    with pytest.raises(ValueError, match="training partition"):
        build_augmentation_plan(
            (
                {
                    **parents[0],
                    "sample_id": "outer-test-parent",
                    "participant_pseudonym": fold.test[0],
                },
            ),
            fold=fold,
            seed=20260908,
        )


def test_imported_augmented_window_rejects_any_parent_outside_training() -> None:
    fold = OuterFold(0, ("P03",), ("P04",), ("P05",))
    corpus = Corpus(
        tensors=np.zeros((4, 5, 90, 33), dtype=np.float32),
        labels=np.zeros(4, dtype=np.int64),
        context=np.zeros((4, 6), dtype=np.float32),
        participants=("P03", "P03", "P04", "P05"),
        source_kinds=("REAL", "AUGMENTED", "REAL", "REAL"),
        sample_ids=("train-window", "child-window", "cal-window", "test-window"),
        dataset_manifest_sha256="0" * 64,
        protocol_version="test-v1",
        phases=("CONFIRMATORY",) * 4,
        parent_provenance_ids=((), ("train-frame", "test-frame"), (), ()),
        source_record_ids=(
            ("train-frame",),
            ("child-frame-1", "child-frame-2"),
            ("cal-frame",),
            ("test-frame",),
        ),
        record_provenance={
            "train-frame": ("P03", "REAL", "CONFIRMATORY"),
            "test-frame": ("P05", "REAL", "CONFIRMATORY"),
        },
    )

    with pytest.raises(ValueError, match="every augmented parent"):
        _assert_research_fold_sources(corpus, fold)
