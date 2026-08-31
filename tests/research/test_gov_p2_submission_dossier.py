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

from build_gov_p2_submission_dossier import (  # noqa: E402
    ANNEX_SOURCES,
    GENERATED_NAMES,
    PackError,
    _verify_exact_input,
    canonical_json_bytes,
    check_pack,
    write_pack,
)

PACK_SOURCE = ROOT / "research" / "institutional_submission" / "v1"


def _copy_sources(tmp_path: Path) -> Path:
    target = tmp_path / "pack"
    shutil.copytree(PACK_SOURCE, target)
    for name in GENERATED_NAMES:
        (target / name).unlink(missing_ok=True)
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
    generated_first = {name: (pack / name).read_bytes() for name in GENERATED_NAMES}
    second = write_pack(pack)

    assert second == first
    assert {name: (pack / name).read_bytes() for name in GENERATED_NAMES} == generated_first
    assert check_pack(pack) == first
    assert first["result"] == "DOSSIER_VALIDATED"
    assert first["status"] == (
        "GOV_P2_SUBMISSION_DOSSIER_LOCALLY_VERIFIED_PENDING_EXTERNAL_REVIEW"
    )
    assert first["submission_state"] == "NOT_SUBMITTED"
    assert first["external_review_status"] == "PENDING"
    assert first["authority_ceiling"]["authority_status"] == "AUTHORITY_NOT_ISSUED"  # type: ignore[index]
    assert first["authority_ceiling"]["research_ready"] is False  # type: ignore[index]
    assert first["authority_ceiling"]["collection_authorized"] is False  # type: ignore[index]


def test_default_check_is_read_only_and_cli_output_is_bounded(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_gov_p2_submission_dossier.py"),
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
    assert json.loads(written.stdout)["result"] == "DOSSIER_VALIDATED"

    generated = {name: (pack / name).read_bytes() for name in GENERATED_NAMES}
    checked = subprocess.run([*command, "--check"], check=False, capture_output=True, text=True)
    assert checked.returncode == 0
    assert checked.stderr == ""
    assert {name: (pack / name).read_bytes() for name in GENERATED_NAMES} == generated


def test_upstream_inputs_require_exact_canonical_path_and_hash(tmp_path: Path) -> None:
    proposal = ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx"
    shadow = tmp_path / proposal.name
    shadow.write_bytes(proposal.read_bytes())

    with pytest.raises(PackError, match="UPSTREAM_PATH_MISMATCH"):
        _verify_exact_input(shadow, proposal, _sha(proposal))
    with pytest.raises(PackError, match="UPSTREAM_HASH_MISMATCH"):
        _verify_exact_input(proposal, proposal, "0" * 64)


def test_source_index_is_closed_and_matches_historical_inputs(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)

    def add_unreviewed_source(body: dict[str, object]) -> None:
        body["sources"].append(  # type: ignore[union-attr]
            {
                "limitation": "none",
                "path": "shadow.txt",
                "role": "SHADOW",
                "sha256": "0" * 64,
            }
        )

    _rewrite_body(pack / "source-index.v1.json", add_unreviewed_source)
    with pytest.raises(PackError, match="SOURCE_INDEX_INVALID"):
        write_pack(pack)


def test_decision_matrix_is_advisor_first_pending_only(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)

    def change_route(body: dict[str, object]) -> None:
        body["review_route"] = "SELF_APPROVED"

    _rewrite_body(pack / "decision-request-matrix.v1.json", change_route)
    with pytest.raises(PackError, match="DECISION_MATRIX_INVALID"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "status")

    def issue_decision(body: dict[str, object]) -> None:
        body["decisions"][0]["current_status"] = "APPROVED"  # type: ignore[index]

    _rewrite_body(pack / "decision-request-matrix.v1.json", issue_decision)
    with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
        write_pack(pack)


def test_forged_approval_and_authority_mutations_fail_closed(tmp_path: Path) -> None:
    mutations = (
        lambda body: body["decisions"][2].update(current_value="FAKE-APPROVAL"),
        lambda body: body.update(research_ready=True),
        lambda body: body.update(collection_authorized=True),
        lambda body: body.update(authority_status="ISSUED"),
    )
    for index, mutation in enumerate(mutations):
        pack = _copy_sources(tmp_path / str(index))
        _rewrite_body(pack / "decision-request-matrix.v1.json", mutation)
        with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
            write_pack(pack)

    pack = _copy_sources(tmp_path / "cover")
    cover = pack / "advisor-cover.vi.v1.md"
    cover.write_text(
        cover.read_text(encoding="utf-8") + "\ninstitutional_approval_id=FAKE-1\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
        write_pack(pack)


def test_markdown_contracts_require_pending_non_authorizing_language(tmp_path: Path) -> None:
    cases = (
        ("advisor-cover.vi.v1.md", "NOT_SUBMITTED", "SUBMITTED"),
        ("risk-safeguard-statement.vi.v1.md", "synthetic", "production"),
        (
            "retention-storage-withdrawal-decision.vi.v1.md",
            "PENDING_EXTERNAL_DECISION",
            "APPROVED",
        ),
    )
    for index, (name, old, new) in enumerate(cases):
        pack = _copy_sources(tmp_path / str(index))
        path = pack / name
        path.write_text(
            path.read_text(encoding="utf-8").replace(old, new),
            encoding="utf-8",
            newline="\n",
        )
        with pytest.raises(PackError, match="MARKDOWN_CONTRACT_INVALID"):
            write_pack(pack)


def test_generated_annexes_are_exact_canonical_snapshots(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)
    write_pack(pack)

    for annex_name, source_path in ANNEX_SOURCES.items():
        assert (pack / annex_name).read_bytes() == source_path.read_bytes()


def test_file_set_reparse_and_generated_tamper_fail_closed(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path / "extra")
    (pack / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "link")
    link = pack / "unexpected-link"
    try:
        os.symlink(pack / "advisor-cover.vi.v1.md", link)
    except OSError:
        link.mkdir()
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "annex")
    write_pack(pack)
    annex = pack / next(iter(ANNEX_SOURCES))
    annex.write_bytes(annex.read_bytes() + b"tamper")
    with pytest.raises(PackError, match="ANNEX_MISMATCH"):
        check_pack(pack)

    pack = _copy_sources(tmp_path / "manifest")
    write_pack(pack)
    manifest = pack / "gov-p2-submission.manifest.v1.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(PackError, match="MANIFEST_MISMATCH"):
        check_pack(pack)


def test_write_preserves_proposal_prior_packs_and_rp2(tmp_path: Path) -> None:
    protected = (
        ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        ROOT / "research" / "pre_collection" / "v1" / "pre-collection-pack.manifest.v1.json",
        ROOT / "research" / "pre_collection" / "gov_p1" / "v1" / "gov-p1-pack.manifest.v1.json",
        ROOT / "docs" / "spec" / "M2_D1_N2_STATIC_BINDING_CANDIDATE.json",
    )
    before = {path: _sha(path) for path in protected}

    write_pack(_copy_sources(tmp_path))

    assert {path: _sha(path) for path in protected} == before
    rp2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_m2_d1_n2_rp2.py"), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rp2.returncode == 0
    assert rp2.stderr == ""
