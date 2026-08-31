"""Build and verify the fail-closed GOV-P5A human-confirmation request pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = (
    ROOT
    / "research"
    / "institutional_submission"
    / "human_confirmation_request"
    / "v1"
)

ADVISOR_REQUEST_NAME = "advisor-human-confirmation-request.vi.v1.md"
QUESTION_MATRIX_NAME = "confirmation-question-matrix.v1.json"
EVIDENCE_REQUIREMENTS_NAME = "response-evidence-requirements.vi.v1.md"
RESPONSE_TEMPLATE_NAME = "human-confirmation-response.template.v1.json"
SOURCE_INDEX_NAME = "source-index.v1.json"
MANIFEST_NAME = "gov-p5-confirmation-request.manifest.v1.json"
VALIDATION_NAME = "gov-p5-confirmation-request.validation.v1.json"

REVIEWED_NAMES = (
    ADVISOR_REQUEST_NAME,
    QUESTION_MATRIX_NAME,
    EVIDENCE_REQUIREMENTS_NAME,
    RESPONSE_TEMPLATE_NAME,
    SOURCE_INDEX_NAME,
)
GENERATED_NAMES = (MANIFEST_NAME, VALIDATION_NAME)
ALL_NAMES = frozenset((*REVIEWED_NAMES, *GENERATED_NAMES))

STATUS = (
    "GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_"
    "PENDING_HUMAN_RESPONSE_NOT_SUBMITTED"
)


@dataclass(frozen=True)
class Upstream:
    path: Path
    relative_path: str
    sha256: str


def _upstream(relative_path: str, sha256: str) -> Upstream:
    return Upstream(ROOT / relative_path, relative_path, sha256)


UPSTREAMS = {
    "CANONICAL_PROPOSAL": _upstream(
        "docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5",
    ),
    "GOV_P2_MANIFEST": _upstream(
        "research/institutional_submission/v1/gov-p2-submission.manifest.v1.json",
        "1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e",
    ),
    "GOV_P2_DECISION_MATRIX": _upstream(
        "research/institutional_submission/v1/decision-request-matrix.v1.json",
        "dcdff3aa61062f9fe0e37919141e9c591eeac751f8f52c296f6bf11f6fb4b9e4",
    ),
    "GOV_P3_MANIFEST": _upstream(
        "research/institutional_submission/advisor_decision/v1/"
        "gov-p3-advisor-decision.manifest.v1.json",
        "7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605",
    ),
    "GOV_P3_VERBAL_RECORD": _upstream(
        "research/institutional_submission/advisor_decision/v1/"
        "advisor-verbal-confirmation.record.v1.json",
        "de5cac7a3abb60774786b2a191632d2b146f501274a33f9bb9f2509f5a7ff0ff",
    ),
    "GOV_P4_MANIFEST": _upstream(
        "research/institutional_submission/route_discovery/v1/"
        "gov-p4-institutional-route.manifest.v1.json",
        "f5caf7fa6f3f3b3c85a494f6b2ba070624971fba1a8611c7a95c8f9b3c2b6531",
    ),
    "GOV_P4_VALIDATION": _upstream(
        "research/institutional_submission/route_discovery/v1/"
        "gov-p4-institutional-route.validation.v1.json",
        "d8d1096d2d86446c4e8e9d5f078013258c2f865050918bd9e25586c5e8c49e81",
    ),
    "GOV_P4_ROUTE_RESOLUTION": _upstream(
        "research/institutional_submission/route_discovery/v1/"
        "route-resolution.v1.json",
        "97e60a43fbeed40238823957d2130e8279c459cc00d0d7872a7cfdde48f8f560",
    ),
    "GOV_P4_CONFIRMATION_CHECKLIST": _upstream(
        "research/institutional_submission/route_discovery/v1/"
        "route-confirmation-checklist.vi.v1.md",
        "6cf503232a00b4957d831f12b817cecd1bce7bb053cf51dec79e0bf1de72cbcd",
    ),
}

AUTHORITY_CEILING: dict[str, object] = {
    "authority_status": "AUTHORITY_NOT_ISSUED",
    "collection_authorized": False,
    "d1_go": False,
    "device_gate_decision": "UNVERIFIED",
    "execution_authorized": False,
    "participant_collection_authorized": False,
    "physical_camera_access_authorized": False,
    "production_reconciler_implemented": False,
    "production_reconciler_real_storage_verified": False,
    "real_data_deletion_authorized": False,
    "research_ready": False,
}

BLOCKING_GATES = (
    "ACL_NOT_VERIFIED",
    "B0_3_CUSTODIAN_UNAVAILABLE",
    "B0_3_EXECUTION_AUTHORITY_NOT_ISSUED",
    "CONSENT_FORM_NOT_INSTITUTIONALLY_APPROVED",
    "CURRENT_CYCLE_LATE_ACCEPTANCE_UNCONFIRMED",
    "ENCRYPTION_NOT_VERIFIED",
    "HUMAN_SUBJECTS_REVIEW_ROUTE_UNCONFIRMED",
    "INSTITUTIONAL_APPROVAL_NOT_ISSUED",
    "M2_DEVICE_EVIDENCE_UNVERIFIED",
    "PRODUCTION_RECONCILER_UNIMPLEMENTED",
    "RETENTION_DECISION_NOT_ISSUED",
    "STORAGE_ROOT_NOT_APPROVED",
)

RESIDUALS = (
    "ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY",
    "CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION",
    "HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED",
    "HUMAN_CONFIRMATION_REQUEST_NOT_TRANSMITTED",
)

EXPECTED_QUESTION_BODY: dict[str, object] = {
    "audience": "FACULTY_ADVISOR_FIRST",
    "authority_effect": "NONE",
    "external_transmission_authorized": False,
    "questions": [
        {
            "allowed_future_outcomes": [
                "LATE_SUBMISSION_ACCEPTED_FOR_ROUTING",
                "LATE_SUBMISSION_NOT_ACCEPTED_CURRENT_CYCLE",
                "REFER_TO_AUTHORIZED_UNIT",
            ],
            "current_status": "PENDING_HUMAN_RESPONSE",
            "current_value": None,
            "decision_id": "HC-01",
            "evidence_requirements": [
                "ANSWER_CODE",
                "AUTHORITATIVE_UNIT",
                "RESPONDENT_ROLE",
                "RESPONSE_DATE",
                "EVIDENCE_REFERENCE",
            ],
            "owner_role": "FACULTY_ADVISOR_ROUTE_TO_AUTHORIZED_UNIT",
            "subject": "CURRENT_CYCLE_LATE_SUBMISSION_ACCEPTANCE",
        },
        {
            "allowed_future_outcomes": [
                "SEPARATE_REVIEW_REQUIRED",
                "COVERED_BY_STUDENT_RESEARCH_ROUTE_WITH_AUTHORITY_REFERENCE",
                "REFER_TO_AUTHORIZED_UNIT",
            ],
            "current_status": "PENDING_HUMAN_RESPONSE",
            "current_value": None,
            "decision_id": "HC-02",
            "evidence_requirements": [
                "ANSWER_CODE",
                "REVIEW_BODY",
                "REQUIRED_TEMPLATE_OR_POLICY_REFERENCE",
                "RESPONDENT_ROLE",
                "RESPONSE_DATE",
                "EVIDENCE_REFERENCE",
            ],
            "owner_role": "FACULTY_ADVISOR_ROUTE_TO_AUTHORIZED_UNIT",
            "subject": "HUMAN_SUBJECTS_ETHICS_REVIEW_ROUTE",
        },
    ],
    "submission_state": "NOT_SUBMITTED",
}

_BLANK_RESPONSE_FIELDS: dict[str, object] = {
    "answer_code": None,
    "authority_reference": None,
    "authoritative_unit": None,
    "evidence_reference": None,
    "required_template_or_policy_reference": None,
    "respondent_role": None,
    "response_date": None,
    "review_body": None,
}

EXPECTED_RESPONSE_BODY: dict[str, object] = {
    "authority_effect": "NONE",
    "evidence_classification": None,
    "questions": [
        {"decision_id": "HC-01", **_BLANK_RESPONSE_FIELDS},
        {"decision_id": "HC-02", **_BLANK_RESPONSE_FIELDS},
    ],
    "request_pack_version": 1,
    "response": None,
    "response_state": "UNFILLED",
    "submission_state": "NOT_SUBMITTED",
}

SOURCE_LIMITATIONS = {
    "CANONICAL_PROPOSAL": (
        "The proposal identifies the study and institution but does not prove "
        "late-cycle acceptance, ethics clearance, approval, or collection readiness."
    ),
    "GOV_P2_MANIFEST": (
        "A locally validated advisor-first dossier is not a submission, external "
        "response, or institutional approval."
    ),
    "GOV_P2_DECISION_MATRIX": (
        "Pending decision requests do not prove that any external decision has "
        "been made."
    ),
    "GOV_P3_MANIFEST": (
        "The GOV-P3 manifest records a user-stated verbal decision and is not "
        "written institutional evidence."
    ),
    "GOV_P3_VERBAL_RECORD": (
        "The verbal record is USER_STATED_UNVERIFIED and cannot close either "
        "GOV-P5A question."
    ),
    "GOV_P4_MANIFEST": (
        "The route manifest proves only local structural verification and does "
        "not prove a human response, ethics clearance, or institutional approval."
    ),
    "GOV_P4_VALIDATION": (
        "The GOV-P4 validation does not resolve late acceptance or "
        "human-subjects review requirements."
    ),
    "GOV_P4_ROUTE_RESOLUTION": (
        "The public route resolution does not establish late-cycle acceptance "
        "or a separate ethics determination."
    ),
    "GOV_P4_CONFIRMATION_CHECKLIST": (
        "The checklist contains unresolved questions and is not evidence that "
        "they were answered."
    ),
}


class PackError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: object, *, trailing_newline: bool = True) -> bytes:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return payload + (b"\n" if trailing_newline else b"")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        stat_result = path.lstat()
    except OSError:
        return False
    attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(os.stat_result, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PackError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(_: str) -> NoReturn:
    raise PackError("INVALID_JSON")


def _strict_json(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        parsed = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except PackError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackError("INVALID_JSON") from exc
    if not isinstance(parsed, dict):
        raise PackError("INVALID_JSON")
    document = cast(dict[str, Any], parsed)
    if payload != canonical_json_bytes(document):
        raise PackError("NONCANONICAL_JSON")
    return document


def _envelope(path: Path, *, artifact_kind: str, status: str) -> dict[str, Any]:
    document = _strict_json(path)
    if set(document) != {
        "artifact_kind",
        "body",
        "body_sha256",
        "schema_version",
        "status",
    }:
        raise PackError("ENVELOPE_INVALID")
    if (
        document["artifact_kind"] != artifact_kind
        or document["schema_version"] != 1
        or document["status"] != status
        or not isinstance(document["body"], dict)
        or not isinstance(document["body_sha256"], str)
    ):
        raise PackError("ENVELOPE_INVALID")
    body = cast(dict[str, Any], document["body"])
    if document["body_sha256"] != _sha256(
        canonical_json_bytes(body, trailing_newline=False)
    ):
        raise PackError("BODY_HASH_MISMATCH")
    return body


def _validate_question_matrix(root: Path) -> None:
    body = _envelope(
        root / QUESTION_MATRIX_NAME,
        artifact_kind="GOV_P5_CONFIRMATION_QUESTION_MATRIX",
        status="PENDING_HUMAN_RESPONSE",
    )
    questions = body.get("questions")
    if (
        body.get("authority_effect") != "NONE"
        or body.get("external_transmission_authorized") is not False
        or body.get("submission_state") != "NOT_SUBMITTED"
        or isinstance(questions, list)
        and any(
            isinstance(question, dict)
            and (
                question.get("current_status") != "PENDING_HUMAN_RESPONSE"
                or question.get("current_value") is not None
            )
            for question in questions
        )
    ):
        raise PackError("AUTHORITY_CEILING_VIOLATION")
    if body != EXPECTED_QUESTION_BODY:
        raise PackError("QUESTION_MATRIX_INVALID")


def _contains_filled_response(body: dict[str, Any]) -> bool:
    if (
        body.get("authority_effect") != "NONE"
        or body.get("response_state") != "UNFILLED"
        or body.get("response") is not None
        or body.get("evidence_classification") is not None
        or body.get("submission_state") != "NOT_SUBMITTED"
    ):
        return True
    questions = body.get("questions")
    if not isinstance(questions, list):
        return False
    return any(
        isinstance(question, dict)
        and any(
            value is not None
            for key, value in question.items()
            if key != "decision_id"
        )
        for question in questions
    )


def _validate_response_template(root: Path) -> None:
    body = _envelope(
        root / RESPONSE_TEMPLATE_NAME,
        artifact_kind="GOV_P5_HUMAN_CONFIRMATION_RESPONSE_TEMPLATE",
        status="UNFILLED_TEMPLATE_NOT_EVIDENCE",
    )
    forbidden_keys = {
        "approval_id",
        "authority_status",
        "collection_authorized",
        "decision_date",
        "participant_collection_authorized",
        "research_ready",
        "storage_root",
    }
    if forbidden_keys.intersection(body) or _contains_filled_response(body):
        raise PackError("AUTHORITY_CEILING_VIOLATION")
    if body != EXPECTED_RESPONSE_BODY:
        raise PackError("RESPONSE_TEMPLATE_INVALID")


def _validate_source_index(root: Path) -> None:
    body = _envelope(
        root / SOURCE_INDEX_NAME,
        artifact_kind="GOV_P5_SOURCE_INDEX",
        status="SOURCE_BOUND",
    )
    sources = body.get("sources")
    if not isinstance(sources, list) or len(sources) != len(UPSTREAMS):
        raise PackError("SOURCE_INDEX_INVALID")
    expected = [
        {
            "limitation": SOURCE_LIMITATIONS[role],
            "path": binding.relative_path,
            "role": role,
            "sha256": binding.sha256,
        }
        for role, binding in UPSTREAMS.items()
    ]
    if sources != expected:
        raise PackError("SOURCE_INDEX_INVALID")


def _read_markdown(root: Path, name: str) -> str:
    try:
        payload = (root / name).read_bytes()
        text = payload.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PackError("MARKDOWN_CONTRACT_INVALID") from exc
    if b"\r" in payload or not payload.endswith(b"\n"):
        raise PackError("MARKDOWN_CONTRACT_INVALID")
    return text


def _validate_markdown(root: Path) -> None:
    request = _read_markdown(root, ADVISOR_REQUEST_NAME)
    evidence = _read_markdown(root, EVIDENCE_REQUIREMENTS_NAME)
    request_markers = (
        "DRAFT_REQUEST_PENDING_HUMAN_RESPONSE_NOT_SUBMITTED",
        "29/08/2026",
        "người trưởng thành tình nguyện",
        "webcam",
        "authority hoặc policy reference",
        "chưa được gửi",
        "không phải phản hồi",
        "Không bắt đầu camera",
    )
    evidence_markers = (
        "EVIDENCE_REQUIREMENTS_ONLY_NO_RESPONSE_RECORDED",
        "USER_STATED_UNVERIFIED",
        "không đóng",
        "authority hoặc policy reference",
        "không phải response record",
        "NOT_SUBMITTED",
        "PENDING_HUMAN_RESPONSE",
        "AUTHORITY_NOT_ISSUED",
        "research_ready=false",
        "collection_authorized=false",
    )
    if any(marker not in request for marker in request_markers) or any(
        marker not in evidence for marker in evidence_markers
    ):
        raise PackError("MARKDOWN_CONTRACT_INVALID")
    combined = f"{request}\n{evidence}".lower()
    forbidden = (
        "submission_state=submitted",
        "institutional_approval_status=issued",
        "human_subjects_review_not_required",
        "research_ready=true",
        "collection_authorized=true",
        "participant_collection_authorized=true",
    )
    if any(token in combined for token in forbidden):
        raise PackError("AUTHORITY_CEILING_VIOLATION")


def _validate_upstreams() -> None:
    for binding in UPSTREAMS.values():
        expected_path = ROOT / Path(binding.relative_path)
        try:
            if binding.path.resolve(strict=True) != expected_path.resolve(strict=True):
                raise PackError("UPSTREAM_PATH_MISMATCH")
            if _sha256(binding.path.read_bytes()) != binding.sha256:
                raise PackError("UPSTREAM_HASH_MISMATCH")
        except PackError:
            raise
        except OSError as exc:
            raise PackError("UPSTREAM_HASH_MISMATCH") from exc


def _validated_root(pack_root: Path) -> Path:
    try:
        absolute = Path(os.path.abspath(pack_root))
        if _is_reparse(absolute) or not absolute.is_dir():
            raise PackError("PACK_ROOT_INVALID")
        return absolute.resolve(strict=True)
    except PackError:
        raise
    except OSError as exc:
        raise PackError("PACK_ROOT_INVALID") from exc


def _validate_file_set(root: Path, *, require_generated: bool) -> None:
    required = ALL_NAMES if require_generated else frozenset(REVIEWED_NAMES)
    try:
        entries = tuple(root.iterdir())
    except OSError as exc:
        raise PackError("FILE_SET_MISMATCH") from exc
    names = frozenset(path.name for path in entries)
    if not required.issubset(names) or not names.issubset(ALL_NAMES):
        raise PackError("FILE_SET_MISMATCH")
    if any(_is_reparse(path) or not path.is_file() for path in entries):
        raise PackError("FILE_SET_MISMATCH")


def _validate_sources(pack_root: Path, *, require_generated: bool) -> Path:
    root = _validated_root(pack_root)
    _validate_file_set(root, require_generated=require_generated)
    _validate_upstreams()
    _validate_source_index(root)
    _validate_question_matrix(root)
    _validate_response_template(root)
    _validate_markdown(root)
    return root


def _manifest_document(root: Path) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    for name in sorted(REVIEWED_NAMES):
        payload = (root / name).read_bytes()
        artifacts.append(
            {"path": name, "sha256": _sha256(payload), "size_bytes": len(payload)}
        )
    return {
        "artifact_kind": "GOV_P5_CONFIRMATION_REQUEST_MANIFEST",
        "artifacts": artifacts,
        "schema_version": 1,
        "upstream_bindings": {
            role: {"path": binding.relative_path, "sha256": binding.sha256}
            for role, binding in sorted(UPSTREAMS.items())
        },
    }


def _result(manifest_sha256: str) -> dict[str, object]:
    return {
        "audience": "FACULTY_ADVISOR_FIRST",
        "authority_ceiling": dict(AUTHORITY_CEILING),
        "blocking_gates": list(BLOCKING_GATES),
        "external_transmission_authorized": False,
        "failure_code": None,
        "human_response_status": "PENDING",
        "manifest_sha256": manifest_sha256,
        "residuals": list(RESIDUALS),
        "result": "CONFIRMATION_REQUEST_PACK_VALIDATED",
        "schema_version": 1,
        "status": STATUS,
        "submission_state": "NOT_SUBMITTED",
    }


def _validation_document(manifest_sha256: str) -> dict[str, object]:
    return {
        "artifact_kind": "GOV_P5_CONFIRMATION_REQUEST_VALIDATION",
        **_result(manifest_sha256),
    }


def _write_generated(root: Path, name: str, payload: bytes) -> None:
    target = root / name
    temporary = root / f".{name}.tmp"
    try:
        if target.exists() and (_is_reparse(target) or not target.is_file()):
            raise PackError("OUTPUT_WRITE_FAILED")
        if temporary.exists() or temporary.is_symlink():
            raise PackError("OUTPUT_WRITE_FAILED")
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except PackError:
        raise
    except OSError as exc:
        raise PackError("OUTPUT_WRITE_FAILED") from exc
    finally:
        try:
            if temporary.exists() and not temporary.is_symlink() and temporary.is_file():
                temporary.unlink()
        except OSError:
            pass


def write_pack(pack_root: Path = DEFAULT_PACK_ROOT) -> dict[str, object]:
    root = _validate_sources(Path(pack_root), require_generated=False)
    manifest_bytes = canonical_json_bytes(_manifest_document(root))
    manifest_sha256 = _sha256(manifest_bytes)
    _write_generated(root, MANIFEST_NAME, manifest_bytes)
    _write_generated(
        root,
        VALIDATION_NAME,
        canonical_json_bytes(_validation_document(manifest_sha256)),
    )
    return _result(manifest_sha256)


def check_pack(pack_root: Path = DEFAULT_PACK_ROOT) -> dict[str, object]:
    root = _validate_sources(Path(pack_root), require_generated=True)
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
    return _result(manifest_sha256)


def _failure(code: str) -> dict[str, object]:
    return {
        "audience": "FACULTY_ADVISOR_FIRST",
        "authority_ceiling": dict(AUTHORITY_CEILING),
        "blocking_gates": list(BLOCKING_GATES),
        "external_transmission_authorized": False,
        "failure_code": code,
        "human_response_status": "PENDING",
        "manifest_sha256": None,
        "residuals": list(RESIDUALS),
        "result": "CONFIRMATION_REQUEST_PACK_REJECTED",
        "schema_version": 1,
        "status": "GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_REJECTED",
        "submission_state": "NOT_SUBMITTED",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = write_pack(arguments.pack_root) if arguments.write else check_pack(
            arguments.pack_root
        )
    except PackError as exc:
        result = _failure(exc.code)
        exit_code = 2
    except Exception:
        result = _failure("UNEXPECTED_FAILURE")
        exit_code = 2
    else:
        exit_code = 0
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
