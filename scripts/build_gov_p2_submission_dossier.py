"""Build and verify the non-authorizing GOV-P2 advisor-first dossier."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = ROOT / "research" / "institutional_submission" / "v1"

STATUS = "GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW"
HISTORICAL_DRIFT = "CURRENT_M1_SOURCE_DRIFT_FROM_GOV_P1_HISTORICAL_RECEIPT"
MANIFEST_NAME = "gov-p2-submission.manifest.v1.json"
VALIDATION_NAME = "gov-p2-submission.validation.v1.json"

REVIEWED_NAMES = (
    "advisor-cover.vi.v1.md",
    "decision-request-matrix.v1.json",
    "retention-storage-withdrawal-decision.vi.v1.md",
    "risk-safeguard-statement.vi.v1.md",
    "source-index.v1.json",
)


@dataclass(frozen=True)
class Upstream:
    path: Path
    sha256: str
    role: str
    limitation: str


UPSTREAMS: dict[str, Upstream] = {
    "proposal": Upstream(
        ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5",
        "CANONICAL_PROPOSAL",
        "Does not establish institutional approval or collection readiness.",
    ),
    "gov_p0_manifest": Upstream(
        ROOT / "research" / "pre_collection" / "v1" / "pre-collection-pack.manifest.v1.json",
        "c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025",
        "GOV_P0_HISTORICAL_MANIFEST",
        "Structural GOV-P0 validation does not establish institutional approval "
        "or collection readiness.",
    ),
    "gov_p1_manifest": Upstream(
        ROOT / "research" / "pre_collection" / "gov_p1" / "v1" / "gov-p1-pack.manifest.v1.json",
        "76fe01de697f44ba82208bd40ce1f14eb9f4df993076c3984ff15906620aa9b4",
        "GOV_P1_HISTORICAL_MANIFEST",
        "Historical synthetic GOV-P1 evidence does not establish institutional "
        "approval, production deletion, or collection readiness.",
    ),
    "gov_p1_dossier": Upstream(
        ROOT
        / "research"
        / "pre_collection"
        / "gov_p1"
        / "v1"
        / "submission-dossier.vi.draft.v1.md",
        "45b29e79698ee39a0377243980d463bba1d718c3ee27b9f49ebb2c502f6c3afd",
        "GOV_P1_DOSSIER_SOURCE",
        "Draft dossier content does not establish institutional approval or collection readiness.",
    ),
    "gov_p1_decision": Upstream(
        ROOT
        / "research"
        / "pre_collection"
        / "gov_p1"
        / "v1"
        / "external-decision-record.template.v1.json",
        "549212658ee2e4210a2a72396ead4a1a40afa0ac4bb91854f84bb5c87691f130",
        "GOV_P1_DECISION_TEMPLATE_SOURCE",
        "A blocked decision template does not establish institutional approval "
        "or collection readiness.",
    ),
    "gov_p0_consent": Upstream(
        ROOT / "research" / "pre_collection" / "v1" / "consent-form.vi.draft.v1.md",
        "eaa0aaa651b3b4ca8778e0f5aa1b48c4663489cf9a4af880b661d57d627b5a71",
        "GOV_P0_CONSENT_DRAFT_SOURCE",
        "A draft consent form cannot be issued and does not establish institutional "
        "approval or collection readiness.",
    ),
    "gov_p0_information": Upstream(
        ROOT / "research" / "pre_collection" / "v1" / "participant-information.vi.draft.v1.md",
        "ff2687d32f55bac9e00f9944c5db86d24d2d2480dee9cdca87241b76729c5c05",
        "GOV_P0_PARTICIPANT_INFORMATION_DRAFT_SOURCE",
        "A draft information sheet is not an invitation and does not establish "
        "institutional approval or collection readiness.",
    ),
}

ANNEX_SOURCES: dict[str, Path] = {
    "annex-a-gov-p1-submission-dossier.vi.draft.v1.md": UPSTREAMS["gov_p1_dossier"].path,
    "annex-b-consent-form.vi.draft.v1.md": UPSTREAMS["gov_p0_consent"].path,
    "annex-c-participant-information.vi.draft.v1.md": UPSTREAMS["gov_p0_information"].path,
    "annex-d-external-decision-record.template.v1.json": UPSTREAMS["gov_p1_decision"].path,
}
GENERATED_NAMES = (*ANNEX_SOURCES, MANIFEST_NAME, VALIDATION_NAME)
SOURCE_AND_ANNEX_NAMES = tuple(sorted((*REVIEWED_NAMES, *ANNEX_SOURCES)))
ALL_NAMES = frozenset((*REVIEWED_NAMES, *GENERATED_NAMES))

GOV_P1_HISTORICAL_M1_SHA256 = (
    "1d28ed877573e99d928516bd8d76490e845a5a030ed23048d6f2931f38e5c67e"
)
CURRENT_M1_SOURCE = ROOT / "src" / "pdu_exam_observer" / "m1.py"

BLOCKING_GATES = tuple(
    sorted(
        (
            "ACL_NOT_VERIFIED",
            "ADVISOR_REVIEW_NOT_COMPLETED",
            "B0_3_CUSTODIAN_UNAVAILABLE",
            "B0_3_EXECUTION_AUTHORITY_NOT_ISSUED",
            "CONSENT_FORM_NOT_INSTITUTIONALLY_APPROVED",
            "ENCRYPTION_NOT_VERIFIED",
            "INSTITUTIONAL_APPROVAL_NOT_ISSUED",
            "INSTITUTIONAL_REVIEW_ROUTE_NOT_CONFIRMED",
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
    )
)

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

EXPECTED_DECISIONS: list[dict[str, object]] = [
    {
        "blocking_gate": "ADVISOR_REVIEW_NOT_COMPLETED",
        "current_status": "PENDING_EXTERNAL_DECISION",
        "current_value": None,
        "decision_id": "ADV-01",
        "owner_role": "FACULTY_ADVISOR",
        "requested_output": [
            "READY_FOR_INSTITUTIONAL_ROUTING",
            "REVISION_REQUIRED",
            "DO_NOT_ADVANCE",
        ],
        "subject": "PROTOCOL_AND_SCOPE_REVIEW",
    },
    {
        "blocking_gate": "INSTITUTIONAL_REVIEW_ROUTE_NOT_CONFIRMED",
        "current_status": "PENDING_EXTERNAL_DECISION",
        "current_value": None,
        "decision_id": "ADV-02",
        "owner_role": "FACULTY_ADVISOR",
        "requested_output": [
            "APPROVING_UNIT",
            "REQUIRED_TEMPLATE",
            "REQUIRED_SIGNATURE_ROLES",
        ],
        "subject": "INSTITUTIONAL_ROUTE_IDENTIFICATION",
    },
    {
        "blocking_gate": "INSTITUTIONAL_APPROVAL_NOT_ISSUED",
        "current_status": "PENDING_EXTERNAL_DECISION",
        "current_value": None,
        "decision_id": "EXT-01",
        "owner_role": "INSTITUTIONAL_AUTHORITY",
        "requested_output": ["APPROVAL_STATUS", "APPROVAL_ID", "ISSUER", "DECISION_DATE"],
        "subject": "INSTITUTIONAL_APPROVAL",
    },
    {
        "blocking_gate": "CONSENT_FORM_NOT_INSTITUTIONALLY_APPROVED",
        "current_status": "PENDING_EXTERNAL_DECISION",
        "current_value": None,
        "decision_id": "EXT-02",
        "owner_role": "INSTITUTIONAL_AUTHORITY",
        "requested_output": ["PARTICIPANT_INFORMATION_VERSION", "CONSENT_VERSION"],
        "subject": "PARTICIPANT_INFORMATION_AND_CONSENT",
    },
    {
        "blocking_gate": "RETENTION_DECISION_NOT_ISSUED",
        "current_status": "PENDING_EXTERNAL_DECISION",
        "current_value": None,
        "decision_id": "EXT-03",
        "owner_role": "INSTITUTIONAL_AUTHORITY",
        "requested_output": ["RETENTION_END_DATE_OR_POLICY_REFERENCE"],
        "subject": "RETENTION_DECISION",
    },
    {
        "blocking_gate": "STORAGE_ROOT_NOT_APPROVED",
        "current_status": "PENDING_EXTERNAL_DECISION",
        "current_value": None,
        "decision_id": "EXT-04",
        "owner_role": "INSTITUTIONAL_AUTHORITY",
        "requested_output": [
            "APPROVED_STORAGE_ROOT_REFERENCE",
            "ENCRYPTION_EVIDENCE",
            "ACL_EVIDENCE",
            "ATTESTOR",
        ],
        "subject": "STORAGE_ENCRYPTION_AND_ACL",
    },
    {
        "blocking_gate": "RESPONSIBLE_AND_WITHDRAWAL_CONTACTS_UNASSIGNED",
        "current_status": "PENDING_EXTERNAL_DECISION",
        "current_value": None,
        "decision_id": "EXT-05",
        "owner_role": "INSTITUTIONAL_AUTHORITY",
        "requested_output": [
            "RESPONSIBLE_CONTACT",
            "WITHDRAWAL_CONTACT",
            "WITHDRAWAL_PROCEDURE_REFERENCE",
        ],
        "subject": "RESPONSIBLE_AND_WITHDRAWAL_CONTACTS",
    },
]


class PackError(ValueError):
    """A bounded, sanitized GOV-P2 failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: object, *, trailing_newline: bool = True) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise PackError("INVALID_JSON") from exc
    if trailing_newline:
        text += "\n"
    return text.encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return True
    return path.is_symlink() or bool(attributes & 0x400)


