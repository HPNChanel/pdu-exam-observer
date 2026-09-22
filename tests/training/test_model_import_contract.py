from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import onnx
import pytest
from onnx import helper

from pdu_exam_observer.showcase.model_import import (
    BUNDLE_FILES,
    BundleImportError,
    ModelRegistry,
)
from pdu_exam_observer.showcase.model_runtime import ModelRuntime, aggregate_context_rows


def _bundle_bytes(*, model_version: str = "demo-v1", extra: str | None = None) -> bytes:
    payloads = {
        "model.onnx": b"fake-onnx",
        "manifest.json": json.dumps(
            {
                "schema_version": 1,
                "runtime_schema_min": 1,
                "runtime_schema_max": 1,
                "model_version": model_version,
                "policy_version": "policy-v1",
                "preprocessing_id": "mediapipe33-bodycenter-resample90-v1",
            },
            sort_keys=True,
        ).encode(),
        "calibration.json": b"{}",
        "policy.json": b"{}",
        "golden_inputs.npz": b"inputs",
        "golden_outputs.npz": b"outputs",
        "MODEL_CARD.md": b"DEMO_ONLY\n",
    }
    payloads["checksums.json"] = json.dumps(
        {
            "schema_version": 1,
            "algorithm": "SHA-256",
            "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()},
        },
        sort_keys=True,
    ).encode()
    if extra is not None:
        payloads[extra] = b"forbidden"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)
    return output.getvalue()


def test_registry_imports_bytes_and_path_then_reports_active_status(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path / "models", validator=lambda _: "READY")

    first = registry.import_bundle(_bundle_bytes())
    bundle_path = tmp_path / "second.zip"
    bundle_path.write_bytes(_bundle_bytes(model_version="demo-v2"))
    second = registry.import_bundle(bundle_path)

    assert first.status == "READY"
    assert second.status == "READY"
    assert registry.status()["status"] == "READY"
    assert registry.status()["bundle_sha256"] == second.bundle_sha256
    assert set(path.name for path in second.bundle_path.iterdir()) == BUNDLE_FILES


def test_failed_import_keeps_previous_active_pointer_atomic(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path / "models", validator=lambda _: "READY")
    accepted = registry.import_bundle(_bundle_bytes())

    with pytest.raises(BundleImportError, match="allowlist"):
        registry.import_bundle(_bundle_bytes(extra="evil.py"))

    assert registry.status()["bundle_sha256"] == accepted.bundle_sha256
    assert not list((tmp_path / "models").glob(".staging-*"))


def test_registry_model_provider_fails_closed_without_tensor_input(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path / "models", validator=lambda _: "READY")
    registry.import_bundle(_bundle_bytes())

    assert registry.model_provider({"head_down_degrees": 30.0}) is None


def test_status_fails_closed_for_non_object_pointer_and_tampered_active_file(
    tmp_path: Path,
) -> None:
    registry = ModelRegistry(tmp_path / "models", validator=lambda _: "READY")
    accepted = registry.import_bundle(_bundle_bytes())
    pointer = tmp_path / "models" / "active.json"

    pointer.write_text("[]", encoding="utf-8")
    assert registry.status()["status"] == "MODEL_UNAVAILABLE"

    pointer.write_text(
        json.dumps({"schema_version": 1, "bundle_sha256": accepted.bundle_sha256}),
        encoding="utf-8",
    )
    (accepted.bundle_path / "MODEL_CARD.md").write_text("tampered", encoding="utf-8")
    assert registry.status()["status"] == "MODEL_INTEGRITY_FAILED"


def test_import_bytes_returns_workspace_facade_shape(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path / "models", validator=lambda _: "READY")

    result = registry.import_bytes(_bundle_bytes())

    assert result["status"] == "READY"
    assert result["model_version"] == "demo-v1"
    assert result["bundle_sha256"] == registry.status()["bundle_sha256"]


class _LogitSession:
    def run(self, _outputs: object, _inputs: object) -> list[np.ndarray]:
        return [np.zeros((1, 4), dtype=np.float32)]


def _research_runtime() -> ModelRuntime:
    return ModelRuntime(
        status="READY",
        session=_LogitSession(),
        manifest={
            "training_mode": "RESEARCH",
            "research_ready": True,
            "demo_only": False,
            "model_version": "research-v1",
            "policy_version": "policy-v1",
        },
        calibration={"camera_temperature": 1.0},
        policy={},
    )


def test_research_runtime_fails_closed_without_exact_context() -> None:
    runtime = _research_runtime()
    tensor = np.zeros((1, 5, 90, 33), dtype=np.float32)

    for context in (None, {}, {"visibility_mean": float("nan")}):
        decision = runtime.infer_pose_tensor(tensor, context=context, source_kind="REAL")
        assert decision is not None
        assert decision["operator_outcome"] == "TECHNICAL_INSUFFICIENT"
        assert decision["source_signals"] == ("RESEARCH_CONTEXT_REQUIRED",)


def test_context_aggregation_averages_all_six_features() -> None:
    first = {
        "visibility_mean": 0.8,
        "blur_score": 0.2,
        "exposure_score": 0.4,
        "frame_gap_ratio": 0.0,
        "focus_fraction": 1.0,
        "scaled_focus_signal_age": 0.0,
    }
    second = {name: value + 0.2 for name, value in first.items()}

    aggregate = aggregate_context_rows((first, second))

    assert aggregate == pytest.approx({name: value + 0.1 for name, value in first.items()})


def test_onnx_external_tensor_data_is_rejected_before_runtime() -> None:
    external = onnx.TensorProto()
    external.name = "external_weight"
    external.data_type = onnx.TensorProto.FLOAT
    external.dims.extend([1])
    external.data_location = onnx.TensorProto.EXTERNAL
    location = external.external_data.add()
    location.key = "location"
    location.value = "../../outside.bin"
    graph = helper.make_graph(
        [helper.make_node("Identity", ["external_weight"], ["output"])],
        "external-graph",
        [],
        [helper.make_tensor_value_info("output", onnx.TensorProto.FLOAT, [1])],
        [external],
    )
    model = helper.make_model(graph)

    with pytest.raises(ValueError, match="external tensor"):
        ModelRuntime._verify_onnx_bytes(model.SerializeToString())
