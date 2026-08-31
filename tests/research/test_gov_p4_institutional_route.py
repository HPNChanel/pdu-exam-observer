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

from build_gov_p4_institutional_route_pack import (  # noqa: E402
    GENERATED_NAMES,
    REVIEWED_NAMES,
    UPSTREAMS,
    PackError,
    canonical_json_bytes,
    check_pack,
    write_pack,
)

PACK_SOURCE = (
    ROOT / "research" / "institutional_submission" / "route_discovery" / "v1"
)


def _copy_sources(tmp_path: Path) -> Path:
    target = tmp_path / "pack"
    target.mkdir(parents=True)
    for name in REVIEWED_NAMES:
        shutil.copy2(PACK_SOURCE / name, target / name)
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


def test_write_and_check_are_deterministic_and_non_authorizing(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)

    first = write_pack(pack)
    generated = {name: (pack / name).read_bytes() for name in GENERATED_NAMES}
    second = write_pack(pack)

    assert first == second == check_pack(pack)
    assert {name: (pack / name).read_bytes() for name in GENERATED_NAMES} == generated
    assert first["result"] == "ROUTE_PACK_VALIDATED"
    assert first["status"] == (
        "GOV_P4_INSTITUTIONAL_ROUTE_SOURCE_VERIFIED_HUMAN_SUBJECTS_REVIEW_"
        "UNCONFIRMED_APPROVAL_NOT_ISSUED"
    )
    assert first["adv_02_status"] == "SATISFIED_BY_PUBLIC_PRIMARY_SOURCES"
    assert first["institutional_approval_status"] == "NOT_ISSUED"
    assert first["submission_state"] == "NOT_SUBMITTED"
    assert first["authority_ceiling"]["collection_authorized"] is False  # type: ignore[index]


def test_default_check_is_read_only_and_cli_output_is_bounded(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_gov_p4_institutional_route_pack.py"),
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
    assert json.loads(written.stdout)["result"] == "ROUTE_PACK_VALIDATED"

    generated = {name: (pack / name).read_bytes() for name in GENERATED_NAMES}
    checked = subprocess.run([*command, "--check"], check=False, capture_output=True, text=True)
    assert checked.returncode == 0
    assert checked.stderr == ""
    assert {name: (pack / name).read_bytes() for name in GENERATED_NAMES} == generated


def test_source_register_pins_current_official_primary_sources(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)
    write_pack(pack)
    document = json.loads(
        (pack / "official-source-register.v1.json").read_text(encoding="utf-8")
    )
    sources = {item["source_id"]: item for item in document["body"]["sources"]}

    assert sources["PDU-REG-2022"]["content_sha256"] == (
        "4deef2d10974d5bbb3b0f4032bfcd0c3c60e867601de439bf63dd3c0be1605eb"
    )
    assert sources["PDU-NOTICE-2026-2027"]["content_sha256"] == (
        "e8daa3697b6b65f69cf47404c0be0d072382717964b1d3e31b36efc5654747ab"
    )
    assert sources["PDU-FORMS-2026"]["content_sha256"] == (
        "d922de642841d7dd6160e33bf69c15098eaa8bd14f46f5c74f7cf2688ddea931"
    )
    assert all(source["publisher"] == "TRUONG_DAI_HOC_PHAM_VAN_DONG" for source in sources.values())
    assert all("pdu.edu.vn" in source["landing_page_url"] for source in sources.values())


def test_route_resolution_matches_public_regulation_and_current_notice(
    tmp_path: Path,
) -> None:
    pack = _copy_sources(tmp_path)
    write_pack(pack)
    route = json.loads(
        (pack / "route-resolution.v1.json").read_text(encoding="utf-8")
    )["body"]

    assert route["institution"] == "TRUONG_DAI_HOC_PHAM_VAN_DONG"
    assert route["faculty"] == "KHOA_CONG_NGHE_THONG_TIN"
    assert route["adv_02_status"] == "SATISFIED_BY_PUBLIC_PRIMARY_SOURCES"
    assert route["proposal_review_body"] == "HOI_DONG_KHOA"
    assert route["administrative_unit"] == "PHONG_QUAN_LY_KHOA_HOC"
    assert route["approval_issuer_role"] == "HIEU_TRUONG"
    assert route["required_templates"] == ["MAU_1", "MAU_2", "MAU_3", "MAU_4", "MAU_5", "MAU_6"]
    assert route["route_steps"][-1] == "STUDENT_BEGINS_ONLY_AFTER_APPROVAL_DECISION"


def test_human_subjects_and_current_cycle_gaps_remain_explicit(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)
    write_pack(pack)
    route = json.loads(
        (pack / "route-resolution.v1.json").read_text(encoding="utf-8")
    )["body"]

    assert route["human_subjects_review_requirement"] == "UNKNOWN_PENDING_CONFIRMATION"
    assert route["consent_form_institutional_status"] == "PENDING_EXTERNAL_DECISION"
    assert route["retention_storage_withdrawal_status"] == "PENDING_EXTERNAL_DECISION"
    assert route["current_cycle_deadline_status"] == (
        "DEADLINE_PASSED_REQUIRES_HUMAN_CONFIRMATION"
    )
    assert route["institutional_approval_status"] == "NOT_ISSUED"
    assert route["approval_id"] is None
    assert route["decision_date"] is None


def test_forged_approval_ethics_clearance_and_authority_are_rejected(
    tmp_path: Path,
) -> None:
    mutations = (
        lambda body: body.update(institutional_approval_status="ISSUED"),
        lambda body: body.update(approval_id="FAKE-APPROVAL"),
        lambda body: body.update(decision_date="2026-08-31"),
        lambda body: body.update(human_subjects_review_requirement="NOT_REQUIRED"),
        lambda body: body.update(consent_form_institutional_status="APPROVED"),
        lambda body: body.update(research_ready=True),
        lambda body: body.update(collection_authorized=True),
        lambda body: body.update(participant_collection_authorized=True),
    )
    for index, mutation in enumerate(mutations):
        pack = _copy_sources(tmp_path / str(index))
        _rewrite_body(pack / "route-resolution.v1.json", mutation)
        with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
            write_pack(pack)


def test_closed_file_set_source_tamper_reparse_and_generated_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    pack = _copy_sources(tmp_path / "source")
    _rewrite_body(
        pack / "official-source-register.v1.json",
        lambda body: body["sources"][0].update(landing_page_url="https://example.com"),
    )
    with pytest.raises(PackError, match="SOURCE_REGISTER_INVALID"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "extra")
    (pack / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "link")
    link = pack / "unexpected-link"
    try:
        os.symlink(pack / "route-resolution.v1.json", link)
    except OSError:
        link.mkdir()
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "manifest")
    write_pack(pack)
    manifest = pack / "gov-p4-institutional-route.manifest.v1.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(PackError, match="MANIFEST_MISMATCH"):
        check_pack(pack)


def test_proposal_gov_p2_gov_p3_rp2_and_package_inputs_remain_immutable(
    tmp_path: Path,
) -> None:
    protected = tuple(binding.path for binding in UPSTREAMS.values()) + (
        ROOT / "docs" / "spec" / "M2_D1_N2_STATIC_BINDING_CANDIDATE.json",
        ROOT / "packaging" / "RELEASE_MANIFEST.json",
    )
    before = {path: _sha(path) for path in protected}

    write_pack(_copy_sources(tmp_path))

    assert {path: _sha(path) for path in protected} == before

