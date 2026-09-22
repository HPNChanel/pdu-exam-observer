"""Build deterministic training notebook/fixtures and optionally run CPU smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_preprocessing_fixture() -> tuple[Path, Path]:
    from pdu_exam_observer.showcase.preprocessing import (
        PREPROCESSING_ID,
        resample_pose_window,
    )

    fixture_root = ROOT / "research" / "training" / "fixtures"
    fixture_root.mkdir(parents=True, exist_ok=True)
    frames = 46
    timestamps = np.arange(frames, dtype=np.int64) * 133_333_333
    landmarks = np.zeros((frames, 33, 4), dtype=np.float32)
    landmarks[..., 3] = 0.9
    landmarks[:, 11, :3] = (0.4, 0.3, 0.0)
    landmarks[:, 12, :3] = (0.6, 0.3, 0.0)
    landmarks[:, 23, :3] = (0.45, 0.6, 0.0)
    landmarks[:, 24, :3] = (0.55, 0.6, 0.0)
    landmarks[:, 0, 0] = np.linspace(0.45, 0.55, frames)
    landmarks[:, 0, 1] = 0.2
    present = np.ones((frames, 33), dtype=bool)
    present[20, 7] = False
    prepared = resample_pose_window(timestamps, landmarks, present)
    fixture_path = fixture_root / "preprocessing_golden.npz"
    np.savez_compressed(
        fixture_path,
        timestamps_ns=timestamps,
        landmarks=landmarks,
        present_mask=present,
        resampled_timestamps_ns=prepared.timestamps_ns,
        pose_sequence=prepared.tensor,
    )
    manifest = {
        "schema_version": 1,
        "preprocessing_id": PREPROCESSING_ID,
        "fixture_sha256": _sha256(fixture_path),
        "preprocessing_source_sha256": _sha256(
            ROOT / "src" / "pdu_exam_observer" / "showcase" / "preprocessing.py"
        ),
        "claim_status": "GOLDEN_NUMERIC_CONTRACT_ONLY",
    }
    manifest_path = fixture_root / "preprocessing_golden.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return fixture_path, manifest_path


def build_synthetic_smoke_fixture() -> tuple[Path, Path]:
    from research.training.showcase.v3.pipeline import SEED, build_synthetic_corpus

    fixture_root = ROOT / "research" / "training" / "fixtures"
    fixture_root.mkdir(parents=True, exist_ok=True)
    corpus = build_synthetic_corpus(samples_per_class_participant=1)
    fixture_path = fixture_root / "synthetic_smoke_input.npz"
    np.savez_compressed(
        fixture_path,
        tensors=corpus.tensors,
        labels=corpus.labels,
        context=corpus.context,
        participants=np.asarray(corpus.participants),
        source_kinds=np.asarray(corpus.source_kinds),
        sample_ids=np.asarray(corpus.sample_ids),
    )
    manifest = {
        "schema_version": 1,
        "claim_status": "DEMO_ONLY_SYNTHETIC_SMOKE_INPUT",
        "seed": SEED,
        "fixture_sha256": _sha256(fixture_path),
        "tensor_shape": list(corpus.tensors.shape),
        "context_shape": list(corpus.context.shape),
        "class_count": 4,
        "participant_count": len(set(corpus.participants)),
    }
    manifest_path = fixture_root / "synthetic_smoke_input.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return fixture_path, manifest_path


def build_colab_delivery(destination: Path) -> Path:
    from research.training.showcase.v3.export_bundle import _write_zip

    training_root = ROOT / "research" / "training" / "showcase" / "v3"
    synthetic, synthetic_manifest = build_synthetic_smoke_fixture()
    files = {
        "pdu_stgcn_training_colab.ipynb": training_root / "pdu_stgcn_training_colab.ipynb",
        "requirements-colab.txt": training_root / "requirements-colab.txt",
        "training_config.json": training_root / "training_config.json",
        "protocol-freeze.template.json": training_root / "protocol-freeze.template.json",
        "hf_source_lock.json": training_root / "hf_source_lock.json",
        "NOTICE.md": training_root / "NOTICE.md",
        "TRAINING_README.md": training_root / "TRAINING_README.md",
        "fixtures/preprocessing_golden.npz": (
            ROOT / "research" / "training" / "fixtures" / "preprocessing_golden.npz"
        ),
        "fixtures/preprocessing_golden.manifest.json": (
            ROOT
            / "research"
            / "training"
            / "fixtures"
            / "preprocessing_golden.manifest.json"
        ),
        "fixtures/synthetic_smoke_input.npz": synthetic,
        "fixtures/synthetic_smoke_input.manifest.json": synthetic_manifest,
    }
    return _write_zip(destination, {name: path.read_bytes() for name, path in files.items()})


def main() -> None:
    from research.training.showcase.v3.build_self_contained_notebook import build_notebook

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "completion-2026-09-08" / "training-delivery",
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    fixture, fixture_manifest = build_preprocessing_fixture()
    notebook = build_notebook()
    colab_delivery = build_colab_delivery(args.output / "pdu-stgcn-colab-delivery.zip")
    result: dict[str, object] = {
        "schema_version": 1,
        "claim_status": "LOCAL_BUILD_ONLY",
        "notebook": str(notebook),
        "notebook_sha256": _sha256(notebook),
        "preprocessing_fixture": str(fixture),
        "preprocessing_fixture_sha256": _sha256(fixture),
        "preprocessing_fixture_manifest": str(fixture_manifest),
        "synthetic_smoke_fixture": str(
            ROOT / "research" / "training" / "fixtures" / "synthetic_smoke_input.npz"
        ),
        "colab_delivery_zip": str(colab_delivery),
        "colab_delivery_zip_sha256": _sha256(colab_delivery),
    }
    if args.smoke:
        from research.training.showcase.v3.pipeline import run_synthetic_smoke

        delivery = run_synthetic_smoke(args.output, epochs=1)
        result["claim_status"] = "LOCAL_SYNTHETIC_CPU_TRAINING_ONNX_IMPORT_READY"
        result["model_zip"] = str(delivery.model_zip)
        result["model_zip_sha256"] = _sha256(delivery.model_zip)
        result["reports_zip"] = str(delivery.reports_zip)
        result["reports_zip_sha256"] = _sha256(delivery.reports_zip)
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = args.output / "training-build-receipt.json"
    receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(receipt)


if __name__ == "__main__":
    main()