def _verify_exact_input(actual: Path, expected: Path, expected_sha256: str) -> None:
    try:
        actual_absolute = Path(os.path.abspath(actual))
        expected_absolute = Path(os.path.abspath(expected))
        if os.path.normcase(str(actual_absolute)) != os.path.normcase(str(expected_absolute)):
            raise PackError("UPSTREAM_PATH_MISMATCH")
        if _is_reparse(actual_absolute) or not actual_absolute.is_file():
            raise PackError("UPSTREAM_PATH_MISMATCH")
        digest = _sha256(actual_absolute.read_bytes())
    except PackError:
        raise
    except OSError as exc:
        raise PackError("UPSTREAM_HASH_MISMATCH") from exc
    if digest != expected_sha256:
        raise PackError("UPSTREAM_HASH_MISMATCH")


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


def _envelope(path: Path, *, kind: str, status: str) -> dict[str, Any]:
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


def _source_index_body() -> dict[str, object]:
    sources = [
        {
            "limitation": upstream.limitation,
            "path": upstream.path.relative_to(ROOT).as_posix(),
            "role": upstream.role,
            "sha256": upstream.sha256,
        }
        for upstream in UPSTREAMS.values()
    ]
    return {
        "sources": sources,
        "upstream_status": "HISTORICAL_EVIDENCE_PINNED_CURRENT_M1_SOURCE_DRIFT_RECORDED",
    }


