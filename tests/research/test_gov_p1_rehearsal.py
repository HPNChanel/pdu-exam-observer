from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_gov_p1_pack as pack_module  # noqa: E402
import run_gov_p1_rehearsal as rehearsal_module  # noqa: E402
from build_gov_p1_pack import PackError, check_pack, write_pack  # noqa: E402
from run_gov_p1_rehearsal import (  # noqa: E402
    RehearsalError,
    canonical_json_bytes,
    delete_owned_files,
    parse_owned_relative_path,
    run_rehearsal,
    write_generated_file,
    write_receipt,
)

PACK_SOURCE = ROOT / "research" / "pre_collection" / "gov_p1" / "v1"
PROPOSAL = ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx"
GOV_P0_MANIFEST = (
    ROOT / "research" / "pre_collection" / "v1" / "pre-collection-pack.manifest.v1.json"
)
M1_SOURCE = ROOT / "src" / "pdu_exam_observer" / "m1.py"
RUNNER_SOURCE = ROOT / "scripts" / "run_gov_p1_rehearsal.py"


def _copy_pack(tmp_path: Path) -> Path:
    target = tmp_path / "pack"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PACK_SOURCE, target)
    for generated in (
        "synthetic-ethics-data-receipt.v1.json",
        "gov-p1-pack.manifest.v1.json",
        "gov-p1-pack.validation.v1.json",
    ):
        (target / generated).unlink(missing_ok=True)
    return target


def _write_receipt(pack: Path, temp_parent: Path) -> dict[str, object]:
    return write_receipt(
        pack,
        contract_path=pack / "rehearsal-contract.v1.json",
        proposal=PROPOSAL,
        gov_p0_manifest=GOV_P0_MANIFEST,
        m1_source=M1_SOURCE,
        runner_source=RUNNER_SOURCE,
        temp_parent=temp_parent,
    )


def _write_pack(pack: Path) -> dict[str, object]:
    return write_pack(
        pack,
        proposal=PROPOSAL,
        gov_p0_manifest=GOV_P0_MANIFEST,
        m1_source=M1_SOURCE,
        runner_source=RUNNER_SOURCE,
    )


def _check_pack(pack: Path) -> dict[str, object]:
    return check_pack(
        pack,
        proposal=PROPOSAL,
        gov_p0_manifest=GOV_P0_MANIFEST,
        m1_source=M1_SOURCE,
        runner_source=RUNNER_SOURCE,
    )


def test_rehearsal_is_deterministic_synthetic_and_fail_closed(tmp_path: Path) -> None:
    first = run_rehearsal(
        contract_path=PACK_SOURCE / "rehearsal-contract.v1.json",
        proposal=PROPOSAL,
        gov_p0_manifest=GOV_P0_MANIFEST,
        m1_source=M1_SOURCE,
        runner_source=RUNNER_SOURCE,
        temp_parent=tmp_path,
    )
    second = run_rehearsal(
        contract_path=PACK_SOURCE / "rehearsal-contract.v1.json",
        proposal=PROPOSAL,
        gov_p0_manifest=GOV_P0_MANIFEST,
        m1_source=M1_SOURCE,
        runner_source=RUNNER_SOURCE,
        temp_parent=tmp_path,
    )

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["status"] == (
        "GOV_P1_SYNTHETIC_REHEARSAL_VERIFIED_"
        "PRODUCTION_RECONCILER_UNIMPLEMENTED"
    )
    body = first["body"]
    assert isinstance(body, dict)
    assert body["data_mode"] == "SYNTHETIC_ONLY"
    assert body["real_participant_count"] == 0
    assert body["session_count"] == 2
    assert body["artifact_count"] == 4
    assert body["pending_withdrawal_task_count"] == 4
    assert body["canonical_withdrawal_receipt_replayed"] is True
    assert body["owned_file_count_deleted"] == 4
    assert body["owned_file_count_remaining"] == 0
    assert body["out_of_manifest_sentinel_preserved"] is True
    assert body["temporary_root_disposed"] is True
    assert body["production_reconciler_implemented"] is False
    assert body["collection_authorized"] is False
    assert body["research_ready"] is False
    serialized = canonical_json_bytes(first).decode("utf-8")
    assert "participant-" not in serialized
    assert "research-" not in serialized
    assert str(tmp_path) not in serialized


