"""Build and verify the synthetic-only GOV-P1 governance pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from run_gov_p1_rehearsal import (
    BLOCKING_GATES,
    CANONICAL_GOV_P0_MANIFEST_SHA256,
    CANONICAL_PROPOSAL_SHA256,
    DEFAULT_GOV_P0_MANIFEST,
    DEFAULT_M1_SOURCE,
    DEFAULT_PACK_ROOT,
    DEFAULT_PROPOSAL,
    DEFAULT_RUNNER_SOURCE,
    RECEIPT_NAME,
    RECEIPT_STATUS,
    REVIEWED_CONTRACT_SHA256,
    RehearsalError,
    _verify_live_source_paths,
    canonical_json_bytes,
    load_contract,
    write_generated_file,
)

CONTRACT_NAME = "rehearsal-contract.v1.json"
DECISION_NAME = "external-decision-record.template.v1.json"
DOSSIER_NAME = "submission-dossier.vi.draft.v1.md"
MANIFEST_NAME = "gov-p1-pack.manifest.v1.json"
VALIDATION_NAME = "gov-p1-pack.validation.v1.json"
SOURCE_ARTIFACTS = tuple(sorted((CONTRACT_NAME, DECISION_NAME, DOSSIER_NAME, RECEIPT_NAME)))
ALL_ARTIFACTS = frozenset((*SOURCE_ARTIFACTS, MANIFEST_NAME, VALIDATION_NAME))
REVIEWED_SOURCE_SHA256 = {
    CONTRACT_NAME: REVIEWED_CONTRACT_SHA256,
    DECISION_NAME: "549212658ee2e4210a2a72396ead4a1a40afa0ac4bb91854f84bb5c87691f130",
    DOSSIER_NAME: "45b29e79698ee39a0377243980d463bba1d718c3ee27b9f49ebb2c502f6c3afd",
}


class PackError(ValueError):
    """A bounded, sanitized GOV-P1 pack failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path, code: str) -> str:
    try:
        return _sha256(path.read_bytes())
    except OSError as exc:
        raise PackError(code) from exc


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
    try:
        canonical = canonical_json_bytes(value)
    except RehearsalError as exc:
        raise PackError(exc.code) from exc
    if canonical != raw:
        raise PackError("NONCANONICAL_JSON")
    return value


def _envelope(path: Path, *, kind: str, status: str) -> tuple[dict[str, Any], str]:
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
    body_hash = document.get("body_sha256")
    if not isinstance(body, dict) or not isinstance(body_hash, str):
        raise PackError("ENVELOPE_INVALID")
    if (
        document.get("artifact_kind") != kind
        or document.get("schema_version") != 1
        or document.get("status") != status
        or _sha256(canonical_json_bytes(body, trailing_newline=False)) != body_hash
    ):
        raise PackError("BODY_HASH_MISMATCH")
    return body, body_hash


def _validated_root(pack_root: Path) -> Path:
    root = pack_root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise PackError("PACK_ROOT_INVALID")
    return root


def _validate_file_set(pack_root: Path, *, require_generated: bool) -> None:
    expected = ALL_ARTIFACTS if require_generated else frozenset(SOURCE_ARTIFACTS)
    try:
        paths = tuple(pack_root.iterdir())
    except OSError as exc:
        raise PackError("FILE_SET_MISMATCH") from exc
    names = frozenset(path.name for path in paths)
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise PackError("FILE_SET_MISMATCH")
    if not expected.issubset(names) or not names.issubset(ALL_ARTIFACTS):
        raise PackError("FILE_SET_MISMATCH")


def _verify_immutable_inputs(proposal: Path, gov_p0_manifest: Path) -> None:
    if _file_sha256(proposal, "PROPOSAL_HASH_MISMATCH") != CANONICAL_PROPOSAL_SHA256:
        raise PackError("PROPOSAL_HASH_MISMATCH")
    if (
        _file_sha256(gov_p0_manifest, "GOV_P0_HASH_MISMATCH")
        != CANONICAL_GOV_P0_MANIFEST_SHA256
    ):
        raise PackError("GOV_P0_HASH_MISMATCH")


def _verify_reviewed_sources(pack_root: Path) -> None:
    for name, expected_hash in REVIEWED_SOURCE_SHA256.items():
        if _file_sha256(pack_root / name, "REVIEWED_SOURCE_UNAVAILABLE") != expected_hash:
            raise PackError("REVIEWED_SOURCE_HASH_MISMATCH")


