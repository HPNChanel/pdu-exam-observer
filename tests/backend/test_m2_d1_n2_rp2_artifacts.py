from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from pdu_exam_observer.m2_d1_n2_bootstrap import (
    BOOTSTRAP_EPOCH_CANONICAL_BYTES,
    BOOTSTRAP_EPOCH_DIGEST,
    BOOTSTRAP_EPOCH_PREIMAGE,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "build_m2_d1_n2_rp2.py"


def _load_builder() -> object:
    specification = importlib.util.spec_from_file_location("rp2_builder", SCRIPT_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _fixture_root(tmp_path: Path, builder: object) -> tuple[Path, Path, Path]:
    root = tmp_path / "repository"
    schema = root / "docs" / "spec" / "M2_D1_N2_AUTHORITY_BINDING.schema.json"
    candidate = root / "docs" / "spec" / "M2_D1_N2_STATIC_BINDING_CANDIDATE.json"
    schema.parent.mkdir(parents=True)
    schema.write_bytes(
        (REPOSITORY_ROOT / "docs" / "spec" / schema.name).read_bytes()
    )
    candidate.write_bytes(
        (REPOSITORY_ROOT / "docs" / "spec" / candidate.name).read_bytes()
    )
    for index, relative in enumerate(builder.ARTIFACT_PATHS.values()):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"fixture-{index}".encode("ascii"))
    return root, schema, candidate


def test_rp2_fixed_inventory_contains_exact_h3_production_sources_and_tool() -> None:
    builder = _load_builder()

    assert builder.ARTIFACT_PATHS == {
        "SRC_M2_D1_NATIVE_PY": "src/pdu_exam_observer/m2_d1_native.py",
        "SRC_M2_D1_N2_AUTHORITY_PY": "src/pdu_exam_observer/m2_d1_n2_authority.py",
        "SRC_M2_D1_N2_A0_PY": "src/pdu_exam_observer/m2_d1_n2_a0.py",
        "SRC_M2_D1_N2_CANONICAL_PY": "src/pdu_exam_observer/m2_d1_n2_canonical.py",
        "SRC_M2_D1_N2_ADAPTER_PY": "src/pdu_exam_observer/m2_d1_n2_adapter.py",
        "SRC_M2_D1_N2_BOOTSTRAP_PY": "src/pdu_exam_observer/m2_d1_n2_bootstrap.py",
        "SRC_M2_D1_N2_BOOTSTRAP_INSTALL_PY": (
            "src/pdu_exam_observer/m2_d1_n2_bootstrap_install.py"
        ),
        "SRC_M2_D1_N2_BOOTSTRAP_WIN32_PY": (
            "src/pdu_exam_observer/m2_d1_n2_bootstrap_win32.py"
        ),
        "SRC_M2_D1_N2_ENTRYPOINT_PY": "src/pdu_exam_observer/m2_d1_n2_entrypoint.py",
        "SRC_M2_D1_N2_EVIDENCE_PY": "src/pdu_exam_observer/m2_d1_n2_evidence.py",
        "SRC_M2_D1_N2_PREPARE_PY": "src/pdu_exam_observer/m2_d1_n2_prepare.py",
        "SRC_M2_D1_N2_NATIVE_PY": "src/pdu_exam_observer/m2_d1_n2_native.py",
        "SRC_M2_D1_N2_CNG_PY": "src/pdu_exam_observer/m2_d1_n2_cng.py",
        "SRC_M2_D1_N2_WIN32_PY": "src/pdu_exam_observer/m2_d1_n2_win32.py",
        "SRC_M2_D1_N2_WIN32_STORE_PY": "src/pdu_exam_observer/m2_d1_n2_win32_store.py",
        "TEST_M2_D1_N2_A0_PY": "tests/backend/test_m2_d1_n2_a0.py",
        "TEST_M2_D1_N2_ADAPTER_PY": "tests/backend/test_m2_d1_n2_adapter.py",
        "TEST_M2_D1_N2_BOOTSTRAP_PY": "tests/backend/test_m2_d1_n2_bootstrap.py",
        "TEST_M2_D1_N2_BOOTSTRAP_INSTALL_PY": (
            "tests/backend/test_m2_d1_n2_bootstrap_install.py"
        ),
        "TEST_M2_D1_N2_BOOTSTRAP_WIN32_PY": (
            "tests/backend/test_m2_d1_n2_bootstrap_win32.py"
        ),
        "TEST_M2_D1_N2_CNG_PY": "tests/backend/test_m2_d1_n2_cng.py",
        "TEST_M2_D1_N2_RP2_ARTIFACTS_PY": (
            "tests/backend/test_m2_d1_n2_rp2_artifacts.py"
        ),
        "UV_LOCK": "uv.lock",
        "POSE_LANDMARKER_LITE_TASK": (
            "src/pdu_exam_observer/assets/models/pose_landmarker_lite.task"
        ),
        "BLAZE_FACE_SHORT_RANGE_TFLITE": (
            "src/pdu_exam_observer/assets/models/blaze_face_short_range.tflite"
        ),
        "RP2_ARTIFACT_BUILDER": "scripts/build_m2_d1_n2_rp2.py",
        "BOOTSTRAP_OPERATOR_SCRIPT": "scripts/provision_m2_d1_n2_bootstrap.py",
    }


def test_rp2_write_is_idempotent_and_check_rejects_source_or_candidate_mutation(
    tmp_path: Path,
) -> None:
    builder = _load_builder()
    root, schema, candidate = _fixture_root(tmp_path, builder)

    assert builder.write_artifacts(root, schema, candidate) is True
    first_schema = schema.read_bytes()
    first_candidate = candidate.read_bytes()
    assert builder.check_artifacts(root, schema, candidate) is True
    assert builder.write_artifacts(root, schema, candidate) is True
    assert schema.read_bytes() == first_schema
    assert candidate.read_bytes() == first_candidate

    (root / builder.ARTIFACT_PATHS["SRC_M2_D1_N2_CANONICAL_PY"]).write_bytes(b"changed")
    assert builder.check_artifacts(root, schema, candidate) is False

    assert builder.write_artifacts(root, schema, candidate) is True
    document = json.loads(candidate.read_text(encoding="utf-8"))
    document["static_bindings"]["artifacts"]["source_inventory"]["EXTRA"] = {}
    candidate.write_text(json.dumps(document), encoding="utf-8")
    assert builder.check_artifacts(root, schema, candidate) is False


def test_rp2_check_rejects_missing_artifact_wrong_status_and_schema_extra(
    tmp_path: Path,
) -> None:
    builder = _load_builder()
    root, schema, candidate = _fixture_root(tmp_path, builder)
    assert builder.write_artifacts(root, schema, candidate) is True

    document = json.loads(candidate.read_text(encoding="utf-8"))
    del document["static_bindings"]["artifacts"]["source_inventory"][
        "SRC_M2_D1_N2_ADAPTER_PY"
    ]
    candidate.write_text(json.dumps(document), encoding="utf-8")
    assert builder.check_artifacts(root, schema, candidate) is False

    assert builder.write_artifacts(root, schema, candidate) is True
    document = json.loads(candidate.read_text(encoding="utf-8"))
    document["issuance_implementation_status"] = "AUTHORITY_ISSUED"
    candidate.write_text(json.dumps(document), encoding="utf-8")
    assert builder.check_artifacts(root, schema, candidate) is False

    assert builder.write_artifacts(root, schema, candidate) is True
    schema_document = json.loads(schema.read_text(encoding="utf-8"))
    schema_document["properties"]["unexpected"] = {"type": "string"}
    schema.write_text(json.dumps(schema_document), encoding="utf-8")
    assert builder.check_artifacts(root, schema, candidate) is False


def test_rp2_write_restores_coordinated_schema_and_candidate_authority_flip(
    tmp_path: Path,
) -> None:
    builder = _load_builder()
    root, schema, candidate = _fixture_root(tmp_path, builder)
    assert builder.write_artifacts(root, schema, candidate) is True

    schema_document = json.loads(schema.read_text(encoding="utf-8"))
    schema_document["properties"]["authority_status"] = {"const": "AUTHORITY_ISSUED"}
    schema_document["properties"]["audio_authorized"] = {"const": True}
    schema.write_text(json.dumps(schema_document), encoding="utf-8")
    candidate_document = json.loads(candidate.read_text(encoding="utf-8"))
    candidate_document["authority_status"] = "AUTHORITY_ISSUED"
    candidate_document["audio_authorized"] = True
    candidate_document["grants_execution_authority"] = True
    candidate_document["static_bindings"]["safety_policy"]["network_authorized"] = True
    candidate.write_text(json.dumps(candidate_document), encoding="utf-8")

    assert builder.write_artifacts(root, schema, candidate) is True
    restored = json.loads(candidate.read_text(encoding="utf-8"))
    assert restored["authority_status"] == "AUTHORITY_NOT_ISSUED"
    assert restored["audio_authorized"] is False
    assert restored["grants_execution_authority"] is False
    assert restored["static_bindings"]["safety_policy"]["network_authorized"] is False
    assert builder.check_artifacts(root, schema, candidate) is True


def test_rp2_policy_preimages_are_computed_and_not_copied_from_candidate(
    tmp_path: Path,
) -> None:
    builder = _load_builder()
    root, schema, candidate = _fixture_root(tmp_path, builder)
    assert builder.write_artifacts(root, schema, candidate) is True
    document = json.loads(candidate.read_text(encoding="utf-8"))
    preimages = document["static_bindings"]["policy_preimages"]
    digest_name = "watchdog_policy_digest"
    original_digest = document["static_bindings"]["policy_digests"][digest_name]
    preimages[digest_name]["projection"] = "forged"
    document["static_bindings"]["policy_digests"][digest_name] = "0" * 64
    candidate.write_text(json.dumps(document), encoding="utf-8")

    assert builder.check_artifacts(root, schema, candidate) is False
    assert builder.write_artifacts(root, schema, candidate) is True
    restored = json.loads(candidate.read_text(encoding="utf-8"))
    assert restored["static_bindings"]["policy_preimages"] == builder.POLICY_PREIMAGES
    assert restored["static_bindings"]["policy_digests"][digest_name] == original_digest


def test_rp2_binds_exact_source_derived_bootstrap_epoch_policy(tmp_path: Path) -> None:
    builder = _load_builder()
    assert builder.BOOTSTRAP_EPOCH_PREIMAGE is BOOTSTRAP_EPOCH_PREIMAGE
    assert builder.BOOTSTRAP_EPOCH_DIGEST == BOOTSTRAP_EPOCH_DIGEST
    policy = {
        "bootstrap_epoch_digest": (
            "736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b"
        ),
        "canonicalization": "json-v1-sort-keys-compact-utf8",
        "epoch_preimage": json.loads(BOOTSTRAP_EPOCH_CANONICAL_BYTES),
        "projection": "d1-n2.b0-r2-bootstrap-epoch",
        "source_id": "SRC_M2_D1_N2_BOOTSTRAP_PY",
        "version": 1,
    }
    assert builder.POLICY_PREIMAGES["bootstrap_epoch_policy_digest"] == policy

    root, schema, candidate = _fixture_root(tmp_path, builder)
    assert builder.write_artifacts(root, schema, candidate) is True
    document = json.loads(candidate.read_text(encoding="utf-8"))
    expected_digest = hashlib.sha256(
        json.dumps(
            policy,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()

    assert (
        document["static_bindings"]["policy_preimages"][
            "bootstrap_epoch_policy_digest"
        ]
        == policy
    )
    assert (
        document["static_bindings"]["policy_digests"][
            "bootstrap_epoch_policy_digest"
        ]
        == expected_digest
    )
