"""Exact eight-file model bundle and separate report ZIP construction."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pdu_exam_observer.showcase.model_import import BUNDLE_FILES


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def _write_zip(path: Path, payloads: Mapping[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(payloads):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payloads[name])
    return path


def export_model_bundle(
    destination: Path,
    *,
    model_path: Path,
    manifest: dict[str, Any],
    calibration: Mapping[str, Any],
    policy: Mapping[str, Any],
    golden_inputs: NDArray[np.float32],
    golden_outputs: NDArray[np.float32],
    model_card: str,
) -> tuple[Path, Path, Path]:
    manifest = dict(manifest)
    model_bytes = model_path.read_bytes()
    manifest["model_sha256"] = hashlib.sha256(model_bytes).hexdigest()
    input_path = destination.parent / "golden_inputs.npz"
    output_path = destination.parent / "golden_outputs.npz"
    np.savez_compressed(input_path, pose_sequence=np.asarray(golden_inputs, dtype=np.float32))
    np.savez_compressed(output_path, camera_logits=np.asarray(golden_outputs, dtype=np.float32))
    payloads: dict[str, bytes] = {
        "model.onnx": model_bytes,
        "manifest.json": _json_bytes(manifest),
        "calibration.json": _json_bytes(calibration),
        "policy.json": _json_bytes(policy),
        "golden_inputs.npz": input_path.read_bytes(),
        "golden_outputs.npz": output_path.read_bytes(),
        "MODEL_CARD.md": model_card.encode("utf-8"),
    }
    payloads["checksums.json"] = _json_bytes(
        {
            "schema_version": 1,
            "algorithm": "SHA-256",
            "files": {
                name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())
            },
        }
    )
    if set(payloads) != BUNDLE_FILES:
        raise RuntimeError("model bundle payload set violates exact allowlist")
    return _write_zip(destination, payloads), input_path, output_path


def export_reports_zip(destination: Path, reports: Mapping[str, Mapping[str, Any] | str]) -> Path:
    payloads = {
        name: value.encode("utf-8") if isinstance(value, str) else _json_bytes(value)
        for name, value in reports.items()
    }
    return _write_zip(destination, payloads)
