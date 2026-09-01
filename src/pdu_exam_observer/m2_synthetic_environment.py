"""Canonical source bindings for the synthetic M2 evidence pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pdu_exam_observer.m2_synthetic_integration import SyntheticEnvironmentBindings

BOUND_SOURCE_RELATIVE_PATHS = (
    "src/pdu_exam_observer/m2_synthetic.py",
    "src/pdu_exam_observer/m2_d1_contract.py",
    "src/pdu_exam_observer/m2_persistence.py",
    "src/pdu_exam_observer/m2_synthetic_integration.py",
    "src/pdu_exam_observer/m2_synthetic_preflight_fixture.py",
    "src/pdu_exam_observer/m2_synthetic_nominal_fixture.py",
    "src/pdu_exam_observer/m2_synthetic_review.py",
    "src/pdu_exam_observer/m2_synthetic_evidence.py",
    "src/pdu_exam_observer/m2_synthetic_environment.py",
)

_POSE_TASK_RELATIVE_PATH = (
    "src/pdu_exam_observer/assets/models/pose_landmarker_lite.task"
)
_RELEASE_MANIFEST_RELATIVE_PATH = "packaging/RELEASE_MANIFEST.json"
_ENCODER_POLICY = b"M2-S2C-SIMULATED-ENCODER-NOT-INVOKED-V1"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_synthetic_environment_bindings() -> SyntheticEnvironmentBindings:
    root = _repository_root()
    source = {
        relative_path: _sha256_file(root / Path(relative_path))
        for relative_path in BOUND_SOURCE_RELATIVE_PATHS
    }
    source_bytes = json.dumps(source, sort_keys=True, separators=(",", ":")).encode("ascii")
    return SyntheticEnvironmentBindings(
        application_revision_digest=hashlib.sha256(source_bytes).hexdigest(),
        release_manifest_digest=_sha256_file(root / _RELEASE_MANIFEST_RELATIVE_PATH),
        pose_engine_digest=_sha256_file(root / _POSE_TASK_RELATIVE_PATH),
        encoder_policy_digest=hashlib.sha256(_ENCODER_POLICY).hexdigest(),
    )


def synthetic_environment_binding_digest(bindings: SyntheticEnvironmentBindings) -> str:
    payload = {
        "application_revision_digest": bindings.application_revision_digest,
        "encoder_policy_digest": bindings.encoder_policy_digest,
        "pose_engine_digest": bindings.pose_engine_digest,
        "release_manifest_digest": bindings.release_manifest_digest,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()