@pytest.mark.parametrize(
    "value",
    (
        "",
        ".",
        "../escape",
        "artifacts/../escape",
        "/absolute/path",
        "C:/absolute/path",
        "C:\\absolute\\path",
        "artifacts\\session-a\\raw-a.bin",
        "//server/share/file",
    ),
)
def test_owned_path_parser_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(RehearsalError, match="OWNED_PATH_INVALID"):
        parse_owned_relative_path(value)


def test_delete_owned_files_rejects_tamper_and_reparse_probe(tmp_path: Path) -> None:
    root = tmp_path / "root"
    target = root / "artifacts" / "fixture.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"tampered")
    fixtures = [
        {
            "relative_path": "artifacts/fixture.bin",
            "payload_sha256": "0" * 64,
            "payload_utf8": "expected",
        }
    ]
    with pytest.raises(RehearsalError, match="FIXTURE_HASH_MISMATCH"):
        delete_owned_files(root, fixtures)
    assert target.read_bytes() == b"tampered"

    fixtures[0]["payload_sha256"] = (
        "d121be3103007b41edf96f8262925f8c7d61894afe9a041843b631f69445bc57"
    )
    with pytest.raises(RehearsalError, match="LINK_OR_REPARSE_DETECTED"):
        delete_owned_files(root, fixtures, reparse_probe=lambda _path: True)
    assert target.exists()


def test_delete_rejects_original_root_reparse_before_resolution(tmp_path: Path) -> None:
    root = tmp_path / "root"
    target = root / "artifacts" / "fixture.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"expected")
    seen: list[Path] = []

    def probe(path: Path) -> bool:
        seen.append(path)
        return path == root

    fixtures = [
        {
            "relative_path": "artifacts/fixture.bin",
            "payload_sha256": "cea23dd4b87e8b00d19fb9ccaaef93e97353c7353e2070f3baf05aeb3995dff4",
            "payload_utf8": "expected",
        }
    ]
    with pytest.raises(RehearsalError, match="LINK_OR_REPARSE_DETECTED"):
        delete_owned_files(root, fixtures, reparse_probe=probe)
    assert seen[0] == root
    assert target.exists()


def test_delete_rechecks_identity_immediately_before_unlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    target = root / "artifacts" / "fixture.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"expected")

    def replace_checked_target(path: Path) -> None:
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(b"expected")
        replacement.replace(path)

    fixtures = [
        {
            "relative_path": "artifacts/fixture.bin",
            "payload_sha256": "cea23dd4b87e8b00d19fb9ccaaef93e97353c7353e2070f3baf05aeb3995dff4",
            "payload_utf8": "expected",
        }
    ]
    with pytest.raises(RehearsalError, match="OWNED_IDENTITY_CHANGED"):
        delete_owned_files(root, fixtures, before_unlink=replace_checked_target)
    assert target.read_bytes() == b"expected"


