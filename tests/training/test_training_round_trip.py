from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np

from pdu_exam_observer.showcase.model_import import ModelRegistry
from research.training.showcase.v3.pipeline import run_synthetic_smoke


def test_cpu_tiny_training_onnx_import_and_inference_round_trip(tmp_path: Path) -> None:
    delivery = run_synthetic_smoke(tmp_path, epochs=1, samples_per_class_participant=1)

    assert delivery.model_zip.is_file()
    assert delivery.reports_zip.is_file()
    with zipfile.ZipFile(delivery.model_zip) as archive:
        assert set(archive.namelist()) == {
            "model.onnx",
            "manifest.json",
            "calibration.json",
            "policy.json",
            "checksums.json",
            "golden_inputs.npz",
            "golden_outputs.npz",
            "MODEL_CARD.md",
        }
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["training_mode"] == "SYNTHETIC_SMOKE"
        assert manifest["demo_only"] is True
        assert manifest["claim_status"] == "DEMO_ONLY_NOT_RESEARCH_PERFORMANCE"
    with zipfile.ZipFile(delivery.reports_zip) as archive:
        fold_report = json.loads(archive.read("fold_metrics.json"))
        assert len(fold_report["folds"]) == 5
        assert all(not fold["participant_overlap"] for fold in fold_report["folds"])
        assert all(not fold["pilot_included"] for fold in fold_report["folds"])

    registry = ModelRegistry(tmp_path / "registry")
    imported = registry.import_bundle(delivery.model_zip)
    assert imported.status == "READY"
    tensor = np.load(delivery.golden_inputs, allow_pickle=False)["pose_sequence"][:1]
    decision = registry.infer_pose_tensor(
        tensor,
        context={
            "visibility_mean": 0.9,
            "blur_score": 0.1,
            "exposure_score": 0.8,
            "frame_gap_ratio": 0.0,
            "focus_fraction": 1.0,
            "scaled_focus_signal_age": 0.0,
        },
        source_kind="SYNTHETIC_SMOKE",
    )
    assert decision is not None
    assert decision["confidence_status"] in {"CALIBRATED", "INSUFFICIENT"}
    assert (
        registry.model_provider(
            {
                "pose_tensor": tensor,
                "context": {
                    "visibility_mean": 0.9,
                    "blur_score": 0.1,
                    "exposure_score": 0.8,
                    "frame_gap_ratio": 0.0,
                    "focus_fraction": 1.0,
                    "scaled_focus_signal_age": 0.0,
                },
                "source_kind": "SYNTHETIC_SMOKE",
            }
        )
        is not None
    )
    assert (
        registry.infer_pose_tensor(
            tensor,
            context={},
            source_kind="REAL",
        )
        is None
    )
