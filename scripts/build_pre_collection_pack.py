"""Build and verify the non-authorizing GOV-P0 pre-collection pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = ROOT / "research" / "pre_collection" / "v1"
DEFAULT_PROPOSAL = ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx"

CANONICAL_PROPOSAL_SHA256 = "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5"
MANIFEST_NAME = "pre-collection-pack.manifest.v1.json"
VALIDATION_NAME = "pre-collection-pack.validation.v1.json"

JSON_CONTRACTS = (
    "external-gates.template.v1.json",
    "labelbook.draft.v1.json",
    "scenario-schedule.template.v1.json",
    "segment-policy.draft.v1.json",
    "source-register.v1.json",
)
MARKDOWN_ARTIFACTS = (
    "borrowed-custodian-request.vi.v1.md",
    "consent-form.vi.draft.v1.md",
    "participant-information.vi.draft.v1.md",
    "reporting-template.v1.md",
    "withdrawal-deletion-rehearsal.v1.md",
)
SOURCE_ARTIFACTS = tuple(sorted((*JSON_CONTRACTS, *MARKDOWN_ARTIFACTS)))
ALL_ARTIFACTS = frozenset((*SOURCE_ARTIFACTS, MANIFEST_NAME, VALIDATION_NAME))

SUPERVISED_CLASSES = (
    "NORMAL",
    "BENIGN_CONFOUNDER",
    "PROLONGED_HEAD_DOWN",
    "PROLONGED_SIDE_LOOK",
    "NO_PERSON",
    "MULTIPLE_PEOPLE",
)
BLOCKING_GATES = (
    "ACL_NOT_VERIFIED",
    "B0_3_CUSTODIAN_UNAVAILABLE",
    "B0_3_EXECUTION_AUTHORITY_NOT_ISSUED",
    "CONSENT_FORM_NOT_INSTITUTIONALLY_APPROVED",
    "ENCRYPTION_NOT_VERIFIED",
    "INSTITUTIONAL_APPROVAL_NOT_ISSUED",
    "LABELBOOK_NOT_FROZEN",
    "M2_DEVICE_EVIDENCE_UNVERIFIED",
    "M3_NOT_OPENED",
    "METHOD_THRESHOLDS_NOT_LOCKED",
    "PROTOCOL_NOT_FROZEN",
    "RESEARCH_COLLECTION_NOT_IMPLEMENTED",
    "RETENTION_DECISION_NOT_ISSUED",
    "STORAGE_ROOT_NOT_APPROVED",
)
EXPECTED_SOURCES = {
    "SRC-ABSTENTION": "https://proceedings.mlr.press/v97/geifman19a.html",
    "SRC-CALIBRATION": "https://proceedings.mlr.press/v70/guo17a.html",
    "SRC-DATA-LAW": (
        "https://vbpl.moj.gov.vn/bocongan/Pages/vbpq-van-ban-goc.aspx?ItemID=179252"
    ),
    "SRC-POSE-33": "https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmark",
    "SRC-PROPOSAL": "docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
    "SRC-STGCN": "https://ojs.aaai.org/index.php/aaai/article/view/12328",
    "SRC-TIOU": "https://activity-net.org/challenges/2018/tasks/anet_localization.html",
}


class PackError(ValueError):
    """A bounded, sanitized pre-collection pack failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: object, *, trailing_newline: bool = True) -> bytes:
    """Return the pack's one canonical JSON encoding."""

    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise PackError("CANONICALIZATION_FAILED") from exc
    if trailing_newline:
        text += "\n"
    return text.encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PackError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except PackError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackError("INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise PackError("ENVELOPE_INVALID")
    if canonical_json_bytes(value) != raw:
        raise PackError("NONCANONICAL_JSON")
    return value


def _validate_envelope(path: Path, kind: str, status: str) -> dict[str, Any]:
    document = _strict_json(path)
    if set(document) != {
        "artifact_kind",
        "body",
        "body_sha256",
        "schema_version",
        "status",
    }:
        raise PackError("ENVELOPE_INVALID")
    body = document.get("body")
    if (
        document.get("schema_version") != 1
        or document.get("artifact_kind") != kind
        or document.get("status") != status
        or not isinstance(body, dict)
        or not isinstance(document.get("body_sha256"), str)
    ):
        raise PackError("ENVELOPE_INVALID")
    if _sha256(canonical_json_bytes(body, trailing_newline=False)) != document["body_sha256"]:
        raise PackError("BODY_HASH_MISMATCH")
    return body


def _validate_source_register(pack_root: Path) -> None:
    body = _validate_envelope(
        pack_root / "source-register.v1.json",
        "SOURCE_REGISTER",
        "SOURCE_REVIEWED_METHOD_LIMITED",
    )
    if set(body) != {"claim_ids", "retrieved_on", "sources"}:
        raise PackError("SOURCE_REGISTER_INVALID")
    if body.get("retrieved_on") != "2026-08-30" or not isinstance(body.get("sources"), list):
        raise PackError("SOURCE_REGISTER_INVALID")
    observed: dict[str, str] = {}
    for source in body["sources"]:
        if not isinstance(source, dict) or set(source) != {
            "authority",
            "limitations",
            "publication_date",
            "source_id",
            "source_type",
            "supports",
            "title",
            "url_or_local_path",
        }:
            raise PackError("SOURCE_REGISTER_INVALID")
        source_id = source.get("source_id")
        location = source.get("url_or_local_path")
        if not isinstance(source_id, str) or not isinstance(location, str) or source_id in observed:
            raise PackError("SOURCE_REGISTER_INVALID")
        if not isinstance(source.get("supports"), list) or not source["supports"]:
            raise PackError("SOURCE_REGISTER_INVALID")
        if not isinstance(source.get("limitations"), str) or not source["limitations"]:
            raise PackError("SOURCE_REGISTER_INVALID")
        observed[source_id] = location
    if observed != EXPECTED_SOURCES or set(body.get("claim_ids", ())) != set(EXPECTED_SOURCES):
        raise PackError("SOURCE_REGISTER_INVALID")


def _validate_labelbook(pack_root: Path) -> None:
    body = _validate_envelope(
        pack_root / "labelbook.draft.v1.json", "LABELBOOK_DRAFT", "DRAFT_NOT_FROZEN"
    )
    if set(body) != {
        "audit_label",
        "operator_outcomes",
        "selection_policy",
        "supervised_classes",
        "technical_outcome",
    }:
        raise PackError("LABEL_TAXONOMY_INVALID")
    classes = body.get("supervised_classes")
    if not isinstance(classes, list) or tuple(
        item.get("code") for item in classes if isinstance(item, dict)
    ) != SUPERVISED_CLASSES:
        raise PackError("LABEL_TAXONOMY_INVALID")
    if any(
        not isinstance(item, dict)
        or set(item) != {"code", "definition", "intent_inference"}
        or item.get("intent_inference") is not False
        for item in classes
    ):
        raise PackError("LABEL_TAXONOMY_INVALID")
    audit = body.get("audit_label")
    technical = body.get("technical_outcome")
    if (
        not isinstance(audit, dict)
        or audit.get("code") != "UNCERTAIN"
        or audit.get("supervised") is not False
        or audit.get("retained_for_audit") is not True
        or not isinstance(technical, dict)
        or technical.get("code") != "TECHNICAL_INSUFFICIENT"
        or technical.get("supervised") is not False
        or body.get("operator_outcomes")
        != ["NORMAL", "REVIEW_REQUIRED", "TECHNICAL_INSUFFICIENT"]
    ):
        raise PackError("LABEL_TAXONOMY_INVALID")
    selection = body.get("selection_policy")
    if (
        not isinstance(selection, dict)
        or selection.get("status") != "UNSET_PENDING_M2_CALIBRATION_OR_PILOT"
        or selection.get("outer_test_data_allowed") is not False
        or not isinstance(selection.get("variables"), dict)
        or any(value is not None for value in selection["variables"].values())
    ):
        raise PackError("METHOD_SELECTION_LEAKAGE")


def _validate_segment_policy(pack_root: Path) -> None:
    body = _validate_envelope(
        pack_root / "segment-policy.draft.v1.json",
        "SEGMENT_POLICY_DRAFT",
        "DRAFT_NOT_FROZEN",
    )
    required = {
        "counts",
        "matching",
        "participant_plan",
        "reporting",
        "threshold_selection",
        "window",
    }
    if set(body) != required:
        raise PackError("SEGMENT_POLICY_INVALID")
    window = body.get("window")
    if not isinstance(window, dict) or window != {
        "duration_ms": 6000,
        "fixed_before_session": True,
        "overlap_allowed": False,
        "post_prediction_boundary_adjustment_allowed": False,
        "raw_continuous_video_local_only": True,
        "session_duration_minutes": 20,
    }:
        raise PackError("SEGMENT_WINDOW_INVALID")
    counts = body.get("counts")
    if not isinstance(counts, dict) or counts != {
        "combined_max": 720,
        "combined_min": 636,
        "confirmatory_max": 600,
        "confirmatory_min": 540,
        "pilot_max": 120,
        "pilot_min": 96,
        "proposal_max": 720,
        "proposal_min": 500,
    }:
        raise PackError("SEGMENT_COUNTS_INVALID")
    participants = body.get("participant_plan")
    if not isinstance(participants, dict) or participants != {
        "confirmatory_clips_per_class_max": 10,
        "confirmatory_clips_per_class_min": 9,
        "confirmatory_participants": 10,
        "pilot_clips_per_class_max": 10,
        "pilot_clips_per_class_min": 8,
        "pilot_participants": 2,
        "sessions_per_participant": 2,
        "supervised_class_count": 6,
    }:
        raise PackError("SEGMENT_COUNTS_INVALID")
    matching = body.get("matching")
    if (
        not isinstance(matching, dict)
        or matching.get("class_aware") is not True
        or matching.get("one_to_one") is not True
        or matching.get("primary_tiou") is not None
        or matching.get("primary_tiou_status") != "UNSET_PENDING_CALIBRATION_OR_PILOT"
        or matching.get("test_data_used_for_selection") is not False
        or matching.get("tiou_sweep")
        != [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
    ):
        raise PackError("METHOD_SELECTION_LEAKAGE")
    threshold = body.get("threshold_selection")
    if (
        not isinstance(threshold, dict)
        or threshold.get("outer_test_data_allowed") is not False
        or threshold.get("status") != "UNSET_PENDING_M2_CALIBRATION_OR_PILOT"
        or threshold.get("source_claim_ceiling") != "METHOD_ONLY_NOT_PDU_NUMERIC_THRESHOLD"
    ):
        raise PackError("METHOD_SELECTION_LEAKAGE")
    reporting = body.get("reporting")
    if not isinstance(reporting, dict) or reporting != {
        "actual_counts_required": True,
        "false_alert_denominator": "VALID_CONTINUOUS_EXAM_HOURS",
        "pilot_excluded_from_confirmatory_metrics": True,
        "uncertain_counts_reported_separately": True,
    }:
        raise PackError("SEGMENT_POLICY_INVALID")


def _validate_scenario(pack_root: Path) -> None:
    body = _validate_envelope(
        pack_root / "scenario-schedule.template.v1.json",
        "SCENARIO_SCHEDULE_TEMPLATE",
        "DRAFT_TEMPLATE_NO_PARTICIPANT",
    )
    constraints = body.get("constraints")
    if (
        set(body)
        != {
            "actual_entries",
            "constraints",
            "participant_pseudonym",
            "protocol_version",
            "schedule_seed",
            "session_index",
        }
        or body.get("actual_entries") != []
        or body.get("participant_pseudonym") != "{{PSEUDONYMOUS_PARTICIPANT_CODE}}"
        or not isinstance(constraints, dict)
        or constraints.get("window_duration_ms") != 6000
        or constraints.get("overlap_allowed") is not False
        or constraints.get("entries_fixed_before_session") is not True
        or constraints.get("classes_per_participant") != 6
    ):
        raise PackError("SCENARIO_TEMPLATE_INVALID")


def _validate_external_gates(pack_root: Path) -> None:
    body = _validate_envelope(
        pack_root / "external-gates.template.v1.json",
        "EXTERNAL_GATES_TEMPLATE",
        "DRAFT_BLOCKED",
    )
    if (
        body.get("research_ready") is not False
        or body.get("collection_authorized") is not False
        or tuple(body.get("blocking_gates", ())) != BLOCKING_GATES
        or body.get("b0_3_status") != "DEFERRED_RESOURCE_CONSTRAINT"
        or body.get("m3_status") != "UNOPENED_DRAFT_ARTIFACTS_ONLY"
        or body.get("institutional_approval_status") != "NOT_ISSUED"
        or body.get("retention_decision_status") != "NOT_ISSUED"
        or body.get("storage_root_status") != "NOT_APPROVED"
        or body.get("encryption_status") != "NOT_VERIFIED"
        or body.get("acl_status") != "NOT_VERIFIED"
    ):
        raise PackError("AUTHORITY_CEILING_VIOLATION")


def _read_markdown(pack_root: Path, name: str, required_status: str) -> str:
    path = pack_root / name
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PackError("MARKDOWN_INVALID") from exc
    if not text.endswith("\n") or f"Status: `{required_status}`" not in text:
        if "{{" in text and "ISSUED" in text:
            raise PackError("UNRESOLVED_ISSUED_TEMPLATE")
        if name == "borrowed-custodian-request.vi.v1.md":
            raise PackError("AUTHORITY_CEILING_VIOLATION")
        raise PackError("MARKDOWN_INVALID")
    if "{{" in text and required_status not in {
        "DRAFT_FOR_INSTITUTIONAL_REVIEW",
    }:
        raise PackError("UNRESOLVED_TEMPLATE")
    return text


def _validate_markdown(pack_root: Path) -> None:
    _read_markdown(
        pack_root, "participant-information.vi.draft.v1.md", "DRAFT_FOR_INSTITUTIONAL_REVIEW"
    )
    _read_markdown(
        pack_root, "consent-form.vi.draft.v1.md", "DRAFT_FOR_INSTITUTIONAL_REVIEW"
    )
    _read_markdown(pack_root, "withdrawal-deletion-rehearsal.v1.md", "SIMULATED_ONLY_NOT_RUN")
    _read_markdown(pack_root, "reporting-template.v1.md", "DRAFT_NOT_FROZEN")
    checklist = _read_markdown(
        pack_root, "borrowed-custodian-request.vi.v1.md", "NO_EXECUTION_AUTHORITY"
    )
    if (
        "không cho phép chạy vật lý" not in checklist
        or "fresh exact B0.3 execution authority" not in checklist
    ):
        raise PackError("AUTHORITY_CEILING_VIOLATION")


def _validated_root(pack_root: Path) -> Path:
    try:
        absolute = pack_root.absolute()
        if absolute.is_symlink() or not absolute.is_dir():
            raise PackError("PACK_ROOT_INVALID")
        root = absolute.resolve(strict=True)
    except OSError as exc:
        raise PackError("PACK_ROOT_INVALID") from exc
    return root


def _validate_file_set(pack_root: Path, *, require_generated: bool) -> None:
    expected = ALL_ARTIFACTS if require_generated else frozenset(SOURCE_ARTIFACTS)
    allowed = ALL_ARTIFACTS
    try:
        names = frozenset(path.name for path in pack_root.iterdir())
        if any(path.is_symlink() or not path.is_file() for path in pack_root.iterdir()):
            raise PackError("FILE_SET_MISMATCH")
    except OSError as exc:
        raise PackError("FILE_SET_MISMATCH") from exc
    if not expected.issubset(names) or not names.issubset(allowed):
        raise PackError("FILE_SET_MISMATCH")


def _verify_proposal(proposal: Path) -> None:
    try:
        digest = _sha256(proposal.read_bytes())
    except OSError as exc:
        raise PackError("PROPOSAL_HASH_MISMATCH") from exc
    if digest != CANONICAL_PROPOSAL_SHA256:
        raise PackError("PROPOSAL_HASH_MISMATCH")


def _validate_sources(pack_root: Path, proposal: Path, *, require_generated: bool) -> Path:
    root = _validated_root(pack_root)
    _validate_file_set(root, require_generated=require_generated)
    _verify_proposal(proposal)
    _validate_source_register(root)
    _validate_labelbook(root)
    _validate_segment_policy(root)
    _validate_scenario(root)
    _validate_external_gates(root)
    _validate_markdown(root)
    return root


def _manifest_document(pack_root: Path) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    for name in SOURCE_ARTIFACTS:
        path = pack_root / name
        payload = path.read_bytes()
        artifacts.append({"path": name, "sha256": _sha256(payload), "size_bytes": len(payload)})
    return {
        "artifact_kind": "PRE_COLLECTION_PACK_MANIFEST",
        "artifacts": artifacts,
        "proposal_sha256": CANONICAL_PROPOSAL_SHA256,
        "schema_version": 1,
    }


def _success_result(manifest_sha256: str) -> dict[str, object]:
    return {
        "blocking_gates": list(BLOCKING_GATES),
        "collection_authorized": False,
        "failure_code": None,
        "manifest_sha256": manifest_sha256,
        "research_ready": False,
        "result": "PACK_VALIDATED",
        "schema_version": 1,
        "structure_valid": True,
    }


def _validation_document(manifest_sha256: str) -> dict[str, object]:
    return {
        "artifact_kind": "PRE_COLLECTION_PACK_VALIDATION",
        **_success_result(manifest_sha256),
    }


def write_pack(pack_root: Path, proposal: Path) -> dict[str, object]:
    """Validate source artifacts and deterministically write derived files."""

    root = _validate_sources(Path(pack_root), Path(proposal), require_generated=False)
    manifest_bytes = canonical_json_bytes(_manifest_document(root))
    manifest_sha256 = _sha256(manifest_bytes)
    validation_bytes = canonical_json_bytes(_validation_document(manifest_sha256))
    try:
        (root / MANIFEST_NAME).write_bytes(manifest_bytes)
        (root / VALIDATION_NAME).write_bytes(validation_bytes)
    except OSError as exc:
        raise PackError("OUTPUT_WRITE_FAILED") from exc
    return _success_result(manifest_sha256)


def check_pack(pack_root: Path, proposal: Path) -> dict[str, object]:
    """Read-only check of sources and exact derived files."""

    root = _validated_root(Path(pack_root))
    _validate_file_set(root, require_generated=True)
    _verify_proposal(Path(proposal))
    expected_manifest = canonical_json_bytes(_manifest_document(root))
    try:
        actual_manifest = (root / MANIFEST_NAME).read_bytes()
    except OSError as exc:
        raise PackError("MANIFEST_MISMATCH") from exc
    if actual_manifest != expected_manifest:
        raise PackError("MANIFEST_MISMATCH")
    manifest_sha256 = _sha256(expected_manifest)
    expected_validation = canonical_json_bytes(_validation_document(manifest_sha256))
    try:
        actual_validation = (root / VALIDATION_NAME).read_bytes()
    except OSError as exc:
        raise PackError("VALIDATION_MISMATCH") from exc
    if actual_validation != expected_validation:
        raise PackError("VALIDATION_MISMATCH")
    _validate_sources(root, Path(proposal), require_generated=True)
    return _success_result(manifest_sha256)


def _rejected_result(code: str) -> dict[str, object]:
    return {
        "blocking_gates": list(BLOCKING_GATES),
        "collection_authorized": False,
        "failure_code": code,
        "manifest_sha256": None,
        "research_ready": False,
        "result": "PACK_REJECTED",
        "schema_version": 1,
        "structure_valid": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write deterministic derived files")
    mode.add_argument("--check", action="store_true", help="check without writing (default)")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PROPOSAL)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = (
            write_pack(arguments.pack_root, arguments.proposal)
            if arguments.write
            else check_pack(arguments.pack_root, arguments.proposal)
        )
    except PackError as exc:
        result = _rejected_result(exc.code)
        exit_code = 2
    except Exception:
        result = _rejected_result("UNEXPECTED_FAILURE")
        exit_code = 2
    else:
        exit_code = 0
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
