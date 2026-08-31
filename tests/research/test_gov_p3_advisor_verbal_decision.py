from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_gov_p3_advisor_decision_receipt import (  # noqa: E402
    GENERATED_NAMES,
    UPSTREAMS,
    PackError,
    canonical_json_bytes,
    check_pack,
    write_pack,
)

PACK_SOURCE = (
    ROOT / "research" / "institutional_submission" / "advisor_decision" / "v1"
)
SOURCE_NAME = "advisor-verbal-confirmation.record.v1.json"


def _copy_source(tmp_path: Path) -> Path:
    target = tmp_path / "pack"
    target.mkdir(parents=True)
    shutil.copy2(PACK_SOURCE / SOURCE_NAME, target / SOURCE_NAME)
    return target


def _rewrite_body(path: Path, mutate: object) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document["body"])  # type: ignore[operator]
    document["body_sha256"] = hashlib.sha256(
        canonical_json_bytes(document["body"], trailing_newline=False)
    ).hexdigest()
    path.write_bytes(canonical_json_bytes(document))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_write_and_check_are_deterministic_and_keep_authority_closed(
    tmp_path: Path,
) -> None:
    pack = _copy_source(tmp_path)

    first = write_pack(pack)
    generated = {name: (pack / name).read_bytes() for name in GENERATED_NAMES}
    second = write_pack(pack)

    assert first == second == check_pack(pack)
    assert {name: (pack / name).read_bytes() for name in GENERATED_NAMES} == generated
    assert first["result"] == "ADVISOR_DECISION_RECEIPT_VALIDATED"
    assert first["status"] == (
        "GOV_P3_ADVISOR_VERBAL_DECISION_RECORDED_USER_STATED_UNVERIFIED_"
        "READY_FOR_INSTITUTIONAL_ROUTING"
    )
    assert first["advisor_review_status"] == "SATISFIED_BY_USER_REPORT_UNVERIFIED"
    assert first["institutional_route_status"] == "PENDING_EXTERNAL_DECISION"
    assert first["institutional_approval_status"] == "NOT_ISSUED"
    assert first["authority_ceiling"]["authority_status"] == "AUTHORITY_NOT_ISSUED"  # type: ignore[index]
    assert first["authority_ceiling"]["collection_authorized"] is False  # type: ignore[index]


def test_default_check_is_read_only_and_cli_output_is_bounded(tmp_path: Path) -> None:
    pack = _copy_source(tmp_path)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_gov_p3_advisor_decision_receipt.py"),
        "--pack-root",
        str(pack),
    ]
    before = {path.name: path.read_bytes() for path in pack.iterdir()}

    missing = subprocess.run(command, check=False, capture_output=True, text=True)
    assert missing.returncode == 2
    assert missing.stderr == ""
    assert missing.stdout.count("\n") == 1
    assert json.loads(missing.stdout)["failure_code"] == "FILE_SET_MISMATCH"
    assert {path.name: path.read_bytes() for path in pack.iterdir()} == before

    written = subprocess.run([*command, "--write"], check=False, capture_output=True, text=True)
    assert written.returncode == 0
    assert written.stderr == ""
    assert written.stdout.count("\n") == 1
    assert json.loads(written.stdout)["result"] == "ADVISOR_DECISION_RECEIPT_VALIDATED"

    generated = {name: (pack / name).read_bytes() for name in GENERATED_NAMES}
    checked = subprocess.run([*command, "--check"], check=False, capture_output=True, text=True)
    assert checked.returncode == 0
    assert checked.stderr == ""
    assert {name: (pack / name).read_bytes() for name in GENERATED_NAMES} == generated


def test_record_closes_only_adv_01_from_a_verbal_user_report(tmp_path: Path) -> None:
    pack = _copy_source(tmp_path)
    write_pack(pack)
    record = json.loads((pack / SOURCE_NAME).read_text(encoding="utf-8"))["body"]

    assert record["decision_id"] == "ADV-01"
    assert record["advisor_outcome"] == "READY_FOR_INSTITUTIONAL_ROUTING"
    assert record["evidence_mode"] == "VERBAL_CONFIRMATION_REPORTED_BY_USER"
    assert record["evidence_classification"] == "USER_STATED_UNVERIFIED"
    assert record["advisor_review_gate_status"] == "SATISFIED_BY_USER_REPORT_UNVERIFIED"
    assert record["advisor_decision_date"] is None
    assert record["written_evidence_available"] is False
    assert record["advisor_identity_stored"] is False
    assert record["adv_02_status"] == "PENDING_EXTERNAL_DECISION"
    assert record["institutional_route_confirmed"] is False


