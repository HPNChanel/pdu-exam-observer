from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_gov_p5_confirmation_request_pack import (  # noqa: E402
    GENERATED_NAMES,
    REVIEWED_NAMES,
    UPSTREAMS,
    PackError,
    canonical_json_bytes,
    check_pack,
    write_pack,
)

PACK_SOURCE = (
    ROOT
    / "research"
    / "institutional_submission"
    / "human_confirmation_request"
    / "v1"
)


def _copy_sources(tmp_path: Path) -> Path:
    target = tmp_path / "pack"
    target.mkdir(parents=True)
    for name in REVIEWED_NAMES:
        shutil.copy2(PACK_SOURCE / name, target / name)
    return target


def _rewrite_body(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    body = document["body"]
    assert isinstance(body, dict)
    mutate(body)
    document["body_sha256"] = hashlib.sha256(
        canonical_json_bytes(body, trailing_newline=False)
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
    assert first["result"] == "CONFIRMATION_REQUEST_PACK_VALIDATED"
    assert first["status"] == (
        "GOV_P5_HUMAN_CONFIRMATION_REQUEST_PACK_LOCALLY_VERIFIED_"
        "PENDING_HUMAN_RESPONSE_NOT_SUBMITTED"
    )
    assert first["audience"] == "FACULTY_ADVISOR_FIRST"
    assert first["human_response_status"] == "PENDING"
    assert first["submission_state"] == "NOT_SUBMITTED"
    assert first["external_transmission_authorized"] is False
    assert first["authority_ceiling"]["collection_authorized"] is False  # type: ignore[index]


def test_default_check_is_read_only_and_cli_output_is_bounded(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_gov_p5_confirmation_request_pack.py"),
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
    assert json.loads(written.stdout)["result"] == "CONFIRMATION_REQUEST_PACK_VALIDATED"

    generated = {name: (pack / name).read_bytes() for name in GENERATED_NAMES}
    checked = subprocess.run([*command, "--check"], check=False, capture_output=True, text=True)
    assert checked.returncode == 0
    assert checked.stderr == ""
    assert {name: (pack / name).read_bytes() for name in GENERATED_NAMES} == generated


def test_source_index_pins_exact_canonical_upstream_paths_and_hashes(
    tmp_path: Path,
) -> None:
    pack = _copy_sources(tmp_path)
    write_pack(pack)
    document = json.loads((pack / "source-index.v1.json").read_text(encoding="utf-8"))
    sources = {item["role"]: item for item in document["body"]["sources"]}

    assert set(sources) == set(UPSTREAMS)
    for role, binding in UPSTREAMS.items():
        assert sources[role]["path"] == binding.relative_path
        assert sources[role]["sha256"] == binding.sha256
        assert binding.path == ROOT / binding.relative_path
        assert "not" in sources[role]["limitation"].lower()


def test_question_matrix_contains_exact_two_pending_questions(tmp_path: Path) -> None:
    pack = _copy_sources(tmp_path)
    write_pack(pack)
    body = json.loads(
        (pack / "confirmation-question-matrix.v1.json").read_text(encoding="utf-8")
    )["body"]
    questions = body["questions"]

    assert body["audience"] == "FACULTY_ADVISOR_FIRST"
    assert body["submission_state"] == "NOT_SUBMITTED"
    assert body["authority_effect"] == "NONE"
    assert body["external_transmission_authorized"] is False
    assert [question["decision_id"] for question in questions] == ["HC-01", "HC-02"]
    assert [question["subject"] for question in questions] == [
        "CURRENT_CYCLE_LATE_SUBMISSION_ACCEPTANCE",
        "HUMAN_SUBJECTS_ETHICS_REVIEW_ROUTE",
    ]
    assert all(question["current_status"] == "PENDING_HUMAN_RESPONSE" for question in questions)
    assert all(question["current_value"] is None for question in questions)
    assert "LATE_SUBMISSION_ACCEPTED_FOR_ROUTING" in questions[0]["allowed_future_outcomes"]
    assert (
        "COVERED_BY_STUDENT_RESEARCH_ROUTE_WITH_AUTHORITY_REFERENCE"
        in questions[1]["allowed_future_outcomes"]
    )


def test_response_template_is_unfilled_and_evidence_rules_remain_fail_closed(
    tmp_path: Path,
) -> None:
    pack = _copy_sources(tmp_path)
    write_pack(pack)
    template = json.loads(
        (pack / "human-confirmation-response.template.v1.json").read_text(
            encoding="utf-8"
        )
    )["body"]
    evidence = (pack / "response-evidence-requirements.vi.v1.md").read_text(
        encoding="utf-8"
    )

    assert template["response_state"] == "UNFILLED"
    assert template["response"] is None
    assert template["evidence_classification"] is None
    assert template["authority_effect"] == "NONE"
    assert template["submission_state"] == "NOT_SUBMITTED"
    for question in template["questions"]:
        assert all(value is None for key, value in question.items() if key != "decision_id")
    assert "USER_STATED_UNVERIFIED" in evidence
    assert "authority hoặc policy reference" in evidence
    assert "không phải response record" in evidence


def test_forged_response_approval_and_authority_mutations_are_rejected(
    tmp_path: Path,
) -> None:
    def mark_question_answered(body: dict[str, object]) -> None:
        questions = body["questions"]
        assert isinstance(questions, list)
        question = questions[0]
        assert isinstance(question, dict)
        question["current_status"] = "SATISFIED"
        question["current_value"] = "LATE_SUBMISSION_ACCEPTED_FOR_ROUTING"

    def authorize_transmission(body: dict[str, object]) -> None:
        body["external_transmission_authorized"] = True

    def complete_template(body: dict[str, object]) -> None:
        body["response_state"] = "COMPLETED"

    def fill_evidence(body: dict[str, object]) -> None:
        questions = body["questions"]
        assert isinstance(questions, list)
        question = questions[1]
        assert isinstance(question, dict)
        question["answer_code"] = "HUMAN_SUBJECTS_REVIEW_NOT_REQUIRED"
        question["evidence_reference"] = "fabricated"

    def add_approval(body: dict[str, object]) -> None:
        body["approval_id"] = "FAKE-APPROVAL"

    def open_collection(body: dict[str, object]) -> None:
        body["research_ready"] = True
        body["collection_authorized"] = True

    matrix = "confirmation-question-matrix.v1.json"
    template = "human-confirmation-response.template.v1.json"
    cases = (
        (matrix, mark_question_answered),
        (matrix, authorize_transmission),
        (template, complete_template),
        (template, fill_evidence),
        (template, add_approval),
        (template, open_collection),
    )
    for index, (name, mutation) in enumerate(cases):
        pack = _copy_sources(tmp_path / str(index))
        _rewrite_body(pack / name, mutation)
        with pytest.raises(PackError, match="AUTHORITY_CEILING_VIOLATION"):
            write_pack(pack)


def test_closed_file_set_links_noncanonical_json_and_generated_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    pack = _copy_sources(tmp_path / "extra")
    (pack / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "link")
    link = pack / "unexpected-link"
    try:
        os.symlink(pack / "source-index.v1.json", link)
    except OSError:
        link.mkdir()
    with pytest.raises(PackError, match="FILE_SET_MISMATCH"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "json")
    matrix = pack / "confirmation-question-matrix.v1.json"
    matrix.write_bytes(matrix.read_bytes() + b" ")
    with pytest.raises(PackError, match="NONCANONICAL_JSON"):
        write_pack(pack)

    pack = _copy_sources(tmp_path / "manifest")
    write_pack(pack)
    manifest = pack / "gov-p5-confirmation-request.manifest.v1.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(PackError, match="MANIFEST_MISMATCH"):
        check_pack(pack)


def test_proposal_gov_p2_p3_p4_rp2_and_package_inputs_remain_immutable(
    tmp_path: Path,
) -> None:
    protected = tuple(binding.path for binding in UPSTREAMS.values()) + (
        ROOT / "docs" / "spec" / "M2_D1_N2_STATIC_BINDING_CANDIDATE.json",
        ROOT / "packaging" / "RELEASE_MANIFEST.json",
    )
    before = {path: _sha(path) for path in protected}

    write_pack(_copy_sources(tmp_path))

    assert {path: _sha(path) for path in protected} == before
