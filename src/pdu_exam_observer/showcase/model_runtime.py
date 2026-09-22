"""NumPy and ONNX Runtime-only inference for an approved eight-file bundle."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import onnxruntime as ort  # type: ignore[import-untyped]
from numpy.typing import NDArray

from .model_import import BUNDLE_FILES, MAX_FILE_BYTES
from .preprocessing import PREPROCESSING_ID

CLASS_ORDER = (
    "NORMAL",
    "BENIGN_CONFOUNDER",
    "PROLONGED_HEAD_DOWN",
    "PROLONGED_SIDE_LOOK",
)
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


def aggregate_context_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    """Average exact per-frame context rows in the shared feature order."""

    if not rows:
        raise ValueError("context rows are empty")
    matrix: list[list[float]] = []
    for row in rows:
        if set(row) != set(CONTEXT_ORDER):
            raise ValueError("context row fields are incompatible")
        values: list[float] = []
        for name in CONTEXT_ORDER:
            value = row[name]
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError("context row value is not numeric")
            normalized = float(value)
            if not math.isfinite(normalized):
                raise ValueError("context row value is non-finite")
            values.append(normalized)
        matrix.append(values)
    aggregate = np.asarray(matrix, dtype=np.float64).mean(axis=0)
    return {name: float(aggregate[index]) for index, name in enumerate(CONTEXT_ORDER)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _softmax(logits: NDArray[np.floating]) -> NDArray[np.float64]:
    values = np.asarray(logits, dtype=np.float64)
    if values.shape != (4,) or not np.isfinite(values).all():
        raise ValueError("logits are invalid")
    shifted = values - values.max()
    exponential = np.exp(shifted)
    return np.asarray(exponential / exponential.sum(), dtype=np.float64)


class ModelRuntime:
    """Validated immutable ONNX session with calibrated camera and context decisions."""

    def __init__(
        self,
        *,
        status: str,
        session: Any | None = None,
        manifest: Mapping[str, Any] | None = None,
        calibration: Mapping[str, Any] | None = None,
        policy: Mapping[str, Any] | None = None,
    ) -> None:
        self.status = status
        self._session = session
        self.manifest = dict(manifest or {})
        self.calibration = dict(calibration or {})
        self.policy = dict(policy or {})

    @classmethod
    def from_bundle(cls, root: Path) -> ModelRuntime:
        if not root.is_dir() or root.is_symlink():
            return cls(status="MODEL_UNAVAILABLE")
        try:
            cls._verify_integrity(root)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return cls(status="MODEL_INTEGRITY_FAILED")
        try:
            manifest = _read_json(root / "manifest.json")
            calibration = _read_json(root / "calibration.json")
            policy = _read_json(root / "policy.json")
            cls._verify_contract(manifest, calibration, policy, root / "model.onnx")
            model_bytes = (root / "model.onnx").read_bytes()
            cls._verify_onnx_bytes(model_bytes)
            ort.disable_telemetry_events()
            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
            session = ort.InferenceSession(
                model_bytes,
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            cls._verify_session(session)
        except (OSError, UnicodeError, ValueError, TypeError, RuntimeError, json.JSONDecodeError):
            return cls(status="MODEL_INCOMPATIBLE")
        try:
            cls._verify_golden(root, session)
        except (OSError, ValueError, TypeError, RuntimeError, AssertionError, KeyError):
            return cls(status="GOLDEN_CHECK_FAILED")
        return cls(
            status="READY",
            session=session,
            manifest=manifest,
            calibration=calibration,
            policy=policy,
        )

    @staticmethod
    def _verify_onnx_bytes(model_bytes: bytes) -> None:
        """Reject every ONNX tensor that could resolve data outside the bundle."""

        model = onnx.load_model_from_string(model_bytes)

        def verify_tensor(tensor: Any) -> None:
            if tensor.data_location == onnx.TensorProto.EXTERNAL or tensor.external_data:
                raise ValueError("ONNX external tensor data is forbidden")

        def verify_sparse_tensor(tensor: Any) -> None:
            verify_tensor(tensor.values)
            verify_tensor(tensor.indices)

        def verify_attribute(attribute: Any) -> None:
            if attribute.type == onnx.AttributeProto.TENSOR:
                verify_tensor(attribute.t)
            elif attribute.type == onnx.AttributeProto.TENSORS:
                for tensor in attribute.tensors:
                    verify_tensor(tensor)
            elif attribute.type == onnx.AttributeProto.SPARSE_TENSOR:
                verify_sparse_tensor(attribute.sparse_tensor)
            elif attribute.type == onnx.AttributeProto.SPARSE_TENSORS:
                for tensor in attribute.sparse_tensors:
                    verify_sparse_tensor(tensor)
            elif attribute.type == onnx.AttributeProto.GRAPH:
                verify_graph(attribute.g)
            elif attribute.type == onnx.AttributeProto.GRAPHS:
                for graph in attribute.graphs:
                    verify_graph(graph)

        def verify_nodes(nodes: Any) -> None:
            for node in nodes:
                for attribute in node.attribute:
                    verify_attribute(attribute)

        def verify_graph(graph: Any) -> None:
            for tensor in graph.initializer:
                verify_tensor(tensor)
            for tensor in graph.sparse_initializer:
                verify_sparse_tensor(tensor)
            verify_nodes(graph.node)

        verify_graph(model.graph)
        for training in model.training_info:
            verify_graph(training.algorithm)
            verify_graph(training.initialization)
        for function in model.functions:
            verify_nodes(function.node)
        onnx.checker.check_model(model)

    @staticmethod
    def _verify_integrity(root: Path) -> None:
        paths = tuple(root.iterdir())
        if {path.name for path in paths} != BUNDLE_FILES:
            raise ValueError("bundle allowlist mismatch")
        if any(not path.is_file() or path.is_symlink() for path in paths):
            raise ValueError("bundle contains a non-regular file")
        if any(path.stat().st_size > MAX_FILE_BYTES[path.name] for path in paths):
            raise ValueError("bundle file exceeds size ceiling")
        checksums = _read_json(root / "checksums.json")
        expected = checksums.get("files")
        if (
            checksums.get("schema_version") != 1
            or checksums.get("algorithm") != "SHA-256"
            or not isinstance(expected, dict)
            or set(expected) != BUNDLE_FILES - {"checksums.json"}
        ):
            raise ValueError("checksum contract is invalid")
        for name, digest in expected.items():
            if not isinstance(digest, str) or len(digest) != 64 or _sha256(root / name) != digest:
                raise ValueError("bundle checksum mismatch")

    @staticmethod
    def _verify_contract(
        manifest: Mapping[str, Any],
        calibration: Mapping[str, Any],
        policy: Mapping[str, Any],
        model_path: Path,
    ) -> None:
        expected = {
            "schema_version": 1,
            "runtime_schema_min": 1,
            "runtime_schema_max": 1,
            "preprocessing_id": PREPROCESSING_ID,
            "topology": "mediapipe-33-v1",
            "fps": 15,
            "window_frames": 90,
            "input_name": "pose_sequence",
            "input_shape": [None, 5, 90, 33],
            "output_name": "camera_logits",
            "output_shape": [None, 4],
            "class_order": list(CLASS_ORDER),
            "context_order": list(CONTEXT_ORDER),
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("manifest tensor contract is incompatible")
        if manifest.get("training_mode") not in {"SYNTHETIC_SMOKE", "RESEARCH"}:
            raise ValueError("manifest training mode is invalid")
        if manifest.get("training_mode") == "SYNTHETIC_SMOKE" and (
            manifest.get("demo_only") is not True
            or manifest.get("claim_status") != "DEMO_ONLY_NOT_RESEARCH_PERFORMANCE"
        ):
            raise ValueError("synthetic model boundary is invalid")
        if manifest.get("training_mode") == "RESEARCH" and (
            manifest.get("demo_only") is not False
            or manifest.get("research_ready") is not True
            or not isinstance(manifest.get("protocol_freeze_sha256"), str)
            or len(str(manifest.get("protocol_freeze_sha256"))) != 64
        ):
            raise ValueError("research model authority boundary is invalid")
        if manifest.get("model_sha256") != _sha256(model_path):
            raise ValueError("manifest model digest is invalid")
        for key in ("model_version", "policy_version", "dataset_manifest_sha256"):
            value = manifest.get(key)
            if not isinstance(value, str) or not value or len(value) > 128:
                raise ValueError("manifest version/dataset identifier is invalid")
        if (
            calibration.get("schema_version") != 1
            or calibration.get("fit_partition")
            not in {"CALIBRATION_PARTICIPANT_DISJOINT", "SYNTHETIC_SMOKE_CALIBRATION"}
            or calibration.get("feature_order") != list(FUSION_FEATURE_ORDER)
            or calibration.get("class_order") != list(CLASS_ORDER)
        ):
            raise ValueError("calibration contract is incompatible")
        camera_temperature = _finite_float(
            calibration.get("camera_temperature"), "camera_temperature"
        )
        fusion_temperature = _finite_float(
            calibration.get("fusion_temperature"), "fusion_temperature"
        )
        coefficients = np.asarray(calibration.get("fusion_coefficients"), dtype=np.float64)
        intercepts = np.asarray(calibration.get("fusion_intercepts"), dtype=np.float64)
        if (
            camera_temperature <= 0
            or fusion_temperature <= 0
            or coefficients.shape != (4, 10)
            or intercepts.shape != (4,)
            or not np.isfinite(coefficients).all()
            or not np.isfinite(intercepts).all()
        ):
            raise ValueError("calibration numeric contract is incompatible")
        threshold = _finite_float(policy.get("abstention_threshold"), "abstention_threshold")
        if (
            policy.get("schema_version") != 1
            or policy.get("policy_version") != manifest.get("policy_version")
            or policy.get("selection_partition")
            not in {"CALIBRATION_PARTICIPANT_DISJOINT", "SYNTHETIC_SMOKE_CALIBRATION"}
            or policy.get("operator_outcome_on_abstention") != "TECHNICAL_INSUFFICIENT"
            or not 0 <= threshold <= 1
        ):
            raise ValueError("policy contract is incompatible")

    @staticmethod
    def _verify_session(session: Any) -> None:
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if (
            len(inputs) != 1
            or inputs[0].name != "pose_sequence"
            or list(inputs[0].shape[1:]) != [5, 90, 33]
            or inputs[0].type != "tensor(float)"
            or len(outputs) != 1
            or outputs[0].name != "camera_logits"
            or list(outputs[0].shape[1:]) != [4]
            or outputs[0].type != "tensor(float)"
            or session.get_providers() != ["CPUExecutionProvider"]
        ):
            raise ValueError("ONNX session contract is incompatible")

    @staticmethod
    def _verify_golden(root: Path, session: Any) -> None:
        with np.load(root / "golden_inputs.npz", allow_pickle=False) as archive:
            if archive.files != ["pose_sequence"]:
                raise ValueError("golden inputs are incompatible")
            inputs = archive["pose_sequence"].astype(np.float32, copy=False)
        with np.load(root / "golden_outputs.npz", allow_pickle=False) as archive:
            if archive.files != ["camera_logits"]:
                raise ValueError("golden outputs are incompatible")
            expected = archive["camera_logits"].astype(np.float32, copy=False)
        if (
            inputs.ndim != 4
            or inputs.shape[1:] != (5, 90, 33)
            or expected.shape != (len(inputs), 4)
        ):
            raise ValueError("golden tensor shape is incompatible")
        actual = np.asarray(
            session.run(["camera_logits"], {"pose_sequence": inputs})[0], dtype=np.float32
        )
        if not np.isfinite(actual).all():
            raise ValueError("golden inference is non-finite")
        np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-5)

    def infer_pose_tensor(
        self,
        pose_tensor: Any,
        *,
        context: Mapping[str, float] | None,
        source_kind: str,
    ) -> Mapping[str, object] | None:
        if self.status != "READY" or self._session is None:
            return None
        if source_kind == "REAL" and (
            self.manifest.get("training_mode") != "RESEARCH"
            or self.manifest.get("research_ready") is not True
            or self.manifest.get("demo_only") is not False
        ):
            return None
        tensor = np.asarray(pose_tensor, dtype=np.float32)
        if tensor.ndim != 4 or tensor.shape[1:] != (5, 90, 33) or not np.isfinite(tensor).all():
            return None
        try:
            logits = np.asarray(
                self._session.run(["camera_logits"], {"pose_sequence": tensor})[0],
                dtype=np.float64,
            )
        except (RuntimeError, ValueError, TypeError, KeyError):
            return None
        if logits.shape != (len(tensor), 4) or len(tensor) != 1 or not np.isfinite(logits).all():
            return None
        context_values: NDArray[np.float64] | None = None
        context_is_exact = False
        if context is not None and set(context) == set(CONTEXT_ORDER):
            context_is_exact = True
            raw_context = [context[name] for name in CONTEXT_ORDER]
            if any(
                isinstance(value, bool) or not isinstance(value, int | float)
                for value in raw_context
            ):
                context_is_exact = False
            else:
                context_values = np.asarray(raw_context, dtype=np.float64)
                if not np.isfinite(context_values).all():
                    context_is_exact = False
                    context_values = None
        if source_kind == "REAL" and not context_is_exact:
            return self._insufficient("RESEARCH_CONTEXT_REQUIRED")
        calibration = self.calibration
        camera_temperature = float(calibration["camera_temperature"])
        camera_probabilities = _softmax(logits[0] / camera_temperature)
        probabilities = camera_probabilities
        signal = "ST_GCN_90_FRAME_SEQUENCE"
        if context_values is not None:
            quality_min = float(self.policy.get("minimum_pose_visibility", 0.0))
            gap_max = float(self.policy.get("maximum_frame_gap_ratio", 1.0))
            focus_age_max = float(self.policy.get("maximum_scaled_focus_signal_age", 1.0))
            if (
                context_values[0] < quality_min
                or context_values[3] > gap_max
                or context_values[5] > focus_age_max
            ):
                return self._insufficient("QUALITY_OR_CONTEXT_INSUFFICIENT")
            coefficients = np.asarray(calibration["fusion_coefficients"], dtype=np.float64)
            intercepts = np.asarray(calibration["fusion_intercepts"], dtype=np.float64)
            fusion_features = np.concatenate((logits[0], context_values))
            fused_logits = fusion_features @ coefficients.T + intercepts
            probabilities = _softmax(fused_logits / float(calibration["fusion_temperature"]))
            signal = "CAMERA_QUALITY_FOCUS_FUSION"
            if float(probabilities.max()) < float(self.policy["abstention_threshold"]):
                return self._insufficient("LOW_CONFIDENCE_ABSTENTION")
        class_index = int(probabilities.argmax())
        label = CLASS_ORDER[class_index]
        return {
            "label": label,
            "research_label": label,
            "operator_outcome": (
                "NORMAL" if label in {"NORMAL", "BENIGN_CONFOUNDER"} else "REVIEW_REQUIRED"
            ),
            "confidence": float(probabilities[class_index]),
            "confidence_status": "CALIBRATED",
            "model_version": self.manifest["model_version"],
            "policy_version": self.manifest["policy_version"],
            "source_signals": (signal,),
        }

    def _insufficient(self, reason: str) -> Mapping[str, object]:
        return {
            "label": "TECHNICAL_INSUFFICIENT",
            "research_label": None,
            "operator_outcome": "TECHNICAL_INSUFFICIENT",
            "confidence": None,
            "confidence_status": "INSUFFICIENT",
            "model_version": self.manifest["model_version"],
            "policy_version": self.manifest["policy_version"],
            "source_signals": (reason,),
        }