def test_generated_output_rejects_reparse_leaf(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    leaf = root / "receipt.json"
    leaf.write_bytes(b"do-not-overwrite")

    with pytest.raises(RehearsalError, match="LINK_OR_REPARSE_DETECTED"):
        write_generated_file(
            root,
            "receipt.json",
            b"replacement",
            reparse_probe=lambda path: path == leaf,
        )
    assert leaf.read_bytes() == b"do-not-overwrite"


def test_receipt_write_is_exact_and_check_rejects_drift(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    first = _write_receipt(pack, tmp_path)
    first_bytes = (pack / "synthetic-ethics-data-receipt.v1.json").read_bytes()
    second = _write_receipt(pack, tmp_path)
    assert first == second
    assert (pack / "synthetic-ethics-data-receipt.v1.json").read_bytes() == first_bytes

    receipt = json.loads(first_bytes)
    receipt["body"]["collection_authorized"] = True
    receipt["body_sha256"] = "0" * 64
    (pack / "synthetic-ethics-data-receipt.v1.json").write_bytes(
        canonical_json_bytes(receipt)
    )
    with pytest.raises(RehearsalError, match="RECEIPT_MISMATCH"):
        run_rehearsal(
            contract_path=pack / "rehearsal-contract.v1.json",
            proposal=PROPOSAL,
            gov_p0_manifest=GOV_P0_MANIFEST,
            m1_source=M1_SOURCE,
            runner_source=RUNNER_SOURCE,
            temp_parent=tmp_path,
            expected_receipt=pack / "synthetic-ethics-data-receipt.v1.json",
        )


def test_pack_write_check_is_deterministic_and_non_authorizing(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    _write_receipt(pack, tmp_path)
    first = _write_pack(pack)
    manifest = (pack / "gov-p1-pack.manifest.v1.json").read_bytes()
    validation = (pack / "gov-p1-pack.validation.v1.json").read_bytes()
    second = _write_pack(pack)

    assert first == second == _check_pack(pack)
    assert (pack / "gov-p1-pack.manifest.v1.json").read_bytes() == manifest
    assert (pack / "gov-p1-pack.validation.v1.json").read_bytes() == validation
    assert first["research_ready"] is False
    assert first["collection_authorized"] is False
    assert "PRODUCTION_RECONCILER_UNIMPLEMENTED" in first["blocking_gates"]


def test_pack_rejects_tamper_extra_noncanonical_and_false_decision(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    _write_receipt(pack, tmp_path)
    _write_pack(pack)
    dossier = pack / "submission-dossier.vi.draft.v1.md"
    dossier.write_text("tampered", encoding="utf-8")
    with pytest.raises(PackError, match="MANIFEST_MISMATCH"):
        _check_pack(pack)

    pack = _copy_pack(tmp_path / "extra")
    _write_receipt(pack, tmp_path)
    (pack / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        _write_pack(pack)

    pack = _copy_pack(tmp_path / "noncanonical")
    contract = pack / "rehearsal-contract.v1.json"
    contract.write_text(contract.read_text(encoding="utf-8").replace("{", "{\n", 1))
    with pytest.raises(RehearsalError, match="REVIEWED_SOURCE_HASH_MISMATCH"):
        _write_receipt(pack, tmp_path)

    pack = _copy_pack(tmp_path / "decision")
    decision = pack / "external-decision-record.template.v1.json"
    document = json.loads(decision.read_text(encoding="utf-8"))
    document["body"]["collection_authorized"] = True
    document["body_sha256"] = "0" * 64
    decision.write_bytes(canonical_json_bytes(document))
    _write_receipt(pack, tmp_path)
    with pytest.raises(PackError, match="REVIEWED_SOURCE_HASH_MISMATCH"):
        _write_pack(pack)


def test_reviewed_sources_remain_pinned_after_self_consistent_mutation(
    tmp_path: Path,
) -> None:
    pack = _copy_pack(tmp_path)
    contract = pack / "rehearsal-contract.v1.json"
    document = json.loads(contract.read_bytes())
    document["body"]["fixtures"][0]["relative_path"] = "artifacts/session-a/renamed.bin"
    document["body_sha256"] = rehearsal_module._sha256(
        canonical_json_bytes(document["body"], trailing_newline=False)
    )
    contract.write_bytes(canonical_json_bytes(document))
    with pytest.raises(RehearsalError, match="REVIEWED_SOURCE_HASH_MISMATCH"):
        _write_receipt(pack, tmp_path)

    pack = _copy_pack(tmp_path / "decision")
    decision = pack / "external-decision-record.template.v1.json"
    decision_document = json.loads(decision.read_bytes())
    decision_document["body"]["decision_issuer"] = "unreviewed-but-self-consistent"
    decision_document["body_sha256"] = rehearsal_module._sha256(
        canonical_json_bytes(decision_document["body"], trailing_newline=False)
    )
    decision.write_bytes(canonical_json_bytes(decision_document))
    _write_receipt(pack, tmp_path)
    with pytest.raises(PackError, match="REVIEWED_SOURCE_HASH_MISMATCH"):
        _write_pack(pack)

    pack = _copy_pack(tmp_path / "dossier")
    dossier = pack / "submission-dossier.vi.draft.v1.md"
    dossier.write_text(
        dossier.read_text(encoding="utf-8") + "\nUnreviewed narrative.\n",
        encoding="utf-8",
    )
    _write_receipt(pack, tmp_path)
    with pytest.raises(PackError, match="REVIEWED_SOURCE_HASH_MISMATCH"):
        _write_pack(pack)


def test_pack_rejects_proposal_gov_p0_and_live_source_drift(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    proposal = tmp_path / "proposal.docx"
    proposal.write_bytes(b"not canonical")
    with pytest.raises(RehearsalError, match="PROPOSAL_HASH_MISMATCH"):
        write_receipt(
            pack,
            contract_path=pack / "rehearsal-contract.v1.json",
            proposal=proposal,
            gov_p0_manifest=GOV_P0_MANIFEST,
            m1_source=M1_SOURCE,
            runner_source=RUNNER_SOURCE,
            temp_parent=tmp_path,
        )

    gov_p0 = tmp_path / "gov-p0.json"
    gov_p0.write_bytes(b"{}\n")
    with pytest.raises(RehearsalError, match="GOV_P0_HASH_MISMATCH"):
        write_receipt(
            pack,
            contract_path=pack / "rehearsal-contract.v1.json",
            proposal=PROPOSAL,
            gov_p0_manifest=gov_p0,
            m1_source=M1_SOURCE,
            runner_source=RUNNER_SOURCE,
            temp_parent=tmp_path,
        )

    changed_m1 = tmp_path / "m1.py"
    changed_m1.write_bytes(M1_SOURCE.read_bytes() + b"\n")
    _write_receipt(pack, tmp_path)
    with pytest.raises(PackError, match="LIVE_SOURCE_PATH_MISMATCH"):
        write_pack(
            pack,
            proposal=PROPOSAL,
            gov_p0_manifest=GOV_P0_MANIFEST,
            m1_source=changed_m1,
            runner_source=RUNNER_SOURCE,
        )

    identical_m1 = tmp_path / "identical-m1.py"
    identical_m1.write_bytes(M1_SOURCE.read_bytes())
    with pytest.raises(RehearsalError, match="LIVE_SOURCE_PATH_MISMATCH"):
        write_receipt(
            pack,
            contract_path=pack / "rehearsal-contract.v1.json",
            proposal=PROPOSAL,
            gov_p0_manifest=GOV_P0_MANIFEST,
            m1_source=identical_m1,
            runner_source=RUNNER_SOURCE,
            temp_parent=tmp_path,
        )


def test_runner_cli_rejection_is_one_sanitized_json_line(tmp_path: Path) -> None:
    proposal = tmp_path / "bad.docx"
    proposal.write_bytes(b"bad")
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER_SOURCE),
            "--check",
            "--proposal",
            str(proposal),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert len(result.stdout.splitlines()) == 1
    payload = json.loads(result.stdout)
    assert payload["result"] == "REHEARSAL_REJECTED"
    assert payload["failure_code"] == "PROPOSAL_HASH_MISMATCH"
    assert str(tmp_path) not in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("module", "target", "expected_result"),
    (
        (rehearsal_module, "run_rehearsal", "REHEARSAL_REJECTED"),
        (pack_module, "check_pack", "PACK_REJECTED"),
    ),
)
def test_cli_unexpected_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module: object,
    target: str,
    expected_result: str,
) -> None:
    def fail() -> None:
        raise RuntimeError("sensitive path: C:/private/operator")

    monkeypatch.setattr(module, target, fail)
    assert module.main(["--check"]) == 2  # type: ignore[attr-defined]
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["result"] == expected_result
    assert payload["failure_code"] == "UNEXPECTED_FAILURE"
    assert "private" not in captured.out
    assert captured.err == ""