def test_forged_verification_identity_and_date_are_rejected(tmp_path: Path) -> None:
    mutations = (
        lambda body: body.update(evidence_classification="SOURCE_VERIFIED"),
        lambda body: body.update(written_evidence_available=True),
        lambda body: body.update(advisor_decision_date="2026-08-31"),
        lambda body: body.update(advisor_identity_stored=True),
        lambda body: body.update(evidence_reference="email-message-id"),
    )
    for index, mutation in enumerate(mutations):
        pack = _copy_source(tmp_path / str(index))
        _rewrite_body(pack / SOURCE_NAME, mutation)
        with pytest.raises(PackError, match="ADVISOR_RECORD_INVALID"):
            write_pack(pack)


def test_institutional_approval_and_authority_escalation_are_rejected(
    tmp_path: Path,
) -> None:
    mutations = (
        lambda body: body.update(adv_02_status="COMPLETED"),
        lambda body: body.update(institutional_route_confirmed=True),
        lambda body: body.update(institutional_approval_status="ISSUED"),
        lambda body: body.update(institutional_approval_id="FAKE-1"),
        lambda body: body.update(research_ready=True),
        lambda body: body.update(collection_authorized=True),
        lambda body: body.update(participant_collection_authorized=True),
        lambda body: body.update(authority_effect="ISSUES_COLLECTION_AUTHORITY"),
    )
    for index, mutation in enumerate(mutations):
        pack = _copy_source(tmp_path / str(index))
        _rewrite_body(pack / SOURCE_NAME, mutation)
        with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
            write_pack(pack)


def test_manifest_pins_exact_gov_p2_inputs_and_does_not_rewrite_them(
    tmp_path: Path,
) -> None:
    before = {name: _sha(binding.path) for name, binding in UPSTREAMS.items()}
    pack = _copy_source(tmp_path)
    write_pack(pack)
    manifest = json.loads(
        (pack / "gov-p3-advisor-decision.manifest.v1.json").read_text(encoding="utf-8")
    )

    assert manifest["upstream_bindings"] == {
        name: {"path": binding.relative_path, "sha256": binding.sha256}
        for name, binding in sorted(UPSTREAMS.items())
    }
    assert {name: _sha(binding.path) for name, binding in UPSTREAMS.items()} == before


def test_closed_file_set_reparse_and_generated_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    pack = _copy_source(tmp_path / "extra")
    (pack / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_source(tmp_path / "link")
    link = pack / "unexpected-link"
    try:
        os.symlink(pack / SOURCE_NAME, link)
    except OSError:
        link.mkdir()
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_source(tmp_path / "manifest")
    write_pack(pack)
    manifest = pack / "gov-p3-advisor-decision.manifest.v1.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(PackError, match="MANIFEST_MISMATCH"):
        check_pack(pack)

    pack = _copy_source(tmp_path / "validation")
    write_pack(pack)
    validation = pack / "gov-p3-advisor-decision.validation.v1.json"
    validation.write_bytes(validation.read_bytes() + b" ")
    with pytest.raises(PackError, match="VALIDATION_MISMATCH"):
        check_pack(pack)


def test_proposal_prior_governance_packs_and_rp2_remain_immutable(
    tmp_path: Path,
) -> None:
    protected = (
        ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        ROOT / "research" / "pre_collection" / "v1" / "pre-collection-pack.manifest.v1.json",
        ROOT / "research" / "pre_collection" / "gov_p1" / "v1" / "gov-p1-pack.manifest.v1.json",
        ROOT
        / "research"
        / "institutional_submission"
        / "v1"
        / "gov-p2-submission.manifest.v1.json",
        ROOT / "docs" / "spec" / "M2_D1_N2_STATIC_BINDING_CANDIDATE.json",
    )
    before = {path: _sha(path) for path in protected}

    write_pack(_copy_source(tmp_path))

    assert {path: _sha(path) for path in protected} == before
