"""Build and verify the fail-closed GOV-P4 institutional route pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = (
    ROOT / "research" / "institutional_submission" / "route_discovery" / "v1"
)

SOURCE_REGISTER_NAME = "official-source-register.v1.json"
ROUTE_RESOLUTION_NAME = "route-resolution.v1.json"
ROUTE_BRIEF_NAME = "route-brief.vi.v1.md"
CHECKLIST_NAME = "route-confirmation-checklist.vi.v1.md"
MANIFEST_NAME = "gov-p4-institutional-route.manifest.v1.json"
VALIDATION_NAME = "gov-p4-institutional-route.validation.v1.json"
REVIEWED_NAMES = (
    SOURCE_REGISTER_NAME,
    ROUTE_RESOLUTION_NAME,
    ROUTE_BRIEF_NAME,
    CHECKLIST_NAME,
)
GENERATED_NAMES = (MANIFEST_NAME, VALIDATION_NAME)
ALL_NAMES = frozenset((*REVIEWED_NAMES, *GENERATED_NAMES))

STATUS = (
    "GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_"
    "UNCONFIRMED_APPROVAL_NOT_ISSUED"
)


@dataclass(frozen=True)
class Upstream:
    path: Path
    relative_path: str
    sha256: str


UPSTREAMS = {
    "canonical_proposal": Upstream(
        path=ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        relative_path="docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        sha256="2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5",
    ),
    "gov_p2_manifest": Upstream(
        path=ROOT
        / "research"
        / "institutional_submission"
        / "v1"
        / "gov-p2-submission.manifest.v1.json",
        relative_path=(
            "research/institutional_submission/v1/"
            "gov-p2-submission.manifest.v1.json"
        ),
        sha256="1e7750308f0f1efedf269b30f8373cc26210a594dcc805d7cfa991c2fe425b1e",
    ),
    "gov_p3_record": Upstream(
        path=ROOT
        / "research"
        / "institutional_submission"
        / "advisor_decision"
        / "v1"
        / "advisor-verbal-confirmation.record.v1.json",
        relative_path=(
            "research/institutional_submission/advisor_decision/v1/"
            "advisor-verbal-confirmation.record.v1.json"
        ),
        sha256="de5cac7a3abb60774786b2a191632d2b146f501274a33f9bb9f2509f5a7ff0ff",
    ),
    "gov_p3_manifest": Upstream(
        path=ROOT
        / "research"
        / "institutional_submission"
        / "advisor_decision"
        / "v1"
        / "gov-p3-advisor-decision.manifest.v1.json",
        relative_path=(
            "research/institutional_submission/advisor_decision/v1/"
            "gov-p3-advisor-decision.manifest.v1.json"
        ),
        sha256="7163fe330a1113f2319b946a253228a5f46c28b001eedfcb64e1b6823603b605",
    ),
    "gov_p3_validation": Upstream(
        path=ROOT
        / "research"
        / "institutional_submission"
        / "advisor_decision"
        / "v1"
        / "gov-p3-advisor-decision.validation.v1.json",
        relative_path=(
            "research/institutional_submission/advisor_decision/v1/"
            "gov-p3-advisor-decision.validation.v1.json"
        ),
        sha256="0b6f8c3e54dabb3590fb56fd620eba20d5dbe1f537ae91fadb7f57751794610c",
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
    "CURRENT_CYCLE_SUBMISSION_ACCEPTANCE_UNCONFIRMED",
    "ENCRYPTION_NOT_VERIFIED",
    "HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED",
    "INSTITUTIONAL_APPROVAL_NOT_ISSUED",
    "LABELBOOK_NOT_FROZEN",
    "M2_DEVICE_EVIDENCE_UNVERIFIED",
    "M3_NOT_OPENED",
    "METHOD_THRESHOLDS_NOT_LOCKED",
    "PRODUCTION_RECONCILER_UNIMPLEMENTED",
    "PROTOCOL_NOT_FROZEN",
    "RESEARCH_COLLECTION_NOT_IMPLEMENTED",
    "RETENTION_DECISION_NOT_ISSUED",
    "STORAGE_ROOT_NOT_APPROVED",
)

RESIDUALS = (
    "ADVISOR_DECISION_EVIDENCE_USER_STATED_ONLY",
    "CURRENT_CYCLE_DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION",
    "HUMAN_SUBJECTS_ETHICS_REVIEW_REQUIREMENT_UNCONFIRMED",
)

EXPECTED_SOURCE_BODY: dict[str, object] = {
    "institution": "TRUONG_DAI_HOC_PHAM_VAN_DONG",
    "retrieved_on": "2026-08-31",
    "sources": [
        {
            "artifact_url": (
                "https://drive.google.com/file/d/"
                "1AUwWV4nbkSZtRneI-kaPizTyoJPwF9OZ/preview"
            ),
            "content_sha256": (
                "4deef2d10974d5bbb3b0f4032bfcd0c3c60e867601de439bf63dd3c0be1605eb"
            ),
            "evidence_classification": "SOURCE_VERIFIED_PUBLIC_PRIMARY_SOURCE",
            "landing_page_url": (
                "https://www.pdu.edu.vn/a/index.php?dept=32&disd=&tid=9890"
            ),
            "limitation": (
                "Does not determine whether this webcam study requires a separate "
                "human-subjects ethics review."
            ),
            "publication_date": "2022-03-07",
            "publisher": "TRUONG_DAI_HOC_PHAM_VAN_DONG",
            "size_bytes": 800911,
            "source_id": "PDU-REG-2022",
            "source_type": "PUBLIC_PDF",
            "supports": [
                "FACULTY_COUNCIL_REVIEW",
                "FORMS_1_TO_6",
                "RESEARCH_OFFICE_FORWARDING",
                "RECTOR_APPROVAL_DECISION",
                "BEGIN_ONLY_AFTER_APPROVAL",
            ],
            "title": "Quyet dinh 104 va Quy dinh hoat dong NCKH cua sinh vien",
        },
        {
            "artifact_url": (
                "https://drive.google.com/file/d/"
                "1GP8PQll44yIPQnhdkBOde-Zj6F6fqWvn/preview"
            ),
            "content_sha256": (
                "e8daa3697b6b65f69cf47404c0be0d072382717964b1d3e31b36efc5654747ab"
            ),
            "evidence_classification": "SOURCE_VERIFIED_PUBLIC_PRIMARY_SOURCE",
            "landing_page_url": (
                "https://www.pdu.edu.vn/a/index.php?dept=32&disd=&tid=12204"
            ),
            "limitation": (
                "The 2026-2027 registration deadline has passed; late acceptance "
                "is not established."
            ),
            "publication_date": "2026-08-10",
            "publisher": "TRUONG_DAI_HOC_PHAM_VAN_DONG",
            "size_bytes": 586224,
            "source_id": "PDU-NOTICE-2026-2027",
            "source_type": "PUBLIC_PDF",
            "supports": [
                "CURRENT_CYCLE_PROCESS",
                "FACULTY_REVIEW_WINDOW",
                "FORMS_1_TO_6",
                "FACULTY_FORWARDS_TO_RESEARCH_OFFICE",
            ],
            "title": (
                "Thong bao dang ky de xuat de tai NCKH sinh vien nam hoc "
                "2026-2027"
            ),
        },
        {
            "artifact_url": (
                "https://docs.google.com/document/d/"
                "1FSyLSGI6YOhwR4t5z4S6gI1K9vuGtbnC/edit"
            ),
            "content_sha256": (
                "d922de642841d7dd6160e33bf69c15098eaa8bd14f46f5c74f7cf2688ddea931"
            ),
            "evidence_classification": "SOURCE_VERIFIED_PUBLIC_PRIMARY_SOURCE",
            "landing_page_url": (
                "https://www.pdu.edu.vn/a/index.php?dept=32&disd=&kh=0802"
            ),
            "limitation": (
                "Template signatures do not themselves issue institutional or "
                "ethics approval."
            ),
            "publication_date": "2026-04-21",
            "publisher": "TRUONG_DAI_HOC_PHAM_VAN_DONG",
            "size_bytes": 229662,
            "source_id": "PDU-FORMS-2026",
            "source_type": "PUBLIC_DOCX",
            "supports": [
                "CURRENT_TEMPLATE_SET",
                "FORM_2_SIGNATURE_ROLES",
                "FORM_5_COUNCIL_CHAIR",
                "FORM_6_FACULTY_LEADERSHIP",
            ],
            "title": "Phu luc bieu mau NCKH cua sinh vien 2026",
        },
    ],
}

EXPECTED_ROUTE_BODY: dict[str, object] = {
    "administrative_unit": "PHONG_QUAN_LY_KHOA_HOC",
    "adv_02_status": "SATISFIED_BY_PUBLIC_PRIMARY_SOURCES",
    "approval_id": None,
    "approval_issuer_role": "HIEU_TRUONG",
    "authority_effect": "NONE",
    "collection_authorized": False,
    "consent_form_institutional_status": "PENDING_EXTERNAL_DECISION",
    "current_cycle_deadline_status": "DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION",
    "decision_date": None,
    "external_submission_authorized": False,
    "faculty": "KHOA_CONG_NGHE_THONG_TIN",
    "human_subjects_review_requirement": "UNKNOWN_PENDING_CONFIRMATION",
    "institution": "TRUONG_DAI_HOC_PHAM_VAN_DONG",
    "institutional_approval_status": "NOT_ISSUED",
    "institutional_route_status": "SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED",
    "participant_collection_authorized": False,
    "proposal_review_body": "HOI_DONG_KHOA",
    "required_signature_roles": {
        "MAU_2": [
            "LANH_DAO_KHOA",
            "GIANG_VIEN_HUONG_DAN",
            "SINH_VIEN_CHIU_TRACH_NHIEM_CHINH",
        ],
        "MAU_3": ["LANH_DAO_KHOA"],
        "MAU_5": ["CHU_TICH_HOI_DONG"],
        "MAU_6": ["LANH_DAO_KHOA"],
    },
    "required_templates": ["MAU_1", "MAU_2", "MAU_3", "MAU_4", "MAU_5", "MAU_6"],
    "research_ready": False,
    "retention_storage_withdrawal_status": "PENDING_EXTERNAL_DECISION",
    "route_steps": [
        "STUDENT_PREPARES_FORMS_1_TO_3",
        "FACULTY_COUNCIL_REVIEWS_WITH_FORM_4",
        "FACULTY_COUNCIL_RECORDS_MINUTES_WITH_FORM_5",
        "FACULTY_PREPARES_APPROVED_LIST_WITH_FORM_6",
        "FACULTY_FORWARDS_FORMS_1_TO_6_TO_RESEARCH_OFFICE",
        "RESEARCH_OFFICE_ADVISES_RECTOR",
        "RECTOR_ISSUES_APPROVAL_DECISION",
        "STUDENT_BEGINS_ONLY_AFTER_APPROVAL_DECISION",
    ],
    "submission_state": "NOT_SUBMITTED",
}


class PackError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: object, *, trailing_newline: bool = True) -> bytes:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
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


def _strict_json(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        parsed = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
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


def _envelope(
    path: Path,
    *,
    artifact_kind: str,
    status: str,
) -> dict[str, Any]:
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
    body_hash = _sha256(canonical_json_bytes(body, trailing_newline=False))
    if document["body_sha256"] != body_hash:
        raise PackError("BODY_HASH_MISMATCH")
    return body


def _validate_source_register(root: Path) -> None:
    body = _envelope(
        root / SOURCE_REGISTER_NAME,
        artifact_kind="GOV_P4_OFFICIAL_SOURCE_REGISTER",
        status="SOURCE_VERIFIED_PUBLIC_PRIMARY_SOURCES",
    )
    if body != EXPECTED_SOURCE_BODY:
        raise PackError("SOURCE_REGISTER_INVALID")


def _validate_route_resolution(root: Path) -> None:
    body = _envelope(
        root / ROUTE_RESOLUTION_NAME,
        artifact_kind="GOV_P4_ROUTE_RESOLUTION",
        status="SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED",
    )
    if (
        body.get("institutional_approval_status") != "NOT_ISSUED"
        or body.get("approval_id") is not None
        or body.get("decision_date") is not None
        or body.get("human_subjects_review_requirement")
        != "UNKNOWN_PENDING_CONFIRMATION"
        or body.get("consent_form_institutional_status")
        != "PENDING_EXTERNAL_DECISION"
        or body.get("retention_storage_withdrawal_status")
        != "PENDING_EXTERNAL_DECISION"
        or body.get("authority_effect") != "NONE"
        or body.get("external_submission_authorized") is not False
        or body.get("research_ready") is not False
        or body.get("collection_authorized") is not False
        or body.get("participant_collection_authorized") is not False
    ):
        raise PackError("AUTHORITY_CEILING_VIOLATION")
    if body != EXPECTED_ROUTE_BODY:
        raise PackError("ROUTE_RESOLUTION_INVALID")


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
    brief = _read_markdown(root, ROUTE_BRIEF_NAME)
    checklist = _read_markdown(root, CHECKLIST_NAME)
    brief_markers = (
        "SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED_APPROVAL_NOT_ISSUED",
        "Hội đồng khoa",
        "Phòng Quản lý Khoa học",
        "Hiệu trưởng",
        "Mẫu 1-6",
        "checker không tự tải lại từ mạng",
        "UNKNOWN_PENDING_CONFIRMATION",
        "institutional_approval_status=NOT_ISSUED",
        "submission_state=NOT_SUBMITTED",
    )
    checklist_markers = (
        "PENDING_HUMAN_CONFIRMATION_NOT_SUBMITTED",
        "29/08/2026",
        "hội đồng đạo đức",
        "consent",
        "Retention",
        "approved storage root",
        "withdrawal",
        "Không gửi email, upload, nộp hồ sơ",
        "Không bắt đầu camera",
    )
    if any(marker not in brief for marker in brief_markers) or any(
        marker not in checklist for marker in checklist_markers
    ):
        raise PackError("MARKDOWN_CONTRACT_INVALID")
    combined = f"{brief}\n{checklist}".lower()
    forbidden = (
        "institutional_approval_status=issued",
        "submission_state=submitted",
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
    _validate_source_register(root)
    _validate_route_resolution(root)
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
        "artifact_kind": "GOV_P4_INSTITUTIONAL_ROUTE_MANIFEST",
        "artifacts": artifacts,
        "schema_version": 1,
        "upstream_bindings": {
            name: {"path": binding.relative_path, "sha256": binding.sha256}
            for name, binding in sorted(UPSTREAMS.items())
        },
    }


def _result(manifest_sha256: str) -> dict[str, object]:
    return {
        "adv_02_status": "SATISFIED_BY_PUBLIC_PRIMARY_SOURCES",
        "authority_ceiling": dict(AUTHORITY_CEILING),
        "blocking_gates": list(BLOCKING_GATES),
        "external_submission_authorized": False,
        "failure_code": None,
        "human_subjects_review_requirement": "UNKNOWN_PENDING_CONFIRMATION",
        "institutional_approval_status": "NOT_ISSUED",
        "institutional_route_status": "SOURCE_VERIFIED_PUBLIC_ROUTE_IDENTIFIED",
        "manifest_sha256": manifest_sha256,
        "residuals": list(RESIDUALS),
        "result": "ROUTE_PACK_VALIDATED",
        "schema_version": 1,
        "status": STATUS,
        "submission_state": "NOT_SUBMITTED",
    }


def _validation_document(manifest_sha256: str) -> dict[str, object]:
    return {"artifact_kind": "GOV_P4_INSTITUTIONAL_ROUTE_VALIDATION", **_result(manifest_sha256)}


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
        "adv_02_status": "UNRESOLVED",
        "authority_ceiling": dict(AUTHORITY_CEILING),
        "blocking_gates": list(BLOCKING_GATES),
        "external_submission_authorized": False,
        "failure_code": code,
        "human_subjects_review_requirement": "UNKNOWN_PENDING_CONFIRMATION",
        "institutional_approval_status": "NOT_ISSUED",
        "institutional_route_status": "UNRESOLVED",
        "manifest_sha256": None,
        "residuals": list(RESIDUALS),
        "result": "ROUTE_PACK_REJECTED",
        "schema_version": 1,
        "status": "GOV_P4_INSTITUTIONAL_ROUTE_PACK_REJECTED",
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
        result = (
            write_pack(arguments.pack_root)
            if arguments.write
            else check_pack(arguments.pack_root)
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