def _validate_source_index(pack_root: Path) -> None:
    body = _envelope(
        pack_root / "source-index.v1.json",
        kind="GOV_P2_SOURCE_INDEX",
        status="SOURCE_PINNED_PENDING_EXTERNAL_REVIEW",
    )
    if body != _source_index_body():
        raise PackError("SOURCE_INDEX_INVALID")


def _validate_decision_matrix(pack_root: Path) -> None:
    body = _envelope(
        pack_root / "decision-request-matrix.v1.json",
        kind="GOV_P2_DECISION_REQUEST_MATRIX",
        status="PENDING_EXTERNAL_DECISION",
    )
    decisions = body.get("decisions")
    if (
        body.get("research_ready") is not False
        or body.get("collection_authorized") is not False
        or "authority_status" in body
        or not isinstance(decisions, list)
        or any(
            not isinstance(decision, dict)
            or decision.get("current_status") != "PENDING_EXTERNAL_DECISION"
            or decision.get("current_value") is not None
            for decision in decisions
        )
    ):
        raise PackError("AUTHORITY_CEILING_VIOLATION")
    expected: dict[str, object] = {
        "authority_effect": "NONE",
        "collection_authorized": False,
        "decisions": EXPECTED_DECISIONS,
        "research_ready": False,
        "review_route": "FACULTY_ADVISOR_FIRST",
        "submission_state": "NOT_SUBMITTED",
    }
    if body != expected:
        raise PackError("DECISION_MATRIX_INVALID")


