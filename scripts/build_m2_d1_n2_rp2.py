"""Build or verify the fixed, non-authorizing D1-N2 RP2 artifact pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import cast

from pdu_exam_observer.m2_d1_n2_bootstrap import (
    BOOTSTRAP_EPOCH_DIGEST,
    BOOTSTRAP_EPOCH_PREIMAGE,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_RELATIVE_PATH = "docs/spec/M2_D1_N2_AUTHORITY_BINDING.schema.json"
CANDIDATE_RELATIVE_PATH = "docs/spec/M2_D1_N2_STATIC_BINDING_CANDIDATE.json"

ARTIFACT_PATHS = {
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

SOURCE_IDS = tuple(
    identifier
    for identifier in ARTIFACT_PATHS
    if identifier.startswith(("SRC_", "TEST_"))
) + ("RP2_ARTIFACT_BUILDER", "BOOTSTRAP_OPERATOR_SCRIPT")
NON_SOURCE_IDS = (
    "UV_LOCK",
    "POSE_LANDMARKER_LITE_TASK",
    "BLAZE_FACE_SHORT_RANGE_TFLITE",
)
ISSUANCE_STATUS = (
    "D1_N2_B0_R2_EPOCH_BINDING_SOURCE_IMPLEMENTED_"
    "BOOTSTRAP_UNPROVISIONED_AUTHORITY_NOT_ISSUED"
)
EVIDENCE_STATUS = (
    "B0_R2_EPOCH_BINDING_SOURCE_IMPLEMENTED_OFFLINE_INDEPENDENT_REVIEW_REQUIRED"
)
DIGEST_METHOD = "sha256(canonical-json(static_bindings);sort_keys=true,separators=comma-colon;utf8)"
ROOT_CANDIDATE_KEYS = frozenset(
    {
        "artifact_kind",
        "audio_authorized",
        "authority_status",
        "created_on",
        "d1_go",
        "d1_n1_terminal_immutable",
        "device_gate_decision",
        "digest_method",
        "environment_candidates",
        "evidence_status",
        "execution_authorized",
        "grants_execution_authority",
        "issuance_implementation_status",
        "issuance_time_bindings",
        "model_training_or_evaluation_authorized",
        "participant_collection_authorized",
        "physical_camera_access_authorized",
        "physical_runtime_evidence",
        "raw_retention_authorized",
        "reopens_d1_n1",
        "schema_version",
        "static_bindings",
        "static_bindings_digest",
        "valid_for_native_launch",
    }
)
STATIC_BINDING_KEYS = frozenset(
    {
        "acceptance_thresholds",
        "artifacts",
        "authority_contract",
        "capture_profile",
        "dependency",
        "policy_digests",
        "policy_preimages",
        "research_scope",
        "routing_receipt",
        "safety_policy",
        "watchdog",
    }
)
POLICY_CANONICALIZATION = "json-v1-sort-keys-compact-utf8"
POLICY_PREIMAGES = {
    "bootstrap_bundle_policy_digest": {
        "source_id": "SRC_M2_D1_N2_BOOTSTRAP_PY",
        "projection": "d1-n2.b0-r1-bootstrap-bundle",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "algorithm": "ECDSA_P256_SHA256_IEEE_P1363",
            "authority_revision": "d1-n2-authority-v1",
            "key_id": "sha256(exact-public-blob)",
            "private_key_api": "PROHIBITED",
        },
    },
    "bootstrap_epoch_policy_digest": {
        "source_id": "SRC_M2_D1_N2_BOOTSTRAP_PY",
        "projection": "d1-n2.b0-r2-bootstrap-epoch",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "epoch_preimage": dict(BOOTSTRAP_EPOCH_PREIMAGE),
        "bootstrap_epoch_digest": BOOTSTRAP_EPOCH_DIGEST,
    },
    "bootstrap_receipt_policy_digest": {
        "source_id": "SRC_M2_D1_N2_BOOTSTRAP_PY",
        "projection": "d1-n2.b0-r1-staged-receipt",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "ceremony_revision": "d1-n2-b0-r1-provisioning-v1",
            "cleanup_before_publication": True,
            "leaf_identity": "RECEIPT_OBJECT",
            "terminal_publication_count": 1,
        },
    },
    "bootstrap_win32_policy_digest": {
        "source_id": "SRC_M2_D1_N2_BOOTSTRAP_WIN32_PY",
        "projection": "d1-n2.b0-r1-fixed-win32-boundary",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "fixed_leaves_only": True,
            "inspection_states": ["OPENED", "ABSENT", "AMBIGUOUS"],
            "no_reparse": True,
            "share_zero": True,
        },
    },
    "bootstrap_install_policy_digest": {
        "source_id": "SRC_M2_D1_N2_BOOTSTRAP_INSTALL_PY",
        "projection": "d1-n2.b0-r1-one-shot-install",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "cleanup_failure_publishes_receipt": False,
            "move_flags": ["MOVEFILE_WRITE_THROUGH"],
            "overwrite": False,
            "retry": False,
        },
    },
    "bootstrap_cng_policy_digest": {
        "source_id": "SRC_M2_D1_N2_CNG_PY",
        "projection": "d1-n2.b0-r1-public-only-cng",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "generation": False,
            "persisted_key": False,
            "private_import": False,
            "signing": False,
            "verification": "P256_SHA256_P1363",
        },
    },
    "bootstrap_production_composition_policy_digest": {
        "source_id": "SRC_M2_D1_N2_ADAPTER_PY",
        "projection": "d1-n2.b0-r1-lazy-production-composition",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "a0_after_bootstrap": True,
            "constructor_io": False,
            "fallback_key": False,
            "installer_reachable": False,
        },
    },
    "a0_approval_policy_digest": {
        "source_id": "SRC_M2_D1_N2_A0_PY",
        "projection": "d1-n2.signed-a0-approval-v1",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "algorithm": "ECDSA_P256_SHA256_IEEE_P1363",
            "duration_seconds": 60,
            "validity_seconds": 900,
            "production_bootstrap": "UNPROVISIONED",
        },
    },
    "independent_rp2_triple_policy_digest": {
        "source_id": "SRC_M2_D1_N2_PREPARE_PY",
        "projection": "d1-n2.independent-approved-rp2-triple",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "candidate_exact_bytes": True,
            "schema_canonical_bytes": True,
            "static_bindings_canonical_bytes": True,
        },
    },
    "challenge_job_binding_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.challenge-job-grant-binding",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "challenge_before_grant": True,
            "job_name_digest_bound": True,
            "raw_challenge_persisted": False,
        },
    },
    "terminal_evidence_policy_digest": {
        "source_id": "SRC_M2_D1_N2_EVIDENCE_PY",
        "projection": "d1-n2.reconstructive-terminal-evidence",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "accounting_recomputed": True,
            "integer_timing_only": True,
            "receipt_and_ledger_persisted": True,
        },
    },
    "ownership_cleanup_policy_digest": {
        "source_id": "SRC_M2_D1_N2_ADAPTER_PY",
        "projection": "d1-n2.exclusive-ownership-close-before-terminal",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {
            "base_exception_cleanup": True,
            "close_before_terminal": True,
            "idempotent_abort": True,
        },
    },
    "worker_argv_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.fixed-worker-argv",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"caller_arguments": "PROHIBITED", "video_only": True},
    },
    "worker_job_policy_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.kill-on-close-job-policy",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"descendant_drain_required": True, "kill_on_close": True},
    },
    "ffmpeg_argv_template_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.fixed-ffmpeg-video-only-template",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"audio": "-an", "data": "-dn", "subtitles": "-sn"},
    },
    "worker_bootstrap_sha256": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.worker-bootstrap-contract",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"environment_override": False, "path_search": False},
    },
    "receipt_schema_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.redacted-receipt-contract",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"d1_go": False, "device_gate_decision": "UNVERIFIED"},
    },
    "failure_ledger_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.redacted-failure-ledger",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"exception_text": "PROHIBITED", "raw_frame_data": "PROHIBITED"},
    },
    "watchdog_policy_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.phased-watchdog",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"phase_count": 6, "capture_seconds": 60, "retry": False},
    },
    "capture_policy_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.fixed-capture-profile",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"fps": 15, "height": 720, "width": 1280},
    },
    "privacy_policy_digest": {
        "source_id": "SRC_M2_D1_N2_NATIVE_PY",
        "projection": "d1-n2.privacy-stop-policy",
        "version": 1,
        "canonicalization": POLICY_CANONICALIZATION,
        "fields": {"audio": False, "network": False, "privacy_stop_terminal": True},
    },
}
ROOT_FIXED = {
    "artifact_kind": "D1_N2_STATIC_BINDING_CANDIDATE",
    "audio_authorized": False,
    "authority_status": "AUTHORITY_NOT_ISSUED",
    "created_on": "2026-08-26",
    "d1_go": False,
    "d1_n1_terminal_immutable": True,
    "device_gate_decision": "UNVERIFIED",
    "digest_method": DIGEST_METHOD,
    "environment_candidates": {
        "supervisor_executable_candidate": {
            "binding_role": "SUPERVISOR_EXECUTABLE_CANDIDATE",
            "binding_status": "CANDIDATE_ONLY_UNVERIFIED",
            "sha256": "5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec",
            "size_bytes": 103192,
        }
    },
    "evidence_status": EVIDENCE_STATUS,
    "execution_authorized": False,
    "grants_execution_authority": False,
    "issuance_implementation_status": ISSUANCE_STATUS,
    "issuance_time_bindings": {
        "authorization_nonce": "UNVERIFIED_AT_ISSUANCE",
        "camera_cardinality_status_safe_name": "UNVERIFIED_AT_ISSUANCE",
        "consumed_authority_digest": "UNVERIFIED_AT_ISSUANCE",
        "ffmpeg_handle_hash_size_version_identity": "UNVERIFIED_AT_ISSUANCE",
        "grant_challenge_capability": "UNVERIFIED_AT_ISSUANCE",
        "installed_dependency_observation": "UNVERIFIED_AT_ISSUANCE",
        "issuance_and_expiry_times": "UNVERIFIED_AT_ISSUANCE",
        "issuance_run_nonce": "UNVERIFIED_AT_ISSUANCE",
        "job_membership_and_drain": "UNVERIFIED_AT_ISSUANCE",
        "opaque_device_token": "UNVERIFIED_AT_ISSUANCE",
        "supervisor_executable_handle_binding": "UNVERIFIED_AT_ISSUANCE",
        "terminal_and_result_digests": "UNVERIFIED_AT_ISSUANCE",
        "worker_executable_handle_binding": "UNVERIFIED_AT_ISSUANCE",
    },
    "model_training_or_evaluation_authorized": False,
    "participant_collection_authorized": False,
    "physical_camera_access_authorized": False,
    "physical_runtime_evidence": "UNVERIFIED",
    "raw_retention_authorized": False,
    "reopens_d1_n1": False,
    "schema_version": 1,
    "valid_for_native_launch": False,
}
STATIC_FIXED = {
    "acceptance_thresholds": {
        "absolute_post_frame_minimum": "NONE_RATE_AND_EVIDENCE_BASED",
        "backlog_ms_max_inclusive": 2000,
        "delivery_failures_max": 0,
        "exact_accounting_reconciliation": True,
        "max_stall_gap_ns_exclusive": 1000000000,
        "p95_ingress_gap_ms_max": 200,
        "p95_pose_latency_ms_max": 200,
        "p99_pose_latency_ms_max": 500,
        "post_drop_plus_inference_failure_rate_max": 0.01,
        "post_success_coverage_min": 0.99,
        "post_successful_fps_min": 13.5,
        "post_warmup_seconds_min": 55,
        "privacy_checked_equals_processed": True,
        "privacy_counts_max": 0,
        "requires_nonempty_gap_and_latency_evidence": True,
        "total_seconds_min": 60,
    },
    "authority_contract": {
        "authority_mutex": "Local\\PDUExamObserver.D1N2.AuthorityV1",
        "authority_revision": "d1-n2-authority-v1",
        "capture_job_prefix": "Local\\PDUExamObserver.D1N2.Capture.",
        "namespace_key": "D1_N2_AUTHORITY_V1",
        "prepared_record": "prepared.v3.json",
        "schema_version": 3,
        "state_transition": ["ABSENT", "PENDING", "PREPARED", "CONSUMED", "TERMINAL"],
        "terminal_record": "terminal.v3.json",
        "video_mutex": "Local\\PDUExamObserver.D1N2.VideoOnly",
        "worker_grant_record": "worker-grant.v2.json",
    },
    "capture_profile": {
        "duration_seconds": 60,
        "fps": 15,
        "height": 720,
        "pixel_format": "rgb24",
        "video_only": True,
        "warmup_seconds": 5,
        "width": 1280,
    },
    "dependency": {"declared_pin": "mediapipe==1.0.1", "expected_version": "1.0.1"},
    "research_scope": {
        "ablations": "N/A_DEVICE_CONTRACT_SLICE",
        "baselines": "N/A_DEVICE_CONTRACT_SLICE",
        "dataset_provenance": "N/A_NO_DATASET_NO_COLLECTION",
        "seeds": "N/A_RUNTIME_CSPRNG_ONLY",
        "split_leakage_controls": "N/A_NO_MODEL_EVALUATION",
        "uncertainty_analysis": "N/A_NO_RESEARCH_FINDING",
    },
    "routing_receipt": {
        "execution_effort": "high",
        "execution_model_family": "Terra",
        "review_effort": "xhigh",
        "review_model_family": "Sol",
        "routing_basis": "HPN_V6_RISK_SCALED",
        "schema_version": 1,
    },
    "safety_policy": {
        "audio_authorized": False,
        "automatic_person_level_decision_authorized": False,
        "fail_closed": True,
        "model_training_or_evaluation_authorized": False,
        "network_authorized": False,
        "offline_runtime": True,
        "one_attempt_no_retry": True,
        "participant_collection_authorized": False,
        "raw_retention_authorized": False,
        "video_only": True,
    },
    "watchdog": {
        "phase_field_allowlists": {
            "AUTHORIZED": ["event", "challenge_digest", "payload.grant_id"],
            "CAPTURE_CLOSED": ["event", "challenge_digest", "payload.worker_monotonic_ns"],
            "CAPTURE_STARTING": ["event", "challenge_digest", "payload.worker_monotonic_ns"],
            "FIRST_FRAME": ["event", "challenge_digest", "payload.worker_monotonic_ns"],
            "PRIVACY_READY": ["event", "challenge_digest"],
            "RECEIPT": ["event", "challenge_digest", "payload"],
        },
        "phases": [
            "AUTHORIZED",
            "PRIVACY_READY",
            "CAPTURE_STARTING",
            "FIRST_FRAME",
            "CAPTURE_CLOSED",
            "RECEIPT",
        ],
        "timeouts": {
            "authorization_seconds": 10.0,
            "capture_seconds": 60.0,
            "device_setup_seconds": 25.0,
            "first_frame_seconds": 10.0,
            "privacy_ready_seconds": 30.0,
            "report_seconds": 5.0,
        },
    },
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid fixed RP2 JSON artifact") from error
    if not isinstance(decoded, dict):
        raise ValueError("fixed RP2 JSON artifact must be an object")
    return decoded


def _artifact(root: Path, identifier: str) -> dict[str, object]:
    relative = ARTIFACT_PATHS[identifier]
    try:
        payload = (root / relative).read_bytes()
    except OSError as error:
        raise ValueError("required fixed RP2 artifact is unavailable") from error
    if not payload:
        raise ValueError("required fixed RP2 artifact is empty")
    return {
        "artifact_id": identifier,
        "path": relative,
        "sha256": _sha256(payload),
        "size_bytes": len(payload),
    }


def _source_inventory(root: Path) -> dict[str, object]:
    return {identifier: _artifact(root, identifier) for identifier in SOURCE_IDS}


def _artifact_schema(identifier: str) -> dict[str, object]:
    return {
        "additionalProperties": False,
        "properties": {
            "artifact_id": {"const": identifier},
            "path": {"const": ARTIFACT_PATHS[identifier]},
            "sha256": {"pattern": "^[0-9a-f]{64}$", "type": "string"},
            "size_bytes": {"minimum": 1, "type": "integer"},
        },
        "required": ["artifact_id", "path", "sha256", "size_bytes"],
        "type": "object",
    }


def _const_schema(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {
            "additionalProperties": False,
            "properties": {name: _const_schema(item) for name, item in value.items()},
            "required": list(value),
            "type": "object",
        }
    return {"const": value}


def _policy_digests(schema: dict[str, object]) -> dict[str, object]:
    return {
        "binding_schema_canonical_sha256": _sha256(_canonical_bytes(schema)),
        **{
            name: _sha256(_canonical_bytes(preimage))
            for name, preimage in POLICY_PREIMAGES.items()
        },
    }


def _static_bindings(schema: dict[str, object], root: Path) -> dict[str, object]:
    return {
        **json.loads(_canonical_bytes(STATIC_FIXED).decode("utf-8")),
        "artifacts": {
            "source_inventory": _source_inventory(root),
            **{identifier.lower(): _artifact(root, identifier) for identifier in NON_SOURCE_IDS},
        },
        "policy_digests": _policy_digests(schema),
        "policy_preimages": json.loads(_canonical_bytes(POLICY_PREIMAGES).decode("utf-8")),
    }


def _schema_with_rp2(_schema: dict[str, object]) -> dict[str, object]:
    artifacts = {
        "additionalProperties": False,
        "properties": {
            "source_inventory": {
                "additionalProperties": False,
                "properties": {
                    identifier: _artifact_schema(identifier) for identifier in SOURCE_IDS
                },
                "required": list(SOURCE_IDS),
                "type": "object",
            },
            **{
                identifier.lower(): _artifact_schema(identifier)
                for identifier in NON_SOURCE_IDS
            },
        },
        "required": ["source_inventory", *[identifier.lower() for identifier in NON_SOURCE_IDS]],
        "type": "object",
    }
    static_properties = {
        **{name: _const_schema(value) for name, value in STATIC_FIXED.items()},
        "artifacts": artifacts,
        "policy_digests": {
            "additionalProperties": False,
            "properties": {
                "binding_schema_canonical_sha256": {
                    "pattern": "^[0-9a-f]{64}$",
                    "type": "string",
                },
                **{
                    name: {"pattern": "^[0-9a-f]{64}$", "type": "string"}
                    for name in POLICY_PREIMAGES
                },
            },
            "required": ["binding_schema_canonical_sha256", *POLICY_PREIMAGES],
            "type": "object",
        },
        "policy_preimages": {
            "additionalProperties": False,
            "properties": {
                name: {"const": preimage} for name, preimage in POLICY_PREIMAGES.items()
            },
            "required": list(POLICY_PREIMAGES),
            "type": "object",
        },
    }
    properties = {
        **{name: _const_schema(value) for name, value in ROOT_FIXED.items()},
        "static_bindings": {
            "additionalProperties": False,
            "properties": static_properties,
            "required": list(static_properties),
            "type": "object",
        },
        "static_bindings_digest": {"pattern": "^[0-9a-f]{64}$", "type": "string"},
    }
    return {
        "$id": "https://pdu.local/schemas/m2-d1-n2-static-binding-candidate-v1",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
        "title": "M2 D1-N2 static binding candidate",
        "type": "object",
    }


def _schema_is_closed(schema: dict[str, object]) -> bool:
    if schema.get("additionalProperties") is not False:
        return False
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return False
    if set(properties) != ROOT_CANDIDATE_KEYS or set(required) != ROOT_CANDIDATE_KEYS:
        return False
    static = properties.get("static_bindings")
    if not isinstance(static, dict) or static.get("additionalProperties") is not False:
        return False
    static_properties = static.get("properties")
    static_required = static.get("required")
    if not isinstance(static_properties, dict) or not isinstance(static_required, list):
        return False
    if set(static_properties) != STATIC_BINDING_KEYS or set(static_required) != STATIC_BINDING_KEYS:
        return False
    artifacts = static_properties.get("artifacts")
    if not isinstance(artifacts, dict) or artifacts.get("additionalProperties") is not False:
        return False
    artifact_properties = artifacts.get("properties")
    artifact_required = artifacts.get("required")
    expected_artifacts = {
        "source_inventory",
        *[identifier.lower() for identifier in NON_SOURCE_IDS],
    }
    if not isinstance(artifact_properties, dict) or not isinstance(artifact_required, list):
        return False
    if (
        set(artifact_properties) != expected_artifacts
        or set(artifact_required) != expected_artifacts
    ):
        return False
    inventory = artifact_properties.get("source_inventory")
    if not isinstance(inventory, dict) or inventory.get("additionalProperties") is not False:
        return False
    inventory_properties = inventory.get("properties")
    inventory_required = inventory.get("required")
    return (
        isinstance(inventory_properties, dict)
        and isinstance(inventory_required, list)
        and set(inventory_properties) == set(SOURCE_IDS)
        and set(inventory_required) == set(SOURCE_IDS)
    )


def _candidate_with_rp2(
    _candidate: dict[str, object], schema: dict[str, object], root: Path
) -> dict[str, object]:
    static = _static_bindings(schema, root)
    result = {
        **json.loads(_canonical_bytes(ROOT_FIXED).decode("utf-8")),
        "static_bindings": static,
    }
    result["static_bindings_digest"] = _sha256(_canonical_bytes(static))
    return cast(dict[str, object], result)


def _validate_internal(candidate: dict[str, object], schema: dict[str, object]) -> bool:
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return False
    if set(candidate) != set(required):
        return False
    for name, rule in properties.items():
        if name not in candidate or not isinstance(rule, dict):
            return False
        if "const" in rule and candidate[name] != rule["const"]:
            return False
    static = candidate.get("static_bindings")
    static_rule = properties.get("static_bindings")
    if not isinstance(static, dict) or not isinstance(static_rule, dict):
        return False
    static_properties = static_rule.get("properties")
    static_required = static_rule.get("required")
    if not isinstance(static_properties, dict) or not isinstance(static_required, list):
        return False
    if set(static) != set(static_required):
        return False
    artifacts = static.get("artifacts")
    artifact_rule = static_properties.get("artifacts")
    if not isinstance(artifacts, dict) or not isinstance(artifact_rule, dict):
        return False
    artifact_properties = artifact_rule.get("properties")
    artifact_required = artifact_rule.get("required")
    if not isinstance(artifact_properties, dict) or not isinstance(artifact_required, list):
        return False
    if set(artifacts) != set(artifact_required):
        return False
    inventory = artifacts.get("source_inventory")
    inventory_rule = artifact_properties.get("source_inventory")
    if not isinstance(inventory, dict) or not isinstance(inventory_rule, dict):
        return False
    inventory_properties = inventory_rule.get("properties")
    if not isinstance(inventory_properties, dict) or set(inventory) != set(SOURCE_IDS):
        return False
    for identifier in (*SOURCE_IDS, *NON_SOURCE_IDS):
        value = (
            inventory.get(identifier)
            if identifier in inventory
            else artifacts.get(identifier.lower())
        )
        if not isinstance(value, dict) or set(value) != {
            "artifact_id",
            "path",
            "sha256",
            "size_bytes",
        }:
            return False
        if (
            value["artifact_id"] != identifier
            or value["path"] != ARTIFACT_PATHS[identifier]
            or not isinstance(value["sha256"], str)
            or len(value["sha256"]) != 64
            or type(value["size_bytes"]) is not int
            or value["size_bytes"] <= 0
        ):
            return False
    return True


def _validate_candidate(candidate: dict[str, object], schema: dict[str, object]) -> bool:
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        return _validate_internal(candidate, schema)
    try:
        jsonschema.Draft202012Validator(schema).validate(candidate)
    except jsonschema.ValidationError:
        return False
    return _validate_internal(candidate, schema)


def write_artifacts(root: Path, schema_path: Path, candidate_path: Path) -> bool:
    try:
        schema = _schema_with_rp2(_load_json(schema_path))
        if not _schema_is_closed(schema):
            return False
        candidate = _candidate_with_rp2(_load_json(candidate_path), schema, root)
    except ValueError:
        return False
    if not _validate_candidate(candidate, schema):
        return False
    try:
        schema_path.write_bytes(_pretty_bytes(schema))
        candidate_path.write_bytes(_pretty_bytes(candidate))
    except OSError:
        return False
    return True


def check_artifacts(root: Path, schema_path: Path, candidate_path: Path) -> bool:
    try:
        schema = _load_json(schema_path)
        candidate = _load_json(candidate_path)
        expected_schema = _schema_with_rp2(schema)
        if (
            not _schema_is_closed(schema)
            or _canonical_bytes(schema) != _canonical_bytes(expected_schema)
        ):
            return False
        if not _validate_candidate(candidate, schema):
            return False
        expected_candidate = _candidate_with_rp2(candidate, schema, root)
    except ValueError:
        return False
    return _canonical_bytes(candidate) == _canonical_bytes(expected_candidate)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    schema = REPOSITORY_ROOT / SCHEMA_RELATIVE_PATH
    candidate = REPOSITORY_ROOT / CANDIDATE_RELATIVE_PATH
    success = (
        write_artifacts(REPOSITORY_ROOT, schema, candidate)
        if args.write
        else check_artifacts(REPOSITORY_ROOT, schema, candidate)
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
