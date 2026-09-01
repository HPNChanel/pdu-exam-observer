"""Canonical download-only evidence bundles for synthetic M2 runs."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from pdu_exam_observer.m2_d1_contract import (
    Accounting,
    D1FailureCode,
    D1Receipt,
    DeviceGateDecision,
    EncoderDurabilityEvidence,
    EvidenceKind,
    MetricSummary,
    RunKind,
    StageState,
    ValidationOutcome,
    verify_receipt_semantics,
)
from pdu_exam_observer.m2_synthetic_integration import (
    IntegrationFailureCode,
    IntegrationStatus,
    SyntheticIntegrationReceipt,
)

MAX_EVIDENCE_BYTES = 4_000_000
STATUS = (
    "M2_S2D_SYNTHETIC_EVIDENCE_EXPORT_LOCALLY_VERIFIED_"
    "DEVICE_UNVERIFIED_NO_COLLECTION_AUTHORITY"
)
REJECTED_STATUS = "M2_S2D_SYNTHETIC_EVIDENCE_REJECTED"
ARTIFACT_KIND = "M2_SYNTHETIC_EVIDENCE_BUNDLE"
_REQUEST_ID = re.compile(r"synrun-[0-9a-f]{32}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/)")

SYNTHETIC_AUTHORITY_CEILING: dict[str, object] = {
    "authority_status": "AUTHORITY_NOT_ISSUED",
    "capability_status": "SYNTHETIC_REVIEW_ONLY",
    "collection_authorized": False,
    "d1_go": False,
    "device_gate_decision": "UNVERIFIED",
    "evidence_kind": "SIMULATED",
    "execution_authorized": False,
    "package_contains_integration": False,
    "participant_collection_authorized": False,
    "physical_camera_access_authorized": False,
    "production_reconciler_implemented": False,
    "production_reconciler_real_storage_verified": False,
    "real_data_deletion_authorized": False,
    "research_ready": False,
    "schema_version": 1,
}

_ARTIFACT_AUTHORITY = {
    "authority_status": "AUTHORITY_NOT_ISSUED",
    "collection_authorized": False,
    "d1_go": False,
    "device_gate_decision": "UNVERIFIED",
    "participant_collection_authorized": False,
    "physical_camera_access_authorized": False,
    "research_ready": False,
}
_FORBIDDEN_KEYS = {
    "audio",
    "camera_id",
    "device_id",
    "frame",
    "image",
    "landmarks",
    "local_path",
    "native_device_identifier",
    "participant_id",
    "participant_pseudonym",
    "path",
    "raw_landmarks",
    "session_id",
    "username",
}


class SyntheticEvidenceFailureCode(StrEnum):
    INPUT_INVALID = "INPUT_INVALID"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    INVALID_JSON = "INVALID_JSON"
    DUPLICATE_JSON_KEY = "DUPLICATE_JSON_KEY"
    NONCANONICAL_JSON = "NONCANONICAL_JSON"
    ENVELOPE_INVALID = "ENVELOPE_INVALID"
    BODY_HASH_MISMATCH = "BODY_HASH_MISMATCH"
    RUN_RECORD_INVALID = "RUN_RECORD_INVALID"
    RECEIPT_INVALID = "RECEIPT_INVALID"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"
    ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"
    D1_RECEIPT_INVALID = "D1_RECEIPT_INVALID"
    OBSERVATION_DIGEST_MISMATCH = "OBSERVATION_DIGEST_MISMATCH"
    AUTHORITY_CEILING_VIOLATION = "AUTHORITY_CEILING_VIOLATION"
    FORBIDDEN_CONTENT = "FORBIDDEN_CONTENT"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


class SyntheticEvidenceError(RuntimeError):
    def __init__(self, code: SyntheticEvidenceFailureCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class SyntheticEvidenceExport:
    payload: bytes
    sha256: str
    filename: str


@dataclass(frozen=True, slots=True)
class SyntheticEvidenceVerificationReceipt:
    schema_version: int
    artifact_kind: str
    result: str
    status: str
    failure_code: SyntheticEvidenceFailureCode | None
    bundle_sha256: str | None
    run_kind: RunKind | None
    source_result_digest: str | None
    source_artifact_sha256: str | None
    observation_count: int | None
    evidence_kind: EvidenceKind
    device_gate_decision: DeviceGateDecision
    d1_go: bool
    authority_status: str
    collection_authorized: bool
    package_contains_integration: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact_kind": self.artifact_kind,
            "authority_status": self.authority_status,
            "bundle_sha256": self.bundle_sha256,
            "collection_authorized": self.collection_authorized,
            "d1_go": self.d1_go,
            "device_gate_decision": self.device_gate_decision.value,
            "evidence_kind": self.evidence_kind.value,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "observation_count": self.observation_count,
            "package_contains_integration": self.package_contains_integration,
            "result": self.result,
            "run_kind": self.run_kind.value if self.run_kind else None,
            "schema_version": self.schema_version,
            "source_artifact_sha256": self.source_artifact_sha256,
            "source_result_digest": self.source_result_digest,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class VerifiedSyntheticEvidenceSource:
    bundle_sha256: str
    run_kind: RunKind
    request_id: str
    run_sequence: int
    integration_receipt: SyntheticIntegrationReceipt
    artifact_bytes: bytes
    artifact_sha256: str
    environment_binding_digest: str
    observation_count: int
    observation_digest: str
    d1_outcome: ValidationOutcome
    d1_failure_code: D1FailureCode | None
    d1_receipt_digest: str

    @property
    def source_result_digest(self) -> str:
        return self.integration_receipt.result_digest


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)[:-1]).hexdigest()


def _duplicate_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.DUPLICATE_JSON_KEY)
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INVALID_JSON)


def _load_json(payload: bytes, *, canonical: bool) -> object:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_constant,
        )
    except SyntheticEvidenceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INVALID_JSON) from exc
    if canonical and canonical_json_bytes(value) != payload:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.NONCANONICAL_JSON)
    return value


def _record(value: object, keys: set[str], code: SyntheticEvidenceFailureCode) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SyntheticEvidenceError(code)
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError
    return value


def _number(value: object) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError
    return float(value)


def _optional_number(value: object) -> float | None:
    return None if value is None else _number(value)


def _pairs(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, list):
        raise ValueError
    result: list[tuple[str, int]] = []
    for item in value:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
        ):
            raise ValueError
        result.append((item[0], _integer(item[1])))
    return tuple(result)


def _accounting(value: object) -> Accounting:
    item = _record(
        value,
        {
            "delivered_frames",
            "inter_frame_gaps",
            "processed",
            "dropped_explicit",
            "failed",
            "quality_insufficient",
            "drop_reasons",
        },
        SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID,
    )
    return Accounting(
        delivered_frames=_integer(item["delivered_frames"]),
        inter_frame_gaps=_integer(item["inter_frame_gaps"]),
        processed=_integer(item["processed"]),
        dropped_explicit=_integer(item["dropped_explicit"]),
        failed=_integer(item["failed"]),
        quality_insufficient=_integer(item["quality_insufficient"]),
        drop_reasons=_pairs(item["drop_reasons"]),
    )


def _metrics(value: object) -> MetricSummary:
    item = _record(
        value,
        {
            "first_capture_monotonic_ns",
            "run_end_monotonic_ns",
            "measured_total_seconds",
            "measured_post_warmup_seconds",
            "delivered_frames_per_second",
            "p95_inter_frame_gap_ms",
            "p95_pose_latency_ms",
            "p99_pose_latency_ms",
            "p10_preflight_throughput_bytes_per_second",
            "backlog_ms",
        },
        SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID,
    )
    return MetricSummary(
        first_capture_monotonic_ns=_integer(item["first_capture_monotonic_ns"]),
        run_end_monotonic_ns=_integer(item["run_end_monotonic_ns"]),
        measured_total_seconds=_number(item["measured_total_seconds"]),
        measured_post_warmup_seconds=_number(item["measured_post_warmup_seconds"]),
        delivered_frames_per_second=_number(item["delivered_frames_per_second"]),
        p95_inter_frame_gap_ms=_optional_number(item["p95_inter_frame_gap_ms"]),
        p95_pose_latency_ms=_optional_number(item["p95_pose_latency_ms"]),
        p99_pose_latency_ms=_optional_number(item["p99_pose_latency_ms"]),
        p10_preflight_throughput_bytes_per_second=_optional_number(
            item["p10_preflight_throughput_bytes_per_second"]
        ),
        backlog_ms=_optional_number(item["backlog_ms"]),
    )


def _stages(value: object) -> EncoderDurabilityEvidence:
    item = _record(
        value,
        {"encoder_open", "encoder_write", "encoder_finalize", "durability"},
        SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID,
    )
    return EncoderDurabilityEvidence(
        encoder_open=StageState(str(item["encoder_open"])),
        encoder_write=StageState(str(item["encoder_write"])),
        encoder_finalize=StageState(str(item["encoder_finalize"])),
        durability=StageState(str(item["durability"])),
    )


_D1_KEYS = {
    "accounting",
    "authority_digest",
    "device_gate_decision",
    "encoded_byte_count",
    "encoded_byte_rate",
    "environment_digest",
    "evaluation_core_digest",
    "evidence_kind",
    "export_attempted",
    "failure_code",
    "failure_counts",
    "frames_per_second",
    "free_bytes",
    "height",
    "input_digest",
    "metrics",
    "outcome",
    "privacy_checked_frames",
    "privacy_stop_count",
    "provenance_digest",
    "reproduction_digest",
    "requested_duration_seconds",
    "required_bytes",
    "result_digest",
    "run_kind",
    "schema_version",
    "seal_attempted",
    "stages",
    "throughput_digest",
    "throughput_sample_count",
    "warmup_accounting",
    "warmup_seconds",
    "width",
}


def _d1_receipt(value: object) -> D1Receipt:
    item = _record(value, _D1_KEYS, SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID)
    try:
        failure = None if item["failure_code"] is None else D1FailureCode(str(item["failure_code"]))
        receipt = D1Receipt(
            schema_version=_integer(item["schema_version"]),
            outcome=ValidationOutcome(str(item["outcome"])),
            device_gate_decision=DeviceGateDecision(str(item["device_gate_decision"])),
            evidence_kind=EvidenceKind(str(item["evidence_kind"])),
            failure_code=failure,
            failure_counts=_pairs(item["failure_counts"]),
            run_kind=RunKind(str(item["run_kind"])),
            width=_integer(item["width"]),
            height=_integer(item["height"]),
            frames_per_second=_integer(item["frames_per_second"]),
            requested_duration_seconds=_integer(item["requested_duration_seconds"]),
            warmup_seconds=_integer(item["warmup_seconds"]),
            privacy_checked_frames=_integer(item["privacy_checked_frames"]),
            privacy_stop_count=_integer(item["privacy_stop_count"]),
            warmup_accounting=_accounting(item["warmup_accounting"]),
            accounting=_accounting(item["accounting"]),
            metrics=_metrics(item["metrics"]),
            required_bytes=_integer(item["required_bytes"]),
            free_bytes=_integer(item["free_bytes"]),
            encoded_byte_count=_integer(item["encoded_byte_count"]),
            encoded_byte_rate=_number(item["encoded_byte_rate"]),
            throughput_sample_count=_integer(item["throughput_sample_count"]),
            throughput_digest=str(item["throughput_digest"]),
            stages=_stages(item["stages"]),
            seal_attempted=item["seal_attempted"] is True,
            export_attempted=item["export_attempted"] is True,
            authority_digest=str(item["authority_digest"]),
            input_digest=str(item["input_digest"]),
            provenance_digest=str(item["provenance_digest"]),
            environment_digest=str(item["environment_digest"]),
            reproduction_digest=str(item["reproduction_digest"]),
            evaluation_core_digest=str(item["evaluation_core_digest"]),
            result_digest=str(item["result_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID) from exc
    if item["seal_attempted"] is not False or item["export_attempted"] is not False:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID)
    if not verify_receipt_semantics(receipt):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID)
    return receipt


_INTEGRATION_KEYS = {
    "artifact_id",
    "artifact_sha256",
    "authority_status",
    "collection_authorized",
    "d1_failure_code",
    "d1_go",
    "d1_outcome",
    "d1_receipt_digest",
    "device_gate_decision",
    "evidence_kind",
    "integration_failure_code",
    "integration_status",
    "manifest_schema_version",
    "observation_count",
    "observation_digest",
    "package_contains_integration",
    "participant_collection_authorized",
    "physical_camera_access_authorized",
    "result_digest",
    "run_kind",
    "schema_version",
    "status",
}


def _integration_receipt(value: object) -> SyntheticIntegrationReceipt:
    item = _record(value, _INTEGRATION_KEYS, SyntheticEvidenceFailureCode.RECEIPT_INVALID)
    try:
        receipt = SyntheticIntegrationReceipt(
            schema_version=_integer(item["schema_version"]),
            status=str(item["status"]),
            integration_status=IntegrationStatus(str(item["integration_status"])),
            evidence_kind=EvidenceKind(str(item["evidence_kind"])),
            run_kind=RunKind(str(item["run_kind"])),
            d1_outcome=(
                None if item["d1_outcome"] is None else ValidationOutcome(str(item["d1_outcome"]))
            ),
            d1_failure_code=(
                None
                if item["d1_failure_code"] is None
                else D1FailureCode(str(item["d1_failure_code"]))
            ),
            integration_failure_code=(
                None
                if item["integration_failure_code"] is None
                else IntegrationFailureCode(str(item["integration_failure_code"]))
            ),
            device_gate_decision=DeviceGateDecision(str(item["device_gate_decision"])),
            d1_go=item["d1_go"] is True,
            authority_status=str(item["authority_status"]),
            physical_camera_access_authorized=item["physical_camera_access_authorized"] is True,
            participant_collection_authorized=item["participant_collection_authorized"] is True,
            collection_authorized=item["collection_authorized"] is True,
            observation_count=_integer(item["observation_count"]),
            observation_digest=(
                None if item["observation_digest"] is None else str(item["observation_digest"])
            ),
            d1_receipt_digest=(
                None if item["d1_receipt_digest"] is None else str(item["d1_receipt_digest"])
            ),
            artifact_id=None if item["artifact_id"] is None else str(item["artifact_id"]),
            artifact_sha256=(
                None if item["artifact_sha256"] is None else str(item["artifact_sha256"])
            ),
            manifest_schema_version=(
                None
                if item["manifest_schema_version"] is None
                else _integer(item["manifest_schema_version"])
            ),
            package_contains_integration=item["package_contains_integration"] is True,
            result_digest=str(item["result_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.RECEIPT_INVALID) from exc
    false_fields = (
        item["d1_go"],
        item["physical_camera_access_authorized"],
        item["participant_collection_authorized"],
        item["collection_authorized"],
        item["package_contains_integration"],
    )
    if (
        receipt.schema_version != 1
        or receipt.integration_status is not IntegrationStatus.PERSISTED
        or receipt.evidence_kind is not EvidenceKind.SIMULATED
        or receipt.device_gate_decision is not DeviceGateDecision.UNVERIFIED
        or receipt.authority_status != "AUTHORITY_NOT_ISSUED"
        or receipt.integration_failure_code is not None
        or receipt.d1_outcome is None
        or receipt.artifact_id is None
        or receipt.artifact_sha256 is None
        or receipt.manifest_schema_version != 2
        or receipt.result_digest != receipt.recompute_digest()
        or any(value is not False for value in false_fields)
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.RECEIPT_INVALID)
    return receipt


def _forbidden(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in _FORBIDDEN_KEYS:
                raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.FORBIDDEN_CONTENT)
            _forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _forbidden(child)
    elif isinstance(value, str) and _ABSOLUTE_PATH.match(value):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.FORBIDDEN_CONTENT)


def _validate_body(body: object, *, bundle_sha256: str) -> VerifiedSyntheticEvidenceSource:
    item = _record(
        body,
        {
            "authority_ceiling",
            "export_authority_effect",
            "export_mode",
            "source_artifact",
            "source_artifact_byte_size",
            "source_artifact_sha256",
            "source_run",
        },
        SyntheticEvidenceFailureCode.ENVELOPE_INVALID,
    )
    if item["authority_ceiling"] != SYNTHETIC_AUTHORITY_CEILING:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.AUTHORITY_CEILING_VIOLATION)
    if (
        item["export_authority_effect"] != "NONE"
        or item["export_mode"] != "DOWNLOAD_ONLY_NO_SERVER_ARCHIVE"
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.ENVELOPE_INVALID)
    _forbidden(item)
    run = _record(
        item["source_run"],
        {
            "job_status",
            "receipt",
            "request_id",
            "run_kind",
            "run_sequence",
            "schema_version",
            "service_failure_code",
        },
        SyntheticEvidenceFailureCode.RUN_RECORD_INVALID,
    )
    try:
        run_kind = RunKind(str(run["run_kind"]))
    except ValueError as exc:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.RUN_RECORD_INVALID) from exc
    if (
        run["schema_version"] != 1
        or run["job_status"] != "TERMINAL"
        or run["service_failure_code"] is not None
        or not isinstance(run["run_sequence"], int)
        or isinstance(run["run_sequence"], bool)
        or int(run["run_sequence"]) < 1
        or not isinstance(run["request_id"], str)
        or not _REQUEST_ID.fullmatch(run["request_id"])
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.RUN_RECORD_INVALID)
    integration = _integration_receipt(run["receipt"])
    if integration.run_kind is not run_kind:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.RECEIPT_INVALID)
    artifact = _record(
        item["source_artifact"],
        {
            "artifact_kind",
            "authority_ceiling",
            "d1_receipt",
            "environment_binding_digest",
            "evidence_kind",
            "observation_digest",
            "observation_result_digests",
            "package_contains_integration",
            "schema_version",
        },
        SyntheticEvidenceFailureCode.ARTIFACT_INVALID,
    )
    expected_kind = {
        RunKind.PREFLIGHT_60S: "M2_SYNTHETIC_PREFLIGHT_RECEIPT",
        RunKind.NOMINAL_20M: "M2_SYNTHETIC_NOMINAL_RECEIPT",
    }[run_kind]
    if (
        artifact["artifact_kind"] != expected_kind
        or artifact["authority_ceiling"] != _ARTIFACT_AUTHORITY
        or artifact["evidence_kind"] != "SIMULATED"
        or artifact["package_contains_integration"] is not False
        or artifact["schema_version"] != 1
        or not isinstance(artifact["environment_binding_digest"], str)
        or not _DIGEST.fullmatch(artifact["environment_binding_digest"])
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.ARTIFACT_INVALID)
    artifact_bytes = canonical_json_bytes(artifact)
    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
    if (
        _integer(item["source_artifact_byte_size"]) != len(artifact_bytes)
        or item["source_artifact_sha256"] != artifact_sha
        or integration.artifact_sha256 != artifact_sha
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.ARTIFACT_HASH_MISMATCH)
    digests = artifact["observation_result_digests"]
    if (
        not isinstance(digests, list)
        or not all(isinstance(value, str) and _DIGEST.fullmatch(value) for value in digests)
        or len(digests) != integration.observation_count
        or artifact["observation_digest"] != _digest(digests)
        or integration.observation_digest != artifact["observation_digest"]
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.OBSERVATION_DIGEST_MISMATCH)
    d1 = _d1_receipt(artifact["d1_receipt"])
    if (
        d1.run_kind is not run_kind
        or d1.outcome is not integration.d1_outcome
        or d1.failure_code is not integration.d1_failure_code
        or d1.result_digest != integration.d1_receipt_digest
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.D1_RECEIPT_INVALID)
    return VerifiedSyntheticEvidenceSource(
        bundle_sha256=bundle_sha256,
        run_kind=run_kind,
        request_id=str(run["request_id"]),
        run_sequence=int(run["run_sequence"]),
        integration_receipt=integration,
        artifact_bytes=artifact_bytes,
        artifact_sha256=artifact_sha,
        environment_binding_digest=str(artifact["environment_binding_digest"]),
        observation_count=len(digests),
        observation_digest=str(artifact["observation_digest"]),
        d1_outcome=d1.outcome,
        d1_failure_code=d1.failure_code,
        d1_receipt_digest=d1.result_digest,
    )


def _validate_envelope(value: object) -> VerifiedSyntheticEvidenceSource:
    envelope = _record(
        value,
        {"artifact_kind", "body", "body_sha256", "schema_version", "status"},
        SyntheticEvidenceFailureCode.ENVELOPE_INVALID,
    )
    if (
        envelope["artifact_kind"] != ARTIFACT_KIND
        or envelope["schema_version"] != 1
        or envelope["status"] != STATUS
        or not isinstance(envelope["body_sha256"], str)
        or not _DIGEST.fullmatch(envelope["body_sha256"])
    ):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.ENVELOPE_INVALID)
    if envelope["body_sha256"] != _digest(envelope["body"]):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.BODY_HASH_MISMATCH)
    bundle_sha256 = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return _validate_body(envelope["body"], bundle_sha256=bundle_sha256)


def build_synthetic_evidence_bundle(
    run_record: Mapping[str, object], artifact_bytes: bytes
) -> SyntheticEvidenceExport:
    if not isinstance(run_record, Mapping) or not isinstance(artifact_bytes, bytes):
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INPUT_INVALID)
    if not artifact_bytes or len(artifact_bytes) > MAX_EVIDENCE_BYTES:
        raise SyntheticEvidenceError(
            SyntheticEvidenceFailureCode.INPUT_TOO_LARGE
            if len(artifact_bytes) > MAX_EVIDENCE_BYTES
            else SyntheticEvidenceFailureCode.INPUT_INVALID
        )
    artifact = _load_json(artifact_bytes, canonical=True)
    body: dict[str, object] = {
        "authority_ceiling": dict(SYNTHETIC_AUTHORITY_CEILING),
        "export_authority_effect": "NONE",
        "export_mode": "DOWNLOAD_ONLY_NO_SERVER_ARCHIVE",
        "source_artifact": artifact,
        "source_artifact_byte_size": len(artifact_bytes),
        "source_artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "source_run": dict(run_record),
    }
    envelope = {
        "artifact_kind": ARTIFACT_KIND,
        "body": body,
        "body_sha256": _digest(body),
        "schema_version": 1,
        "status": STATUS,
    }
    _validate_envelope(envelope)
    payload = canonical_json_bytes(envelope)
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INPUT_TOO_LARGE)
    request_id = str(dict(run_record).get("request_id", ""))
    return SyntheticEvidenceExport(
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
        filename=f"m2-s2d-{request_id}.json",
    )


def _verification(
    *,
    result: str,
    failure: SyntheticEvidenceFailureCode | None,
    bundle_sha256: str | None,
    verified: VerifiedSyntheticEvidenceSource | None = None,
) -> SyntheticEvidenceVerificationReceipt:
    return SyntheticEvidenceVerificationReceipt(
        schema_version=1,
        artifact_kind="M2_SYNTHETIC_EVIDENCE_VERIFICATION_RECEIPT",
        result=result,
        status=STATUS if failure is None else REJECTED_STATUS,
        failure_code=failure,
        bundle_sha256=bundle_sha256,
        run_kind=verified.run_kind if verified else None,
        source_result_digest=verified.source_result_digest if verified else None,
        source_artifact_sha256=verified.artifact_sha256 if verified else None,
        observation_count=verified.observation_count if verified else None,
        evidence_kind=EvidenceKind.SIMULATED,
        device_gate_decision=DeviceGateDecision.UNVERIFIED,
        d1_go=False,
        authority_status="AUTHORITY_NOT_ISSUED",
        collection_authorized=False,
        package_contains_integration=False,
    )


def verify_synthetic_evidence_bytes(payload: bytes) -> SyntheticEvidenceVerificationReceipt:
    bundle_sha: str | None = None
    try:
        if not isinstance(payload, bytes) or not payload:
            raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INPUT_INVALID)
        if len(payload) > MAX_EVIDENCE_BYTES:
            raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INPUT_TOO_LARGE)
        bundle_sha = hashlib.sha256(payload).hexdigest()
        value = _load_json(payload, canonical=True)
        verified = _validate_envelope(value)
        return _verification(
            result="EVIDENCE_VERIFIED",
            failure=None,
            bundle_sha256=bundle_sha,
            verified=verified,
        )
    except SyntheticEvidenceError as exc:
        return _verification(
            result="EVIDENCE_REJECTED",
            failure=exc.code,
            bundle_sha256=bundle_sha,
        )
    except Exception:
        return _verification(
            result="EVIDENCE_REJECTED",
            failure=SyntheticEvidenceFailureCode.UNEXPECTED_FAILURE,
            bundle_sha256=bundle_sha,
        )


def load_verified_synthetic_evidence_bytes(payload: bytes) -> VerifiedSyntheticEvidenceSource:
    if not isinstance(payload, bytes) or not payload:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INPUT_INVALID)
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.INPUT_TOO_LARGE)
    value = _load_json(payload, canonical=True)
    return _validate_envelope(value)
