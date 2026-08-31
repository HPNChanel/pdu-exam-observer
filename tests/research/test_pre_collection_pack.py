from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_pre_collection_pack import (  # noqa: E402
    CANONICAL_PROPOSAL_SHA256,
    PackError,
    canonical_json_bytes,
    check_pack,
    write_pack,
)

PACK_SOURCE = ROOT / "research" / "pre_collection" / "v1"
PROPOSAL = ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx"


def _copy_pack(tmp_path: Path) -> Path:
    target = tmp_path / "pack"
    shutil.copytree(PACK_SOURCE, target)
    for generated in (
        "pre-collection-pack.manifest.v1.json",
        "pre-collection-pack.validation.v1.json",
    ):
        (target / generated).unlink(missing_ok=True)
    return target


def _rewrite_body(path: Path, mutate: object) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document["body"])  # type: ignore[operator]
    document["body_sha256"] = hashlib.sha256(
        canonical_json_bytes(document["body"], trailing_newline=False)
    ).hexdigest()
    path.write_bytes(canonical_json_bytes(document))


def test_write_and_check_are_deterministic_and_remain_not_ready(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)

    first = write_pack(pack, PROPOSAL)
    manifest_first = (pack / "pre-collection-pack.manifest.v1.json").read_bytes()
    receipt_first = (pack / "pre-collection-pack.validation.v1.json").read_bytes()
    second = write_pack(pack, PROPOSAL)

    assert first == second
    assert (pack / "pre-collection-pack.manifest.v1.json").read_bytes() == manifest_first
    assert (pack / "pre-collection-pack.validation.v1.json").read_bytes() == receipt_first
    assert check_pack(pack, PROPOSAL) == first
    assert first["result"] == "PACK_VALIDATED"
    assert first["structure_valid"] is True
    assert first["research_ready"] is False
    assert first["collection_authorized"] is False
    assert first["blocking_gates"]


def test_pack_rejects_wrong_proposal_hash(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    wrong = tmp_path / "proposal.docx"
    wrong.write_bytes(b"not the proposal")

    with pytest.raises(PackError, match="PROPOSAL_HASH_MISMATCH"):
        write_pack(pack, wrong)

    assert hashlib.sha256(PROPOSAL.read_bytes()).hexdigest() == CANONICAL_PROPOSAL_SHA256


def test_labelbook_has_six_supervised_classes_and_audit_only_uncertain(
    tmp_path: Path,
) -> None:
    pack = _copy_pack(tmp_path)
    labelbook = pack / "labelbook.draft.v1.json"

    def make_uncertain_trainable(body: dict[str, object]) -> None:
        body["audit_label"]["supervised"] = True  # type: ignore[index]

    _rewrite_body(labelbook, make_uncertain_trainable)
    with pytest.raises(PackError, match="LABEL_TAXONOMY_INVALID"):
        write_pack(pack, PROPOSAL)

    pack = _copy_pack(tmp_path / "second")

    def remove_class(body: dict[str, object]) -> None:
        body["supervised_classes"] = body["supervised_classes"][:-1]  # type: ignore[index]

    _rewrite_body(pack / "labelbook.draft.v1.json", remove_class)
    with pytest.raises(PackError, match="LABEL_TAXONOMY_INVALID"):
        write_pack(pack, PROPOSAL)


def test_segment_contract_rejects_wrong_duration_counts_and_test_selection(
    tmp_path: Path,
) -> None:
    mutations = (
        ("SEGMENT_WINDOW_INVALID", lambda body: body["window"].update(duration_ms=5000)),
        ("SEGMENT_COUNTS_INVALID", lambda body: body["counts"].update(combined_min=500)),
        (
            "METHOD_SELECTION_LEAKAGE",
            lambda body: body["matching"].update(test_data_used_for_selection=True),
        ),
    )
    for index, (failure, mutation) in enumerate(mutations):
        pack = _copy_pack(tmp_path / str(index))
        _rewrite_body(pack / "segment-policy.draft.v1.json", mutation)
        with pytest.raises(PackError, match=failure):
            write_pack(pack, PROPOSAL)


def test_external_gates_cannot_claim_readiness_or_collection_authority(
    tmp_path: Path,
) -> None:
    pack = _copy_pack(tmp_path)

    def claim_ready(body: dict[str, object]) -> None:
        body["research_ready"] = True
        body["collection_authorized"] = True

    _rewrite_body(pack / "external-gates.template.v1.json", claim_ready)
    with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
        write_pack(pack, PROPOSAL)


def test_issued_consent_with_template_tokens_is_rejected(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    consent = pack / "consent-form.vi.draft.v1.md"
    consent.write_text(
        consent.read_text(encoding="utf-8").replace(
            "DRAFT_FOR_INSTITUTIONAL_REVIEW", "ISSUED"
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(PackError, match="UNRESOLVED_ISSUED_TEMPLATE"):
        write_pack(pack, PROPOSAL)


def test_manifest_rejects_tamper_extra_file_and_noncanonical_json(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    write_pack(pack, PROPOSAL)
    (pack / "reporting-template.v1.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(PackError, match="MANIFEST_MISMATCH"):
        check_pack(pack, PROPOSAL)

    pack = _copy_pack(tmp_path / "extra")
    (pack / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack, PROPOSAL)

    pack = _copy_pack(tmp_path / "json")
    source = pack / "source-register.v1.json"
    source.write_text(source.read_text(encoding="utf-8").replace("{", "{\n", 1), encoding="utf-8")
    with pytest.raises(PackError, match="NONCANONICAL_JSON"):
        write_pack(pack, PROPOSAL)


def test_duplicate_json_key_and_body_hash_mismatch_fail_closed(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    target = pack / "external-gates.template.v1.json"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            '"schema_version":1', '"schema_version":1,"schema_version":1'
        ),
        encoding="utf-8",
    )
    with pytest.raises(PackError, match="DUPLICATE_JSON_KEY"):
        write_pack(pack, PROPOSAL)

    pack = _copy_pack(tmp_path / "hash")
    target = pack / "labelbook.draft.v1.json"
    document = json.loads(target.read_text(encoding="utf-8"))
    document["body_sha256"] = "0" * 64
    target.write_bytes(canonical_json_bytes(document))
    with pytest.raises(PackError, match="BODY_HASH_MISMATCH"):
        write_pack(pack, PROPOSAL)


def test_custodian_checklist_remains_non_authorizing(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    checklist = pack / "borrowed-custodian-request.vi.v1.md"
    checklist.write_text(
        checklist.read_text(encoding="utf-8").replace(
            "NO_EXECUTION_AUTHORITY", "EXECUTION_AUTHORIZED"
        ),
        encoding="utf-8",
    )
    with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
        write_pack(pack, PROPOSAL)


def test_cli_emits_one_bounded_json_object(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_pre_collection_pack.py"),
        "--write",
        "--pack-root",
        str(pack),
        "--proposal",
        str(PROPOSAL),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.count("\n") == 1
    assert json.loads(completed.stdout)["result"] == "PACK_VALIDATED"

    (pack / "labelbook.draft.v1.json").write_text("{}\n", encoding="utf-8")
    completed = subprocess.run(
        [*command[:2], "--check", *command[3:]],
        check=False,
        capture_output=True,
        text=True,
    )
    rejected = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert completed.stderr == ""
    assert rejected["result"] == "PACK_REJECTED"
    assert rejected["failure_code"] in {
        "ENVELOPE_INVALID",
        "MANIFEST_MISMATCH",
        "NONCANONICAL_JSON",
    }