def _read_markdown(pack_root: Path, name: str) -> str:
    try:
        raw = (pack_root / name).read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PackError("MARKDOWN_CONTRACT_INVALID") from exc
    if b"\r" in raw or not raw.endswith(b"\n"):
        raise PackError("MARKDOWN_CONTRACT_INVALID")
    return text


def _validate_markdown(pack_root: Path) -> None:
    cover = _read_markdown(pack_root, "advisor-cover.vi.v1.md")
    risk = _read_markdown(pack_root, "risk-safeguard-statement.vi.v1.md")
    decision = _read_markdown(pack_root, "retention-storage-withdrawal-decision.vi.v1.md")
    cover_markers = (
        "DRAFT_FOR_ADVISOR_REVIEW_NOT_SUBMITTED",
        "FACULTY_ADVISOR_FIRST",
        "NOT_SUBMITTED",
        "READY_FOR_INSTITUTIONAL_ROUTING",
        "REVISION_REQUIRED",
        "DO_NOT_ADVANCE",
        "không phải advisor decision",
        "quản lý ngoài repository",
    )
    risk_markers = (
        "synthetic",
        "Raw video chỉ lưu cục bộ",
        "con người xem xét",
        "không phải kết luận kỷ luật tự động",
        "Pilot",
        "confirmatory",
        "Withdrawal",
        "hostile same-account race resistance",
    )
    decision_markers = (
        "Status: `PENDING_EXTERNAL_DECISION`",
        "Retention mode",
        "Approved storage-root reference",
        "Encryption evidence",
        "ACL evidence",
        "Responsible contact",
        "Withdrawal contact",
        "Institutional route",
        "AUTHORITY_NOT_ISSUED",
        "research_ready=false",
        "collection_authorized=false",
    )
    if (
        any(marker not in cover for marker in cover_markers)
        or any(marker not in risk for marker in risk_markers)
        or any(marker not in decision for marker in decision_markers)
        or decision.count("PENDING_EXTERNAL_DECISION") < 8
    ):
        raise PackError("MARKDOWN_CONTRACT_INVALID")
    forbidden = (
        "institutional_approval_id=",
        "approval_id=",
        "decision_issuer=",
        "approved_storage_root=",
        "student_name=",
        "student_id=",
    )
    combined = "\n".join((cover, risk, decision)).lower()
    if any(token in combined for token in forbidden):
        raise PackError("AUTHORITY_CEILING_VIOLATION")


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


def _validate_file_set(pack_root: Path, *, require_generated: bool) -> None:
    expected = ALL_NAMES if require_generated else frozenset(REVIEWED_NAMES)
    try:
        entries = tuple(pack_root.iterdir())
    except OSError as exc:
        raise PackError("FILE_SET_MISMATCH") from exc
    names = frozenset(path.name for path in entries)
    if not expected.issubset(names) or not names.issubset(ALL_NAMES):
        raise PackError("FILE_SET_MISMATCH")
    if any(_is_reparse(path) or not path.is_file() for path in entries):
        raise PackError("FILE_SET_MISMATCH")