def _verify_live_sources(m1_source: Path, runner_source: Path) -> None:
    try:
        _verify_live_source_paths(m1_source, runner_source)
    except RehearsalError as exc:
        raise PackError(exc.code) from exc


def _validate_decision(pack_root: Path) -> None:
    body, _body_hash = _envelope(
        pack_root / DECISION_NAME,
        kind="GOV_P1_EXTERNAL_DECISION_TEMPLATE",
        status="DRAFT_BLOCKED",
    )
    if body != {
        "acl_status": "NOT_VERIFIED",
        "approved_responsible_contact": None,
        "approved_withdrawal_contact": None,
        "collection_authorized": False,
        "consent_version": None,
        "decision_date": None,
        "decision_issuer": None,
        "encryption_status": "NOT_VERIFIED",
        "institutional_approval_id": None,
        "institutional_approval_status": "NOT_ISSUED",
        "participant_information_version": None,
        "retention_decision": {
            "end_date": None,
            "mode": "UNDECIDED",
            "policy_reference": None,
        },
        "storage_root_approval": {"root_reference": None, "status": "NOT_APPROVED"},
    }:
        raise PackError("EXTERNAL_DECISION_INVALID")


def _validate_dossier(pack_root: Path) -> None:
    try:
        raw = (pack_root / DOSSIER_NAME).read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PackError("DOSSIER_INVALID") from exc
    required = (
        "Status: `DRAFT_FOR_INSTITUTIONAL_REVIEW`",
        CANONICAL_PROPOSAL_SHA256,
        CANONICAL_GOV_P0_MANIFEST_SHA256,
        "Production reconciler chưa được triển khai",
        "chưa phải hồ sơ đã nộp",
    )
    if not text.endswith("\n") or any(value not in text for value in required):
        raise PackError("DOSSIER_INVALID")


def _validate_receipt(
    pack_root: Path,
    *,
    m1_source: Path,
    runner_source: Path,
) -> None:
    body, _receipt_body_hash = _envelope(
        pack_root / RECEIPT_NAME,
        kind="ETHICS_DATA_RECEIPT",
        status=RECEIPT_STATUS,
    )
    try:
        _contract, contract_body_hash = load_contract(pack_root / CONTRACT_NAME)
    except RehearsalError as exc:
        raise PackError(exc.code) from exc
    exact = {
        "artifact_count": 4,
        "canonical_withdrawal_receipt_nonempty": True,
        "canonical_withdrawal_receipt_replayed": True,
        "collection_blocked_session_count": 2,
        "invalidated_artifact_count": 4,
        "late_artifact_registration_rejected": True,
        "late_write_intent_rejected": True,
        "out_of_manifest_sentinel_preserved": True,
        "owned_file_count_deleted": 4,
        "owned_file_count_remaining": 0,
        "participant_count": 1,
        "pending_withdrawal_task_count": 4,
        "recording_started": False,
        "session_count": 2,
        "terminal_session_count": 2,
        "withdrawal_request_count": 2,
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "blocking_gates": list(BLOCKING_GATES),
        "collection_authorized": False,
        "concurrent_same_account_mutation_resistant": False,
        "contract_body_sha256": contract_body_hash,
        "data_mode": "SYNTHETIC_ONLY",
        "device_gate_decision": "UNVERIFIED",
        "d1_go": False,
        "export_capability_status": "NOT_IMPLEMENTED_IN_M1_NOT_EXERCISED",
        "gov_p0_manifest_sha256": CANONICAL_GOV_P0_MANIFEST_SHA256,
        "human_review_required": True,
        "generated_output_atomic_replace": True,
        "m1_source_sha256": _file_sha256(m1_source, "LIVE_SOURCE_UNAVAILABLE"),
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
        "production_reconciler_implemented": False,
        "proposal_sha256": CANONICAL_PROPOSAL_SHA256,
        "real_participant_count": 0,
        "real_person_data_present": False,
        "research_ready": False,
        "reviewed_source_hashes_pinned": True,
        "runner_sha256": _file_sha256(runner_source, "LIVE_SOURCE_UNAVAILABLE"),
        "temporary_root_disposed": True,
        "path_identity_rechecked_before_unlink": True,
    }
    if body != exact:
        raise PackError("LIVE_BINDING_MISMATCH")