def _validate_upstreams() -> None:
    for upstream in UPSTREAMS.values():
        _verify_exact_input(upstream.path, upstream.path, upstream.sha256)
    try:
        gov_p1 = _strict_json(UPSTREAMS["gov_p1_manifest"].path)
        historical_sha = gov_p1.get("m1_source_sha256")
        current_sha = _sha256(CURRENT_M1_SOURCE.read_bytes())
    except OSError as exc:
        raise PackError("UPSTREAM_HASH_MISMATCH") from exc
    if historical_sha != GOV_P1_HISTORICAL_M1_SHA256 or current_sha == historical_sha:
        raise PackError("SOURCE_INDEX_INVALID")


def _validate_sources(pack_root: Path, *, require_generated: bool) -> Path:
    root = _validated_root(pack_root)
    _validate_file_set(root, require_generated=require_generated)
    _validate_upstreams()
    _validate_source_index(root)
    _validate_decision_matrix(root)
    _validate_markdown(root)
    return root


def _validate_annexes(pack_root: Path) -> None:
    for annex_name, source_path in ANNEX_SOURCES.items():
        try:
            if (pack_root / annex_name).read_bytes() != source_path.read_bytes():
                raise PackError("ANNEX_MISMATCH")
        except PackError:
            raise
        except OSError as exc:
            raise PackError("ANNEX_MISMATCH") from exc


def _manifest_document(pack_root: Path) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    for name in SOURCE_AND_ANNEX_NAMES:
        payload = (pack_root / name).read_bytes()
        artifacts.append({"path": name, "sha256": _sha256(payload), "size_bytes": len(payload)})
    return {
        "artifact_kind": "GOV_P2_SUBMISSION_MANIFEST",
        "artifacts": artifacts,
        "schema_version": 1,
        "upstream_bindings": {
            "gov_p0_manifest_sha256": UPSTREAMS["gov_p0_manifest"].sha256,
            "gov_p1_historical_manifest_sha256": UPSTREAMS["gov_p1_manifest"].sha256,
            "proposal_sha256": UPSTREAMS["proposal"].sha256,
        },
    }


def _result(manifest_sha256: str) -> dict[str, object]:
    return {
        "audience": "FACULTY_ADVISOR_FIRST",
        "authority_ceiling": dict(AUTHORITY_CEILING),
        "blocking_gates": list(BLOCKING_GATES),
        "external_review_status": "PENDING",
        "failure_code": None,
        "manifest_sha256": manifest_sha256,
        "residuals": [HISTORICAL_DRIFT],
        "result": "DOSSIER_VALIDATED",
        "schema_version": 1,
        "status": STATUS,
        "structure_valid": True,
        "submission_state": "NOT_SUBMITTED",
    }


def _validation_document(manifest_sha256: str) -> dict[str, object]:
    return {"artifact_kind": "GOV_P2_SUBMISSION_VALIDATION", **_result(manifest_sha256)}


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
    """Validate reviewed sources and write only fixed generated GOV-P2 leaves."""

    root = _validate_sources(Path(pack_root), require_generated=False)
    for annex_name, source_path in ANNEX_SOURCES.items():
        try:
            payload = source_path.read_bytes()
        except OSError as exc:
            raise PackError("UPSTREAM_HASH_MISMATCH") from exc
        _write_generated(root, annex_name, payload)
    _validate_annexes(root)
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
    """Read-only verification of exact GOV-P2 source and generated bytes."""

    root = _validate_sources(Path(pack_root), require_generated=True)
    _validate_annexes(root)
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
        "external_review_status": "PENDING",
        "failure_code": code,
        "manifest_sha256": None,
        "residuals": [HISTORICAL_DRIFT],
        "result": "DOSSIER_REJECTED",
        "schema_version": 1,
        "status": "GOV_P2_SUBMISSION_DOSSIER_REJECTED",
        "structure_valid": False,
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