def _validate_sources(
    pack_root: Path,
    *,
    proposal: Path,
    gov_p0_manifest: Path,
    m1_source: Path,
    runner_source: Path,
    require_generated: bool,
) -> Path:
    root = _validated_root(pack_root)
    _validate_file_set(root, require_generated=require_generated)
    _verify_immutable_inputs(proposal, gov_p0_manifest)
    _verify_live_sources(m1_source, runner_source)
    _verify_reviewed_sources(root)
    try:
        load_contract(root / CONTRACT_NAME)
    except RehearsalError as exc:
        raise PackError(exc.code) from exc
    _validate_decision(root)
    _validate_dossier(root)
    _validate_receipt(root, m1_source=m1_source, runner_source=runner_source)
    return root


def _manifest_document(
    pack_root: Path,
    *,
    m1_source: Path,
    runner_source: Path,
) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    for name in SOURCE_ARTIFACTS:
        payload = (pack_root / name).read_bytes()
        artifacts.append({"path": name, "sha256": _sha256(payload), "size_bytes": len(payload)})
    return {
        "artifact_kind": "GOV_P1_PACK_MANIFEST",
        "artifacts": artifacts,
        "gov_p0_manifest_sha256": CANONICAL_GOV_P0_MANIFEST_SHA256,
        "m1_source_sha256": _file_sha256(m1_source, "LIVE_SOURCE_UNAVAILABLE"),
        "proposal_sha256": CANONICAL_PROPOSAL_SHA256,
        "runner_sha256": _file_sha256(runner_source, "LIVE_SOURCE_UNAVAILABLE"),
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
    return {"artifact_kind": "GOV_P1_PACK_VALIDATION", **_success_result(manifest_sha256)}


def write_pack(
    pack_root: Path = DEFAULT_PACK_ROOT,
    *,
    proposal: Path = DEFAULT_PROPOSAL,
    gov_p0_manifest: Path = DEFAULT_GOV_P0_MANIFEST,
    m1_source: Path = DEFAULT_M1_SOURCE,
    runner_source: Path = DEFAULT_RUNNER_SOURCE,
) -> dict[str, object]:
    """Validate sources and write only deterministic derived pack files."""

    root = _validate_sources(
        Path(pack_root),
        proposal=proposal,
        gov_p0_manifest=gov_p0_manifest,
        m1_source=m1_source,
        runner_source=runner_source,
        require_generated=False,
    )
    manifest_bytes = canonical_json_bytes(
        _manifest_document(root, m1_source=m1_source, runner_source=runner_source)
    )
    manifest_sha256 = _sha256(manifest_bytes)
    validation_bytes = canonical_json_bytes(_validation_document(manifest_sha256))
    try:
        write_generated_file(root, MANIFEST_NAME, manifest_bytes)
        write_generated_file(root, VALIDATION_NAME, validation_bytes)
    except RehearsalError as exc:
        raise PackError(exc.code) from exc
    return _success_result(manifest_sha256)


def check_pack(
    pack_root: Path = DEFAULT_PACK_ROOT,
    *,
    proposal: Path = DEFAULT_PROPOSAL,
    gov_p0_manifest: Path = DEFAULT_GOV_P0_MANIFEST,
    m1_source: Path = DEFAULT_M1_SOURCE,
    runner_source: Path = DEFAULT_RUNNER_SOURCE,
) -> dict[str, object]:
    """Read-only check of exact generated bytes and live semantic bindings."""

    root = _validated_root(Path(pack_root))
    _validate_file_set(root, require_generated=True)
    _verify_immutable_inputs(proposal, gov_p0_manifest)
    expected_manifest = canonical_json_bytes(
        _manifest_document(root, m1_source=m1_source, runner_source=runner_source)
    )
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
    _validate_sources(
        root,
        proposal=proposal,
        gov_p0_manifest=gov_p0_manifest,
        m1_source=m1_source,
        runner_source=runner_source,
        require_generated=True,
    )
    return _success_result(manifest_sha256)


def _failure_result(code: str) -> dict[str, object]:
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
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = write_pack() if arguments.write else check_pack()
    except PackError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(_failure_result(exc.code)))
        return 2
    except Exception:
        sys.stdout.buffer.write(canonical_json_bytes(_failure_result("UNEXPECTED_FAILURE")))
        return 2
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
